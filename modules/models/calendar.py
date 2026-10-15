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
from typing import Any, Dict, List, Optional, Union


class CalendarExceptionCategory:
    HOLIDAY = "HOLIDAY"
    SUSPENSION = "SUSPENDED"
    SUSPENDED = "SUSPENDED"
    EXAM = "EXAM"
    EXAM_WEEK = "EXAM"
    EVENT = "EVENT"
    ACTIVE = "ACTIVE"


class CalendarExceptionMode:
    OMIT_COLUMN = "OMIT_COLUMN"
    STAMP_COLUMN = "STAMP_COLUMN"


CATEGORY_TAG_MAP = {
    CalendarExceptionCategory.HOLIDAY: "HOLIDAY",
    CalendarExceptionCategory.SUSPENDED: "SUSP.",
    CalendarExceptionCategory.EXAM: "EXAM",
    CalendarExceptionCategory.EVENT: "EVENT",
    CalendarExceptionCategory.ACTIVE: "",
}


@dataclass
class ResolvedDateInfo:
    date: date
    status: str  # ACTIVE, HOLIDAY, SUSPENDED, EXAM, EVENT
    label: str = ""
    mode: str = CalendarExceptionMode.OMIT_COLUMN
    display_tag: str = ""

    @property
    def is_working_session(self) -> bool:
        return self.status == CalendarExceptionCategory.ACTIVE


@dataclass
class CalendarException:
    start_date: date
    end_date: date
    label: str
    category: str = CalendarExceptionCategory.HOLIDAY
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
        if cat in ("SUSPENSION", "SUSPENDED", "WALANGPASOK"):
            self.category = CalendarExceptionCategory.SUSPENDED
        elif cat in ("EXAM", "EXAMINATION", "EXAM_WEEK"):
            self.category = CalendarExceptionCategory.EXAM
        elif cat in ("HOLIDAY", "HOLIDAYS"):
            self.category = CalendarExceptionCategory.HOLIDAY
        elif cat == "ACTIVE":
            self.category = CalendarExceptionCategory.ACTIVE
        else:
            self.category = CalendarExceptionCategory.EVENT

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
