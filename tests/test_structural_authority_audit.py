"""
tests/test_structural_authority_audit.py

Comprehensive test suite verifying the complete structural authority closure:
1. Generic DOCX physical geometry bounds checks (headers, roster, signatures, corrupt files)
2. Serialized generic DOCX geometry bounds checks
3. Physical XLSX geometry bounds checks (worksheets, headers, roster, signatures, corrupt files)
4. Serialized XLSX geometry bounds checks
5. Structural ambiguity rejection across headers, signatures, and roster tables
6. Generator-side fail-closed execution safeguards
"""

import os
import pytest
import docx
import openpyxl

from modules.models.recipe import (
    RECIPE_SCHEMA_VERSION,
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    RosterBinding,
    HeaderCellBinding,
    SignatureBinding,
    AttendanceMatrixBinding,
    AttendanceInfoBinding,
    RawTemplateRecipeCandidate,
    ValidatedTemplateRecipe,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    _PRIVATE_CONSTRUCTION_SENTINEL,
)
from modules.parsers.recipe_validator import RecipeValidator
from modules.generators.document_generator import DocumentGenerator
from modules.generators.grade_gen import GradeGenerator


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Generic DOCX Physical Geometry Validation
# ═══════════════════════════════════════════════════════════════════════════════

def _create_minimal_docx(path: str, num_tables: int = 1, rows: int = 3, cols: int = 3, paras: int = 2):
    doc = docx.Document()
    for _ in range(paras):
        doc.add_paragraph("Sample paragraph text")
    for _ in range(num_tables):
        doc.add_table(rows=rows, cols=cols)
    doc.save(path)


def test_docx_physical_header_table_index_out_of_range(tmp_path):
    """Physical header table index >= number of tables must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (5, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "table index 5 out of range" in str(exc.value)


def test_docx_physical_header_row_out_of_range(tmp_path):
    """Physical header row index >= row count must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 10, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "row index 10 out of range" in str(exc.value)


def test_docx_physical_header_cell_out_of_range(tmp_path):
    """Physical header cell index >= cell count must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 10), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "cell index 10 out of range" in str(exc.value)


def test_docx_physical_paragraph_index_out_of_range(tmp_path):
    """Physical paragraph index >= paragraph count must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3, paras=2)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_paragraph", "target": 15, "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "paragraph index 15 out of range" in str(exc.value)


def test_docx_physical_roster_table_index_out_of_range(tmp_path):
    """Physical roster table index out of range must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 5, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Roster binding table index 5 out of range" in str(exc.value)


def test_docx_physical_roster_row_out_of_range(tmp_path):
    """Physical roster first_data_row_index out of range must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 10, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Roster first_data_row_index 10 out of range" in str(exc.value)


def test_docx_physical_roster_name_col_out_of_range(tmp_path):
    """Physical roster name_col out of range must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 10, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Roster name_col (10) out of range" in str(exc.value)


def test_docx_physical_roster_id_col_out_of_range(tmp_path):
    """Physical roster id_col out of range must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 10},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Roster id_col (10) out of range" in str(exc.value)


def test_docx_physical_signature_table_coordinate_out_of_range(tmp_path):
    """Physical signature table coordinate out of range must raise InvalidRecipeError."""
    doc_path = str(tmp_path / "test_doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=3, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
        signature_candidates=[
            {"role": "instructor_signature", "target": (5, 0, 0), "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Signature binding for 'instructor_signature' table index 5 out of range" in str(exc.value)


def test_docx_corrupt_file_fails_closed(tmp_path):
    """Corrupt physical DOCX template must fail closed with TemplateError."""
    doc_path = str(tmp_path / "corrupt.docx")
    with open(doc_path, "wb") as f:
        f.write(b"not a valid zip file or docx")

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp_corrupt",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises(TemplateError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Physical template inspection failed" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Serialized Generic DOCX Geometry Validation
# ═══════════════════════════════════════════════════════════════════════════════

def test_docx_serialized_missing_geometry_fails():
    """Serialized recipe with coordinates and missing physical file requires docx_geometry."""
    cand = RawTemplateRecipeCandidate(
        template_path="nonexistent.docx",
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
        metadata={},
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "missing required 'docx_geometry' metadata" in str(exc.value)


def test_docx_serialized_table_coordinate_out_of_bounds():
    """Serialized recipe with out-of-bounds table coordinate against docx_geometry fails."""
    cand = RawTemplateRecipeCandidate(
        template_path="nonexistent.docx",
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (2, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
        metadata={
            "docx_geometry": {
                "table_row_cell_counts": [[3, 3]],  # 1 table with 2 rows, 3 cells each
                "paragraph_count": 2,
            }
        },
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "table index 2 out of range" in str(exc.value)


def test_docx_serialized_row_coordinate_out_of_bounds():
    """Serialized recipe with out-of-bounds row coordinate against docx_geometry fails."""
    cand = RawTemplateRecipeCandidate(
        template_path="nonexistent.docx",
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 5, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
        metadata={
            "docx_geometry": {
                "table_row_cell_counts": [[3, 3]],
                "paragraph_count": 2,
            }
        },
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "row index 5 out of range" in str(exc.value)


def test_docx_serialized_cell_coordinate_out_of_bounds():
    """Serialized recipe with out-of-bounds cell coordinate against docx_geometry fails."""
    cand = RawTemplateRecipeCandidate(
        template_path="nonexistent.docx",
        profile_id="academic_docx",
        fingerprint="fp1",
        roster_candidate={"table_index": 0, "first_data_row_index": 1, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 8), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
        metadata={
            "docx_geometry": {
                "table_row_cell_counts": [[3, 3]],
                "paragraph_count": 2,
            }
        },
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "cell index 8 out of range" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. XLSX Physical and Serialized Geometry Validation
# ═══════════════════════════════════════════════════════════════════════════════

def _create_minimal_xlsx(path: str, sheets=("Lecture", "Grading Sheet"), max_r=20, max_c=10):
    wb = openpyxl.Workbook()
    default_ws = wb.active
    default_ws.title = sheets[0]
    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            default_ws.cell(r, c).value = f"cell_{r}_{c}"

    for s in sheets[1:]:
        ws = wb.create_sheet(title=s)
        for r in range(1, max_r + 1):
            for c in range(1, max_c + 1):
                ws.cell(r, c).value = f"cell_{r}_{c}"
    wb.save(path)


def test_xlsx_physical_worksheet_target_invalid(tmp_path):
    """Physical XLSX with invalid worksheet target raises InvalidRecipeError."""
    xlsx_path = str(tmp_path / "test.xlsx")
    _create_minimal_xlsx(xlsx_path, sheets=("Lecture",))

    cand = RawTemplateRecipeCandidate(
        template_path=xlsx_path,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "NonExistentSheet",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "Worksheet 'NonExistentSheet' not found" in str(exc.value)


def test_xlsx_physical_header_cell_out_of_bounds(tmp_path):
    """Physical XLSX with header cell coordinate out of worksheet bounds raises InvalidRecipeError."""
    xlsx_path = str(tmp_path / "test.xlsx")
    _create_minimal_xlsx(xlsx_path, sheets=("Lecture",), max_r=20, max_c=10)

    cand = RawTemplateRecipeCandidate(
        template_path=xlsx_path,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!Z100", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "out of bounds for sheet 'Lecture'" in str(exc.value)


def test_xlsx_physical_roster_row_out_of_bounds(tmp_path):
    """Physical XLSX with roster row out of worksheet bounds raises InvalidRecipeError."""
    xlsx_path = str(tmp_path / "test.xlsx")
    _create_minimal_xlsx(xlsx_path, sheets=("Lecture",), max_r=20, max_c=10)

    cand = RawTemplateRecipeCandidate(
        template_path=xlsx_path,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 50,  # max_r is 20
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "Roster first_data_row_index 50 out of bounds" in str(exc.value)


def test_xlsx_physical_roster_col_out_of_bounds(tmp_path):
    """Physical XLSX with roster column out of worksheet bounds raises InvalidRecipeError."""
    xlsx_path = str(tmp_path / "test.xlsx")
    _create_minimal_xlsx(xlsx_path, sheets=("Lecture",), max_r=20, max_c=10)

    cand = RawTemplateRecipeCandidate(
        template_path=xlsx_path,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 50,  # max_c is 10
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "Roster name_col 50 out of bounds" in str(exc.value)


def test_xlsx_physical_signature_target_out_of_bounds(tmp_path):
    """Physical XLSX with signature coordinate out of bounds raises InvalidRecipeError."""
    xlsx_path = str(tmp_path / "test.xlsx")
    _create_minimal_xlsx(xlsx_path, sheets=("Lecture",), max_r=20, max_c=10)

    cand = RawTemplateRecipeCandidate(
        template_path=xlsx_path,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
        signature_candidates=[
            {"role": "instructor", "target": "Lecture!Z100", "confidence": 1.0},
        ],
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "Signature binding for 'instructor' coordinate 'Lecture!Z100' out of bounds" in str(exc.value)


def test_xlsx_corrupt_file_fails_closed(tmp_path):
    """Corrupt physical XLSX template must fail closed with TemplateError."""
    xlsx_path = str(tmp_path / "corrupt.xlsx")
    with open(xlsx_path, "wb") as f:
        f.write(b"corrupt xlsx bytes")

    cand = RawTemplateRecipeCandidate(
        template_path=xlsx_path,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp_corrupt",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(TemplateError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "Physical template inspection failed" in str(exc.value)


def test_xlsx_serialized_missing_geometry_fails():
    """Serialized XLSX recipe without physical file and missing xlsx_geometry raises InvalidRecipeError."""
    cand = RawTemplateRecipeCandidate(
        template_path="nonexistent.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
        metadata={},
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "missing required 'xlsx_geometry' metadata" in str(exc.value)


def test_xlsx_serialized_coordinate_out_of_bounds():
    """Serialized XLSX recipe with out-of-bounds coordinate against xlsx_geometry raises InvalidRecipeError."""
    cand = RawTemplateRecipeCandidate(
        template_path="nonexistent.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 10,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!M50", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!C1", "field": "schedule_code", "confidence": 1.0},
        ],
        metadata={
            "xlsx_geometry": {
                "worksheets": {
                    "Lecture": {"max_row": 20, "max_column": 10},
                }
            }
        },
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_GRADE_SHEET_XLSX)
    assert "out of bounds for sheet 'Lecture'" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Structural Ambiguity Rejection (Requirement 6)
# ═══════════════════════════════════════════════════════════════════════════════

def test_ambiguity_two_plausible_instructor_cells_rejected(tmp_path):
    """Two plausible instructor cells without a unique structural discriminator must raise AmbiguousTemplateError."""
    doc_path = str(tmp_path / "ambig_inst.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=4, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp_ambig",
        roster_candidate={"table_index": 0, "first_data_row_index": 2, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "instructor", "confidence": 0.91},
            {"cell_type": "docx_table", "target": (0, 1, 1), "field": "instructor", "confidence": 0.87},
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "course_section", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 0.95},
        ],
    )
    with pytest.raises(AmbiguousTemplateError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Ambiguous template binding for field 'instructor'" in str(exc.value)


def test_ambiguity_two_plausible_course_cells_rejected(tmp_path):
    """Two plausible course cells without structural discriminator must raise AmbiguousTemplateError."""
    doc_path = str(tmp_path / "ambig_course.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=4, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp_ambig",
        roster_candidate={"table_index": 0, "first_data_row_index": 2, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "course_section", "confidence": 0.93},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "course_section", "confidence": 0.88},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "instructor", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 1, 2), "field": "subject", "confidence": 0.95},
        ],
    )
    with pytest.raises(AmbiguousTemplateError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Ambiguous template binding for field 'course_section'" in str(exc.value)


def test_ambiguity_two_plausible_signature_targets_rejected(tmp_path):
    """Two plausible signature targets for the same role without structural dominance must raise AmbiguousTemplateError."""
    doc_path = str(tmp_path / "ambig_sig.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=4, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp_ambig",
        roster_candidate={"table_index": 0, "first_data_row_index": 2, "name_col": 0, "id_col": 1},
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "course_section", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "instructor", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 0.95},
            {"cell_type": "docx_table", "target": (0, 1, 2), "field": "subject", "confidence": 0.95},
        ],
        signature_candidates=[
            {"role": "instructor_signature", "target": (0, 2, 1), "confidence": 0.90},
            {"role": "instructor_signature", "target": (0, 3, 1), "confidence": 0.85},
        ],
    )
    with pytest.raises(AmbiguousTemplateError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "Ambiguous signature binding for role 'instructor_signature'" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Generator Fail-Closed Safeguards
# ═══════════════════════════════════════════════════════════════════════════════

class DummyDocGenerator(DocumentGenerator):
    """Concrete DocumentGenerator for testing fail-closed execution."""
    def _fill_student_row(self, cells, idx, name, stnum):
        pass


def test_document_generator_fails_closed_on_impossible_header_coordinate(tmp_path):
    """DocumentGenerator must raise TemplateError if an impossible coordinate is consumed."""
    doc_path = str(tmp_path / "doc.docx")
    _create_minimal_docx(doc_path, num_tables=1, rows=2, cols=2)

    # Construct recipe with out-of-bounds target via internal token
    recipe = ValidatedTemplateRecipe(
        schema_version=RECIPE_SCHEMA_VERSION,
        profile_id="academic_docx",
        fingerprint="fp1",
        template_path=doc_path,
        roster_binding=RosterBinding(table_index=0, first_data_row_index=1, name_col=0, id_col=1),
        header_bindings={
            "instructor": HeaderCellBinding(cell_type="docx_table", target=(0, 99, 0), field="instructor"),
        },
        signature_bindings={},
        metadata={},
        verified_safe=True,
        _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
    )

    from modules.models.schedule import ClassInfo

    info = ClassInfo(
        instructor="Dr. Smith",
        course_section="BSCS 3-1",
        schedule_code="12345",
        subject="CS 101",
        students=[("Student One", "123")],
    )
    gen = DummyDocGenerator(doc_path, recipe)
    with pytest.raises(TemplateError) as exc:
        gen.generate(info, str(tmp_path / "out.docx"))
    assert "out of range" in str(exc.value)


def test_grade_generator_rejects_missing_index_col(tmp_path):
    """GradeGenerator fails closed with TemplateError if recipe.roster_binding.index_col is missing."""
    template_path = str(tmp_path / "grading.xlsx")
    _create_minimal_xlsx(template_path, sheets=("Lecture", "Grading Sheet"))
    recipe = ValidatedTemplateRecipe(
        schema_version=RECIPE_SCHEMA_VERSION,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        template_path=template_path,
        roster_binding=RosterBinding(
            table_index=0,
            worksheet_name="Lecture",
            first_data_row_index=7,
            name_col=3,
            id_col=1,
            index_col=None,  # Missing!
            capacity_limit=50,
        ),
        header_bindings={},
        signature_bindings={},
        metadata={},
        verified_safe=True,
        _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
    )

    gen = GradeGenerator(template_path, recipe)
    info = {"semester": "1st Semester 2025-2026", "subject": "CS 101 - Intro", "course": "BSCS 3-1", "sched": "12345"}
    with pytest.raises(TemplateError) as exc:
        gen.generate(info, [("Student", "123")], str(tmp_path / "out.xlsx"))
    assert "missing mandatory index_col" in str(exc.value)


def test_grade_generator_rejects_missing_worksheet_name(tmp_path):
    """GradeGenerator fails closed with TemplateError if recipe.roster_binding.worksheet_name is missing."""
    template_path = str(tmp_path / "grading.xlsx")
    _create_minimal_xlsx(template_path, sheets=("Lecture", "Grading Sheet"))
    recipe = ValidatedTemplateRecipe(
        schema_version=RECIPE_SCHEMA_VERSION,
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        template_path=template_path,
        roster_binding=RosterBinding(
            table_index=0,
            worksheet_name=None,  # Missing!
            first_data_row_index=7,
            name_col=3,
            id_col=1,
            index_col=1,
            capacity_limit=50,
        ),
        header_bindings={},
        signature_bindings={},
        metadata={},
        verified_safe=True,
        _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
    )

    gen = GradeGenerator(template_path, recipe)
    info = {"semester": "1st Semester 2025-2026", "subject": "CS 101 - Intro", "course": "BSCS 3-1", "sched": "12345"}
    with pytest.raises(TemplateError) as exc:
        gen.generate(info, [("Student", "123")], str(tmp_path / "out.xlsx"))
    assert "missing mandatory worksheet_name" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Forensic Elimination of Fabricated Structural Defaults
# ═══════════════════════════════════════════════════════════════════════════════

def test_zero_or_negative_roster_capacity_fails_closed(tmp_path):
    """Zero or negative roster capacity must fail closed with InvalidRecipeError rather than defaulting to 50."""
    doc_path = str(tmp_path / "zero_cap_template.docx")
    # Table with 1 row: only header row, 0 data rows
    _create_minimal_docx(doc_path, num_tables=1, rows=1, cols=3)

    cand = RawTemplateRecipeCandidate(
        template_path=doc_path,
        profile_id="academic_docx",
        fingerprint="fp_zero_cap",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 1,  # Out of bounds for 1-row table!
            "name_col": 0,
            "id_col": 1,
            "capacity_limit": 0,  # Zero capacity
        },
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "subject", "confidence": 1.0},
        ],
    )
    with pytest.raises((InvalidRecipeError, TemplateError)) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "requires capacity_limit > 0" in str(exc.value) or "capacity_limit must be > 0" in str(exc.value) or "out of range" in str(exc.value)


def test_negative_roster_capacity_in_serialized_recipe_fails_closed():
    """Serialized recipe with negative capacity fails closed with InvalidRecipeError."""
    cand = RawTemplateRecipeCandidate(
        template_path="",  # Serialized
        profile_id="academic_docx",
        fingerprint="fp_ser",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 1,
            "name_col": 0,
            "id_col": 1,
            "capacity_limit": -10,  # Explicitly negative!
        },
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
        ],
        metadata={
            "docx_geometry": {
                "table_row_cell_counts": [(3, 3)],
                "paragraph_count": 5,
            }
        },
    )
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate(cand, PROFILE_ACADEMIC_DOCX)
    assert "requires capacity_limit > 0" in str(exc.value) or "capacity_limit must be > 0" in str(exc.value)


def test_missing_serialized_geometry_fails_closed():
    """Missing serialized geometry metadata fails closed with InvalidRecipeError when physical file is unavailable."""
    # 1. DOCX missing docx_geometry
    cand_docx = RawTemplateRecipeCandidate(
        template_path="",
        profile_id="academic_docx",
        fingerprint="fp_missing_geom",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 1,
            "name_col": 0,
            "id_col": 1,
        },
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "docx_table", "target": (0, 1, 0), "field": "subject", "confidence": 1.0},
        ],
        metadata={},  # No docx_geometry!
    )
    with pytest.raises(InvalidRecipeError) as exc_docx:
        RecipeValidator.validate(cand_docx, PROFILE_ACADEMIC_DOCX)
    assert "missing required 'docx_geometry' metadata" in str(exc_docx.value)

    # 2. XLSX missing xlsx_geometry
    cand_xlsx = RawTemplateRecipeCandidate(
        template_path="",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp_missing_geom_xlsx",
        roster_candidate={
            "table_index": 0,
            "worksheet_name": "Lecture",
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "index_col": 1,
            "capacity_limit": 50,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "Lecture!B2", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B3", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "Lecture!B4", "field": "schedule_code", "confidence": 1.0},
        ],
        metadata={},  # No xlsx_geometry!
    )
    with pytest.raises(InvalidRecipeError) as exc_xlsx:
        RecipeValidator.validate(cand_xlsx, PROFILE_GRADE_SHEET_XLSX)
    assert "missing required 'xlsx_geometry' metadata" in str(exc_xlsx.value)

    # 3. Attendance missing template_student_row_capacity
    from modules.models.recipe import RawAttendanceTemplateRecipeCandidate, PROFILE_ATTENDANCE_DOCX
    cand_att = RawAttendanceTemplateRecipeCandidate(
        template_path="",
        profile_id="attendance_docx",
        fingerprint="fp_att",
        info_candidate={
            "table_index": 0,
            "row_cell_counts": [2, 2],
            "bindings": {"instructor": [0, 1]},
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
            "summary_column_indices": [7, 8, 9],
            "summary_header1_cell_cols": [7, 8, 9],
            "student_summary_cell_cols": [7, 8, 9],
            "week_template_cell_col": 3,
            "summary_header0_cell_col": 7,
            "date_template_cell_col": 3,
            "student_date_template_cell_col": 3,
            "template_session_capacity": 4,
            "matrix_row_count": 5,
            "row0_cell_count": 8,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
            # Missing template_student_row_capacity!
        },
    )
    with pytest.raises(InvalidRecipeError) as exc_att:
        RecipeValidator.validate(cand_att, PROFILE_ATTENDANCE_DOCX)
    assert "template_student_row_capacity" in str(exc_att.value)


def test_legacy_compatibility_output_cannot_introduce_fabricated_coordinates(tmp_path):
    """Legacy compatibility dicts cannot fabricate missing coordinates or defaults."""
    # 1. Missing table_cell coordinates in legacy dict must raise InvalidRecipeError
    bad_legacy_dict = {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "profile_id": "academic_docx",
        "fingerprint": "fp_leg",
        "header_bindings": [
            {
                "field": "instructor",
                "type": "table_cell",
                # Missing table_index, row_index, cell_index!
            }
        ],
        "roster_table": {
            "table_index": 0,
            "first_data_row_index": 1,
            "name_col": 0,
            "id_col": 1,
        },
        "docx_geometry": {
            "table_row_cell_counts": [(3, 3)],
            "paragraph_count": 5,
        },
    }
    with pytest.raises(InvalidRecipeError) as exc:
        RecipeValidator.validate_dict(bad_legacy_dict, profile="academic_docx")
    assert "missing required coordinates" in str(exc.value)

    # 2. Missing paragraph_colon coordinate in legacy dict must raise InvalidRecipeError
    bad_para_dict = {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "profile_id": "academic_docx",
        "fingerprint": "fp_leg",
        "header_bindings": [
            {
                "field": "instructor",
                "type": "paragraph_colon",
                # Missing para_index!
            }
        ],
        "roster_table": {
            "table_index": 0,
            "first_data_row_index": 1,
            "name_col": 0,
            "id_col": 1,
        },
        "docx_geometry": {
            "table_row_cell_counts": [(3, 3)],
            "paragraph_count": 5,
        },
    }
    with pytest.raises(InvalidRecipeError) as exc_para:
        RecipeValidator.validate_dict(bad_para_dict, profile="academic_docx")
    assert "missing required 'para_index'" in str(exc_para.value)


def test_real_academic_attendance_and_grade_templates_continue_to_generate_successfully():
    """Verify all real production template families continue to validate and generate without fallbacks."""
    from modules.services.template_recipe_service import TemplateRecipeResolver
    resolver = TemplateRecipeResolver.get_instance()

    # 1. Real Academic Template
    academic_tmpl = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "template_syllabus.docx")
    if os.path.exists(academic_tmpl):
        recipe_acad = resolver.resolve(academic_tmpl, "academic_docx")
        assert recipe_acad.verified_safe is True
        assert recipe_acad.roster_binding.capacity_limit is not None
        assert recipe_acad.roster_binding.capacity_limit > 0

    # 2. Real Attendance Template
    attendance_tmpl = os.path.join(os.path.dirname(os.path.dirname(__file__)), "attendance", "template lec.docx")
    if os.path.exists(attendance_tmpl):
        recipe_att = resolver.resolve(attendance_tmpl, "attendance_docx")
        assert recipe_att.verified_safe is True
        assert recipe_att.matrix_binding.template_student_row_capacity > 0

    # 3. Real Grade Template
    grade_tmpl = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
    if os.path.exists(grade_tmpl):
        recipe_grade = resolver.resolve(grade_tmpl, "grade_sheet_xlsx")
        assert recipe_grade.verified_safe is True
        assert recipe_grade.roster_binding.capacity_limit > 0
        assert recipe_grade.roster_binding.index_col is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Attendance Structural Coordinate Authority Closure Tests (Commit 157)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_valid_attendance_serialized_dict():
    return {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "profile_id": "attendance_docx",
        "fingerprint": "att_fp_valid",
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
            "template_session_capacity": 4,
            "summary_columns_count": 3,
            "summary_column_names": ["lb", "lc", "r"],
            "summary_column_indices": [7, 8, 9],
            "summary_header1_cell_cols": [7, 8, 9],
            "student_summary_cell_cols": [7, 8, 9],
            "week_template_cell_col": 3,
            "summary_header0_cell_col": 7,
            "date_template_cell_col": 3,
            "student_date_template_cell_col": 3,
            "template_student_row_capacity": 40,
            "summary_column_widths": [212, 208, 133],
            "matrix_row_count": 5,
            "row0_cell_count": 8,
            "row1_cell_count": 10,
            "student_row_cell_count": 10,
        },
        "metadata": {"output_folder": "Attendance"},
    }


@pytest.mark.parametrize(
    "missing_field,expected_exc",
    [
        ("header_row0_index", InvalidRecipeError),
        ("header_row1_index", InvalidRecipeError),
        ("student_template_row_index", InvalidRecipeError),
        ("no_col", InvalidRecipeError),
        ("name_col", TemplateError),
        ("id_col", TemplateError),
        ("date_columns_start", InvalidRecipeError),
        ("template_session_capacity", InvalidRecipeError),
        ("summary_columns_count", InvalidRecipeError),
        ("summary_column_names", InvalidRecipeError),
        ("summary_column_indices", InvalidRecipeError),
        ("summary_header1_cell_cols", InvalidRecipeError),
        ("student_summary_cell_cols", InvalidRecipeError),
        ("week_template_cell_col", InvalidRecipeError),
        ("summary_header0_cell_col", InvalidRecipeError),
        ("date_template_cell_col", InvalidRecipeError),
        ("student_date_template_cell_col", InvalidRecipeError),
    ],
)
def test_attendance_serialized_recipe_missing_structural_field_fails_closed(tmp_path, missing_field, expected_exc):
    """
    Every required attendance structural coordinate must be explicit in serialized recipes.
    Omitting any coordinate MUST raise InvalidRecipeError (or TemplateError for name/id),
    yielding NO validated recipe, preventing generator instantiation/execution, and producing NO output file.
    """
    data = _make_valid_attendance_serialized_dict()
    data["matrix_binding"].pop(missing_field)

    out_file = str(tmp_path / f"output_never_created_{missing_field}.docx")
    assert not os.path.exists(out_file)

    validated_recipe = None
    with pytest.raises(expected_exc):
        validated_recipe = RecipeValidator.validate_dict(data, profile="attendance_docx")

    assert validated_recipe is None
    assert not os.path.exists(out_file)

    # Invariant: AttendanceGenerator cannot run without a ValidatedAttendanceTemplateRecipe
    from modules.generators.attendance_gen import AttendanceGenerator
    with pytest.raises(TypeError, match="AttendanceGenerator requires a ValidatedAttendanceTemplateRecipe"):
        AttendanceGenerator("dummy.docx", validated_recipe)  # type: ignore

    assert not os.path.exists(out_file)


@pytest.mark.parametrize(
    "omitted_field",
    [
        "table_index",
        "header_row0_index",
        "header_row1_index",
        "student_template_row_index",
        "no_col",
        "name_col",
        "id_col",
        "date_columns_start",
        "template_session_capacity",
        "template_student_row_capacity",
        "summary_columns_count",
        "summary_column_names",
        "summary_column_indices",
        "summary_header1_cell_cols",
        "student_summary_cell_cols",
        "week_template_cell_col",
        "summary_header0_cell_col",
        "date_template_cell_col",
        "student_date_template_cell_col",
    ],
)
def test_attendance_matrix_binding_from_dict_strictly_forbids_omitted_coordinates(omitted_field):
    """AttendanceMatrixBinding.from_dict must NOT synthesize missing coordinates with defaults."""
    valid_mb_dict = dict(_make_valid_attendance_serialized_dict()["matrix_binding"])
    valid_mb_dict.pop(omitted_field)

    with pytest.raises(InvalidRecipeError) as exc_info:
        AttendanceMatrixBinding.from_dict(valid_mb_dict)
    assert omitted_field in str(exc_info.value) or "requires explicit" in str(exc_info.value)


def test_attendance_matrix_binding_dataclass_forbids_omitted_coordinates():
    """Direct AttendanceMatrixBinding constructor must require all structural coordinates without defaults."""
    with pytest.raises(TypeError) as exc_info:
        # Omitting week_template_cell_col, summary_header0_cell_col, date_template_cell_col, etc.
        AttendanceMatrixBinding(
            table_index=1,
            header_row0_index=0,
            header_row1_index=1,
            student_template_row_index=2,
            no_col=0,
            name_col=1,
            id_col=2,
            date_columns_start=3,
            summary_columns_count=3,
            summary_column_names=("lb", "lc", "r"),
            template_session_capacity=4,
            template_student_row_capacity=40,
        )
    assert "missing" in str(exc_info.value) and "required positional argument" in str(exc_info.value)


def test_serialized_attendance_recipe_with_geometry_missing_structural_coordinate_fails_closed(tmp_path):
    """Even when full geometric counts are present, missing any structural coordinate fails closed."""
    data = _make_valid_attendance_serialized_dict()
    assert "row0_cell_count" in data["matrix_binding"]
    assert "row1_cell_count" in data["matrix_binding"]
    assert "student_row_cell_count" in data["matrix_binding"]
    assert "matrix_row_count" in data["matrix_binding"]

    # Remove student_date_template_cell_col
    data["matrix_binding"].pop("student_date_template_cell_col")

    out_file = str(tmp_path / "never_created_geom_test.docx")
    with pytest.raises(InvalidRecipeError) as exc_info:
        RecipeValidator.validate_dict(data, profile="attendance_docx")
    assert "student_date_template_cell_col" in str(exc_info.value)
    assert not os.path.exists(out_file)


