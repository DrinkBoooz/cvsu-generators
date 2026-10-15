"""
Comprehensive Adversarial Template Matrix Test Suite.
Validates that:
  - Inspector discovers physical structure (where).
  - Detector proposes role hypotheses.
  - Validator enforces physical bounds and role compatibility (gatekeeper).
  - Generator consumes only validated recipes.
  - Ambiguity fails closed.
  - Metadata, sheet order, filenames, formula counts, and dimensions DO NOT confer authority.
  - User cannot supply structural coordinates (injected coordinate fields are rejected or ignored).
  - Blank formula-free templates are supported via explicit discovered-candidate confirmation.
  - Helper/master sheets cannot be promoted to instructional roles.
"""

import os
import copy
import pytest
import openpyxl
import docx

from modules.models.recipe import (
    RawTemplateRecipeCandidate,
    ValidatedTemplateRecipe,
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    RosterBinding,
)
from modules.models.template_set import (
    ROLE_GRADE_SHEET_LECTURE,
    ROLE_GRADE_SHEET_LECTURE_LAB,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_SYLLABUS,
)
from modules.parsers.template_inspector import XlsxTemplateInspector, DocxTemplateInspector
from modules.parsers.template_role_detector import TemplateRoleDetector
from modules.parsers.recipe_validator import RecipeValidator
from modules.generators.grade_gen import GradeGenerator
from modules.generators.document_generator import ConfigurableDocumentGenerator


# ── Fixture Builders ──────────────────────────────────────────────────────────

def _build_valid_lecture_wb(dest_path: str):
    """Creates a standard valid lecture grade template."""
    wb = openpyxl.Workbook()
    ws_lec = wb.active
    ws_lec.title = "Lecture"
    ws_lec.cell(1, 1, "Instructor: Prof. Dan Joseph Ortega")
    ws_lec.cell(2, 1, "Course & Section: BSCS-4A")
    ws_lec.cell(3, 1, "Schedule Code: 99112")
    ws_lec.cell(4, 1, "Subject: Software Architecture")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Quiz 1")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-CS-{r - 6:03d}")
        ws_lec.cell(r, 4, 85)

    ws_sum = wb.create_sheet("Grading Sheet")
    ws_sum.cell(1, 1, "Cavite State University - Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"='Lecture'!C{r}")
        ws_sum.cell(r, 2, f"='Lecture'!D{r}")

    wb.save(dest_path)


def _build_blank_formula_free_wb(dest_path: str):
    """Creates a valid template with zero formulas."""
    wb = openpyxl.Workbook()
    ws_lec = wb.active
    ws_lec.title = "Component_Roster"
    ws_lec.cell(1, 1, "Instructor: Prof. Dan Joseph Ortega")
    ws_lec.cell(2, 1, "Course & Section: BSCS-4A")
    ws_lec.cell(3, 1, "Schedule Code: 99112")
    ws_lec.cell(4, 1, "Subject: Software Architecture")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Midterm Exam")
    ws_lec.cell(6, 5, "Final Exam")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-CS-{r - 6:03d}")
        ws_lec.cell(r, 4, 88)
        ws_lec.cell(r, 5, 92)

    ws_sum = wb.create_sheet("Grade_Summary")
    ws_sum.cell(1, 1, "Cavite State University - Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"2026-CS-{r - 6:03d}")
        ws_sum.cell(r, 2, 90.0)

    wb.save(dest_path)


# ── Adversarial Tests ─────────────────────────────────────────────────────────

def test_adversarial_valid_structured_template(tmp_path):
    """Case 1: Standard valid structured template passes inspector, detector, and validator."""
    p = str(tmp_path / "valid_structured.xlsx")
    _build_valid_lecture_wb(p)

    detector = TemplateRoleDetector()
    res = detector.detect_role(p)
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE

    # Resolves and validates recipe
    is_valid, err, recipe = detector.validate_role(p, ROLE_GRADE_SHEET_LECTURE)
    assert is_valid is True
    assert isinstance(recipe, ValidatedTemplateRecipe)
    assert recipe.roster_binding.name_col == 2
    assert recipe.roster_binding.id_col == 3


def test_adversarial_valid_blank_formula_free_template(tmp_path):
    """Case 2: Blank custom XLSX template with ZERO formulas."""
    p = str(tmp_path / "blank_formula_free.xlsx")
    _build_blank_formula_free_wb(p)

    # Assert exactly 0 formulas exist
    wb = openpyxl.load_workbook(p, data_only=False)
    formula_count = sum(
        1 for ws in wb.worksheets
        for row in ws.iter_rows(values_only=True)
        for c in row
        if isinstance(c, str) and c.startswith("=")
    )
    assert formula_count == 0, "Template must contain ZERO formulas"

    detector = TemplateRoleDetector()
    # Automatic detection fails closed because formula lineage is absent
    det_res = detector.detect_role(p)
    assert det_res.status == "ambiguous"
    disc = det_res.discovered_structures
    assert "Component_Roster" in disc.get("roster_candidates", [])
    assert "Grade_Summary" in disc.get("summary_candidates", [])

    # Manual confirmation of discovered candidate sheets
    sheet_sel = {"roster_sheet": "Component_Roster", "summary_sheet": "Grade_Summary"}
    is_valid, err, recipe = detector.validate_role(p, ROLE_GRADE_SHEET_LECTURE, sheet_selection=sheet_sel)
    assert is_valid is True
    assert isinstance(recipe, ValidatedTemplateRecipe)

    # Real generator consumes validated recipe
    out_f = str(tmp_path / "out_blank.xlsx")
    gen = GradeGenerator(p, recipe)
    dummy_info = {
        "instructor": "Prof. Dan",
        "course_section": "BSCS-4A",
        "schedule_code": "99112",
        "subject": "Software Architecture",
        "semester": "1st Semester AY 2026-2027",
    }
    dummy_students = [("LOVELACE, ADA A.", "202610001")]
    assert gen.generate(dummy_info, dummy_students, out_f) is True
    assert os.path.exists(out_f)


def test_adversarial_foreign_terminology_cases(tmp_path):
    """Case 3: Foreign terminology templates with distinct semantic anchors."""
    detector = TemplateRoleDetector()

    pairs = [
        ("Participant", "Matriculation"),
        ("Candidate", "Registration"),
        ("Person", "Identifier"),
    ]
    for name_h, id_h in pairs:
        p = str(tmp_path / f"foreign_{name_h}_{id_h}.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Assessment_Sheet"
        ws.cell(1, 1, "Instructor: Prof. Dan")
        ws.cell(2, 1, "Course & Section: BSCS-4A")
        ws.cell(3, 1, "Schedule Code: 99112")
        ws.cell(5, 1, "#")
        ws.cell(5, 2, name_h)
        ws.cell(5, 3, id_h)
        ws.cell(5, 4, "Score")
        for r in range(6, 10):
            ws.cell(r, 1, r - 5)
            ws.cell(r, 2, f"Student {r}")
            ws.cell(r, 3, f"ID-{r:04d}")
            ws.cell(r, 4, 90)

        ws_sum = wb.create_sheet("Grading Sheet")
        ws_sum.cell(1, 1, "Grading Sheet Summary")
        ws_sum.cell(6, 1, "Student Number")
        ws_sum.cell(6, 2, "Final Rating")
        for r in range(6, 10):
            ws_sum.cell(r + 1, 1, f"='Assessment_Sheet'!C{r}")
            ws_sum.cell(r + 1, 2, f"='Assessment_Sheet'!D{r}")
        wb.save(p)

        res = detector.detect_role(p)
        assert res.status == "confirmed", f"Failed for {name_h}/{id_h}"
        assert res.role == ROLE_GRADE_SHEET_LECTURE


def test_adversarial_renamed_file_and_workbook(tmp_path):
    """Cases 4 & 5: Renamed template file and arbitrary workbook title do not alter authority."""
    p = str(tmp_path / "COMPLETELY_RANDOM_NAME_12345.xyz.xlsx")
    _build_valid_lecture_wb(p)

    detector = TemplateRoleDetector()
    res = detector.detect_role(p)
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE


def test_adversarial_reordered_and_extra_sheets(tmp_path):
    """Cases 6, 7 & 8: Reordered sheets and extra unrelated sheets do not disrupt role detection."""
    p = str(tmp_path / "reordered_and_extra.xlsx")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Extra sheet 1 (unrelated instructions)
    ws_notes = wb.create_sheet("Grading Guidelines & Notes")
    ws_notes.cell(1, 1, "Read these instructions carefully before submitting.")
    ws_notes.cell(2, 1, "Deadlines are final.")

    # Summary sheet placed BEFORE lecture sheet in tab order
    ws_sum = wb.create_sheet("Grading Sheet")
    ws_sum.cell(1, 1, "Cavite State University - Summary")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")

    # Lecture sheet placed LAST in tab order
    ws_lec = wb.create_sheet("Lecture")
    ws_lec.cell(1, 1, "Instructor: Prof. Dan Joseph Ortega")
    ws_lec.cell(2, 1, "Course & Section: BSCS-4A")
    ws_lec.cell(3, 1, "Schedule Code: 99112")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Quiz 1")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-CS-{r - 6:03d}")
        ws_lec.cell(r, 4, 85)
        # Summary formulas point to Lecture
        ws_sum.cell(r, 1, f"='Lecture'!C{r}")
        ws_sum.cell(r, 2, f"='Lecture'!D{r}")

    # Extra sheet 2 (grade transmutation table)
    ws_trans = wb.create_sheet("Transmutation Table")
    for r in range(1, 10):
        ws_trans.cell(r, 1, 70 + r * 3)
        ws_trans.cell(r, 2, 3.0 - (r * 0.25))

    wb.save(p)

    detector = TemplateRoleDetector()
    res = detector.detect_role(p)
    assert res.status == "confirmed"
    assert res.role == ROLE_GRADE_SHEET_LECTURE


def test_adversarial_missing_required_roster_fails_closed(tmp_path):
    """Case 9: Missing required student roster fails closed."""
    p = str(tmp_path / "missing_roster.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary Only"
    ws.cell(1, 1, "Grading Sheet Summary")
    ws.cell(2, 1, "No roster sheet exists here")
    wb.save(p)

    detector = TemplateRoleDetector()
    res = detector.detect_role(p)
    assert res.status in ("ambiguous", "unrecognized", "unsupported")


def test_adversarial_opaque_headers_fails_closed(tmp_path):
    """Case 10: Opaque identity headers without semantic anchors fail closed as ambiguous."""
    p = str(tmp_path / "opaque_headers.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lecture"
    ws.cell(1, 1, "Instructor: Prof. Dan")
    ws.cell(2, 1, "Course & Section: BSCS-4A")
    ws.cell(3, 1, "Schedule Code: 99112")
    ws.cell(5, 1, "COL_A")
    ws.cell(5, 2, "COL_B")
    ws.cell(5, 3, "COL_C")
    ws.cell(5, 4, "COL_D")
    for r in range(6, 11):
        ws.cell(r, 1, r - 5)
        ws.cell(r, 2, f"Val_{r}_B")
        ws.cell(r, 3, f"Val_{r}_C")
        ws.cell(r, 4, 85)
    wb.save(p)

    detector = TemplateRoleDetector()
    res = detector.detect_role(p)
    assert res.status != "confirmed", "Opaque headers must fail closed and not guess roles"


def test_adversarial_helper_and_student_master_cannot_acquire_instructional_role(tmp_path):
    """Cases 11 & 12: Helper/directory sheet cannot be promoted to instructional role."""
    p = str(tmp_path / "helper_master_test.xlsx")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Primary Lecture
    ws_lec = wb.create_sheet("Lecture")
    ws_lec.cell(1, 1, "Instructor: Prof. Dan Joseph Ortega")
    ws_lec.cell(2, 1, "Course & Section: BSCS-4A")
    ws_lec.cell(3, 1, "Schedule Code: 99112")
    ws_lec.cell(4, 1, "Subject: Software Architecture")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Quiz")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-CS-{r - 6:03d}")
        ws_lec.cell(r, 4, 85)

    # Student Master: directory sheet with 10 metadata fields and address column, but NO grade contribution
    ws_mast = wb.create_sheet("Student Master")
    for i, meta in enumerate(["Instructor: Prof Dan", "College: CEIT", "Dept: DIT", "Campus: Main", "Term: 1st"], 1):
        ws_mast.cell(i, 1, meta)
    ws_mast.cell(6, 1, "#")
    ws_mast.cell(6, 2, "Student Name")
    ws_mast.cell(6, 3, "Student Number")
    ws_mast.cell(6, 4, "Address")
    for r in range(7, 12):
        ws_mast.cell(r, 1, r - 6)
        ws_mast.cell(r, 2, f"Student {r - 6}")
        ws_mast.cell(r, 3, f"2026-CS-{r - 6:03d}")
        ws_mast.cell(r, 4, "Cavite")

    # Summary: points exclusively to Lecture
    ws_sum = wb.create_sheet("Grading Sheet")
    ws_sum.cell(1, 1, "Official Grades")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"='Lecture'!C{r}")
        ws_sum.cell(r, 2, f"='Lecture'!D{r}")

    wb.save(p)

    detector = TemplateRoleDetector()
    # Automatic detection fails closed as ambiguous because multiple candidate rosters exist
    det = detector.detect_role(p)
    assert det.status == "ambiguous"
    disc = det.discovered_structures
    assert "Lecture" in disc.get("roster_candidates", [])
    assert "Student Master" in disc.get("roster_candidates", [])

    # Manual selection of true instructional sheet succeeds
    is_valid_lec, err_lec, recipe_lec = detector.validate_role(
        p,
        ROLE_GRADE_SHEET_LECTURE,
        sheet_selection={"roster_sheet": "Lecture"},
    )
    assert is_valid_lec is True
    assert recipe_lec.roster_binding.worksheet_name == "Lecture"

    # User explicitly attempting to force "Student Master" as primary roster is rejected
    is_valid_mast, err_mast, _ = detector.validate_role(
        p,
        ROLE_GRADE_SHEET_LECTURE,
        sheet_selection={"roster_sheet": "Student Master"},
    )
    assert is_valid_mast is False
    assert "Manual selection cannot promote a non-instructional helper sheet" in str(err_mast)


def test_adversarial_recipe_validator_rejects_column_collisions():
    """Case 13: RecipeValidator rejects structurally incompatible bindings within physical bounds."""
    # name_col == id_col
    cand_name_id = RawTemplateRecipeCandidate(
        template_path="fake.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Roster",
            "first_data_row_index": 7,
            "name_col": 2,
            "id_col": 2,  # Collision
            "capacity_limit": 50,
        },
        header_candidates=[
            {"field": "instructor", "cell_type": "xlsx_cell", "target": "A1"},
            {"field": "course_section", "cell_type": "xlsx_cell", "target": "A2"},
            {"field": "schedule_code", "cell_type": "xlsx_cell", "target": "A3"},
        ],
    )
    with pytest.raises(TemplateError) as exc1:
        RecipeValidator.validate(cand_name_id, "grade_sheet_xlsx")
    assert "name_col and id_col cannot bind to the same column" in str(exc1.value)

    # name_col == index_col
    cand_name_idx = RawTemplateRecipeCandidate(
        template_path="fake.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp2",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Roster",
            "first_data_row_index": 7,
            "name_col": 2,
            "id_col": 3,
            "index_col": 2,  # Collision
            "capacity_limit": 50,
        },
        header_candidates=[
            {"field": "instructor", "cell_type": "xlsx_cell", "target": "A1"},
            {"field": "course_section", "cell_type": "xlsx_cell", "target": "A2"},
            {"field": "schedule_code", "cell_type": "xlsx_cell", "target": "A3"},
        ],
    )
    with pytest.raises(TemplateError) as exc2:
        RecipeValidator.validate(cand_name_idx, "grade_sheet_xlsx")
    assert "index_col cannot collide with name_col" in str(exc2.value)


def test_adversarial_user_coordinate_injection_prevention(tmp_path):
    """
    Cases 14-17: User cannot supply structural coordinates.
    Injecting row, column, name_col, id_col, table_index, etc., into public payloads
    MUST NOT alter the validated recipe bindings computed by the inspector.
    """
    p = str(tmp_path / "coord_injection_test.xlsx")
    _build_valid_lecture_wb(p)

    detector = TemplateRoleDetector()

    # Attempt to inject adversarial coordinate values via sheet_selection
    malicious_selection = {
        "roster_sheet": "Lecture",
        "row": 999,
        "col": 888,
        "name_col": 44,
        "id_col": 55,
        "index_col": 66,
        "first_data_row_index": 123,
        "table_index": 77,
    }

    is_valid, err, recipe = detector.validate_role(
        p,
        ROLE_GRADE_SHEET_LECTURE,
        sheet_selection=malicious_selection,
    )
    assert is_valid is True
    assert isinstance(recipe, ValidatedTemplateRecipe)

    # Verify that the physical coordinates in the binding were inspector-derived, NOT user-injected
    assert recipe.roster_binding.first_data_row_index == 7, "Injected first_data_row_index was ignored"
    assert recipe.roster_binding.name_col == 2, "Injected name_col was ignored"
    assert recipe.roster_binding.id_col == 3, "Injected id_col was ignored"
    assert recipe.roster_binding.index_col == 1, "Injected index_col was ignored"
    assert recipe.roster_binding.table_index == 0, "Injected table_index was ignored"


def test_adversarial_metadata_decoy_sheet_cannot_steal_primary(tmp_path):
    """
    Cases 18-21: Metadata-heavy decoy sheet cannot steal primary role from true instructional sheet.
    Even with 15 metadata labels on Decoy, true student identity derivation takes sole authority.
    """
    p = str(tmp_path / "metadata_decoy.xlsx")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Sheet 1: Decoy (15 metadata labels, but no formula lineage from summary)
    ws_decoy = wb.create_sheet("Decoy_Admin_Sheet")
    for i in range(1, 16):
        ws_decoy.cell(i, 1, f"Administrative Label {i}: Important Value")
    ws_decoy.cell(16, 1, "#")
    ws_decoy.cell(16, 2, "Student Name")
    ws_decoy.cell(16, 3, "Student Number")
    ws_decoy.cell(16, 4, "Static Column")
    for r in range(17, 22):
        ws_decoy.cell(r, 1, r - 16)
        ws_decoy.cell(r, 2, f"Student {r - 16}")
        ws_decoy.cell(r, 3, f"2026-CS-{r - 16:03d}")
        ws_decoy.cell(r, 4, 100)

    # Sheet 2: Real Lecture (only 2 metadata labels, but summary derives from it)
    ws_lec = wb.create_sheet("Actual_Lecture")
    ws_lec.cell(1, 1, "Instructor: Prof. Dan Joseph Ortega")
    ws_lec.cell(2, 1, "Course & Section: BSCS-4A")
    ws_lec.cell(3, 1, "Schedule Code: 99112")
    ws_lec.cell(4, 1, "Subject: Software Architecture")
    ws_lec.cell(6, 1, "#")
    ws_lec.cell(6, 2, "Student Name")
    ws_lec.cell(6, 3, "Student Number")
    ws_lec.cell(6, 4, "Quiz Grade")
    for r in range(7, 12):
        ws_lec.cell(r, 1, r - 6)
        ws_lec.cell(r, 2, f"Student {r - 6}")
        ws_lec.cell(r, 3, f"2026-CS-{r - 6:03d}")
        ws_lec.cell(r, 4, 85)

    # Summary derives from Actual_Lecture
    ws_sum = wb.create_sheet("Grading Sheet")
    ws_sum.cell(1, 1, "Official Grades")
    ws_sum.cell(6, 1, "Student Number")
    ws_sum.cell(6, 2, "Final Rating")
    for r in range(7, 12):
        ws_sum.cell(r, 1, f"='Actual_Lecture'!C{r}")
        ws_sum.cell(r, 2, f"='Actual_Lecture'!D{r}")

    wb.save(p)

    detector = TemplateRoleDetector()
    # Automatic detection fails closed as ambiguous because multiple candidate rosters exist
    res = detector.detect_role(p)
    assert res.status == "ambiguous"
    disc = res.discovered_structures
    assert "Actual_Lecture" in disc.get("roster_candidates", [])
    assert "Decoy_Admin_Sheet" in disc.get("roster_candidates", [])

    # Confirm manual selection of Actual_Lecture binds Actual_Lecture, not Decoy
    is_valid, err, recipe = detector.validate_role(
        p,
        ROLE_GRADE_SHEET_LECTURE,
        sheet_selection={"roster_sheet": "Actual_Lecture"},
    )
    assert is_valid is True
    assert recipe.roster_binding.worksheet_name == "Actual_Lecture"

    # Confirm manual selection of Decoy is rejected
    is_valid_decoy, err_decoy, _ = detector.validate_role(
        p,
        ROLE_GRADE_SHEET_LECTURE,
        sheet_selection={"roster_sheet": "Decoy_Admin_Sheet"},
    )
    assert is_valid_decoy is False
