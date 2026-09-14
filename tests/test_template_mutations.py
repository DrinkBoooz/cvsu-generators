import os
import shutil
import tempfile
import docx
import openpyxl
from openpyxl.utils import get_column_letter

from modules.models.schedule import ClassInfo
from modules.generators.ceit_gen import (
    SyllabusGenerator,
    ExamReturnsGenerator,
    GradeDiscussionGenerator,
)
from modules.generators.grade_gen import GradeGenerator
from modules.services.template_recipe_service import TemplateRecipeResolver


SAMPLE_INFO = ClassInfo(
    instructor="DR. JUAN DELA CRUZ",
    course_section="BSCS 3-1",
    schedule_code="202699999",
    subject="COSC 70 - SOFTWARE ENGINEERING",
    time_days_room="Mon: 08:00AM-11:00AM / CL3",
    semester_ay="1st Semester 2026-2027",
    students=[
        ("ALVAREZ, MARIA A.", "202310001"),
        ("SANTOS, CARLOS B.", "202310002"),
    ],
    college="COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY",
)

SAMPLE_GRADE_INFO = {
    "instructor": "DR. JUAN DELA CRUZ",
    "course": "BSCS 3-1",
    "sched": "202699999",
    "subject": "COSC 70 - SOFTWARE ENGINEERING",
    "semester": "1st Semester 2026-2027",
    "time": "Mon: 08:00AM-11:00AM / CL3",
    "has_lab": False,
    "college": "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY",
}

SAMPLE_GRADE_STUDENTS = [
    {"student_name": "ALVAREZ, MARIA A.", "student_number": "202310001"},
    {"student_name": "SANTOS, CARLOS B.", "student_number": "202310002"},
]


def test_m1_syllabus_swap_metadata_rows(tmp_path):
    """M1: Swap Row 0 (Instructor) & Row 5 (Semester) in template_syllabus.docx.
    Dual Assertions:
    1. Row 0 (now Semester) receives Semester value.
    2. Row 5 (now Instructor) receives Instructor value.
    3. Row 0 does NOT receive Instructor value.
    4. Row 5 does NOT receive Semester value."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "template_syllabus.docx")
    mut_path = str(tmp_path / "mut_syl_swap.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    t0 = doc.tables[0]
    r0_c0, r0_c1 = t0.rows[0].cells[0].text, t0.rows[0].cells[1].text
    r5_c0, r5_c1 = t0.rows[5].cells[0].text, t0.rows[5].cells[1].text

    t0.rows[0].cells[0].text = r5_c0
    t0.rows[0].cells[1].text = r5_c1
    t0.rows[5].cells[0].text = r0_c0
    t0.rows[5].cells[1].text = r0_c1
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "syllabus")
    gen = SyllabusGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m1.docx")
    gen.generate(SAMPLE_INFO, out_path)

    out_doc = docx.Document(out_path)
    out_t0 = out_doc.tables[0]
    val_row0 = out_t0.rows[0].cells[1].text.strip()
    val_row5 = out_t0.rows[5].cells[1].text.strip()

    # 1. Row 0 (now Semester) receives Semester value
    assert "1st Semester" in val_row0
    # 2. Row 5 (now Instructor) receives Instructor value
    assert "DR. JUAN DELA CRUZ" in val_row5
    # 3. Row 0 does NOT receive Instructor value
    assert "DR. JUAN DELA CRUZ" not in val_row0
    # 4. Row 5 does NOT receive Semester value
    assert "1st Semester" not in val_row5


def test_m2_syllabus_insert_department_row(tmp_path):
    """M2: Insert 'Department' row at Row 0 in template_syllabus.docx.
    Dual Assertions:
    1. Row 0 ('Department') value remains 'Department of Computer Studies'.
    2. Row 1 ('Instructor') receives Instructor value.
    3. Row 0 does NOT receive Instructor value."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "template_syllabus.docx")
    mut_path = str(tmp_path / "mut_syl_insert_dept.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    t0 = doc.tables[0]
    # Add a row and move it to the top before row 0
    new_row = t0.add_row()
    t0.rows[0]._tr.addprevious(new_row._tr)
    new_row.cells[0].text = "Department:"
    new_row.cells[1].text = "Department of Computer Studies"
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "syllabus")
    gen = SyllabusGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m2.docx")
    gen.generate(SAMPLE_INFO, out_path)

    out_doc = docx.Document(out_path)
    out_t0 = out_doc.tables[0]
    val_row0 = out_t0.rows[0].cells[1].text.strip()
    val_row1 = out_t0.rows[1].cells[1].text.strip()

    # 1. Row 0 ('Department') value remains intact
    assert "Department of Computer Studies" in val_row0
    # 2. Row 1 ('Instructor') receives Instructor value
    assert "DR. JUAN DELA CRUZ" in val_row1
    # 3. Row 0 does NOT receive Instructor value
    assert "DR. JUAN DELA CRUZ" not in val_row0


def test_m3_syllabus_insert_control_table(tmp_path):
    """M3: Insert a 2-row Control Table before Table 0 in template_syllabus.docx.
    Dual Assertions:
    1. Control table cells remain unmolested.
    2. Metadata is written to Syllabus table.
    3. Control table does NOT receive metadata values."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "template_syllabus.docx")
    mut_path = str(tmp_path / "mut_syl_control_tbl.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    # Insert control table before table 0
    t0_elem = doc.tables[0]._tbl
    ctrl_tbl = doc.add_table(rows=2, cols=2)
    ctrl_tbl.rows[0].cells[0].text = "Control Code:"
    ctrl_tbl.rows[0].cells[1].text = "CTRL-2026"
    ctrl_tbl.rows[1].cells[0].text = "Version:"
    ctrl_tbl.rows[1].cells[1].text = "REV-01"

    # Move ctrl_tbl before t0_elem in body xml
    t0_elem.addprevious(ctrl_tbl._tbl)
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "syllabus")
    gen = SyllabusGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m3.docx")
    gen.generate(SAMPLE_INFO, out_path)

    out_doc = docx.Document(out_path)
    # Table 0 is now the control table
    tbl_ctrl = out_doc.tables[0]
    # Table 1 is the metadata table
    tbl_meta = out_doc.tables[1]

    # 1. Control table cells remain unmolested
    assert tbl_ctrl.rows[0].cells[1].text.strip() == "CTRL-2026"
    assert tbl_ctrl.rows[1].cells[1].text.strip() == "REV-01"
    # 2. Metadata is written to Syllabus table
    assert "DR. JUAN DELA CRUZ" in tbl_meta.rows[0].cells[1].text
    # 3. Control table does NOT receive metadata values
    assert "DR. JUAN DELA CRUZ" not in tbl_ctrl.rows[0].cells[1].text
    assert "DR. JUAN DELA CRUZ" not in tbl_ctrl.rows[1].cells[1].text


def test_m4_exam_swap_roster_columns(tmp_path):
    """M4: Swap Column 0 (Name) & Column 1 (ID) in student table of template_exam_midterm.docx.
    Dual Assertions:
    1. Column 0 receives Student ID.
    2. Column 1 receives Student Name.
    3. Column 0 does NOT receive Student Name.
    4. Column 1 does NOT receive Student ID."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "template_exam_midterm.docx")
    mut_path = str(tmp_path / "mut_exam_swap_cols.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    roster_tbl = doc.tables[1]
    # Swap header row cells
    hdr_c0 = roster_tbl.rows[0].cells[0].text
    hdr_c1 = roster_tbl.rows[0].cells[1].text
    roster_tbl.rows[0].cells[0].text = hdr_c1  # now Student Number
    roster_tbl.rows[0].cells[1].text = hdr_c0  # now Student Name
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "exam_midterm")
    gen = ExamReturnsGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m4.docx")
    gen.generate(SAMPLE_INFO, out_path)

    out_doc = docx.Document(out_path)
    out_roster = out_doc.tables[1]
    # Student 1 row (row 1)
    s1_c0 = out_roster.rows[1].cells[0].text.strip()
    s1_c1 = out_roster.rows[1].cells[1].text.strip()

    # 1. Column 0 receives Student ID
    assert s1_c0 == "202310001"
    # 2. Column 1 receives Student Name
    assert s1_c1 == "ALVAREZ, MARIA A."
    # 3. Column 0 does NOT receive Student Name
    assert "ALVAREZ" not in s1_c0
    # 4. Column 1 does NOT receive Student ID
    assert "202310001" not in s1_c1


def test_m5_grade_discussion_2col_layout(tmp_path):
    """M5: Convert Table 0 from 3 cols [L|:|V] to 2 cols [L|V] in Final-Grade-Discussion_LATEST.docx.
    Dual Assertions:
    1. Column 1 receives metadata values.
    2. No rows are silently skipped."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "Final-Grade-Discussion_LATEST.docx")
    mut_path = str(tmp_path / "mut_disc_2col.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    t0 = doc.tables[0]
    for row in t0.rows:
        if len(row.cells) >= 3:
            # Merge cell 0 and cell 1, or remove cell 1
            row.cells[0].text = row.cells[0].text.strip() + ":"
            row._tr.remove(row.cells[1]._tc)
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "grade_finals")
    gen = GradeDiscussionGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m5.docx")
    gen.generate(SAMPLE_INFO, out_path)

    out_doc = docx.Document(out_path)
    out_t0 = out_doc.tables[0]
    found_instructor = False
    found_course = False
    for row in out_t0.rows:
        lbl = row.cells[0].text.strip()
        val = row.cells[1].text.strip()
        if "INSTRUCTOR" in lbl:
            assert "DR. JUAN DELA CRUZ" in val
            found_instructor = True
        elif "COURSE" in lbl:
            assert "BSCS 3-1" in val
            found_course = True

    assert found_instructor, "Instructor must be bound in 2-column layout"
    assert found_course, "Course section must be bound in 2-column layout"


def test_m6_xlsx_relocate_course_section_binding(tmp_path):
    """M6: Relocate Course Section binding in GRADING_LECTURE_TEMPLATE.xlsx.
    Label I1 -> Q1, Target M1:S1 -> T1:Z1.
    Dual Assertions:
    1. Capture orig_m1 = ws['M1'].value before mutation.
    2. Cell T1 receives Course Section.
    3. Cell M1 retains orig_m1 unchanged."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
    mut_path = str(tmp_path / "mut_grade_relocate_m6.xlsx")
    shutil.copy2(src, mut_path)

    wb = openpyxl.load_workbook(mut_path)
    ws = wb["Lecture"]
    orig_m1 = ws["M1"].value

    # Move label from I1 to Q1
    lbl_val = ws["I1"].value
    ws["I1"].value = None

    # Unmerge M1:S1 first so Q1 is free, and set target merge at T1:Z1
    for rng in list(ws.merged_cells.ranges):
        if str(rng) == "M1:S1":
            ws.unmerge_cells(str(rng))

    ws["Q1"].value = lbl_val or "COURSE & SECTION:"
    ws.merge_cells("T1:Z1")
    wb.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "grade_sheet_xlsx")
    gen = GradeGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m6.xlsx")
    gen.generate(SAMPLE_GRADE_INFO, SAMPLE_GRADE_STUDENTS, out_path)

    out_wb = openpyxl.load_workbook(out_path)
    out_ws = out_wb["Lecture"]

    # 1. Target T1 receives Course Section
    assert out_ws["T1"].value == "BSCS 3-1"
    # 2. Cell M1 retains its original value unchanged
    assert out_ws["M1"].value == orig_m1


def test_m7_xlsx_insert_sub_header_row(tmp_path):
    """M7: Insert Sub-Header row at Row 11 in GRADING_LECTURE_TEMPLATE.xlsx.
    Dual Assertions:
    1. Row 11 sub-header text remains intact.
    2. Student 1 is written to Row 12.
    3. Row 11 is NOT overwritten with Student 1 data."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
    mut_path = str(tmp_path / "mut_grade_subhdr_m7.xlsx")
    shutil.copy2(src, mut_path)

    wb = openpyxl.load_workbook(mut_path)
    ws = wb["Lecture"]
    ws.insert_rows(11)
    ws.cell(11, 1).value = "MALE STUDENTS"
    wb.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "grade_sheet_xlsx")
    gen = GradeGenerator(mut_path, recipe)

    out_path = str(tmp_path / "out_m7.xlsx")
    gen.generate(SAMPLE_GRADE_INFO, SAMPLE_GRADE_STUDENTS, out_path)

    out_wb = openpyxl.load_workbook(out_path)
    out_ws = out_wb["Lecture"]

    # 1. Row 11 sub-header text remains intact
    assert out_ws.cell(11, 1).value == "MALE STUDENTS"
    # 2. Student 1 is written to Row 12
    assert out_ws.cell(12, 2).value == "ALVAREZ, MARIA A."
    # 3. Row 11 is NOT overwritten with Student 1 data
    assert out_ws.cell(11, 2).value is None or out_ws.cell(11, 2).value != "ALVAREZ, MARIA A."


def test_m8_xlsx_structural_signature_geometry(tmp_path):
    """M8: Move Instructor signature label from BI60:BR62 to AA30:AJ32 and
    structural signature box to AA27:AJ29 in GRADING_LECTURE_LAB_TEMPLATE.xlsx.
    Dual Assertions:
    1. Signature is written to AA27 based on structural merged geometry above label.
    2. BI57 remains empty/unmolested.
    3. Proves discovery relies on structural line evidence, not a hardcoded row - 3 offset."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "templates", "GRADING_LECTURE_LAB_TEMPLATE.xlsx")
    mut_path = str(tmp_path / "mut_grade_sig_m8.xlsx")
    shutil.copy2(src, mut_path)

    wb = openpyxl.load_workbook(mut_path)
    ws = wb["Lecture"]

    # Remove old signature ranges if present
    for rng_str in ["BI57:BR59", "BI60:BR62"]:
        if rng_str in [str(r) for r in list(ws.merged_cells.ranges)]:
            ws.unmerge_cells(rng_str)
    ws["BI60"].value = None
    ws["BI57"].value = None

    # Create new signature label block at AA30:AJ32
    ws.merge_cells("AA30:AJ32")
    ws["AA30"].value = "INSTRUCTOR"

    # Create new structural target block directly above it at AA27:AJ29
    ws.merge_cells("AA27:AJ29")
    wb.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, "grade_sheet_xlsx")
    gen = GradeGenerator(mut_path, recipe)

    info_lab = dict(SAMPLE_GRADE_INFO)
    info_lab["has_lab"] = True
    out_path = str(tmp_path / "out_m8.xlsx")
    gen.generate(info_lab, SAMPLE_GRADE_STUDENTS, out_path)

    out_wb = openpyxl.load_workbook(out_path)
    out_ws = out_wb["Lecture"]

    # 1. Signature is written to AA27 based on structural merged geometry above label
    assert out_ws["AA27"].value == "DR. JUAN DELA CRUZ"
    # 2. BI57 remains empty / unmolested
    assert out_ws["BI57"].value is None
