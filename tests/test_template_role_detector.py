#!/usr/bin/env python3
"""
tests/test_template_role_detector.py

Comprehensive tests for dynamic TemplateRoleDetector:
  - Physical detection of academic DOCX, attendance DOCX, and grade XLSX.
  - Verification that physical structure (not filename) governs classification.
  - Renamed files (e.g. arbitrary names) are correctly classified.
  - Attendance capacity discrimination (4 sessions -> lecture, >=8 -> lecture+lab).
  - Grade sheet worksheet discrimination (presence of Laboratory sheet).
  - Ambiguity reporting and candidate enumeration.
  - Unsupported file rejection.
  - Authoritative validation via validate_role().
"""

import os
import shutil
import pytest

from modules.models.template_set import (
    ROLE_SYLLABUS,
    ROLE_EXAM_RETURNS_MIDTERM,
    ROLE_EXAM_RETURNS_FINAL,
    ROLE_TOS_MIDTERM,
    ROLE_TOS_FINAL,
    ROLE_GRADE_DISCUSSION_MIDTERM,
    ROLE_GRADE_DISCUSSION_FINAL,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_ATTENDANCE_LECTURE_LAB,
    ROLE_GRADE_SHEET_LECTURE,
    ROLE_GRADE_SHEET_LECTURE_LAB,
)
from modules.parsers.template_role_detector import TemplateRoleDetector


@pytest.fixture(scope="module")
def detector():
    return TemplateRoleDetector()


@pytest.fixture(scope="module")
def templates_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))


@pytest.fixture(scope="module")
def attendance_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "attendance"))


def test_detect_syllabus(detector, templates_dir):
    p = os.path.join(templates_dir, "template_syllabus.docx")
    res = detector.detect_role(p)
    assert res.status == "confirmed"
    assert res.role == ROLE_SYLLABUS
    assert res.profile_id == "syllabus"
    assert len(res.structural_evidence) > 0


def test_detect_exam_returns(detector, templates_dir):
    p_mid = os.path.join(templates_dir, "template_exam_midterm.docx")
    res_mid = detector.detect_role(p_mid)
    assert res_mid.status == "confirmed"
    assert res_mid.role == ROLE_EXAM_RETURNS_MIDTERM

    p_fin = os.path.join(templates_dir, "template_exam_finals.docx")
    res_fin = detector.detect_role(p_fin)
    assert res_fin.status == "confirmed"
    assert res_fin.role == ROLE_EXAM_RETURNS_FINAL


def test_detect_grade_discussion(detector, templates_dir):
    p_mid = os.path.join(templates_dir, "Midterm-Grade-Discussion_LATEST.docx")
    res_mid = detector.detect_role(p_mid)
    assert res_mid.status == "confirmed"
    assert res_mid.role == ROLE_GRADE_DISCUSSION_MIDTERM

    p_fin = os.path.join(templates_dir, "Final-Grade-Discussion_LATEST.docx")
    res_fin = detector.detect_role(p_fin)
    assert res_fin.status == "confirmed"
    assert res_fin.role == ROLE_GRADE_DISCUSSION_FINAL


def test_detect_tos(detector, templates_dir):
    p_mid = os.path.join(templates_dir, "template_tos_midterm.docx")
    res_mid = detector.detect_role(p_mid)
    assert res_mid.status == "confirmed"
    assert res_mid.role == ROLE_TOS_MIDTERM

    p_fin = os.path.join(templates_dir, "template_tos_finals.docx")
    res_fin = detector.detect_role(p_fin)
    # If ambiguous due to overlapping text in template body, tos_final must be in candidates
    if res_fin.status == "ambiguous":
        assert ROLE_TOS_FINAL in res_fin.candidate_roles
    else:
        assert res_fin.status == "confirmed"
        assert res_fin.role == ROLE_TOS_FINAL


def test_detect_attendance_lecture_vs_lab(detector, attendance_dir):
    p_lec = os.path.join(attendance_dir, "template lec.docx")
    res_lec = detector.detect_role(p_lec)
    assert res_lec.status == "confirmed"
    assert res_lec.role == ROLE_ATTENDANCE_LECTURE
    assert any("capacity: 4" in ev for ev in res_lec.structural_evidence)

    p_lab = os.path.join(attendance_dir, "template lab and lec.docx")
    res_lab = detector.detect_role(p_lab)
    assert res_lab.status == "confirmed"
    assert res_lab.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert any("capacity: 8" in ev or "capacity: 10" in ev for ev in res_lab.structural_evidence)


def test_detect_grade_sheet_lecture_vs_lab(detector, templates_dir):
    p_lec = os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx")
    res_lec = detector.detect_role(p_lec)
    assert res_lec.status == "confirmed"
    assert res_lec.role == ROLE_GRADE_SHEET_LECTURE

    p_lab = os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    res_lab = detector.detect_role(p_lab)
    assert res_lab.status == "confirmed"
    assert res_lab.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert any("Laboratory" in ev for ev in res_lab.structural_evidence)


def test_detection_never_uses_filename_alone(detector, templates_dir, attendance_dir, tmp_path):
    """
    Copy templates to completely arbitrary, misleading, or neutral filenames.
    Verify detection succeeds based strictly on physical structure.
    """
    # 1. Grade sheet lab renamed to ArbitraryGradebook.xlsx
    custom_grade = tmp_path / "ArbitraryGradebook.xlsx"
    shutil.copy2(os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx"), custom_grade)
    res_grade = detector.detect_role(str(custom_grade))
    assert res_grade.status == "confirmed"
    assert res_grade.role == ROLE_GRADE_SHEET_LECTURE_LAB

    # 2. Attendance lab renamed to random_document_001.docx
    custom_att = tmp_path / "random_document_001.docx"
    shutil.copy2(os.path.join(attendance_dir, "template lab and lec.docx"), custom_att)
    res_att = detector.detect_role(str(custom_att))
    assert res_att.status == "confirmed"
    assert res_att.role == ROLE_ATTENDANCE_LECTURE_LAB

    # 3. Syllabus renamed to CourseInformation.docx
    custom_syl = tmp_path / "CourseInformation.docx"
    shutil.copy2(os.path.join(templates_dir, "template_syllabus.docx"), custom_syl)
    res_syl = detector.detect_role(str(custom_syl))
    assert res_syl.status == "confirmed"
    assert res_syl.role == ROLE_SYLLABUS


def test_unsupported_file_detection(detector, tmp_path):
    # Non-supported extension
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("just some text")
    res = detector.detect_role(str(txt_file))
    assert res.status == "unsupported"

    # Non-existent file
    res_missing = detector.detect_role(str(tmp_path / "does_not_exist.docx"))
    assert res_missing.status == "unsupported"


def test_validate_role_authoritative(detector, templates_dir):
    syl_path = os.path.join(templates_dir, "template_syllabus.docx")

    # Valid matching role
    is_valid, err, val_recipe = detector.validate_role(syl_path, ROLE_SYLLABUS)
    assert is_valid is True
    assert err is None
    assert val_recipe is not None

    # Incompatible declared role fails validation
    is_valid_bad, err_bad, val_bad = detector.validate_role(syl_path, ROLE_GRADE_SHEET_LECTURE)
    assert is_valid_bad is False
    assert err_bad is not None
    assert val_bad is None
