#!/usr/bin/env python3
"""
modules/models/calendar.py

Data models for the 3-Layer Dynamic Academic Calendar, Holiday & Suspension Engine.
Supports:
  - Recurrence rules (fixed date, nth weekday)
  - Normalized calendar exceptions from .ics and natural text/CSV
  - Per-date interactive overrides (ACTIVE, HOLIDAY, SUSPENDED, EXAM, EVENT)
  - Rendering mode policies (OMIT_COLUMN vs. STAMP_COLUMN)
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union


class CalendarExceptionCategory:
    HOLIDAY = "HOLIDAY"
    SUSPENSION = "SUSPENDED"
    SUSPENDED = "SUSPENDED"
    WEATHER_SUSPENSION = "SUSPENDED"
    INSTRUCTOR_LEAVE = "INSTRUCTOR_LEAVE"
    LEAVE = "INSTRUCTOR_LEAVE"
    ADM_ASYNC = "ADM_ASYNC"
    ADM = "ADM_ASYNC"
    EXAM = "EXAM"
    EXAM_WEEK = "EXAM"
    EVENT = "EVENT"
    ACTIVE = "ACTIVE"


class CalendarTimeScope:
    ALL_DAY = "ALL_DAY"
    MIDDAY_ONWARDS = "MIDDAY_ONWARDS"      # 12:00 NN onwards (Aug 14)
    AFTERNOON_1PM = "AFTERNOON_1PM"        # 1:00 PM onwards (Aug 28 MC 132)
    MORNING_ONLY = "MORNING_ONLY"          # 00:00 - 12:00 NN
    CUSTOM_TIME = "CUSTOM_TIME"            # specific start_time / end_time


class CalendarExceptionMode:
    OMIT_COLUMN = "OMIT_COLUMN"
    STAMP_COLUMN = "STAMP_COLUMN"


CATEGORY_TAG_MAP = {
    CalendarExceptionCategory.HOLIDAY: "HOLIDAY",
    CalendarExceptionCategory.SUSPENDED: "SUSP.",
    CalendarExceptionCategory.INSTRUCTOR_LEAVE: "LEAVE",
    CalendarExceptionCategory.ADM_ASYNC: "ADM",
    CalendarExceptionCategory.EXAM: "EXAM",
    CalendarExceptionCategory.EVENT: "EVENT",
    CalendarExceptionCategory.ACTIVE: "",
}


@dataclass
class ResolvedDateInfo:
    date: date
    status: str  # ACTIVE, HOLIDAY, SUSPENDED, INSTRUCTOR_LEAVE, ADM_ASYNC, EXAM, EVENT
    label: str = ""
    mode: str = CalendarExceptionMode.OMIT_COLUMN
    display_tag: str = ""
    time_scope: str = CalendarTimeScope.ALL_DAY

    @property
    def is_working_session(self) -> bool:
        return self.status == CalendarExceptionCategory.ACTIVE


@dataclass
class CalendarException:
    start_date: date
    end_date: date
    label: str
    category: str = CalendarExceptionCategory.HOLIDAY
    time_scope: str = CalendarTimeScope.ALL_DAY
    start_time: Optional[str] = None  # e.g. "12:00", "13:00"
    end_time: Optional[str] = None    # e.g. "23:59"
    mode: Optional[str] = None
    raw_source: str = ""

    def __post_init__(self):
        if isinstance(self.start_date, str):
            self.start_date = date.fromisoformat(self.start_date)
        if isinstance(self.end_date, str):
            self.end_date = date.fromisoformat(self.end_date)
        if self.start_date > self.end_date:
            self.start_date, self.end_date = self.end_date, self.start_date

        cat = (self.category or "HOLIDAY").upper()
        if cat in ("SUSPENSION", "SUSPENDED", "WALANGPASOK", "WEATHER_SUSPENSION"):
            self.category = CalendarExceptionCategory.SUSPENDED
        elif cat in ("INSTRUCTOR_LEAVE", "LEAVE", "PERSONAL_LEAVE", "ON_LEAVE"):
            self.category = CalendarExceptionCategory.INSTRUCTOR_LEAVE
        elif cat in ("ADM_ASYNC", "ADM", "ASYNC", "ASYNCHRONOUS", "ONLINE"):
            self.category = CalendarExceptionCategory.ADM_ASYNC
        elif cat in ("EXAM", "EXAMINATION", "EXAM_WEEK"):
            self.category = CalendarExceptionCategory.EXAM
        elif cat in ("HOLIDAY", "HOLIDAYS"):
            self.category = CalendarExceptionCategory.HOLIDAY
        elif cat == "ACTIVE":
            self.category = CalendarExceptionCategory.ACTIVE
        else:
            self.category = CalendarExceptionCategory.EVENT

        # Auto-detect time_scope if not explicitly set
        if not self.time_scope or self.time_scope == CalendarTimeScope.ALL_DAY:
            low_label = self.label.lower()
            if "12:00" in low_label or "12 nn" in low_label or "12nn" in low_label or "midday" in low_label:
                self.time_scope = CalendarTimeScope.MIDDAY_ONWARDS
                if not self.start_time:
                    self.start_time = "12:00"
            elif "1:00" in low_label or "1pm" in low_label or "1 pm" in low_label or "13:00" in low_label:
                self.time_scope = CalendarTimeScope.AFTERNOON_1PM
                if not self.start_time:
                    self.start_time = "13:00"

    def get_effective_minutes_window(self) -> Tuple[int, int]:
        """Returns (start_minute, end_minute) from midnight (0 to 1440)."""
        if self.time_scope == CalendarTimeScope.MIDDAY_ONWARDS:
            return (12 * 60, 24 * 60)
        elif self.time_scope == CalendarTimeScope.AFTERNOON_1PM:
            return (13 * 60, 24 * 60)
        elif self.time_scope == CalendarTimeScope.MORNING_ONLY:
            return (0, 12 * 60)
        elif self.time_scope == CalendarTimeScope.CUSTOM_TIME and self.start_time:
            try:
                s_h, s_m = map(int, self.start_time.split(":"))
                e_h, e_m = map(int, (self.end_time or "23:59").split(":"))
                return (s_h * 60 + s_m, e_h * 60 + e_m)
            except Exception:
                pass
        return (0, 24 * 60)

    def spans_date(self, target: Union[date, str]) -> bool:
        if isinstance(target, str):
            target = date.fromisoformat(target)
        return self.start_date <= target <= self.end_date

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "label": self.label,
            "category": self.category,
            "time_scope": self.time_scope,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "mode": self.mode,
            "raw_source": self.raw_source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CalendarException:
        start_d = data.get("start_date")
        end_d = data.get("end_date") or start_d
        if isinstance(start_d, str):
            start_d = date.fromisoformat(start_d)
        if isinstance(end_d, str):
            end_d = date.fromisoformat(end_d)

        return cls(
            start_date=start_d,
            end_date=end_d,
            label=str(data.get("label", "")),
            category=str(data.get("category", CalendarExceptionCategory.HOLIDAY)).upper(),
            time_scope=str(data.get("time_scope", CalendarTimeScope.ALL_DAY)),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            mode=str(data["mode"]).upper() if data.get("mode") is not None else None,
            raw_source=str(data.get("raw_source", "")),
        )


@dataclass
class RecurrenceRule:
    rule_type: str  # "fixed_date" or "nth_weekday"
    name: str
    category: str = CalendarExceptionCategory.HOLIDAY
    month: int = 1
    day: Optional[int] = None
    weekday: Optional[int] = None  # 0=Monday ... 6=Sunday
    nth: Optional[Union[int, str]] = None  # 1, 2, 3, 4, -1, "last"
    mode: Optional[str] = None

    def resolve_for_year(self, year: int) -> CalendarException:
        if self.rule_type == "fixed_date":
            if self.day is None:
                raise ValueError(f"Fixed date recurrence rule '{self.name}' missing day")
            d = date(year, self.month, self.day)
            return CalendarException(
                start_date=d,
                end_date=d,
                label=self.name,
                category=self.category,
                mode=self.mode,
                raw_source="recurrence_rule",
            )
        elif self.rule_type == "nth_weekday":
            if self.weekday is None or self.nth is None:
                raise ValueError(f"Nth-weekday recurrence rule '{self.name}' requires weekday and nth")
            from modules.parsers.calendar_resolver import compute_nth_weekday
            d = compute_nth_weekday(year, self.month, self.weekday, self.nth)
            return CalendarException(
                start_date=d,
                end_date=d,
                label=self.name,
                category=self.category,
                mode=self.mode,
                raw_source="recurrence_rule",
            )
        else:
            raise ValueError(f"Unknown recurrence rule type: {self.rule_type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_type": self.rule_type,
            "name": self.name,
            "category": self.category,
            "month": self.month,
            "day": self.day,
            "weekday": self.weekday,
            "nth": self.nth,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecurrenceRule:
        return cls(
            rule_type=data.get("rule_type", "fixed_date"),
            name=data.get("name", "Holiday"),
            category=data.get("category", CalendarExceptionCategory.HOLIDAY),
            month=int(data.get("month", 1)),
            day=int(data["day"]) if data.get("day") is not None else None,
            weekday=int(data["weekday"]) if data.get("weekday") is not None else None,
            nth=data.get("nth"),
            mode=data.get("mode", CalendarExceptionMode.OMIT_COLUMN),
        )


# ── Built-in Academic Presets Library ─────────────────────────────────────────

CVSU_INDANG_2026_PRESET: List[Dict[str, Any]] = [
    {
        "start_date": "2026-08-10",
        "end_date": "2026-08-10",
        "label": "Habagat Monsoon Rain (LGU Indang / Provincial)",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-08-14",
        "end_date": "2026-08-14",
        "label": "Habagat Monsoon Rain (Suspended at 12:00 NN)",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.MIDDAY_ONWARDS,
        "start_time": "12:00",
        "end_time": "23:59",
    },
    {
        "start_date": "2026-08-17",
        "end_date": "2026-08-17",
        "label": "Torrential Monsoon Rains / Online ADM Shift",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-08-19",
        "end_date": "2026-08-19",
        "label": "Habagat & Tropical Depression Neneng",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-08-20",
        "end_date": "2026-08-20",
        "label": "Habagat Weather Disturbances (Shift to ADM)",
        "category": CalendarExceptionCategory.ADM_ASYNC,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-08-21",
        "end_date": "2026-08-21",
        "label": "Ninoy Aquino Day (Special Non-Working Holiday)",
        "category": CalendarExceptionCategory.HOLIDAY,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-08-28",
        "end_date": "2026-08-28",
        "label": "MC No. 132 Monsoon (Suspended starting 1:00 PM)",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.AFTERNOON_1PM,
        "start_time": "13:00",
        "end_time": "23:59",
    },
    {
        "start_date": "2026-08-29",
        "end_date": "2026-08-29",
        "label": "Weekend Monsoon Downpours (Habagat / LPA)",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-08-31",
        "end_date": "2026-08-31",
        "label": "National Heroes Day (Regular Holiday)",
        "category": CalendarExceptionCategory.HOLIDAY,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-09-02",
        "end_date": "2026-09-02",
        "label": "Cavite Day (Provincial Holiday)",
        "category": CalendarExceptionCategory.HOLIDAY,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-09-03",
        "end_date": "2026-09-03",
        "label": "Persistent Habagat (Shift to ADM)",
        "category": CalendarExceptionCategory.ADM_ASYNC,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-09-04",
        "end_date": "2026-09-04",
        "label": "Malacañang Advisory (In-person suspension / Shift to ADM)",
        "category": CalendarExceptionCategory.ADM_ASYNC,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-09-07",
        "end_date": "2026-09-07",
        "label": "Heavy Rainfall / Flood Alert (LGU Indang / PAGASA)",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-09-08",
        "end_date": "2026-09-08",
        "label": "Severe Monsoon Rain (Habagat)",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
    {
        "start_date": "2026-10-05",
        "end_date": "2026-10-05",
        "label": "World / National Teachers' Day Observance",
        "category": CalendarExceptionCategory.SUSPENDED,
        "time_scope": CalendarTimeScope.ALL_DAY,
    },
]

CALENDAR_PRESETS: Dict[str, Dict[str, Any]] = {
    "cvsu_indang_2026_sem1": {
        "id": "cvsu_indang_2026_sem1",
        "name": "CvSU Main (Indang) — 1st Semester 2026-2027 (Aug–Oct Verified)",
        "description": "15 verified Habagat weather suspensions, Malacañang proclamations, Cavite Day, and Teachers' Day disruptions.",
        "exceptions": CVSU_INDANG_2026_PRESET,
    }
}

