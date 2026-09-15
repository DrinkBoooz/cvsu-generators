#!/usr/bin/env python3
"""
modules/generators/field_resolver.py

Centralized runtime field-resolution engine for generic document generation.
Maps recipe-declared fields to authoritative ClassInfo data, deterministic derived
values, and explicit recipe metadata. Enforces non-fabrication rules (Rule A),
authoritative precedence (Rule B), and safe empty-string behavior (Rule C).
"""

import re
from typing import Optional, Any, Dict, Union

from modules.models.schedule import ClassInfo
from modules.models.recipe import ValidatedTemplateRecipe


class FieldResolver:
    """
    Authoritative field resolver for template generation.
    Resolves field values given a canonical field name, runtime ClassInfo,
    and optional ValidatedTemplateRecipe (or recipe dict).
    """

    # Direct canonical fields that map strictly to ClassInfo attributes
    DIRECT_CANONICAL_FIELDS = {
        "instructor",
        "course_section",
        "schedule_code",
        "subject",
        "time_days_room",
        "semester_ay",
        "college",
    }

    # Derived fields that compute deterministic values from ClassInfo
    DERIVED_FIELDS = {
        "subject_code",
        "subject_title",
        "semester",
        "school_year",
        "academic_year",
    }

    # Context-dependent fields that require explicit recipe metadata / runtime input
    CONTEXT_FIELDS = {
        "date",
        "period",
        "units",
        "department",
        "program",
        "section",
    }

    @classmethod
    def resolve(
        cls,
        field_name: str,
        info: Optional[ClassInfo] = None,
        recipe: Optional[Union[ValidatedTemplateRecipe, Dict[str, Any]]] = None,
    ) -> str:
        """
        Authoritatively resolves the string value for field_name.
        Precedence:
          1. Direct authoritative ClassInfo fields (e.g. instructor, course_section, subject, etc.)
          2. Explicit values from recipe metadata (e.g. date, period, department, program)
          3. Deterministic derived values from ClassInfo (e.g. subject_code, subject_title, semester, school_year)
          4. Safe empty string fallback (Rule C: never 'None', never fabricated data)
        """
        if not field_name:
            return ""

        key = str(field_name).strip().lower()

        # Extract recipe metadata dictionary if available
        meta: Dict[str, Any] = {}
        if recipe is not None:
            if isinstance(recipe, dict):
                meta = recipe.get("metadata", {})
                if not isinstance(meta, dict):
                    meta = {}
            elif hasattr(recipe, "metadata") and isinstance(recipe.metadata, dict):
                meta = recipe.metadata

        # 1. Direct Authoritative Runtime Fields (ClassInfo takes precedence)
        if key == "instructor":
            if info and getattr(info, "instructor", None):
                return str(info.instructor).strip()
            return str(meta.get("instructor") or "").strip()

        if key in ("course_section", "course_sec"):
            if info and getattr(info, "course_section", None):
                return str(info.course_section).strip()
            return str(meta.get("course_section") or "").strip()

        if key in ("schedule_code", "sched_code"):
            if info and getattr(info, "schedule_code", None):
                return str(info.schedule_code).strip()
            return str(meta.get("schedule_code") or "").strip()

        if key == "subject":
            if info and getattr(info, "subject", None):
                return str(info.subject).strip()
            return str(meta.get("subject") or "").strip()

        if key == "time_days_room":
            if info and getattr(info, "time_days_room", None):
                return str(info.time_days_room).strip()
            return str(meta.get("time_days_room") or "").strip()

        if key == "semester_ay":
            if info and getattr(info, "semester_ay", None):
                return str(info.semester_ay).strip()
            return str(meta.get("semester_ay") or "").strip()

        if key == "college":
            if info and getattr(info, "college", None):
                return str(info.college).strip()
            return str(meta.get("college") or "").strip()

        # 2. Context-dependent fields: check recipe metadata first
        if key in meta and meta[key] is not None:
            return str(meta[key]).strip()

        # Check explicit runtime attribute on info if present
        if info is not None and hasattr(info, key):
            val = getattr(info, key)
            if val is not None and not callable(val):
                s_val = str(val).strip()
                if s_val:
                    return s_val

        # 3. Subject Code and Subject Title
        if key == "subject_code":
            # 1. info.subject_code if explicitly set
            if info and getattr(info, "subject_code", None):
                return str(info.subject_code).strip()
            # 2. deterministic derivation from info.subject
            if info and getattr(info, "subject", None):
                return cls._derive_subject_code(info.subject)
            return ""

        if key == "subject_title":
            # 1. info.subject_name if explicitly distinct from full subject
            if info and getattr(info, "subject_name", None):
                if getattr(info, "subject", None) != info.subject_name:
                    return str(info.subject_name).strip()
            # 2. deterministic derivation from info.subject
            if info and getattr(info, "subject", None):
                derived = cls._derive_subject_title(info.subject)
                if derived:
                    return derived
                return str(info.subject).strip()
            return ""

        # 4. Semester and School Year
        if key == "semester":
            if info and getattr(info, "semester_ay", None):
                return cls._derive_semester(info.semester_ay)
            return ""

        if key in ("school_year", "academic_year"):
            if info and getattr(info, "semester_ay", None):
                return cls._derive_school_year(info.semester_ay)
            return ""

        # 5. Program and Section
        # Only resolve if explicitly in info or meta; never speculative parse
        if key == "program":
            if info and hasattr(info, "program") and info.program:
                return str(info.program).strip()
            return str(meta.get("program") or "").strip()

        if key == "section":
            if info and hasattr(info, "section") and info.section:
                return str(info.section).strip()
            return str(meta.get("section") or "").strip()

        # 6. Context fields: date, period, units, department
        # Never fabricate date or period (Rule A)
        if key in ("date", "period", "units", "department"):
            return str(meta.get(key) or "").strip()

        # 7. Arbitrary Field Fallback: check recipe metadata
        if key in meta:
            return str(meta[key] or "").strip()

        # Unknown fields return empty string (Rule C)
        return ""

    @staticmethod
    def _derive_subject_code(subject: str) -> str:
        """Splits 'CODE - TITLE' on hyphen to extract subject code."""
        if not subject:
            return ""
        raw = str(subject).strip()
        parts = re.split(r'\s*[-–—―−]\s*', raw, maxsplit=1)
        if len(parts) == 2 and parts[0]:
            return parts[0].strip()
        return ""

    @staticmethod
    def _derive_subject_title(subject: str) -> str:
        """Splits 'CODE - TITLE' on hyphen to extract subject title."""
        if not subject:
            return ""
        raw = str(subject).strip()
        parts = re.split(r'\s*[-–—―−]\s*', raw, maxsplit=1)
        if len(parts) == 2 and parts[1]:
            return parts[1].strip()
        return ""

    @staticmethod
    def _derive_semester(semester_ay: str) -> str:
        """Extracts and normalizes semester from semester_ay string."""
        if not semester_ay:
            return ""
        raw = str(semester_ay).strip()
        low = raw.lower()

        if "second" in low or "2nd" in low:
            return "2nd Semester"
        if "first" in low or "1st" in low:
            return "1st Semester"
        if "midyear" in low or "summer" in low:
            return "Midyear"

        # Check segment before delimiter
        parts = re.split(r'[/,]', raw)
        if parts:
            cand = parts[0].strip()
            if any(k in cand.lower() for k in ("semester", "sem", "term")):
                return cand

        return ""

    @staticmethod
    def _derive_school_year(semester_ay: str) -> str:
        """Extracts school year (e.g. 2026-2027) from semester_ay string."""
        if not semester_ay:
            return ""
        raw = str(semester_ay).strip()

        # Check YYYY-YYYY or YYYY/YYYY
        m = re.search(r'(20\d{2})\s*[-–/]\s*(20\d{2})', raw)
        if m:
            return f"{m.group(1)}-{m.group(2)}"

        # Check multiple individual years
        years = re.findall(r'20\d{2}', raw)
        if len(years) >= 2:
            return f"{years[0]}-{years[1]}"
        if len(years) == 1:
            if "midyear" in raw.lower() or "summer" in raw.lower():
                return years[0]
            y = int(years[0])
            return f"{y}-{y+1}"

        return ""


def resolve_field_value(
    field_name: str,
    info: Optional[ClassInfo] = None,
    recipe: Optional[Union[ValidatedTemplateRecipe, Dict[str, Any]]] = None,
) -> str:
    """Convenience helper delegating directly to FieldResolver.resolve()."""
    return FieldResolver.resolve(field_name, info, recipe)


__all__ = [
    "FieldResolver",
    "resolve_field_value",
]
