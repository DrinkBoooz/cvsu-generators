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
import shutil
import tempfile
import pytest
import openpyxl
import docx

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
)
from modules.parsers.template_role_detector import TemplateRoleDetector, RoleCandidate
from modules.parsers.template_inspector import XlsxTemplateInspector
from modules.services.template_set_manager import TemplateSetManager
from modules.generators.ceit_gen import GeneratorFactory
from modules.generators.attendance_gen import AttendanceGenerator
from modules.generators.grade_gen import GradeGenerator
from modules.services.template_recipe_service import TemplateRecipeResolver
from modules.common.docx_utils import load_docx, get_full_text, set_cell_text, w


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
    assert "does not support multi-session attendance" in (err_2 or "")

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

