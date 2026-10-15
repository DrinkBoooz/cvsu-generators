#!/usr/bin/env python3
"""
tests/test_custom_docx_typography.py

Regression tests for custom DOCX typography, wrapping, and schedule rendering:
1. Short instructor preserves template typography without line breaks.
2. Long instructor preserves template typography without premature shrinking.
3. Long subject/title preserves template typography without 40-char shrinking.
4. One schedule entry rendered in exactly one paragraph.
5. Two schedule entries separated by '; ' in exactly one paragraph.
6. Three schedule entries separated by '; ' in exactly one paragraph.
7. Schedule is contained in exactly one logical <w:p>.
8. Schedule contains zero generated w:br.
9. Schedule contains zero generated w:cr.
10. Schedule entries are separated by '; '.
11. Custom template with non-default font family preserves exact font family.
12. Custom template with non-default font size preserves exact font size.
13. Normal fields do not receive arbitrary 9pt (sz="18") fallback.
14. Long student names retain existing controlled scaling behavior (>32 chars).
15. Existing custom-template generation remains compatible.
16. Section 8 Real-Generation Case with exact verification points.
"""

import os
import docx
import pytest
from lxml import etree

from modules.models.schedule import ClassInfo
from modules.models.recipe import PROFILE_CUSTOM_DOCX
from modules.parsers.template_inspector import DocxTemplateInspector
from modules.parsers.recipe_validator import RecipeValidator
from modules.generators.generic_doc_gen import ConfigurableDocumentGenerator
from modules.common.docx_utils import load_docx, w, get_full_text

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_TEMPLATES_DIR = os.path.join(REPO_ROOT, "tests", "test_templates")


def _create_custom_template_with_typography(
    path: str,
    font_name: str = "Georgia",
    font_pt: int = 14,
    bold: bool = False,
    italic: bool = False,
) -> dict:
    """
    Creates a custom DOCX template with explicit run typography
    and returns a map of field_name -> expected font properties.
    """
    doc = docx.Document()
    table = doc.add_table(rows=4, cols=2)

    # Helper to populate cell with styled run
    def set_cell(r_idx, label, val_text, f_name, f_pt, is_b=False, is_i=False):
        table.rows[r_idx].cells[0].paragraphs[0].add_run(label).bold = True
        cell_val = table.rows[r_idx].cells[1]
        p = cell_val.paragraphs[0]
        run = p.add_run(val_text)
        run.font.name = f_name
        run.font.size = docx.shared.Pt(f_pt)
        run.bold = is_b
        run.italic = is_i
        return {
            "font_name": f_name,
            "font_pt": f_pt,
            "sz_val": str(f_pt * 2),
            "bold": is_b,
            "italic": is_i,
        }

    props = {}
    props["instructor"] = set_cell(0, "Instructor:", "Default Instructor", font_name, font_pt, is_b=bold, is_i=italic)
    props["subject"] = set_cell(1, "Course Code & Title:", "Default Subject", "Century Gothic", 12, is_b=True)
    props["time_days_room"] = set_cell(2, "Class Schedule:", "Default Schedule", "Courier New", 11)
    props["semester_ay"] = set_cell(3, "Semester & AY:", "Default Semester", "Arial", 10)

    # Add a minimal roster table
    r_tbl = doc.add_table(rows=2, cols=3)
    r_tbl.rows[0].cells[0].paragraphs[0].add_run("No.")
    r_tbl.rows[0].cells[1].paragraphs[0].add_run("Student Name")
    r_tbl.rows[0].cells[2].paragraphs[0].add_run("Student Number")

    r_run = r_tbl.rows[1].cells[1].paragraphs[0].add_run("Sample Student")
    r_run.font.name = "Arial"
    r_run.font.size = docx.shared.Pt(10)
    r_tbl.rows[1].cells[2].paragraphs[0].add_run("2026-0001")

    doc.save(path)
    return props


def _extract_cell_run_properties(cell_el):
    """Inspects the first run of the first paragraph in a table cell element."""
    p = cell_el.find(w("p"))
    if p is None:
        return None
    runs = p.findall(w("r"))
    if not runs:
        return None
    r = runs[0]
    rpr = r.find(w("rPr"))
    props = {
        "text": run_text(r),
        "font_name": None,
        "sz": None,
        "bold": False,
        "italic": False,
    }
    if rpr is not None:
        rfonts = rpr.find(w("rFonts"))
        if rfonts is not None:
            props["font_name"] = rfonts.get(w("ascii")) or rfonts.get(w("hAnsi"))
        sz = rpr.find(w("sz"))
        if sz is not None:
            props["sz"] = sz.get(w("val"))
        props["bold"] = rpr.find(w("b")) is not None
        props["italic"] = rpr.find(w("i")) is not None
    return props


def run_text(r_el):
    return "".join(t.text or "" for t in r_el.iter(w("t")))


# ==============================================================================
# 1. Short Instructor
# ==============================================================================
def test_short_instructor_preserves_typography(tmp_path):
    tmpl_path = str(tmp_path / "tmpl_short_inst.docx")
    out_path = str(tmp_path / "out_short_inst.docx")
    props = _create_custom_template_with_typography(tmpl_path, font_name="Georgia", font_pt=14)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        subject="COSC 111",
        time_days_room="Wed: 11:00AM-01:00PM / LEC: OS",
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    t = body.findall(w("tbl"))[0]
    inst_cell = t.findall(w("tr"))[0].findall(w("tc"))[1]
    res = _extract_cell_run_properties(inst_cell)

    assert "DAN JOSEPH A. ORTEGA" in res["text"]
    assert res["font_name"] == "Georgia"
    assert res["sz"] == "28"  # 14pt = 28 half-points
    assert len(inst_cell.findall(w("p"))) == 1


# ==============================================================================
# 2. Long Instructor
# ==============================================================================
def test_long_instructor_does_not_shrink_prematurely(tmp_path):
    tmpl_path = str(tmp_path / "tmpl_long_inst.docx")
    out_path = str(tmp_path / "out_long_inst.docx")
    props = _create_custom_template_with_typography(tmpl_path, font_name="Georgia", font_pt=14)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    # 46 characters (> 30 CEIT threshold)
    long_name = "PROF. ENGR. DAN JOSEPH A. ORTEGA, M.SC., PH.D."
    info = ClassInfo(
        instructor=long_name,
        subject="COSC 111",
        time_days_room="Wed: 11:00AM-01:00PM / LEC: OS",
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    t = body.findall(w("tbl"))[0]
    inst_cell = t.findall(w("tr"))[0].findall(w("tc"))[1]
    res = _extract_cell_run_properties(inst_cell)

    assert long_name in res["text"]
    assert res["font_name"] == "Georgia"
    assert res["sz"] == "28"  # 14pt preserved, NOT shrunk to 18 (9pt)
    assert len(inst_cell.findall(w("p"))) == 1


# ==============================================================================
# 3. Long Subject / Title
# ==============================================================================
def test_long_subject_does_not_shrink_prematurely(tmp_path):
    tmpl_path = str(tmp_path / "tmpl_long_subj.docx")
    out_path = str(tmp_path / "out_long_subj.docx")
    props = _create_custom_template_with_typography(tmpl_path, font_name="Georgia", font_pt=14)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    # 48 characters (> 40 CEIT threshold)
    long_subject = "COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)"
    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        subject=long_subject,
        time_days_room="Wed: 11:00AM-01:00PM / LEC: OS",
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    t = body.findall(w("tbl"))[0]
    subj_cell = t.findall(w("tr"))[1].findall(w("tc"))[1]
    res = _extract_cell_run_properties(subj_cell)

    assert long_subject in res["text"]
    assert res["font_name"] == "Century Gothic"
    assert res["sz"] == "24"  # 12pt preserved, NOT shrunk to 18 (9pt)
    assert len(subj_cell.findall(w("p"))) == 1


# ==============================================================================
# 4, 5, 6, 7, 8, 9, 10. Schedule Entries, Delimiters, and Continuous Paragraph
# ==============================================================================
@pytest.mark.parametrize(
    "entries,expected_count",
    [
        (["Wed: 11:00AM-01:00PM / LEC: OS"], 1),
        (["Wed: 11:00AM-01:00PM / LEC: OS", "Fri: 09:00AM-11:00AM / LAB: CCL 102"], 2),
        (["Mon: 08:00AM-10:00AM / LEC: CS 1", "Wed: 10:00AM-12:00PM / LAB: CCL 102", "Fri: 01:00PM-03:00PM / LEC: CS 2"], 3),
    ],
)
def test_schedule_entries_contract(tmp_path, entries, expected_count):
    tmpl_path = str(tmp_path / f"tmpl_sched_{expected_count}.docx")
    out_path = str(tmp_path / f"out_sched_{expected_count}.docx")
    _create_custom_template_with_typography(tmpl_path)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    sched_str = "; ".join(entries)
    instructor_name = "DAN JOSEPH A. ORTEGA"
    info = ClassInfo(
        instructor=instructor_name,
        subject="COSC 111",
        time_days_room=sched_str,
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    t = body.findall(w("tbl"))[0]
    sched_cell = t.findall(w("tr"))[2].findall(w("tc"))[1]

    # Requirement 4, 5, 6: Exactly one logical <w:p>
    paras = sched_cell.findall(w("p"))
    assert len(paras) == 1, f"Expected exactly 1 <w:p> in schedule cell, found {len(paras)}"
    sched_p = paras[0]

    # Requirement 7 & 8: Zero generated w:br and zero generated w:cr
    brs = sched_p.findall(".//" + w("br"))
    crs = sched_p.findall(".//" + w("cr"))
    assert len(brs) == 0, f"Expected 0 <w:br> in schedule paragraph, found {len(brs)}"
    assert len(crs) == 0, f"Expected 0 <w:cr> in schedule paragraph, found {len(crs)}"

    # Requirement 9: Entries separated by '; '
    full_sched_text = get_full_text(sched_p).strip()
    assert full_sched_text == sched_str
    assert "\n" not in full_sched_text
    assert "\r" not in full_sched_text
    if expected_count > 1:
        assert "; " in full_sched_text
        parts = full_sched_text.split("; ")
        assert len(parts) == expected_count

    # Requirement 10: Schedule does NOT contain instructor text (instructor is a separate field)
    assert instructor_name not in full_sched_text
    assert "ORTEGA" not in full_sched_text


# ==============================================================================
# 11 & 12. Non-default font family and font size preservation
# ==============================================================================
def test_non_default_font_family_and_size_preservation(tmp_path):
    tmpl_path = str(tmp_path / "tmpl_custom_fonts.docx")
    out_path = str(tmp_path / "out_custom_fonts.docx")
    _create_custom_template_with_typography(
        tmpl_path,
        font_name="Garamond",
        font_pt=16,
        bold=True,
        italic=True,
    )

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        subject="ADVANCED OPERATING SYSTEMS",
        time_days_room="Tue: 08:00AM-11:00AM / CS LAB",
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    t = body.findall(w("tbl"))[0]
    inst_cell = t.findall(w("tr"))[0].findall(w("tc"))[1]
    res = _extract_cell_run_properties(inst_cell)

    assert res["font_name"] == "Garamond"
    assert res["sz"] == "32"  # 16pt = 32 half-points
    assert res["bold"] is True
    assert res["italic"] is True


# ==============================================================================
# 13. Normal fields do not receive arbitrary 9pt fallback
# ==============================================================================
def test_normal_fields_do_not_receive_arbitrary_9pt_fallback(tmp_path):
    tmpl_path = str(tmp_path / "tmpl_normal_fields.docx")
    out_path = str(tmp_path / "out_normal_fields.docx")
    _create_custom_template_with_typography(tmpl_path, font_name="Georgia", font_pt=14)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        subject="COSC 111",
        time_days_room="Wed: 11:00AM-01:00PM / LEC: OS",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    t = body.findall(w("tbl"))[0]
    for row_idx, expected_sz in [(0, "28"), (1, "24"), (2, "22"), (3, "20")]:
        cell = t.findall(w("tr"))[row_idx].findall(w("tc"))[1]
        res = _extract_cell_run_properties(cell)
        assert res["sz"] != "18", f"Row {row_idx} incorrectly received arbitrary 9pt (sz='18')"
        assert res["sz"] == expected_sz


# ==============================================================================
# 14. Long student names retain controlled scaling behavior
# ==============================================================================
def test_student_name_controlled_scaling(tmp_path):
    tmpl_path = str(tmp_path / "tmpl_roster.docx")
    out_path = str(tmp_path / "out_roster.docx")
    _create_custom_template_with_typography(tmpl_path)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    short_name = "CRUZ, JUAN A."                          # 13 chars <= 32
    long_name = "CRISOSTOMO, NEIL ANGELO MARQUEZ JR."      # 35 chars > 32
    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        subject="COSC 111",
        students=[
            (short_name, "2026-0001"),
            (long_name, "2026-0002"),
        ],
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)

    zin, root, body = load_docx(out_path)
    r_tbl = body.findall(w("tbl"))[1]
    rows = r_tbl.findall(w("tr"))

    # Row 1 (short name)
    short_cell = rows[1].findall(w("tc"))[1]
    res_short = _extract_cell_run_properties(short_cell)
    assert short_name in res_short["text"]
    assert res_short["sz"] == "20"  # 10pt base font preserved

    # Row 2 (long name)
    long_cell = rows[2].findall(w("tc"))[1]
    res_long = _extract_cell_run_properties(long_cell)
    assert long_name in res_long["text"]
    assert res_long["sz"] == "18"  # Scaled down to 9pt


# ==============================================================================
# 15. Existing custom-template generation remains compatible
# ==============================================================================
def test_existing_custom_templates_remain_compatible(tmp_path):
    existing_tmpl = os.path.join(TEST_TEMPLATES_DIR, "template_laboratory_monitoring.docx")
    assert os.path.exists(existing_tmpl), f"Template must exist at {existing_tmpl}"

    out_path = str(tmp_path / "out_lab_monitoring.docx")
    inspector = DocxTemplateInspector()
    cand = inspector.inspect(existing_tmpl, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        course_section="BSCS 4-1",
        schedule_code="12345",
        subject="COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)",
        time_days_room="Wed: 11:00AM-01:00PM / LEC: OS / ORTEGA; Fri: 09:00AM-11:00AM / LAB: CCL 102 / ORTEGA",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        students=[("Aquino, Benigno C.", "202110443")],
    )

    gen = ConfigurableDocumentGenerator(existing_tmpl, recipe)
    gen.generate(info, out_path)
    assert os.path.exists(out_path)

    zin, root, body = load_docx(out_path)
    tables = body.findall(w("tbl"))
    assert len(tables) >= 2


# ==============================================================================
# 16. Section 8 Real-Generation Case
# ==============================================================================
def test_section_8_real_generation_case(tmp_path):
    """
    Generate an actual custom document with exact specified parameters:
    - Course Code & Title: COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)
    - Class Schedule: Wed: 11:00AM-01:00PM / LEC: OS / ORTEGA; Fri: 09:00AM-11:00AM / LAB: CCL 102 / ORTEGA
    - Semester & AY: FIRST SEMESTER, AY 2026 - 2027
    - Instructor: DAN JOSEPH A. ORTEGA

    Verify:
    - schedule remains one logical paragraph;
    - no explicit line-break elements are generated;
    - separator remains '; ';
    - source font family is preserved;
    - source font size is preserved when content fits;
    - unnecessary shrinking does not occur;
    - custom cell/table structure remains intact.
    """
    tmpl_path = str(tmp_path / "tmpl_real_generation.docx")
    out_path = str(tmp_path / "out_real_generation.docx")

    # Capture source template font properties before generation
    source_props = _create_custom_template_with_typography(
        tmpl_path,
        font_name="Georgia",
        font_pt=14,
        bold=False,
        italic=False,
    )

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    course_title = "COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)"
    class_sched = "Wed: 11:00AM-01:00PM / LEC: OS; Fri: 09:00AM-11:00AM / LAB: CCL 102"
    semester_ay = "FIRST SEMESTER, AY 2026 - 2027"
    instructor_name = "DAN JOSEPH A. ORTEGA"

    info = ClassInfo(
        instructor=instructor_name,
        course_section="BSCS 4-1",
        schedule_code="12345",
        subject=course_title,
        time_days_room=class_sched,
        semester_ay=semester_ay,
        students=[("Sample Student", "2026-0001")],
    )

    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    gen.generate(info, out_path)
    assert os.path.exists(out_path)

    # Direct XML Inspection
    zin, root, body = load_docx(out_path)
    tables = body.findall(w("tbl"))
    assert len(tables) == 2, "Custom table structure intact (2 tables)"

    hdr_tbl = tables[0]
    rows = hdr_tbl.findall(w("tr"))
    assert len(rows) == 4, "Header table maintains 4 rows"

    # 1. Schedule Cell Verification
    sched_cell = rows[2].findall(w("tc"))[1]
    sched_paras = sched_cell.findall(w("p"))
    assert len(sched_paras) == 1, "Schedule remains exactly one logical paragraph"
    sched_p = sched_paras[0]

    # No explicit line-break elements generated
    assert len(sched_p.findall(".//" + w("br"))) == 0, "No w:br elements generated"
    assert len(sched_p.findall(".//" + w("cr"))) == 0, "No w:cr elements generated"

    # Separator remains '; '
    sched_text = get_full_text(sched_p).strip()
    assert sched_text == class_sched
    assert "\n" not in sched_text
    assert "\r" not in sched_text
    assert "; " in sched_text
    parts = sched_text.split("; ")
    assert len(parts) == 2
    assert parts[0] == "Wed: 11:00AM-01:00PM / LEC: OS"
    assert parts[1] == "Fri: 09:00AM-11:00AM / LAB: CCL 102"

    # Proof that instructor name appears only in the instructor field and NOT in schedule
    assert instructor_name not in sched_text
    assert "ORTEGA" not in sched_text

    # 2. Source Font Family & Size Preservation (before vs after comparison)
    # Instructor
    inst_cell = rows[0].findall(w("tc"))[1]
    inst_props = _extract_cell_run_properties(inst_cell)
    assert instructor_name in inst_props["text"]
    assert inst_props["font_name"] == source_props["instructor"]["font_name"], "Instructor font family preserved"
    assert inst_props["sz"] == source_props["instructor"]["sz_val"], "Instructor font size preserved without shrinking"

    # Course Code & Title
    subj_cell = rows[1].findall(w("tc"))[1]
    subj_props = _extract_cell_run_properties(subj_cell)
    assert course_title in subj_props["text"]
    assert instructor_name not in subj_props["text"]
    assert subj_props["font_name"] == source_props["subject"]["font_name"], "Subject font family preserved"
    assert subj_props["sz"] == source_props["subject"]["sz_val"], "Subject font size preserved without shrinking"

    # Class Schedule
    sched_props = _extract_cell_run_properties(sched_cell)
    assert sched_props["font_name"] == source_props["time_days_room"]["font_name"], "Schedule font family preserved"
    assert sched_props["sz"] == source_props["time_days_room"]["sz_val"], "Schedule font size preserved without shrinking"

    # Semester & AY
    sem_cell = rows[3].findall(w("tc"))[1]
    sem_props = _extract_cell_run_properties(sem_cell)
    assert semester_ay in sem_props["text"]
    assert instructor_name not in sem_props["text"]
    assert sem_props["font_name"] == source_props["semester_ay"]["font_name"], "Semester font family preserved"
    assert sem_props["sz"] == source_props["semester_ay"]["sz_val"], "Semester font size preserved without shrinking"


# ==============================================================================
# 17. Custom Template Routing and Lifecycle Regression
# ==============================================================================
def test_custom_template_routing_and_lifecycle(tmp_path):
    from modules.common.config_manager import ParserConfigManager

    cfg_dir = str(tmp_path / "config")
    mgr = ParserConfigManager(config_dir=cfg_dir)

    tmpl_path = str(tmp_path / "tmpl_lifecycle.docx")
    _create_custom_template_with_typography(tmpl_path)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(tmpl_path, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)
    recipe_dict = recipe.to_dict()
    recipe_dict["metadata"] = {"output_folder": "Advising_Logs"}

    save_res = mgr.save_custom_template(
        source_path=tmpl_path,
        title="Lifecycle Custom Form",
        suffix="LIFECYCLE_FORM",
        recipe=recipe_dict,
        enabled=True,
    )
    assert save_res["status"] == "success"

    templates = mgr.get_custom_templates()
    assert len(templates) == 1
    assert templates[0]["recipe"]["metadata"]["output_folder"] == "Advising_Logs"

    # Generator output_folder property
    recipe = recipe.with_metadata({"output_folder": "Advising_Logs"})
    gen = ConfigurableDocumentGenerator(tmpl_path, recipe)
    assert gen.output_folder == "Advising_Logs"


# ==============================================================================
# 18. Native Attendance Regression (Section 10)
# ==============================================================================
def test_native_attendance_regression(tmp_path):
    """
    Verify native attendance templates (template lec.docx, template lab and lec.docx)
    continue to use native attendance engine without regression.
    """
    import attendancegen

    lec_tmpl = os.path.join(REPO_ROOT, "attendance", "template lec.docx")
    assert os.path.exists(lec_tmpl), "Native attendance lec template must exist"

    course_title = "COSC 101 - ADVANCED SOFTWARE ENGINEERING"
    class_sched = "Wed: 09:00AM-11:00AM / ITC 501; Fri: 01:00PM-03:00PM / CCL 102"
    semester_ay = "1st Semester / 2026-2027"
    room_assignment = "ITC 501 / CCL 102"
    instructor = "DAN JOSEPH A. ORTEGA"
    months = [9]
    year = 2026
    weekdays = [2, 4]  # Wed=2, Fri=4
    students = [("CRUZ, JUAN A.", "2026-0001")]

    out_path = str(tmp_path / "out_native_attendance.docx")
    attendancegen.build_attendance_sheet(
        template_path=lec_tmpl,
        output_path=out_path,
        course_code_title=course_title,
        class_schedule=class_sched,
        semester_ay=semester_ay,
        room_assignment=room_assignment,
        instructor=instructor,
        months=months,
        year=year,
        weekdays=weekdays,
        students=students,
    )
    assert os.path.exists(out_path)

    zin, root, body = load_docx(out_path)
    tables = body.findall(w("tbl"))
    assert len(tables) >= 2
    info_tbl = tables[0]
    info_rows = info_tbl.findall(w("tr"))
    sched_p = info_rows[1].findall(w("tc"))[1].find(w("p"))
    sched_text = get_full_text(sched_p).strip()
    assert "; " in sched_text


# ==============================================================================
# 19. Native CEIT Regression (Section 11)
# ==============================================================================
def test_native_ceit_regression(tmp_path):
    """
    Verify native CEIT templates preserve native CEIT FIELD_SHRINK_THRESHOLDS
    and continue to generate with complete output parity.
    """
    from modules.services.template_recipe_service import TemplateRecipeResolver
    from modules.generators.ceit_gen import SyllabusGenerator

    syllabus_tmpl = os.path.join(REPO_ROOT, "templates", "template_syllabus.docx")
    assert os.path.exists(syllabus_tmpl), "Native CEIT syllabus template must exist"

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(syllabus_tmpl, profile_id="academic_docx")

    # Verify native CEIT retains FIELD_SHRINK_THRESHOLDS
    assert recipe.header_bindings["instructor"].shrink_threshold == 30
    assert recipe.header_bindings["subject"].shrink_threshold == 40

    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        course_section="BSCS 1-4",
        schedule_code="202522383",
        subject="ITEC50 - WEB SYSTEMS AND TECHNOLOGY",
        time_days_room="10:00AM-12:00AM / M / CCL 305",
        semester_ay="2nd Semester / 2025-2026",
        students=[("ALVAREZ, MARIA C.", "202310001")],
    )

    out_path = str(tmp_path / "out_ceit_syllabus.docx")
    gen = SyllabusGenerator(syllabus_tmpl, recipe)
    gen.generate(info, out_path)
    assert os.path.exists(out_path)
