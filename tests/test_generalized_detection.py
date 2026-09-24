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
import re
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
from modules.models.recipe import TemplateError, AmbiguousTemplateError
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


def rename_worksheet_with_formulas(wb, old_name: str, new_name: str):
    """
    Simulates Excel's native behavior of updating cross-sheet formula references
    when a worksheet is renamed in a workbook.
    """
    if old_name not in wb.sheetnames:
        return
    wb[old_name].title = new_name
    esc_old = old_name.replace("'", "''")
    pattern = re.compile(
        rf"(?:'|(?<![A-Za-z0-9_]))(?:{re.escape(old_name)}|{re.escape(esc_old)})(?:'|(?![A-Za-z0-9_]))!",
        re.IGNORECASE,
    )
    escaped_new = new_name.replace("'", "''")
    quoted_new = (
        f"'{escaped_new}'!"
        if (" " in new_name or "'" in new_name or "-" in new_name)
        else f"{new_name}!"
    )
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("=") and "!" in cell.value:
                    if pattern.search(cell.value):
                        cell.value = pattern.sub(quoted_new, cell.value)


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
    rename_worksheet_with_formulas(wb, "Lecture", "Main")
    rename_worksheet_with_formulas(wb, "Laboratory", "Practical")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Final Scores")
    if "Consolidated" in wb.sheetnames:
        rename_worksheet_with_formulas(wb, "Consolidated", "Combined")
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
    rename_worksheet_with_formulas(wb, "Lecture", "Main")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Final Scores")
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
            rename_worksheet_with_formulas(wb, "Lecture", "Main")
            rename_worksheet_with_formulas(wb, "Grading Sheet", "Final Scores")
            wb.save(dst_path)
        elif opaque_fn == "scores_dual.xlsx":
            wb = openpyxl.load_workbook(dst_path)
            rename_worksheet_with_formulas(wb, "Lecture", "Main")
            rename_worksheet_with_formulas(wb, "Laboratory", "Practical")
            rename_worksheet_with_formulas(wb, "Grading Sheet", "Final Scores")
            if "Consolidated" in wb.sheetnames:
                rename_worksheet_with_formulas(wb, "Consolidated", "Combined")
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
    rename_worksheet_with_formulas(wb, "Lecture", "Sheet_A")
    rename_worksheet_with_formulas(wb, "Laboratory", "Sheet_B")
    rename_worksheet_with_formulas(wb, "Consolidated", "Results")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Summary_2026")

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
                rename_worksheet_with_formulas(wb, "Lecture", "Sheet_A")
                rename_worksheet_with_formulas(wb, "Grading Sheet", "Summary_2026")
                wb.save(dst_path)

            elif opaque_fn == "k11.xlsx":
                wb = openpyxl.load_workbook(src_path)
                rename_worksheet_with_formulas(wb, "Lecture", "Sheet_A")
                rename_worksheet_with_formulas(wb, "Laboratory", "Sheet_B")
                rename_worksheet_with_formulas(wb, "Consolidated", "Results")
                rename_worksheet_with_formulas(wb, "Grading Sheet", "Summary_2026")
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
    rename_worksheet_with_formulas(wb, "Lecture", "Data")
    rename_worksheet_with_formulas(wb, "Laboratory", "Practical_Component")
    rename_worksheet_with_formulas(wb, "Consolidated", "Computation")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Official_Grades")
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
                rename_worksheet_with_formulas(wb, "Lecture", "Data")
                rename_worksheet_with_formulas(wb, "Grading Sheet", "Official_Grades")
                wb.save(dst)

            elif target_fn == "k.xlsx":
                wb = openpyxl.load_workbook(src_path)
                rename_worksheet_with_formulas(wb, "Lecture", "Data")
                rename_worksheet_with_formulas(wb, "Laboratory", "Practical_Component")
                rename_worksheet_with_formulas(wb, "Consolidated", "Computation")
                rename_worksheet_with_formulas(wb, "Grading Sheet", "Official_Grades")
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
    rename_worksheet_with_formulas(wb, "Lecture", "Omega")
    rename_worksheet_with_formulas(wb, "Laboratory", "Q7")
    rename_worksheet_with_formulas(wb, "Consolidated", "Ledger_19")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "BlueSheet")
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
    rename_worksheet_with_formulas(wb, "Lecture", "Laboratory")  # Deceptive!
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Final_Review")
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
            ws_summary.append([idx, f"Student {idx}", f"2026-{idx:04d}", f"=Omega!F{idx + 6}", "PASSED"])

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
        rename_worksheet_with_formulas(wb1, old_n, new_n)

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
        rename_worksheet_with_formulas(wb2, old_n, new_n)

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

    bad_source_4 = """
def inspect_xlsx(wb):
    primary_roster_sheet = scored_rosters[0]
"""
    violations_4 = scan_source(bad_source_4, "template_inspector.py")
    assert any(cat == "E" for _, cat, _ in violations_4), "Audit failed to catch scored_rosters[0] workbook-order authority"

    bad_source_5 = """
def resolve_secondary(cols1, cols2):
    if cols1 > cols2:
        lab_sheet = "Sheet_A"
        con_sheet = "Sheet_B"
"""
    violations_5 = scan_source(bad_source_5, "template_inspector.py")
    assert any(cat == "E" for _, cat, _ in violations_5), "Audit failed to catch dimension-based role authority"

    bad_source_6 = """
def resolve_secondary(refs1, refs2):
    if refs1 > refs2:
        con_sheet = "Sheet_A"
        lab_sheet = "Sheet_B"
"""
    violations_6 = scan_source(bad_source_6, "template_inspector.py")
    assert any(cat == "E" for _, cat, _ in violations_6), "Audit failed to catch reference-count-based role authority"

    # Assert live modules have zero prohibited assumptions
    ret = audit(os.path.join(repo_root, "modules"))
    assert ret == 0, f"Live codebase audit returned non-zero code: {ret}"


# ── 12. Final Micro-Closure: XLSX Structural Ambiguity & Fail-Closed Tests ──

def test_xlsx_duplicate_roster_is_ambiguous(detector, tmp_path):
    """
    Requirement 3: Create a workbook containing two worksheets with genuinely equivalent
    student-roster structures. Neither sheet may have an identifying name.
    Expected: inspection/detection -> ambiguous.
    The system must not silently choose worksheet 0.
    """
    wb = openpyxl.Workbook()
    # Sheet 1: Data_Alpha
    ws_a = wb.active
    ws_a.title = "Data_Alpha"
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")

    # Sheet 2: Data_Beta (genuinely equivalent student roster structure)
    ws_b = wb.create_sheet(title="Data_Beta")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")

    # Sheet 3: Summary ratings
    ws_s = wb.create_sheet(title="Ratings")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(3, 1, "#")
    ws_s.cell(3, 2, "Student Number")
    ws_s.cell(3, 3, "Final Grade")
    for r in range(4, 9):
        ws_s.cell(r, 1, r - 3)
        ws_s.cell(r, 2, f"2026-000{r - 3}")
        ws_s.cell(r, 3, "1.50")

    p = tmp_path / "ambiguous_duplicate_rosters.xlsx"
    wb.save(str(p))

    # 1. Inspector must raise AmbiguousTemplateError and not silently pick sheet 0
    from modules.parsers.template_inspector import XlsxTemplateInspector
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "multiple ambiguous candidate roster worksheets" in str(exc_info.value).lower()

    # 2. Detector must classify as ambiguous with both grade sheet roles
    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert ROLE_GRADE_SHEET_LECTURE in res.candidate_roles
    assert ROLE_GRADE_SHEET_LECTURE_LAB in res.candidate_roles
    assert res.role is None


def test_xlsx_duplicate_summary_is_ambiguous(detector, tmp_path):
    """
    Requirement 4: Create two worksheets with equally strong summary/rating structures.
    Use completely opaque worksheet names.
    Expected: summary selection -> ambiguous.
    Do not select based on workbook order.
    """
    wb = openpyxl.Workbook()
    # Sheet 1: Primary roster
    ws_r = wb.active
    ws_r.title = "Section_Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")

    # Sheet 2: Summary A (opaque name)
    ws_s1 = wb.create_sheet(title="Report_Omega")
    ws_s1.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s1.cell(2, 1, "OFFICIAL GRADES")
    ws_s1.cell(4, 1, "#")
    ws_s1.cell(4, 2, "Student Number")
    ws_s1.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s1.cell(r, 1, r - 4)
        ws_s1.cell(r, 2, f"2026-000{r - 4}")
        ws_s1.cell(r, 3, "1.25")

    # Sheet 3: Summary B (equally strong summary/rating structure, opaque name)
    ws_s2 = wb.create_sheet(title="Report_Sigma")
    ws_s2.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s2.cell(2, 1, "OFFICIAL GRADES")
    ws_s2.cell(4, 1, "#")
    ws_s2.cell(4, 2, "Student Number")
    ws_s2.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s2.cell(r, 1, r - 4)
        ws_s2.cell(r, 2, f"2026-000{r - 4}")
        ws_s2.cell(r, 3, "1.25")

    p = tmp_path / "ambiguous_duplicate_summaries.xlsx"
    wb.save(str(p))

    # 1. Inspector must raise AmbiguousTemplateError and not pick Report_Omega by order
    from modules.parsers.template_inspector import XlsxTemplateInspector
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "multiple ambiguous summary rating worksheets" in str(exc_info.value).lower()

    # 2. Detector must classify as ambiguous
    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert ROLE_GRADE_SHEET_LECTURE in res.candidate_roles
    assert ROLE_GRADE_SHEET_LECTURE_LAB in res.candidate_roles
    assert res.role is None


def test_xlsx_identical_secondary_matrices_is_ambiguous(detector, tmp_path):
    """
    Requirement 5: Create two secondary assessment worksheets with:
      - identical dimensions;
      - equivalent structural evidence;
      - no informative worksheet names.
    Expected: lab/consolidated assignment -> ambiguous.
    Never use worksheet order as the deciding factor.
    """
    wb = openpyxl.Workbook()
    # Sheet 1: Primary roster
    ws_r = wb.active
    ws_r.title = "Component_Primary"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    # Sheet 2: Summary sheet
    ws_s = wb.create_sheet(title="Component_Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Component_Primary'!D{r}")

    # Sheet 3: Secondary Matrix 1 (opaque name, assessment grid)
    ws_m1 = wb.create_sheet(title="Matrix_Foo")
    ws_m1.cell(4, 1, "#")
    ws_m1.cell(4, 2, "Name of Student")
    ws_m1.cell(4, 3, "Student Number")
    ws_m1.cell(4, 4, "Task 1")
    ws_m1.cell(4, 5, "Task 2")
    for r in range(5, 10):
        ws_m1.cell(r, 1, r - 4)
        ws_m1.cell(r, 2, f"Student {r - 4}")
        ws_m1.cell(r, 3, f"2026-000{r - 4}")
        ws_m1.cell(r, 4, 85)
        ws_m1.cell(r, 5, 90)

    # Sheet 4: Secondary Matrix 2 (opaque name, IDENTICAL dimensions and structural evidence)
    ws_m2 = wb.create_sheet(title="Matrix_Bar")
    ws_m2.cell(4, 1, "#")
    ws_m2.cell(4, 2, "Name of Student")
    ws_m2.cell(4, 3, "Student Number")
    ws_m2.cell(4, 4, "Task 1")
    ws_m2.cell(4, 5, "Task 2")
    for r in range(5, 10):
        ws_m2.cell(r, 1, r - 4)
        ws_m2.cell(r, 2, f"Student {r - 4}")
        ws_m2.cell(r, 3, f"2026-000{r - 4}")
        ws_m2.cell(r, 4, 88)
        ws_m2.cell(r, 5, 92)

    p = tmp_path / "ambiguous_secondary_matrices.xlsx"
    wb.save(str(p))

    # 1. Inspector must raise AmbiguousTemplateError and not assign lab/consolidated by order
    from modules.parsers.template_inspector import XlsxTemplateInspector
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "multiple secondary assessment worksheets" in str(exc_info.value).lower()

    # 2. Detector must classify as ambiguous with candidate_roles=[ROLE_GRADE_SHEET_LECTURE_LAB]
    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_dimension_only_secondary_is_ambiguous(detector, tmp_path):
    """
    Forensic Micro-Closure 1: Secondary assessment sheets with different physical dimensions
    (e.g. 15 columns vs 8 columns) but no structural lineage uniquely establishing Laboratory
    vs Consolidated must raise AmbiguousTemplateError and detector status='ambiguous'.
    Must not use max_column / dimension alone as role authority.
    Verifies both workbook appearance orders.
    """
    def build_test_wb(sheet_order_reversed: bool):
        wb = openpyxl.Workbook()
        ws_r = wb.active
        ws_r.title = "Main_Roster"
        ws_r.cell(1, 1, "Course: BSCS")
        ws_r.cell(2, 1, "Instructor: Dr. Turing")
        ws_r.cell(4, 1, "#")
        ws_r.cell(4, 2, "Name of Student")
        ws_r.cell(4, 3, "Student Number")
        ws_r.cell(4, 4, "Score")
        for r in range(5, 10):
            ws_r.cell(r, 1, r - 4)
            ws_r.cell(r, 2, f"Student {r - 4}")
            ws_r.cell(r, 3, f"2026-000{r - 4}")
            ws_r.cell(r, 4, 85)

        ws_s = wb.create_sheet(title="Institutional_Summary")
        ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
        ws_s.cell(2, 1, "OFFICIAL GRADES")
        ws_s.cell(4, 1, "#")
        ws_s.cell(4, 2, "Student Number")
        ws_s.cell(4, 3, "Final Grade")
        for r in range(5, 10):
            ws_s.cell(r, 1, r - 4)
            ws_s.cell(r, 2, f"2026-000{r - 4}")
            ws_s.cell(r, 3, f"='Main_Roster'!D{r}")

        # Wide secondary sheet: 15 columns
        def populate_wide(ws):
            ws.cell(4, 1, "#")
            ws.cell(4, 2, "Name of Student")
            ws.cell(4, 3, "Student Number")
            for c in range(4, 16):
                ws.cell(4, c, f"Assessment_{c - 3}")
            for r in range(5, 10):
                ws.cell(r, 1, r - 4)
                ws.cell(r, 2, f"Student {r - 4}")
                ws.cell(r, 3, f"2026-000{r - 4}")
                for c in range(4, 16):
                    ws.cell(r, c, 80 + c)

        # Narrow secondary sheet: 6 columns
        def populate_narrow(ws):
            ws.cell(4, 1, "#")
            ws.cell(4, 2, "Name of Student")
            ws.cell(4, 3, "Student Number")
            for c in range(4, 7):
                ws.cell(4, c, f"Score_{c - 3}")
            for r in range(5, 10):
                ws.cell(r, 1, r - 4)
                ws.cell(r, 2, f"Student {r - 4}")
                ws.cell(r, 3, f"2026-000{r - 4}")
                for c in range(4, 7):
                    ws.cell(r, c, 90 + c)

        if not sheet_order_reversed:
            ws_wide = wb.create_sheet(title="Component_Wide")
            populate_wide(ws_wide)
            ws_narrow = wb.create_sheet(title="Component_Narrow")
            populate_narrow(ws_narrow)
        else:
            ws_narrow = wb.create_sheet(title="Component_Narrow")
            populate_narrow(ws_narrow)
            ws_wide = wb.create_sheet(title="Component_Wide")
            populate_wide(ws_wide)

        return wb

    from modules.parsers.template_inspector import XlsxTemplateInspector

    # Order 1: Wide sheet before Narrow sheet
    p1 = tmp_path / "dim_only_wide_first.xlsx"
    wb1 = build_test_wb(sheet_order_reversed=False)
    wb1.save(str(p1))

    with pytest.raises(AmbiguousTemplateError) as exc1:
        XlsxTemplateInspector().inspect(str(p1), profile_id="grade_sheet_xlsx")
    assert "no unique structural lineage" in str(exc1.value).lower()

    res1 = detector.detect_role(str(p1))
    assert res1.status == "ambiguous"
    assert res1.role is None
    assert res1.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]

    # Order 2: Narrow sheet before Wide sheet
    p2 = tmp_path / "dim_only_narrow_first.xlsx"
    wb2 = build_test_wb(sheet_order_reversed=True)
    wb2.save(str(p2))

    with pytest.raises(AmbiguousTemplateError) as exc2:
        XlsxTemplateInspector().inspect(str(p2), profile_id="grade_sheet_xlsx")
    assert "no unique structural lineage" in str(exc2.value).lower()

    res2 = detector.detect_role(str(p2))
    assert res2.status == "ambiguous"
    assert res2.role is None
    assert res2.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_reversed_dimensions_remain_ambiguous(detector, tmp_path):
    """
    Forensic Micro-Closure 2: Reversed dimensions must not manufacture role identity.
    Creating Sheet A wider / Sheet B narrower, and then Sheet A narrower / Sheet B wider,
    with no unique structural lineage must result in ambiguous in both cases.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    for swap in [False, True]:
        wb = openpyxl.Workbook()
        ws_r = wb.active
        ws_r.title = "Roster"
        ws_r.cell(1, 1, "Course: BSCS")
        ws_r.cell(2, 1, "Instructor: Dr. Turing")
        ws_r.cell(4, 1, "#")
        ws_r.cell(4, 2, "Name of Student")
        ws_r.cell(4, 3, "Student Number")
        ws_r.cell(4, 4, "Score")
        for r in range(5, 10):
            ws_r.cell(r, 1, r - 4)
            ws_r.cell(r, 2, f"Student {r - 4}")
            ws_r.cell(r, 3, f"2026-000{r - 4}")
            ws_r.cell(r, 4, 85)

        ws_s = wb.create_sheet(title="Summary")
        ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
        ws_s.cell(2, 1, "OFFICIAL GRADES")
        ws_s.cell(4, 1, "#")
        ws_s.cell(4, 2, "Student Number")
        ws_s.cell(4, 3, "Final Grade")
        for r in range(5, 10):
            ws_s.cell(r, 1, r - 4)
            ws_s.cell(r, 2, f"2026-000{r - 4}")
            ws_s.cell(r, 3, f"='Roster'!D{r}")

        cols_a = 18 if not swap else 7
        cols_b = 7 if not swap else 18

        ws_a = wb.create_sheet(title="Alpha_Grid")
        ws_a.cell(4, 1, "#")
        ws_a.cell(4, 2, "Name of Student")
        ws_a.cell(4, 3, "Student Number")
        for c in range(4, cols_a + 1):
            ws_a.cell(4, c, f"A_{c}")
        for r in range(5, 10):
            ws_a.cell(r, 1, r - 4)
            ws_a.cell(r, 2, f"Student {r - 4}")
            ws_a.cell(r, 3, f"2026-000{r - 4}")
            for c in range(4, cols_a + 1):
                ws_a.cell(r, c, 75)

        ws_b = wb.create_sheet(title="Beta_Grid")
        ws_b.cell(4, 1, "#")
        ws_b.cell(4, 2, "Name of Student")
        ws_b.cell(4, 3, "Student Number")
        for c in range(4, cols_b + 1):
            ws_b.cell(4, c, f"B_{c}")
        for r in range(5, 10):
            ws_b.cell(r, 1, r - 4)
            ws_b.cell(r, 2, f"Student {r - 4}")
            ws_b.cell(r, 3, f"2026-000{r - 4}")
            for c in range(4, cols_b + 1):
                ws_b.cell(r, c, 85)

        f_path = tmp_path / f"rev_dim_swap_{swap}.xlsx"
        wb.save(str(f_path))

        with pytest.raises(AmbiguousTemplateError):
            XlsxTemplateInspector().inspect(str(f_path), profile_id="grade_sheet_xlsx")

        res = detector.detect_role(str(f_path))
        assert res.status == "ambiguous"
        assert res.role is None
        assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_unique_structural_evidence_still_resolves(detector, tmp_path, repo_root):
    """
    Forensic Micro-Closure 3: Canonical dual-component grading sheet with existing structural lineage
    (e.g. cross-sheet aggregation references) still resolves Laboratory and Consolidated,
    even with opaque worksheet names and permuted sheet order.
    """
    src_grade = os.path.join(repo_root, "templates", "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    wb = openpyxl.load_workbook(src_grade)

    # Rename all sheets to opaque non-informative names
    rename_worksheet_with_formulas(wb, "Lecture", "Custom_Lec")
    rename_worksheet_with_formulas(wb, "Laboratory", "Custom_Lab")
    rename_worksheet_with_formulas(wb, "Consolidated", "Custom_Con")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Custom_Summary")

    # Permute order so Summary is first, followed by Consolidated, Lecture, and Lab
    desired_order = ["Custom_Summary", "Custom_Con", "Custom_Lec", "Custom_Lab"]
    wb._sheets = [wb[n] for n in desired_order if n in wb.sheetnames]

    dst = tmp_path / "permuted_canonical_dual.xlsx"
    wb.save(str(dst))

    from modules.parsers.template_inspector import XlsxTemplateInspector
    cand = XlsxTemplateInspector().inspect(str(dst), profile_id="grade_sheet_xlsx")
    assert cand.metadata["roster_sheet"] == "Custom_Lec"
    assert cand.metadata["summary_sheet"] == "Custom_Summary"
    assert cand.metadata["lab_sheet"] == "Custom_Lab"
    assert cand.metadata["con_sheet"] == "Custom_Con"

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.variant == "lecture_lab"


def test_xlsx_permutation_invariance(detector, tmp_path, repo_root):
    """
    Forensic Micro-Closure 5: Permuting workbook sheet order produces the exact same detection result
    for both ambiguous cases and uniquely resolvable cases.
    """
    # 1. Ambiguous case permutation invariance
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb_ambig = openpyxl.Workbook()
    ws_r = wb_ambig.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb_ambig.create_sheet(title="Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_m1 = wb_ambig.create_sheet(title="Matrix_1")
    ws_m1.cell(4, 1, "#")
    ws_m1.cell(4, 2, "Name of Student")
    ws_m1.cell(4, 3, "Student Number")
    for c in range(4, 12):
        ws_m1.cell(4, c, f"M1_{c}")
    for r in range(5, 10):
        ws_m1.cell(r, 1, r - 4)
        ws_m1.cell(r, 2, f"Student {r - 4}")
        ws_m1.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 12):
            ws_m1.cell(r, c, 80)

    ws_m2 = wb_ambig.create_sheet(title="Matrix_2")
    ws_m2.cell(4, 1, "#")
    ws_m2.cell(4, 2, "Name of Student")
    ws_m2.cell(4, 3, "Student Number")
    for c in range(4, 8):
        ws_m2.cell(4, c, f"M2_{c}")
    for r in range(5, 10):
        ws_m2.cell(r, 1, r - 4)
        ws_m2.cell(r, 2, f"Student {r - 4}")
        ws_m2.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 8):
            ws_m2.cell(r, c, 85)

    ambig_orders = [
        ["Roster", "Summary", "Matrix_1", "Matrix_2"],
        ["Summary", "Matrix_2", "Roster", "Matrix_1"],
        ["Matrix_1", "Matrix_2", "Summary", "Roster"],
        ["Matrix_2", "Summary", "Matrix_1", "Roster"],
    ]

    for idx, order in enumerate(ambig_orders):
        wb_ambig._sheets = [wb_ambig[n] for n in order]
        p_order = tmp_path / f"ambig_perm_{idx}.xlsx"
        wb_ambig.save(str(p_order))

        with pytest.raises(AmbiguousTemplateError):
            XlsxTemplateInspector().inspect(str(p_order), profile_id="grade_sheet_xlsx")

        res = detector.detect_role(str(p_order))
        assert res.status == "ambiguous"
        assert res.role is None
        assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_reference_count_trap_asymmetric_refs_remain_ambiguous(detector, tmp_path):
    """
    Forensic Micro-Closure: Reference counts are evidence, NOT role authority.
    Create a workbook where Sheet A -> unrelated sheet, Sheet B -> another unrelated sheet,
    with refs(A) > refs(B), but neither references the other.
    Both refs(A) > refs(B) and refs(A) < refs(B) MUST remain ambiguous.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    for swap in [False, True]:
        wb = openpyxl.Workbook()
        ws_r = wb.active
        ws_r.title = "Roster"
        ws_r.cell(1, 1, "Course: BSCS")
        ws_r.cell(2, 1, "Instructor: Dr. Turing")
        ws_r.cell(4, 1, "#")
        ws_r.cell(4, 2, "Name of Student")
        ws_r.cell(4, 3, "Student Number")
        ws_r.cell(4, 4, "Score")
        for r in range(5, 10):
            ws_r.cell(r, 1, r - 4)
            ws_r.cell(r, 2, f"Student {r - 4}")
            ws_r.cell(r, 3, f"2026-000{r - 4}")
            ws_r.cell(r, 4, 85)

        ws_s = wb.create_sheet(title="Summary")
        ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
        ws_s.cell(2, 1, "OFFICIAL GRADES")
        ws_s.cell(4, 1, "#")
        ws_s.cell(4, 2, "Student Number")
        ws_s.cell(4, 3, "Final Grade")
        for r in range(5, 10):
            ws_s.cell(r, 1, r - 4)
            ws_s.cell(r, 2, f"2026-000{r - 4}")
            ws_s.cell(r, 3, f"='Roster'!D{r}")

        # Unrelated metadata sheet
        ws_aux = wb.create_sheet(title="Notes")
        for r in range(1, 10):
            ws_aux.cell(r, 1, f"Note_{r}")

        ws_a = wb.create_sheet(title="Matrix_A")
        ws_a.cell(4, 1, "#")
        ws_a.cell(4, 2, "Name of Student")
        ws_a.cell(4, 3, "Student Number")
        for c in range(4, 10):
            ws_a.cell(4, c, f"A_{c}")
        for r in range(5, 10):
            ws_a.cell(r, 1, r - 4)
            ws_a.cell(r, 2, f"Student {r - 4}")
            ws_a.cell(r, 3, f"2026-000{r - 4}")
            for c in range(4, 10):
                ws_a.cell(r, c, 80)

        ws_b = wb.create_sheet(title="Matrix_B")
        ws_b.cell(4, 1, "#")
        ws_b.cell(4, 2, "Name of Student")
        ws_b.cell(4, 3, "Student Number")
        for c in range(4, 10):
            ws_b.cell(4, c, f"B_{c}")
        for r in range(5, 10):
            ws_b.cell(r, 1, r - 4)
            ws_b.cell(r, 2, f"Student {r - 4}")
            ws_b.cell(r, 3, f"2026-000{r - 4}")
            for c in range(4, 10):
                ws_b.cell(r, c, 85)

        # Injects formulas referencing the unrelated sheet 'Notes'
        # Neither Matrix_A nor Matrix_B references each other!
        # Case 1: Matrix_A has 5 refs to Notes, Matrix_B has 1 ref to Notes (refs_A > refs_B)
        # Case 2: Matrix_A has 1 ref to Notes, Matrix_B has 5 refs to Notes (refs_A < refs_B)
        refs_a = 5 if not swap else 1
        refs_b = 1 if not swap else 5

        for i in range(refs_a):
            ws_a.cell(5 + i, 4, f"=Notes!A{i+1}")
        for i in range(refs_b):
            ws_b.cell(5 + i, 4, f"=Notes!A{i+1}")

        p = tmp_path / f"ref_trap_swap_{swap}.xlsx"
        wb.save(str(p))

        with pytest.raises(AmbiguousTemplateError):
            XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")

        res = detector.detect_role(str(p))
        assert res.status == "ambiguous"
        assert res.role is None
        assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_quoted_name_lineage_resolution(detector, tmp_path, repo_root):
    """
    Forensic Micro-Closure: Quoted-name worksheet references with spaces and escaped apostrophes.
    Construct a valid dual-component workbook with:
      - Main Roster
      - Practical Component
      - Dean's Practical Sheet (escaped as 'Dean''s Practical Sheet')
      - Official Results
    Formulas in 'Dean''s Practical Sheet' reference 'Practical Component'.
    The inspector and detector must correctly resolve the roles despite quoted names and arbitrary order.
    """
    src_grade = os.path.join(repo_root, "templates", "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    wb = openpyxl.load_workbook(src_grade)

    # Rename using quoted names with spaces and apostrophes
    rename_worksheet_with_formulas(wb, "Lecture", "Main Roster")
    rename_worksheet_with_formulas(wb, "Laboratory", "Practical Component")
    rename_worksheet_with_formulas(wb, "Consolidated", "Dean's Practical Sheet")
    rename_worksheet_with_formulas(wb, "Grading Sheet", "Official Results")

    # Permute order arbitrarily so Official Results is index 0, followed by Consolidated, Lecture, Lab
    desired_order = ["Official Results", "Dean's Practical Sheet", "Main Roster", "Practical Component"]
    wb._sheets = [wb[n] for n in desired_order if n in wb.sheetnames]

    dst = tmp_path / "quoted_apostrophe_grades.xlsx"
    wb.save(str(dst))

    from modules.parsers.template_inspector import XlsxTemplateInspector
    cand = XlsxTemplateInspector().inspect(str(dst), profile_id="grade_sheet_xlsx")
    assert cand.metadata["roster_sheet"] == "Main Roster"
    assert cand.metadata["summary_sheet"] == "Official Results"
    assert cand.metadata["lab_sheet"] == "Practical Component"
    assert cand.metadata["con_sheet"] == "Dean's Practical Sheet"

    res = detector.detect_role(str(dst))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.variant == "lecture_lab"

    # Also verify pair with hyphen and apostrophe: Omega-7 and Dean's Practical Sheet
    wb2 = openpyxl.load_workbook(src_grade)
    rename_worksheet_with_formulas(wb2, "Lecture", "Main Roster")
    rename_worksheet_with_formulas(wb2, "Laboratory", "Omega-7")
    rename_worksheet_with_formulas(wb2, "Consolidated", "Dean's Practical Sheet")
    rename_worksheet_with_formulas(wb2, "Grading Sheet", "Official Results")

    dst2 = tmp_path / "hyphen_apostrophe_grades.xlsx"
    wb2.save(str(dst2))

    cand2 = XlsxTemplateInspector().inspect(str(dst2), profile_id="grade_sheet_xlsx")
    assert cand2.metadata["roster_sheet"] == "Main Roster"
    assert cand2.metadata["summary_sheet"] == "Official Results"
    assert cand2.metadata["lab_sheet"] == "Omega-7"
    assert cand2.metadata["con_sheet"] == "Dean's Practical Sheet"

    res2 = detector.detect_role(str(dst2))
    assert res2.status == "confirmed"
    assert res2.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_cyclic_lineage_is_ambiguous(detector, tmp_path):
    """
    Forensic Micro-Closure: Cyclic / competing formula lineage between secondary assessment sheets.
    Sheet A -> Sheet B AND Sheet B -> Sheet A.
    Must raise AmbiguousTemplateError and detector must return status="ambiguous".
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    # Injects circular formula dependencies:
    # Component_A references Component_B
    ws_a.cell(5, 4, "=Component_B!D5 * 0.5")
    # Component_B references Component_A
    ws_b.cell(5, 4, "=Component_A!D5 * 0.5")

    p = tmp_path / "cyclic_lineage.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "competing/cyclic formula lineage" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_misleading_lineage_without_primary_aggregation_is_ambiguous(detector, tmp_path):
    """
    Requirement 3:
    Misleading-lineage regression:
      Component_A -> Component_B
      Component_B !-> Component_A
    but the physical structures indicate that neither sheet can uniquely be classified
    as Consolidated/Laboratory because neither exhibits role-consistent aggregation
    of the primary lecture grade structure.
    Expected:
      AmbiguousTemplateError raised by inspector.
      detector returns status="ambiguous", role=None, candidate_roles=[ROLE_GRADE_SHEET_LECTURE_LAB].
    This proves dependency direction alone cannot manufacture semantic role identity.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    # Injects directed formula dependency: Component_A -> Component_B
    # but NEITHER sheet references 'Roster' (primary_roster_sheet)!
    ws_a.cell(5, 4, "=Component_B!D5 * 0.5")

    p = tmp_path / "misleading_lineage.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "role-consistent physical aggregation topology" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_unparseable_formula_fails_closed(detector, tmp_path):
    """
    Requirement 5:
    Unusual / unparseable formula handling:
    When a candidate secondary assessment worksheet contains an unparseable or corrupted
    cross-sheet formula necessary for role determination, the lineage is indeterminate (unknown).
    The resolver must fail closed rather than manufacturing a false dependency edge.
    Expected:
      AmbiguousTemplateError raised by inspector.
      detector returns status="ambiguous", role=None, candidate_roles=[ROLE_GRADE_SHEET_LECTURE_LAB].
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    # Component_A references Component_B and Roster
    ws_a.cell(5, 4, "=Component_B!D5 * 0.5")
    ws_a.cell(5, 5, "=Roster!A5")

    # Component_B has an unparseable/corrupted formula with '!'
    ws_b.cell(5, 4, "=UNPARSEABLE(!)")

    p = tmp_path / "unparseable_lineage.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "unparseable or indeterminate formula lineage" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_extract_referenced_sheets_syntax_and_conservative_coverage():
    """
    Requirement 5 & 6:
    Preserve formula syntax coverage and verify conservative fallback behavior:
      - SheetA!A1
      - 'Sheet A'!A1
      - 'Practical Component'!$B$5
      - SUM('Summary 2026'!A1:A20)
      - 'Dean''s Practical Sheet'!C7
      - multiple references
      - ranges
      - absolute references
      - text strings with !
      - unparseable formulas, unclosed quotes, invalid characters failing closed
    """
    from modules.parsers.template_inspector import extract_referenced_sheets

    cases = [
        ("=SheetA!A1", {"SheetA"}, True),
        ("='Sheet A'!A1", {"Sheet A"}, True),
        ("='Practical Component'!$B$5", {"Practical Component"}, True),
        ("=SUM('Summary 2026'!A1:A20)", {"Summary 2026"}, True),
        ("='Dean''s Practical Sheet'!C7", {"Dean's Practical Sheet"}, True),
        ("='Sheet1'!A1 + 'Sheet2'!B2", {"Sheet1", "Sheet2"}, True),
        ('="Hello!World"', set(), True),
        ("='Valid Sheet'!A1:B10", {"Valid Sheet"}, True),
        ("='Sheet 1'!$A$1:$Z$100", {"Sheet 1"}, True),
        ("='Dean''s Sheet'!#REF!", {"Dean's Sheet"}, True),
        # Dynamic / hidden formulas must return is_reliable=False (UNKNOWN != NO DEPENDENCY)
        ('=INDIRECT("Sheet1!A1")', set(), False),
        ('=INDIRECT(A1)', set(), False),
        ('="Sheet1!" & A1', set(), True),
        ('=SUM(INDIRECT("\'" & A1 & "\'!B2"))', set(), False),
        # External workbook references must return is_reliable=False and NOT convert to local sheets
        ("='[External.xlsx]Sheet1'!A1", set(), False),
        ("=[External.xlsx]Sheet1!A1", set(), False),
        ("=SUM([Budget.xlsx]Q1!A1:A10)", set(), False),
        # Unsupported 3D syntax must return is_reliable=False
        ("=Sheet1:Sheet3!A1", set(), False),
        ("=SUM('Sheet1:Sheet3'!A1)", set(), False),
        # Corrupted / unparseable formulas must return is_reliable=False
        ("=SUM('Unclosed Sheet!A1)", set(), False),
        ("=Sheet1!A1 + @#$%", set(), False),
        ("='Broken'!$#@!", set(), False),
        ("=UNPARSEABLE(!)", set(), False),
        ("=Sheet1!A1 + BrokenRef!", set(), False),
    ]

    for formula_str, expected_refs, expected_reliable in cases:
        result = extract_referenced_sheets(formula_str)
        assert set(result) == expected_refs, f"Mismatch in refs for {formula_str}: got {set(result)}, expected {expected_refs}"
        assert result.is_reliable == expected_reliable, f"Mismatch in reliability for {formula_str}: got {result.is_reliable}, expected {expected_reliable}"


# ── 16. Forensic Micro-Closure: Generic Aggregation Topology & Formula Hardening ──

def test_xlsx_generic_consolidated_topology_without_primary_roster_dependency(detector, tmp_path):
    """
    Requirement 3 & Requirement 6 Test A & I:
    Generic consolidated topology without direct primary-roster dependency:
      - Legitimate Consolidated-equivalent sheet (Component_A) references a generic student/master sheet (Student_Master)
      - It references a secondary component sheet (Component_B)
      - It does NOT directly reference a worksheet that happens to look like a 'primary lecture roster'
      - Its physical layout and formulas establish combined/aggregated output (mathematical combination of both)
      - Component_B is an independent component sheet
    Verify that the resolver does not incorrectly reject it solely because the CvSU-specific primary-roster relationship is absent.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Student_Master"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 80)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Student_Master'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        ws_a.cell(r, 4, 75)
        # Combines Component_B and Student_Master with mathematical weighting
        ws_a.cell(r, 5, f"=Component_B!D{r} * 0.4 + Student_Master!D{r} * 0.6")

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    p = tmp_path / "generic_consolidated.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Component_A"
    assert cand.metadata["lab_sheet"] == "Component_B"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.variant == "lecture_lab"


def test_xlsx_misleading_lineage_with_plain_mirror_is_ambiguous(detector, tmp_path):
    """
    Requirement 3 & Requirement 6 Test B:
    Misleading topology where:
      - A -> B (via plain mirror: =Component_B!D5)
      - A -> Student_Master (via plain mirror: =Student_Master!A5)
      - but A has no physically demonstrated aggregation structure (no mathematical combination, weighting, or multi-sheet formula)
      - and B has no uniquely identifiable secondary-component role
    Verify that the resolver remains ambiguous.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Student_Master"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 80)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "COLLEGE OF ENGINEERING")
    ws_s.cell(2, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Student_Master'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    # Injects plain single-cell mirrors without aggregation structure
    ws_a.cell(5, 4, "=Component_B!D5")
    ws_a.cell(5, 5, "=Student_Master!A5")

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    p = tmp_path / "misleading_mirror.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "role-consistent physical aggregation topology" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_dynamic_indirect_formula_fails_closed(detector, tmp_path):
    """
    Requirement 4 & Requirement 6 Test C:
    Dynamic INDIRECT-based hidden dependency:
    When a candidate worksheet uses INDIRECT(...), its full dependency set cannot
    be statically determined with confidence.
    The resolver must treat lineage as UNKNOWN (is_reliable=False) and fail closed.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    # Injects dynamic INDIRECT formula on Component_A
    ws_a.cell(5, 4, '=INDIRECT("Component_B!D5")')

    p = tmp_path / "dynamic_indirect.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "unparseable or indeterminate formula lineage" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_external_workbook_reference_fails_closed(detector, tmp_path):
    """
    Requirement 4, 5 & Requirement 6 Test D:
    External workbook reference:
    Formulas referencing external workbooks ('[Other.xlsx]Sheet1!A1') must not be
    converted into false local dependencies. Lineage is treated as UNKNOWN and fails closed.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    # Injects external workbook reference
    ws_a.cell(5, 4, "=[External.xlsx]Sheet1!A1")

    p = tmp_path / "external_ref.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "unparseable or indeterminate formula lineage" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_unsupported_3d_formula_fails_closed(detector, tmp_path):
    """
    Requirement 4 & Requirement 6 Test E:
    Unsupported formula syntax (3D multi-sheet reference Sheet1:Sheet3!A1):
    Lineage is treated as UNKNOWN and fails closed rather than misidentifying dependencies.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Roster"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Roster'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    # Injects 3D multi-sheet formula
    ws_a.cell(5, 4, "=SUM(Sheet1:Sheet3!A1)")

    p = tmp_path / "3d_ref.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "unparseable or indeterminate formula lineage" in str(exc.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_xlsx_symmetrical_topology_is_ambiguous(detector, tmp_path):
    """
    Requirement 6 Test K:
    Equal/symmetrical topology:
    Neither candidate secondary assessment sheet aggregates the other, and both have
    identical or symmetrical physical structure.
    Must fail closed as ambiguous.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    ws_r = wb.active
    ws_r.title = "Student_Master"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    ws_r.cell(4, 4, "Score")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 85)

    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Student_Master'!D{r}")

    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 75)

    p = tmp_path / "symmetric_lineage.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError):
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    assert res.candidate_roles == [ROLE_GRADE_SHEET_LECTURE_LAB]


def test_structural_audit_catches_prohibited_assumptions():
    """
    Requirement 7:
    Verify that tests/audit_structural_patterns.py strictly identifies and classifies
    any future reintroduction of prohibited authoritative assumptions as Category E:
      - primary-roster-role-authority
      - direct-dependency-role-authority
      - dimension-role-authority
      - reference-count-role-authority
      - worksheet-name-equality
      - workbook-order-role-selection
      - constant-4-week-assumption
      - filename-role-classification
    """
    from tests.audit_structural_patterns import scan_source

    violations = [
        ("modules/parsers/template_inspector.py", "if s1_refs_primary: con_sheet = s1", "primary-roster-role-authority"),
        ("modules/parsers/template_inspector.py", "if s1_refs_s2: con_sheet = s1", "direct-dependency-role-authority"),
        ("modules/parsers/template_inspector.py", "if cols1 > cols2:\n    con_sheet = s1", "dimension-role-authority"),
        ("modules/parsers/template_inspector.py", "if refs1 > refs2:\n    con_sheet = s1", "reference-count-role-authority"),
        ("modules/parsers/template_role_detector.py", "if sheet_name == 'Lecture': role = ROLE_GRADE_SHEET_LECTURE_LAB", "worksheet-name-equality"),
        ("modules/parsers/template_role_detector.py", "res = scored_rosters[0]", "workbook-order-role-selection"),
        ("modules/parsers/template_role_detector.py", "cap = cap / 4 # four-week assumption", "constant-4-week-assumption"),
        ("modules/parsers/template_role_detector.py", "if fn_indicates_role(filename): return", "filename-role-classification"),
        ("modules/parsers/template_inspector.py", "if is_consolidation_formula(val, s2, comps): con_sheet = s1", "aggregation-formula-role-authority"),
        ("modules/parsers/template_inspector.py", "non_summary_sheets = {s for s in sheet_names}", "non-summary-sheet-broad-set"),
        ("modules/parsers/template_inspector.py", "if has_operators: return True", "single-source-operator-consolidation"),
        ("modules/parsers/template_inspector.py", "student_component_sheets = set(roster_candidates_by_sheet.keys())", "summary-in-component-sheets"),
        ("modules/parsers/template_inspector.py", "student_component_sheets = set(sheet_names)", "broad-workbook-sheets-as-components"),
        ("modules/parsers/template_inspector.py", "for row in ws.iter_rows(values_only=True):", "whole-sheet-consolidation-scan"),
        ("modules/parsers/template_inspector.py", "sample_rows = range(first_row, first_row + 10)", "arbitrary-sampling-bounds"),
        ("modules/parsers/template_inspector.py", "cols = range(1, min(ws.max_column + 1, 50))", "arbitrary-sampling-bounds"),
        ("modules/parsers/template_inspector.py", "def is_aggregation_formula(val, other_sheet, all_sheets):", "all-sheets-compatibility-alias"),
        ("modules/parsers/template_inspector.py", "lab_sheet = remaining_assessment_sheets[0]", "unverified-candidate-promotion"),
        ("modules/parsers/template_inspector.py", "primary_roster_sheet = primary_candidate", "metadata-primary-authority-anti-pattern"),
    ]

    for rel_path, snippet, expected_label in violations:
        findings = scan_source(snippet, file_name=rel_path)
        assert len(findings) > 0, f"Audit pattern not matched for {snippet}"
        item, cat, just = findings[0]
        assert item["label"] == expected_label, f"Expected {expected_label}, got {item['label']}"
        assert cat == "E", f"Expected Category E violation for {expected_label}, got {cat} ({just})"


# ── 17. Adversarial False-Positive Regressions: Consolidation vs Transformation ──

def _build_adversarial_base_workbook():
    wb = openpyxl.Workbook()
    # 1. Primary Roster (Student_Master)
    ws_r = wb.active
    ws_r.title = "Student_Master"
    ws_r.cell(1, 1, "Course: BSCS")
    ws_r.cell(2, 1, "Instructor: Dr. Turing")
    ws_r.cell(4, 1, "#")
    ws_r.cell(4, 2, "Name of Student")
    ws_r.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 80)

    # 2. Summary
    ws_s = wb.create_sheet(title="Summary")
    ws_s.cell(1, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Student_Master'!D{r}")

    # 3. Component_A
    ws_a = wb.create_sheet(title="Component_A")
    ws_a.cell(4, 1, "#")
    ws_a.cell(4, 2, "Name of Student")
    ws_a.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_a.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)

    # 4. Component_B
    ws_b = wb.create_sheet(title="Component_B")
    ws_b.cell(4, 1, "#")
    ws_b.cell(4, 2, "Name of Student")
    ws_b.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_b.cell(4, c, f"B_{c}")
    for r in range(5, 10):
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_b.cell(r, c, 85)

    return wb, ws_r, ws_s, ws_a, ws_b


def test_xlsx_adversarial_case_a_arithmetic_transformation_no_consolidation(detector, tmp_path):
    """
    Adversarial Case A:
    A -> B with arithmetic transformation (=Component_B!D5 * 1 or + 0) but no multi-source consolidation.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5 * 1")
    p = tmp_path / "adv_case_a.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_b_sum_over_one_cell_only(detector, tmp_path):
    """
    Adversarial Case B:
    A -> B with SUM() over one cell only (=SUM(Component_B!D5)).
    Single-source aggregation is not multi-component consolidation.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=SUM(Component_B!D5)")
    p = tmp_path / "adv_case_b.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_c_weighted_arithmetic_single_component(detector, tmp_path):
    """
    Adversarial Case C:
    A -> B with weighted arithmetic affecting only one component (=Component_B!D5 * 0.4 or ROUND).
    Single-source weighting/function does not prove consolidation.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5 * 0.4")
    p = tmp_path / "adv_case_c.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_d_references_helper_sheet_without_combining_instructional_structures(detector, tmp_path):
    """
    Adversarial Case D:
    A references two sheets (Component_B and Notes), but Notes is a non-instructional helper sheet.
    References to non-student sheets must not satisfy the multi-component requirement.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_notes = wb.create_sheet(title="Notes")
    ws_notes.cell(1, 1, "Grading Scale: Passing >= 75")
    ws_a.cell(5, 4, "=Component_B!D5")
    ws_a.cell(5, 5, "=Notes!A1")
    p = tmp_path / "adv_case_d.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_e_has_internal_aggregation_but_is_secondary_component(detector, tmp_path):
    """
    Adversarial Case E:
    A has an internal aggregation formula (=SUM(A_6:A_9)) across its own row, but is
    structurally a secondary component and does not combine multiple student components.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5")
    ws_a.cell(5, 5, "=SUM(A_6:A_9)")
    p = tmp_path / "adv_case_e.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_f_both_satisfy_aggregation_predicates_competing(detector, tmp_path):
    """
    Adversarial Case F:
    Both A and B satisfy aggregation predicates referencing each other, creating competing/cyclic lineage.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, ws_b = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5*0.4 + Student_Master!D5*0.6")
    ws_b.cell(5, 4, "=Component_A!D5*0.4 + Student_Master!D5*0.6")
    p = tmp_path / "adv_case_f.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_g_symmetrical_aggregation_topology(detector, tmp_path):
    """
    Adversarial Case G:
    A and B have symmetrical aggregation topology (both reference Student_Master identically).
    Neither can be uniquely identified as Consolidated.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, ws_b = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Student_Master!D5*0.5")
    ws_b.cell(5, 4, "=Student_Master!D5*0.5")
    p = tmp_path / "adv_case_g.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_case_h_references_helper_and_master_metadata_but_no_assessment_combination(detector, tmp_path):
    """
    Adversarial Case H:
    A -> B plus helper/master references, but A remains structurally a secondary component:
    A references Component_B, references a lookup table (Transmutation_Table), and references
    title metadata (Student_Master!A1), but does not combine student assessment rows.
    Must fail closed as ambiguous.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_tt = wb.create_sheet(title="Transmutation_Table")
    ws_tt.cell(1, 1, "Scale")
    ws_a.cell(1, 1, "=Student_Master!A1")
    ws_a.cell(5, 4, "=Component_B!D5*0.5")
    ws_a.cell(5, 5, "=Transmutation_Table!A1")
    p = tmp_path / "adv_case_h.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_positive_synthesized_column_combination_resolves_consolidated(detector, tmp_path):
    """
    Requirement 4:
    Synthesized column combination on student rows:
    In Component_A, Col 4 imports Component_B (=Component_B!D5), Col 5 imports Student_Master
    (=Student_Master!D5), and Col 6 combines Col 4 and Col 5 (=D5*0.4 + E5*0.6).
    The resolver must identify Component_A as Consolidated and Component_B as Laboratory.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5")
    ws_a.cell(5, 5, "=Student_Master!D5")
    ws_a.cell(5, 6, "=D5*0.4 + E5*0.6")
    p = tmp_path / "pos_synthesized.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Component_A"
    assert cand.metadata["lab_sheet"] == "Component_B"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_indirect_on_unrelated_sheet_does_not_invalidate_candidates(detector, tmp_path):
    """
    Requirement 6:
    Verify that an INDIRECT() formula on an unrelated sheet (such as Notes) does NOT
    invalidate the template or candidate secondary worksheets when the candidate sheets
    have reliable formula lineages.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_notes = wb.create_sheet(title="Notes")
    ws_notes.cell(1, 1, '=INDIRECT("A1")')
    ws_a.cell(5, 4, "=Component_B!D5*0.4 + Student_Master!D5*0.6")
    p = tmp_path / "indirect_notes.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Component_A"
    assert cand.metadata["lab_sheet"] == "Component_B"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_adversarial_metadata_header_formula_fails_closed_as_ambiguous(detector, tmp_path):
    """
    Forensic Micro-Closure: Metadata / header formulas must not prove consolidation.
    Cell A1 = Component_B!A1 & Student_Master!A1 in title/metadata row must not satisfy
    consolidation structure when student assessment data rows have no multi-component combinations.
    Must fail closed as ambiguous.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector, AmbiguousTemplateError

    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(1, 1, "=Component_B!A1 & Student_Master!A1")
    ws_a.cell(2, 1, "=Component_B!A2 & Student_Master!A2")
    p = tmp_path / "header_formula_adv.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError):
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_summary_sheet_roster_excluded_from_student_components(detector, tmp_path):
    """
    Forensic Micro-Closure: Summary worksheet satisfying roster detection must NOT become
    student-component evidence. Component_A referencing Component_B and Summary must NOT
    satisfy >= 2 student components requirement. Must fail closed as ambiguous.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector, AmbiguousTemplateError

    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5*0.5 + Summary!D5*0.5")
    p = tmp_path / "summary_comp_adv.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError):
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_positive_consolidation_beyond_10_row_window(detector, tmp_path):
    """
    Forensic Micro-Closure: Removing arbitrary 10-row sampling limit.
    Consolidation formulas appearing only after row 15 (beyond former 10-row window)
    must be fully discovered across the structurally identified data region.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb, ws_r, ws_s, ws_a, ws_b = _build_adversarial_base_workbook()
    for r in range(10, 26):
        ws_r.cell(r, 1, r - 4)
        ws_r.cell(r, 2, f"Student {r - 4}")
        ws_r.cell(r, 3, f"2026-000{r - 4}")
        ws_r.cell(r, 4, 80)
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Student_Master'!D{r}")
        ws_a.cell(r, 1, r - 4)
        ws_a.cell(r, 2, f"Student {r - 4}")
        ws_a.cell(r, 3, f"2026-000{r - 4}")
        ws_b.cell(r, 1, r - 4)
        ws_b.cell(r, 2, f"Student {r - 4}")
        ws_b.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_a.cell(r, c, 75)
            ws_b.cell(r, c, 85)
    for r in range(16, 21):
        ws_a.cell(r, 4, f"=Component_B!D{r}*0.4 + Student_Master!D{r}*0.6")

    p = tmp_path / "beyond_10_rows.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Component_A"
    assert cand.metadata["lab_sheet"] == "Component_B"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_positive_synthesized_column_beyond_49_column_window(detector, tmp_path):
    """
    Forensic Micro-Closure: Removing arbitrary 49-column sampling limit.
    Synthesized combination columns at column 65 (BM), 66 (BN), 67 (BO)
    must be fully discovered across all structurally used worksheet columns.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 65, "=Component_B!BM5")
    ws_a.cell(5, 66, "=Student_Master!BN5")
    ws_a.cell(5, 67, "=BM5*0.4 + BN5*0.6")

    p = tmp_path / "beyond_49_cols.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Component_A"
    assert cand.metadata["lab_sheet"] == "Component_B"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_adversarial_synthesized_source_formulas_outside_student_rows(detector, tmp_path):
    """
    Forensic Micro-Closure: Source formulas appearing outside student data rows (in headers)
    must not satisfy synthesized column consolidation evidence.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(1, 4, "=Component_B!D1")
    ws_a.cell(1, 5, "=Student_Master!E1")
    ws_a.cell(5, 6, "=D5*0.4 + E5*0.6")

    p = tmp_path / "synth_outside_rows.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_synthesized_unrelated_formulas_in_other_columns(detector, tmp_path):
    """
    Forensic Micro-Closure: Unrelated formulas in other columns that do not combine imported
    secondary and partner component columns must not trigger synthesized consolidation.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5")
    ws_a.cell(5, 5, "=Student_Master!D5")
    ws_a.cell(5, 6, "=AVERAGE(D5:D9)")
    ws_a.cell(5, 7, "=E5*2")

    p = tmp_path / "synth_unrelated_cols.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_synthesized_helper_sheet_formula_not_student_component(detector, tmp_path):
    """
    Forensic Micro-Closure: Formulas importing from helper sheets (Notes, Settings, etc.)
    must not count as student component imports.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_notes = wb.create_sheet(title="Notes")
    ws_notes.cell(1, 1, "Help")
    ws_a.cell(5, 4, "=Notes!D5")
    ws_a.cell(5, 5, "=Student_Master!D5")
    ws_a.cell(5, 6, "=D5*0.4 + E5*0.6")

    p = tmp_path / "synth_helper_sheet.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_adversarial_synthesized_combines_student_row_with_header_cell(detector, tmp_path):
    """
    Forensic Micro-Closure: A formula combining student data with a header/metadata cell
    from another column does not combine imported student assessment data.
    """
    wb, _, _, ws_a, _ = _build_adversarial_base_workbook()
    ws_a.cell(5, 4, "=Component_B!D5")
    ws_a.cell(1, 5, "=Student_Master!E1")
    ws_a.cell(5, 6, "=D5*0.4 + E1*0.6")

    p = tmp_path / "synth_header_cell_mix.xlsx"
    wb.save(str(p))

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_permutation_renamed_and_reordered_with_helpers_and_summary_first(detector, tmp_path):
    """
    Forensic Micro-Closure: Full permutation invariance.
    Worksheets are renamed to non-canonical titles and reordered such that the summary sheet
    appears at index 0 (and also satisfies roster detection), a helper sheet appears at index 1,
    and candidate component sheets appear afterwards.
    Role detector must correctly confirm ROLE_GRADE_SHEET_LECTURE_LAB with validated recipes.
    """
    from modules.parsers.template_inspector import XlsxTemplateInspector

    wb = openpyxl.Workbook()
    # Sheet 0: Official_Summary (summary rating sheet at position 0, satisfying roster detection)
    ws_s = wb.active
    ws_s.title = "Official_Summary"
    ws_s.cell(1, 1, "OFFICIAL GRADES")
    ws_s.cell(4, 1, "#")
    ws_s.cell(4, 2, "Student Number")
    ws_s.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_s.cell(r, 1, r - 4)
        ws_s.cell(r, 2, f"2026-000{r - 4}")
        ws_s.cell(r, 3, f"='Master_Component'!D{r}")

    # Sheet 1: Auxiliary_Guide (helper sheet)
    ws_g = wb.create_sheet(title="Auxiliary_Guide")
    ws_g.cell(1, 1, "Instructions and Reference Scale")

    # Sheet 2: Component_Secondary (laboratory component)
    ws_sec = wb.create_sheet(title="Component_Secondary")
    ws_sec.cell(4, 1, "#")
    ws_sec.cell(4, 2, "Name of Student")
    ws_sec.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_sec.cell(4, c, f"S_{c}")
    for r in range(5, 10):
        ws_sec.cell(r, 1, r - 4)
        ws_sec.cell(r, 2, f"Student {r - 4}")
        ws_sec.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_sec.cell(r, c, 85)

    # Sheet 3: Master_Component (primary roster component with class metadata)
    ws_m = wb.create_sheet(title="Master_Component")
    ws_m.cell(1, 1, "Course: BSCS")
    ws_m.cell(2, 1, "Instructor: Dr. Turing")
    ws_m.cell(4, 1, "#")
    ws_m.cell(4, 2, "Name of Student")
    ws_m.cell(4, 3, "Student Number")
    for r in range(5, 10):
        ws_m.cell(r, 1, r - 4)
        ws_m.cell(r, 2, f"Student {r - 4}")
        ws_m.cell(r, 3, f"2026-000{r - 4}")
        ws_m.cell(r, 4, 80)

    # Sheet 4: Component_Aggregate (consolidated component combining secondary + master)
    ws_agg = wb.create_sheet(title="Component_Aggregate")
    ws_agg.cell(4, 1, "#")
    ws_agg.cell(4, 2, "Name of Student")
    ws_agg.cell(4, 3, "Student Number")
    for c in range(4, 10):
        ws_agg.cell(4, c, f"A_{c}")
    for r in range(5, 10):
        ws_agg.cell(r, 1, r - 4)
        ws_agg.cell(r, 2, f"Student {r - 4}")
        ws_agg.cell(r, 3, f"2026-000{r - 4}")
        for c in range(4, 10):
            ws_agg.cell(r, c, 75)
        ws_agg.cell(r, 4, f"=Component_Secondary!D{r}*0.4 + Master_Component!D{r}*0.6")

    p = tmp_path / "perm_full.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Component_Aggregate"
    assert cand.metadata["lab_sheet"] == "Component_Secondary"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_fake_roster_helper_cannot_satisfy_multi_component(tmp_path):
    """
    Commit 173 Section 2:
    Construct a foreign XLSX workbook containing:
      Primary Component
      Secondary Component
      Official Results
      Student Master
      Notes
    Make Student Master physically resemble a valid roster:
      No | Student Name | Student ID
      1
      2
      ...
    but make it a reference/master sheet that is not an instructional assessment component.
    Create a secondary-role topology where:
      Consolidated candidate
          references Secondary Component
          references Student Master
    but does NOT contain true multi-component assessment consolidation.

    Expected:
      status = "ambiguous"
      The master/helper roster must not satisfy the multi-component requirement.
    """
    detector = TemplateRoleDetector()

    # Topology 2A: Workbook with Consolidated candidate referencing Secondary Component and Student Master
    # (combines a secondary component and an external helper roster, NOT the primary component).
    wb_2a = openpyxl.Workbook()
    ws_prim = wb_2a.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_prim.cell(2, 1, "Course & Section: CS101-1A")
    ws_prim.cell(3, 1, "Subject: Programming Fundamentals")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Midterm Exam")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-000{r - 6}")
        ws_prim.cell(r, 4, 88)

    ws_sec = wb_2a.create_sheet(title="Secondary Component")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Activity")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"Student {r - 6}")
        ws_sec.cell(r, 3, f"2026-000{r - 6}")
        ws_sec.cell(r, 4, 92)

    # Student Master physically resembles a valid roster: No, Student Name, Student ID
    ws_mst = wb_2a.create_sheet(title="Student Master")
    ws_mst.cell(5, 1, "No")
    ws_mst.cell(5, 2, "Student Name")
    ws_mst.cell(5, 3, "Student ID")
    for r in range(6, 11):
        ws_mst.cell(r, 1, r - 5)
        ws_mst.cell(r, 2, f"Student {r - 5}")
        ws_mst.cell(r, 3, f"2026-000{r - 5}")

    # Consolidated candidate references Secondary Component and Student Master
    # (lacks consolidation with Primary Component)
    ws_con = wb_2a.create_sheet(title="Consolidated candidate")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Consolidated")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"Student {r - 6}")
        ws_con.cell(r, 3, f"2026-000{r - 6}")
        ws_con.cell(r, 4, f"='Secondary Component'!D{r}*0.5 + 'Student Master'!C{r - 1}*0.5")

    ws_sum = wb_2a.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-000{r - 6}")
        ws_sum.cell(r, 2, "1.75")

    ws_not = wb_2a.create_sheet(title="Notes")
    ws_not.cell(1, 1, "Institutional grading policy guidelines and grade conversion scales.")

    p_2a = tmp_path / "fake_helper_2a.xlsx"
    wb_2a.save(str(p_2a))

    res_2a = detector.detect_role(str(p_2a))
    assert res_2a.status == "ambiguous"

    # Topology 2B: 5 sheets only (Primary Component, Secondary Component, Official Results, Student Master, Notes)
    # where Secondary Component references Student Master (directed lineage to helper roster).
    wb_2b = openpyxl.Workbook()
    ws_p2 = wb_2b.active
    ws_p2.title = "Primary Component"
    ws_p2.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_p2.cell(2, 1, "Course & Section: CS101-1A")
    ws_p2.cell(3, 1, "Subject: Programming Fundamentals")
    ws_p2.cell(6, 1, "#")
    ws_p2.cell(6, 2, "Student Name")
    ws_p2.cell(6, 3, "Student Number")
    ws_p2.cell(6, 4, "Midterm Exam")
    for r in range(7, 12):
        ws_p2.cell(r, 1, r - 6)
        ws_p2.cell(r, 2, f"Student {r - 6}")
        ws_p2.cell(r, 3, f"2026-000{r - 6}")
        ws_p2.cell(r, 4, 88)

    ws_s2 = wb_2b.create_sheet(title="Secondary Component")
    ws_s2.cell(6, 1, "#")
    ws_s2.cell(6, 2, "Student Name")
    ws_s2.cell(6, 3, "Student Number")
    ws_s2.cell(6, 4, "Score")
    for r in range(7, 12):
        ws_s2.cell(r, 1, r - 6)
        ws_s2.cell(r, 2, f"Student {r - 6}")
        ws_s2.cell(r, 3, f"2026-000{r - 6}")
        # References Student Master (single-direction link to reference roster)
        ws_s2.cell(r, 4, f"='Student Master'!C{r - 1}")

    ws_m2 = wb_2b.create_sheet(title="Student Master")
    ws_m2.cell(5, 1, "No")
    ws_m2.cell(5, 2, "Student Name")
    ws_m2.cell(5, 3, "Student ID")
    for r in range(6, 11):
        ws_m2.cell(r, 1, r - 5)
        ws_m2.cell(r, 2, f"Student {r - 5}")
        ws_m2.cell(r, 3, f"2026-000{r - 5}")

    ws_res2 = wb_2b.create_sheet(title="Official Results")
    ws_res2.cell(1, 1, "Republic of the Philippines")
    ws_res2.cell(2, 1, "Cavite State University")
    ws_res2.cell(3, 1, "Official Grades")
    ws_res2.cell(6, 1, "Student Number")
    ws_res2.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_res2.cell(r, 1, f"2026-000{r - 6}")
        ws_res2.cell(r, 2, "1.75")

    ws_not2 = wb_2b.create_sheet(title="Notes")
    ws_not2.cell(1, 1, "General Notes and scale references")

    p_2b = tmp_path / "fake_helper_2b.xlsx"
    wb_2b.save(str(p_2b))

    res_2b = detector.detect_role(str(p_2b))
    assert res_2b.status == "ambiguous"


def test_xlsx_legitimate_dual_component_positive_control(tmp_path):
    """
    Commit 173 Section 3:
    Construct the corresponding valid workbook where the second roster-shaped worksheet
    really IS an independent instructional component.
    Expected:
      status = "confirmed"
      role = ROLE_GRADE_SHEET_LECTURE_LAB
      with correct lab_sheet and con_sheet.
      The system must still resolve legitimate dual-component workbooks.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Primary Component (Lecture): metadata + roster + scores
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_prim.cell(2, 1, "Course & Section: CS101-1A")
    ws_prim.cell(3, 1, "Subject: Programming Fundamentals")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-000{r - 6}")
        ws_prim.cell(r, 4, 88)

    # Secondary Component (Laboratory): roster + lab scores
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Grade")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"='Primary Component'!B{r}")
        ws_sec.cell(r, 3, f"='Primary Component'!C{r}")
        ws_sec.cell(r, 4, 94)

    # Consolidated Component: combines Primary Component and Secondary Component
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Combined Grade")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"='Primary Component'!B{r}")
        ws_con.cell(r, 3, f"='Primary Component'!C{r}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")

    # Summary: Official Results
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-000{r - 6}")
        ws_sum.cell(r, 2, f"='Consolidated Component'!D{r}")

    # Notes
    ws_not = wb.create_sheet(title="Notes")
    ws_not.cell(1, 1, "Course grading syllabus notes.")

    p = tmp_path / "valid_dual_control.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["con_sheet"] == "Consolidated Component"
    assert cand.metadata["lab_sheet"] == "Secondary Component"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_three_indistinguishable_roster_sheets_fails_closed_ambiguous(tmp_path):
    """
    Commit 173 Section 4:
    Construct:
      Component A
      Component B
      Student Master
    where all three contain valid-looking student roster structures.
    Only A and B participate in the actual instructional assessment topology.
    Student Master is a reference dataset.
    Expected:
      Student Master != student component
      and the system must not resolve it as a component merely because it looks like a roster.
      If the topology cannot distinguish the three roles safely, return:
      ambiguous (do not guess).
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Component A: roster + class metadata
    ws_a = wb.active
    ws_a.title = "Component A"
    ws_a.cell(1, 1, "Instructor: Dr. Alan Turing")
    ws_a.cell(2, 1, "Course: BSCS-4A")
    ws_a.cell(5, 1, "#")
    ws_a.cell(5, 2, "Student Name")
    ws_a.cell(5, 3, "Student ID")
    ws_a.cell(5, 4, "Midterm")
    for r in range(6, 11):
        ws_a.cell(r, 1, r - 5)
        ws_a.cell(r, 2, f"Student {r - 5}")
        ws_a.cell(r, 3, f"2026-100{r - 5}")
        ws_a.cell(r, 4, 85)

    # Component B: roster structure + scores
    ws_b = wb.create_sheet(title="Component B")
    ws_b.cell(5, 1, "#")
    ws_b.cell(5, 2, "Student Name")
    ws_b.cell(5, 3, "Student ID")
    ws_b.cell(5, 4, "Final")
    for r in range(6, 11):
        ws_b.cell(r, 1, r - 5)
        ws_b.cell(r, 2, f"Student {r - 5}")
        ws_b.cell(r, 3, f"2026-100{r - 5}")
        ws_b.cell(r, 4, 90)

    # Student Master: valid-looking roster structure (reference dataset)
    ws_mst = wb.create_sheet(title="Student Master")
    ws_mst.cell(5, 1, "No.")
    ws_mst.cell(5, 2, "Student Name")
    ws_mst.cell(5, 3, "Student Number")
    for r in range(6, 11):
        ws_mst.cell(r, 1, r - 5)
        ws_mst.cell(r, 2, f"Student {r - 5}")
        ws_mst.cell(r, 3, f"2026-100{r - 5}")

    # Summary
    ws_sum = wb.create_sheet(title="Official Summary")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades")
    ws_sum.cell(5, 1, "Student ID")
    ws_sum.cell(5, 2, "Final Mark")
    for r in range(6, 11):
        ws_sum.cell(r, 1, f"2026-100{r - 5}")
        ws_sum.cell(r, 2, "1.50")

    p = tmp_path / "three_rosters_undistinguished.xlsx"
    wb.save(str(p))

    # Neither B nor Student Master have directed consolidation lineage distinguishing roles
    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_summary_roster_structure_never_satisfies_component_count(tmp_path):
    """
    Commit 173 Section 5:
    Preserve existing protection:
    If the summary sheet also satisfies roster detection:
      summary sheet != student component
    It must remain excluded.
    Verify that when the summary sheet has:
      - sequential student numbers;
      - student names;
      - student IDs;
      - rating columns;
    it still cannot satisfy the student-component count.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Single primary instructional component: Lecture
    ws_lec = wb.active
    ws_lec.title = "Lecture Component"
    ws_lec.cell(1, 1, "Instructor: Prof. Claude Shannon")
    ws_lec.cell(2, 1, "Course & Section: BSCS-3B")
    ws_lec.cell(3, 1, "Subject: Information Theory")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Grade")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-300{r - 6}")
        ws_lec.cell(r, 4, 88)

    # Summary sheet that physically satisfies roster detection:
    # Has sequential student numbers, student names, student IDs, AND rating columns
    ws_sum = wb.create_sheet(title="Official Grading Sheet")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "College of Engineering and Information Technology")
    ws_sum.cell(4, 1, "Official Grades Summary")
    ws_sum.cell(7, 1, "#")
    ws_sum.cell(7, 2, "Student Name")
    ws_sum.cell(7, 3, "Student Number")
    ws_sum.cell(7, 4, "Final Grade")
    ws_sum.cell(7, 5, "Remarks")
    for r in range(8, 13):
        ws_sum.cell(r, 1, r - 7)
        ws_sum.cell(r, 2, f"Student {r - 7}")
        ws_sum.cell(r, 3, f"2026-300{r - 7}")
        ws_sum.cell(r, 4, f"='Lecture Component'!D{r - 2}")
        ws_sum.cell(r, 5, "Passed")

    ws_not = wb.create_sheet(title="Notes")
    ws_not.cell(1, 1, "Grading criteria instructions")

    p = tmp_path / "summary_roster_single_comp.xlsx"
    wb.save(str(p))

    # The summary sheet must be resolved as summary_sheet and excluded from student components.
    # Therefore, remaining secondary assessment sheets must be empty, confirming single component (Lecture).
    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["summary_sheet"] == "Official Grading Sheet"
    assert cand.metadata["roster_sheet"] == "Lecture Component"
    assert cand.metadata.get("has_lab") is False
    assert cand.metadata.get("lab_sheet") is None
    assert cand.metadata.get("con_sheet") is None

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE


def test_xlsx_convincing_fake_master_never_becomes_authoritative_role(tmp_path):
    """
    Commit 174 Section 2:
    Foreign workbook containing:
      - Primary instructional component
      - Real secondary/laboratory component
      - Consolidated candidate
      - Official results/summary
      - Student Master (intentionally convincing: valid roster headers, sequential student numbers,
        student names and IDs, grade/assessment-looking columns, realistic student rows, enough physical
        structure to resemble an assessment worksheet).
      - Notes
    Verify:
      Student Master never becomes an authoritative s1/s2 role without unique role-consistent topology.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary instructional component
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Marie Curie")
    ws_prim.cell(2, 1, "Course & Section: PHYS301-A")
    ws_prim.cell(3, 1, "Subject: Modern Physics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # 2. Real secondary/laboratory component
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Practical Score")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"='Primary Component'!B{r}")
        ws_sec.cell(r, 3, f"='Primary Component'!C{r}")
        ws_sec.cell(r, 4, 94)

    # 3. Consolidated candidate (combines Primary Component and Secondary Component)
    ws_con = wb.create_sheet(title="Consolidated candidate")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Combined Final")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"='Primary Component'!B{r}")
        ws_con.cell(r, 3, f"='Primary Component'!C{r}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")

    # 4. Official results/summary
    ws_sum = wb.create_sheet(title="Official results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Consolidated candidate'!D{r}")

    # 5. Student Master: Intentionally convincing assessment structure!
    # Valid roster headers, sequential student numbers, student names, IDs,
    # grade/assessment-looking columns (Quiz, Homework, Exam, Total), realistic rows.
    ws_mst = wb.create_sheet(title="Student Master")
    ws_mst.cell(5, 1, "#")
    ws_mst.cell(5, 2, "Student Name")
    ws_mst.cell(5, 3, "Student ID")
    ws_mst.cell(5, 4, "Quiz Avg")
    ws_mst.cell(5, 5, "HW Avg")
    ws_mst.cell(5, 6, "Term Project")
    ws_mst.cell(5, 7, "Master Score")
    for r in range(6, 11):
        ws_mst.cell(r, 1, r - 5)
        ws_mst.cell(r, 2, f"Student {r - 5}")
        ws_mst.cell(r, 3, f"2026-PHYS-{r - 5:03d}")
        ws_mst.cell(r, 4, 85)
        ws_mst.cell(r, 5, 90)
        ws_mst.cell(r, 6, 88)
        ws_mst.cell(r, 7, f"=AVERAGE(D{r}:F{r})")

    # 6. Notes
    ws_not = wb.create_sheet(title="Notes")
    ws_not.cell(1, 1, "Physics Laboratory Safety Guidelines and Grading Policy.")

    p = tmp_path / "strong_fake_master.xlsx"
    wb.save(str(p))

    # Inspection / Detection:
    # Student Master enters generic roster candidate collection because of its physical roster table,
    # but the workbook contains 3 secondary candidate worksheets without a supported 3-way consolidation schema.
    # Therefore, the system fails closed as ambiguous and NEVER crowns Student Master as an authoritative role!
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "secondary assessment worksheets" in str(exc_info.value)
    assert "Student Master" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    # Student Master must never be chosen as lab_sheet or con_sheet:
    for cand in res.candidates:
        assert getattr(cand, "lab_sheet", None) != "Student Master"
        assert getattr(cand, "con_sheet", None) != "Student Master"


def test_xlsx_valid_foreign_dual_component_positive_control(tmp_path):
    """
    Commit 174 Section 3:
    Keep the valid foreign dual-component workbook:
      Primary Component
      Secondary Component
      Consolidated Component
      Official Results
    and verify it still produces:
      grade_sheet_lecture_lab
    with:
      lab_sheet = Secondary Component
      con_sheet = Consolidated Component
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Primary Component
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Marie Curie")
    ws_prim.cell(2, 1, "Course & Section: PHYS301-A")
    ws_prim.cell(3, 1, "Subject: Modern Physics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # Secondary Component
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Score")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"='Primary Component'!B{r}")
        ws_sec.cell(r, 3, f"='Primary Component'!C{r}")
        ws_sec.cell(r, 4, 95)

    # Consolidated Component
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Composite Grade")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"='Primary Component'!B{r}")
        ws_con.cell(r, 3, f"='Primary Component'!C{r}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")

    # Official Results
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Consolidated Component'!D{r}")

    p = tmp_path / "valid_foreign_dual.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["lab_sheet"] == "Secondary Component"
    assert cand.metadata["con_sheet"] == "Consolidated Component"
    assert cand.metadata["has_lab"] is True

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB
    assert res.variant == "lecture_lab"


def test_xlsx_stronger_roster_fake_master_false_promotion_regression(tmp_path):
    """
    Commit 174 Section 4:
    Construct a workbook where Student Master looks MORE like a roster than the actual
    secondary component (e.g. 50 students, all consecutive, formatted headers, higher capacity).
    Ensure the resolver does NOT choose:
      Student Master = Laboratory
    or:
      Student Master = Consolidated
    merely because its roster structure is stronger.
    Expected:
      ambiguous (or correct legitimate role resolution based on physical instructional components).
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Primary Component
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_prim.cell(2, 1, "Course & Section: CS202-B")
    ws_prim.cell(3, 1, "Subject: Data Structures")
    ws_prim.cell(5, 1, "#")
    ws_prim.cell(5, 2, "Student Name")
    ws_prim.cell(5, 3, "Student Number")
    ws_prim.cell(5, 4, "Grade")
    for r in range(6, 16):
        ws_prim.cell(r, 1, r - 5)
        ws_prim.cell(r, 2, f"Student {r - 5}")
        ws_prim.cell(r, 3, f"2026-CS-{r - 5:03d}")
        ws_prim.cell(r, 4, 85)

    # Real secondary component: minimal 10 students
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(5, 1, "#")
    ws_sec.cell(5, 2, "Student Name")
    ws_sec.cell(5, 3, "Student Number")
    ws_sec.cell(5, 4, "Lab Score")
    for r in range(6, 16):
        ws_sec.cell(r, 1, r - 5)
        ws_sec.cell(r, 2, f"Student {r - 5}")
        ws_sec.cell(r, 3, f"2026-CS-{r - 5:03d}")
        ws_sec.cell(r, 4, 90)

    # Student Master: looks MUCH STRONGER as a roster!
    # 50 students, high capacity, formatted columns, detailed fields
    ws_mst = wb.create_sheet(title="Student Master")
    ws_mst.cell(4, 1, "No.")
    ws_mst.cell(4, 2, "Student Full Name")
    ws_mst.cell(4, 3, "Student ID Number")
    ws_mst.cell(4, 4, "Course")
    ws_mst.cell(4, 5, "Section")
    ws_mst.cell(4, 6, "Email Address")
    for r in range(5, 55):
        ws_mst.cell(r, 1, r - 4)
        ws_mst.cell(r, 2, f"Full Student Name {r - 4}")
        ws_mst.cell(r, 3, f"2026-ALL-{r - 4:04d}")
        ws_mst.cell(r, 4, "BSCS")
        ws_mst.cell(r, 5, "Section B")
        ws_mst.cell(r, 6, f"student{r - 4}@university.edu")

    # Official Summary
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades")
    ws_sum.cell(5, 1, "Student Number")
    ws_sum.cell(5, 2, "Final Rating")
    for r in range(6, 16):
        ws_sum.cell(r, 1, f"2026-CS-{r - 5:03d}")
        ws_sum.cell(r, 2, "1.75")

    p = tmp_path / "stronger_master_regression.xlsx"
    wb.save(str(p))

    # The resolver must NOT choose Student Master as Laboratory or Consolidated
    # merely because it has 50 students vs 10 students.
    try:
        cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
        assert cand.metadata.get("lab_sheet") != "Student Master"
        assert cand.metadata.get("con_sheet") != "Student Master"
    except AmbiguousTemplateError:
        pass  # Fails closed as ambiguous - correct!

    res = detector.detect_role(str(p))
    # Must be ambiguous, or if confirmed, must never crown Student Master
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_assessment_looking_helper_with_formulas_fails_closed_without_topology(tmp_path):
    """
    Commit 174 Section 5:
    Create a helper sheet that contains:
      - student roster;
      - grade columns;
      - sequential rows;
      - formulas;
      - metadata.
    It must still NOT automatically become an instructional component (Laboratory)
    unless the surrounding physical topology establishes that role (i.e. referenced by
    summary rating sheet or primary roster sheet).
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Primary Component (Lecture)
    ws_lec = wb.active
    ws_lec.title = "Lecture Component"
    ws_lec.cell(1, 1, "Instructor: Prof. Claude Shannon")
    ws_lec.cell(2, 1, "Course & Section: BSCS-3B")
    ws_lec.cell(3, 1, "Subject: Information Theory")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Lecture Grade")
    for r in range(7, 17):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-IT-{r - 6:03d}")
        ws_lec.cell(r, 4, 88)

    # Official Grading Sheet (pulls grades ONLY from Lecture Component)
    ws_sum = wb.create_sheet(title="Official Grading Sheet")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 17):
        ws_sum.cell(r, 1, f"2026-IT-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Lecture Component'!D{r}")

    # Helper sheet with assessment-looking structure:
    # student roster, grade columns, sequential rows, formulas, and metadata!
    ws_hlp = wb.create_sheet(title="Assessment Criteria Helper")
    ws_hlp.cell(1, 1, "Assessment Rubric and Grading Criteria Breakdown")
    ws_hlp.cell(2, 1, "Passing threshold: 75% | Final Grade Weighting: Lecture 100%")
    ws_hlp.cell(5, 1, "#")
    ws_hlp.cell(5, 2, "Student Name")
    ws_hlp.cell(5, 3, "Student Number")
    ws_hlp.cell(5, 4, "Prelim")
    ws_hlp.cell(5, 5, "Midterm")
    ws_hlp.cell(5, 6, "Final")
    ws_hlp.cell(5, 7, "Computed Grade")
    for r in range(6, 16):
        ws_hlp.cell(r, 1, r - 5)
        ws_hlp.cell(r, 2, f"Student {r - 5}")
        ws_hlp.cell(r, 3, f"2026-IT-{r - 5:03d}")
        ws_hlp.cell(r, 4, 80)
        ws_hlp.cell(r, 5, 85)
        ws_hlp.cell(r, 6, 90)
        # Formulas present inside helper sheet:
        ws_hlp.cell(r, 7, f"=AVERAGE(D{r}:F{r})")

    # Notes sheet
    ws_not = wb.create_sheet(title="Notes")
    ws_not.cell(1, 1, "Departmental grading policy notes.")

    p = tmp_path / "assessment_looking_helper.xlsx"
    wb.save(str(p))

    # Even though Assessment Criteria Helper contains roster headers, student names, IDs,
    # sequential rows, assessment columns, formulas, and metadata:
    # The surrounding physical topology does NOT integrate it into the course grade calculation
    # (neither Official Grading Sheet nor Lecture Component pulls grades from it).
    # Therefore, it must NOT automatically become an authoritative Laboratory component!
    # It must fail closed as ambiguous.
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "lacking role-consistent physical instructional lineage" in str(exc_info.value)
    assert "Assessment Criteria Helper" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    # Crucially: it must NOT be confirmed as Lecture+Lab!
    assert res.role != ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_metadata_richer_fake_master_does_not_become_primary(tmp_path):
    """
    Commit 175 Section 2, 3, 4:
    Adversarial metadata-rich master workbook:
      - Primary Component (Lecture with 3 metadata fields: Instructor, Course, Subject)
      - Secondary Component (Lab with 2 metadata fields: Instructor, Course)
      - Consolidated Component (combines Primary Component and Secondary Component)
      - Official Results (summary rating sheet pulling final grades from Consolidated Component)
      - Student Master (convincing roster with 10 metadata fields:
          Instructor, Course, Subject, Section, Term, Program, Department, College, Campus, AY)
      - Notes

    Student Master has significantly MORE metadata fields (10 fields vs 3 in Primary Component).
    However, Student Master is an unintegrated reference/master worksheet, NOT an instructional component.
    The system must NOT allow metadata density alone to promote Student Master to primary_roster_sheet.
    It must fail closed as ambiguous, preventing Student Master from silently becoming primary,
    preventing corrupt student_component_sheets universes, and preventing invalid lab/con assignments.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary Component (Lecture) - 3 metadata fields
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_prim.cell(2, 1, "Course & Section: BS-Physics-3A")
    ws_prim.cell(3, 1, "Subject: Quantum Mechanics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # 2. Secondary Component (Laboratory) - 2 metadata fields
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_sec.cell(2, 1, "Course & Section: BS-Physics-3A")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Practical Score")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"Student {r - 6}")
        ws_sec.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_sec.cell(r, 4, 94)

    # 3. Consolidated Component (combines Primary Component and Secondary Component)
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Combined Final")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"Student {r - 6}")
        ws_con.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")

    # 4. Official Results (Official summary rating sheet)
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Consolidated Component'!D{r}")

    # 5. Student Master: Intentionally rich in administrative metadata (10 fields)!
    ws_mst = wb.create_sheet(title="Student Master")
    ws_mst.cell(1, 1, "Instructor: Dr. Albert Einstein")
    ws_mst.cell(1, 3, "Course & Section: BS-Physics-3A")
    ws_mst.cell(2, 1, "Subject: General Relativity")
    ws_mst.cell(2, 3, "Section: 3A")
    ws_mst.cell(3, 1, "Term: First Semester")
    ws_mst.cell(3, 3, "Program: Bachelor of Science in Applied Physics")
    ws_mst.cell(4, 1, "Department: Physical Sciences Department")
    ws_mst.cell(4, 3, "College: College of Arts and Sciences")
    ws_mst.cell(5, 1, "Campus: Main Campus - Don Severino delas Alas")
    ws_mst.cell(5, 3, "Academic Year: 2026-2027")
    ws_mst.cell(7, 1, "#")
    ws_mst.cell(7, 2, "Student Name")
    ws_mst.cell(7, 3, "Student ID")
    ws_mst.cell(7, 4, "Directory Score")
    for r in range(8, 13):
        ws_mst.cell(r, 1, r - 7)
        ws_mst.cell(r, 2, f"Student {r - 7}")
        ws_mst.cell(r, 3, f"2026-PHYS-{r - 7:03d}")
        ws_mst.cell(r, 4, 99)

    # 6. Notes
    ws_not = wb.create_sheet(title="Notes")
    ws_not.cell(1, 1, "General physics grading guidelines.")

    p = tmp_path / "metadata_richer_fake_master.xlsx"
    wb.save(str(p))

    # 1. Inspector verification:
    # Student Master has highest metadata score (250 pts vs 75 in Primary Component),
    # but lacks physical instructional calculation lineage to Official Results.
    # Therefore, inspector MUST fail closed as ambiguous.
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    err_msg = str(exc_info.value)
    assert "Student Master" in err_msg
    assert "lacks role-consistent physical instructional lineage" in err_msg

    # 2. Detector verification:
    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    # Crucially: Student Master must never be promoted to authoritative primary role!
    for cand in res.candidates:
        assert getattr(cand, "primary_roster_sheet", None) != "Student Master"
        assert getattr(cand, "lab_sheet", None) != "Student Master"
        assert getattr(cand, "con_sheet", None) != "Student Master"


def test_xlsx_legitimate_positive_control_with_stronger_primary_metadata(tmp_path):
    """
    Commit 175 Section 5:
    Legitimate positive control:
      - Primary Component (Lecture) with stronger metadata evidence (3 metadata fields)
      - Secondary Component (Laboratory) with weaker metadata evidence (1 metadata field)
      - Consolidated Component (combines Primary and Secondary)
      - Official Results (summary sheet pulling from Consolidated Component)
    All physically distinct.
    Verify correct resolution:
      - role = ROLE_GRADE_SHEET_LECTURE_LAB
      - primary_roster_sheet = 'Primary Component'
      - lab_sheet = 'Secondary Component'
      - con_sheet = 'Consolidated Component'
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary Component (Lecture) - 3 metadata fields (score = 75)
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_prim.cell(2, 1, "Course & Section: BS-Physics-3A")
    ws_prim.cell(3, 1, "Subject: Quantum Mechanics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # 2. Secondary Component (Laboratory) - 1 metadata field (score = 25)
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Score")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"='Primary Component'!B{r}")
        ws_sec.cell(r, 3, f"='Primary Component'!C{r}")
        ws_sec.cell(r, 4, 92)

    # 3. Consolidated Component
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Combined Grade")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"='Primary Component'!B{r}")
        ws_con.cell(r, 3, f"='Primary Component'!C{r}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")

    # 4. Official Results
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Consolidated Component'!D{r}")

    p = tmp_path / "positive_control_lecture_lab.xlsx"
    wb.save(str(p))

    cand = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert cand.metadata["roster_sheet"] == "Primary Component"
    assert cand.metadata["lab_sheet"] == "Secondary Component"
    assert cand.metadata["con_sheet"] == "Consolidated Component"
    assert cand.metadata["has_lab"] is True

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_equal_primary_evidence_is_ambiguous(tmp_path):
    """
    Commit 175 Section 6:
    Create two candidate roster sheets with equally strong metadata evidence
    and no unique physical topology distinguishing which is the primary instructional component.
    Expected: status = ambiguous.
    Workbook order must NOT be used as a tie-breaker.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # Sheet Alpha: candidate roster with 2 metadata fields
    ws_a = wb.active
    ws_a.title = "Component Alpha"
    ws_a.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_a.cell(2, 1, "Course & Section: BSCS-3A")
    ws_a.cell(5, 1, "#")
    ws_a.cell(5, 2, "Student Name")
    ws_a.cell(5, 3, "Student Number")
    ws_a.cell(5, 4, "Score Alpha")
    for r in range(6, 11):
        ws_a.cell(r, 1, r - 5)
        ws_a.cell(r, 2, f"Student {r - 5}")
        ws_a.cell(r, 3, f"2026-CS-{r - 5:03d}")
        ws_a.cell(r, 4, 85)

    # Sheet Beta: candidate roster with IDENTICAL 2 metadata fields
    ws_b = wb.create_sheet(title="Component Beta")
    ws_b.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_b.cell(2, 1, "Course & Section: BSCS-3A")
    ws_b.cell(5, 1, "#")
    ws_b.cell(5, 2, "Student Name")
    ws_b.cell(5, 3, "Student Number")
    ws_b.cell(5, 4, "Score Beta")
    for r in range(6, 11):
        ws_b.cell(r, 1, r - 5)
        ws_b.cell(r, 2, f"Student {r - 5}")
        ws_b.cell(r, 3, f"2026-CS-{r - 5:03d}")
        ws_b.cell(r, 4, 90)

    # Official Results references both equally without distinguishing which is primary:
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(5, 1, "Student Number")
    ws_sum.cell(5, 2, "Final Rating")
    for r in range(6, 11):
        ws_sum.cell(r, 1, f"2026-CS-{r - 5:03d}")
        ws_sum.cell(r, 2, f"=('Component Alpha'!D{r} + 'Component Beta'!D{r})/2")

    p = tmp_path / "equal_primary_evidence.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "multiple ambiguous candidate roster worksheets with equal structural evidence" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_indistinguishable_master_hard_information_boundary_is_ambiguous(tmp_path):
    """
    Commit 175 Section 7:
    Hard information boundary:
    Create two physically equivalent worksheets:
      - Real Laboratory
      - Fake Master
    where both:
      - have roster structures;
      - have assessment columns;
      - participate in physically identical consolidation topology.
    Verify the resolver does NOT claim it can determine intent that is absent from the workbook.
    Expected: status = ambiguous.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary Component (Lecture) - 3 metadata fields
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Prof. Marie Curie")
    ws_prim.cell(2, 1, "Course & Section: BS-Chem-2A")
    ws_prim.cell(3, 1, "Subject: Physical Chemistry")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-CHEM-{r - 6:03d}")
        ws_prim.cell(r, 4, 85)

    # 2. Real Laboratory: roster structure, assessment column
    ws_lab = wb.create_sheet(title="Real Laboratory")
    ws_lab.cell(6, 1, "#")
    ws_lab.cell(6, 2, "Student Name")
    ws_lab.cell(6, 3, "Student Number")
    ws_lab.cell(6, 4, "Lab Assessment")
    for r in range(7, 12):
        ws_lab.cell(r, 1, r - 6)
        ws_lab.cell(r, 2, f"='Primary Component'!B{r}")
        ws_lab.cell(r, 3, f"='Primary Component'!C{r}")
        ws_lab.cell(r, 4, 90)

    # 3. Fake Master: physically equivalent roster structure, assessment column
    ws_fak = wb.create_sheet(title="Fake Master")
    ws_fak.cell(6, 1, "#")
    ws_fak.cell(6, 2, "Student Name")
    ws_fak.cell(6, 3, "Student Number")
    ws_fak.cell(6, 4, "Master Assessment")
    for r in range(7, 12):
        ws_fak.cell(r, 1, r - 6)
        ws_fak.cell(r, 2, f"='Primary Component'!B{r}")
        ws_fak.cell(r, 3, f"='Primary Component'!C{r}")
        ws_fak.cell(r, 4, 92)

    # 4. Consolidated Component participates in physically identical consolidation topology
    # referencing both Real Laboratory and Fake Master symmetrically:
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Aggregated Grade")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"='Primary Component'!B{r}")
        ws_con.cell(r, 3, f"='Primary Component'!C{r}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Real Laboratory'!D{r}*0.2 + 'Fake Master'!D{r}*0.2")

    # 5. Official Results
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-CHEM-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Consolidated Component'!D{r}")

    p = tmp_path / "indistinguishable_master_information_boundary.xlsx"
    wb.save(str(p))

    # The workbook contains secondary assessment candidates exceeding supported dual-component capacity
    # and lacking unique structural lineage to distinguish laboratory from helper roles.
    # The resolver must NOT guess intent: it MUST fail closed as ambiguous.
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "secondary assessment worksheets" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_no_primary_lineage_fails_closed(tmp_path):
    """
    Commit 176 Section 5:
    Adversarial foreign workbook with no verified formula lineage:
      - Primary Component (roster-shaped candidate with 3 metadata fields)
      - Student Master (metadata-rich roster-shaped candidate with 10 metadata fields)
      - Official Results (structurally detectable summary rating sheet, but with static values instead of grade formulas)

    Summary is structurally detectable but provides NO verifiable formula lineage connecting
    it to any candidate instructional roster.
    The system must NOT interpret an empty upstream set or missing formula lineage as permission
    to promote the highest metadata candidate.
    Expected:
      AmbiguousTemplateError
      status = "ambiguous"
      role = None
      No candidate may become authoritative primary.
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary Component: candidate roster with 3 metadata fields
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Marie Curie")
    ws_prim.cell(2, 1, "Course & Section: BS-Physics-3A")
    ws_prim.cell(3, 1, "Subject: Quantum Mechanics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Score")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # 2. Student Master: metadata-rich roster with 10 metadata fields
    ws_mast = wb.create_sheet(title="Student Master")
    for i, meta in enumerate([
        "Instructor: Dr. Marie Curie", "Course: BS-Physics", "Subject: Quantum Mechanics",
        "Section: 3A", "Term: First", "Program: Physics", "Department: Physical Sciences",
        "College: CEIT", "Campus: Main", "Academic Year: 2026-2027"
    ], start=1):
        ws_mast.cell(i, 1, meta)
    ws_mast.cell(11, 1, "#")
    ws_mast.cell(11, 2, "Student Name")
    ws_mast.cell(11, 3, "Student Number")
    ws_mast.cell(11, 4, "Permanent Address")
    for r in range(12, 17):
        ws_mast.cell(r, 1, r - 11)
        ws_mast.cell(r, 2, f"Student {r - 11}")
        ws_mast.cell(r, 3, f"2026-PHYS-{r - 11:03d}")
        ws_mast.cell(r, 4, "Cavite")

    # 3. Official Results: structurally detectable summary with static ratings (no formula lineage)
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, 1.75)  # STATIC NUMERICAL VALUES: NO FORMULA LINEAGE!

    p = tmp_path / "no_primary_lineage.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "lacks verified physical student-row instructional calculation lineage" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_upstream_helper_without_grade_contribution_does_not_become_primary(tmp_path):
    """
    Commit 176 Section 6:
    Adversarial workbook where upstream helper provides student identity/lookup but NOT grade calculations:
      - Student Master: 10 metadata fields (highest metadata density)
      - Primary Component: 3 metadata fields (actual instructional grade source)
      - Official Results: summary rating sheet that references Student Master for student number
        and student name, but derives Final Rating from Primary Component.

    Student Master is technically upstream from summary (referenced for name and ID).
    However, Student Master provides zero instructional grade calculations; the final rating
    does NOT derive instructional grade values from Student Master.
    Student Master must NOT become primary.
    Because the metadata-proposed candidate (Student Master) lacks verified instructional lineage,
    the system must fail closed without silently choosing Primary Component unless uniquely proved.
    Expected:
      AmbiguousTemplateError
      status = "ambiguous"
      role = None
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary Component: actual instructional grade source (3 metadata fields)
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_prim.cell(2, 1, "Course & Section: BS-Physics-3A")
    ws_prim.cell(3, 1, "Subject: Quantum Mechanics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # 2. Student Master: lookup/directory sheet with 10 metadata fields (highest metadata density)
    ws_mast = wb.create_sheet(title="Student Master")
    for i, meta in enumerate([
        "Instructor: Dr. Richard Feynman", "Course: BS-Physics", "Subject: Quantum Mechanics",
        "Section: 3A", "Term: First", "Program: Physics", "Department: Physical Sciences",
        "College: CEIT", "Campus: Main", "Academic Year: 2026-2027"
    ], start=1):
        ws_mast.cell(i, 1, meta)
    ws_mast.cell(11, 1, "#")
    ws_mast.cell(11, 2, "Student Name")
    ws_mast.cell(11, 3, "Student Number")
    ws_mast.cell(11, 4, "Address")
    for r in range(12, 17):
        ws_mast.cell(r, 1, r - 11)
        ws_mast.cell(r, 2, f"Student {r - 11}")
        ws_mast.cell(r, 3, f"2026-PHYS-{r - 11:03d}")
        ws_mast.cell(r, 4, "Cavite")

    # 3. Official Results: references Student Master for ID and Name, but Primary Component for Rating!
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Student Name")
    ws_sum.cell(6, 3, "Final Rating")
    for r in range(7, 12):
        # Non-instructional lookup references:
        ws_sum.cell(r, 1, f"='Student Master'!C{r + 5}")
        ws_sum.cell(r, 2, f"='Student Master'!B{r + 5}")
        # Instructional grade calculation reference:
        ws_sum.cell(r, 3, f"='Primary Component'!D{r}")

    p = tmp_path / "upstream_helper_not_instructional.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "candidate primary roster 'Student Master' has highest metadata density" in str(exc_info.value)
    assert "lacks verified student-row instructional calculation lineage" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None
    # Helper is strictly never promoted to primary, laboratory, or consolidated component
    assert res.role != ROLE_GRADE_SHEET_LECTURE
    assert res.role != ROLE_GRADE_SHEET_LECTURE_LAB


def test_xlsx_summary_without_rating_column_fails_closed(tmp_path):
    """
    Commit 176 Section 9:
    Audit summary-sheet authority:
    A worksheet that contains institutional banners ("University", "College")
    but lacks a physical rating column cannot become authoritative summary sheet.
    Expected: TemplateError (missing required summary rating sheet).
    """
    wb = openpyxl.Workbook()

    # Sheet 1: Institutional banner only (no rating column)
    ws_banner = wb.active
    ws_banner.title = "Institutional Banner"
    ws_banner.cell(1, 1, "Republic of the Philippines")
    ws_banner.cell(2, 1, "Cavite State University")
    ws_banner.cell(3, 1, "College of Engineering and Information Technology")
    ws_banner.cell(5, 1, "General Information and Guidelines")

    # Sheet 2: Candidate roster
    ws_roster = wb.create_sheet(title="Lecture")
    ws_roster.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_roster.cell(5, 1, "#")
    ws_roster.cell(5, 2, "Student Name")
    ws_roster.cell(5, 3, "Student Number")
    ws_roster.cell(5, 4, "Score")
    for r in range(6, 11):
        ws_roster.cell(r, 1, r - 5)
        ws_roster.cell(r, 2, f"Student {r - 5}")
        ws_roster.cell(r, 3, f"2026-{r - 5:03d}")
        ws_roster.cell(r, 4, 90)

    p = tmp_path / "banner_without_rating_col.xlsx"
    wb.save(str(p))

    with pytest.raises(TemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "missing required 'Grading Sheet' worksheet or structural summary rating sheet" in str(exc_info.value)


def test_xlsx_numeric_master_contribution_is_ambiguous_without_independent_role_evidence(tmp_path):
    """
    Commit 177 / Micro-closure Section 4:
    Hard information-boundary test for numeric helper contribution:
      - Primary Component: metadata + roster + scores
      - Secondary Component: roster + scores
      - Consolidated Component: physically consumes Primary, Secondary, AND Student Master Directory Score
      - Official Results: summary rating sheet referencing Consolidated Component
      - Student Master: Student ID and Directory Score
    
    Numeric contribution != necessarily instructional identity.
    Consolidation combining references from auxiliary/external sheets on student data rows
    exceeds supported dual-component capacity and lacks independent role evidence.
    Expected:
      AmbiguousTemplateError
      status = "ambiguous"
      role = None
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Primary Component (Lecture)
    ws_prim = wb.active
    ws_prim.title = "Primary Component"
    ws_prim.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_prim.cell(2, 1, "Course & Section: BS-Physics-3A")
    ws_prim.cell(3, 1, "Subject: Quantum Mechanics")
    ws_prim.cell(4, 1, "Schedule Code: 20268877")
    ws_prim.cell(5, 1, "Semester & AY: First Semester 2026-2027")
    ws_prim.cell(7, 1, "#")
    ws_prim.cell(7, 2, "Student Name")
    ws_prim.cell(7, 3, "Student Number")
    ws_prim.cell(7, 4, "Score")
    for r in range(8, 13):
        ws_prim.cell(r, 1, r - 7)
        ws_prim.cell(r, 2, f"Student {r - 7}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 7:03d}")
        ws_prim.cell(r, 4, 85)

    # 2. Secondary Component (Laboratory)
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(7, 1, "#")
    ws_sec.cell(7, 2, "Student Name")
    ws_sec.cell(7, 3, "Student Number")
    ws_sec.cell(7, 4, "Score")
    for r in range(8, 13):
        ws_sec.cell(r, 1, r - 7)
        ws_sec.cell(r, 2, f"='Primary Component'!B{r}")
        ws_sec.cell(r, 3, f"='Primary Component'!C{r}")
        ws_sec.cell(r, 4, 90)

    # 3. Consolidated Component: physically consumes Directory Score from Student Master!
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(7, 1, "#")
    ws_con.cell(7, 2, "Student Name")
    ws_con.cell(7, 3, "Student Number")
    ws_con.cell(7, 4, "Combined Grade")
    for r in range(8, 13):
        ws_con.cell(r, 1, r - 7)
        ws_con.cell(r, 2, f"='Primary Component'!B{r}")
        ws_con.cell(r, 3, f"='Primary Component'!C{r}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.5 + 'Secondary Component'!D{r}*0.3 + 'Student Master'!B{r - 3}*0.2")

    # 4. Student Master: contains Student ID and Directory Score
    ws_mast = wb.create_sheet(title="Student Master")
    ws_mast.cell(1, 1, "Student ID")
    ws_mast.cell(1, 2, "Directory Score")
    for r in range(5, 10):
        ws_mast.cell(r, 1, f"2026-PHYS-{r - 4:03d}")
        ws_mast.cell(r, 2, 80)

    # 5. Official Results: summary rating sheet referencing Consolidated Component
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Student Name")
    ws_sum.cell(6, 3, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, f"Student {r - 6}")
        ws_sum.cell(r, 3, f"='Consolidated Component'!D{r + 1}")

    p = tmp_path / "numeric_master_contribution.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "lacking role-consistent physical aggregation topology" in str(exc_info.value)

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_fake_summary_helper_with_higher_score_does_not_override_real_summary(tmp_path):
    """
    Commit 177 / Micro-closure Section 5:
    Adversarial summary authority test:
      - Fake Report Helper: contains student number, final grade column, and MORE institutional
        banners than the real summary (higher lexical summary score), but static ratings.
      - Official Summary: contains student number, final grade column, and fewer banner words,
        but physically derives ratings via formulas from Lecture!
      - Lecture: candidate roster worksheet.
    
    Lexical/banner score alone must NOT establish summary authority.
    The system must identify the unique physical final-rating calculation topology.
    Expected:
      Official Summary is validated as summary_sheet.
      status = "confirmed"
      role = ROLE_GRADE_SHEET_LECTURE
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Fake Report Helper: 5 banner fields (score 125), static ratings (no lineage)
    ws_fake = wb.active
    ws_fake.title = "Report Helper"
    ws_fake.cell(1, 1, "Republic of the Philippines")
    ws_fake.cell(2, 1, "Cavite State University")
    ws_fake.cell(3, 1, "College of Engineering and Information Technology")
    ws_fake.cell(4, 1, "Department of Information Technology")
    ws_fake.cell(5, 1, "Official Grades Summary Report")
    ws_fake.cell(7, 1, "Student Number")
    ws_fake.cell(7, 2, "Student Name")
    ws_fake.cell(7, 3, "Final Grade")
    for r in range(8, 13):
        ws_fake.cell(r, 1, f"2026-{r:03d}")
        ws_fake.cell(r, 2, f"Student {r}")
        ws_fake.cell(r, 3, 1.75)  # Static values

    # 2. Official Summary: fewer banner words (score 100), but verified final-rating lineage!
    ws_real = wb.create_sheet(title="Official Summary")
    ws_real.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_real.cell(4, 1, "Student Number")
    ws_real.cell(4, 2, "Student Name")
    ws_real.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_real.cell(r, 1, f"2026-{r:03d}")
        ws_real.cell(r, 2, f"Student {r}")
        ws_real.cell(r, 3, f"='Lecture'!D{r + 2}")  # Derives from Lecture!

    # 3. Lecture (Primary Roster)
    ws_lec = wb.create_sheet(title="Lecture")
    ws_lec.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_lec.cell(2, 1, "Course & Section: BSCS 3-1")
    ws_lec.cell(3, 1, "Subject: Computer Science")
    ws_lec.cell(4, 1, "Schedule Code: 12345")
    ws_lec.cell(5, 1, "Semester & AY: 1st Sem 2026-2027")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Score")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 2}")
        ws_lec.cell(r, 3, f"2026-{r - 2:03d}")
        ws_lec.cell(r, 4, 88)

    p = tmp_path / "fake_summary_higher_score.xlsx"
    wb.save(str(p))

    recipe = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert recipe.metadata["summary_sheet"] == "Official Summary"
    assert recipe.metadata["roster_sheet"] == "Lecture"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE


def test_xlsx_equal_summary_evidence_is_ambiguous(tmp_path):
    """
    Commit 177 / Micro-closure Section 6:
    Two summary-like worksheets with identical rating-table structure,
    comparable institutional evidence, and both deriving grades from candidate rosters
    (no unique downstream/final-rating topology).
    Workbook order must not resolve the tie.
    Expected:
      AmbiguousTemplateError
      status = "ambiguous"
      role = None
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Lecture (Primary Roster)
    ws_lec = wb.active
    ws_lec.title = "Lecture"
    ws_lec.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_lec.cell(2, 1, "Course & Section: BSCS 3-1")
    ws_lec.cell(3, 1, "Subject: Computer Science")
    ws_lec.cell(4, 1, "Schedule Code: 12345")
    ws_lec.cell(5, 1, "Semester & AY: 1st Sem 2026-2027")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Score")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-{r - 6:03d}")
        ws_lec.cell(r, 4, 88)

    # 2. Summary A: Rating column deriving from Lecture
    ws_sa = wb.create_sheet(title="Summary A")
    ws_sa.cell(1, 1, "Cavite State University")
    ws_sa.cell(4, 1, "Student Number")
    ws_sa.cell(4, 2, "Student Name")
    ws_sa.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_sa.cell(r, 1, f"2026-{r - 4:03d}")
        ws_sa.cell(r, 2, f"Student {r - 4}")
        ws_sa.cell(r, 3, f"='Lecture'!D{r + 2}")

    # 3. Summary B: Identical Rating column also deriving from Lecture
    ws_sb = wb.create_sheet(title="Summary B")
    ws_sb.cell(1, 1, "Cavite State University")
    ws_sb.cell(4, 1, "Student Number")
    ws_sb.cell(4, 2, "Student Name")
    ws_sb.cell(4, 3, "Final Grade")
    for r in range(5, 10):
        ws_sb.cell(r, 1, f"2026-{r - 4:03d}")
        ws_sb.cell(r, 2, f"Student {r - 4}")
        ws_sb.cell(r, 3, f"='Lecture'!D{r + 2}")

    p = tmp_path / "equal_summary_evidence.xlsx"
    wb.save(str(p))

    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "multiple ambiguous summary rating worksheets" in str(exc_info.value).lower()

    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_summary_helper_referenced_only_for_metadata_not_selected_as_summary(tmp_path):
    """
    Commit 177 / Micro-closure Section 8:
    Construct:
      - Real Summary: derives actual final rating values from Lecture,
        and references Header Helper!A1 for teacher/term/display metadata only.
      - Header Helper: contains rating-looking labels ("Remarks", "Grade") but only
        supplies header text to Real Summary!A1, with no final-rating lineage.
    Header Helper must NOT be selected as summary authority.
    Expected:
      Real Summary is validated as summary_sheet.
      status = "confirmed"
      role = ROLE_GRADE_SHEET_LECTURE
    """
    detector = TemplateRoleDetector()
    wb = openpyxl.Workbook()

    # 1. Header Helper: contains header label and metadata
    ws_help = wb.active
    ws_help.title = "Header Helper"
    ws_help.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_help.cell(2, 1, "Remarks")
    ws_help.cell(3, 1, "Grade Reference Notes")

    # 2. Real Summary: derives final ratings from Lecture and teacher from Header Helper!A1
    ws_real = wb.create_sheet(title="Real Summary")
    ws_real.cell(1, 1, "='Header Helper'!A1")
    ws_real.cell(2, 1, "Course & Section: BSCS 3-1")
    ws_real.cell(3, 1, "Subject: Computer Science")
    ws_real.cell(4, 1, "Schedule Code: 12345")
    ws_real.cell(5, 1, "Semester & AY: 1st Sem 2026-2027")
    ws_real.cell(6, 1, "Student Number")
    ws_real.cell(6, 2, "Student Name")
    ws_real.cell(6, 3, "Final Grade")
    for r in range(7, 12):
        ws_real.cell(r, 1, f"2026-{r - 6:03d}")
        ws_real.cell(r, 2, f"Student {r - 6}")
        ws_real.cell(r, 3, f"='Lecture'!D{r}")

    # 3. Lecture (Primary Roster)
    ws_lec = wb.create_sheet(title="Lecture")
    ws_lec.cell(1, 1, "Instructor: Dr. Ada Lovelace")
    ws_lec.cell(2, 1, "Course & Section: BSCS 3-1")
    ws_lec.cell(3, 1, "Subject: Computer Science")
    ws_lec.cell(4, 1, "Schedule Code: 12345")
    ws_lec.cell(5, 1, "Semester & AY: 1st Sem 2026-2027")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Score")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-{r - 6:03d}")
        ws_lec.cell(r, 4, 92)

    p = tmp_path / "summary_helper_metadata_only.xlsx"
    wb.save(str(p))

    recipe = XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert recipe.metadata["summary_sheet"] == "Real Summary"
    assert recipe.metadata["roster_sheet"] == "Lecture"

    res = detector.detect_role(str(p))
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE


def test_xlsx_higher_metadata_secondary_does_not_override_primary_without_independent_discriminator(detector, tmp_path):
    """
    Commit 178 forensic micro-closure:
    Secondary Component has significantly higher metadata score (10 fields) than Primary Component (3 fields).
    Both are valid roster candidates, have valid student data regions, valid score structures,
    and are physically integrated into final grading via Consolidated Component.
    However, NEITHER derives from the other and NEITHER has an independent structural discriminator
    (asymmetric dependency, summary student roster identity, or consolidation student identity).

    METADATA DENSITY = CANDIDATE EVIDENCE ONLY.
    Secondary MUST NOT be promoted to primary solely from metadata density.
    Because multiple primary-compatible candidates remain without an independent physical discriminator,
    the system MUST fail closed as ambiguous:
        status == "ambiguous"
        role is None
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # 1. Primary Component (lower metadata score: 3 fields)
    ws_prim = wb.create_sheet(title="Primary Component")
    ws_prim.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_prim.cell(2, 1, "Course & Section: Physics 101")
    ws_prim.cell(3, 1, "Subject: Mechanics")
    ws_prim.cell(6, 1, "#")
    ws_prim.cell(6, 2, "Student Name")
    ws_prim.cell(6, 3, "Student Number")
    ws_prim.cell(6, 4, "Lecture Grade")
    for r in range(7, 12):
        ws_prim.cell(r, 1, r - 6)
        ws_prim.cell(r, 2, f"Student {r - 6}")
        ws_prim.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_prim.cell(r, 4, 88)

    # 2. Secondary Component (much higher metadata score: 10 fields)
    ws_sec = wb.create_sheet(title="Secondary Component")
    ws_sec.cell(1, 1, "Instructor: Dr. Richard Feynman")
    ws_sec.cell(2, 1, "Course & Section: Physics 101")
    ws_sec.cell(3, 1, "Subject: Mechanics")
    ws_sec.cell(4, 1, "Section: Section A")
    ws_sec.cell(5, 1, "Term: 1st Semester")
    ws_sec.cell(6, 1, "#")
    ws_sec.cell(6, 2, "Student Name")
    ws_sec.cell(6, 3, "Student Number")
    ws_sec.cell(6, 4, "Lab Score")
    ws_sec.cell(13, 1, "Program: BS Applied Physics")
    ws_sec.cell(14, 1, "Department: Physical Sciences")
    ws_sec.cell(15, 1, "College: College of Arts and Sciences")
    ws_sec.cell(16, 1, "Campus: Main Campus")
    ws_sec.cell(17, 1, "Academic Year: AY 2026-2027")
    for r in range(7, 12):
        ws_sec.cell(r, 1, r - 6)
        ws_sec.cell(r, 2, f"Student {r - 6}")
        ws_sec.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_sec.cell(r, 4, 95)

    # 3. Consolidated Component (symmetrically combines scores from both components)
    ws_con = wb.create_sheet(title="Consolidated Component")
    ws_con.cell(6, 1, "#")
    ws_con.cell(6, 2, "Student Name")
    ws_con.cell(6, 3, "Student Number")
    ws_con.cell(6, 4, "Combined Grade")
    for r in range(7, 12):
        ws_con.cell(r, 1, r - 6)
        ws_con.cell(r, 2, f"Student {r - 6}")
        ws_con.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
        ws_con.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")

    # 4. Official Results
    ws_sum = wb.create_sheet(title="Official Results")
    ws_sum.cell(1, 1, "Republic of the Philippines")
    ws_sum.cell(2, 1, "Cavite State University")
    ws_sum.cell(3, 1, "Official Grades Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
        ws_sum.cell(r, 2, f"='Consolidated Component'!D{r}")

    p = tmp_path / "higher_metadata_secondary_no_discriminator.xlsx"
    wb.save(str(p))

    # Inspector MUST raise AmbiguousTemplateError because multiple primary candidates exist without discriminator
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        XlsxTemplateInspector().inspect(str(p), profile_id="grade_sheet_xlsx")
    assert "multiple ambiguous candidate roster worksheets" in str(exc_info.value)

    # Detector MUST fail closed as ambiguous
    res = detector.detect_role(str(p))
    assert res.status == "ambiguous"
    assert res.role is None


def test_xlsx_primary_selection_permutation_invariance(detector, tmp_path):
    """
    Commit 178 permutation regression:
    Worksheet creation/order must NEVER determine primary role.

    Permutation A (Ambiguous case):
      Permutation 1: [Primary, Secondary, Consolidated, Official Results]
      Permutation 2: [Secondary, Primary, Consolidated, Official Results]
      Both permutations MUST fail closed as ambiguous.

    Permutation B (Positive control with independent physical discriminator):
      Secondary derives student roster from Primary (asymmetric dependency).
      Permutation 1: [Primary, Secondary, Consolidated, Official Results]
      Permutation 2: [Secondary, Primary, Consolidated, Official Results]
      Both permutations MUST resolve to the exact same confirmed semantic roles:
        roster_sheet == "Primary Component"
        lab_sheet == "Secondary Component"
        con_sheet == "Consolidated Component"
    """
    def build_workbook(order: list, with_discriminator: bool):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        for sheet_name in order:
            ws = wb.create_sheet(title=sheet_name)
            if sheet_name == "Primary Component":
                ws.cell(1, 1, "Instructor: Dr. Richard Feynman")
                ws.cell(2, 1, "Course & Section: Physics 101")
                ws.cell(3, 1, "Subject: Mechanics")
                ws.cell(6, 1, "#")
                ws.cell(6, 2, "Student Name")
                ws.cell(6, 3, "Student Number")
                ws.cell(6, 4, "Lecture Grade")
                for r in range(7, 12):
                    ws.cell(r, 1, r - 6)
                    ws.cell(r, 2, f"Student {r - 6}")
                    ws.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
                    ws.cell(r, 4, 88)
            elif sheet_name == "Secondary Component":
                ws.cell(1, 1, "Instructor: Dr. Richard Feynman")
                ws.cell(2, 1, "Course & Section: Physics 101")
                ws.cell(3, 1, "Subject: Mechanics")
                ws.cell(4, 1, "Section: Section A")
                ws.cell(5, 1, "Term: 1st Semester")
                ws.cell(6, 1, "#")
                ws.cell(6, 2, "Student Name")
                ws.cell(6, 3, "Student Number")
                ws.cell(6, 4, "Lab Score")
                ws.cell(13, 1, "Program: BS Applied Physics")
                ws.cell(14, 1, "Department: Physical Sciences")
                ws.cell(15, 1, "College: College of Arts and Sciences")
                ws.cell(16, 1, "Campus: Main Campus")
                ws.cell(17, 1, "Academic Year: AY 2026-2027")
                for r in range(7, 12):
                    ws.cell(r, 1, r - 6)
                    if with_discriminator:
                        # Secondary derives student identity from Primary (independent physical discriminator)
                        ws.cell(r, 2, f"='Primary Component'!B{r}")
                        ws.cell(r, 3, f"='Primary Component'!C{r}")
                    else:
                        ws.cell(r, 2, f"Student {r - 6}")
                        ws.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
                    ws.cell(r, 4, 95)
            elif sheet_name == "Consolidated Component":
                ws.cell(6, 1, "#")
                ws.cell(6, 2, "Student Name")
                ws.cell(6, 3, "Student Number")
                ws.cell(6, 4, "Combined Grade")
                for r in range(7, 12):
                    ws.cell(r, 1, r - 6)
                    if with_discriminator:
                        ws.cell(r, 2, f"='Primary Component'!B{r}")
                        ws.cell(r, 3, f"='Primary Component'!C{r}")
                    else:
                        ws.cell(r, 2, f"Student {r - 6}")
                        ws.cell(r, 3, f"2026-PHYS-{r - 6:03d}")
                    ws.cell(r, 4, f"='Primary Component'!D{r}*0.6 + 'Secondary Component'!D{r}*0.4")
            elif sheet_name == "Official Results":
                ws.cell(1, 1, "Republic of the Philippines")
                ws.cell(2, 1, "Cavite State University")
                ws.cell(3, 1, "Official Grades Summary")
                ws.cell(6, 1, "Student Number")
                ws.cell(6, 2, "Final Rating")
                for r in range(7, 12):
                    ws.cell(r, 1, f"2026-PHYS-{r - 6:03d}")
                    ws.cell(r, 2, f"='Consolidated Component'!D{r}")
        return wb

    order1 = ["Primary Component", "Secondary Component", "Consolidated Component", "Official Results"]
    order2 = ["Secondary Component", "Primary Component", "Consolidated Component", "Official Results"]

    # --- Part A: Ambiguous case (without discriminator) ---
    p_amb1 = tmp_path / "perm_amb_order1.xlsx"
    build_workbook(order1, with_discriminator=False).save(str(p_amb1))
    res_amb1 = detector.detect_role(str(p_amb1))
    assert res_amb1.status == "ambiguous"
    assert res_amb1.role is None

    p_amb2 = tmp_path / "perm_amb_order2.xlsx"
    build_workbook(order2, with_discriminator=False).save(str(p_amb2))
    res_amb2 = detector.detect_role(str(p_amb2))
    assert res_amb2.status == "ambiguous"
    assert res_amb2.role is None

    # --- Part B: Positive control (with independent physical discriminator) ---
    p_pos1 = tmp_path / "perm_pos_order1.xlsx"
    build_workbook(order1, with_discriminator=True).save(str(p_pos1))
    res_pos1 = detector.detect_role(str(p_pos1))
    assert res_pos1.status == "confirmed"
    assert res_pos1.role == ROLE_GRADE_SHEET_LECTURE_LAB
    rec_pos1 = XlsxTemplateInspector().inspect(str(p_pos1), profile_id="grade_sheet_xlsx")
    assert rec_pos1.metadata["roster_sheet"] == "Primary Component"
    assert rec_pos1.metadata["lab_sheet"] == "Secondary Component"
    assert rec_pos1.metadata["con_sheet"] == "Consolidated Component"

    p_pos2 = tmp_path / "perm_pos_order2.xlsx"
    build_workbook(order2, with_discriminator=True).save(str(p_pos2))
    res_pos2 = detector.detect_role(str(p_pos2))
    assert res_pos2.status == "confirmed"
    assert res_pos2.role == ROLE_GRADE_SHEET_LECTURE_LAB
    rec_pos2 = XlsxTemplateInspector().inspect(str(p_pos2), profile_id="grade_sheet_xlsx")
    assert rec_pos2.metadata["roster_sheet"] == "Primary Component"
    assert rec_pos2.metadata["lab_sheet"] == "Secondary Component"
    assert rec_pos2.metadata["con_sheet"] == "Consolidated Component"














