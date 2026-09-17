#!/usr/bin/env python3
"""
tests/test_compound_semantic_labels.py

Matcher-level tests proving isolated, collision-free semantic matching:
- 'Course Code' -> subject_code
- 'Course Title' -> subject_title
- 'Course Code & Title' -> subject
- 'Schedule Code' -> schedule_code
- Verification against actual SemanticRegistry.match_metadata_candidate
"""

import pytest
from modules.parsers.semantic_registry import (
    SemanticRegistry,
    FIELD_SUBJECT_CODE,
    FIELD_SUBJECT_TITLE,
    FIELD_SUBJECT,
    FIELD_SCHEDULE_CODE,
    FIELD_COURSE_SECTION,
    FIELD_COLLEGE,
    FIELD_DEPARTMENT,
    FIELD_PROGRAM,
)


def test_course_code_matches_subject_code_without_schedule_collision():
    for label in ("Course Code", "Course Code:", "course code", "COURSE CODE:"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_SUBJECT_CODE
        assert conf >= 0.9
        # Prove no collision with schedule_code or course_section
        assert not any(f == FIELD_SCHEDULE_CODE for f, _ in matches)
        assert not any(f == FIELD_COURSE_SECTION for f, _ in matches)


def test_course_title_matches_subject_title():
    for label in ("Course Title", "Course Title:", "course title", "COURSE TITLE:"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_SUBJECT_TITLE
        assert conf >= 0.9
        assert not any(f == FIELD_SUBJECT for f, _ in matches)


def test_course_code_and_title_matches_subject():
    compound_variants = (
        "Course Code & Title",
        "Course Code & Title:",
        "Course Code and Title",
        "Course Code and Title:",
        "Course Code / Title",
        "Course Code / Title:",
        "Course Title & Code",
        "Course Title and Code",
        "Subject Code & Title",
        "Subject Code and Title",
    )
    for label in compound_variants:
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_SUBJECT
        assert conf >= 0.9
        # Prove no ambiguity collision with subject_code or subject_title
        assert not any(f == FIELD_SUBJECT_CODE for f, _ in matches)
        assert not any(f == FIELD_SUBJECT_TITLE for f, _ in matches)


def test_schedule_code_matches_schedule_code():
    for label in ("Schedule Code", "Schedule Code:", "Sched Code", "Sched. Code:", "Class Code"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_SCHEDULE_CODE
        assert conf >= 0.9
        assert not any(f == FIELD_SUBJECT_CODE for f, _ in matches)


def test_signature_region_suppression():
    """Verify compound patterns do not trigger in signature regions."""
    assert SemanticRegistry.match_metadata_candidate("Course Code & Title", is_signature_region=True) == []


def test_department_matches_without_signature_collision():
    for label in ("Department", "Department:", "department", "Dept.", "DEPT:"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_DEPARTMENT
        assert conf >= 0.9


def test_college_matches_college():
    for label in ("College", "College:", "college", "Col.", "COL:"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_COLLEGE
        assert conf >= 0.9


def test_program_matches_without_course_section_collision():
    for label in ("Program", "Program:", "Degree Program", "Degree Program:", "Academic Program"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_PROGRAM
        assert conf >= 0.9
        # Must not collide with course_section
        assert not any(f == FIELD_COURSE_SECTION for f, _ in matches)


def test_course_section_compound_labels_do_not_collide_with_program():
    for label in ("Course / Section", "Course & Section", "Degree Program & Section", "Degree Program / Section", "Section", "Section:", "SECTION"):
        matches = SemanticRegistry.match_metadata_candidate(label)
        assert len(matches) == 1, f"Expected exactly 1 match for {label!r}, got {matches}"
        field, conf = matches[0]
        assert field == FIELD_COURSE_SECTION
        assert conf >= 0.9
        # Must not collide with program
        assert not any(f == FIELD_PROGRAM for f, _ in matches)
