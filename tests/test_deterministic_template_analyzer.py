"""
Unit and Integration Test Suite for DocxGridTable and DeterministicTemplateAnalyzer.

Validates:
  1. Low-level OpenXML grid normalization across gridSpan and vMerge topologies.
  2. Safe mutation routing and duplicate write prevention.
  3. Dynamic introspection of all production CEIT, Attendance, and Grading templates.
  4. Invariance under synthetic perturbations (inserted paragraphs, decoy tables, row shifts).
  5. Manifest serialization, deserialization, and deterministic SHA-256 fingerprinting.
"""

import copy
import io
import os
import zipfile
import pytest
from lxml import etree

from modules.common.docx_utils import w, get_full_text
from modules.parsers.docx_grid_table import DocxGridTable, DocxGridCell
from modules.parsers.template_analyzer import (
    DeterministicTemplateAnalyzer,
    TemplateManifest,
    SemanticSlot,
    RepeatingTableTopology,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")
ATTENDANCE_DIR = os.path.join(REPO_ROOT, "attendance")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for In-Memory OpenXML Table Construction
# ─────────────────────────────────────────────────────────────────────────────

def make_xml_cell(text: str = "", grid_span: int = 1, v_merge: str | None = None) -> etree._Element:
    """Creates a <w:tc> element with optional gridSpan and vMerge."""
    tc = etree.Element(w("tc"))
    tcpr = etree.SubElement(tc, w("tcPr"))

    if grid_span > 1:
        gs = etree.SubElement(tcpr, w("gridSpan"))
        gs.set(w("val"), str(grid_span))

    if v_merge is not None:
        vm = etree.SubElement(tcpr, w("vMerge"))
        if v_merge != "":
            vm.set(w("val"), v_merge)

    p = etree.SubElement(tc, w("p"))
    if text:
        r = etree.SubElement(p, w("r"))
        t = etree.SubElement(r, w("t"))
        t.text = text

    return tc


def make_xml_row(cells: list[etree._Element]) -> etree._Element:
    """Creates a <w:tr> element containing the given cells."""
    tr = etree.Element(w("tr"))
    for cell in cells:
        tr.append(cell)
    return tr


def make_xml_table(rows: list[etree._Element], grid_col_widths: list[int] | None = None) -> etree._Element:
    """Creates a <w:tbl> element containing optional <w:tblGrid> and rows."""
    tbl = etree.Element(w("tbl"))
    if grid_col_widths:
        tgrid = etree.SubElement(tbl, w("tblGrid"))
        for w_val in grid_col_widths:
            gc = etree.SubElement(tgrid, w("gridCol"))
            gc.set(w("w"), str(w_val))
    for row in rows:
        tbl.append(row)
    return tbl


# ─────────────────────────────────────────────────────────────────────────────
# 1. DocxGridTable Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_docx_grid_table_uniform_grid():
    """Verify standard uniform 3x4 grid mapping."""
    rows = []
    for r in range(3):
        cells = [make_xml_cell(f"R{r}C{c}") for c in range(4)]
        rows.append(make_xml_row(cells))
    tbl = make_xml_table(rows)

    grid = DocxGridTable(tbl)
    assert grid.num_rows == 3
    assert grid.num_cols == 4
    assert grid.dimensions == (3, 4)

    for r in range(3):
        for c in range(4):
            cell = grid.cell(r, c)
            assert cell.is_origin is True
            assert cell.is_continuation is False
            assert cell.row_span == 1
            assert cell.col_span == 1
            assert cell.origin_row == r
            assert cell.origin_col == c
            assert cell.text == f"R{r}C{c}"

    # Verify adjacent navigation
    assert grid.adjacent_right(0, 0).text == "R0C1"
    assert grid.adjacent_right(0, 3) is None
    assert grid.adjacent_below(0, 0).text == "R1C0"
    assert grid.adjacent_below(2, 0) is None


def test_docx_grid_table_horizontal_span_gridspan():
    """Verify horizontal merge (w:gridSpan) coordinate resolution."""
    # Row 0: Cell 0 spans 3 cols, Cell 1 spans 1 col (total 4 cols)
    # Row 1: 4 separate cells (total 4 cols)
    r0 = make_xml_row([
        make_xml_cell("HeaderSpan3", grid_span=3),
        make_xml_cell("HeaderSingle", grid_span=1),
    ])
    r1 = make_xml_row([
        make_xml_cell("Sub0"),
        make_xml_cell("Sub1"),
        make_xml_cell("Sub2"),
        make_xml_cell("Sub3"),
    ])
    tbl = make_xml_table([r0, r1])

    grid = DocxGridTable(tbl)
    assert grid.num_rows == 2
    assert grid.num_cols == 4

    # Visual (0, 0): origin cell of the 3-column span
    c00 = grid.cell(0, 0)
    assert c00.is_origin is True
    assert c00.col_span == 3
    assert c00.text == "HeaderSpan3"

    # Visual (0, 1) and (0, 2): horizontal continuations of (0, 0)
    c01 = grid.cell(0, 1)
    assert c01.is_origin is False
    assert c01.is_hmerge_continuation is True
    assert c01.origin_row == 0
    assert c01.origin_col == 0
    assert c01.tc is c00.tc

    c02 = grid.cell(0, 2)
    assert c02.is_origin is False
    assert c02.origin_col == 0

    # Visual (0, 3): single cell after the span
    c03 = grid.cell(0, 3)
    assert c03.is_origin is True
    assert c03.col_span == 1
    assert c03.text == "HeaderSingle"

    # Adjacent right of (0, 0) should skip past its 3-column span directly to (0, 3)
    assert grid.adjacent_right(0, 0).text == "HeaderSingle"


def test_docx_grid_table_vertical_merge_vmerge():
    """Verify vertical merge (w:vMerge) continuation resolution."""
    # Row 0: Col 0 vmerge=restart, Col 1 normal
    # Row 1: Col 0 vmerge=continue, Col 1 normal
    # Row 2: Col 0 normal (ends vmerge), Col 1 normal
    r0 = make_xml_row([
        make_xml_cell("MergedVertical", v_merge="restart"),
        make_xml_cell("R0C1"),
    ])
    r1 = make_xml_row([
        make_xml_cell("", v_merge=""),  # OpenXML continuation
        make_xml_cell("R1C1"),
    ])
    r2 = make_xml_row([
        make_xml_cell("R2C0"),
        make_xml_cell("R2C1"),
    ])
    tbl = make_xml_table([r0, r1, r2])

    grid = DocxGridTable(tbl)
    assert grid.num_rows == 3
    assert grid.num_cols == 2

    # Visual (0, 0): origin of vertical merge spanning 2 rows
    c00 = grid.cell(0, 0)
    assert c00.is_origin is True
    assert c00.row_span == 2
    assert c00.text == "MergedVertical"

    # Visual (1, 0): vertical continuation of (0, 0)
    c10 = grid.cell(1, 0)
    assert c10.is_origin is False
    assert c10.is_vmerge_continuation is True
    assert c10.origin_row == 0
    assert c10.origin_col == 0
    assert c10.tc is c00.tc

    # Visual (2, 0): new cell after vertical merge ended
    c20 = grid.cell(2, 0)
    assert c20.is_origin is True
    assert c20.row_span == 1
    assert c20.text == "R2C0"

    # Adjacent below (0, 0) should skip past its 2-row span directly to (2, 0)
    assert grid.adjacent_below(0, 0).text == "R2C0"


def test_docx_grid_table_combined_gridspan_and_vmerge():
    """Verify combined horizontal and vertical merge (2x2 block)."""
    # 2x2 merged block in top-left
    r0 = make_xml_row([
        make_xml_cell("Block2x2", grid_span=2, v_merge="restart"),
        make_xml_cell("R0C2"),
    ])
    r1 = make_xml_row([
        make_xml_cell("", grid_span=2, v_merge=""),
        make_xml_cell("R1C2"),
    ])
    tbl = make_xml_table([r0, r1])

    grid = DocxGridTable(tbl)
    assert grid.num_rows == 2
    assert grid.num_cols == 3

    origin = grid.cell(0, 0)
    assert origin.is_origin is True
    assert origin.row_span == 2
    assert origin.col_span == 2
    assert origin.span_shape == (2, 2)
    assert origin.text == "Block2x2"

    for r in range(2):
        for c in range(2):
            cell = grid.cell(r, c)
            assert cell.origin_row == 0
            assert cell.origin_col == 0
            assert cell.tc is origin.tc

    assert grid.adjacent_right(0, 0).text == "R0C2"
    assert grid.adjacent_below(0, 0) is None


def test_docx_grid_table_target_value_cell_colon_skip():
    """Verify target_value_cell_right jumps past colon-only separator cells."""
    r0 = make_xml_row([
        make_xml_cell("Instructor Name"),
        make_xml_cell(":"),
        make_xml_cell("Dan Joseph Ortega"),
    ])
    tbl = make_xml_table([r0])
    grid = DocxGridTable(tbl)

    target = grid.target_value_cell_right(0, 0)
    assert target is not None
    assert target.col == 2
    assert target.text == "Dan Joseph Ortega"


def test_docx_grid_table_safe_mutation():
    """Verify set_cell_text mutates only canonical origin and prevents duplicate writes."""
    r0 = make_xml_row([
        make_xml_cell("Original", grid_span=2, v_merge="restart"),
    ])
    r1 = make_xml_row([
        make_xml_cell("", grid_span=2, v_merge=""),
    ])
    tbl = make_xml_table([r0, r1])
    grid = DocxGridTable(tbl)

    # Mutate through continuation coordinate (1, 1)
    grid.set_cell_text(1, 1, "MutatedValue", allow_duplicate_write=False)

    # Canonical origin and all continuation views must reflect new text
    assert grid.cell(0, 0).text == "MutatedValue"
    assert grid.cell(1, 1).text == "MutatedValue"
    assert grid.has_mutated(0, 0) is True
    assert grid.has_mutated(1, 1) is True

    # Duplicate write prevention test
    with pytest.raises(ValueError, match="already been mutated"):
        grid.set_cell_text(0, 0, "DuplicateAttempt", allow_duplicate_write=False)

    # Forced overwrite works when allowed
    grid.set_cell_text(0, 0, "ForcedOverwrite", allow_duplicate_write=True)
    assert grid.cell(0, 0).text == "ForcedOverwrite"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Integration Tests with Real Repository Templates
# ─────────────────────────────────────────────────────────────────────────────

def test_analyzer_real_ceit_syllabus():
    """Test deterministic analysis of template_syllabus.docx."""
    path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    analyzer = DeterministicTemplateAnalyzer()
    manifest = analyzer.analyze(path)

    assert manifest.file_type == "docx"
    assert manifest.template_type == "academic_ceit"
    assert manifest.suggested_suffix == "SYLLABUS_ACCEPTANCE"
    assert len(manifest.content_hash) == 64

    # Verify core metadata slots
    fields = {s.field: s for s in manifest.slots}
    assert "instructor" in fields
    assert "course_section" in fields
    assert "schedule_code" in fields
    assert "subject" in fields
    assert "semester_ay" in fields

    # Verify roster table
    roster = manifest.roster_table
    assert roster is not None
    assert roster.topology_type == "student_roster"
    assert roster.first_data_row_index == 1
    assert roster.data_rows_capacity == 40
    assert roster.columns["index"] == 0
    assert roster.columns["name"] == 1
    assert roster.columns["student_number"] == 2
    assert roster.columns["signature"] == 3


def test_analyzer_real_ceit_exam_midterm_and_finals():
    """Test deterministic analysis of template_exam_midterm.docx and template_exam_finals.docx."""
    analyzer = DeterministicTemplateAnalyzer()

    for fname, exp_suffix in [
        ("template_exam_midterm.docx", "EXAM_RETURNS_MIDTERM"),
        ("template_exam_finals.docx", "EXAM_RETURNS_FINALS"),
    ]:
        path = os.path.join(TEMPLATES_DIR, fname)
        manifest = analyzer.analyze(path)

        assert manifest.template_type == "academic_ceit"
        assert manifest.suggested_suffix == exp_suffix

        roster = manifest.roster_table
        assert roster is not None
        assert roster.columns["name"] == 0
        assert roster.columns["student_number"] == 1
        assert roster.columns["signature"] == 2
        assert roster.data_rows_capacity == 40


def test_analyzer_real_ceit_grade_discussion_colon_jump():
    """Test colon column skipping in Final-Grade-Discussion_LATEST.docx."""
    path = os.path.join(TEMPLATES_DIR, "Final-Grade-Discussion_LATEST.docx")
    analyzer = DeterministicTemplateAnalyzer()
    manifest = analyzer.analyze(path)

    assert manifest.suggested_suffix == "FINAL_GRADE_DISCUSSION"
    instructor_slot = manifest.get_slot("instructor")
    assert instructor_slot is not None
    # Label is in col 0, colon is in col 1, target is in col 2
    assert instructor_slot.col_index == 0
    assert instructor_slot.target_col_index == 2


def test_analyzer_real_attendance_lecture():
    """Test attendance lecture template (10 columns, 2 header rows)."""
    path = os.path.join(ATTENDANCE_DIR, "template lec.docx")
    analyzer = DeterministicTemplateAnalyzer()
    manifest = analyzer.analyze(path)

    assert manifest.template_type == "attendance"
    assert manifest.suggested_suffix == "ATTENDANCE"

    roster = manifest.roster_table
    assert roster is not None
    assert roster.topology_type == "attendance_matrix"
    assert roster.total_cols == 10
    # Must detect both header rows (rows 0 and 1 due to vertical merge)
    assert roster.header_rows == [0, 1]
    assert roster.first_data_row_index == 2
    assert roster.columns["index"] == 0
    assert roster.columns["name"] == 1
    assert roster.columns["student_number"] == 2


def test_analyzer_real_attendance_lab_and_lec():
    """Test attendance lab & lec template (14 columns, 2 header rows)."""
    path = os.path.join(ATTENDANCE_DIR, "template lab and lec.docx")
    analyzer = DeterministicTemplateAnalyzer()
    manifest = analyzer.analyze(path)

    assert manifest.template_type == "attendance"
    roster = manifest.roster_table
    assert roster is not None
    assert roster.total_cols == 14
    assert roster.header_rows == [0, 1]
    assert roster.first_data_row_index == 2
    assert roster.columns["index"] == 0
    assert roster.columns["name"] == 1
    assert roster.columns["student_number"] == 2


def test_analyzer_real_grading_sheet_xlsx():
    """Test deterministic analysis of Excel grading sheet template."""
    path = os.path.join(TEMPLATES_DIR, "GRADING_LECTURE_TEMPLATE.xlsx")
    analyzer = DeterministicTemplateAnalyzer()
    manifest = analyzer.analyze(path)

    assert manifest.file_type == "xlsx"
    assert manifest.template_type == "grading_sheet"
    assert manifest.roster_table is not None
    assert "name" in manifest.roster_table.columns
    assert len(manifest.slots) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Synthetic Perturbation Tests (Dynamic Invariance)
# ─────────────────────────────────────────────────────────────────────────────

def test_analyzer_invariant_to_injected_paragraphs():
    """
    Assert that injecting arbitrary dummy paragraphs before tables does not
    break semantic slot or roster table detection.
    """
    src_path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    with zipfile.ZipFile(src_path, "r") as z:
        doc_xml = z.read("word/document.xml")
    root = etree.fromstring(doc_xml)
    body = root.find(w("body"))

    # Inject 3 dummy paragraphs at the start of body
    for i in range(3):
        dummy_p = etree.Element(w("p"))
        r = etree.SubElement(dummy_p, w("r"))
        t = etree.SubElement(r, w("t"))
        t.text = f"Decoy Paragraph {i}: Not a label or table."
        body.insert(0, dummy_p)

    # Serialize to in-memory docx
    buf = io.BytesIO()
    with zipfile.ZipFile(src_path, "r") as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/document.xml":
                    zout.writestr(item, etree.tostring(root, xml_declaration=True, encoding="utf-8"))
                else:
                    zout.writestr(item, zin.read(item.filename))

    perturbed_bytes = buf.getvalue()

    # Write temporary file
    temp_path = os.path.join(TEMPLATES_DIR, "_temp_perturbed_syllabus.docx")
    try:
        with open(temp_path, "wb") as f:
            f.write(perturbed_bytes)

        analyzer = DeterministicTemplateAnalyzer()
        manifest = analyzer.analyze(temp_path)

        assert manifest.suggested_suffix == "SYLLABUS_ACCEPTANCE"
        assert manifest.roster_table is not None
        assert manifest.roster_table.columns["name"] == 1
        assert manifest.roster_table.columns["student_number"] == 2
        assert len(manifest.slots) >= 5
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_analyzer_invariant_to_injected_decoy_table():
    """
    Assert that injecting a decoy non-roster table shifts table indices dynamically
    without misclassifying the roster table or metadata slots.
    """
    src_path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    with zipfile.ZipFile(src_path, "r") as z:
        doc_xml = z.read("word/document.xml")
    root = etree.fromstring(doc_xml)
    body = root.find(w("body"))

    # Create a 2x2 decoy table with non-metadata text
    decoy_rows = [
        make_xml_row([make_xml_cell("Decoy Col A"), make_xml_cell("Decoy Col B")]),
        make_xml_row([make_xml_cell("Data A1"), make_xml_cell("Data B1")]),
    ]
    decoy_tbl = make_xml_table(decoy_rows)
    body.insert(0, decoy_tbl)

    buf = io.BytesIO()
    with zipfile.ZipFile(src_path, "r") as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/document.xml":
                    zout.writestr(item, etree.tostring(root, xml_declaration=True, encoding="utf-8"))
                else:
                    zout.writestr(item, zin.read(item.filename))

    temp_path = os.path.join(TEMPLATES_DIR, "_temp_decoy_tbl_syllabus.docx")
    try:
        with open(temp_path, "wb") as f:
            f.write(buf.getvalue())

        analyzer = DeterministicTemplateAnalyzer()
        manifest = analyzer.analyze(temp_path)

        # Original Table 0 became Table 1, Table 1 became Table 2
        assert manifest.metadata_table_index == 1
        assert manifest.roster_table is not None
        assert manifest.roster_table.table_index == 2
        assert manifest.roster_table.columns["name"] == 1
        assert manifest.roster_table.columns["student_number"] == 2
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_analyzer_explicit_placeholder_detection():
    """Verify that templates with {{TAG}} and <TAG> placeholders are cataloged."""
    src_path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    with zipfile.ZipFile(src_path, "r") as z:
        doc_xml = z.read("word/document.xml")
    root = etree.fromstring(doc_xml)
    body = root.find(w("body"))

    # Append paragraph with explicit placeholders
    p = etree.SubElement(body, w("p"))
    r = etree.SubElement(p, w("r"))
    t = etree.SubElement(r, w("t"))
    t.text = "Dean: {{DEAN_NAME}}, Approved: <DATE_APPROVED>"

    buf = io.BytesIO()
    with zipfile.ZipFile(src_path, "r") as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/document.xml":
                    zout.writestr(item, etree.tostring(root, xml_declaration=True, encoding="utf-8"))
                else:
                    zout.writestr(item, zin.read(item.filename))

    temp_path = os.path.join(TEMPLATES_DIR, "_temp_placeholders_test.docx")
    try:
        with open(temp_path, "wb") as f:
            f.write(buf.getvalue())

        analyzer = DeterministicTemplateAnalyzer()
        manifest = analyzer.analyze(temp_path)

        assert manifest.has_explicit_placeholders is True
        assert "{{DEAN_NAME}}" in manifest.explicit_placeholders
        assert "<DATE_APPROVED>" in manifest.explicit_placeholders
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Serialization & Roundtrip Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_template_manifest_serialization_roundtrip():
    """Verify TemplateManifest serializes to dict/JSON and roundtrips with 100% fidelity."""
    path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    analyzer = DeterministicTemplateAnalyzer()
    manifest = analyzer.analyze(path)

    d = manifest.to_dict()
    assert isinstance(d, dict)
    assert d["content_hash"] == manifest.content_hash

    restored = TemplateManifest.from_dict(d)
    assert restored.template_path == manifest.template_path
    assert restored.content_hash == manifest.content_hash
    assert restored.suggested_suffix == manifest.suggested_suffix
    assert len(restored.slots) == len(manifest.slots)
    assert restored.roster_table.columns == manifest.roster_table.columns
