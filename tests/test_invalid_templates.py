import copy
import os
import shutil
import tempfile
from datetime import date
import docx
import openpyxl
import pytest

from modules.models.recipe import (
    RECIPE_SCHEMA_VERSION,
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    RawTemplateRecipeCandidate,
    RawAttendanceTemplateRecipeCandidate,
    ValidatedAttendanceTemplateRecipe,
    AttendanceInfoBinding,
    AttendanceMatrixBinding,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    PROFILE_ATTENDANCE_DOCX,
    PROFILE_REGISTRY,
)
from modules.parsers.recipe_validator import RecipeValidator
from modules.parsers.template_inspector import (
    DocxTemplateInspector,
    XlsxTemplateInspector,
    AttendanceTemplateInspector,
)
from modules.generators.ceit_gen import GeneratorFactory
from modules.generators.attendance_gen import (
    AttendanceGenerator,
    generate_attendance_for_month,
)
from modules.services.template_recipe_service import TemplateRecipeResolver


def test_e0_missing_canonical_template_fails_explicitly(tmp_path):
    """E0: Missing canonical native template raises FileNotFoundError explicitly,
    proving no shadow-template fallback survives."""
    empty_templates_dir = tmp_path / "templates"
    empty_templates_dir.mkdir()

    factory = GeneratorFactory(str(empty_templates_dir))
    all_gens = factory.get_all(include_custom=False)
    assert len(all_gens) == 7

    for gen_factory, suffix in all_gens:
        with pytest.raises(FileNotFoundError) as exc_info:
            gen_factory()
        assert "Template not found" in str(exc_info.value)


def test_e1_missing_required_metadata_field(tmp_path):
    """E1: Missing Required Field raises TemplateError during validation."""
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.docx"),
        profile_id="academic_docx",
        fingerprint="dummy_fp",
        roster_candidate={
            "table_index": 1,
            "first_data_row_index": 1,
            "name_col": 1,
            "id_col": 2,
        },
        header_candidates=[
            # Missing "instructor", which is strictly required by PROFILE_ACADEMIC_DOCX
            {
                "field": "course_section",
                "cell_type": "docx_table",
                "target": (0, 0, 1),
                "confidence": 1.0,
            }
        ],
        signature_candidates=[],
        collisions=[],
        metadata={},
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "Missing required field 'instructor'" in str(exc_info.value)


def test_e2_duplicate_ambiguous_metadata_binding(tmp_path):
    """E2: Duplicate / ambiguous candidate bindings with identical confidence raise AmbiguousTemplateError."""
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.docx"),
        profile_id="academic_docx",
        fingerprint="dummy_fp",
        roster_candidate={
            "table_index": 1,
            "first_data_row_index": 1,
            "name_col": 1,
            "id_col": 2,
        },
        header_candidates=[
            {
                "field": "instructor",
                "cell_type": "docx_table",
                "target": (0, 0, 1),
                "confidence": 0.90,
            }
        ],
        signature_candidates=[],
        collisions=[
            {
                "field": "instructor",
                "candidates": [
                    {"cell_type": "docx_table", "target": (0, 0, 1), "confidence": 0.90},
                    {"cell_type": "docx_table", "target": (0, 1, 1), "confidence": 0.90},
                ],
            }
        ],
        metadata={},
    )
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "Ambiguous template binding for field 'instructor'" in str(exc_info.value)


def test_e3_cross_field_collision(tmp_path):
    """E3: Candidate collision with equal confidence across ambiguous interpretations raises AmbiguousTemplateError."""
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.docx"),
        profile_id="academic_docx",
        fingerprint="dummy_fp",
        roster_candidate={
            "table_index": 1,
            "first_data_row_index": 1,
            "name_col": 1,
            "id_col": 2,
        },
        header_candidates=[],
        signature_candidates=[],
        collisions=[
            {
                "field": "subject",
                "candidates": [
                    {"cell_type": "docx_table", "target": (0, 2, 1), "confidence": 0.85},
                    {"cell_type": "docx_table", "target": (0, 3, 1), "confidence": 0.85},
                ],
            }
        ],
        metadata={},
    )
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "Ambiguous template binding for field 'subject'" in str(exc_info.value)


def test_e4_missing_roster_name_column(tmp_path):
    """E4: Missing Roster Name Column raises TemplateError."""
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.docx"),
        profile_id="academic_docx",
        fingerprint="dummy_fp",
        roster_candidate={
            "table_index": 1,
            "first_data_row_index": 1,
            "name_col": None,
            "id_col": 2,
            "has_split_names": False,
        },
        header_candidates=[
            {
                "field": "instructor",
                "cell_type": "docx_table",
                "target": (0, 0, 1),
                "confidence": 1.0,
            }
        ],
        signature_candidates=[],
        collisions=[],
        metadata={},
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "Roster binding requires name_col or split names" in str(exc_info.value)


def test_e5_missing_student_id_column(tmp_path):
    """E5: Missing Student ID Column raises TemplateError."""
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.docx"),
        profile_id="academic_docx",
        fingerprint="dummy_fp",
        roster_candidate={
            "table_index": 1,
            "first_data_row_index": 1,
            "name_col": 1,
            "id_col": None,
        },
        header_candidates=[
            {
                "field": "instructor",
                "cell_type": "docx_table",
                "target": (0, 0, 1),
                "confidence": 1.0,
            }
        ],
        signature_candidates=[],
        collisions=[],
        metadata={},
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "Roster binding requires id_col" in str(exc_info.value)


def test_e5_physical_docx_missing_student_id_column(tmp_path):
    """E5: Physical DOCX template with roster table missing Student ID column raises TemplateError."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "template_syllabus.docx")
    mut_path = str(tmp_path / "missing_id_col.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    # In table 1 (roster), replace 'Student Number' header with 'Remarks'
    roster_tbl = doc.tables[1]
    roster_tbl.rows[0].cells[1].text = "Remarks"
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    with pytest.raises(TemplateError) as exc_info:
        resolver.resolve(mut_path, "academic_docx")
    assert "id_col" in str(exc_info.value).lower() or "roster" in str(exc_info.value).lower()


def test_e6_missing_roster_table(tmp_path):
    """E6: Missing required roster table on an academic profile raises TemplateError."""
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.docx"),
        profile_id="academic_docx",
        fingerprint="dummy_fp",
        roster_candidate=None,
        header_candidates=[
            {
                "field": "instructor",
                "cell_type": "docx_table",
                "target": (0, 0, 1),
                "confidence": 1.0,
            }
        ],
        signature_candidates=[],
        collisions=[],
        metadata={},
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "strictly requires a student roster table" in str(exc_info.value)


def test_e7_multiple_ambiguous_roster_tables(tmp_path):
    """E7: Multiple Ambiguous Roster Tables detection raises TemplateError during inspection/validation."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_docx = os.path.join(repo_root, "templates", "template_syllabus.docx")
    mut_docx = str(tmp_path / "two_rosters.docx")
    shutil.copy2(src_docx, mut_docx)

    doc = docx.Document(mut_docx)
    # Clone the roster table to create two duplicate, equally scoring roster tables
    roster_tbl = doc.tables[1]
    new_tbl = doc.add_table(rows=len(roster_tbl.rows), cols=len(roster_tbl.columns))
    for r_idx, row in enumerate(roster_tbl.rows):
        for c_idx, cell in enumerate(row.cells):
            new_tbl.rows[r_idx].cells[c_idx].text = cell.text
    doc.save(mut_docx)

    inspector = DocxTemplateInspector()
    with pytest.raises(TemplateError) as exc_info:
        inspector.inspect(mut_docx, "academic_docx")
    assert "Multiple candidate roster tables detected" in str(exc_info.value)


def test_e8_missing_mandatory_worksheet_or_invalid_capacity(tmp_path):
    """E8: Missing mandatory worksheet or invalid capacity raises TemplateError."""
    # 1. Missing required worksheet "Grading Sheet"
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_xlsx = os.path.join(repo_root, "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
    mut_xlsx = str(tmp_path / "no_grading_sheet.xlsx")
    shutil.copy2(src_xlsx, mut_xlsx)

    wb = openpyxl.load_workbook(mut_xlsx)
    del wb["Grading Sheet"]
    wb.save(mut_xlsx)

    inspector = XlsxTemplateInspector()
    with pytest.raises(TemplateError) as exc_info:
        inspector.inspect(mut_xlsx, "grade_sheet_xlsx")
    assert "missing required 'grading sheet' worksheet" in str(exc_info.value).lower()

    # 2. Invalid capacity_limit <= 0 in candidate
    candidate = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy.xlsx"),
        profile_id="grade_sheet_xlsx",
        fingerprint="dummy_fp",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 11,
            "name_col": 2,
            "id_col": 3,
            "capacity_limit": 0,  # Invalid: must be > 0
        },
        header_candidates=[
            {
                "field": "instructor",
                "cell_type": "xlsx_cell",
                "target": "M4",
                "confidence": 1.0,
            }
        ],
        signature_candidates=[],
        collisions=[],
        metadata={},
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_GRADE_SHEET_XLSX)
    assert "requires capacity_limit > 0" in str(exc_info.value)


def test_e9_stale_persisted_recipe_invalidation(tmp_path):
    """E9: Stale Persisted Recipe Invalidation.
    Modifying a template file on disk alters its SHA-256 fingerprint, triggering
    automatic cache invalidation and re-inspection/re-validation upon resolution."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_docx = os.path.join(repo_root, "templates", "template_syllabus.docx")
    mut_docx = str(tmp_path / "stale_test.docx")
    shutil.copy2(src_docx, mut_docx)

    resolver = TemplateRecipeResolver.get_instance()
    # 1. First resolution: caches recipe with original fingerprint
    recipe1 = resolver.resolve(mut_docx, "academic_docx")
    assert recipe1.fingerprint is not None
    fp1 = recipe1.fingerprint

    # 2. Modify template on disk (e.g. append a paragraph)
    doc = docx.Document(mut_docx)
    doc.add_paragraph("Extra modification to change SHA-256 fingerprint")
    doc.save(mut_docx)

    # 3. Resolve again: resolver detects fingerprint mismatch, invalidates cache,
    # re-inspects, re-validates, and returns a fresh ValidatedTemplateRecipe
    recipe2 = resolver.resolve(mut_docx, "academic_docx")
    assert recipe2.fingerprint is not None
    fp2 = recipe2.fingerprint

    assert fp1 != fp2, "Fingerprint must have changed after file modification"
    assert recipe2.template_path == os.path.abspath(mut_docx)
    assert recipe2.verified_safe is True


def test_e10_legacy_and_unsupported_schema_rejection():
    """E10: Legacy & Unsupported Schema Rejection.
    Rejects schema_version != 2 (missing, v1, or future versions) and rejects external construction tokens."""
    # 1. Missing schema_version
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict({"profile_id": "academic_docx"})
    assert "Unsupported recipe schema_version: None" in str(exc_info.value)

    # 2. Legacy schema_version = 1
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict({"schema_version": 1, "profile_id": "academic_docx"})
    assert "Unsupported recipe schema_version: 1" in str(exc_info.value)

    # 3. Future schema_version = 3
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict({"schema_version": 3, "profile_id": "academic_docx"})
    assert "Unsupported recipe schema_version: 3" in str(exc_info.value)

    # 4. Externally supplied construction token is strictly rejected
    tampered_data = {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "profile_id": "academic_docx",
        "_construction_token": "malicious_token_attempt",
    }
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(tampered_data)
    assert "Externally supplied '_construction_token' is prohibited" in str(exc_info.value)

    # 5. Direct instantiation of ValidatedTemplateRecipe outside validator is forbidden
    from modules.models.recipe import ValidatedTemplateRecipe
    with pytest.raises(PermissionError) as exc_info:
        ValidatedTemplateRecipe(
            schema_version=RECIPE_SCHEMA_VERSION,
            profile_id="academic_docx",
            fingerprint="fake_fp",
            template_path="fake.docx",
            roster_binding=None,
            header_bindings={},
            signature_bindings={},
            metadata={},
            verified_safe=True,
            _construction_token="unauthorized_sentinel",
        )
    assert "can only be constructed via RecipeValidator.validate()" in str(exc_info.value)

    # 6. Direct instantiation of ValidatedAttendanceTemplateRecipe outside validator is forbidden
    with pytest.raises(PermissionError) as exc_info:
        ValidatedAttendanceTemplateRecipe(
            schema_version=RECIPE_SCHEMA_VERSION,
            profile_id="attendance_docx",
            fingerprint="fake_fp",
            template_path="fake.docx",
            info_binding=AttendanceInfoBinding(0, {}),
            matrix_binding=AttendanceMatrixBinding(1, 0, 1, 2, 0, 1, 2, 3, 3, ("lb", "lc", "r"), 4, 40),
            metadata={},
            verified_safe=True,
            _construction_token="unauthorized_sentinel",
        )
    assert "can only be constructed via RecipeValidator.validate()" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# Attendance Invalid-Template Tests (E11–E18) & Recipe Path Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

def test_e11_missing_attendance_matrix(tmp_path):
    """E11: Template missing required attendance matrix table raises TemplateError."""
    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy_att.docx"),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate={
            "table_index": 0,
            "bindings": {"course_code_title": (0, 1), "month_year": (0, 4)},
        },
        matrix_candidate=None,
        metadata={},
        collisions=[],
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ATTENDANCE_DOCX)
    assert "missing required attendance matrix table" in str(exc_info.value)


def test_e12_missing_student_name_or_number(tmp_path):
    """E12: Matrix table missing student name or student number column raises TemplateError."""
    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy_att.docx"),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate={
            "table_index": 0,
            "bindings": {"course_code_title": (0, 1)},
        },
        matrix_candidate={
            "table_index": 1,
            "name_col": 1,
            "id_col": None,  # Missing student number column
            "date_columns_start": 3,
            "template_session_capacity": 4,
            "student_template_row_index": 2,
        },
        metadata={},
        collisions=[],
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ATTENDANCE_DOCX)
    assert "missing student name or student number column" in str(exc_info.value)


def test_e13_missing_info_table(tmp_path):
    """E13: Template missing required information table raises TemplateError."""
    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy_att.docx"),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate=None,
        matrix_candidate={
            "table_index": 1,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "template_session_capacity": 4,
            "student_template_row_index": 2,
        },
        metadata={},
        collisions=[],
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ATTENDANCE_DOCX)
    assert "missing required information table" in str(exc_info.value)


def test_e14_ambiguous_attendance_matrices(tmp_path):
    """E14: Conflicting or ambiguous attendance matrix candidates raise AmbiguousTemplateError."""
    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy_att.docx"),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate={"table_index": 0, "bindings": {"course_code_title": (0, 1)}},
        matrix_candidate=None,
        metadata={},
        collisions=[
            {
                "type": "ambiguous_matrix_table",
                "candidates": [1, 2],
            }
        ],
    )
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ATTENDANCE_DOCX)
    assert "conflicting structural candidates" in str(exc_info.value)


def test_e15_ambiguous_date_session_structure(tmp_path):
    """E15: Conflicting or ambiguous date/session structure in template raises AmbiguousTemplateError."""
    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy_att.docx"),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate={"table_index": 0, "bindings": {"course_code_title": (0, 1)}},
        matrix_candidate={
            "table_index": 1,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "template_session_capacity": 4,
            "student_template_row_index": 2,
        },
        metadata={},
        collisions=[
            {
                "type": "ambiguous_date_structure",
                "candidates": [(1, 3), (1, 5)],
            }
        ],
    )
    with pytest.raises(AmbiguousTemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ATTENDANCE_DOCX)
    assert "conflicting structural candidates" in str(exc_info.value)


def test_e16_invalid_attendance_geometry(tmp_path):
    """E16: Matrix candidate with invalid geometry (negative columns, 0 capacity) raises TemplateError."""
    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "dummy_att.docx"),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate={"table_index": 0, "bindings": {"course_code_title": (0, 1)}},
        matrix_candidate={
            "table_index": 1,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": -1,  # Invalid
            "template_session_capacity": 0,  # Invalid
            "student_template_row_index": 2,
        },
        metadata={},
        collisions=[],
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(candidate, PROFILE_ATTENDANCE_DOCX)
    assert "invalid date columns start" in str(exc_info.value) or "invalid session capacity" in str(exc_info.value)


def test_e17_insufficient_generation_capacity(tmp_path):
    """E17: Requesting sessions that exceed printable width threshold (DATE_W < 25 pct) raises TemplateError."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmpl_path = os.path.join(repo_root, "attendance", "template lec.docx")
    assert os.path.exists(tmpl_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(tmpl_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)

    gen = AttendanceGenerator(tmpl_path, recipe)
    out_path = str(tmp_path / "out_e17.docx")

    # 12 months with 5 days a week -> over 250 dates, column width < 10 pct -> raises TemplateError
    all_months = list(range(1, 13))
    all_weekdays = [0, 1, 2, 3, 4]  # Mon-Fri
    with pytest.raises(TemplateError) as exc_info:
        gen.generate(
            output_path=out_path,
            course_code_title="COSC 100",
            class_schedule="08:00AM-09:00AM / Mon, Tue, Wed, Thu, Fri",
            semester_ay="1st Sem",
            room_assignment="CL1",
            instructor="Prof. Test",
            months=all_months,
            year=2026,
            weekdays=all_weekdays,
            students=[("Student A", "20261001")],
        )
    assert "Insufficient generation capacity" in str(exc_info.value)


def test_e18_wrong_profile_supplied_to_ordinary_docx(tmp_path):
    """E18: Supplying wrong profile to template fails closed with TemplateError."""
    # 1. Ordinary non-attendance candidate with attendance profile
    raw_cand = RawTemplateRecipeCandidate(
        template_path=str(tmp_path / "ordinary.docx"),
        profile_id="academic_docx",
        fingerprint="fp_ord",
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(raw_cand, profile=PROFILE_ATTENDANCE_DOCX)
    assert "fails profile 'attendance_docx'" in str(exc_info.value)

    # 2. Attendance candidate with non-attendance profile
    att_cand = RawAttendanceTemplateRecipeCandidate(
        template_path=str(tmp_path / "att.docx"),
        profile_id="attendance_docx",
        fingerprint="fp_att",
    )
    with pytest.raises(TemplateError) as exc_info:
        RecipeValidator.validate(att_cand, profile=PROFILE_ACADEMIC_DOCX)
    assert "cannot be validated against profile 'academic_docx'" in str(exc_info.value)


def test_direct_recipe_path_enforcement(tmp_path):
    """Requirement 15: Prove AttendanceGenerator rejects invalid recipes,
    and generate_attendance_for_month cannot bypass recipe resolution."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmpl_path = os.path.join(repo_root, "attendance", "template lec.docx")
    assert os.path.exists(tmpl_path)

    # 1. AttendanceGenerator rejects arbitrary/invalid objects
    with pytest.raises(TypeError) as exc_info:
        AttendanceGenerator(tmpl_path, "not_a_recipe")
    assert "requires a ValidatedAttendanceTemplateRecipe" in str(exc_info.value)

    with pytest.raises(TypeError) as exc_info:
        AttendanceGenerator(tmpl_path, None)
    assert "requires a ValidatedAttendanceTemplateRecipe" in str(exc_info.value)

    # 2. AttendanceGenerator rejects non-attendance ValidatedTemplateRecipe
    resolver = TemplateRecipeResolver.get_instance()
    syl_path = os.path.join(repo_root, "templates", "template_syllabus.docx")
    syl_recipe = resolver.resolve(syl_path, profile_id="academic_docx")
    with pytest.raises(TypeError) as exc_info:
        AttendanceGenerator(tmpl_path, syl_recipe)
    assert "requires a ValidatedAttendanceTemplateRecipe" in str(exc_info.value)

    # 3. generate_attendance_for_month cannot bypass recipe resolution on nonexistent template
    out_path = str(tmp_path / "out_enforce.docx")
    with pytest.raises(FileNotFoundError):
        generate_attendance_for_month(
            template_path=str(tmp_path / "nonexistent_tmpl.docx"),
            output_path=out_path,
            info={"course": "CS", "subject": "Math"},
            students=[],
            month="DECEMBER",
            year=2026,
            class_day="Mon",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 1: Resolver Profile-Aware Dispatch Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_resolver_unknown_profile_rejection(tmp_path):
    """Task 1: Unknown profile IDs must fail closed with TemplateError."""
    resolver = TemplateRecipeResolver()
    dummy_file = tmp_path / "dummy.docx"
    dummy_file.write_text("dummy")

    # get_inspector must raise TemplateError on unknown profile
    with pytest.raises(TemplateError) as exc_info:
        resolver.get_inspector(str(dummy_file), profile_id="unknown_profile_xyz")
    assert "Unknown generator profile ID" in str(exc_info.value)

    # resolve_recipe must raise TemplateError on unknown profile
    with pytest.raises(TemplateError) as exc_info:
        resolver.resolve_recipe(str(dummy_file), profile_id="unknown_profile_xyz")
    assert "Unknown generator profile ID" in str(exc_info.value)


def test_resolver_canonical_attendance_dispatch(tmp_path):
    """Task 1: .docx + attendance_docx canonical dispatch selects AttendanceTemplateInspector."""
    resolver = TemplateRecipeResolver()
    dummy_file = tmp_path / "dummy.docx"
    dummy_file.write_text("dummy")

    inspector = resolver.get_inspector(str(dummy_file), profile_id="attendance_docx")
    assert isinstance(inspector, AttendanceTemplateInspector)

    # Subprofile alias "attendance" also maps to AttendanceTemplateInspector
    inspector2 = resolver.get_inspector(str(dummy_file), profile_id="attendance")
    assert isinstance(inspector2, AttendanceTemplateInspector)


def test_resolver_legacy_registration_does_not_override_canonical_attendance(tmp_path):
    """Task 1: Legacy extension-only registration cannot override canonical attendance dispatch."""
    resolver = TemplateRecipeResolver()
    dummy_file = tmp_path / "dummy.docx"
    dummy_file.write_text("dummy")

    class LegacyCustomDocxInspector:
        pass

    # Register legacy .docx override
    resolver.register_inspector(".docx", LegacyCustomDocxInspector)

    # For attendance_docx, legacy override MUST NOT take precedence over canonical inspector
    attendance_insp = resolver.get_inspector(str(dummy_file), profile_id="attendance_docx")
    assert isinstance(attendance_insp, AttendanceTemplateInspector)
    assert not isinstance(attendance_insp, LegacyCustomDocxInspector)


def test_resolver_exact_profile_registration_override(tmp_path):
    """Task 1: Exact (extension, profile_id) registration overrides canonical mapping when intentional."""
    resolver = TemplateRecipeResolver()
    dummy_file = tmp_path / "dummy.docx"
    dummy_file.write_text("dummy")

    class CustomAttendanceInspector:
        pass

    resolver.register_profile_inspector(".docx", "attendance_docx", CustomAttendanceInspector)
    insp = resolver.get_inspector(str(dummy_file), profile_id="attendance_docx")
    assert isinstance(insp, CustomAttendanceInspector)


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 2: validate_dict() Attendance Validation & Profile Security Tests
# ═══════════════════════════════════════════════════════════════════════════════

VALID_ATTENDANCE_DICT = {
    "schema_version": RECIPE_SCHEMA_VERSION,
    "profile_id": "attendance_docx",
    "fingerprint": "test_fp",
    "template_path": "test.docx",
    "info_binding": {
        "table_index": 0,
        "row_cell_counts": [2, 2],
        "bindings": {"course_code_title": [0, 1], "instructor": [1, 1]},
    },
    "matrix_binding": {
        "table_index": 1,
        "header_row0_index": 0,
        "header_row1_index": 1,
        "student_template_row_index": 2,
        "no_col": 0,
        "name_col": 1,
        "id_col": 2,
        "date_columns_start": 3,
        "summary_columns_count": 3,
        "summary_column_names": ["lb", "lc", "r"],
        "template_session_capacity": 4,
        "template_student_row_capacity": 40,
        "matrix_row_count": 5,
        "row0_cell_count": 8,
        "row1_cell_count": 10,
        "student_row_cell_count": 10,
    },
    "metadata": {"output_folder": "Attendance"},
}

VALID_ACADEMIC_DICT = {
    "schema_version": RECIPE_SCHEMA_VERSION,
    "profile_id": "academic_docx",
    "fingerprint": "test_fp",
    "template_path": "test.docx",
    "header_bindings": {
        "instructor": {
            "cell_type": "docx_table",
            "target": [0, 0, 1],
            "field": "instructor",
            "confidence": 1.0,
        }
    },
    "signature_bindings": {},
    "metadata": {"output_folder": "CEIT_Forms"},
}


def test_validate_dict_attendance_missing_info():
    """Task 2: Deserialized attendance recipe missing info_binding raises InvalidRecipeError."""
    bad_data = dict(VALID_ATTENDANCE_DICT)
    bad_data.pop("info_binding")
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(bad_data, profile="attendance_docx")
    assert "attendance serialized recipe" in str(exc_info.value) or "info_binding" in str(exc_info.value)


def test_validate_dict_attendance_missing_matrix():
    """Task 2: Deserialized attendance recipe missing matrix_binding raises InvalidRecipeError."""
    bad_data = dict(VALID_ATTENDANCE_DICT)
    bad_data.pop("matrix_binding")
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(bad_data, profile="attendance_docx")
    assert "attendance serialized recipe" in str(exc_info.value) or "matrix_binding" in str(exc_info.value)


def test_validate_dict_attendance_negative_date_start():
    """Task 2: Deserialized attendance recipe with negative date_columns_start raises InvalidRecipeError."""
    bad_data = copy.deepcopy(VALID_ATTENDANCE_DICT)
    bad_data["matrix_binding"]["date_columns_start"] = -1
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(bad_data, profile="attendance_docx")
    assert "invalid date_columns_start" in str(exc_info.value)


def test_validate_dict_attendance_zero_session_capacity():
    """Task 2: Deserialized attendance recipe with zero session capacity raises InvalidRecipeError."""
    bad_data = copy.deepcopy(VALID_ATTENDANCE_DICT)
    bad_data["matrix_binding"]["template_session_capacity"] = 0
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(bad_data, profile="attendance_docx")
    assert "template_session_capacity must be an integer > 0" in str(exc_info.value)


def test_validate_dict_attendance_invalid_student_row():
    """Task 2: Deserialized attendance recipe with negative student_template_row_index raises InvalidRecipeError."""
    bad_data = copy.deepcopy(VALID_ATTENDANCE_DICT)
    bad_data["matrix_binding"]["student_template_row_index"] = -1
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(bad_data, profile="attendance_docx")
    assert "invalid student_template_row_index" in str(exc_info.value)


def test_validate_dict_attendance_with_academic_profile():
    """Task 2: Supplying attendance serialized data with academic profile raises InvalidRecipeError."""
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(VALID_ATTENDANCE_DICT, profile="academic_docx")
    assert "Attendance data supplied with non-attendance profile" in str(exc_info.value)


def test_validate_dict_academic_with_attendance_profile():
    """Task 2: Supplying academic serialized data with attendance profile raises InvalidRecipeError."""
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(VALID_ACADEMIC_DICT, profile="attendance_docx")
    assert "Academic data supplied with attendance profile" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 5: Attendance Capacity Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_attendance_capacity_below_template_capacity(tmp_path):
    """Task 5: Generating with sessions below template capacity succeeds."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_cap_below.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    # Template has 4 date columns capacity
    assert recipe.matrix_binding.template_session_capacity == 4

    out_path = str(tmp_path / "out_below.docx")
    # Request 3 sessions (3 dates in month)
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=[("STUDENT 1", "20230001")],
        start_bound=(12, 1),
        end_bound=(12, 22),  # 3 Mondays: Dec 7, 14, 21
    )
    assert os.path.exists(out_path)


def test_attendance_capacity_exactly_at_template_capacity(tmp_path):
    """Task 5: Generating with sessions exactly equal to template capacity succeeds."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_cap_exact.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert recipe.matrix_binding.template_session_capacity == 4

    out_path = str(tmp_path / "out_exact.docx")
    # Dec 2026 has 4 Mondays: 7, 14, 21, 28
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=[("STUDENT 1", "20230001")],
    )
    assert os.path.exists(out_path)


def test_attendance_capacity_above_template_capacity_legal_expansion(tmp_path):
    """Task 5: Generating with sessions above template capacity legally expands when DATE_W >= 25."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_cap_expand.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert recipe.matrix_binding.template_session_capacity == 4

    out_path = str(tmp_path / "out_expand.docx")
    # Request 8 sessions (e.g. Mon & Thu in Dec 2026 = 8 sessions). DATE_W = 2423 // 8 = 302 >= 25.
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-10:00AM / Mon, Thu",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0, 3],
        students=[("STUDENT 1", "20230001")],
    )
    assert os.path.exists(out_path)
    out_doc = docx.Document(out_path)
    # Output table must have expanded date columns to accommodate 10 sessions (5 weeks * 2 days)
    r1 = out_doc.tables[1].rows[1]
    # date columns are between date_columns_start (col 3) and summary columns (last 3)
    num_date_cols = len(r1.cells) - 3 - 3
    assert num_date_cols == 10
    assert num_date_cols > recipe.matrix_binding.template_session_capacity


def test_attendance_capacity_above_printable_width_threshold_fails(tmp_path):
    """Task 5: Generating with required sessions exceeding printable width (DATE_W < 25) fails closed."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_cap_unprintable.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")

    out_path = str(tmp_path / "out_unprintable.docx")
    # Request 7 days a week for 6 months (massive session count, DATE_W < 25)
    with pytest.raises(TemplateError) as exc_info:
        AttendanceGenerator(mut_path, recipe).generate(
            output_path=out_path,
            course_code_title="COSC 101",
            class_schedule="08:00AM-10:00AM / Mon, Tue, Wed, Thu, Fri, Sat, Sun",
            semester_ay="1st Sem",
            room_assignment="CL3",
            instructor="DR. DELA CRUZ",
            months=[1, 2, 3, 4, 5, 6],
            year=2026,
            weekdays=[0, 1, 2, 3, 4, 5, 6],
            students=[("STUDENT 1", "20230001")],
        )
    assert "exceeds printable page width capacity" in str(exc_info.value)


def test_attendance_student_count_below_template_minimum(tmp_path):
    """Task 5: When student count is below generator minimum (40), exactly 40 rows are rendered."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_stu_min.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")

    out_path = str(tmp_path / "out_stu_min.docx")
    # 2 students
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=[("STUDENT 1", "20230001"), ("STUDENT 2", "20230002")],
    )
    out_doc = docx.Document(out_path)
    # 2 header rows + 40 student rows = 42 rows
    assert len(out_doc.tables[1].rows) == 42


def test_attendance_student_count_above_template_capacity(tmp_path):
    """Task 5: When student count exceeds template capacity (40), renders all students without truncation."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_stu_max.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")

    out_path = str(tmp_path / "out_stu_max.docx")
    # 45 students
    many_students = [(f"STUDENT {i}", f"2023{i:04d}") for i in range(1, 46)]
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=many_students,
    )
    out_doc = docx.Document(out_path)
    # 2 header rows + 45 student rows = 47 rows
    assert len(out_doc.tables[1].rows) == 47


def test_validate_dict_attendance_summary_column_widths_validation():
    """Verify validate_dict enforces strict validation on summary_column_widths."""
    from modules.parsers.recipe_validator import RecipeValidator, InvalidRecipeError

    valid_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "attendance/template lec.docx",
        "template_hash": "sha256:dummy",
        "detected_profile": "attendance_docx",
        "info_binding": {
            "table_index": 0,
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "summary_column_widths": [212, 208, 133],
        },
    }

    # 1. Valid dict succeeds
    recipe = RecipeValidator.validate_dict(valid_dict)
    assert recipe.matrix_binding.summary_column_widths == (212, 208, 133)

    # 2. Length mismatch fails
    bad_dict = copy.deepcopy(valid_dict)
    bad_dict["matrix_binding"]["summary_column_widths"] = [212, 208]
    with pytest.raises(InvalidRecipeError, match="must match summary_column_names"):
        RecipeValidator.validate_dict(bad_dict)

    # 3. Non-positive width fails
    bad_dict = copy.deepcopy(valid_dict)
    bad_dict["matrix_binding"]["summary_column_widths"] = [212, -10, 133]
    with pytest.raises(InvalidRecipeError, match="contains invalid width"):
        RecipeValidator.validate_dict(bad_dict)

    # 4. Non-int width fails
    bad_dict = copy.deepcopy(valid_dict)
    bad_dict["matrix_binding"]["summary_column_widths"] = [212, "208", 133]
    with pytest.raises(InvalidRecipeError, match="contains invalid width"):
        RecipeValidator.validate_dict(bad_dict)


def test_serialized_attendance_out_of_range_week_template_cell_col_fails():
    """Verify out-of-range week_template_cell_col fails validation."""
    valid_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "dummy_nonexistent.docx",
        "info_binding": {
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "matrix_row_count": 5,
            "row0_cell_count": 5,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            "week_template_cell_col": 8,  # > row0_cell_count (5)
        },
    }
    with pytest.raises(InvalidRecipeError, match="week_template_cell_col .* out of range"):
        RecipeValidator.validate_dict(valid_dict)

    # Negative index fails
    neg_dict = copy.deepcopy(valid_dict)
    neg_dict["matrix_binding"]["week_template_cell_col"] = -1
    with pytest.raises(InvalidRecipeError, match="Invalid week_template_cell_col"):
        RecipeValidator.validate_dict(neg_dict)


def test_serialized_attendance_out_of_range_summary_header0_cell_col_fails():
    """Verify out-of-range summary_header0_cell_col fails validation."""
    valid_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "dummy_nonexistent.docx",
        "info_binding": {
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "matrix_row_count": 5,
            "row0_cell_count": 5,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            "summary_header0_cell_col": 9,  # > row0_cell_count (5)
        },
    }
    with pytest.raises(InvalidRecipeError, match="summary_header0_cell_col .* out of range"):
        RecipeValidator.validate_dict(valid_dict)


def test_serialized_attendance_out_of_range_date_template_cell_col_fails():
    """Verify out-of-range date_template_cell_col fails validation."""
    valid_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "dummy_nonexistent.docx",
        "info_binding": {
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "matrix_row_count": 5,
            "row0_cell_count": 5,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            "week_template_cell_col": 3,
            "summary_header0_cell_col": 4,
            "date_template_cell_col": 15,  # > row1_cell_count (10)
        },
    }
    with pytest.raises(InvalidRecipeError, match="date_template_cell_col .* out of range"):
        RecipeValidator.validate_dict(valid_dict)


def test_serialized_attendance_invalid_summary_source_indices_fail():
    """Verify invalid summary source indices fail validation (bounds, negative, duplicate, overlap)."""
    base_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "dummy_nonexistent.docx",
        "info_binding": {
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "matrix_row_count": 5,
            "row0_cell_count": 5,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            "week_template_cell_col": 3,
            "summary_header0_cell_col": 4,
            "date_template_cell_col": 3,
            "student_date_template_cell_col": 3,
        },
    }

    # 1. Out of range of row1
    d1 = copy.deepcopy(base_dict)
    d1["matrix_binding"]["summary_header1_cell_cols"] = [7, 8, 99]
    with pytest.raises(InvalidRecipeError, match="summary_header1_cell_cols index .* out of range"):
        RecipeValidator.validate_dict(d1)

    # 2. Negative index
    d2 = copy.deepcopy(base_dict)
    d2["matrix_binding"]["summary_header1_cell_cols"] = [7, -2, 9]
    with pytest.raises(InvalidRecipeError, match="Invalid non-negative summary_header1_cell_cols"):
        RecipeValidator.validate_dict(d2)

    # 3. Duplicate columns in summary
    d3 = copy.deepcopy(base_dict)
    d3["matrix_binding"]["summary_header1_cell_cols"] = [7, 8, 8]
    with pytest.raises(InvalidRecipeError, match="contain duplicate columns"):
        RecipeValidator.validate_dict(d3)

    # 4. Overlap with date columns (date cols are 3..6: 3, 4, 5, 6)
    d4 = copy.deepcopy(base_dict)
    d4["matrix_binding"]["summary_header1_cell_cols"] = [5, 7, 8]
    with pytest.raises(InvalidRecipeError, match="overlap with date columns"):
        RecipeValidator.validate_dict(d4)


def test_serialized_attendance_invalid_student_prototype_source_indices_fail():
    """Verify invalid student prototype source indices fail validation."""
    base_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "dummy_nonexistent.docx",
        "info_binding": {
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "matrix_row_count": 5,
            "row0_cell_count": 5,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            "week_template_cell_col": 3,
            "summary_header0_cell_col": 4,
            "date_template_cell_col": 3,
            "student_date_template_cell_col": 3,
            "summary_header1_cell_cols": [7, 8, 9],
        },
    }

    # 1. Out of range student_summary_cell_cols
    d1 = copy.deepcopy(base_dict)
    d1["matrix_binding"]["student_summary_cell_cols"] = [7, 8, 42]
    with pytest.raises(InvalidRecipeError, match="student_summary_cell_cols index .* out of range"):
        RecipeValidator.validate_dict(d1)

    # 2. Out of range student_date_template_cell_col
    d2 = copy.deepcopy(base_dict)
    d2["matrix_binding"]["student_date_template_cell_col"] = 15
    with pytest.raises(InvalidRecipeError, match="student_date_template_cell_col .* out of range"):
        RecipeValidator.validate_dict(d2)

    # 3. Out of range name_col
    d3 = copy.deepcopy(base_dict)
    d3["matrix_binding"]["name_col"] = 25
    with pytest.raises(InvalidRecipeError, match="name_col .* out of range"):
        RecipeValidator.validate_dict(d3)


def test_serialized_attendance_mismatched_summary_array_lengths_fail():
    """Verify mismatched summary array lengths fail validation."""
    base_dict = {
        "schema_version": 2,
        "profile_id": "attendance_docx",
        "template_path": "dummy_nonexistent.docx",
        "info_binding": {
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"course_code_title": [0, 1]},
        },
        "matrix_binding": {
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "matrix_row_count": 5,
            "row0_cell_count": 5,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            "summary_column_indices": [7, 8, 9],
            "summary_header1_cell_cols": [7, 8, 9],
            "student_summary_cell_cols": [7, 8, 9],
            "summary_column_widths": [212, 208, 133],
        },
    }

    # 1. summary_header1_cell_cols length mismatch
    d1 = copy.deepcopy(base_dict)
    d1["matrix_binding"]["summary_header1_cell_cols"] = [7, 8]
    with pytest.raises(InvalidRecipeError, match="Summary header1 cell cols length"):
        RecipeValidator.validate_dict(d1)

    # 2. student_summary_cell_cols length mismatch
    d2 = copy.deepcopy(base_dict)
    d2["matrix_binding"]["student_summary_cell_cols"] = [7, 8, 9, 10]
    with pytest.raises(InvalidRecipeError, match="Student summary cell cols length"):
        RecipeValidator.validate_dict(d2)

    # 3. summary_column_indices length mismatch
    d3 = copy.deepcopy(base_dict)
    d3["matrix_binding"]["summary_column_indices"] = [7]
    with pytest.raises(InvalidRecipeError, match="Summary column indices length"):
        RecipeValidator.validate_dict(d3)


def test_attendance_generator_never_performs_fallback_substitution(tmp_path):
    """Verify AttendanceGenerator raises TemplateError on invalid coordinates and NEVER substitutes date template."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "template.docx")
    shutil.copy2(src, mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    valid_recipe = resolver.resolve(mut_path, profile_id="attendance_docx")

    # Construct invalid recipe dictionary with out-of-bounds summary_header1_cell_cols
    recipe_dict = valid_recipe.to_dict()
    recipe_dict["matrix_binding"]["summary_header1_cell_cols"] = [7, 8, 99]

    # If bypassed or constructed with out-of-range coordinate directly:
    from modules.models.recipe import _PRIVATE_CONSTRUCTION_SENTINEL
    invalid_mb = AttendanceMatrixBinding(
        table_index=valid_recipe.matrix_binding.table_index,
        header_row0_index=valid_recipe.matrix_binding.header_row0_index,
        header_row1_index=valid_recipe.matrix_binding.header_row1_index,
        student_template_row_index=valid_recipe.matrix_binding.student_template_row_index,
        no_col=valid_recipe.matrix_binding.no_col,
        name_col=valid_recipe.matrix_binding.name_col,
        id_col=valid_recipe.matrix_binding.id_col,
        date_columns_start=valid_recipe.matrix_binding.date_columns_start,
        summary_columns_count=valid_recipe.matrix_binding.summary_columns_count,
        summary_column_names=valid_recipe.matrix_binding.summary_column_names,
        template_session_capacity=valid_recipe.matrix_binding.template_session_capacity,
        template_student_row_capacity=valid_recipe.matrix_binding.template_student_row_capacity,
        summary_header1_cell_cols=(7, 8, 99),  # Out of range of header row 1!
    )
    crafted_recipe = ValidatedAttendanceTemplateRecipe(
        schema_version=RECIPE_SCHEMA_VERSION,
        profile_id="attendance_docx",
        fingerprint=valid_recipe.fingerprint,
        template_path=valid_recipe.template_path,
        info_binding=valid_recipe.info_binding,
        matrix_binding=invalid_mb,
        metadata=dict(valid_recipe.metadata),
        verified_safe=True,
        _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
    )

    out_path = str(tmp_path / "out_should_fail.docx")
    gen = AttendanceGenerator(mut_path, crafted_recipe)
    with pytest.raises(TemplateError, match="Invalid summary_header1_cell_cols index 99 out of range"):
        gen.generate(
            output_path=out_path,
            course_code_title="COSC 101",
            class_schedule="08:00AM-11:00AM / Mon",
            semester_ay="1st Sem",
            room_assignment="CL3",
            instructor="DR. DELA CRUZ",
            months=[12],
            year=2026,
            weekdays=[0],
            students=[("STUDENT 1", "20230001")],
        )

    # Output file must NOT have been generated
    assert not os.path.exists(out_path)


# ═══════════════════════════════════════════════════════════════════════════════
# AMENDMENT 1 & 2: Structural Geometry & Serialized Profile Integrity Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_validate_attendance_physical_info_table_index_out_of_range(tmp_path):
    """Amendment 1: Physical info table index out of range fails closed with InvalidRecipeError."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "template.docx")
    shutil.copy2(src, mut_path)

    raw_cand = AttendanceTemplateInspector().inspect(mut_path, PROFILE_ATTENDANCE_DOCX)
    raw_cand.info_candidate["table_index"] = 99

    with pytest.raises(InvalidRecipeError, match="Info table index 99 out of range"):
        RecipeValidator.validate(raw_cand, profile=PROFILE_ATTENDANCE_DOCX)


def test_validate_attendance_physical_info_binding_row_out_of_range(tmp_path):
    """Amendment 1: Physical info binding row index out of range fails closed with InvalidRecipeError."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "template.docx")
    shutil.copy2(src, mut_path)

    raw_cand = AttendanceTemplateInspector().inspect(mut_path, PROFILE_ATTENDANCE_DOCX)
    raw_cand.info_candidate["bindings"]["course_code_title"] = [999, 0]

    with pytest.raises(InvalidRecipeError, match=r"row index 999.*out of range"):
        RecipeValidator.validate(raw_cand, profile=PROFILE_ATTENDANCE_DOCX)


def test_validate_attendance_physical_info_binding_column_out_of_range(tmp_path):
    """Amendment 1: Physical info binding column index out of range fails closed with InvalidRecipeError."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "template.docx")
    shutil.copy2(src, mut_path)

    raw_cand = AttendanceTemplateInspector().inspect(mut_path, PROFILE_ATTENDANCE_DOCX)
    raw_cand.info_candidate["bindings"]["course_code_title"] = [0, 999]

    with pytest.raises(InvalidRecipeError, match=r"column index 999.*out of range"):
        RecipeValidator.validate(raw_cand, profile=PROFILE_ATTENDANCE_DOCX)


def test_serialized_attendance_info_binding_row_out_of_range():
    """Amendment 1: Serialized info binding row index out of range fails closed with InvalidRecipeError."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["template_path"] = "dummy_nonexistent.docx"
    d["info_binding"]["row_cell_counts"] = [2, 2]
    d["info_binding"]["bindings"]["course_code_title"] = [5, 0]
    with pytest.raises(InvalidRecipeError, match=r"row index 5.*out of range"):
        RecipeValidator.validate_dict(d)


def test_serialized_attendance_info_binding_column_out_of_range():
    """Amendment 1: Serialized info binding column index out of range fails closed with InvalidRecipeError."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["template_path"] = "dummy_nonexistent.docx"
    d["info_binding"]["row_cell_counts"] = [2, 2]
    d["info_binding"]["bindings"]["course_code_title"] = [0, 5]
    with pytest.raises(InvalidRecipeError, match=r"column index 5.*out of range"):
        RecipeValidator.validate_dict(d)


def test_serialized_attendance_missing_info_geometry_fails():
    """Amendment 1: Serialized attendance recipe missing row_cell_counts fails closed with InvalidRecipeError."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["template_path"] = "dummy_nonexistent.docx"
    d["info_binding"].pop("row_cell_counts", None)
    with pytest.raises(InvalidRecipeError, match="missing required 'row_cell_counts' in info_binding"):
        RecipeValidator.validate_dict(d)


def test_validate_dict_attendance_conflicting_profile_id():
    """Amendment 2: Conflicting serialized profile_id raises InvalidRecipeError."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["profile_id"] = "academic_docx"
    with pytest.raises(InvalidRecipeError, match="Profile mismatch.*conflicts with requested profile"):
        RecipeValidator.validate_dict(d, profile=PROFILE_ATTENDANCE_DOCX)


def test_validate_dict_attendance_alias_accepted():
    """Amendment 2: Valid serialized profile alias 'attendance' resolves to canonical profile."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["profile_id"] = "attendance"
    recipe = RecipeValidator.validate_dict(d, profile=PROFILE_ATTENDANCE_DOCX)
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.profile_id == "attendance_docx"


def test_validate_dict_attendance_alias_canonicalized():
    """Amendment 2: Serialized profile alias with case/whitespace is accepted and canonicalized."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["profile_id"] = "  ATTENDANCE  "
    recipe = RecipeValidator.validate_dict(d, profile=PROFILE_ATTENDANCE_DOCX)
    assert recipe.profile_id == "attendance_docx"


def test_validate_dict_unknown_serialized_profile_id_fails():
    """Amendment 2: Unknown serialized profile_id raises InvalidRecipeError."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["profile_id"] = "unknown_profile_xyz"
    with pytest.raises(InvalidRecipeError, match="Unknown serialized profile ID"):
        RecipeValidator.validate_dict(d, profile=PROFILE_ATTENDANCE_DOCX)


def test_validate_dict_non_string_serialized_profile_id_fails():
    """Amendment 2: Non-string serialized profile_id raises InvalidRecipeError."""
    d = copy.deepcopy(VALID_ATTENDANCE_DICT)
    d["profile_id"] = 12345
    with pytest.raises(InvalidRecipeError, match="Serialized recipe profile_id must be a string"):
        RecipeValidator.validate_dict(d, profile=PROFILE_ATTENDANCE_DOCX)


def test_validate_attendance_corrupt_physical_docx_fails(tmp_path):
    """Test A: Physical inspection fails closed on a corrupt physical file."""
    corrupt_docx = tmp_path / "corrupt.docx"
    corrupt_docx.write_bytes(b"NOT_A_VALID_DOCX_OR_ZIP")

    candidate = RawAttendanceTemplateRecipeCandidate(
        template_path=str(corrupt_docx),
        profile_id="attendance_docx",
        fingerprint="dummy_fp",
        info_candidate={
            "table_index": 0,
            "bindings": {"course_code_title": [0, 1]},
            "row_cell_counts": (2, 2),
        },
        matrix_candidate={
            "table_index": 1,
            "header_row0_index": 0,
            "header_row1_index": 1,
            "student_template_row_index": 2,
            "no_col": 0,
            "name_col": 1,
            "id_col": 2,
            "date_columns_start": 3,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "template_session_capacity": 4,
            "template_student_row_capacity": 40,
            "summary_column_widths": [212, 208, 133],
            "matrix_row_count": 5,
            "row0_cell_count": 8,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
        },
    )

    with pytest.raises((TemplateError, InvalidRecipeError)):
        RecipeValidator.validate(candidate, profile=PROFILE_ATTENDANCE_DOCX)


def test_validate_attendance_physical_geometry_out_of_bounds_fails(tmp_path):
    """Test B: Valid physical DOCX with out-of-bounds structural matrix geometry fails closed."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "valid_template.docx")
    shutil.copy2(src, mut_path)

    raw_cand = AttendanceTemplateInspector().inspect(mut_path, PROFILE_ATTENDANCE_DOCX)
    raw_cand.matrix_candidate["header_row0_index"] = 999

    recipe = None
    with pytest.raises(InvalidRecipeError, match="header_row0_index .* out of range"):
        recipe = RecipeValidator.validate(raw_cand, profile=PROFILE_ATTENDANCE_DOCX)

    # Invariant: NO ValidatedAttendanceTemplateRecipe returned
    assert recipe is None

    # NO generator execution possible with invalid physical structure
    out_path = str(tmp_path / "should_not_exist.docx")
    assert not os.path.exists(out_path)



