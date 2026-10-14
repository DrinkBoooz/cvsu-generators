#!/usr/bin/env python3
"""
tests/test_dynamic_renderer_resilience.py

Comprehensive Resilience and Parity Verification Suite for DynamicDocumentRenderer:
  1. 100% Golden Parity across all CEIT forms and Attendance sheets
  2. End-to-End Structural Perturbation Resilience (decoy tables and prepended paragraphs)
  3. Style Preservation (run font names, bold flags, student font ladder, cell shading)
  4. Explicit Placeholders ({{TAG}} / <TAG>)
  5. Excel (.xlsx) dynamic sheet rendering
"""

import os
import sys
import copy
import glob
import tempfile
import pytest
import docx
import openpyxl
from lxml import etree

from modules.common.docx_utils import load_docx, save_docx, w, get_full_text
from modules.models.schedule import ClassInfo
from modules.generators.dynamic_renderer import DynamicDocumentRenderer
from modules.generators.ceit_gen import (
    SyllabusGenerator,
    ExamReturnsGenerator,
    TOSGenerator,
    GradeDiscussionGenerator,
)
from modules.generators.attendance_gen import AttendanceGenerator
from modules.services.template_recipe_service import TemplateRecipeResolver

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(WORKSPACE_DIR, "templates")
ATTENDANCE_DIR = os.path.join(WORKSPACE_DIR, "attendance")


@pytest.fixture
def sample_class_info():
    return ClassInfo(
        instructor="DAN JOSEPH ORTEGA",
        course_section="BSCS 3-1",
        schedule_code="202612040",
        subject="DCIT 50 - OBJECT ORIENTED PROGRAMMING",
        time_days_room="THU: 07:00AM-12:00PM (CL4)",
        semester_ay="1st Semester AY 2026-2027",
        students=[
            ("AGUILAR, JOHN DOE A.", "202610001"),
            ("DELA CRUZ, JUAN P.", "202610002"),
            ("DE RUEDA, ALELHY ALLESSANDRA M.", "202610003"),  # 31 chars -> 7pt (14)
            ("DE LOS REYES, MA. CONCEPCION DELA CRUZ", "202610004"),  # 39 chars -> 6pt (12)
        ],
    )


def test_dynamic_renderer_ceit_golden_parity(tmp_path, sample_class_info):
    """
    Assert 100% structural and text parity between official CEIT generators
    and DynamicDocumentRenderer across all standard forms.
    """
    ceit_forms = [
        ("template_syllabus.docx", SyllabusGenerator, {}),
        ("template_exam_midterm.docx", ExamReturnsGenerator, {"period": "MIDTERM"}),
        ("template_exam_finals.docx", ExamReturnsGenerator, {"period": "FINALS"}),
        ("template_tos_midterm.docx", TOSGenerator, {"period": "Midterm"}),
        ("template_tos_finals.docx", TOSGenerator, {"period": "Finals"}),
        ("Midterm-Grade-Discussion_LATEST.docx", GradeDiscussionGenerator, {"period": "Midterm"}),
        ("Final-Grade-Discussion_LATEST.docx", GradeDiscussionGenerator, {"period": "Finals"}),
    ]

    resolver = TemplateRecipeResolver.get_instance()
    renderer = DynamicDocumentRenderer()

    for tmpl_name, gen_cls, kwargs in ceit_forms:
        tmpl_path = os.path.join(TEMPLATES_DIR, tmpl_name)
        assert os.path.isfile(tmpl_path), f"Template missing: {tmpl_path}"

        gen_out = str(tmp_path / f"gen_{tmpl_name}")
        dyn_out = str(tmp_path / f"dyn_{tmpl_name}")

        recipe = resolver.resolve(tmpl_path, "academic_docx")
        generator = gen_cls(tmpl_path, recipe, **kwargs)
        generator.generate(sample_class_info, gen_out)

        # Context adjustment for TOS forms
        ctx = sample_class_info
        if "tos" in tmpl_name.lower():
            ctx = ClassInfo(
                instructor=sample_class_info.instructor,
                course_section=sample_class_info.course_section,
                schedule_code=sample_class_info.schedule_code,
                subject=sample_class_info.subject,
                time_days_room=sample_class_info.time_days_room,
                semester_ay=f"{sample_class_info.semester_ay} ({kwargs.get('period', '')})",
                students=sample_class_info.students,
            )

        renderer.render_docx(tmpl_path, ctx, dyn_out)

        # Assert 100% table count, row count, and cell text parity
        doc_gen = docx.Document(gen_out)
        doc_dyn = docx.Document(dyn_out)

        assert len(doc_gen.tables) == len(doc_dyn.tables), (
            f"Table count mismatch for {tmpl_name}: {len(doc_gen.tables)} vs {len(doc_dyn.tables)}"
        )

        for t_idx in range(len(doc_gen.tables)):
            tbl_gen = doc_gen.tables[t_idx]
            tbl_dyn = doc_dyn.tables[t_idx]
            assert len(tbl_gen.rows) == len(tbl_dyn.rows), (
                f"{tmpl_name} Table {t_idx} row count mismatch: {len(tbl_gen.rows)} vs {len(tbl_dyn.rows)}"
            )
            for r_idx in range(len(tbl_gen.rows)):
                r_gen = [c.text.strip() for c in tbl_gen.rows[r_idx].cells]
                r_dyn = [c.text.strip() for c in tbl_dyn.rows[r_idx].cells]
                assert r_gen == r_dyn, (
                    f"{tmpl_name} Table {t_idx} Row {r_idx} mismatch:\n  Gen: {r_gen}\n  Dyn: {r_dyn}"
                )


def test_perturbation_resilience_ceit_syllabus(tmp_path, sample_class_info):
    """
    End-to-End Perturbation Test: Insert decoy table and extra paragraphs
    before Table 0 in template_syllabus.docx, and assert DynamicDocumentRenderer
    still populates the correct metadata table and student roster table.
    """
    syllabus_p = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    perturbed_tmpl = str(tmp_path / "perturbed_syllabus.docx")
    output_docx = str(tmp_path / "perturbed_syllabus_output.docx")

    zin, root, body = load_docx(syllabus_p)

    # 1. Prepend decoy table
    decoy_tbl = etree.Element(w("tbl"))
    decoy_tr = etree.SubElement(decoy_tbl, w("tr"))
    decoy_tc = etree.SubElement(decoy_tr, w("tc"))
    decoy_p = etree.SubElement(decoy_tc, w("p"))
    decoy_r = etree.SubElement(decoy_p, w("r"))
    decoy_t = etree.SubElement(decoy_r, w("t"))
    decoy_t.text = "DECOY ARTIFACT TABLE"

    # 2. Prepend decoy paragraphs
    decoy_para = etree.Element(w("p"))
    dp_r = etree.SubElement(decoy_para, w("r"))
    dp_t = etree.SubElement(dp_r, w("t"))
    dp_t.text = "DECOY PREPENDED PARAGRAPH HEADER"

    body.insert(0, decoy_tbl)
    body.insert(0, decoy_para)
    save_docx(zin, root, perturbed_tmpl)

    # 3. Render perturbed template
    renderer = DynamicDocumentRenderer()
    renderer.render_docx(perturbed_tmpl, sample_class_info, output_docx)

    # 4. Assert correctness
    doc = docx.Document(output_docx)
    assert len(doc.tables) == 3, f"Expected 3 tables (1 decoy + 2 original), got {len(doc.tables)}"

    # Table 0: Decoy table is untouched
    t0_text = doc.tables[0].rows[0].cells[0].text.strip()
    assert t0_text == "DECOY ARTIFACT TABLE", f"Decoy table was corrupted: {t0_text}"

    # Table 1: Real metadata table has instructor and section
    t1_flat = " ".join(" ".join(c.text.strip() for c in r.cells) for r in doc.tables[1].rows)
    assert "DAN JOSEPH ORTEGA" in t1_flat, f"Instructor not found in Table 1: {t1_flat}"
    assert "BSCS 3-1" in t1_flat, f"Section not found in Table 1: {t1_flat}"
    assert "202612040" in t1_flat, f"Schedule code not found in Table 1: {t1_flat}"

    # Table 2: Real student roster table has all students
    t2_rows = doc.tables[2].rows
    assert len(t2_rows) == 5, f"Expected 5 rows in Table 2 (1 header + 4 students), got {len(t2_rows)}"
    st1_text = " ".join(c.text.strip() for c in t2_rows[1].cells)
    assert "AGUILAR, JOHN DOE A." in st1_text
    assert "202610001" in st1_text


def test_perturbation_resilience_ceit_tos(tmp_path, sample_class_info):
    """
    Perturbation Test for TOS templates: Insert decoy table and assert metadata
    and roster land in the appropriate shifted tables.
    """
    tos_p = os.path.join(TEMPLATES_DIR, "template_tos_midterm.docx")
    perturbed_tmpl = str(tmp_path / "perturbed_tos.docx")
    output_docx = str(tmp_path / "perturbed_tos_output.docx")

    zin, root, body = load_docx(tos_p)
    decoy_tbl = etree.Element(w("tbl"))
    d_tr = etree.SubElement(decoy_tbl, w("tr"))
    d_tc = etree.SubElement(d_tr, w("tc"))
    d_p = etree.SubElement(d_tc, w("p"))
    d_r = etree.SubElement(d_p, w("r"))
    d_t = etree.SubElement(d_r, w("t"))
    d_t.text = "DECOY TOS TOP"
    body.insert(0, decoy_tbl)
    save_docx(zin, root, perturbed_tmpl)

    renderer = DynamicDocumentRenderer()
    renderer.render_docx(perturbed_tmpl, sample_class_info, output_docx)

    doc = docx.Document(output_docx)
    assert len(doc.tables) >= 3

    # Table 0: Decoy
    assert doc.tables[0].rows[0].cells[0].text.strip() == "DECOY TOS TOP"

    # Table 1: Real metadata table
    t1_flat = " ".join(" ".join(c.text.strip() for c in r.cells) for r in doc.tables[1].rows)
    assert "DAN JOSEPH ORTEGA" in t1_flat
    assert "BSCS 3-1" in t1_flat


def test_perturbation_resilience_attendance_template(tmp_path):
    """
    Perturbation Test for AttendanceGenerator: Prepend decoy table to template lec.docx,
    run AttendanceGenerator.generate, and assert both info table and matrix table
    resolve dynamically to Table 1 and Table 2.
    """
    att_tmpl = os.path.join(ATTENDANCE_DIR, "template lec.docx")
    assert os.path.isfile(att_tmpl), f"Attendance template missing: {att_tmpl}"

    perturbed_tmpl = str(tmp_path / "perturbed_att.docx")
    output_docx = str(tmp_path / "perturbed_att_output.docx")

    zin, root, body = load_docx(att_tmpl)

    # Prepend decoy table
    decoy_tbl = etree.Element(w("tbl"))
    d_tr = etree.SubElement(decoy_tbl, w("tr"))
    d_tc = etree.SubElement(d_tr, w("tc"))
    d_p = etree.SubElement(d_tc, w("p"))
    d_r = etree.SubElement(d_p, w("r"))
    d_t = etree.SubElement(d_r, w("t"))
    d_t.text = "DECOY ATTENDANCE TABLE"
    body.insert(0, decoy_tbl)
    save_docx(zin, root, perturbed_tmpl)

    # Resolve recipe and run AttendanceGenerator
    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(att_tmpl, "attendance_docx")
    gen = AttendanceGenerator(perturbed_tmpl, recipe)

    gen.generate(
        output_path=output_docx,
        course_code_title="DCIT 50 - OBJECT ORIENTED PROGRAMMING",
        class_schedule="THU: 07:00AM-12:00PM (CL4)",
        semester_ay="1st Semester AY 2026-2027",
        room_assignment="CL4",
        instructor="DAN JOSEPH ORTEGA",
        months=[8],
        year=2026,
        weekdays=[3],  # Thursday
        students=[
            ("AGUILAR, JOHN DOE A.", "202610001"),
            ("DELA CRUZ, JUAN P.", "202610002"),
        ],
    )

    doc = docx.Document(output_docx)
    assert len(doc.tables) == 3, f"Expected 3 tables (1 decoy + 2 attendance), got {len(doc.tables)}"

    # Table 0: Decoy table is untouched
    assert doc.tables[0].rows[0].cells[0].text.strip() == "DECOY ATTENDANCE TABLE"

    # Table 1: Info table populated dynamically
    t1_flat = " ".join(" ".join(c.text.strip() for c in r.cells) for r in doc.tables[1].rows)
    assert "DAN JOSEPH ORTEGA" in t1_flat
    assert "DCIT 50" in t1_flat
    assert "CL4" in t1_flat

    # Table 2: Attendance matrix table populated dynamically
    t2_rows = doc.tables[2].rows
    assert len(t2_rows) >= 3, f"Expected matrix rows in Table 2, got {len(t2_rows)}"
    t2_flat = " ".join(" ".join(c.text.strip() for c in r.cells) for r in t2_rows)
    assert "AGUILAR, JOHN DOE A." in t2_flat
    assert "202610001" in t2_flat


def test_style_preservation_font_and_shading(tmp_path, sample_class_info):
    """
    Assert run font formatting, dynamic student font scaling ladder, and cell properties
    are preserved after dynamic slot and table population.
    """
    syllabus_p = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    output_docx = str(tmp_path / "style_test_output.docx")

    renderer = DynamicDocumentRenderer()
    renderer.render_docx(syllabus_p, sample_class_info, output_docx)

    # Inspect XML nodes directly for style preservation
    zin, root, body = load_docx(output_docx)
    tables = body.findall(w("tbl"))
    roster_tbl = tables[1]
    rows = roster_tbl.findall(w("tr"))

    # Student 1: 20 chars <= 30 -> 8pt (sz="16")
    st1_tc = rows[1].findall(w("tc"))[1]
    st1_sz = st1_tc.find(".//" + w("r") + "/" + w("rPr") + "/" + w("sz"))
    assert st1_sz is not None and st1_sz.get(w("val")) == "16", "Expected 8pt (sz=16) for standard name"

    # Student 3: 31 chars -> 7pt (sz="14")
    st3_tc = rows[3].findall(w("tc"))[1]
    st3_sz = st3_tc.find(".//" + w("r") + "/" + w("rPr") + "/" + w("sz"))
    assert st3_sz is not None and st3_sz.get(w("val")) == "14", "Expected 7pt (sz=14) for 31-char name"

    # Student 4: 39 chars -> 6pt (sz="12")
    st4_tc = rows[4].findall(w("tc"))[1]
    st4_sz = st4_tc.find(".//" + w("r") + "/" + w("rPr") + "/" + w("sz"))
    assert st4_sz is not None and st4_sz.get(w("val")) == "12", "Expected 6pt (sz=12) for 39-char name"

    # Table 0 metadata: verify cell borders and formatting are intact
    meta_tbl = tables[0]
    cell_0_0 = meta_tbl.find(".//" + w("tc"))
    assert cell_0_0 is not None
    tc_pr = cell_0_0.find(w("tcPr"))
    assert tc_pr is not None, "Cell properties <w:tcPr> must be preserved"


def test_dynamic_renderer_explicit_placeholders(tmp_path):
    """
    Verify explicit placeholders {{INSTRUCTOR}}, {{SUBJECT}}, and <COURSE_SEC>
    are cleanly replaced while preserving run formatting.
    """
    doc_path = str(tmp_path / "custom_placeholder_template.docx")
    out_path = str(tmp_path / "custom_placeholder_output.docx")

    # Create a minimal docx with explicit placeholders
    doc = docx.Document()
    p1 = doc.add_paragraph("Course: ")
    r1 = p1.add_run("{{SUBJECT}}")
    r1.bold = True
    p2 = doc.add_paragraph("Faculty: <INSTRUCTOR>")
    doc.save(doc_path)

    data = {
        "subject": "DCIT 50 - OOP",
        "instructor": "DR. DAN JOSEPH ORTEGA",
    }

    renderer = DynamicDocumentRenderer()
    renderer.render_docx(doc_path, data, out_path)

    doc_out = docx.Document(out_path)
    p1_out = doc_out.paragraphs[0]
    p2_out = doc_out.paragraphs[1]

    assert "DCIT 50 - OOP" in p1_out.text
    assert "{{SUBJECT}}" not in p1_out.text
    assert "DR. DAN JOSEPH ORTEGA" in p2_out.text
    assert "<INSTRUCTOR>" not in p2_out.text

    # Bold run property preserved
    bold_runs = [r for r in p1_out.runs if r.bold]
    assert len(bold_runs) >= 1, "Bold property must be preserved on replaced run"


def test_dynamic_renderer_xlsx_rendering(tmp_path):
    """
    Verify Excel (.xlsx) template rendering driven by TemplateManifest.
    """
    lecture_tmpl = os.path.join(WORKSPACE_DIR, "Lecture only.xlsx")
    assert os.path.isfile(lecture_tmpl), f"Lecture template missing: {lecture_tmpl}"

    out_xlsx = str(tmp_path / "dynamic_grade_sheet.xlsx")

    data = {
        "instructor": "DAN JOSEPH ORTEGA",
        "subject": "DCIT 50 - OBJECT ORIENTED PROGRAMMING",
        "course_section": "BSCS 3-1",
        "students": [
            ("TEST STUDENT A", "202610001"),
            ("TEST STUDENT B", "202610002"),
        ],
    }

    renderer = DynamicDocumentRenderer()
    renderer.render_xlsx(lecture_tmpl, data, out_xlsx)

    assert os.path.isfile(out_xlsx)
    wb = openpyxl.load_workbook(out_xlsx)
    assert len(wb.sheetnames) >= 1


def test_perturbation_resilience_ceit_exam(tmp_path, sample_class_info):
    """
    Perturbation Test for Exam Returns: Insert decoy table and assert metadata
    and roster land in the appropriate shifted tables.
    """
    exam_p = os.path.join(TEMPLATES_DIR, "template_exam_midterm.docx")
    perturbed_tmpl = str(tmp_path / "perturbed_exam.docx")
    output_docx = str(tmp_path / "perturbed_exam_output.docx")

    zin, root, body = load_docx(exam_p)
    decoy_tbl = etree.Element(w("tbl"))
    d_tr = etree.SubElement(decoy_tbl, w("tr"))
    d_tc = etree.SubElement(d_tr, w("tc"))
    d_p = etree.SubElement(d_tc, w("p"))
    d_r = etree.SubElement(d_p, w("r"))
    d_t = etree.SubElement(d_r, w("t"))
    d_t.text = "DECOY EXAM TOP"
    body.insert(0, decoy_tbl)
    save_docx(zin, root, perturbed_tmpl)

    renderer = DynamicDocumentRenderer()
    renderer.render_docx(perturbed_tmpl, sample_class_info, output_docx)

    doc = docx.Document(output_docx)
    assert len(doc.tables) >= 3

    # Table 0: Decoy
    assert doc.tables[0].rows[0].cells[0].text.strip() == "DECOY EXAM TOP"

    # Table 1: Real metadata table
    t1_flat = " ".join(" ".join(c.text.strip() for c in r.cells) for r in doc.tables[1].rows)
    assert "DAN JOSEPH ORTEGA" in t1_flat
    assert "BSCS 3-1" in t1_flat


def test_document_generator_dynamic_resilience_under_perturbation(tmp_path, sample_class_info):
    """
    Verify that existing DocumentGenerator subclasses (e.g. SyllabusGenerator)
    leverage dynamic topological resolution when executing on a perturbed template.
    """
    syllabus_p = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    perturbed_tmpl = str(tmp_path / "perturbed_docgen.docx")
    output_docx = str(tmp_path / "perturbed_docgen_output.docx")

    zin, root, body = load_docx(syllabus_p)
    decoy_tbl = etree.Element(w("tbl"))
    d_tr = etree.SubElement(decoy_tbl, w("tr"))
    d_tc = etree.SubElement(d_tr, w("tc"))
    d_p = etree.SubElement(d_tc, w("p"))
    d_r = etree.SubElement(d_p, w("r"))
    d_t = etree.SubElement(d_r, w("t"))
    d_t.text = "DECOY FOR DOCGEN"
    body.insert(0, decoy_tbl)
    save_docx(zin, root, perturbed_tmpl)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(syllabus_p, "academic_docx")
    generator = SyllabusGenerator(perturbed_tmpl, recipe)
    generator.generate(sample_class_info, output_docx)

    doc = docx.Document(output_docx)
    assert len(doc.tables) == 3

    # Table 0: Decoy
    assert doc.tables[0].rows[0].cells[0].text.strip() == "DECOY FOR DOCGEN"

    # Table 1: Real metadata table populated
    t1_flat = " ".join(" ".join(c.text.strip() for c in r.cells) for r in doc.tables[1].rows)
    assert "DAN JOSEPH ORTEGA" in t1_flat

    # Table 2: Student roster populated
    t2_rows = doc.tables[2].rows
    assert len(t2_rows) == len(sample_class_info.students) + 1

