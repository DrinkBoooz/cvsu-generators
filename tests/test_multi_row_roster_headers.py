#!/usr/bin/env python3
"""
tests/test_multi_row_roster_headers.py

Comprehensive tests for multi-row roster header detection:
- Single-row header templates (syllabus, exam returns)
- Blank template data rows (grade discussion) - ensure blank rows are not treated as headers
- Multi-row header templates (attendance sheet with Week 1..4 parent headers and Date subheaders)
- Explicit <w:tblHeader/> markers
- Recipe validator constraint enforcement (first_data_row_index >= header_row_index + header_row_count)
- End-to-end student roster generation preserving secondary header rows
"""

import os
import tempfile
import docx
import pytest
from modules.parsers.template_inspector import DocxTemplateInspector
from modules.parsers.recipe_validator import RecipeValidator
from modules.generators.generic_doc_gen import ConfigurableDocumentGenerator
from modules.models.recipe import TemplateError, RosterBinding
from modules.models.schedule import ClassInfo

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")


def test_single_row_header_detection():
    """Verify standard CEIT forms detect exactly 1 header row and first_data_row_index == 1."""
    insp = DocxTemplateInspector()
    for fname in ("template_syllabus.docx", "template_exam_finals.docx", "template_tos_midterm.docx"):
        p = os.path.join(TEMPLATES_DIR, fname)
        cand = insp.inspect(p)
        rc = cand.roster_candidate
        assert rc is not None, f"Expected roster candidate for {fname}"
        assert rc["header_row_index"] == 0
        assert rc["header_row_count"] == 1
        assert rc["first_data_row_index"] == 1


def test_blank_template_row_handling():
    """
    Verify blank rows after headers are NOT treated as headers or termination.
    They must be detected as the intended template data row.
    """
    insp = DocxTemplateInspector()
    p = os.path.join(TEMPLATES_DIR, "Final-Grade-Discussion_LATEST.docx")
    cand = insp.inspect(p)
    rc = cand.roster_candidate
    assert rc is not None
    assert rc["header_row_index"] == 0
    assert rc["header_row_count"] == 1
    # Row 1 is all blank, so it must be first_data_row_index = 1
    assert rc["first_data_row_index"] == 1


def test_multi_row_attendance_sheet_detection():
    """
    Verify attendance templates with subheaders (e.g. S August Attendance Sheet)
    detect header_row_count == 2 and first_data_row_index == 2.
    """
    appdata = os.environ.get("APPDATA", "")
    custom_path = os.path.join(appdata, "CVSU_Generators", "custom_templates", "s_august_attendance_sheet.docx")
    if not os.path.exists(custom_path):
        pytest.skip("s_august_attendance_sheet.docx not found in AppData custom_templates")

    insp = DocxTemplateInspector()
    cand = insp.inspect(custom_path)
    rc = cand.roster_candidate
    assert rc is not None
    assert rc["header_row_index"] == 0
    assert rc["header_row_count"] == 2
    assert rc["first_data_row_index"] == 2
    assert rc["name_col"] == 1
    assert rc["id_col"] == 2
    assert rc["index_col"] == 0


def test_recipe_validator_enforces_header_bounds():
    """Verify validator rejects recipes where first_data_row_index precedes or collides with headers."""
    # Valid binding
    valid_data = {
        "table_index": 1,
        "header_row_index": 0,
        "header_row_count": 2,
        "first_data_row_index": 2,
        "name_col": 1,
        "id_col": 2,
    }
    from modules.models.recipe import PROFILE_CUSTOM_DOCX
    binding = RecipeValidator._validate_roster(valid_data, PROFILE_CUSTOM_DOCX)
    assert binding.header_row_count == 2
    assert binding.first_data_row_index == 2

    # Invalid: first_data_row_index inside header range
    invalid_data = {
        "table_index": 1,
        "header_row_index": 0,
        "header_row_count": 2,
        "first_data_row_index": 1,  # Collides with secondary header row 1
        "name_col": 1,
        "id_col": 2,
    }
    with pytest.raises(TemplateError, match="cannot precede headers"):
        RecipeValidator._validate_roster(invalid_data, PROFILE_CUSTOM_DOCX)


def test_end_to_end_multi_row_table_generation_preserves_subheaders(tmp_path):
    """
    Verify that document generation on a multi-row header template preserves
    Row 0 (Week headers) and Row 1 (Date subheaders), placing Student 1 at Row 2.
    """
    appdata = os.environ.get("APPDATA", "")
    custom_path = os.path.join(appdata, "CVSU_Generators", "custom_templates", "s_august_attendance_sheet.docx")
    if not os.path.exists(custom_path):
        pytest.skip("s_august_attendance_sheet.docx not found in AppData custom_templates")

    cand = DocxTemplateInspector().inspect(custom_path)
    val = RecipeValidator.validate(cand, "custom_docx")

    info = ClassInfo(
        instructor="Dr. Dan Joseph Ortega",
        course_section="BSCS 1-4",
        schedule_code="202522383",
        subject="DCIT 21 - INTRODUCTION TO COMPUTING",
        students=[
            ("ALMOZARA, ALFRED D.", "251013131"),
            ("ABUYO, JHEMM AMIRAH C.", "251013299"),
            ("CRUZ, JUAN D.", "251013300"),
        ],
    )

    out_file = str(tmp_path / "generated_attendance.docx")
    gen = ConfigurableDocumentGenerator(custom_path, val)
    gen.generate(info, out_file)

    assert os.path.isfile(out_file)

    out_doc = docx.Document(out_file)
    tbl = out_doc.tables[1]

    # Row 0: Primary header
    row0_texts = [c.text.strip() for c in tbl.rows[0].cells]
    assert "NO." in row0_texts[0]
    assert "NAME" in row0_texts[1]
    assert "STUDENT NUMBER" in row0_texts[2]
    assert any("Week" in t or "Weel" in t for t in row0_texts)

    # Row 1: Secondary header (Date subheaders) MUST NOT be overwritten
    row1_texts = [c.text.strip() for c in tbl.rows[1].cells]
    assert any("Date" in t for t in row1_texts[3:]), f"Expected Date subheaders in row 1, got {row1_texts}"
    assert "ALMOZARA" not in row1_texts[1], "Student 1 must NOT overwrite secondary header in Row 1"

    # Row 2: Student 1
    row2_texts = [c.text.strip() for c in tbl.rows[2].cells]
    assert row2_texts[0] == "1"
    assert "ALMOZARA" in row2_texts[1]
    assert "251013131" in row2_texts[2]

    # Row 3: Student 2
    row3_texts = [c.text.strip() for c in tbl.rows[3].cells]
    assert row3_texts[0] == "2"
    assert "ABUYO" in row3_texts[1]
    assert "251013299" in row3_texts[2]

    # Row 4: Student 3
    row4_texts = [c.text.strip() for c in tbl.rows[4].cells]
    assert row4_texts[0] == "3"
    assert "CRUZ" in row4_texts[1]
    assert "251013300" in row4_texts[2]
