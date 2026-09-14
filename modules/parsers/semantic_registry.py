#!/usr/bin/env python3
"""
modules/parsers/semantic_registry.py

Semantic Registry for Authoritative Dynamic Template Discovery.
Provides normalization, alias matching, regex candidate matching, and collision observations.

NOTE: This registry provides candidate observations only. It does NOT authorize bindings
or make final validity decisions. RecipeValidator owns final ambiguity, required/prohibited,
structural, confidence, and verified_safe decisions.
"""

import re
from typing import Dict, List, Tuple, Optional, Any, Set


# Canonical semantic field names
FIELD_SCHEDULE_CODE = "schedule_code"
FIELD_COURSE_SECTION = "course_section"
FIELD_SUBJECT_CODE = "subject_code"
FIELD_SUBJECT_TITLE = "subject_title"
FIELD_SUBJECT = "subject"
FIELD_SEMESTER = "semester"
FIELD_SCHOOL_YEAR = "school_year"
FIELD_SEMESTER_AY = "semester_ay"
FIELD_INSTRUCTOR = "instructor"
FIELD_UNITS = "units"
FIELD_PERIOD = "period"
FIELD_DATE = "date"
FIELD_TIME_DAYS_ROOM = "time_days_room"

# Signature role names
ROLE_INSTRUCTOR_SIGNATURE = "instructor_signature"
ROLE_PREPARED_BY = "prepared_by"
ROLE_EVALUATED_BY = "evaluated_by"
ROLE_APPROVED_BY = "approved_by"
ROLE_RECOMMENDING_APPROVAL = "recommending_approval"
ROLE_DEPT_CHAIR = "dept_chair"
ROLE_DEAN = "dean"


# Alias patterns mapping raw labels to canonical semantic fields
SEMANTIC_ALIASES: Dict[str, List[re.Pattern]] = {
    FIELD_SCHEDULE_CODE: [
        re.compile(r"^\s*(?:schedule\s*code|sched\.?\s*code|class\s*code|course\s*code)\s*:?\s*$", re.IGNORECASE),
        re.compile(r"\b(?:schedule\s*code|sched\.?\s*code)\b", re.IGNORECASE),
    ],
    FIELD_COURSE_SECTION: [
        re.compile(r"^\s*(?:course\s*(?:and|&|/)?\s*(?:year|yr\.?)?\s*(?:and|&|/)?\s*sec(?:tion)?|class|section|degree\s*program)\s*:?\s*$", re.IGNORECASE),
        re.compile(r"\b(?:course\s*(?:and|&|/)?\s*sec(?:tion)?|class)\b", re.IGNORECASE),
    ],
    FIELD_SUBJECT_CODE: [
        re.compile(r"^\s*(?:subject\s*code|course\s*code|subj\.?\s*code)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_SUBJECT_TITLE: [
        re.compile(r"^\s*(?:subject\s*title|course\s*title|subj\.?\s*title|descriptive\s*title)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_SUBJECT: [
        re.compile(r"^\s*(?:subject|course|subject\s*(?:and|&|/)?\s*title)\s*:?\s*$", re.IGNORECASE),
        re.compile(r"\b(?:subject|descriptive\s*title)\b", re.IGNORECASE),
    ],
    FIELD_SEMESTER: [
        re.compile(r"^\s*(?:semester|sem\.?|term)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_SCHOOL_YEAR: [
        re.compile(r"^\s*(?:school\s*year|academic\s*year|s\.?y\.?|a\.?y\.?)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_SEMESTER_AY: [
        re.compile(r"^\s*(?:semester\s*(?:and|&|/)?\s*(?:academic\s*year|school\s*year|ay|a\.y\.)|term\s*(?:and|&|/)?\s*ay)\s*:?\s*$", re.IGNORECASE),
        re.compile(r"\b(?:semester\s*(?:and|&|/)?\s*(?:ay|a\.y\.|academic\s*year))\b", re.IGNORECASE),
    ],
    FIELD_INSTRUCTOR: [
        re.compile(r"^\s*(?:instructor|instructor['’]?s?\s*name|faculty|teacher|professor)\s*:?\s*$", re.IGNORECASE),
        re.compile(r"\b(?:instructor|faculty|professor)\b", re.IGNORECASE),
    ],
    FIELD_UNITS: [
        re.compile(r"^\s*(?:units|credit\s*units|no\.?\s*of\s*units)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_PERIOD: [
        re.compile(r"^\s*(?:period|grading\s*period|term/period)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_DATE: [
        re.compile(r"^\s*(?:date|petsa)\s*:?\s*$", re.IGNORECASE),
    ],
    FIELD_TIME_DAYS_ROOM: [
        re.compile(r"^\s*(?:time\s*(?:and|&|/)?\s*days?\s*(?:and|&|/)?\s*room(?:\s*no\.?)?|class\s*hours?|schedule)\s*:?\s*$", re.IGNORECASE),
        re.compile(r"\b(?:time\s*(?:and|&|/)?\s*days?|schedule)\b", re.IGNORECASE),
    ],
}

# Patterns recognizing signature roles and regions
SIGNATURE_PATTERNS: Dict[str, List[re.Pattern]] = {
    ROLE_PREPARED_BY: [
        re.compile(r"\bprepared\s*by\b", re.IGNORECASE),
        re.compile(r"\bsubmitted\s*by\b", re.IGNORECASE),
    ],
    ROLE_EVALUATED_BY: [
        re.compile(r"\bevaluated\s*by\b", re.IGNORECASE),
        re.compile(r"\bchecked\s*by\b", re.IGNORECASE),
    ],
    ROLE_APPROVED_BY: [
        re.compile(r"\bapproved\s*by\b", re.IGNORECASE),
    ],
    ROLE_RECOMMENDING_APPROVAL: [
        re.compile(r"\brecommending\s*approval\b", re.IGNORECASE),
    ],
    ROLE_DEPT_CHAIR: [
        re.compile(r"\b(?:department\s*chair(?:person)?|dept\.?\s*chair)\b", re.IGNORECASE),
    ],
    ROLE_DEAN: [
        re.compile(r"\bdean\b", re.IGNORECASE),
    ],
    ROLE_INSTRUCTOR_SIGNATURE: [
        re.compile(r"\binstructor['’]?s?\s*signature\b", re.IGNORECASE),
        re.compile(r"\bsignature\s*of\s*instructor\b", re.IGNORECASE),
    ],
}


class SemanticRegistry:
    """
    Registry service for candidate observation, text normalization, and collision detection.
    Does not authorize or produce validated recipes.
    """

    @staticmethod
    def normalize_text(text: Optional[str]) -> str:
        """Strips whitespace, replaces multiple spaces with single space, and unifies symbols."""
        if not text:
            return ""
        # Remove non-breaking spaces and other Unicode spaces
        cleaned = re.sub(r"[\s\u00a0\u200b]+", " ", str(text))
        return cleaned.strip()

    @classmethod
    def match_metadata_candidate(
        cls,
        text: str,
        is_signature_region: bool = False,
    ) -> List[Tuple[str, float]]:
        """
        Observes potential metadata field candidates from label text.
        If is_signature_region is True, returns empty list to prevent metadata discovery
        from accidentally binding signature labels.
        Returns list of (field_name, confidence) tuples.
        """
        if is_signature_region:
            return []

        cleaned = cls.normalize_text(text)
        if not cleaned:
            return []

        results: List[Tuple[str, float]] = []

        for field, patterns in SEMANTIC_ALIASES.items():
            for idx, pattern in enumerate(patterns):
                if pattern.search(cleaned):
                    # Exact pattern match has higher confidence than loose token match
                    conf = 0.95 if idx == 0 else 0.75
                    results.append((field, conf))
                    break

        return results

    @classmethod
    def match_signature_candidate(
        cls,
        text: str,
        in_signature_table: bool = False,
        relative_vertical_pos: float = 0.5,
    ) -> List[Tuple[str, float]]:
        """
        Observes potential signature roles from label or block text.
        Requires signature indicators, signature table context, or lower-document positioning.
        """
        cleaned = cls.normalize_text(text)
        if not cleaned:
            return []

        results: List[Tuple[str, float]] = []

        for role, patterns in SIGNATURE_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(cleaned):
                    conf = 0.90 if in_signature_table else (0.80 if relative_vertical_pos > 0.5 else 0.60)
                    results.append((role, conf))
                    break

        # Contextual check: "INSTRUCTOR" appearing in signature table or bottom half
        if not results:
            if re.search(r"\binstructor\b", cleaned, re.IGNORECASE):
                if in_signature_table or relative_vertical_pos > 0.6:
                    results.append((ROLE_INSTRUCTOR_SIGNATURE, 0.75))

        return results

    @classmethod
    def is_signature_context(
        cls,
        text: str,
        table_index: int,
        total_tables: int,
        row_index: int,
        total_rows: int,
    ) -> bool:
        """
        Disambiguates metadata vs signature context based on document and table position.
        """
        cleaned = cls.normalize_text(text)
        # Explicit signature phrasing is always signature context
        for patterns in SIGNATURE_PATTERNS.values():
            if any(p.search(cleaned) for p in patterns):
                return True

        # Top table (table_index == 0) in multi-table document is metadata header, not signature
        if total_tables > 1 and table_index == 0:
            return False

        # If in the last table of multi-table doc, or bottom rows of a table
        is_last_table = (total_tables > 1 and table_index >= total_tables - 1)
        is_bottom_rows = (total_rows > 5 and row_index >= total_rows - 2)

        if (is_last_table or is_bottom_rows) and re.search(r"\binstructor\b", cleaned, re.IGNORECASE):
            return True

        return False

    @staticmethod
    def observe_collisions(
        candidate_bindings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Inspects candidate bindings and returns any collisions (multiple candidates for same field).
        Emits observations for RecipeValidator to assess ambiguity.
        """
        field_map: Dict[str, List[Dict[str, Any]]] = {}
        for c in candidate_bindings:
            field = c.get("field")
            if field:
                field_map.setdefault(field, []).append(c)

        collisions = []
        for field, c_list in field_map.items():
            if len(c_list) > 1:
                collisions.append({
                    "field": field,
                    "count": len(c_list),
                    "candidates": c_list,
                })
        return collisions
