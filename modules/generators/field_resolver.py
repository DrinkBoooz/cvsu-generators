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
from collections.abc import Mapping

from modules.models.schedule import ClassInfo, LEGACY_DEFAULT_COLLEGE
from modules.models.recipe import ValidatedTemplateRecipe


class FieldResolver:
    """
    Authoritative field resolver for template generation.
    The DOCX execution engine no longer contains an inline field-to-ClassInfo mapping.
    Field semantics are centralized in FieldResolver.

    Precedence Policy:
      1. Authoritative canonical runtime fields (ClassInfo takes precedence).
      2. Derived fields (subject_code, subject_title, semester, school_year):
         explicit runtime field > deterministic derivation > recipe metadata fallback > ""
      3. Contextual fields (date, period, units, department, program, section):
         runtime attribute on info > recipe metadata fallback > ""
      4. College field:
         explicit runtime college > recipe metadata > legacy CEIT default > ""
      5. Arbitrary recipe fields:
         runtime attribute on info > recipe metadata fallback > ""
      6. Safe empty string fallback (Rule C: never 'None', never fabricated data).
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
        """
        if not field_name:
            return ""

        key = str(field_name).strip().lower()

        # Extract recipe metadata dictionary if available
        meta: Any = {}
        if recipe is not None:
            if isinstance(recipe, (dict, Mapping)):
                meta = recipe.get("metadata", {})
                if not isinstance(meta, (dict, Mapping)):
                    meta = {}
            elif hasattr(recipe, "metadata") and isinstance(recipe.metadata, (dict, Mapping)):
                meta = recipe.metadata

        # -------------------------------------------------------------------------
        # 1. Authoritative Canonical Runtime Fields (ClassInfo takes precedence)
        # -------------------------------------------------------------------------
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

        if key in ("subject", "course"):
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
            if info is not None:
                is_explicit = getattr(info, "has_explicit_college", None)
                college_val = getattr(info, "college", None)
                # If explicit on ClassInfo, it is authoritative
                if is_explicit is True and college_val:
                    return str(college_val).strip()
                # If legacy default on ClassInfo, recipe metadata can override
                if is_explicit is False:
                    if meta.get("college"):
                        return str(meta["college"]).strip()
                    if college_val:
                        return str(college_val).strip()
                # If dict or non-ClassInfo object
                if isinstance(info, dict):
                    c_dict = info.get("college")
                    if c_dict and c_dict != LEGACY_DEFAULT_COLLEGE:
                        return str(c_dict).strip()
                    if meta.get("college"):
                        return str(meta["college"]).strip()
                    if c_dict:
                        return str(c_dict).strip()
                elif college_val:
                    if college_val != LEGACY_DEFAULT_COLLEGE:
                        return str(college_val).strip()
                    if meta.get("college"):
                        return str(meta["college"]).strip()
                    return str(college_val).strip()
            if meta.get("college"):
                return str(meta["college"]).strip()
            return ""

        # -------------------------------------------------------------------------
        # 2. Derived Fields: explicit runtime > deterministic derivation > metadata > ""
        # -------------------------------------------------------------------------
        if key in ("subject_code", "course_code", "subj_code"):
            # a. Explicit runtime field
            if info and getattr(info, "subject_code", None):
                return str(info.subject_code).strip()
            # b. Deterministic derivation from subject
            if info and getattr(info, "subject", None):
                derived = cls._derive_subject_code(info.subject)
                if derived:
                    return derived
            # c. Explicit metadata fallback
            for m_key in ("subject_code", "course_code", "subj_code"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        if key in ("subject_title", "course_title", "subj_title"):
            # a. Explicit runtime field (info.subject_name if distinct from subject)
            if info and getattr(info, "subject_name", None):
                if getattr(info, "subject", None) != info.subject_name:
                    return str(info.subject_name).strip()
            # b. Deterministic derivation from subject
            if info and getattr(info, "subject", None):
                derived = cls._derive_subject_title(info.subject)
                if derived:
                    return derived
                # If no hyphen to split, full subject acts as title
                return str(info.subject).strip()
            # c. Explicit metadata fallback
            for m_key in ("subject_title", "course_title", "subj_title", "subject_name"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        if key in ("semester", "term", "sem"):
            # a. Explicit runtime field
            if info and getattr(info, "semester", None):
                return str(info.semester).strip()
            # b. Deterministic derivation from semester_ay
            if info and getattr(info, "semester_ay", None):
                derived = cls._derive_semester(info.semester_ay)
                if derived:
                    return derived
            # c. Explicit metadata fallback
            for m_key in ("semester", "term", "sem"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        if key in ("school_year", "academic_year", "ay", "sy"):
            # a. Explicit runtime field
            if info and getattr(info, "school_year", None):
                return str(info.school_year).strip()
            if info and getattr(info, "academic_year", None):
                return str(info.academic_year).strip()
            # b. Deterministic derivation from semester_ay
            if info and getattr(info, "semester_ay", None):
                derived = cls._derive_school_year(info.semester_ay)
                if derived:
                    return derived
            # c. Explicit metadata fallback
            for m_key in ("school_year", "academic_year", "ay", "sy"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        # -------------------------------------------------------------------------
        # 3. Contextual Fields: runtime source > recipe metadata > ""
        # -------------------------------------------------------------------------
        if key in ("program", "degree_program", "academic_program"):
            for attr in ("program", "degree_program", "academic_program"):
                if info and getattr(info, attr, None):
                    return str(getattr(info, attr)).strip()
            for m_key in ("program", "degree_program", "academic_program"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        if key == "section":
            if info and getattr(info, "section", None):
                return str(info.section).strip()
            return str(meta.get("section") or "").strip()

        if key in ("department", "dept"):
            for attr in ("department", "dept"):
                if info and getattr(info, attr, None):
                    return str(getattr(info, attr)).strip()
            for m_key in ("department", "dept"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        if key == "date":
            if info and getattr(info, "date", None):
                return str(info.date).strip()
            return str(meta.get("date") or "").strip()

        if key in ("period", "grading_period"):
            for attr in ("period", "grading_period"):
                if info and getattr(info, attr, None):
                    return str(getattr(info, attr)).strip()
            for m_key in ("period", "grading_period"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        if key in ("units", "credit_units"):
            for attr in ("units", "credit_units"):
                if info and getattr(info, attr, None):
                    return str(getattr(info, attr)).strip()
            for m_key in ("units", "credit_units"):
                if m_key in meta and meta[m_key] is not None:
                    return str(meta[m_key]).strip()
            return ""

        # -------------------------------------------------------------------------
        # 4. Arbitrary Unknown Field Fallback: runtime attribute > recipe metadata > ""
        # -------------------------------------------------------------------------
        if info is not None and hasattr(info, key):
            val = getattr(info, key)
            if val is not None and not callable(val):
                s_val = str(val).strip()
                if s_val:
                    return s_val

        if key in meta and meta[key] is not None:
            return str(meta[key]).strip()

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
        """Extracts an explicit academic-year range from semester_ay."""
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
            return ""

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
