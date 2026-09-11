import os
import tempfile
import pytest
from modules.models.schedule import ClassInfo
from modules.parsers.template_inspector import TemplateInspector
from modules.generators.generic_doc_gen import ConfigurableDocumentGenerator
from modules.common.docx_utils import load_docx, get_full_text, w

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")


@pytest.fixture
def sample_class_info():
    return ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        course_section="BSCS 1-4",
        schedule_code="202522383",
        subject="ITEC50 – WEB SYSTEMS AND TECHNOLOGY",
        time_days_room="10:00AM-12:00AM / M / CCL 305",
        semester_ay="2nd Semester / 2025-2026",
        students=[
            ("ALVAREZ, MARIA C.", "202310001"),
            ("CRUZ, JUAN B.", "202310002"),
            ("SANTOS, JHOANNA P.", "202310003"),
        ],
    )


def test_generic_doc_gen_syllabus(sample_class_info, tmp_path):
    template_path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    inspector = TemplateInspector()
    recipe = inspector.inspect_docx(template_path)

    gen = ConfigurableDocumentGenerator(template_path, recipe)
    out_path = str(tmp_path / "out_syllabus.docx")
    gen.generate(sample_class_info, out_path)

    assert os.path.exists(out_path)
    zin, root, body = load_docx(out_path)
    tables = body.findall(w("tbl"))
    assert len(tables) >= 2

    # Verify Header Table
    tbl0 = tables[0]
    row0_text = get_full_text(tbl0.findall(w("tr"))[0])
    assert "DAN JOSEPH A. ORTEGA" in row0_text
    row1_text = get_full_text(tbl0.findall(w("tr"))[1])
    assert "BSCS 1-4" in row1_text

    # Verify Student Roster Table
    tbl1 = tables[1]
    rows = tbl1.findall(w("tr"))
    # 1 header + 3 student rows = 4 rows
    assert len(rows) == 4

    row1_cells = [get_full_text(c).strip() for c in rows[1].findall(w("tc"))]
    assert row1_cells[0] == "1"
    assert row1_cells[1] == "ALVAREZ, MARIA C."
    assert row1_cells[2] == "202310001"


def test_generic_doc_gen_exam(sample_class_info, tmp_path):
    template_path = os.path.join(TEMPLATES_DIR, "template_exam_midterm.docx")
    inspector = TemplateInspector()
    recipe = inspector.inspect_docx(template_path)

    gen = ConfigurableDocumentGenerator(template_path, recipe)
    out_path = str(tmp_path / "out_exam.docx")
    gen.generate(sample_class_info, out_path)

    assert os.path.exists(out_path)
    zin, root, body = load_docx(out_path)
    tables = body.findall(w("tbl"))

    tbl1 = tables[1]
    rows = tbl1.findall(w("tr"))
    assert len(rows) == 4

    row1_cells = [get_full_text(c).strip() for c in rows[1].findall(w("tc"))]
    assert row1_cells[0] == "ALVAREZ, MARIA C."
    assert row1_cells[1] == "202310001"
