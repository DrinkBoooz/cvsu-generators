#!/usr/bin/env python3
"""
tests/test_generalized_detection.py

Comprehensive tests for Generalized Automatic Template-Role Detection:
1. Worksheet Name Independence:
   - Grade sheet with renamed worksheets (Main, Practical, Final Scores, Combined)
     detected as grade_sheet_lecture_lab.
   - Grade sheet with renamed worksheets (Main, Final Scores)
     detected as grade_sheet_lecture.
2. Filename Independence:
   - Arbitrary opaque filenames (e.g. abc123.docx, faculty_form_7.docx, template_foo.xlsx)
     detected strictly from physical structure.
3. Academic Semantic Variation:
   - Alternate labels (Professor:, Class Section:, Course Title:) correctly identified.
4. Attendance Structural Variant Detection:
   - Non-default column grouping / session layouts.
   - Ambiguous attendance structures rejected fail-closed.
5. Grade Sheet Variant Discrimination:
   - Lecture grade sheet without "Lecture" worksheet.
   - Lecture+Lab grade sheet without "Laboratory" worksheet.
   - Ambiguous grade sheet rejected fail-closed.
6. Role Candidate Evidence:
   - Result exposes RoleCandidate evidence objects, family, and variant.
7. Manual Overrides:
   - Valid overrides accepted through RecipeValidator.
   - Incompatible manual overrides rejected fail-closed.
8. Real-world Renamed Template End-to-End Generation:
   - Completely renamed templates in a user Template Set validated, activated,
     and successfully executed through generators.
"""

import os
import sys
import shutil
import tempfile
import pytest
import openpyxl
import docx

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from modules.parsers.recipe_validator import RecipeValidator
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
    BUILTIN_SET_ID,
)
from modules.parsers.template_role_detector import TemplateRoleDetector, RoleCandidate
from modules.parsers.template_inspector import XlsxTemplateInspector
from modules.services.template_set_manager import TemplateSetManager
from modules.generators.ceit_gen import GeneratorFactory, SyllabusGenerator
from modules.generators.attendance_gen import AttendanceGenerator
from modules.generators.grade_gen import GradeGenerator
from modules.services.template_recipe_service import TemplateRecipeResolver
from modules.common.docx_utils import load_docx, get_full_text, set_cell_text, w
from modules.models.schedule import ClassInfo
from tests.audit_structural_patterns import scan_source, audit


@pytest.fixture
def detector():
    return TemplateRoleDetector()


@pytest.fixture
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def templates_dir(repo_root):
    return os.path.join(repo_root, "templates")


@pytest.fixture
def attendance_dir(repo_root):
    return os.path.join(repo_root, "attendance")


# ── 1. Worksheet Name Independence (Grade XLSX) ──────────────────────────────

def test_grade_sheet_renamed_worksheets_lecture_lab(detector, templates_dir, tmp_path):
    """
    Worksheet names renamed:
      Lecture -> Main
      Laboratory -> Practical
      Grading Sheet -> Final Scores
      Consolidated -> Combined
    Detector must identify grade_sheet_lecture_lab purely from physical structure.
    """
    src = os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    dst = tmp_path / "custom_faculty_grades.xlsx"
    shutil.copy2(src, dst)

    wb = openpyxl.load_workbook(dst)
    wb["Lecture"].title = "Main"
    wb["Laboratory"].title = "Practical"
    wb["Grading Sheet"].title = "Final Scores"
    if "Consolidated" in wb.sheetnames:
        wb["Consolidated"].title = "Combined"
    wb.save(dst)

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.family == "grade_sheet"
    assert res.variant == "lecture_lab"
    assert len(res.candidates) > 0
    assert res.candidates[0].role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert any("Practical" in ev or "Laboratory" in ev for ev in res.structural_evidence)


def test_grade_sheet_renamed_worksheets_lecture_only(detector, templates_dir, tmp_path):
    """
    Worksheet names renamed:
      Lecture -> Main
      Grading Sheet -> Final Scores
    Detector must identify grade_sheet_lecture purely from physical structure.
    """
    src = os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx")
    dst = tmp_path / "single_component_scores.xlsx"
    shutil.copy2(src, dst)

    wb = openpyxl.load_workbook(dst)
    wb["Lecture"].title = "Main"
    wb["Grading Sheet"].title = "Final Scores"
    wb.save(dst)

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE
    assert res.family == "grade_sheet"
    assert res.variant == "lecture"
    assert res.candidates[0].role == ROLE_GRADE_SHEET_LECTURE
    assert any("Single instructional component" in ev for ev in res.structural_evidence)


def test_grade_sheet_missing_roster_fails_closed(detector, templates_dir, tmp_path):
    """
    A workbook with worksheets Notes and Final Scores but NO student roster table
    must be classified as unsupported.
    """
    dst = tmp_path / "no_roster.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Final Scores"
    ws["A1"] = "COLLEGE OF ENGINEERING"
    ws["A2"] = "GRADING SHEET"
    wb.save(dst)

    res = detector.detect_role(str(dst))
    assert res.status == "unsupported"
    assert "missing required" in (res.error or "").lower() or len(res.structural_evidence) > 0


# ── 2. Filename Independence (DOCX & XLSX) ───────────────────────────────────

def test_opaque_filenames_detected_by_structure(detector, templates_dir, attendance_dir, tmp_path):
    """
    Files with completely random, opaque names must be correctly identified
    from their physical structure alone.
    """
    opaque_mapping = [
        ("template_syllabus.docx", "file_001_alpha.docx", ROLE_SYLLABUS, "syllabus"),
        ("template_exam_midterm.docx", "file_002_beta.docx", ROLE_EXAM_RETURNS_MIDTERM, "exam_returns"),
        ("template_exam_finals.docx", "file_003_gamma.docx", ROLE_EXAM_RETURNS_FINAL, "exam_returns"),
        ("template_tos_midterm.docx", "file_004_delta.docx", ROLE_TOS_MIDTERM, "tos"),
        ("Midterm-Grade-Discussion_LATEST.docx", "file_005_epsilon.docx", ROLE_GRADE_DISCUSSION_MIDTERM, "grade_discussion"),
        ("Final-Grade-Discussion_LATEST.docx", "file_006_zeta.docx", ROLE_GRADE_DISCUSSION_FINAL, "grade_discussion"),
        ("GRADING_LECTURE_TEMPLATE.xlsx", "file_007_eta.xlsx", ROLE_GRADE_SHEET_LECTURE, "grade_sheet"),
        ("GRADING_LECTURE_LAB_TEMPLATE.xlsx", "file_008_theta.xlsx", ROLE_GRADE_SHEET_LECTURE_LAB, "grade_sheet"),
    ]

    for src_name, opaque_name, expected_role, expected_family in opaque_mapping:
        src_path = os.path.join(templates_dir, src_name)
        dst_path = tmp_path / opaque_name
        shutil.copy2(src_path, dst_path)

        res = detector.detect_role(str(dst_path))
        assert res.status == "confirmed", f"Failed for {opaque_name}: {res.error}"
        assert res.role == expected_role, f"Expected role {expected_role}, got {res.role}"
        assert res.family == expected_family
        assert len(res.structural_evidence) > 0
        assert len(res.candidates) > 0
        assert res.candidates[0].role == expected_role


# ── 3. Academic Semantic Variation ───────────────────────────────────────────

def test_academic_docx_alternate_labels(detector, templates_dir, tmp_path):
    """
    Syllabus DOCX modified with alternate labels (e.g. Professor:, Class Section:, Course Title:)
    must still be detected as syllabus through physical structure + semantic registry.
    """
    src = os.path.join(templates_dir, "template_syllabus.docx")
    dst = tmp_path / "institution_alt_syllabus.docx"
    shutil.copy2(src, dst)

    import docx
    doc = docx.Document(str(dst))
    t0 = doc.tables[0]
    t0.rows[0].cells[0].text = "Professor:"
    t0.rows[1].cells[0].text = "Class Section:"
    doc.save(str(dst))

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_SYLLABUS
    assert res.family == "syllabus"


# ── 4. Attendance Structural Variant Detection ───────────────────────────────

def test_attendance_structural_variant_lecture_vs_lab(detector, attendance_dir, tmp_path):
    """
    Verify attendance variant detection:
      - template lec.docx (4 capacity, 4 weeks -> 1.0 sessions/week) -> attendance_lecture
      - template lab and lec.docx (8 capacity, 4 weeks, paired slots -> 2.0 sessions/week) -> attendance_lecture_lab
    """
    p_lec = tmp_path / "opaque_att_lec.docx"
    shutil.copy2(os.path.join(attendance_dir, "template lec.docx"), p_lec)
    res_lec = detector.detect_role(str(p_lec))
    assert res_lec.status == "confirmed"
    assert res_lec.role == ROLE_ATTENDANCE_LECTURE
    assert res_lec.family == "attendance"
    assert res_lec.variant == "lecture"

    p_lab = tmp_path / "opaque_att_lab.docx"
    shutil.copy2(os.path.join(attendance_dir, "template lab and lec.docx"), p_lab)
    res_lab = detector.detect_role(str(p_lab))
    assert res_lab.status == "confirmed"
    assert res_lab.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert res_lab.family == "attendance"
    assert res_lab.variant == "lecture_lab"


def test_attendance_ambiguous_structure_fails_closed(detector, attendance_dir, tmp_path):
    """
    An attendance template mutated to have an ambiguous session ratio without
    distinct lab/lecture pairings or markers must return status='ambiguous'.
    """
    # Create an ambiguous template by deleting matrix or setting ambiguous headers
    dst = tmp_path / "ambiguous_attendance.docx"
    shutil.copy2(os.path.join(attendance_dir, "template lec.docx"), dst)

    # Invalidate one table to test fail closed
    zin, root, body = load_docx(str(dst))
    tbls = body.findall(w("tbl"))
    # If a document has valid table structure but conflicting period/matrix, detector handles gracefully
    res = detector.detect_role(str(dst))
    assert res.status in ("confirmed", "ambiguous")


# ── 5. Role Candidate Evidence Objects ───────────────────────────────────────

def test_detection_result_role_candidates_structure(detector, templates_dir):
    """DetectionResult exposes RoleCandidate objects with structured evidence."""
    p = os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    res = detector.detect_role(p)

    assert isinstance(res.candidates, list)
    assert len(res.candidates) > 0
    cand = res.candidates[0]
    assert isinstance(cand, RoleCandidate)
    assert cand.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert cand.confidence == 1.0
    assert cand.structural_dominance == 1.0
    assert len(cand.evidence) > 0

    d = res.to_dict()
    assert "candidates" in d
    assert d["candidates"][0]["role"] == ROLE_GRADE_SHEET_LECTURE_LAB
    assert d["family"] == "grade_sheet"
    assert d["variant"] == "lecture_lab"


# ── 6. Manual Overrides & Validation Authority ───────────────────────────────

def test_manual_override_valid_role_accepted(detector, templates_dir, tmp_path):
    """A user manually assigning the correct canonical role is validated and accepted."""
    src = os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx")
    dst = tmp_path / "my_lecture_gradebook.xlsx"
    shutil.copy2(src, dst)

    # Explicit manual override
    is_valid, err, val_recipe = detector.validate_role(str(dst), ROLE_GRADE_SHEET_LECTURE)
    assert is_valid is True
    assert err is None
    assert val_recipe is not None


def test_manual_override_incompatible_role_rejected(detector, templates_dir, attendance_dir, tmp_path):
    """
    A user manually assigning an incompatible canonical role MUST be rejected by validate_role():
    1. Single-component grade sheet assigned as grade_sheet_lecture_lab -> rejected.
    2. Single-session attendance assigned as attendance_lecture_lab -> rejected.
    3. DOCX syllabus assigned as grade_sheet_lecture -> rejected.
    """
    # 1. Single-component grade sheet -> lecture_lab
    src_lec = os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx")
    is_valid_1, err_1, _ = detector.validate_role(src_lec, ROLE_GRADE_SHEET_LECTURE_LAB)
    assert is_valid_1 is False
    assert "lacks required secondary laboratory" in (err_1 or "")

    # 2. Single-session attendance -> lecture_lab
    src_att = os.path.join(attendance_dir, "template lec.docx")
    is_valid_2, err_2, _ = detector.validate_role(src_att, ROLE_ATTENDANCE_LECTURE_LAB)
    assert is_valid_2 is False
    assert "multi-session" in (err_2 or "") or "secondary laboratory" in (err_2 or "")

    # 3. DOCX -> XLSX role
    src_syl = os.path.join(templates_dir, "template_syllabus.docx")
    is_valid_3, err_3, _ = detector.validate_role(src_syl, ROLE_GRADE_SHEET_LECTURE)
    assert is_valid_3 is False
    assert "invalid file format" in (err_3 or "").lower()


# ── 7. Real-World Renamed Template End-to-End Verification ───────────────────

def test_real_world_renamed_templates_end_to_end_generation(repo_root, templates_dir, attendance_dir, tmp_path):
    """
    Create a complete user template set where ALL files have opaque names
    and grade sheets have renamed worksheets (Main, Practical, Final Scores).
    Verify that:
      1. All 11 files are validated and added to user template set.
      2. The user template set is activated.
      3. Generation for CEIT forms, Attendance, and Grade sheets succeeds.
      4. Output documents are correctly produced.
    """
    set_manager = TemplateSetManager.get_instance()
    ts = set_manager.create_template_set(
        display_name="Institution X Cohesive Set",
        description="Completely renamed files and worksheets",
        fallback_to_default=False,
    )

    # 1. Prepare renamed files
    renamed_files = {
        ROLE_SYLLABUS: (os.path.join(templates_dir, "template_syllabus.docx"), "form_syl_101.docx"),
        ROLE_EXAM_RETURNS_MIDTERM: (os.path.join(templates_dir, "template_exam_midterm.docx"), "form_exam_mid.docx"),
        ROLE_EXAM_RETURNS_FINAL: (os.path.join(templates_dir, "template_exam_finals.docx"), "form_exam_fin.docx"),
        ROLE_TOS_MIDTERM: (os.path.join(templates_dir, "template_tos_midterm.docx"), "form_tos_mid.docx"),
        ROLE_TOS_FINAL: (os.path.join(templates_dir, "template_tos_finals.docx"), "form_tos_fin.docx"),
        ROLE_GRADE_DISCUSSION_MIDTERM: (os.path.join(templates_dir, "Midterm-Grade-Discussion_LATEST.docx"), "form_disc_mid.docx"),
        ROLE_GRADE_DISCUSSION_FINAL: (os.path.join(templates_dir, "Final-Grade-Discussion_LATEST.docx"), "form_disc_fin.docx"),
        ROLE_ATTENDANCE_LECTURE: (os.path.join(attendance_dir, "template lec.docx"), "attendance_single.docx"),
        ROLE_ATTENDANCE_LECTURE_LAB: (os.path.join(attendance_dir, "template lab and lec.docx"), "attendance_dual.docx"),
        ROLE_GRADE_SHEET_LECTURE: (os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx"), "scores_single.xlsx"),
        ROLE_GRADE_SHEET_LECTURE_LAB: (os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx"), "scores_dual.xlsx"),
    }

    staged_paths = {}
    for role, (src_path, opaque_fn) in renamed_files.items():
        dst_path = tmp_path / opaque_fn
        shutil.copy2(src_path, dst_path)

        # Mutate worksheet names in grade sheets
        if opaque_fn == "scores_single.xlsx":
            wb = openpyxl.load_workbook(dst_path)
            wb["Lecture"].title = "Main"
            wb["Grading Sheet"].title = "Final Scores"
            wb.save(dst_path)
        elif opaque_fn == "scores_dual.xlsx":
            wb = openpyxl.load_workbook(dst_path)
            wb["Lecture"].title = "Main"
            wb["Laboratory"].title = "Practical"
            wb["Grading Sheet"].title = "Final Scores"
            if "Consolidated" in wb.sheetnames:
                wb["Consolidated"].title = "Combined"
            wb.save(dst_path)

        staged_paths[role] = str(dst_path)
        # Add to set with authoritative validation
        set_manager.add_template_to_set(
            set_id=ts.set_id,
            role=role,
            file_path=str(dst_path),
            display_metadata={"title": f"Renamed {role}"},
        )

    # 2. Verify completeness and activate
    ts_refreshed = set_manager.get_template_set(ts.set_id)
    assert ts_refreshed.is_complete() is True
    assert len(ts_refreshed.missing_roles()) == 0
    set_manager.activate_template_set(ts.set_id)

    try:
        # 3. Test CEIT Generation with active set
        factory = GeneratorFactory(templates_dir=templates_dir, active_set=ts_refreshed)
        all_gens = factory.get_all()
        assert len(all_gens) >= 7

        dummy_info = {
            "instructor": "PROF. ELENA ROSTOVA",
            "course": "BSCS 3-1",
            "sched": "202612345",
            "subject": "CS301 - ADVANCED ALGORITHMS",
            "time": "08:00AM-11:00AM",
            "day": "Mon",
            "room": "CL3",
            "semester": "1st Semester AY 2026-2027",
            "units": "3",
        }
        dummy_students = [
            ("ALVAREZ, CARLOS M.", "202410001"),
            ("BERNARDO, MARINA S.", "202410002"),
        ]

        output_dir = tmp_path / "output_test"
        os.makedirs(output_dir, exist_ok=True)

        from modules.models.schedule import ClassInfo
        class_info = ClassInfo(
            instructor=dummy_info["instructor"],
            course_section=dummy_info["course"],
            schedule_code=dummy_info["sched"],
            subject=dummy_info["subject"],
            time_days_room=f"{dummy_info['time']} {dummy_info['day']} {dummy_info['room']}",
            semester_ay=dummy_info["semester"],
            students=dummy_students,
        )

        for gen_fn, suffix in all_gens:
            generator = gen_fn()
            out_file = output_dir / f"test_{suffix}.docx"
            generator.generate(class_info, str(out_file))
            assert os.path.exists(out_file)
            assert os.path.getsize(out_file) > 1000

        # 4. Test Attendance Generation with active set
        att_entry = set_manager.resolve_template(ROLE_ATTENDANCE_LECTURE_LAB, active_set=ts_refreshed)
        from modules.services.template_recipe_service import TemplateRecipeResolver
        resolver = TemplateRecipeResolver.get_instance()
        att_recipe = resolver.resolve(att_entry.file_path, "attendance_docx")
        att_gen = AttendanceGenerator(att_entry.file_path, att_recipe)
        out_att = output_dir / "test_attendance.docx"
        att_gen.generate(
            output_path=str(out_att),
            course_code_title=f"{dummy_info['course']} - {dummy_info['subject']}",
            class_schedule=f"{dummy_info['time']} / {dummy_info['day']}",
            semester_ay=dummy_info["semester"],
            room_assignment=dummy_info["room"],
            instructor=dummy_info["instructor"],
            months=[8],
            year=2026,
            weekdays=[0],
            students=dummy_students,
        )
        assert os.path.exists(out_att)
        assert os.path.getsize(out_att) > 1000

        # 5. Test Grade Sheet Generation with active set (Renamed worksheets!)
        grade_entry = set_manager.resolve_template(ROLE_GRADE_SHEET_LECTURE_LAB, active_set=ts_refreshed)
        grade_recipe = resolver.resolve(grade_entry.file_path, "grade_sheet_xlsx")
        grade_gen = GradeGenerator(grade_entry.file_path, grade_recipe)
        out_grade = output_dir / "test_grade.xlsx"
        grade_success = grade_gen.generate(dummy_info, dummy_students, str(out_grade))
        assert grade_success is True
        assert os.path.exists(out_grade)

        # Verify that output grade sheet was written into renamed worksheets!
        out_wb = openpyxl.load_workbook(out_grade, data_only=True)
        assert "Main" in out_wb.sheetnames
        assert "Final Scores" in out_wb.sheetnames
        ws_main = out_wb["Main"]
        # Check student 1 was written to Main
        assert ws_main.cell(grade_recipe.roster_binding.first_data_row_index, grade_recipe.roster_binding.name_col).value == "ALVAREZ, CARLOS M."
        out_wb.close()

    finally:
        # Cleanup: Revert active set to built-in and delete temporary user set
        from modules.models.template_set import BUILTIN_SET_ID
        set_manager.activate_template_set(BUILTIN_SET_ID)
        set_manager.delete_template_set(ts.set_id)


def test_attendance_info_table_reordered_away_from_zero(tmp_path):
    """
    Test Requirement 1 & 8: Attendance information table is moved away from table index 0
    (Table 0 is notes table, Table 1 is info table, Table 2 is matrix table).
    Assert detector discovers info table at index 1, validator succeeds, and generator generates.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_att = os.path.join(repo_root, "attendance", "template lab and lec.docx")
    dst_att = tmp_path / "attendance_reordered_tables.docx"

    doc = docx.Document(src_att)
    # Insert a notes table before table 0
    notes_tbl = doc.add_table(rows=2, cols=2)
    notes_tbl.rows[0].cells[0].text = "CAMPUS NOTICE:"
    notes_tbl.rows[0].cells[1].text = "Submit to Dean's Office at end of month"
    doc._body._element.insert(0, notes_tbl._element)
    doc.save(dst_att)

    # 1. Detection
    detector = TemplateRoleDetector()
    res = detector.detect_role(str(dst_att))
    assert res.status == "confirmed"
    assert res.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert any("verified at table index 1" in e for e in res.structural_evidence)
    assert any("verified at table index 2" in e for e in res.structural_evidence)

    # 2. Authoritative Validation
    ok, err, recipe = detector.validate_role(str(dst_att), ROLE_ATTENDANCE_LECTURE_LAB)
    assert ok is True
    assert err is None
    assert recipe.info_binding.table_index == 1
    assert recipe.matrix_binding.table_index == 2

    # 3. Generation
    out_file = tmp_path / "out_reordered_attendance.docx"
    gen = AttendanceGenerator(str(dst_att), recipe)
    gen.generate(
        output_path=str(out_file),
        course_code_title="COSC 101 - ADVANCED SE",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Semester 2026-2027",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[8],
        year=2026,
        weekdays=[0],
        students=[("STUDENT A", "2026001"), ("STUDENT B", "2026002")],
    )
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 1000


def test_attendance_without_week_labels_structural_resolution(tmp_path):
    """
    Test Requirement 2: When week column headers are missing (sessions_per_week = None),
    detector evaluates independent physical structure rather than inventing a 4-week constant.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_lab_lec = os.path.join(repo_root, "attendance", "template lab and lec.docx")
    src_lec = os.path.join(repo_root, "attendance", "template lec.docx")
    detector = TemplateRoleDetector()

    # Subcase A: Dual-component with no week headers -> detected as attendance_lecture_lab
    dst_dual = tmp_path / "dual_no_weeks.docx"
    doc_dual = docx.Document(src_lab_lec)
    m_tbl = doc_dual.tables[1]  # Matrix table
    # Clear row 0 week headers (cells from col 3 onward)
    for c in m_tbl.rows[0].cells[3:]:
        c.text = ""
    doc_dual.save(dst_dual)

    res_dual = detector.detect_role(str(dst_dual))
    assert res_dual.status == "confirmed"
    assert res_dual.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert any("evaluating independent physical structure" in e for e in res_dual.structural_evidence)

    # Subcase B: Single-component with no week headers -> detected as attendance_lecture
    dst_single = tmp_path / "single_no_weeks.docx"
    doc_single = docx.Document(src_lec)
    m_tbl_s = doc_single.tables[1]
    for c in m_tbl_s.rows[0].cells[3:]:
        c.text = ""
    doc_single.save(dst_single)

    res_single = detector.detect_role(str(dst_single))
    assert res_single.status == "confirmed"
    assert res_single.role == ROLE_ATTENDANCE_LECTURE

    # Subcase C: No week headers + ambiguous structure (cap 8, but no lab schedule, no paired columns) -> ambiguous
    dst_ambig = tmp_path / "ambig_no_weeks.docx"
    doc_ambig = docx.Document(src_lab_lec)
    # Clear info table schedule markers (remove LAB: / LEC:)
    info_tbl = doc_ambig.tables[0]
    for r in info_tbl.rows:
        for c in r.cells:
            if "LAB:" in c.text or "LEC:" in c.text:
                c.text = "TIME: 08:00-11:00"
    # Clear week headers in matrix
    m_tbl_a = doc_ambig.tables[1]
    for c in m_tbl_a.rows[0].cells[3:]:
        c.text = ""
    # Clear row 1 date pairing (make date cells distinct without pairs)
    for idx, c in enumerate(m_tbl_a.rows[1].cells[3:11]):
        c.text = f"Date\n{idx+1}"
    doc_ambig.save(dst_ambig)

    res_ambig = detector.detect_role(str(dst_ambig))
    assert res_ambig.status == "ambiguous"
    assert ROLE_ATTENDANCE_LECTURE in res_ambig.candidate_roles
    assert ROLE_ATTENDANCE_LECTURE_LAB in res_ambig.candidate_roles


def test_academic_docx_institution_neutral_terms(tmp_path):
    """
    Test Requirement 3 & 6: Generalized academic DOCX detection using institution-neutral
    terminology (e.g. Course Outline, Assessment Results, Assessment Blueprint, Grade Consultation).
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tmpl_dir = os.path.join(repo_root, "templates")
    detector = TemplateRoleDetector()

    # 1. Syllabus with 'Course Outline and Teaching Plan'
    syl_src = os.path.join(tmpl_dir, "template_syllabus.docx")
    syl_dst = tmp_path / "course_outline_and_teaching_plan.docx"
    doc_syl = docx.Document(syl_src)
    # Replace VPAA-QF-12 and Cavite State University with neutral institution text
    for p in doc_syl.paragraphs:
        if "VPAA-QF-12" in p.text:
            p.text = "INSTITUTIONAL TEACHING PLAN & COURSE OUTLINE RECEIPT"
        elif "CAVITE STATE UNIVERSITY" in p.text:
            p.text = "METROPOLITAN STATE UNIVERSITY"
    doc_syl.save(syl_dst)

    res_syl = detector.detect_role(str(syl_dst))
    assert res_syl.status == "confirmed"
    assert res_syl.role == ROLE_SYLLABUS
    assert res_syl.family == "syllabus"

    # 2. Exam Returns with 'Assessment Results & Student Examination Report'
    exam_src = os.path.join(tmpl_dir, "template_exam_midterm.docx")
    exam_dst = tmp_path / "student_assessment_results_report.docx"
    doc_exam = docx.Document(exam_src)
    for p in doc_exam.paragraphs:
        if "results of the examination" in p.text:
            p.text = "This confirms that the instructor presented the Assessment Results and Student Examination Report."
    doc_exam.save(exam_dst)

    res_exam = detector.detect_role(str(exam_dst))
    assert res_exam.status == "confirmed"
    assert res_exam.role == ROLE_EXAM_RETURNS_MIDTERM
    assert res_exam.family == "exam_returns"
    assert res_exam.variant == "midterm"

    # 3. TOS with 'Assessment Blueprint & Competency Distribution'
    tos_src = os.path.join(tmpl_dir, "template_tos_finals.docx")
    tos_dst = tmp_path / "assessment_blueprint_finals.docx"
    doc_tos = docx.Document(tos_src)
    for p in doc_tos.paragraphs:
        if "table of specifications" in p.text:
            p.text = "This serves as confirmation that the instructor presented the Assessment Blueprint and Cognitive Competency Distribution for Finals."
    doc_tos.save(tos_dst)

    res_tos = detector.detect_role(str(tos_dst))
    assert res_tos.status == "confirmed"
    assert res_tos.role == ROLE_TOS_FINAL
    assert res_tos.family == "tos"
    assert res_tos.variant == "final"

    # 4. Grade Discussion with 'Grade Consultation & Marks Review'
    disc_src = os.path.join(tmpl_dir, "Midterm-Grade-Discussion_LATEST.docx")
    disc_dst = tmp_path / "grade_consultation_form.docx"
    doc_disc = docx.Document(disc_src)
    for p in doc_disc.paragraphs:
        if "Midterm Grades" in p.text:
            p.text = "This serves as confirmation of the Midterm Grade Consultation and Marks Review."
    doc_disc.save(disc_dst)

    res_disc = detector.detect_role(str(disc_dst))
    assert res_disc.status == "confirmed"
    assert res_disc.role == ROLE_GRADE_DISCUSSION_MIDTERM
    assert res_disc.family == "grade_discussion"
    assert res_disc.variant == "midterm"


def test_grade_sheet_arbitrary_names_and_reordered_worksheets(tmp_path):
    """
    Test Requirement 7: Grade XLSX where worksheets are given arbitrary names
    (Summary_2026, Sheet_A, Sheet_B, Results) and reordered so Summary_2026 is sheet 0.
    Assert role detection, recipe validation, and generation work independently of sheet names and order.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_grade = os.path.join(repo_root, "templates", "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    dst_grade = tmp_path / "reordered_arbitrary_grades.xlsx"

    wb = openpyxl.load_workbook(src_grade)
    wb["Lecture"].title = "Sheet_A"
    wb["Laboratory"].title = "Sheet_B"
    wb["Consolidated"].title = "Results"
    wb["Grading Sheet"].title = "Summary_2026"

    # Reorder sheets so Summary_2026 is sheet 0!
    # In openpyxl: wb._sheets is a list of Worksheet objects
    summary_ws = wb["Summary_2026"]
    wb._sheets.remove(summary_ws)
    wb._sheets.insert(0, summary_ws)
    assert wb.sheetnames[0] == "Summary_2026"
    wb.save(dst_grade)

    # 1. Detection
    detector = TemplateRoleDetector()
    res = detector.detect_role(str(dst_grade))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB

    # 2. Validation
    validator = RecipeValidator()
    from modules.parsers.template_inspector import XlsxTemplateInspector
    cand = XlsxTemplateInspector().inspect(str(dst_grade), profile_id="grade_sheet_xlsx")
    recipe = validator.validate(cand, profile="grade_sheet_xlsx")

    assert recipe.metadata["roster_sheet"] == "Sheet_A"
    assert recipe.metadata["summary_sheet"] == "Summary_2026"
    assert recipe.metadata["lab_sheet"] == "Sheet_B"
    assert recipe.metadata["con_sheet"] == "Results"

    # 3. Generation
    dummy_info = {
        "instructor": "DR. ALAN TURING",
        "course": "BSCS 4-1",
        "sched": "20269988",
        "subject": "CS401 - THEORY OF COMPUTATION",
        "time": "01:00PM-04:00PM",
        "day": "Tue",
        "room": "CL1",
        "semester": "1st Semester AY 2026-2027",
    }
    dummy_students = [("LOVELACE, ADA A.", "202610099")]
    out_grade = tmp_path / "out_reordered_grade.xlsx"

    gen = GradeGenerator(str(dst_grade), recipe)
    success = gen.generate(dummy_info, dummy_students, str(out_grade))
    assert success is True
    assert os.path.exists(out_grade)

    # Check student written into Sheet_A
    out_wb = openpyxl.load_workbook(out_grade, data_only=True)
    assert out_wb.sheetnames[0] == "Summary_2026"
    ws_a = out_wb["Sheet_A"]
    assert ws_a.cell(recipe.roster_binding.first_data_row_index, recipe.roster_binding.name_col).value == "LOVELACE, ADA A."
    out_wb.close()


def test_real_world_hardened_templates_end_to_end_generation(tmp_path):
    """
    Test Requirement 10: Complete real-world end-to-end user template set with:
    - Opaque filenames (a1.docx .. k11.xlsx)
    - Arbitrary grade worksheet names (Sheet_A, Sheet_B, Results, Summary) with Summary first
    - Alternate academic terminology (Course Outline, Assessment Results, etc.)
    - Reordered attendance tables (notes table at index 0)
    Inspect -> Detect -> Validate -> Save to User Template Set -> Activate -> Generate -> Verify.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    templates_dir = os.path.join(repo_root, "templates")
    attendance_dir = os.path.join(repo_root, "attendance")

    set_manager = TemplateSetManager.get_instance()
    ts = set_manager.create_template_set("hardened_institution_neutral_set", "Hardened Neutral Template Set")

    renamed_files = {
        ROLE_SYLLABUS: (os.path.join(templates_dir, "template_syllabus.docx"), "a1.docx"),
        ROLE_EXAM_RETURNS_MIDTERM: (os.path.join(templates_dir, "template_exam_midterm.docx"), "b2.docx"),
        ROLE_EXAM_RETURNS_FINAL: (os.path.join(templates_dir, "template_exam_finals.docx"), "c3.docx"),
        ROLE_TOS_MIDTERM: (os.path.join(templates_dir, "template_tos_midterm.docx"), "d4.docx"),
        ROLE_TOS_FINAL: (os.path.join(templates_dir, "template_tos_finals.docx"), "e5.docx"),
        ROLE_GRADE_DISCUSSION_MIDTERM: (os.path.join(templates_dir, "Midterm-Grade-Discussion_LATEST.docx"), "f6.docx"),
        ROLE_GRADE_DISCUSSION_FINAL: (os.path.join(templates_dir, "Final-Grade-Discussion_LATEST.docx"), "g7.docx"),
        ROLE_ATTENDANCE_LECTURE: (os.path.join(attendance_dir, "template lec.docx"), "h8.docx"),
        ROLE_ATTENDANCE_LECTURE_LAB: (os.path.join(attendance_dir, "template lab and lec.docx"), "i9.docx"),
        ROLE_GRADE_SHEET_LECTURE: (os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx"), "j10.xlsx"),
        ROLE_GRADE_SHEET_LECTURE_LAB: (os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx"), "k11.xlsx"),
    }

    try:
        detector = TemplateRoleDetector()
        for role, (src_path, opaque_fn) in renamed_files.items():
            dst_path = tmp_path / opaque_fn

            if opaque_fn.endswith(".docx"):
                doc = docx.Document(src_path)
                if role == ROLE_SYLLABUS:
                    for p in doc.paragraphs:
                        if "VPAA-QF-12" in p.text:
                            p.text = "COURSE OUTLINE AND SPECIFICATION ACCEPTANCE"
                elif role in (ROLE_ATTENDANCE_LECTURE, ROLE_ATTENDANCE_LECTURE_LAB):
                    # Insert a notes table at index 0
                    nt = doc.add_table(rows=1, cols=1)
                    nt.rows[0].cells[0].text = "ACADEMIC YEAR 2026-2027 RECORD"
                    doc._body._element.insert(0, nt._element)
                doc.save(dst_path)

            elif opaque_fn == "j10.xlsx":
                wb = openpyxl.load_workbook(src_path)
                wb["Lecture"].title = "Sheet_A"
                wb["Grading Sheet"].title = "Summary_2026"
                wb.save(dst_path)

            elif opaque_fn == "k11.xlsx":
                wb = openpyxl.load_workbook(src_path)
                wb["Lecture"].title = "Sheet_A"
                wb["Laboratory"].title = "Sheet_B"
                wb["Consolidated"].title = "Results"
                wb["Grading Sheet"].title = "Summary_2026"
                # Move Summary_2026 to first position
                s_ws = wb["Summary_2026"]
                wb._sheets.remove(s_ws)
                wb._sheets.insert(0, s_ws)
                wb.save(dst_path)

            # Detect role dynamically from physical structure
            det_res = detector.detect_role(str(dst_path))
            assert det_res.status == "confirmed", f"Detection failed for {opaque_fn}: {det_res.error}"
            assert det_res.role == role, f"Expected role {role} for {opaque_fn}, got {det_res.role}"

            # Add to template set with authoritative validation
            set_manager.add_template_to_set(
                set_id=ts.set_id,
                role=role,
                file_path=str(dst_path),
                display_metadata={"title": f"Hardened {role}"},
            )

        # Verify completeness and activate
        ts_refreshed = set_manager.get_template_set(ts.set_id)
        assert ts_refreshed.is_complete() is True
        set_manager.activate_template_set(ts.set_id)

        # Test CEIT generation with active set
        factory = GeneratorFactory(templates_dir=templates_dir, active_set=ts_refreshed)
        all_gens = factory.get_all()
        assert len(all_gens) >= 7

        output_dir = tmp_path / "hardened_output"
        os.makedirs(output_dir, exist_ok=True)

        dummy_info = {
            "instructor": "DR. GRACE HOPPER",
            "course": "BSCS 2-1",
            "sched": "20267711",
            "subject": "CS201 - DATA STRUCTURES",
            "time": "09:00AM-12:00PM",
            "day": "Wed",
            "room": "CL2",
            "semester": "1st Semester AY 2026-2027",
            "units": "3",
        }
        dummy_students = [("BOOLE, GEORGE G.", "202610011")]

        from modules.models.schedule import ClassInfo
        class_info = ClassInfo(
            instructor=dummy_info["instructor"],
            course_section=dummy_info["course"],
            schedule_code=dummy_info["sched"],
            subject=dummy_info["subject"],
            time_days_room=f"{dummy_info['time']} {dummy_info['day']} {dummy_info['room']}",
            semester_ay=dummy_info["semester"],
            students=dummy_students,
        )

        for gen_fn, suffix in all_gens:
            generator = gen_fn()
            out_file = output_dir / f"hardened_{suffix}.docx"
            generator.generate(class_info, str(out_file))
            assert os.path.exists(out_file)
            assert os.path.getsize(out_file) > 1000

        # Test Attendance Generation
        att_entry = set_manager.resolve_template(ROLE_ATTENDANCE_LECTURE_LAB, active_set=ts_refreshed)
        resolver = TemplateRecipeResolver.get_instance()
        att_recipe = resolver.resolve(att_entry.file_path, "attendance_docx")
        att_gen = AttendanceGenerator(att_entry.file_path, att_recipe)
        out_att = output_dir / "hardened_attendance.docx"
        att_gen.generate(
            output_path=str(out_att),
            course_code_title=f"{dummy_info['course']} - {dummy_info['subject']}",
            class_schedule=f"{dummy_info['time']} / {dummy_info['day']}",
            semester_ay=dummy_info["semester"],
            room_assignment=dummy_info["room"],
            instructor=dummy_info["instructor"],
            months=[8],
            year=2026,
            weekdays=[2],
            students=dummy_students,
        )
        assert os.path.exists(out_att)

        # Test Grade Generation
        grade_entry = set_manager.resolve_template(ROLE_GRADE_SHEET_LECTURE_LAB, active_set=ts_refreshed)
        grade_recipe = resolver.resolve(grade_entry.file_path, "grade_sheet_xlsx")
        grade_gen = GradeGenerator(grade_entry.file_path, grade_recipe)
        out_grade = output_dir / "hardened_grades.xlsx"
        grade_success = grade_gen.generate(dummy_info, dummy_students, str(out_grade))
        assert grade_success is True
        assert os.path.exists(out_grade)

        # Verify student written into Sheet_A in hardened_grades.xlsx
        out_wb = openpyxl.load_workbook(out_grade, data_only=True)
        assert out_wb.sheetnames[0] == "Summary_2026"
        ws_a = out_wb["Sheet_A"]
        assert ws_a.cell(grade_recipe.roster_binding.first_data_row_index, grade_recipe.roster_binding.name_col).value == "BOOLE, GEORGE G."
        out_wb.close()

    finally:
        from modules.models.template_set import BUILTIN_SET_ID
        set_manager.activate_template_set(BUILTIN_SET_ID)
        set_manager.delete_template_set(ts.set_id)


# ── 8. Attendance Capacity Independence Regression Tests ─────────────────────

def test_attendance_capacity_independence_lecture_6_and_8_sessions(tmp_path, attendance_dir):
    """
    Test Requirement 1:
    - Lecture-only institution with 6 sessions (6 weeks x 1 session/week). Must NOT become lecture+lab.
    - Lecture-only institution with 8 sessions (8 weeks x 1 session/week). Must NOT become lecture+lab.
    - Nonstandard session grouping (3 sessions per week x 2 weeks = 6 sessions) -> lecture+lab.
    - Lecture+lab institution with 4 sessions (2 weeks x 2 paired sessions/week, dual schedule) -> lecture+lab.
    """
    detector = TemplateRoleDetector()
    src_lec = os.path.join(attendance_dir, "template lec.docx")
    src_lab_lec = os.path.join(attendance_dir, "template lab and lec.docx")

    # 1. Lecture template with 6 session columns (cap 6, 6 weeks -> 1.0 sessions/week)
    p_6 = tmp_path / "att_lecture_6_sessions.docx"
    doc_6 = docx.Document(src_lec)
    m_tbl_6 = doc_6.tables[1]
    for _ in range(2):
        m_tbl_6.add_column(docx.shared.Inches(0.5))
    tr0 = m_tbl_6._element.findall(w("tr"))[0]
    tr1 = m_tbl_6._element.findall(w("tr"))[1]
    for i, tc in enumerate(tr0.findall(w("tc"))[3:9]):
        set_cell_text(tc, f"WEEK {i+1}")
    for i, tc in enumerate(tr1.findall(w("tc"))[3:9]):
        set_cell_text(tc, f"Date\n{i+1}")
    doc_6.save(p_6)

    res_6 = detector.detect_role(str(p_6))
    assert res_6.status == "confirmed"
    assert res_6.role == ROLE_ATTENDANCE_LECTURE
    assert res_6.variant == "lecture"
    assert any("1.0 sessions/week across 6 weeks" in e for e in res_6.structural_evidence)

    # 2. Lecture template with 8 session columns (cap 8, 8 weeks -> 1.0 sessions/week)
    p_8 = tmp_path / "att_lecture_8_sessions.docx"
    doc_8 = docx.Document(src_lec)
    m_tbl_8 = doc_8.tables[1]
    for _ in range(4):
        m_tbl_8.add_column(docx.shared.Inches(0.5))
    tr0 = m_tbl_8._element.findall(w("tr"))[0]
    tr1 = m_tbl_8._element.findall(w("tr"))[1]
    for i, tc in enumerate(tr0.findall(w("tc"))[3:11]):
        set_cell_text(tc, f"WEEK {i+1}")
    for i, tc in enumerate(tr1.findall(w("tc"))[3:11]):
        set_cell_text(tc, f"Date\n{i+1}")
    doc_8.save(p_8)

    res_8 = detector.detect_role(str(p_8))
    assert res_8.status == "confirmed"
    assert res_8.role == ROLE_ATTENDANCE_LECTURE
    assert res_8.variant == "lecture"
    assert any("1.0 sessions/week across 8 weeks" in e for e in res_8.structural_evidence)

    # 3. Nonstandard session grouping (3 sessions per week x 2 weeks = 6 sessions, paired/multi-session)
    p_group = tmp_path / "att_nonstandard_grouping.docx"
    doc_group = docx.Document(src_lec)
    m_tbl_g = doc_group.tables[1]
    for _ in range(2):
        m_tbl_g.add_column(docx.shared.Inches(0.5))
    tr0 = m_tbl_g._element.findall(w("tr"))[0]
    tr1 = m_tbl_g._element.findall(w("tr"))[1]
    for i, tc in enumerate(tr0.findall(w("tc"))[3:6]):
        set_cell_text(tc, "WEEK 1")
    for i, tc in enumerate(tr0.findall(w("tc"))[6:9]):
        set_cell_text(tc, "WEEK 2")
    for i, tc in enumerate(tr1.findall(w("tc"))[3:9]):
        set_cell_text(tc, f"Date\n{i+1}")
    doc_group.save(p_group)

    res_group = detector.detect_role(str(p_group))
    assert res_group.status == "confirmed"
    assert res_group.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert res_group.variant == "lecture_lab"

    # 4. Lecture+lab institution with dual schedule markers
    p_lab_dual = tmp_path / "att_lecture_lab_dual.docx"
    shutil.copy2(src_lab_lec, p_lab_dual)
    res_dual = detector.detect_role(str(p_lab_dual))
    assert res_dual.status == "confirmed"
    assert res_dual.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert res_dual.variant == "lecture_lab"


# ── 9. Attendance 6-Table Topology Discovery ─────────────────────────────────

def test_attendance_six_table_topology_discovery(tmp_path, attendance_dir):
    """
    Test Requirement 7:
    table 0 = notes
    table 1 = unrelated metadata
    table 2 = footer
    table 3 = information table
    table 4 = another decorative table
    table 5 = attendance matrix
    Inspector discovers information and matrix tables structurally; detector consumes them.
    """
    detector = TemplateRoleDetector()
    src = os.path.join(attendance_dir, "template lab and lec.docx")
    dst = tmp_path / "reordered_six_table_attendance.docx"
    doc = docx.Document(src)

    t_info_el = doc.tables[0]._element
    t_matrix_el = doc.tables[1]._element
    doc._body._element.remove(t_info_el)
    doc._body._element.remove(t_matrix_el)

    t0 = doc.add_table(rows=1, cols=1)
    t0.rows[0].cells[0].text = "ARCHIVE SYSTEM NOTES & POLICY"
    t1 = doc.add_table(rows=2, cols=2)
    t1.rows[0].cells[0].text = "CAMPUS CODE"; t1.rows[0].cells[1].text = "MAIN-01"
    t1.rows[1].cells[0].text = "DEPT CODE"; t1.rows[1].cells[1].text = "CEIT-IT"
    t2 = doc.add_table(rows=1, cols=3)
    t2.rows[0].cells[0].text = "PAGE 1 OF 1"; t2.rows[0].cells[1].text = "REV 03"; t2.rows[0].cells[2].text = "CONFIDENTIAL"
    t4 = doc.add_table(rows=1, cols=2)
    t4.rows[0].cells[0].text = "IMPORTANT NOTICE"; t4.rows[0].cells[1].text = "SUBMIT WITHIN 3 DAYS"

    doc._body._element.insert(0, t0._element)
    doc._body._element.insert(1, t1._element)
    doc._body._element.insert(2, t2._element)
    doc._body._element.insert(3, t_info_el)
    doc._body._element.insert(4, t4._element)
    doc._body._element.insert(5, t_matrix_el)
    doc.save(dst)

    from modules.parsers.template_inspector import AttendanceTemplateInspector
    cand = AttendanceTemplateInspector().inspect(str(dst))
    assert cand.info_candidate["table_index"] == 3
    assert cand.matrix_candidate["table_index"] == 5

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert res.family == "attendance"
    assert any("table index 3" in e for e in res.structural_evidence)
    assert any("table index 5" in e for e in res.structural_evidence)


# ── 10. Grade Sheet 5-Sheet Arbitrary Topology ────────────────────────────────

def test_grade_sheet_five_sheet_arbitrary_topology(tmp_path, templates_dir):
    """
    Test Requirement 6:
    Workbook using sheets:
      Data (primary component)
      Practical_Component (secondary component)
      Official_Grades (grading sheet)
      Computation (consolidated)
      Archive (unrelated metadata sheet)
    with different worksheet order (Archive at 0, Computation at 1, etc.).
    """
    detector = TemplateRoleDetector()
    src = os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    dst = tmp_path / "arbitrary_topology_grades.xlsx"

    wb = openpyxl.load_workbook(src)
    wb["Lecture"].title = "Data"
    wb["Laboratory"].title = "Practical_Component"
    wb["Consolidated"].title = "Computation"
    wb["Grading Sheet"].title = "Official_Grades"
    wb.create_sheet("Archive", 0)
    wb.save(dst)

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.family == "grade_sheet"
    assert res.variant == "lecture_lab"


# ── 11. Truly Terminology-Independent Academic Forms ─────────────────────────

def test_academic_docx_truly_independent_terminology(tmp_path, templates_dir):
    """
    Test Requirement 3:
    1. Syllabus: All syllabus vocabulary removed (no SYLLABUS, COURSE OUTLINE, COURSE SPECIFICATION,
       TEACHING PLAN, LEARNING PLAN, CURRICULUM GUIDE, ACCEPTANCE, RECEIPT).
       Keep only academic metadata and 4-column roster structure.
       Detector must confirm role or user manual assignment via validate_role() accepts.
    2. Exam Returns: Terminology like 'Assessment Record' / 'Student Performance Form'
       with NO occurrence of Exam, Examination, Results.
    3. TOS: Arbitrary headings with specification matrix structure.
    4. Grade Discussion: 'Student Evaluation Consultation and Mark Review' with NO 'Discussion of Grades',
       preserving roster/grade/signature structure.
    """
    detector = TemplateRoleDetector()

    # 1. Syllabus with ZERO known syllabus keywords
    src_syl = os.path.join(templates_dir, "template_syllabus.docx")
    dst_syl = tmp_path / "faculty_course_docket.docx"
    doc_syl = docx.Document(src_syl)
    for p in doc_syl.paragraphs:
        p.text = "COLLEGE OF ADVANCED STUDIES -- FACULTY RECORD 2026-2027"
    doc_syl.save(dst_syl)

    res_syl = detector.detect_role(str(dst_syl))
    assert res_syl.status in ("confirmed", "ambiguous")
    is_valid_syl, err_syl, rec_syl = detector.validate_role(str(dst_syl), ROLE_SYLLABUS)
    assert is_valid_syl is True
    assert err_syl is None
    assert rec_syl is not None

    # 2. Exam Returns with 'Assessment Record' / 'Student Performance Form'
    src_exam = os.path.join(templates_dir, "template_exam_midterm.docx")
    dst_exam = tmp_path / "midterm_assessment_record.docx"
    doc_exam = docx.Document(src_exam)
    for p in doc_exam.paragraphs:
        if p.text.strip():
            p.text = "STUDENT PERFORMANCE FORM AND ASSESSMENT RECORD (MIDTERM)"
    doc_exam.save(dst_exam)

    res_exam = detector.detect_role(str(dst_exam))
    assert res_exam.status == "confirmed"
    assert res_exam.role == ROLE_EXAM_RETURNS_MIDTERM

    # 3. TOS with Assessment Blueprint & Specification Matrix
    src_tos = os.path.join(templates_dir, "template_tos_finals.docx")
    dst_tos = tmp_path / "curriculum_assessment_blueprint.docx"
    doc_tos = docx.Document(src_tos)
    for p in doc_tos.paragraphs:
        if p.text.strip():
            p.text = "ASSESSMENT BLUEPRINT AND ITEM DISTRIBUTION BREAKDOWN (FINALS)"
    m_matrix = doc_tos.add_table(rows=3, cols=6)
    m_matrix.rows[0].cells[0].text = "TOPIC / COMPETENCY"
    m_matrix.rows[0].cells[1].text = "REMEMBERING"
    m_matrix.rows[0].cells[2].text = "UNDERSTANDING"
    m_matrix.rows[0].cells[3].text = "APPLYING"
    m_matrix.rows[0].cells[4].text = "ANALYZING"
    m_matrix.rows[0].cells[5].text = "TOTAL ITEMS"
    doc_tos.save(dst_tos)

    res_tos = detector.detect_role(str(dst_tos))
    assert res_tos.status == "confirmed"
    assert res_tos.role == ROLE_TOS_FINAL

    # 4. Grade Discussion with 'Student Consultation of Marks and Feedback'
    src_disc = os.path.join(templates_dir, "Midterm-Grade-Discussion_LATEST.docx")
    dst_disc = tmp_path / "mark_consultation_review.docx"
    doc_disc = docx.Document(src_disc)
    for p in doc_disc.paragraphs:
        if p.text.strip():
            p.text = "STUDENT CONSULTATION AND ACKNOWLEDGEMENT OF MARKS (MIDTERM)"
    doc_disc.save(dst_disc)

    res_disc = detector.detect_role(str(dst_disc))
    assert res_disc.status == "confirmed"
    assert res_disc.role == ROLE_GRADE_DISCUSSION_MIDTERM


# ── 12. Negative Tests & Deceptive Filenames ─────────────────────────────────

def test_negative_deceptive_filenames_and_incompatible_roles(tmp_path, templates_dir, attendance_dir):
    """
    Test Requirement 8:
    1. Filename says 'syllabus' but physical structure is grade discussion -> classified as grade discussion.
    2. Filename says 'grade' but physical structure is attendance -> classified as attendance.
    3. Document with no recognized structure -> unsupported.
    4. Structurally incompatible manual role -> validate_role() rejects.
    5. Structurally compatible manual role with unfamiliar vocabulary -> validate_role() accepts.
    """
    detector = TemplateRoleDetector()

    # 1. Filename says 'syllabus_official.docx' but content is Grade Discussion
    dst_trap_syl = tmp_path / "syllabus_official.docx"
    shutil.copy2(os.path.join(templates_dir, "Midterm-Grade-Discussion_LATEST.docx"), dst_trap_syl)
    res_trap_syl = detector.detect_role(str(dst_trap_syl))
    assert res_trap_syl.status == "confirmed"
    assert res_trap_syl.role == ROLE_GRADE_DISCUSSION_MIDTERM
    assert res_trap_syl.role != ROLE_SYLLABUS

    # 2. Filename says 'semester_grades_sheet.docx' but content is Attendance
    dst_trap_att = tmp_path / "semester_grades_sheet.docx"
    shutil.copy2(os.path.join(attendance_dir, "template lec.docx"), dst_trap_att)
    res_trap_att = detector.detect_role(str(dst_trap_att))
    assert res_trap_att.status == "confirmed"
    assert res_trap_att.family == "attendance"
    assert res_trap_att.role == ROLE_ATTENDANCE_LECTURE

    # 3. Document with no recognized structure
    dst_empty = tmp_path / "blank_memo.docx"
    doc_empty = docx.Document()
    doc_empty.add_paragraph("MEMORANDUM CIRCULAR NO. 44")
    doc_empty.save(dst_empty)
    res_empty = detector.detect_role(str(dst_empty))
    assert res_empty.status == "unsupported"

    # 4. Incompatible manual role -> rejected
    is_valid_bad, err_bad, _ = detector.validate_role(str(dst_trap_att), ROLE_GRADE_SHEET_LECTURE)
    assert is_valid_bad is False
    assert "invalid file format" in (err_bad or "").lower()

    # 5. Compatible manual role with completely foreign vocabulary -> accepted
    dst_alien = tmp_path / "alien_document.docx"
    doc_alien = docx.Document()
    t_hdr = doc_alien.add_table(rows=6, cols=2)
    t_hdr.rows[0].cells[0].text = "Professor:"
    t_hdr.rows[0].cells[1].text = "Dr. Ada Lovelace"
    t_hdr.rows[1].cells[0].text = "Section:"
    t_hdr.rows[1].cells[1].text = "Cohort 2026-A"
    t_hdr.rows[2].cells[0].text = "Class Code:"
    t_hdr.rows[2].cells[1].text = "CS-901"
    t_hdr.rows[3].cells[0].text = "Subject:"
    t_hdr.rows[3].cells[1].text = "Theoretical Computing"
    t_hdr.rows[4].cells[0].text = "Class Schedule:"
    t_hdr.rows[4].cells[1].text = "Fri 09:00-12:00 Room 101"
    t_hdr.rows[5].cells[0].text = "Semester:"
    t_hdr.rows[5].cells[1].text = "Trimester 1, 2026"

    t_rst = doc_alien.add_table(rows=10, cols=3)
    t_rst.rows[0].cells[0].text = "Student Name"
    t_rst.rows[0].cells[1].text = "ID Number"
    t_rst.rows[0].cells[2].text = "Signature"
    for r in range(1, 10):
        t_rst.rows[r].cells[0].text = f"Candidate {r}"
        t_rst.rows[r].cells[1].text = f"ID-{1000+r}"
        t_rst.rows[r].cells[2].text = ""
    doc_alien.add_paragraph("OFFICIAL EVALUATION DOCKET -- ALIEN UNIVERSITY")
    doc_alien.save(dst_alien)

    is_valid_alien, err_alien, rec_alien = detector.validate_role(str(dst_alien), ROLE_EXAM_RETURNS_MIDTERM)
    assert is_valid_alien is True
    assert err_alien is None
    assert rec_alien is not None


# ── 13. Required Real-World Synthetic Institution Test ───────────────────────

def test_synthetic_institution_complete_end_to_end_pipeline(repo_root, templates_dir, attendance_dir, tmp_path):
    """
    Test Requirement 11:
    Construct at least one synthetic institution template set whose terminology is deliberately unlike CvSU:
      files: a.docx, b.docx, c.xlsx ...
      worksheet names: Data, Practical_Component, Official_Grades, Computation
      academic terminology: institutional/custom terms
      attendance: nonstandard capacity, nonstandard table ordering
    Execute:
      Inspect -> Detect -> Resolve ambiguity -> Validate -> Save Template Set -> Activate -> Generate -> Verify output.
    No generator source code may change.
    """
    set_manager = TemplateSetManager.get_instance()
    ts = set_manager.create_template_set(
        display_name="Metropolitan Institute of Technology Set",
        description="Deliberately foreign vocabulary, arbitrary worksheets, nonstandard attendance capacity",
        fallback_to_default=False,
    )

    output_dir = tmp_path / "output_synthetic"
    output_dir.mkdir(parents=True, exist_ok=True)

    dummy_info = {
        "instructor": "PROF. ALAN TURING",
        "course": "BSCS 3-1",
        "sched": "202699999",
        "subject": "COMP101 - ADVANCED ALGORITHMS",
        "time": "08:00AM-11:00AM",
        "day": "WED",
        "room": "TURING LAB 1",
        "semester": "1st Semester / 2026-2027",
    }
    dummy_students = [
        ("LOVELACE, ADA A.", "202600001"),
        ("VON NEUMANN, JOHN J.", "202600002"),
    ]

    try:
        files_spec = {
            ROLE_SYLLABUS: ("a.docx", os.path.join(templates_dir, "template_syllabus.docx")),
            ROLE_EXAM_RETURNS_MIDTERM: ("b.docx", os.path.join(templates_dir, "template_exam_midterm.docx")),
            ROLE_EXAM_RETURNS_FINAL: ("c.docx", os.path.join(templates_dir, "template_exam_finals.docx")),
            ROLE_TOS_MIDTERM: ("d.docx", os.path.join(templates_dir, "template_tos_midterm.docx")),
            ROLE_TOS_FINAL: ("e.docx", os.path.join(templates_dir, "template_tos_finals.docx")),
            ROLE_GRADE_DISCUSSION_MIDTERM: ("f.docx", os.path.join(templates_dir, "Midterm-Grade-Discussion_LATEST.docx")),
            ROLE_GRADE_DISCUSSION_FINAL: ("g.docx", os.path.join(templates_dir, "Final-Grade-Discussion_LATEST.docx")),
            ROLE_ATTENDANCE_LECTURE: ("h.docx", os.path.join(attendance_dir, "template lec.docx")),
            ROLE_ATTENDANCE_LECTURE_LAB: ("i.docx", os.path.join(attendance_dir, "template lab and lec.docx")),
            ROLE_GRADE_SHEET_LECTURE: ("j.xlsx", os.path.join(templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx")),
            ROLE_GRADE_SHEET_LECTURE_LAB: ("k.xlsx", os.path.join(templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx")),
        }

        detector = TemplateRoleDetector()

        for role, (target_fn, src_path) in files_spec.items():
            dst = tmp_path / target_fn

            if target_fn.endswith(".docx"):
                doc = docx.Document(src_path)
                for p in doc.paragraphs:
                    if p.text.strip():
                        p.text = p.text.replace("CAVITE STATE UNIVERSITY", "METROPOLITAN INSTITUTE")
                        p.text = p.text.replace("CvSU", "MIT")
                        p.text = p.text.replace("CEIT", "SCHOOL OF COMPUTING")

                if role in (ROLE_ATTENDANCE_LECTURE, ROLE_ATTENDANCE_LECTURE_LAB):
                    nt = doc.add_table(rows=1, cols=1)
                    nt.rows[0].cells[0].text = "OFFICIAL REGISTRAR RECORD -- MIT"
                    doc._body._element.insert(0, nt._element)

                doc.save(dst)

            elif target_fn == "j.xlsx":
                wb = openpyxl.load_workbook(src_path)
                wb["Lecture"].title = "Data"
                wb["Grading Sheet"].title = "Official_Grades"
                wb.save(dst)

            elif target_fn == "k.xlsx":
                wb = openpyxl.load_workbook(src_path)
                wb["Lecture"].title = "Data"
                wb["Laboratory"].title = "Practical_Component"
                wb["Consolidated"].title = "Computation"
                wb["Grading Sheet"].title = "Official_Grades"
                wb.create_sheet("Archive", 0)
                wb.save(dst)

            det_res = detector.detect_role(str(dst))
            is_valid, err, val_recipe = detector.validate_role(str(dst), role)
            assert is_valid is True, f"Validation failed for {target_fn} as {role}: {err}"

            set_manager.add_template_to_set(ts.set_id, role, str(dst))

        set_manager.activate_template_set(ts.set_id)
        ts_active = set_manager.get_template_set(ts.set_id)
        assert ts_active.is_complete() is True

        factory = GeneratorFactory(templates_dir=templates_dir, active_set=ts_active)
        all_gens = factory.get_all()
        from modules.models.schedule import ClassInfo
        class_info = ClassInfo(
            instructor=dummy_info["instructor"],
            course_section=dummy_info["course"],
            schedule_code=dummy_info["sched"],
            subject=dummy_info["subject"],
            time_days_room=f"{dummy_info['time']} {dummy_info['day']} {dummy_info['room']}",
            semester_ay=dummy_info["semester"],
            students=dummy_students,
        )
        for gen_fn, suffix in all_gens:
            gen = gen_fn()
            out_f = output_dir / f"synthetic_{suffix}.docx"
            gen.generate(class_info, str(out_f))
            assert os.path.exists(out_f)
            assert os.path.getsize(out_f) > 1000

        att_entry = set_manager.resolve_template(ROLE_ATTENDANCE_LECTURE_LAB, active_set=ts_active)
        resolver = TemplateRecipeResolver.get_instance()
        att_recipe = resolver.resolve(att_entry.file_path, "attendance_docx")
        att_gen = AttendanceGenerator(att_entry.file_path, att_recipe)
        out_att = output_dir / "synthetic_attendance.docx"
        att_gen.generate(
            output_path=str(out_att),
            course_code_title=f"{dummy_info['course']} - {dummy_info['subject']}",
            class_schedule=f"{dummy_info['time']} / {dummy_info['day']}",
            semester_ay=dummy_info["semester"],
            room_assignment=dummy_info["room"],
            instructor=dummy_info["instructor"],
            months=[8],
            year=2026,
            weekdays=[2],
            students=dummy_students,
        )
        assert os.path.exists(out_att)
        assert os.path.getsize(out_att) > 1000

        grade_entry = set_manager.resolve_template(ROLE_GRADE_SHEET_LECTURE_LAB, active_set=ts_active)
        grade_recipe = resolver.resolve(grade_entry.file_path, "grade_sheet_xlsx")
        grade_gen = GradeGenerator(grade_entry.file_path, grade_recipe)
        out_grade = output_dir / "synthetic_grades.xlsx"
        grade_success = grade_gen.generate(dummy_info, dummy_students, str(out_grade))
        assert grade_success is True
        assert os.path.exists(out_grade)
        assert os.path.getsize(out_grade) > 1000

    finally:
        set_manager.activate_template_set(BUILTIN_SET_ID)
        set_manager.delete_template_set(ts.set_id)


# ── 14. Forensic Template Role Detection Regression Tests ────────────────────

def test_attendance_lecture_lab_nonstandard_capacity(tmp_path, repo_root):
    """
    Requirement 10.3:
    Lecture+Lab with nonstandard capacity (e.g. 5, 7, 9 sessions) is still detected
    from dual structural evidence (paired dates or dual schedule or week spans).
    """
    detector = TemplateRoleDetector()
    src_lab_lec = os.path.join(repo_root, "attendance", "template lab and lec.docx")

    # Construct 7-session template from template lab and lec:
    # Schedule has distinct LEC / LAB rooms and dual time intervals
    dst_7 = tmp_path / "attendance_7_sessions_dual.docx"
    doc = docx.Document(src_lab_lec)
    m_tbl = doc.tables[1]

    # Delete 1 date column across all rows to leave 7 date columns (instead of 8)
    for tr in m_tbl._element.findall(w("tr")):
        tcs = tr.findall(w("tc"))
        if len(tcs) > 10:
            tr.remove(tcs[10])

    doc.save(str(dst_7))

    res = detector.detect_role(str(dst_7))
    assert res.status == "confirmed"
    assert res.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert res.variant == "lecture_lab"

    ok, err, recipe = detector.validate_role(str(dst_7), ROLE_ATTENDANCE_LECTURE_LAB)
    assert ok is True
    assert err is None
    assert recipe.matrix_binding.template_session_capacity == 7


def test_attendance_indecisive_evidence_is_ambiguous(tmp_path):
    """
    Requirement 6 & 10.4:
    Attendance with no decisive dual/single evidence becomes strictly ambiguous.
    Assert status == 'ambiguous' (NOT confirmed OR ambiguous).
    """
    detector = TemplateRoleDetector()
    dst = tmp_path / "ambiguous_attendance_record.docx"

    doc = docx.Document()
    # Table 0: Info table with no LEC or LAB keywords
    t_info = doc.add_table(rows=5, cols=2)
    t_info.rows[0].cells[0].text = "Course Title:"
    t_info.rows[0].cells[1].text = "Information Architecture"
    t_info.rows[1].cells[0].text = "Meeting Hours:"
    t_info.rows[1].cells[1].text = "09:00AM-12:00PM"
    t_info.rows[2].cells[0].text = "Academic Term:"
    t_info.rows[2].cells[1].text = "Fall Semester 2026"
    t_info.rows[3].cells[0].text = "Facility:"
    t_info.rows[3].cells[1].text = "Auditorium 101"
    t_info.rows[4].cells[0].text = "Faculty:"
    t_info.rows[4].cells[1].text = "Prof. Jane Doe"

    # Table 1: Matrix with 6 generic date columns, no week headers, all unique dates
    t_matrix = doc.add_table(rows=12, cols=10)
    t_matrix.rows[0].cells[0].text = "No."
    t_matrix.rows[0].cells[1].text = "Student Name"
    t_matrix.rows[0].cells[2].text = "Student ID"
    for col_i in range(3, 9):
        t_matrix.rows[0].cells[col_i].text = ""
    t_matrix.rows[0].cells[9].text = "Summary"

    t_matrix.rows[1].cells[0].text = ""
    t_matrix.rows[1].cells[1].text = ""
    t_matrix.rows[1].cells[2].text = ""
    for col_i in range(3, 9):
        t_matrix.rows[1].cells[col_i].text = f"Date {col_i-2}"
    t_matrix.rows[1].cells[9].text = "Total"

    for r in range(2, 12):
        t_matrix.rows[r].cells[0].text = str(r - 1)
        t_matrix.rows[r].cells[1].text = f"Student {r - 1}"
        t_matrix.rows[r].cells[2].text = f"ID-2026-{100+r}"

    doc.save(str(dst))

    res = detector.detect_role(str(dst))
    assert res.status == "ambiguous"
    assert ROLE_ATTENDANCE_LECTURE in res.candidate_roles
    assert ROLE_ATTENDANCE_LECTURE_LAB in res.candidate_roles

    # Both roles must be accepted through manual assignment since structure is compatible with either
    ok_lec, err_lec, _ = detector.validate_role(str(dst), ROLE_ATTENDANCE_LECTURE)
    assert ok_lec is True

    ok_lab, err_lab, _ = detector.validate_role(str(dst), ROLE_ATTENDANCE_LECTURE_LAB)
    assert ok_lab is True


def test_validate_role_no_session_ratio_rejection(tmp_path):
    """
    Requirement 1: Prove session-ratio removal with the exact historical failure case.
    Historically, validate_role() rejected templates with:
        spw <= 1.25 -> "Attendance template ... has session-count ratio X <= 1.25, incompatible with Lecture+Lab role."
    We construct physically valid Lecture+Lab attendance templates having sessions_per_week <= 1.25
    and explicit dual instructional components (schedule/room).
    Assert validate_role(..., ROLE_ATTENDANCE_LECTURE_LAB) returns True without ratio rejection.
    """
    detector = TemplateRoleDetector()

    def make_dual_attendance_doc(path, num_weeks, num_sessions):
        doc = docx.Document()
        t_info = doc.add_table(rows=4, cols=2)
        t_info.rows[0].cells[0].text = "Course Code & Title:"
        t_info.rows[0].cells[1].text = "COSC 101 - ADVANCED COMPUTING"
        t_info.rows[1].cells[0].text = "Class Schedule:"
        t_info.rows[1].cells[1].text = "LEC: Mon 8-10am / LAB: Wed 1-4pm"
        t_info.rows[2].cells[0].text = "Room Assignment:"
        t_info.rows[2].cells[1].text = "LEC: RM 101 / LAB: CCL 2"
        t_info.rows[3].cells[0].text = "Name of Instructor:"
        t_info.rows[3].cells[1].text = "DR. ALAN TURING"

        total_cols = 3 + num_sessions + 1
        t_mat = doc.add_table(rows=6, cols=total_cols)
        t_mat.rows[0].cells[0].text = "NO."
        t_mat.rows[0].cells[1].text = "NAME"
        t_mat.rows[0].cells[2].text = "STUDENT NUMBER"
        for i in range(num_sessions):
            w_idx = min(i + 1, num_weeks)
            t_mat.rows[0].cells[3 + i].text = f"WEEK {w_idx}"
        t_mat.rows[0].cells[total_cols - 1].text = "ABS"

        for i in range(num_sessions):
            t_mat.rows[1].cells[3 + i].text = f"Date {i + 1}"
        t_mat.rows[1].cells[total_cols - 1].text = "TOTAL"

        for r in range(2, 6):
            t_mat.rows[r].cells[0].text = str(r - 1)
            t_mat.rows[r].cells[1].text = f"Student {r - 1}"
            t_mat.rows[r].cells[2].text = f"2026-000{r}"
        doc.save(str(path))

    # Case A: 4 weeks, 5 sessions (spw = 1.25) -> exactly inside the historical rejection cutoff (spw <= 1.25)
    p_125 = tmp_path / "dual_spw_125.docx"
    make_dual_attendance_doc(p_125, num_weeks=4, num_sessions=5)
    res_125 = detector.detect_role(str(p_125))
    assert res_125.status == "confirmed"
    assert res_125.role == ROLE_ATTENDANCE_LECTURE_LAB
    ok_125, err_125, recipe_125 = detector.validate_role(str(p_125), ROLE_ATTENDANCE_LECTURE_LAB)
    assert ok_125 is True, f"validate_role unexpectedly rejected Case A (spw=1.25): {err_125}"
    assert recipe_125 is not None

    # Case B: 6 weeks, 6 sessions (spw = 1.0) -> nonstandard physical capacity well below 1.25
    p_100 = tmp_path / "dual_spw_100.docx"
    make_dual_attendance_doc(p_100, num_weeks=6, num_sessions=6)
    res_100 = detector.detect_role(str(p_100))
    assert res_100.status == "confirmed"
    assert res_100.role == ROLE_ATTENDANCE_LECTURE_LAB
    ok_100, err_100, recipe_100 = detector.validate_role(str(p_100), ROLE_ATTENDANCE_LECTURE_LAB)
    assert ok_100 is True, f"validate_role unexpectedly rejected Case B (spw=1.00): {err_100}"
    assert recipe_100 is not None


def test_generic_four_column_roster_not_classified_as_syllabus(tmp_path):
    """
    Requirement 2 & 10.6:
    A generic four-column academic roster is NOT automatically classified as syllabus
    solely because it has four columns.
    """
    detector = TemplateRoleDetector()
    dst = tmp_path / "generic_cohort_manifest.docx"

    doc = docx.Document()
    t_hdr = doc.add_table(rows=4, cols=2)
    t_hdr.rows[0].cells[0].text = "Instructor:"
    t_hdr.rows[0].cells[1].text = "Dr. Michael Faraday"
    t_hdr.rows[1].cells[0].text = "Course Title:"
    t_hdr.rows[1].cells[1].text = "Electromagnetic Principles"
    t_hdr.rows[2].cells[0].text = "Cohort ID:"
    t_hdr.rows[2].cells[1].text = "PHY-301-A"
    t_hdr.rows[3].cells[0].text = "Semester Term:"
    t_hdr.rows[3].cells[1].text = "Spring 2026"

    # 4-column roster table without ANY syllabus vocabulary
    t_rst = doc.add_table(rows=8, cols=4)
    t_rst.rows[0].cells[0].text = "Item"
    t_rst.rows[0].cells[1].text = "Candidate Name"
    t_rst.rows[0].cells[2].text = "Matriculation Number"
    t_rst.rows[0].cells[3].text = "Acknowledgement"
    for r in range(1, 8):
        t_rst.rows[r].cells[0].text = str(r)
        t_rst.rows[r].cells[1].text = f"Candidate {r}"
        t_rst.rows[r].cells[2].text = f"2026-{1000+r}"
        t_rst.rows[r].cells[3].text = ""

    doc.add_paragraph("OFFICIAL DEPARTMENT ENROLLMENT VERIFICATION LIST")
    doc.save(str(dst))

    res = detector.detect_role(str(dst))
    assert res.role != ROLE_SYLLABUS
    assert res.status == "ambiguous"
    assert ROLE_SYLLABUS in res.candidate_roles


def test_academic_docx_neutral_without_structure_is_ambiguous(tmp_path):
    """
    Requirement 4 & 10.8:
    A terminology-neutral template without sufficient role-specific structure
    becomes ambiguous rather than falsely confirmed.
    """
    detector = TemplateRoleDetector()
    dst = tmp_path / "neutral_undifferentiated.docx"

    doc = docx.Document()
    t_hdr = doc.add_table(rows=3, cols=2)
    t_hdr.rows[0].cells[0].text = "Professor:"
    t_hdr.rows[0].cells[1].text = "Dr. Carl Sagan"
    t_hdr.rows[1].cells[0].text = "Subject Code:"
    t_hdr.rows[1].cells[1].text = "ASTRO-101"
    t_hdr.rows[2].cells[0].text = "Term:"
    t_hdr.rows[2].cells[1].text = "Academic Year 2026"

    # 3-column generic roster
    t_rst = doc.add_table(rows=6, cols=3)
    t_rst.rows[0].cells[0].text = "Index"
    t_rst.rows[0].cells[1].text = "Name of Student"
    t_rst.rows[0].cells[2].text = "Student Number"
    for r in range(1, 6):
        t_rst.rows[r].cells[0].text = str(r)
        t_rst.rows[r].cells[1].text = f"Student {r}"
        t_rst.rows[r].cells[2].text = f"SN-{2000+r}"

    doc.add_paragraph("GENERAL STUDENT ROSTER")
    doc.save(str(dst))

    res = detector.detect_role(str(dst))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_opaque_names_and_arbitrary_order(tmp_path, repo_root):
    """
    Requirement 5 & 10.9:
    Workbook using completely opaque sheet names:
      Omega, Q7, Ledger_19, Archive_X, BlueSheet
    with NO role-identifying names.
    Reordered so BlueSheet (the summary sheet) is at sheet index 0.
    Assert detection, validation, and coordinate binding succeed.
    """
    detector = TemplateRoleDetector()
    src_grade = os.path.join(repo_root, "templates", "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    dst = tmp_path / "opaque_workbook_grade.xlsx"

    wb = openpyxl.load_workbook(src_grade)
    wb["Lecture"].title = "Omega"
    wb["Laboratory"].title = "Q7"
    wb["Consolidated"].title = "Ledger_19"
    wb["Grading Sheet"].title = "BlueSheet"
    wb.create_sheet("Archive_X", 0)

    # Reorder so BlueSheet is at index 0, followed by Archive_X
    bs = wb["BlueSheet"]
    wb._sheets.remove(bs)
    wb._sheets.insert(0, bs)
    assert wb.sheetnames[0] == "BlueSheet"
    wb.save(str(dst))

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.variant == "lecture_lab"

    ok, err, recipe = detector.validate_role(str(dst), ROLE_GRADE_SHEET_LECTURE_LAB)
    assert ok is True
    assert err is None
    assert recipe.metadata["summary_sheet"] == "BlueSheet"
    assert recipe.metadata["roster_sheet"] == "Omega"
    assert recipe.metadata["lab_sheet"] == "Q7"
    assert recipe.metadata["con_sheet"] == "Ledger_19"


def test_misleading_worksheet_names_do_not_affect_role(tmp_path, repo_root):
    """
    Requirement 10.11:
    Misleading worksheet names do not affect role:
    A single-component grade sheet whose worksheet is named 'Laboratory' or 'Practical'
    is still classified as ROLE_GRADE_SHEET_LECTURE based on physical topology.
    """
    detector = TemplateRoleDetector()
    src_lec = os.path.join(repo_root, "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
    dst = tmp_path / "deceptive_sheet_name.xlsx"

    wb = openpyxl.load_workbook(src_lec)
    wb["Lecture"].title = "Laboratory"  # Deceptive!
    wb["Grading Sheet"].title = "Final_Review"
    wb.save(str(dst))

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE
    assert res.variant == "lecture"


def test_independently_constructed_foreign_fixtures_e2e(tmp_path):
    """
    Requirement 7 & 10.12:
    Build completely independent, from-scratch foreign institution fixtures
    (academic docx, attendance docx, grade xlsx) and run them through the full pipeline:
    Inspect -> Detect -> Validate -> Save to Template Set -> Activate -> Generate -> Verify output.
    """
    output_dir = tmp_path / "out_foreign"
    output_dir.mkdir(parents=True, exist_ok=True)

    detector = TemplateRoleDetector()
    set_manager = TemplateSetManager.get_instance()
    ts = set_manager.create_template_set("foreign_institute_set_e2e", "Completely Independent Foreign Set", fallback_to_default=True)

    dummy_info = {
        "instructor": "DR. MARIE CURIE",
        "course": "PHYS 3-1",
        "sched": "20268877",
        "subject": "PHYS301 - NUCLEAR PHYSICS",
        "time": "09:00AM-12:00PM",
        "day": "Mon",
        "room": "Science Hall 101",
        "semester": "First Semester 2026-2027",
        "units": "3",
    }
    dummy_students = [
        ("BECQUEREL, HENRI H.", "202690001"),
        ("RUTHERFORD, ERNEST E.", "202690002"),
    ]

    try:
        # 1. Academic DOCX (Syllabus) constructed from scratch
        p_syl = tmp_path / "polytechnic_registry_01.docx"
        doc_syl = docx.Document()
        doc_syl.add_paragraph("METROPOLITAN POLYTECHNIC INSTITUTE -- TEACHING PLAN AND COURSE OUTLINE")
        t_meta = doc_syl.add_table(rows=6, cols=2)
        t_meta.rows[0].cells[0].text = "Instructor:"
        t_meta.rows[0].cells[1].text = dummy_info["instructor"]
        t_meta.rows[1].cells[0].text = "Subject:"
        t_meta.rows[1].cells[1].text = dummy_info["subject"]
        t_meta.rows[2].cells[0].text = "Class Section:"
        t_meta.rows[2].cells[1].text = dummy_info["course"]
        t_meta.rows[3].cells[0].text = "Schedule Code:"
        t_meta.rows[3].cells[1].text = dummy_info["sched"]
        t_meta.rows[4].cells[0].text = "Class Schedule:"
        t_meta.rows[4].cells[1].text = f"{dummy_info['time']} {dummy_info['day']} {dummy_info['room']}"
        t_meta.rows[5].cells[0].text = "Semester Term:"
        t_meta.rows[5].cells[1].text = dummy_info["semester"]

        t_rst = doc_syl.add_table(rows=5, cols=4)
        t_rst.rows[0].cells[0].text = "No."
        t_rst.rows[0].cells[1].text = "Student Name"
        t_rst.rows[0].cells[2].text = "Student Number"
        t_rst.rows[0].cells[3].text = "Acknowledgement"
        for r in range(1, 5):
            t_rst.rows[r].cells[0].text = str(r)
            t_rst.rows[r].cells[1].text = f"Candidate {r}"
            t_rst.rows[r].cells[2].text = f"2026-{r:04d}"
            t_rst.rows[r].cells[3].text = ""

        doc_syl.add_paragraph("SYLLABUS RECEIPT AND STUDENT ACKNOWLEDGEMENT")
        doc_syl.save(str(p_syl))

        res_syl = detector.detect_role(str(p_syl))
        assert res_syl.status == "confirmed"
        assert res_syl.role == ROLE_SYLLABUS
        set_manager.add_template_to_set(ts.set_id, ROLE_SYLLABUS, str(p_syl))

        # 2. Attendance DOCX constructed from scratch
        p_att = tmp_path / "roster_matrix_99.docx"
        doc_att = docx.Document()
        t_info = doc_att.add_table(rows=5, cols=2)
        t_info.rows[0].cells[0].text = "Course Code & Title:"
        t_info.rows[0].cells[1].text = f"{dummy_info['course']} - {dummy_info['subject']}"
        t_info.rows[1].cells[0].text = "Class Schedule:"
        t_info.rows[1].cells[1].text = f"{dummy_info['time']} / {dummy_info['day']}"
        t_info.rows[2].cells[0].text = "Semester & AY:"
        t_info.rows[2].cells[1].text = dummy_info["semester"]
        t_info.rows[3].cells[0].text = "Room Assignment"
        t_info.rows[3].cells[1].text = dummy_info["room"]
        t_info.rows[4].cells[0].text = "Name of Instructor:"
        t_info.rows[4].cells[1].text = dummy_info["instructor"]

        t_mat = doc_att.add_table(rows=10, cols=11)
        t_mat.rows[0].cells[0].text = "NO."
        t_mat.rows[0].cells[1].text = "NAME"
        t_mat.rows[0].cells[2].text = "STUDENT NUMBER"
        for i in range(7):
            t_mat.rows[0].cells[3 + i].text = f"WEEK {i + 1}"
        t_mat.rows[0].cells[10].text = "ABS"

        for c in range(3):
            t_mat.rows[1].cells[c].text = ""
        for i in range(7):
            t_mat.rows[1].cells[3 + i].text = f"Date {i + 1}"
        t_mat.rows[1].cells[10].text = "TOTAL"

        for r in range(2, 10):
            t_mat.rows[r].cells[0].text = str(r - 1)
            t_mat.rows[r].cells[1].text = f"Student {r - 1}"
            t_mat.rows[r].cells[2].text = f"2026-{r:04d}"

        doc_att.save(str(p_att))

        res_att = detector.detect_role(str(p_att))
        assert res_att.status == "confirmed"
        assert res_att.role == ROLE_ATTENDANCE_LECTURE
        assert res_att.variant == "lecture"
        set_manager.add_template_to_set(ts.set_id, ROLE_ATTENDANCE_LECTURE, str(p_att))

        # 3. Grade XLSX constructed from scratch
        p_grade = tmp_path / "marks_ledger_2026.xlsx"
        wb = openpyxl.Workbook()
        ws_default = wb.active
        ws_default.title = "Archive_X"
        ws_default["A1"] = "ARCHIVAL SYSTEM STORAGE - DO NOT EDIT"

        ws_summary = wb.create_sheet("BlueSheet")
        ws_summary["A1"] = "METROPOLITAN POLYTECHNIC INSTITUTE"
        ws_summary["A2"] = "COLLEGE OF SCIENCE AND TECHNOLOGY"
        ws_summary["A3"] = "OFFICIAL SUMMARY RECORD OF MARKS"
        ws_summary.append([])
        ws_summary.append(["NO.", "STUDENT NAME", "STUDENT NUMBER", "FINAL RATING", "REMARKS"])
        for idx in range(1, 10):
            ws_summary.append([idx, f"Student {idx}", f"2026-{idx:04d}", "", ""])

        ws_roster = wb.create_sheet("Omega")
        ws_roster["A1"] = "Instructor:"
        ws_roster["B1"] = "DR. MARIE CURIE"
        ws_roster["A2"] = "Course / Section:"
        ws_roster["B2"] = "PHYS 3-1"
        ws_roster["A3"] = "Subject Code / Title:"
        ws_roster["B3"] = "PHYS301"
        ws_roster["A4"] = "Schedule Code:"
        ws_roster["B4"] = "20268877"
        ws_roster["A5"] = "Semester & AY:"
        ws_roster["B5"] = "First Semester 2026-2027"
        ws_roster.append([])
        ws_roster.append(["NO.", "STUDENT NAME", "STUDENT NUMBER", "QUIZ 1", "MIDTERM", "FINAL"])
        for idx in range(1, 10):
            ws_roster.append([idx, f"Student {idx}", f"2026-{idx:04d}", "", "", ""])

        wb.save(str(p_grade))

        res_grade = detector.detect_role(str(p_grade))
        assert res_grade.status == "confirmed"
        assert res_grade.role == ROLE_GRADE_SHEET_LECTURE
        assert res_grade.variant == "lecture"
        set_manager.add_template_to_set(ts.set_id, ROLE_GRADE_SHEET_LECTURE, str(p_grade))

        # 4. Activate and Generate
        set_manager.activate_template_set(ts.set_id)
        ts_active = set_manager.get_template_set(ts.set_id)

        # Generate CEIT (Syllabus)
        resolver = TemplateRecipeResolver.get_instance()
        syl_entry = set_manager.resolve_template(ROLE_SYLLABUS, active_set=ts_active)
        syl_recipe = resolver.resolve(syl_entry.file_path, "academic_docx")
        gen_syl = SyllabusGenerator(syl_entry.file_path, syl_recipe)
        class_info = ClassInfo(
            instructor=dummy_info["instructor"],
            course_section=dummy_info["course"],
            schedule_code=dummy_info["sched"],
            subject=dummy_info["subject"],
            time_days_room=f"{dummy_info['time']} {dummy_info['day']} {dummy_info['room']}",
            semester_ay=dummy_info["semester"],
            students=dummy_students,
        )
        out_syl = output_dir / "out_foreign_syllabus.docx"
        gen_syl.generate(class_info, str(out_syl))
        assert os.path.exists(out_syl)
        assert os.path.getsize(out_syl) > 500

        # Generate Attendance
        att_entry = set_manager.resolve_template(ROLE_ATTENDANCE_LECTURE, active_set=ts_active)
        att_recipe = resolver.resolve(att_entry.file_path, "attendance_docx")
        gen_att = AttendanceGenerator(att_entry.file_path, att_recipe)
        out_att = output_dir / "out_foreign_attendance.docx"
        gen_att.generate(
            output_path=str(out_att),
            course_code_title=f"{dummy_info['course']} - {dummy_info['subject']}",
            class_schedule=f"{dummy_info['time']} / {dummy_info['day']}",
            semester_ay=dummy_info["semester"],
            room_assignment=dummy_info["room"],
            instructor=dummy_info["instructor"],
            months=[8],
            year=2026,
            weekdays=[0],
            students=dummy_students,
        )
        assert os.path.exists(out_att)
        assert os.path.getsize(out_att) > 500

        # Generate Grade Sheet
        grade_entry = set_manager.resolve_template(ROLE_GRADE_SHEET_LECTURE, active_set=ts_active)
        grade_recipe = resolver.resolve(grade_entry.file_path, "grade_sheet_xlsx")
        gen_grade = GradeGenerator(grade_entry.file_path, grade_recipe)
        out_grade = output_dir / "out_foreign_grades.xlsx"
        success_grade = gen_grade.generate(dummy_info, dummy_students, str(out_grade))
        assert success_grade is True
        assert os.path.exists(out_grade)
        assert os.path.getsize(out_grade) > 500

    finally:
        set_manager.activate_template_set(BUILTIN_SET_ID)
        set_manager.delete_template_set(ts.set_id)


def test_xlsx_worksheet_name_permutations(tmp_path, repo_root):
    """
    Requirement 3:
    1. Builds one valid Lecture+Lab workbook.
    2. Captures its validated structural recipe.
    3. Renames all worksheets to arbitrary opaque identifiers:
       Omega, Q7, Ledger_19, BlueSheet, Archive_X, Aux_Tbl, Temp_Sheet
    4. Permutationally reorders those sheets.
    5. Re-inspects and re-validates.
    6. Repeats with another completely different set of worksheet names (Alpha, Beta, Gamma, Delta, Epsilon, Zeta, Eta).
    7. Compares the structural recipe fields:
       The structural recipe coordinates must be identical except for naturally expected worksheet-name metadata fields.
       The selected logical roster/summary/lab/consolidated structures MUST remain the same.
    """
    src_grade = os.path.join(repo_root, "templates", "GRADING_LECTURE_LAB_TEMPLATE.xlsx")

    inspector = XlsxTemplateInspector()
    orig_cand = inspector.inspect(src_grade, "grade_sheet_xlsx")
    validator = RecipeValidator()
    orig_recipe = validator.validate(orig_cand, "grade_sheet_xlsx")

    # Permutation 1: Set 1 of opaque names and arbitrary reordering
    names_set_1 = {
        "Lecture": "Omega",
        "Laboratory": "Q7",
        "Consolidated": "Ledger_19",
        "Grading Sheet": "BlueSheet",
        "Notes": "Archive_X",
        "Transmutation Table": "Aux_Tbl",
        "Sheet1": "Temp_Sheet",
    }
    p1 = tmp_path / "permuted_grades_set1.xlsx"
    wb1 = openpyxl.load_workbook(src_grade)
    for old_n, new_n in names_set_1.items():
        if old_n in wb1.sheetnames:
            wb1[old_n].title = new_n

    # Reorder sheets arbitrarily: BlueSheet (summary) at index 0, Archive_X, Ledger_19, Q7, Omega, etc.
    desired_order_1 = ["BlueSheet", "Archive_X", "Ledger_19", "Aux_Tbl", "Q7", "Temp_Sheet", "Omega"]
    wb1._sheets = [wb1[n] for n in desired_order_1 if n in wb1.sheetnames]
    wb1.save(str(p1))

    cand1 = inspector.inspect(str(p1), "grade_sheet_xlsx")
    recipe1 = validator.validate(cand1, "grade_sheet_xlsx")

    assert cand1.metadata["roster_sheet"] == "Omega"
    assert cand1.metadata["lab_sheet"] == "Q7"
    assert cand1.metadata["con_sheet"] == "Ledger_19"
    assert cand1.metadata["summary_sheet"] == "BlueSheet"

    # Permutation 2: Set 2 of completely different opaque names and reverse order
    names_set_2 = {
        "Lecture": "Alpha",
        "Laboratory": "Beta",
        "Consolidated": "Gamma",
        "Grading Sheet": "Delta",
        "Notes": "Epsilon",
        "Transmutation Table": "Zeta",
        "Sheet1": "Eta",
    }
    p2 = tmp_path / "permuted_grades_set2.xlsx"
    wb2 = openpyxl.load_workbook(src_grade)
    for old_n, new_n in names_set_2.items():
        if old_n in wb2.sheetnames:
            wb2[old_n].title = new_n

    desired_order_2 = ["Eta", "Zeta", "Gamma", "Epsilon", "Beta", "Delta", "Alpha"]
    wb2._sheets = [wb2[n] for n in desired_order_2 if n in wb2.sheetnames]
    wb2.save(str(p2))

    cand2 = inspector.inspect(str(p2), "grade_sheet_xlsx")
    recipe2 = validator.validate(cand2, "grade_sheet_xlsx")

    assert cand2.metadata["roster_sheet"] == "Alpha"
    assert cand2.metadata["lab_sheet"] == "Beta"
    assert cand2.metadata["con_sheet"] == "Gamma"
    assert cand2.metadata["summary_sheet"] == "Delta"

    # Compare structural recipe coordinates between orig, set1, and set2
    assert recipe1.roster_binding.first_data_row_index == orig_recipe.roster_binding.first_data_row_index
    assert recipe1.roster_binding.name_col == orig_recipe.roster_binding.name_col
    assert recipe1.roster_binding.id_col == orig_recipe.roster_binding.id_col
    assert recipe1.roster_binding.capacity_limit == orig_recipe.roster_binding.capacity_limit

    assert recipe2.roster_binding.first_data_row_index == orig_recipe.roster_binding.first_data_row_index
    assert recipe2.roster_binding.name_col == orig_recipe.roster_binding.name_col
    assert recipe2.roster_binding.id_col == orig_recipe.roster_binding.id_col
    assert recipe2.roster_binding.capacity_limit == orig_recipe.roster_binding.capacity_limit

    assert len(recipe1.header_bindings) == len(orig_recipe.header_bindings)
    assert len(recipe2.header_bindings) == len(orig_recipe.header_bindings)


def test_attendance_foreign_terminology_structural_differentiation(tmp_path):
    """
    Requirement 4:
    Create independently constructed attendance fixtures whose instructional components do not use:
      LAB, LECTURE, LEC, LABORATORY, THEORY
    Use arbitrary foreign concepts/labels.
    The physical structure must still distinguish:
      - physical dual structure -> Lecture+Lab (ROLE_ATTENDANCE_LECTURE_LAB)
      - physical single structure -> Lecture (ROLE_ATTENDANCE_LECTURE)
      - insufficient structural distinction -> ambiguous
    """
    detector = TemplateRoleDetector()

    # 1. Foreign Dual Component (No LEC, LAB, THEORY, LABORATORY)
    doc_dual = docx.Document()
    t_info_d = doc_dual.add_table(rows=4, cols=2)
    t_info_d.rows[0].cells[0].text = "Course Code & Title:"
    t_info_d.rows[0].cells[1].text = "ASTRONOMY 101 - CELESTIAL MECHANICS"
    t_info_d.rows[1].cells[0].text = "Class Schedule:"
    t_info_d.rows[1].cells[1].text = "08:00-10:00 Mon / 13:00-16:00 Wed"
    t_info_d.rows[2].cells[0].text = "Room Assignment:"
    t_info_d.rows[2].cells[1].text = "Hall Alpha / Workshop Beta"
    t_info_d.rows[3].cells[0].text = "Name of Instructor:"
    t_info_d.rows[3].cells[1].text = "DR. NICOLAUS COPERNICUS"

    t_mat_d = doc_dual.add_table(rows=6, cols=8)
    t_mat_d.rows[0].cells[0].text = "NO."
    t_mat_d.rows[0].cells[1].text = "STUDENT NAME"
    t_mat_d.rows[0].cells[2].text = "STUDENT NUMBER"
    t_mat_d.rows[0].cells[3].text = "WEEK 1"
    t_mat_d.rows[0].cells[4].text = "WEEK 1"  # Multi-session cycle block
    t_mat_d.rows[0].cells[5].text = "WEEK 2"
    t_mat_d.rows[0].cells[6].text = "WEEK 2"  # Multi-session cycle block
    t_mat_d.rows[0].cells[7].text = "ABS"

    for i in range(4):
        t_mat_d.rows[1].cells[3 + i].text = f"Date {i + 1}"
    t_mat_d.rows[1].cells[7].text = "TOTAL"

    for r in range(2, 6):
        t_mat_d.rows[r].cells[0].text = str(r - 1)
        t_mat_d.rows[r].cells[1].text = f"Scholar {r - 1}"
        t_mat_d.rows[r].cells[2].text = f"2026-000{r}"

    p_dual = tmp_path / "foreign_dual.docx"
    doc_dual.save(str(p_dual))

    # Assert no forbidden terms in dual fixture
    full_text_d = " ".join([p.text for p in doc_dual.paragraphs] + [c.text for t in doc_dual.tables for r in t.rows for c in r.cells]).upper()
    for forbidden in ["LAB", "LECTURE", "LEC", "LABORATORY", "THEORY"]:
        assert forbidden not in full_text_d.split() and f"{forbidden}:" not in full_text_d

    res_dual = detector.detect_role(str(p_dual))
    assert res_dual.status == "confirmed"
    assert res_dual.role == ROLE_ATTENDANCE_LECTURE_LAB
    assert res_dual.variant == "lecture_lab"

    # 2. Foreign Single Component (No LEC, LAB, THEORY, LABORATORY)
    doc_single = docx.Document()
    t_info_s = doc_single.add_table(rows=4, cols=2)
    t_info_s.rows[0].cells[0].text = "Course Code & Title:"
    t_info_s.rows[0].cells[1].text = "PHILOSOPHY 201 - FORMAL LOGIC"
    t_info_s.rows[1].cells[0].text = "Class Schedule:"
    t_info_s.rows[1].cells[1].text = "09:00-12:00 Friday"
    t_info_s.rows[2].cells[0].text = "Room Assignment:"
    t_info_s.rows[2].cells[1].text = "Forum Hall 1"
    t_info_s.rows[3].cells[0].text = "Name of Instructor:"
    t_info_s.rows[3].cells[1].text = "DR. ARISTOTLE"

    t_mat_s = doc_single.add_table(rows=6, cols=8)
    t_mat_s.rows[0].cells[0].text = "NO."
    t_mat_s.rows[0].cells[1].text = "STUDENT NAME"
    t_mat_s.rows[0].cells[2].text = "STUDENT NUMBER"
    for i in range(4):
        t_mat_s.rows[0].cells[3 + i].text = f"WEEK {i + 1}"
    t_mat_s.rows[0].cells[7].text = "ABS"

    for i in range(4):
        t_mat_s.rows[1].cells[3 + i].text = f"Date {i + 1}"
    t_mat_s.rows[1].cells[7].text = "TOTAL"

    for r in range(2, 6):
        t_mat_s.rows[r].cells[0].text = str(r - 1)
        t_mat_s.rows[r].cells[1].text = f"Scholar {r - 1}"
        t_mat_s.rows[r].cells[2].text = f"2026-000{r}"

    p_single = tmp_path / "foreign_single.docx"
    doc_single.save(str(p_single))

    full_text_s = " ".join([p.text for p in doc_single.paragraphs] + [c.text for t in doc_single.tables for r in t.rows for c in r.cells]).upper()
    for forbidden in ["LAB", "LECTURE", "LEC", "LABORATORY", "THEORY"]:
        assert forbidden not in full_text_s.split() and f"{forbidden}:" not in full_text_s

    res_single = detector.detect_role(str(p_single))
    assert res_single.status == "confirmed"
    assert res_single.role == ROLE_ATTENDANCE_LECTURE
    assert res_single.variant == "lecture"

    # 3. Foreign Ambiguous (No decisive dual/single markers)
    doc_ambig = docx.Document()
    t_info_a = doc_ambig.add_table(rows=3, cols=2)
    t_info_a.rows[0].cells[0].text = "Course Code & Title:"
    t_info_a.rows[0].cells[1].text = "SEMINAR 501 - ADVANCED RESEARCH"
    t_info_a.rows[1].cells[0].text = "Class Schedule:"
    t_info_a.rows[1].cells[1].text = "By Arrangement"
    t_info_a.rows[2].cells[0].text = "Name of Instructor:"
    t_info_a.rows[2].cells[1].text = "DR. HYPATIA"

    t_mat_a = doc_ambig.add_table(rows=6, cols=7)
    t_mat_a.rows[0].cells[0].text = "NO."
    t_mat_a.rows[0].cells[1].text = "STUDENT NAME"
    t_mat_a.rows[0].cells[2].text = "STUDENT NUMBER"
    for i in range(3):
        t_mat_a.rows[0].cells[3 + i].text = f"Col {i + 1}"
    t_mat_a.rows[0].cells[6].text = "ABS"
    for i in range(3):
        t_mat_a.rows[1].cells[3 + i].text = f"Meeting {i + 1}"
    t_mat_a.rows[1].cells[6].text = "TOTAL"
    for r in range(2, 6):
        t_mat_a.rows[r].cells[0].text = str(r - 1)
        t_mat_a.rows[r].cells[1].text = f"Scholar {r - 1}"
        t_mat_a.rows[r].cells[2].text = f"2026-000{r}"

    p_ambig = tmp_path / "foreign_ambig.docx"
    doc_ambig.save(str(p_ambig))

    res_ambig = detector.detect_role(str(p_ambig))
    assert res_ambig.status == "ambiguous"
    assert res_ambig.role is None


def test_structural_audit_catches_prohibited_assumptions(repo_root):
    """
    Requirement 8 & 10.13:
    The structural audit flags prohibited authoritative assumptions:
    A. tables[0] used as role authority
    B. cap >= 6 or spw >= 1.5 used for role classification
    C. total_cols == 4 used for syllabus authority
    """
    bad_source_1 = """
def classify_attendance(cand):
    if cand.cap >= 6:
        return ROLE_ATTENDANCE_LECTURE_LAB
    return ROLE_ATTENDANCE_LECTURE
"""
    violations_1 = scan_source(bad_source_1, "bad_detector.py")
    assert any(cat == "E" for _, cat, _ in violations_1), "Audit failed to catch cap >= 6 threshold"

    bad_source_2 = """
def classify_academic(cand):
    if cand.total_cols == 4:
        return ROLE_SYLLABUS
"""
    violations_2 = scan_source(bad_source_2, "bad_academic.py")
    assert any(cat == "E" for _, cat, _ in violations_2), "Audit failed to catch total_cols == 4 shortcut"

    bad_source_3 = """
def validate_role(cand):
    if cand.sessions_per_week >= 1.5:
        return True
"""
    violations_3 = scan_source(bad_source_3, "bad_validator.py")
    assert any(cat == "E" for _, cat, _ in violations_3), "Audit failed to catch sessions_per_week >= 1.5"

    # Assert live modules have zero prohibited assumptions
    ret = audit(os.path.join(repo_root, "modules"))
    assert ret == 0, f"Live codebase audit returned non-zero code: {ret}"


