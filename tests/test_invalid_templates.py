import os
import shutil
import tempfile
import docx
import openpyxl
import pytest

from modules.models.recipe import (
    RECIPE_SCHEMA_VERSION,
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    RawTemplateRecipeCandidate,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    PROFILE_REGISTRY,
)
from modules.parsers.recipe_validator import RecipeValidator
from modules.parsers.template_inspector import DocxTemplateInspector, XlsxTemplateInspector
from modules.generators.ceit_gen import GeneratorFactory
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
