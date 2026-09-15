#!/usr/bin/env python3
"""
tests/test_field_resolver.py

Comprehensive tests for the generalized FieldResolver engine:
- Direct authoritative ClassInfo fields (instructor, course_section, schedule_code, etc.)
- Metadata precedence rules (ClassInfo direct fields override recipe metadata; context fields read metadata)
- Deterministic derived fields (subject_code, subject_title, semester, school_year)
- Non-fabrication invariants (Rule A: never fabricate date, period, or units)
- Safe empty string handling (Rule C: never return 'None')
- Non-speculative program and section handling (no speculative parsing from course_section)
- Arbitrary recipe-declared metadata fields
- Unified placeholder field resolution
"""

import pytest
from modules.models.schedule import ClassInfo
from modules.models.recipe import (
    ValidatedTemplateRecipe,
    HeaderCellBinding,
    _PRIVATE_CONSTRUCTION_SENTINEL,
    RECIPE_SCHEMA_VERSION,
)
from modules.generators.field_resolver import FieldResolver, resolve_field_value


def _make_dummy_recipe(metadata=None, header_bindings=None):
    """Helper to create a ValidatedTemplateRecipe for testing."""
    return ValidatedTemplateRecipe(
        schema_version=RECIPE_SCHEMA_VERSION,
        profile_id="custom_docx",
        fingerprint="dummy_fp",
        template_path="dummy.docx",
        roster_binding=None,
        header_bindings=header_bindings or {},
        signature_bindings={},
        metadata=metadata or {},
        _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
    )


# ══ Direct Canonical Fields ═══════════════════════════════════════════════════

def test_direct_canonical_fields_resolve_from_class_info():
    info = ClassInfo(
        instructor="Prof. Alan Turing",
        course_section="BSCS 3-1",
        schedule_code="99881",
        subject="COSC 101 - Theory of Computation",
        time_days_room="MWF 10:00-11:30 AM / CL1",
        semester_ay="1st Semester / 2026-2027",
        college="COLLEGE OF COMPUTER STUDIES",
    )

    assert resolve_field_value("instructor", info) == "Prof. Alan Turing"
    assert resolve_field_value("course_section", info) == "BSCS 3-1"
    assert resolve_field_value("course_sec", info) == "BSCS 3-1"
    assert resolve_field_value("schedule_code", info) == "99881"
    assert resolve_field_value("sched_code", info) == "99881"
    assert resolve_field_value("subject", info) == "COSC 101 - Theory of Computation"
    assert resolve_field_value("time_days_room", info) == "MWF 10:00-11:30 AM / CL1"
    assert resolve_field_value("semester_ay", info) == "1st Semester / 2026-2027"
    assert resolve_field_value("college", info) == "COLLEGE OF COMPUTER STUDIES"


def test_metadata_precedence_direct_fields_prefer_class_info():
    """ClassInfo direct fields must take precedence over recipe metadata."""
    info = ClassInfo(
        instructor="Authoritative Instructor",
        course_section="Authoritative Section",
    )
    recipe = _make_dummy_recipe(metadata={
        "instructor": "Metadata Instructor",
        "course_section": "Metadata Section",
    })

    assert resolve_field_value("instructor", info, recipe) == "Authoritative Instructor"
    assert resolve_field_value("course_section", info, recipe) == "Authoritative Section"


def test_metadata_used_when_class_info_direct_field_is_empty():
    """When ClassInfo field is empty, fallback to recipe metadata."""
    info = ClassInfo(instructor="", course_section="")
    recipe = _make_dummy_recipe(metadata={
        "instructor": "Fallback Instructor",
        "course_section": "Fallback Section",
    })

    assert resolve_field_value("instructor", info, recipe) == "Fallback Instructor"
    assert resolve_field_value("course_section", info, recipe) == "Fallback Section"


# ══ Subject Code and Subject Title ════════════════════════════════════════════

def test_subject_code_and_title_from_explicit_class_info():
    """Explicit subject_code and distinct subject_name take highest priority."""
    info = ClassInfo(
        subject_code="DCIT 21",
        subject_name="INTRODUCTION TO COMPUTING",
        subject="DCIT 21 - INTRODUCTION TO COMPUTING",
    )
    assert resolve_field_value("subject_code", info) == "DCIT 21"
    assert resolve_field_value("subject_title", info) == "INTRODUCTION TO COMPUTING"
    assert resolve_field_value("subject", info) == "DCIT 21 - INTRODUCTION TO COMPUTING"


def test_subject_code_and_title_derived_from_hyphenated_subject():
    """Standard hyphen / dash formats split cleanly into code and title."""
    # Standard hyphen
    info1 = ClassInfo(subject="DCIT 21 - INTRODUCTION TO COMPUTING")
    assert resolve_field_value("subject_code", info1) == "DCIT 21"
    assert resolve_field_value("subject_title", info1) == "INTRODUCTION TO COMPUTING"

    # En-dash
    info2 = ClassInfo(subject="ITEC 50 – WEB SYSTEMS AND TECHNOLOGY")
    assert resolve_field_value("subject_code", info2) == "ITEC 50"
    assert resolve_field_value("subject_title", info2) == "WEB SYSTEMS AND TECHNOLOGY"

    # Em-dash
    info3 = ClassInfo(subject="MATH 101 — ADVANCED CALCULUS")
    assert resolve_field_value("subject_code", info3) == "MATH 101"
    assert resolve_field_value("subject_title", info3) == "ADVANCED CALCULUS"


def test_subject_without_hyphen_handling():
    """When subject lacks a hyphen, do not guess code; title becomes full subject."""
    info = ClassInfo(subject="SEMINAR AND FIELD TRIP")
    assert resolve_field_value("subject_code", info) == ""
    assert resolve_field_value("subject_title", info) == "SEMINAR AND FIELD TRIP"
    assert resolve_field_value("subject", info) == "SEMINAR AND FIELD TRIP"


# ══ Semester and School Year Derivation ═══════════════════════════════════════

@pytest.mark.parametrize("sem_ay, exp_sem, exp_year", [
    ("1st Semester / 2026-2027", "1st Semester", "2026-2027"),
    ("2nd Semester / 2026-2027", "2nd Semester", "2026-2027"),
    ("First Semester / AY 2026-2027", "1st Semester", "2026-2027"),
    ("Second Semester / AY 2026-2027", "2nd Semester", "2026-2027"),
    ("FIRST SEMESTER, AY 2026 - 2027", "1st Semester", "2026-2027"),
    ("Midyear / 2026", "Midyear", "2026"),
    ("Summer 2025", "Midyear", "2025"),
])
def test_semester_and_school_year_derivation(sem_ay, exp_sem, exp_year):
    info = ClassInfo(semester_ay=sem_ay)
    assert resolve_field_value("semester", info) == exp_sem
    assert resolve_field_value("school_year", info) == exp_year
    assert resolve_field_value("academic_year", info) == exp_year


def test_semester_and_school_year_empty_when_unparseable():
    """Unparseable or empty semester_ay yields empty strings, never crashes."""
    info = ClassInfo(semester_ay="")
    assert resolve_field_value("semester", info) == ""
    assert resolve_field_value("school_year", info) == ""


# ══ Context-Dependent Fields (Rule A: Non-Fabrication) ═════════════════════════

def test_date_never_fabricated():
    """Date must return empty string unless explicitly provided in recipe metadata."""
    info = ClassInfo()
    # No metadata
    assert resolve_field_value("date", info) == ""

    # Explicit metadata
    recipe = _make_dummy_recipe(metadata={"date": "October 2026"})
    assert resolve_field_value("date", info, recipe) == "October 2026"


def test_period_never_fabricated():
    """Period must return empty string unless explicitly provided in recipe metadata."""
    info = ClassInfo()
    assert resolve_field_value("period", info) == ""

    recipe = _make_dummy_recipe(metadata={"period": "Midterm"})
    assert resolve_field_value("period", info, recipe) == "Midterm"


def test_units_never_fabricated():
    """Units must return empty string unless explicitly provided."""
    info = ClassInfo()
    assert resolve_field_value("units", info) == ""

    recipe = _make_dummy_recipe(metadata={"units": "3"})
    assert resolve_field_value("units", info, recipe) == "3"


# ══ Program, Department, and Section (Rule B & Non-Speculative Parsing) ════════

def test_department_resolved_from_recipe_metadata():
    info = ClassInfo()
    assert resolve_field_value("department", info) == ""

    recipe = _make_dummy_recipe(metadata={"department": "Department of Information Technology"})
    assert resolve_field_value("department", info, recipe) == "Department of Information Technology"


def test_program_and_section_not_speculatively_derived():
    """Program and section must NOT be guessed from course_section."""
    info = ClassInfo(course_section="BSCS 1-4")
    # Must NOT automatically guess program='BSCS' or section='1-4'
    assert resolve_field_value("program", info) == ""
    assert resolve_field_value("section", info) == ""

    # Must resolve when provided via recipe metadata
    recipe = _make_dummy_recipe(metadata={"program": "BSCS", "section": "1-4"})
    assert resolve_field_value("program", info, recipe) == "BSCS"
    assert resolve_field_value("section", info, recipe) == "1-4"


# ══ Arbitrary Fields & Safe Fallback (Rule C) ══════════════════════════════════

def test_arbitrary_recipe_fields_resolve_from_metadata():
    info = ClassInfo()
    recipe = _make_dummy_recipe(metadata={
        "campus": "CvSU Main Campus",
        "room_type": "Laboratory",
    })
    assert resolve_field_value("campus", info, recipe) == "CvSU Main Campus"
    assert resolve_field_value("room_type", info, recipe) == "Laboratory"


def test_unknown_field_returns_empty_string():
    info = ClassInfo()
    assert resolve_field_value("nonexistent_unknown_field", info) == ""
    assert resolve_field_value("", info) == ""
    assert resolve_field_value(None, info) == ""


# ══ Explicit Precedence Conflict Tests (Issue 1) ══════════════════════════════

def test_precedence_explicit_model_field_overrides_metadata():
    """Explicit ClassInfo subject_code takes precedence over conflicting recipe metadata."""
    info = ClassInfo(subject_code="COSC 70")
    recipe = _make_dummy_recipe(metadata={"subject_code": "WRONG_METADATA"})
    assert resolve_field_value("subject_code", info, recipe) == "COSC 70"


def test_precedence_derived_school_year_overrides_metadata():
    """Derived school_year from ClassInfo takes precedence over conflicting recipe metadata."""
    info = ClassInfo(semester_ay="1st Semester / 2026-2027")
    recipe = _make_dummy_recipe(metadata={"school_year": "2099-2100", "academic_year": "2099-2100"})
    assert resolve_field_value("school_year", info, recipe) == "2026-2027"
    assert resolve_field_value("academic_year", info, recipe) == "2026-2027"


def test_precedence_derived_semester_overrides_metadata():
    """Derived semester from ClassInfo takes precedence over conflicting recipe metadata."""
    info = ClassInfo(semester_ay="1st Semester / 2026-2027")
    recipe = _make_dummy_recipe(metadata={"semester": "Midyear"})
    assert resolve_field_value("semester", info, recipe) == "1st Semester"


def test_precedence_derived_subject_code_and_title_override_metadata():
    """Derived subject_code and subject_title from ClassInfo.subject override recipe metadata."""
    info = ClassInfo(subject="COSC 70 - SOFTWARE ENGINEERING")
    recipe = _make_dummy_recipe(metadata={
        "subject_code": "WRONG_CODE",
        "subject_title": "WRONG_TITLE",
    })
    assert resolve_field_value("subject_code", info, recipe) == "COSC 70"
    assert resolve_field_value("subject_title", info, recipe) == "SOFTWARE ENGINEERING"


def test_precedence_metadata_fallback_when_classinfo_has_no_derived_source():
    """When ClassInfo lacks a source to derive from, recipe metadata fallback is used."""
    info = ClassInfo(subject="", semester_ay="")
    recipe = _make_dummy_recipe(metadata={
        "subject_code": "BIO 101",
        "subject_title": "GENERAL BIOLOGY",
        "semester": "2nd Semester",
        "school_year": "2026-2027",
    })
    assert resolve_field_value("subject_code", info, recipe) == "BIO 101"
    assert resolve_field_value("subject_title", info, recipe) == "GENERAL BIOLOGY"
    assert resolve_field_value("semester", info, recipe) == "2nd Semester"
    assert resolve_field_value("school_year", info, recipe) == "2026-2027"


# ══ College Legacy Default vs Explicit Resolution Tests (Issue 2) ══════════════

def test_college_legacy_default_overridden_by_recipe_metadata():
    """When ClassInfo has the un-specified legacy CEIT default, recipe metadata overrides it."""
    info = ClassInfo()  # default college
    assert info.has_explicit_college is False
    assert info.college == "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"

    recipe = _make_dummy_recipe(metadata={"college": "COLLEGE OF ARTS AND SCIENCES"})
    assert resolve_field_value("college", info, recipe) == "COLLEGE OF ARTS AND SCIENCES"


def test_college_legacy_default_preserved_when_no_recipe_metadata():
    """When ClassInfo has the default and no metadata is supplied, legacy default is preserved."""
    info = ClassInfo()
    assert resolve_field_value("college", info) == "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"


def test_college_explicit_class_info_overrides_recipe_metadata():
    """When ClassInfo explicitly specifies college, it takes authoritative precedence over recipe metadata."""
    info = ClassInfo(college="COLLEGE OF COMPUTER STUDIES")
    assert info.has_explicit_college is True

    recipe = _make_dummy_recipe(metadata={"college": "COLLEGE OF ARTS AND SCIENCES"})
    assert resolve_field_value("college", info, recipe) == "COLLEGE OF COMPUTER STUDIES"


def test_college_explicit_ceit_takes_precedence_over_metadata():
    """When CEIT college is explicitly supplied, has_explicit_college is True and takes precedence."""
    info = ClassInfo(college="COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY")
    assert info.has_explicit_college is True

    recipe = _make_dummy_recipe(metadata={"college": "COLLEGE OF ARTS AND SCIENCES"})
    assert resolve_field_value("college", info, recipe) == "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"


def test_college_mutation_after_initialization_is_authoritative():
    info = ClassInfo()
    info.college = "COLLEGE OF COMPUTER STUDIES"
    recipe = _make_dummy_recipe(metadata={"college": "COLLEGE OF ARTS AND SCIENCES"})

    assert info.has_explicit_college is True
    assert resolve_field_value("college", info, recipe) == "COLLEGE OF COMPUTER STUDIES"


def test_single_semester_year_does_not_fabricate_academic_year():
    info = ClassInfo(semester_ay="1st Semester 2026")
    assert resolve_field_value("school_year", info) == ""


def test_single_semester_year_uses_metadata_fallback():
    info = ClassInfo(semester_ay="1st Semester 2026")
    recipe = _make_dummy_recipe(metadata={"school_year": "2026-2027"})
    assert resolve_field_value("school_year", info, recipe) == "2026-2027"


def test_explicit_model_school_year_overrides_derived_and_metadata_values():
    info = ClassInfo(semester_ay="1st Semester / 2026-2027")
    info.school_year = "2030-2031"
    recipe = _make_dummy_recipe(metadata={"school_year": "2099-2100"})
    assert resolve_field_value("school_year", info, recipe) == "2030-2031"
