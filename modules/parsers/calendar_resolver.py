#!/usr/bin/env python3
"""
modules/parsers/calendar_resolver.py

100% Offline, 3-Layer Dynamic Academic Calendar, Holiday & Suspension Engine.

Architecture:
  - Layer 1: Algorithmic Recurrence Rule Engine (fixed dates & Nth weekdays across any target year).
  - Layer 2: Offline .ics (iCalendar) parser & smart natural text/CSV announcement parser.
  - Layer 3: Per-date interactive overrides taking priority over Layers 1 & 2.
  - Matrix Policies: Resolves dates into OMIT_COLUMN (removes column) or STAMP_COLUMN (stamps label).
"""

from __future__ import annotations

import calendar
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from modules.common.logger import logger
from modules.models.calendar import (
    CalendarException,
    CalendarExceptionCategory,
    CalendarExceptionMode,
    CATEGORY_TAG_MAP,
    RecurrenceRule,
    ResolvedDateInfo,
)


def compute_nth_weekday(year: int, month: int, weekday: int, nth: Union[int, str]) -> date:
    """
    Computes the date of the Nth weekday in a given month and year.
    weekday: 0=Monday ... 6=Sunday
    nth: 1, 2, 3, 4, 5, -1, or "last"
    """
    _, ndays = calendar.monthrange(year, month)
    
    if nth == "last" or nth == -1:
        # Walk backwards from the last day of the month
        for d in range(ndays, 0, -1):
            if date(year, month, d).weekday() == weekday:
                return date(year, month, d)
        raise ValueError(f"No weekday {weekday} found in {year}-{month:02d}")
    
    nth_int = int(nth)
    if nth_int <= 0:
        raise ValueError(f"Positive nth or 'last' expected, got {nth}")
    
    count = 0
    for d in range(1, ndays + 1):
        if date(year, month, d).weekday() == weekday:
            count += 1
            if count == nth_int:
                return date(year, month, d)
                
    raise ValueError(f"Occurrence {nth_int} of weekday {weekday} does not exist in {year}-{month:02d}")


def get_default_cavite_recurrence_rules() -> List[RecurrenceRule]:
    """
    Default national and Cavite provincial holidays resolved dynamically for any year.
    """
    return [
        RecurrenceRule("fixed_date", "New Year's Day", CalendarExceptionCategory.HOLIDAY, month=1, day=1),
        RecurrenceRule("fixed_date", "Araw ng Kagitingan", CalendarExceptionCategory.HOLIDAY, month=4, day=9),
        RecurrenceRule("fixed_date", "Labor Day", CalendarExceptionCategory.HOLIDAY, month=5, day=1),
        RecurrenceRule("fixed_date", "Independence Day", CalendarExceptionCategory.HOLIDAY, month=6, day=12),
        RecurrenceRule("fixed_date", "Ninoy Aquino Day", CalendarExceptionCategory.HOLIDAY, month=8, day=21),
        RecurrenceRule("fixed_date", "Cavite Day", CalendarExceptionCategory.HOLIDAY, month=9, day=2),
        RecurrenceRule("fixed_date", "All Saints' Day", CalendarExceptionCategory.HOLIDAY, month=11, day=1),
        RecurrenceRule("fixed_date", "All Souls' Day", CalendarExceptionCategory.HOLIDAY, month=11, day=2),
        RecurrenceRule("fixed_date", "Bonifacio Day", CalendarExceptionCategory.HOLIDAY, month=11, day=30),
        RecurrenceRule("fixed_date", "Feast of the Immaculate Conception", CalendarExceptionCategory.HOLIDAY, month=12, day=8),
        RecurrenceRule("fixed_date", "Christmas Eve", CalendarExceptionCategory.HOLIDAY, month=12, day=24),
        RecurrenceRule("fixed_date", "Christmas Day", CalendarExceptionCategory.HOLIDAY, month=12, day=25),
        RecurrenceRule("fixed_date", "Rizal Day", CalendarExceptionCategory.HOLIDAY, month=12, day=30),
        RecurrenceRule("fixed_date", "New Year's Eve", CalendarExceptionCategory.HOLIDAY, month=12, day=31),
        RecurrenceRule("nth_weekday", "National Heroes Day", CalendarExceptionCategory.HOLIDAY, month=8, weekday=0, nth="last"),
    ]


def _categorize_label(label: str) -> str:
    """Auto-categorizes calendar events based on institutional keywords."""
    low = label.lower()
    if any(k in low for k in ("exam", "examination", "midterm", "finals", "test")):
        return CalendarExceptionCategory.EXAM
    if any(k in low for k in ("suspension", "suspended", "walang pasok", "walangpasok", "typhoon", "bagyo", "flood", "strike", "weather", "storm", "rain")):
        return CalendarExceptionCategory.SUSPENSION
    if any(k in low for k in ("holiday", "araw", "day", "christmas", "new year", "heroes", "saints", "souls", "bonifacio", "rizal")):
        return CalendarExceptionCategory.HOLIDAY
    return CalendarExceptionCategory.EVENT


def _parse_ical_date(val_str: str) -> Tuple[date, bool]:
    """
    Parses iCalendar date string:
    - 20261020 -> (date(2026, 10, 20), True) [is_all_day = True]
    - 20261020T080000Z -> (date(2026, 10, 20), False)
    """
    clean_val = val_str.strip()
    if "T" in clean_val:
        date_part = clean_val.split("T", 1)[0]
        y = int(date_part[:4])
        m = int(date_part[4:6])
        d = int(date_part[6:8])
        return date(y, m, d), False
    else:
        y = int(clean_val[:4])
        m = int(clean_val[4:6])
        d = int(clean_val[6:8])
        return date(y, m, d), True


def parse_ics_content(ics_text: str) -> List[CalendarException]:
    """
    Offline .ics parser adhering to RFC 5545 using Python stdlib.
    Unfolds lines, parses VEVENT blocks, and normalizes date ranges.
    """
    lines: List[str] = []
    for raw_line in ics_text.splitlines():
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line.strip())

    exceptions: List[CalendarException] = []
    in_event = False
    current_summary = ""
    current_start: Optional[date] = None
    current_end: Optional[date] = None
    is_all_day_end = False

    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event = True
            current_summary = ""
            current_start = None
            current_end = None
            is_all_day_end = False
        elif line == "END:VEVENT":
            if in_event and current_start is not None:
                label = current_summary or "Calendar Event"
                category = _categorize_label(label)
                if current_end is None:
                    end_d = current_start
                else:
                    # RFC 5545: DTEND for DATE values is exclusive
                    if is_all_day_end and current_end > current_start:
                        end_d = current_end - timedelta(days=1)
                    else:
                        end_d = current_end

                exceptions.append(CalendarException(
                    start_date=current_start,
                    end_date=end_d,
                    label=label,
                    category=category,
                    raw_source="ics",
                ))
            in_event = False
        elif in_event:
            if line.startswith("SUMMARY:"):
                current_summary = line.split(":", 1)[1].replace("\\,", ",").replace("\\;", ";").strip()
            elif line.startswith("DTSTART"):
                val = line.split(":", 1)[1].strip()
                dt, _ = _parse_ical_date(val)
                current_start = dt
            elif line.startswith("DTEND"):
                val = line.split(":", 1)[1].strip()
                dt, is_all_day = _parse_ical_date(val)
                current_end = dt
                is_all_day_end = is_all_day

    return exceptions


# Month dictionary for text parser
_MONTH_DICT = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_announcement_lines(text: str, default_year: Optional[int] = None) -> List[CalendarException]:
    """
    Parses announcement text or CSV lines into normalized CalendarException objects.
    Supports:
      - "Oct 20-24, 2026: Midterm Examination Week"
      - "Nov 2, 2026 - All Souls' Day"
      - "Aug 24, 2026: Typhoon Suspension"
      - "2026-09-02: Cavite Day"
      - "2026-12-14 to 2026-12-18, Final Examination Week, EXAM, STAMP_COLUMN"
      - "#WalangPasok: Sept 25, 2026 - Heavy Rain Suspension"
    """
    if default_year is None:
        default_year = date.today().year

    exceptions: List[CalendarException] = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Month name regex
    m_pattern = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

    for line in lines:
        # Ignore comments that don't contain #walangpasok
        if line.startswith("#") and "walangpasok" not in line.lower():
            continue

        raw_line = line
        if line.lower().startswith("#walangpasok"):
            # Strip hashtag prefix but record suspension hint
            line = re.sub(r"^#walangpasok\s*[:\-]?\s*", "", line, flags=re.IGNORECASE)

        # 1. Natural language pattern with colon or spaced dash separator
        # e.g., "Oct 20-24, 2026: Midterm Examination" or "Nov 2, 2026 - All Souls' Day"
        date_candidate = ""
        label_candidate = ""
        handled_sep = False

        if ":" in line:
            parts = line.split(":", 1)
            cand_d, cand_lbl = parts[0].strip(), parts[1].strip()
            if _parse_date_range_token(cand_d, default_year) or _parse_date_range_token(cand_lbl, default_year):
                date_candidate, label_candidate = cand_d, cand_lbl
                handled_sep = True
        
        if not handled_sep and re.search(r"\s+[\-–]\s+", line):
            m = re.search(r"\s+[\-–]\s+", line)
            cand_d, cand_lbl = line[:m.start()].strip(), line[m.end():].strip()
            if _parse_date_range_token(cand_d, default_year) or _parse_date_range_token(cand_lbl, default_year):
                date_candidate, label_candidate = cand_d, cand_lbl
                handled_sep = True

        # 2. Try CSV format: date_or_range, label, [category], [mode]
        if not handled_sep:
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2 and any(sep in parts[0] for sep in ("-", "/", "to")):
                date_part = parts[0]
                label = parts[1]
                cat = parts[2].upper() if len(parts) >= 3 else _categorize_label(label)
                mode = parts[3].upper() if len(parts) >= 4 else CalendarExceptionMode.OMIT_COLUMN

                parsed_dates = _parse_date_range_token(date_part, default_year)
                if parsed_dates:
                    start_d, end_d = parsed_dates
                    exceptions.append(CalendarException(
                        start_date=start_d,
                        end_date=end_d,
                        label=label,
                        category=cat,
                        mode=mode,
                        raw_source="csv_announcement",
                    ))
                    continue

        if not handled_sep and re.search(r"[\-–]\s*", line):
            m_direct = re.search(r"[\-–]\s*", line)
            if _parse_date_range_token(line[:m_direct.start()].strip(), default_year):
                date_candidate = line[:m_direct.start()].strip()
                label_candidate = line[m_direct.end():].strip()

        if date_candidate and label_candidate:
            parsed_dates = _parse_date_range_token(date_candidate, default_year)
            if not parsed_dates:
                # Invert search: maybe format was "Midterm Exam - Oct 20-24, 2026"
                parsed_dates = _parse_date_range_token(label_candidate, default_year)
                if parsed_dates:
                    label_candidate = date_candidate

            if parsed_dates and label_candidate:
                start_d, end_d = parsed_dates
                category = _categorize_label(label_candidate)
                if "walangpasok" in raw_line.lower():
                    category = CalendarExceptionCategory.SUSPENSION

                exceptions.append(CalendarException(
                    start_date=start_d,
                    end_date=end_d,
                    label=label_candidate,
                    category=category,
                    raw_source="text_announcement",
                ))
                continue

        # 3. Direct date range without separator
        parsed_dates = _parse_date_range_token(line, default_year)
        if parsed_dates:
            start_d, end_d = parsed_dates
            exceptions.append(CalendarException(
                start_date=start_d,
                end_date=end_d,
                label="Calendar Exception",
                category=_categorize_label(line),
                raw_source="text_announcement",
            ))

    return exceptions


def _parse_date_range_token(token: str, default_year: int) -> Optional[Tuple[date, date]]:
    """Helper to parse varied date and date-range tokens."""
    token = token.strip()
    
    # ISO Range: "2026-10-20 to 2026-10-24" or "2026-10-20 - 2026-10-24"
    iso_range = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(?:to|-|–)\s*(\d{4}-\d{2}-\d{2})$", token)
    if iso_range:
        return date.fromisoformat(iso_range.group(1)), date.fromisoformat(iso_range.group(2))

    # Single ISO: "2026-09-02"
    iso_single = re.match(r"^(\d{4}-\d{2}-\d{2})$", token)
    if iso_single:
        d = date.fromisoformat(iso_single.group(1))
        return d, d

    m_names = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

    # Range within same month: "Oct 20-24, 2026" or "October 20 - 24, 2026"
    same_month_range = re.match(rf"^{m_names}\s+(\d{{1,2}})\s*(?:-|–|to)\s*(\d{{1,2}})(?:,?\s*(\d{{4}}))?$", token, re.IGNORECASE)
    if same_month_range:
        m_str = same_month_range.group(1).lower()
        m = _MONTH_DICT[m_str]
        d1 = int(same_month_range.group(2))
        d2 = int(same_month_range.group(3))
        y = int(same_month_range.group(4)) if same_month_range.group(4) else default_year
        return date(y, m, d1), date(y, m, d2)

    # Range across different months: "Oct 28 - Nov 2, 2026"
    diff_month_range = re.match(rf"^{m_names}\s+(\d{{1,2}})\s*(?:-|–|to)\s*{m_names}\s+(\d{{1,2}})(?:,?\s*(\d{{4}}))?$", token, re.IGNORECASE)
    if diff_month_range:
        m1 = _MONTH_DICT[diff_month_range.group(1).lower()]
        d1 = int(diff_month_range.group(2))
        m2 = _MONTH_DICT[diff_month_range.group(3).lower()]
        d2 = int(diff_month_range.group(4))
        y = int(diff_month_range.group(5)) if diff_month_range.group(5) else default_year
        return date(y, m1, d1), date(y, m2, d2)

    # Single month day: "Nov 2, 2026" or "November 2, 2026"
    single_date = re.match(rf"^{m_names}\s+(\d{{1,2}})(?:,?\s*(\d{{4}}))?$", token, re.IGNORECASE)
    if single_date:
        m = _MONTH_DICT[single_date.group(1).lower()]
        d = int(single_date.group(2))
        y = int(single_date.group(3)) if single_date.group(3) else default_year
        return date(y, m, d), date(y, m, d)

    return None


class CalendarResolver:
    """
    3-Layer Dynamic Calendar Resolver:
      Layer 1: Recurrence rules (fixed & nth weekday)
      Layer 2: Parsed .ics and announcement text exceptions
      Layer 3: Single-date interactive overrides (highest priority)
    """

    def __init__(
        self,
        rules: Optional[List[RecurrenceRule]] = None,
        exceptions: Optional[List[CalendarException]] = None,
        overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        default_mode: str = CalendarExceptionMode.OMIT_COLUMN,
    ):
        self.rules = rules if rules is not None else get_default_cavite_recurrence_rules()
        self.exceptions: List[CalendarException] = exceptions or []
        # overrides format: { "YYYY-MM-DD": { "status": "ACTIVE|HOLIDAY|...", "label": "...", "mode": "..." } }
        self.overrides: Dict[str, Dict[str, Any]] = overrides or {}
        self.default_mode = default_mode

    def add_exception(self, exception: CalendarException) -> None:
        self.exceptions.append(exception)

    def set_date_override(
        self,
        target_date: Union[date, str],
        status: str,
        label: str = "",
        mode: Optional[str] = None,
    ) -> None:
        d_str = target_date.isoformat() if isinstance(target_date, date) else target_date
        self.overrides[d_str] = {
            "status": status.upper(),
            "label": label,
            "mode": (mode or self.default_mode).upper(),
        }

    def clear_date_override(self, target_date: Union[date, str]) -> None:
        d_str = target_date.isoformat() if isinstance(target_date, date) else target_date
        self.overrides.pop(d_str, None)

    def get_recurring_holidays(self, year: int) -> List[CalendarException]:
        res = []
        for r in self.rules:
            try:
                res.append(r.resolve_for_year(year))
            except Exception as e:
                logger.warning(f"Failed resolving recurrence rule '{r.name}' for {year}: {e}")
        return res

    def resolve_date(self, target_date: date) -> ResolvedDateInfo:
        """
        Resolves a single date across all 3 layers.
        Precedence:
          1. Layer 3: Interactive Overrides
          2. Layer 2: Manual Exceptions (.ics / Announcements)
          3. Layer 1: Recurrence Rules
          4. Default: ACTIVE
        """
        d_iso = target_date.isoformat()

        # Layer 3: Overrides
        if d_iso in self.overrides:
            ov = self.overrides[d_iso]
            if isinstance(ov, str):
                status = ov.upper()
                label = ""
                mode = self.default_mode.upper()
            else:
                status = ov.get("status", CalendarExceptionCategory.ACTIVE).upper()
                label = ov.get("label", "")
                mode = ov.get("mode", self.default_mode).upper()
            tag = CATEGORY_TAG_MAP.get(status, "")
            return ResolvedDateInfo(
                date=target_date,
                status=status,
                label=label,
                mode=mode,
                display_tag=tag,
            )

        # Layer 2: Exceptions (latest takes priority)
        for exc in reversed(self.exceptions):
            if exc.spans_date(target_date):
                mode = (exc.mode or self.default_mode).upper()
                tag = CATEGORY_TAG_MAP.get(exc.category, "HOLIDAY")
                return ResolvedDateInfo(
                    date=target_date,
                    status=exc.category,
                    label=exc.label,
                    mode=mode,
                    display_tag=tag,
                )

        # Layer 1: Recurring Holidays
        for exc in self.get_recurring_holidays(target_date.year):
            if exc.spans_date(target_date):
                mode = (exc.mode or self.default_mode).upper()
                tag = CATEGORY_TAG_MAP.get(exc.category, "HOLIDAY")
                return ResolvedDateInfo(
                    date=target_date,
                    status=exc.category,
                    label=exc.label,
                    mode=mode,
                    display_tag=tag,
                )

        # Default: Active session
        return ResolvedDateInfo(
            date=target_date,
            status=CalendarExceptionCategory.ACTIVE,
            label="",
            mode=self.default_mode,
            display_tag="",
        )

    def filter_or_stamp_dates(
        self,
        class_dates: List[date],
        default_mode: Optional[str] = None,
    ) -> Tuple[List[date], Dict[int, str]]:
        """
        Processes candidate class dates according to resolved modes.
        Returns:
          - filtered_dates: The final list of dates for attendance columns.
          - stamped_column_tags: Map of col_idx -> status tag (e.g. {3: "SUSP.", 4: "HOLIDAY"}).
        """
        mode_policy = (default_mode or self.default_mode).upper()
        final_dates: List[date] = []
        stamped_tags: Dict[int, str] = {}

        for dt in class_dates:
            info = self.resolve_date(dt)
            if info.is_working_session:
                final_dates.append(dt)
            else:
                # Non-working date (HOLIDAY, SUSPENDED, EXAM, EVENT)
                effective_mode = (info.mode or mode_policy).upper()
                if effective_mode == CalendarExceptionMode.OMIT_COLUMN:
                    # Exclude non-working date from column sequence
                    continue
                else:
                    # STAMP_COLUMN: Keep date and assign display tag
                    col_idx = len(final_dates)
                    final_dates.append(dt)
                    stamped_tags[col_idx] = info.display_tag or "HOLIDAY"

        return final_dates, stamped_tags

    def preview_semester_dates(
        self,
        year: int,
        months: List[int],
        weekdays: List[int],
        start_bound: Optional[Tuple[int, int]] = None,
        end_bound: Optional[Tuple[int, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates full metadata for UI strip rendering of candidate dates in a semester.
        """
        from modules.generators.attendance_gen import get_class_dates_for_weekdays
        raw_dates = get_class_dates_for_weekdays(months, year, weekdays, start_bound, end_bound)
        preview: List[Dict[str, Any]] = []

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for dt in raw_dates:
            res = self.resolve_date(dt)
            preview.append({
                "date": dt.isoformat(),
                "date_str": dt.isoformat(),
                "day": dt.day,
                "month": dt.month,
                "year": dt.year,
                "weekday": dt.weekday(),
                "weekday_name": day_names[dt.weekday()],
                "status": res.status,
                "category": res.status,
                "label": res.label,
                "mode": res.mode,
                "display_tag": res.display_tag,
                "is_active": res.is_working_session,
                "is_working": res.is_working_session,
            })
        return preview

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_mode": self.default_mode,
            "rules": [r.to_dict() for r in self.rules],
            "exceptions": [e.to_dict() for e in self.exceptions],
            "overrides": self.overrides,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CalendarResolver:
        rules = [RecurrenceRule.from_dict(r) for r in data.get("rules", [])] if "rules" in data else None
        exceptions = [CalendarException.from_dict(e) for e in data.get("exceptions", [])]
        overrides = data.get("overrides", {})
        default_mode = data.get("default_mode", CalendarExceptionMode.OMIT_COLUMN)
        return cls(rules=rules, exceptions=exceptions, overrides=overrides, default_mode=default_mode)
