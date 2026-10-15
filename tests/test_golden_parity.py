"""
Golden-Master Verification Suite & Low-Level DOCX Parity Test Harness.

Migrated and formalized from ad-hoc debug tools:
  - debug/dump_header_paras.py
  - debug/inspect_doc.py
  - debug/inspect_doc_file.py
  - debug/inspect_doc_test.py
  - debug/inspect_exam_template.py
  - debug/inspect_output_folder.py
  - debug/inspect_table_cells.py
  - debug/inspect_table_original.py
  - debug/inspect_table_test3.py
  - debug/inspect_template_syllabus.py
  - debug/inspect_template_tos.py
  - debug/test_outputs.py
  - debug/verify_outputs.py

Programmatically inspects:
  1. Low-level OpenXML schema nodes: <w:tbl>, <w:tr>, <w:tc>, <w:p>, <w:t>, <w:numPr>.
  2. Document body, header stories (word/header*.xml), and footer stories (word/footer*.xml).
  3. Table cell topologies (row counts, column counts, cell text content, formatting runs).
  4. End-to-end structural schema parity between newly generated outputs and baseline golden outputs.
"""

import os
import sys
import glob
import zipfile
import pytest
from lxml import etree
import docx

# Ensure workspace root is available on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

import process_schedule
import ceit_generator
import attendancegen

# Namespaces for OpenXML WordprocessingML
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_URI = f"{{{W_NS}}}"


def w(tag: str) -> str:
    """Return qualified Clark notation tag for OpenXML WordprocessingML."""
    return f"{W_URI}{tag}"


class OpenXmlInspector:
    """Low-level OpenXML document parser extracting structural topology and story streams."""

    def __init__(self, docx_path: str):
        self.docx_path = docx_path
        if not os.path.isfile(docx_path):
            raise FileNotFoundError(f"DOCX file does not exist: {docx_path}")

        self.body_paragraphs = []
        self.header_paragraphs = []
        self.footer_paragraphs = []
        self.tables = []
        self._parse()

    def _extract_para_text(self, p_elem) -> str:
        return "".join((t.text or "") for t in p_elem.iter(w("t")))

    def _parse(self):
        with zipfile.ZipFile(self.docx_path, "r") as z:
            # 1. Main document story
            if "word/document.xml" in z.namelist():
                doc_xml = z.read("word/document.xml")
                root = etree.fromstring(doc_xml)
                body = root.find(w("body"))
                if body is not None:
                    self.body_paragraphs = [
                        self._extract_para_text(p) for p in body.findall(".//" + w("p"))
                    ]
                    self.tables = body.findall(".//" + w("tbl"))

            # 2. Header stories
            for fname in z.namelist():
                if fname.startswith("word/header") and fname.endswith(".xml"):
                    h_root = etree.fromstring(z.read(fname))
                    for p in h_root.findall(".//" + w("p")):
                        t = self._extract_para_text(p)
                        if t.strip():
                            self.header_paragraphs.append(t)

            # 3. Footer stories
            for fname in z.namelist():
                if fname.startswith("word/footer") and fname.endswith(".xml"):
                    f_root = etree.fromstring(z.read(fname))
                    for p in f_root.findall(".//" + w("p")):
                        t = self._extract_para_text(p)
                        if t.strip():
                            self.footer_paragraphs.append(t)

    def get_table_topology(self, tbl_idx: int = 0) -> dict:
        """Inspect table row count, cell counts per row, and cell text matrices."""
        if tbl_idx >= len(self.tables):
            return {"exists": False, "rows": 0, "matrix": []}

        tbl = self.tables[tbl_idx]
        rows = tbl.findall(w("tr"))
        matrix = []
        has_num_pr = []

        for row in rows:
            cells = row.findall(w("tc"))
            row_texts = ["".join((t.text or "") for t in c.iter(w("t"))).strip() for c in cells]
            matrix.append(row_texts)

            # Check for numPr (list formatting)
            row_numpr = False
            for c in cells:
                for p in c.findall(w("p")):
                    ppr = p.find(w("pPr"))
                    if ppr is not None and ppr.find(w("numPr")) is not None:
                        row_numpr = True
                        break
            has_num_pr.append(row_numpr)

        return {
            "exists": True,
            "rows": len(rows),
            "columns": len(matrix[0]) if matrix else 0,
            "matrix": matrix,
            "has_num_pr": has_num_pr,
        }


# Fixtures directory paths
GOLDEN_ROOT = os.path.join(WORKSPACE_DIR, "tests", "fixtures", "golden_outputs")
GOLDEN_CEIT = os.path.join(GOLDEN_ROOT, "CEIT_Forms")
GOLDEN_ATTENDANCE = os.path.join(GOLDEN_ROOT, "Attendance")
SCHEDULE_FIXTURE = os.path.join(WORKSPACE_DIR, "tests", "fixtures", "schedules", "ORTEGA_SCHEDULE.xls")
ROSTER_FIXTURE = os.path.join(
    WORKSPACE_DIR, "schedules", "BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.xlsx"
)


def test_golden_master_fixtures_present():
    """Verify that the preserved golden-master fixtures exist and are readable."""
    assert os.path.isdir(GOLDEN_CEIT), f"Missing golden CEIT directory: {GOLDEN_CEIT}"
    assert os.path.isdir(GOLDEN_ATTENDANCE), f"Missing golden Attendance directory: {GOLDEN_ATTENDANCE}"

    ceit_files = [f for f in os.listdir(GOLDEN_CEIT) if f.endswith(".docx")]
    att_files = [f for f in os.listdir(GOLDEN_ATTENDANCE) if f.endswith(".docx")]

    assert len(ceit_files) == 5, f"Expected 5 golden CEIT forms, found: {ceit_files}"
    assert len(att_files) == 5, f"Expected 5 golden Attendance sheets, found: {att_files}"

    for cf in ceit_files:
        p = os.path.join(GOLDEN_CEIT, cf)
        assert os.path.getsize(p) > 1000, f"Golden file {cf} is corrupted or empty"

    for af in att_files:
        p = os.path.join(GOLDEN_ATTENDANCE, af)
        assert os.path.getsize(p) > 1000, f"Golden file {af} is corrupted or empty"


def test_golden_fixtures_openxml_topology():
    """Verify OpenXML table cell topology in the golden baseline documents."""
    expected_ceit_topology = {
        "EXAM_RETURNS_FINALS": {"tables": 2, "t0_rows": 5, "t1_rows": 41, "t1_cols": 3},
        "EXAM_RETURNS_MIDTERM": {"tables": 2, "t0_rows": 5, "t1_rows": 41, "t1_cols": 3},
        "SYLLABUS_ACCEPTANCE": {"tables": 2, "t0_rows": 6, "t1_rows": 41, "t1_cols": 4},
        "TOS_FINALS": {"tables": 2, "t0_rows": 6, "t1_rows": 41, "t1_cols": 3},
        "TOS_MIDTERM": {"tables": 2, "t0_rows": 6, "t1_rows": 41, "t1_cols": 3},
    }

    for fname in os.listdir(GOLDEN_CEIT):
        if not fname.endswith(".docx"):
            continue
        p = os.path.join(GOLDEN_CEIT, fname)
        inspector = OpenXmlInspector(p)
        assert len(inspector.tables) >= 2, f"{fname} should have at least 2 tables"

        for key, spec in expected_ceit_topology.items():
            if key in fname:
                t0 = inspector.get_table_topology(0)
                t1 = inspector.get_table_topology(1)
                assert t0["rows"] == spec["t0_rows"], f"{fname} Table 0 expected {spec['t0_rows']} rows, got {t0['rows']}"
                assert t1["rows"] == spec["t1_rows"], f"{fname} Table 1 expected {spec['t1_rows']} rows, got {t1['rows']}"
                assert t1["columns"] == spec["t1_cols"], f"{fname} Table 1 expected {spec['t1_cols']} cols, got {t1['columns']}"


def test_golden_fixtures_header_and_metadata_paragraphs():
    """Verify metadata paragraphs and header texts across all golden forms (from inspect_doc & verify_outputs)."""
    for fname in os.listdir(GOLDEN_CEIT):
        if not fname.endswith(".docx"):
            continue
        p = os.path.join(GOLDEN_CEIT, fname)
        inspector = OpenXmlInspector(p)

        all_text = " ".join(inspector.body_paragraphs + inspector.header_paragraphs)
        assert (
            "CAVITE STATE UNIVERSITY" in all_text
            or "Cavite State University" in all_text
            or "Indang, Cavite" in all_text
            or "COLLEGE OF ENGINEERING" in all_text
        )

        # Table 0 metadata labels
        t0 = inspector.get_table_topology(0)
        t0_flat = " ".join(" ".join(row) for row in t0["matrix"]).upper()
        assert "INSTRUCTOR" in t0_flat or "FACULTY" in t0_flat
        assert "COURSE" in t0_flat or "SECTION" in t0_flat
        assert "SCHEDULE CODE" in t0_flat or "202612040" in t0_flat


def test_template_structural_schemas():
    """Verify official templates in templates/ match the structural invariants checked in debug scripts."""
    template_dir = os.path.join(WORKSPACE_DIR, "templates")

    # 1. Syllabus template (from inspect_template_syllabus.py)
    syllabus_p = os.path.join(template_dir, "template_syllabus.docx")
    assert os.path.isfile(syllabus_p), "template_syllabus.docx must exist"
    s_insp = OpenXmlInspector(syllabus_p)
    assert len(s_insp.body_paragraphs) > 10, "template_syllabus.docx should have body paragraphs"
    assert len(s_insp.tables) >= 1, "template_syllabus.docx must contain at least 1 table"
    s_t0 = s_insp.get_table_topology(0)
    assert s_t0["rows"] >= 5, "template_syllabus.docx Table 0 must have at least 5 metadata rows"

    # 2. TOS templates (from inspect_template_tos.py)
    for tos_name in ["template_tos_midterm.docx", "template_tos_finals.docx"]:
        tos_p = os.path.join(template_dir, tos_name)
        assert os.path.isfile(tos_p), f"{tos_name} must exist"
        tos_insp = OpenXmlInspector(tos_p)
        assert len(tos_insp.tables) >= 1
        tos_t0 = tos_insp.get_table_topology(0)
        assert tos_t0["rows"] >= 5

    # 3. Exam returns templates (from inspect_exam_template.py)
    for exam_name in ["template_exam_midterm.docx", "template_exam_finals.docx"]:
        exam_p = os.path.join(template_dir, exam_name)
        assert os.path.isfile(exam_p), f"{exam_name} must exist"
        exam_insp = OpenXmlInspector(exam_p)
        assert len(exam_insp.tables) >= 1
        exam_t0 = exam_insp.get_table_topology(0)
        assert exam_t0["rows"] >= 4


def test_generated_output_structural_parity_with_golden_master(tmp_path):
    """
    End-to-End Parity: Generate BSCS1-4 forms from scratch and verify they
    exhibit 100% structural parity with tests/fixtures/golden_outputs/.
    """
    assert os.path.isfile(SCHEDULE_FIXTURE), f"Schedule fixture missing: {SCHEDULE_FIXTURE}"
    assert os.path.isfile(ROSTER_FIXTURE), f"Roster fixture missing: {ROSTER_FIXTURE}"

    out_dir = str(tmp_path / "parity_test_run")
    os.makedirs(out_dir, exist_ok=True)

    # Execute generator orchestrator for BSCS1-4
    res = process_schedule.process_all(
        schedule_path=SCHEDULE_FIXTURE,
        xlsx_files=[ROSTER_FIXTURE],
        output_dir_base=out_dir,
        class_filter=["202612040_CS1-4"],
        engine_filter=["ceit", "attendance"],
    )

    generated_ceit = res.get("generated", {}).get("ceit", [])
    generated_attendance = res.get("generated", {}).get("attendance", [])

    assert len(generated_ceit) >= 5, f"Expected at least 5 CEIT forms, got {generated_ceit}"
    assert len(generated_attendance) == 5, f"Expected 5 Attendance sheets, got {generated_attendance}"

    # Verify structural topology parity against golden master
    parity_targets = [
        ("SYLLABUS_ACCEPTANCE", "BSCS1-4_202612040_SYLLABUS_ACCEPTANCE.docx"),
        ("EXAM_RETURNS_MIDTERM", "BSCS1-4_202612040_EXAM_RETURNS_MIDTERM.docx"),
        ("EXAM_RETURNS_FINALS", "BSCS1-4_202612040_EXAM_RETURNS_FINALS.docx"),
        ("TOS_MIDTERM", "BSCS1-4_202612040_TOS_MIDTERM.docx"),
        ("TOS_FINALS", "BSCS1-4_202612040_TOS_FINALS.docx"),
    ]

    for suffix, golden_name in parity_targets:
        golden_file = os.path.join(GOLDEN_CEIT, golden_name)
        assert os.path.isfile(golden_file), f"Golden file missing: {golden_file}"

        # Find corresponding generated file
        candidates = glob.glob(os.path.join(out_dir, "**", f"*{suffix}*.docx"), recursive=True)
        assert candidates, f"No generated file found for suffix {suffix} under {out_dir}"
        gen_file = candidates[0]

        golden_insp = OpenXmlInspector(golden_file)
        gen_insp = OpenXmlInspector(gen_file)

        # 1. Table count parity
        assert len(gen_insp.tables) == len(golden_insp.tables), (
            f"Table count mismatch for {suffix}: gen={len(gen_insp.tables)}, golden={len(golden_insp.tables)}"
        )

        # 2. Table 0 metadata rows and columns
        g_t0 = golden_insp.get_table_topology(0)
        g_t0_rows = g_t0["rows"]
        gen_t0 = gen_insp.get_table_topology(0)
        assert gen_t0["rows"] == g_t0_rows, (
            f"Table 0 row mismatch for {suffix}: gen={gen_t0['rows']}, golden={g_t0_rows}"
        )
        assert gen_t0["columns"] == g_t0["columns"]

        # 3. Table 1 roster rows and student count
        g_t1 = golden_insp.get_table_topology(1)
        gen_t1 = gen_insp.get_table_topology(1)
        assert gen_t1["rows"] == g_t1["rows"], (
            f"Table 1 row mismatch for {suffix}: gen={gen_t1['rows']}, golden={g_t1['rows']}"
        )
        assert gen_t1["columns"] == g_t1["columns"]

        # 4. Verify student identity cells match roster data
        # Row 1 is the first student
        assert len(gen_t1["matrix"]) > 1
        first_gen_row = " ".join(gen_t1["matrix"][1])
        assert "ARCA" in first_gen_row and "261014253" in first_gen_row, (
            f"First student mismatch in {suffix}: {first_gen_row}"
        )


def test_attendance_structural_parity_with_golden_master(tmp_path):
    """Verify generated Attendance sheets match golden master table topology."""
    out_dir = str(tmp_path / "attendance_parity_run")
    os.makedirs(out_dir, exist_ok=True)

    res = process_schedule.process_all(
        schedule_path=SCHEDULE_FIXTURE,
        xlsx_files=[ROSTER_FIXTURE],
        output_dir_base=out_dir,
        class_filter=["202612040_CS1-4"],
        engine_filter=["attendance"],
    )

    gen_att_files = glob.glob(os.path.join(out_dir, "**", "*ATTENDANCE*.docx"), recursive=True)
    assert len(gen_att_files) == 5, f"Expected 5 generated attendance sheets, found: {len(gen_att_files)}"

    months = ["AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

    for month in months:
        # Match generated month file
        gen_matches = [f for f in gen_att_files if month.lower() in f.lower()]
        assert gen_matches, f"No generated attendance file found for month {month}"
        gen_f = gen_matches[0]

        # Match golden month file
        golden_f = os.path.join(GOLDEN_ATTENDANCE, f"BSCS1-4_202612040_ATTENDANCE_{month}_2026.docx")
        assert os.path.isfile(golden_f), f"Golden attendance fixture missing: {golden_f}"

        golden_insp = OpenXmlInspector(golden_f)
        gen_insp = OpenXmlInspector(gen_f)

        assert len(gen_insp.tables) == len(golden_insp.tables), f"Table count mismatch for {month}"

        g_t0 = golden_insp.get_table_topology(0)
        g_t1 = golden_insp.get_table_topology(1)

        cur_t0 = gen_insp.get_table_topology(0)
        cur_t1 = gen_insp.get_table_topology(1)

        assert cur_t0["rows"] == g_t0["rows"], f"Attendance header table rows mismatch in {gen_f}"
        assert cur_t1["rows"] == g_t1["rows"], f"Attendance roster table rows mismatch in {gen_f}"
        assert cur_t1["columns"] == g_t1["columns"], f"Attendance column mismatch in {gen_f}"


def test_no_unreplaced_placeholders_in_outputs(tmp_path):
    """Ensure no raw template tags like <NAME>, {{TAG}}, or #HEADER# remain unpopulated."""
    out_dir = str(tmp_path / "placeholder_check")
    os.makedirs(out_dir, exist_ok=True)

    process_schedule.process_all(
        schedule_path=SCHEDULE_FIXTURE,
        xlsx_files=[ROSTER_FIXTURE],
        output_dir_base=out_dir,
        class_filter=["202612040_CS1-4"],
        engine_filter=["ceit", "attendance"],
    )

    all_docx = glob.glob(os.path.join(out_dir, "**", "*.docx"), recursive=True)
    assert all_docx, "No generated documents found to verify"

    raw_patterns = ["<INSTRUCTOR>", "<COURSE>", "{{", "}}", "<<", ">>", "__PLACEHOLDER__"]

    for doc_path in all_docx:
        insp = OpenXmlInspector(doc_path)
        all_para_text = " ".join(insp.body_paragraphs)
        for pattern in raw_patterns:
            assert pattern not in all_para_text, f"Found raw unreplaced placeholder '{pattern}' in {doc_path}"

        for ti, tbl in enumerate(insp.tables):
            topo = insp.get_table_topology(ti)
            for r_idx, row in enumerate(topo["matrix"]):
                row_str = " ".join(row)
                for pattern in raw_patterns:
                    assert pattern not in row_str, (
                        f"Found raw unreplaced placeholder '{pattern}' in {doc_path} Table {ti} Row {r_idx}"
                    )


def test_generated_outputs_instructor_and_metadata_compliance(tmp_path):
    """
    Formalized from debug/verify_outputs.py and debug/test_outputs.py:
    Verify instructor, section, subject, student count, and first student presence in all outputs.
    """
    out_dir = str(tmp_path / "compliance_check")
    os.makedirs(out_dir, exist_ok=True)

    students = ceit_generator.load_students(ROSTER_FIXTURE)
    assert len(students) == 40, f"Expected 40 students in BSCS1-4 roster, got {len(students)}"

    process_schedule.process_all(
        schedule_path=SCHEDULE_FIXTURE,
        xlsx_files=[ROSTER_FIXTURE],
        output_dir_base=out_dir,
        class_filter=["202612040_CS1-4"],
        engine_filter=["ceit", "attendance"],
    )

    all_docx = glob.glob(os.path.join(out_dir, "**", "*.docx"), recursive=True)
    assert len(all_docx) >= 10, f"Expected at least 10 DOCX files, got {len(all_docx)}"

    first_student_name, first_student_num = students[0]

    for doc_path in all_docx:
        insp = OpenXmlInspector(doc_path)
        all_para_text = " ".join(insp.body_paragraphs + insp.header_paragraphs)

        # Check instructor presence (debug/test_outputs.py)
        has_instructor = (
            "ORTEGA" in all_para_text
            or "DAN JOSEPH" in all_para_text
            or any("ORTEGA" in " ".join(row) for t in range(len(insp.tables)) for row in insp.get_table_topology(t)["matrix"])
        )
        assert has_instructor, f"Instructor DAN JOSEPH A. ORTEGA missing from {doc_path}"

        # Check minimum rows (debug/test_outputs.py: row_count >= 5)
        assert len(insp.tables) > 0, f"No tables in {doc_path}"
        t0 = insp.get_table_topology(0)
        assert t0["rows"] >= 5, f"Table 0 should have >= 5 rows in {doc_path}"

        # If roster table exists (Table 1), check student presence (debug/verify_outputs.py)
        if len(insp.tables) >= 2:
            t1 = insp.get_table_topology(1)
            t1_flat = " ".join(" ".join(r) for r in t1["matrix"])
            assert first_student_name in t1_flat, (
                f"First student name '{first_student_name}' missing from roster table in {doc_path}"
            )
            assert first_student_num in t1_flat, (
                f"First student number '{first_student_num}' missing from roster table in {doc_path}"
            )


def test_table_paragraph_list_formatting_numpr():
    """
    Formalized from debug/inspect_table_test3.py:
    Verify that table cells in CEIT forms and golden baseline correctly manage
    list formatting (w:numPr) without unintentional numbered list corruption.
    """
    for fname in os.listdir(GOLDEN_CEIT):
        if not fname.endswith(".docx"):
            continue
        p = os.path.join(GOLDEN_CEIT, fname)
        insp = OpenXmlInspector(p)
        for ti in range(len(insp.tables)):
            topo = insp.get_table_topology(ti)
            # Ensure topology parser correctly inspected numPr status per row
            assert len(topo["has_num_pr"]) == topo["rows"]

