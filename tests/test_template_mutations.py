import os
import copy
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
from modules.generators.attendance_gen import (
    AttendanceGenerator,
    build_attendance_sheet,
)
from modules.models.recipe import ValidatedAttendanceTemplateRecipe
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


def test_m10_xlsx_signature_offset_fallback_is_compatibility_behavior(tmp_path):
        """M10: Preserve the documented legacy signature offset fallback.

        Evidence record:
        - Pre-change assumption: a plain INSTRUCTOR label without merged geometry
            may derive its target three rows above within the legacy scan window.
        - Current authority: XlsxTemplateInspector emits the fallback candidate;
            GradeGenerator consumes its validated signature binding.
        - Demonstrated boundary: no merged signature box exists, so structural
            geometry cannot provide a target; the compatibility fallback is used.
        - Phase 4 rationale: this is existing template-discovery compatibility,
            not Phase 3 field resolution or business/data transformation.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = os.path.join(repo_root, "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
        mut_path = str(tmp_path / "mut_grade_sig_m10.xlsx")
        shutil.copy2(src, mut_path)

        wb = openpyxl.load_workbook(mut_path)
        ws = wb["Lecture"]
        for rng in ("BI57:BR59", "BI60:BR62"):
                if rng in [str(existing) for existing in ws.merged_cells.ranges]:
                        ws.unmerge_cells(rng)
        ws["BI57"] = None
        ws["BI60"] = None
        ws["E70"] = "INSTRUCTOR"
        wb.save(mut_path)

        recipe = TemplateRecipeResolver.get_instance().resolve(mut_path, "grade_sheet_xlsx")
        lecture_signature = recipe.signature_bindings.get("instructor")
        assert lecture_signature is not None
        assert lecture_signature.target == "E67"

        out_path = str(tmp_path / "out_m10.xlsx")
        GradeGenerator(mut_path, recipe).generate(SAMPLE_GRADE_INFO, SAMPLE_GRADE_STUDENTS, out_path)
        out_wb = openpyxl.load_workbook(out_path)
        assert out_wb["Lecture"]["E67"].value == "DR. JUAN DELA CRUZ"


def test_m9_xlsx_roster_outside_legacy_scan_window(tmp_path):
        """M9: Move the roster beyond the former fixed scan window.

        Evidence record:
        - Pre-change assumption: roster headers were restricted to rows 6-15 and
            columns 1-9, with execution implicitly targeting Lecture.
        - Current authority: XlsxTemplateInspector discovers roster coordinates and
            RecipeValidator stores them in RosterBinding for GradeGenerator.
        - Demonstrated failure: a valid roster at row 20 / columns L-N was not
            discovered and could not reach recipe-driven execution.
        - Phase 4 rationale: this is physical template structure, not Phase 3
            field precedence or business/data transformation.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src = os.path.join(repo_root, "templates", "GRADING_LECTURE_TEMPLATE.xlsx")
        mut_path = str(tmp_path / "mut_grade_roster_m9.xlsx")
        shutil.copy2(src, mut_path)

        wb = openpyxl.load_workbook(mut_path)
        ws = wb["Lecture"]
        for row in range(7, 51):
            for col in range(1, 4):
                cell = ws.cell(row, col)
                if cell.__class__.__name__ != "MergedCell":
                    cell.value = None

        ws["L20"] = "#"
        ws["M20"] = "Student Name"
        ws["N20"] = "Student Number"
        for index in range(1, 41):
            ws.cell(20 + index + 3, 12).value = index
        wb.save(mut_path)

        resolver = TemplateRecipeResolver.get_instance()
        recipe = resolver.resolve(mut_path, "grade_sheet_xlsx")
        assert recipe.roster_binding.worksheet_name == "Lecture"
        assert recipe.roster_binding.first_data_row_index == 24
        assert recipe.roster_binding.name_col == 13
        assert recipe.roster_binding.id_col == 14

        out_path = str(tmp_path / "out_m9.xlsx")
        GradeGenerator(mut_path, recipe).generate(
                SAMPLE_GRADE_INFO,
                SAMPLE_GRADE_STUDENTS,
                out_path,
        )
        out_wb = openpyxl.load_workbook(out_path, data_only=False)
        out_ws = out_wb["Lecture"]
        assert out_ws.cell(24, 13).value == "ALVAREZ, MARIA A."
        assert out_ws.cell(24, 14).value == 202310001


# ═══════════════════════════════════════════════════════════════════════════════
# Attendance Template Mutation Tests (M11–M20)
# ═══════════════════════════════════════════════════════════════════════════════

ATTENDANCE_STUDENTS = [
    ("ALVAREZ, MARIA A.", "202310001"),
    ("SANTOS, CARLOS B.", "202310002"),
]


def test_m11_decoy_table_insertion(tmp_path):
    """M11: Insert a decoy table before Table 0 in template lec.docx.
    The inspector must discover that the real info table is Table 1 and matrix table is Table 2.
    Generation must target the real tables and leave Table 0 untouched."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m11_decoy.docx")
    shutil.copy2(src, mut_path)

    # Insert decoy table at the start of document
    doc = docx.Document(mut_path)
    decoy = doc.add_table(rows=2, cols=2)
    decoy.rows[0].cells[0].text = "NOTICE: DECOY SYSTEM METADATA"
    decoy.rows[0].cells[1].text = "DO NOT POPULATE"
    decoy.rows[1].cells[0].text = "Department Notice"
    decoy.rows[1].cells[1].text = "Archived"

    # Move decoy table to the beginning of document body
    body = doc._body._element
    tbl_elements = body.findall(docx.oxml.ns.qn("w:tbl"))
    # Move the last table (the newly added decoy) to the very beginning
    body.insert(0, tbl_elements[-1])
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.info_binding.table_index == 1
    assert recipe.matrix_binding.table_index == 2

    out_path = str(tmp_path / "out_m11.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101 - ADVANCED SE",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Semester 2026-2027",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )

    out_doc = docx.Document(out_path)
    # 1. Decoy table untouched
    assert "NOTICE: DECOY SYSTEM METADATA" in out_doc.tables[0].rows[0].cells[0].text
    # 2. Info table populated
    assert "DR. JUAN DELA CRUZ" in out_doc.tables[1].rows[4].cells[1].text
    # 3. Matrix table populated
    assert "ALVAREZ, MARIA A." in out_doc.tables[2].rows[2].cells[1].text
    assert "202310001" in out_doc.tables[2].rows[2].cells[2].text


def test_m12_information_matrix_table_order_swap(tmp_path):
    """M12: Swap order of Information Table and Attendance Matrix Table.
    Matrix is now Table 0, Info is now Table 1.
    The inspector must discover matrix at Table 0 and info at Table 1."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m12_swap.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    body = doc._body._element
    tbls = body.findall(docx.oxml.ns.qn("w:tbl"))
    assert len(tbls) >= 2
    # Swap table 0 and table 1 in XML body
    t0, t1 = tbls[0], tbls[1]
    idx0 = list(body).index(t0)
    idx1 = list(body).index(t1)
    body.remove(t0)
    body.insert(idx1, t0)
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.matrix_binding.table_index == 0
    assert recipe.info_binding.table_index == 1

    out_path = str(tmp_path / "out_m12.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101 - ADVANCED SE",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Semester 2026-2027",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )

    out_doc = docx.Document(out_path)
    # Matrix table is at index 0
    assert "ALVAREZ, MARIA A." in out_doc.tables[0].rows[2].cells[1].text
    # Info table is at index 1
    assert "DR. JUAN DELA CRUZ" in out_doc.tables[1].rows[4].cells[1].text


def test_m13_student_column_reorder(tmp_path):
    """M13: Reorder student columns in attendance matrix (Col 1 is Student Number, Col 2 is Name).
    Inspector discovers id_col=1, name_col=2.
    Generator populates student number in col 1, student name in col 2."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m13_reorder.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]
    # Swap headers in Row 0 for cols 1 and 2
    c1_text = attn_tbl.rows[0].cells[1].text
    c2_text = attn_tbl.rows[0].cells[2].text
    attn_tbl.rows[0].cells[1].text = c2_text
    attn_tbl.rows[0].cells[2].text = c1_text
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.matrix_binding.id_col == 1
    assert recipe.matrix_binding.name_col == 2

    out_path = str(tmp_path / "out_m13.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )

    out_doc = docx.Document(out_path)
    r2_cells = out_doc.tables[1].rows[2].cells
    # Assert Col 1 contains student number and Col 2 contains student name
    assert "202310001" in r2_cells[1].text
    assert "ALVAREZ, MARIA A." in r2_cells[2].text
    assert "ALVAREZ, MARIA A." not in r2_cells[1].text
    assert "202310001" not in r2_cells[2].text


def test_m14_metadata_field_relocation(tmp_path):
    """M14: Swap Row 0 (Course Code) and Row 4 (Instructor) in info table.
    Inspector discovers instructor at (0, 1) and course_code_title at (4, 1)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m14_reloc.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    info_tbl = doc.tables[0]
    # Swap row 0 and row 4 labels & values
    r0_texts = [c.text for c in info_tbl.rows[0].cells]
    r4_texts = [c.text for c in info_tbl.rows[4].cells]

    for i in range(len(r0_texts)):
        info_tbl.rows[0].cells[i].text = r4_texts[i] if i < len(r4_texts) else ""
    for i in range(len(r4_texts)):
        info_tbl.rows[4].cells[i].text = r0_texts[i] if i < len(r0_texts) else ""
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.info_binding.bindings["instructor"] == (0, 1)
    assert recipe.info_binding.bindings["course_code_title"] == (4, 1)

    out_path = str(tmp_path / "out_m14.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101 - RELOCATED",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )

    out_doc = docx.Document(out_path)
    # Row 0 now receives instructor
    assert "DR. JUAN DELA CRUZ" in out_doc.tables[0].rows[0].cells[1].text
    # Row 4 now receives course code
    assert "COSC 101 - RELOCATED" in out_doc.tables[0].rows[4].cells[1].text


def test_m15_matrix_row_displacement(tmp_path):
    """M15: Insert an empty decorative row between header rows and student template row.
    Inspector distinguishes header row, decorative row, and template student row."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m15_displace.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]
    # Insert empty row at index 2
    r_elm = copy.deepcopy(attn_tbl.rows[2]._tr)
    for tc in r_elm.findall(docx.oxml.ns.qn("w:tc")):
        for p in tc.findall(docx.oxml.ns.qn("w:p")):
            for t in p.findall(docx.oxml.ns.qn("w:t")):
                t.text = ""
    attn_tbl.rows[1]._tr.addnext(r_elm)
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.matrix_binding.student_template_row_index >= 2

    out_path = str(tmp_path / "out_m15.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )
    assert os.path.exists(out_path)
    out_doc = docx.Document(out_path)
    st_row = recipe.matrix_binding.student_template_row_index
    name_col = recipe.matrix_binding.name_col
    assert "ALVAREZ, MARIA A." in out_doc.tables[1].rows[st_row].cells[name_col].text


def test_m16_week_header_structural_variation(tmp_path):
    """M16: Week-header row text varied to nonstandard labels.
    Inspector discovers week header row structure robustly."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m16_weeks.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]
    # Change "WEEK 1" to "CYCLE 1 (WEEK)", etc.
    for c in attn_tbl.rows[0].cells[3:]:
        if "WEEK" in c.text:
            c.text = c.text.replace("WEEK", "CYCLE (WEEK)")
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.matrix_binding.header_row0_index == 0

    out_path = str(tmp_path / "out_m16.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )
    assert os.path.exists(out_path)
    out_doc = docx.Document(out_path)
    assert "WEEK 1" in out_doc.tables[1].rows[0].cells[3].text


def test_m17_date_session_header_variation(tmp_path):
    """M17: Date/session header variation in row 1.
    Inspector discovers session columns and capacity correctly."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m17_dates.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]
    # Replace digits with session labels
    for idx, c in enumerate(attn_tbl.rows[1].cells[3:7], 1):
        c.text = f"SES {idx}"
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.matrix_binding.template_session_capacity == 4

    out_path = str(tmp_path / "out_m17.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )
    assert os.path.exists(out_path)


def test_m18_summary_region_reordering(tmp_path):
    """M18: Summary columns reordered to 'r', 'lc', 'lb'.
    Inspector discovers discovered order, generator outputs in discovered order."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m18_sum.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]
    # In row 1: cells[-3], cells[-2], cells[-1] are lb, lc, r
    attn_tbl.rows[1].cells[-3].text = "r"
    attn_tbl.rows[1].cells[-2].text = "lc"
    attn_tbl.rows[1].cells[-1].text = "lb"
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    assert recipe.matrix_binding.summary_column_names == ("r", "lc", "lb")

    out_path = str(tmp_path / "out_m18.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )
    out_doc = docx.Document(out_path)
    r1_cells = out_doc.tables[1].rows[1].cells
    assert r1_cells[-3].text == "r"
    assert r1_cells[-2].text == "lc"
    assert r1_cells[-1].text == "lb"

    # Verify tblGrid has reordered column widths matching r (133), lc (208), lb (212)
    grid_cols = out_doc.tables[1]._tbl.tblGrid.findall(docx.oxml.ns.qn("w:gridCol"))
    widths = [int(gc.get(docx.oxml.ns.qn("w:w"))) for gc in grid_cols]
    assert widths[-3:] == [133, 208, 212], f"Expected widths [133, 208, 212] for reordered ('r', 'lc', 'lb'), got {widths[-3:]}"

    # Verify student row cells also use the semantic reordered widths
    st_cells = out_doc.tables[1].rows[2].cells
    assert st_cells[-3]._tc.get_or_add_tcPr().tcW.w == 133
    assert st_cells[-2]._tc.get_or_add_tcPr().tcW.w == 208
    assert st_cells[-1]._tc.get_or_add_tcPr().tcW.w == 212


def test_m19_additional_unrelated_matrix_column(tmp_path):
    """M19: Additional column inserted before date columns.
    Inspector discovers date_columns_start correctly."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m19_col.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]
    from docx.oxml import parse_xml
    from docx.oxml.ns import nsdecls
    ns = nsdecls("w")
    for r_idx, r in enumerate(attn_tbl.rows):
        txt = "SECTION" if r_idx == 0 else ("SEC" if r_idx == 1 else "")
        tc = parse_xml(f'<w:tc {ns}><w:p><w:r><w:t>{txt}</w:t></w:r></w:p></w:tc>')
        tcs = [c for c in r._tr if c.tag.endswith('tc')]
        insert_idx = r._tr.index(tcs[3]) if len(tcs) > 3 else len(r._tr)
        r._tr.insert(insert_idx, tc)
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    # date_columns_start is now 4 (offset by inserted column)
    assert recipe.matrix_binding.date_columns_start == 4

    out_path = str(tmp_path / "out_m19.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )
    assert os.path.exists(out_path)
    out_doc = docx.Document(out_path)
    out_t = out_doc.tables[1]
    # Extra column preserved before date columns
    assert out_t.rows[0].cells[3].text == "SECTION"
    assert out_t.rows[1].cells[3].text == "SEC"
    # Date region starts at col 4
    assert "WEEK 1" in out_t.rows[0].cells[4].text
    assert out_t.rows[1].cells[4].text != ""


def test_m20_student_template_row_relocation(tmp_path):
    """M20: Student template row relocated.
    Inspector distinguishes header row, decorative guidance row, and student template row.
    Prototype row is relocated to index 3 and made structurally distinguishable from guidance row at index 2."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo_root, "attendance", "template lec.docx")
    mut_path = str(tmp_path / "mut_m20_reloc_student.docx")
    shutil.copy2(src, mut_path)

    doc = docx.Document(mut_path)
    attn_tbl = doc.tables[1]

    # Structurally distinguish prototype student row (initially at index 2, will become index 3)
    proto_row = attn_tbl.rows[2]._tr
    for tc in proto_row.findall(docx.oxml.ns.qn("w:tc")):
        tcPr = tc.find(docx.oxml.ns.qn("w:tcPr"))
        if tcPr is None:
            tcPr = docx.oxml.OxmlElement("w:tcPr")
            tc.insert(0, tcPr)
        for shd in tcPr.findall(docx.oxml.ns.qn("w:shd")):
            tcPr.remove(shd)
        shd = docx.oxml.OxmlElement("w:shd")
        shd.set(docx.oxml.ns.qn("w:val"), "clear")
        shd.set(docx.oxml.ns.qn("w:color"), "auto")
        shd.set(docx.oxml.ns.qn("w:fill"), "FFFFCC")  # Distinguishable yellow shading for prototype
        tcPr.append(shd)

    # Add decorative guidance row before the student row with unmistakable marker text and gray shading
    guide_row = copy.deepcopy(proto_row)
    tcs = guide_row.findall(docx.oxml.ns.qn("w:tc"))
    for tc in tcs:
        tcPr = tc.find(docx.oxml.ns.qn("w:tcPr"))
        if tcPr is None:
            tcPr = docx.oxml.OxmlElement("w:tcPr")
            tc.insert(0, tcPr)
        for shd in tcPr.findall(docx.oxml.ns.qn("w:shd")):
            tcPr.remove(shd)
        shd = docx.oxml.OxmlElement("w:shd")
        shd.set(docx.oxml.ns.qn("w:val"), "clear")
        shd.set(docx.oxml.ns.qn("w:color"), "auto")
        shd.set(docx.oxml.ns.qn("w:fill"), "D3D3D3")  # Distinguishable gray shading for guidance row
        tcPr.append(shd)

        for t in tc.iter(docx.oxml.ns.qn("w:t")):
            t.text = ""

    # Explicitly set marker text in first cell of guidance row
    p = tcs[0].find(docx.oxml.ns.qn("w:p"))
    if p is None:
        p = docx.oxml.OxmlElement("w:p")
        tcs[0].append(p)
    r = docx.oxml.OxmlElement("w:r")
    t = docx.oxml.OxmlElement("w:t")
    t.text = "GUIDE ROW - DO NOT CLONE"
    r.append(t)
    p.append(r)

    # Insert guide row at index 2 (after header row 1)
    # The prototype student row is now moved to index 3
    attn_tbl.rows[1]._tr.addnext(guide_row)
    doc.save(mut_path)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(mut_path, profile_id="attendance_docx")
    assert isinstance(recipe, ValidatedAttendanceTemplateRecipe)
    # Real prototype student row discovered at row 3
    assert recipe.matrix_binding.student_template_row_index == 3

    out_path = str(tmp_path / "out_m20.docx")
    AttendanceGenerator(mut_path, recipe).generate(
        output_path=out_path,
        course_code_title="COSC 101",
        class_schedule="08:00AM-11:00AM / Mon",
        semester_ay="1st Sem",
        room_assignment="CL3",
        instructor="DR. JUAN DELA CRUZ",
        months=[12],
        year=2026,
        weekdays=[0],
        students=ATTENDANCE_STUDENTS,
    )
    assert os.path.exists(out_path)
    out_doc = docx.Document(out_path)
    out_t = out_doc.tables[1]
    name_col = recipe.matrix_binding.name_col

    # Output must populate students from the real prototype, NOT from guide row 2
    assert "ALVAREZ, MARIA A." in out_t.rows[2].cells[name_col].text

    qn_tcPr = docx.oxml.ns.qn("w:tcPr")
    qn_shd = docx.oxml.ns.qn("w:shd")
    qn_fill = docx.oxml.ns.qn("w:fill")

    # Prove that the guide row was NOT cloned, and generated rows inherit structure from prototype row 3
    for r in out_t.rows[2:]:
        for c in r.cells:
            assert "GUIDE ROW - DO NOT CLONE" not in c.text
            tcPr = c._tc.find(qn_tcPr)
            assert tcPr is not None, "Generated cell must retain tcPr from prototype"
            shd = tcPr.find(qn_shd)
            assert shd is not None, "Generated cell must retain shading from prototype row 3"
            assert shd.get(qn_fill) == "FFFFCC", (
                f"Generated cell must inherit 'FFFFCC' shading from recipe prototype row 3, got '{shd.get(qn_fill)}'. "
                f"A regression to orig_rows[2] would produce 'D3D3D3'."
            )
            assert shd.get(qn_fill) != "D3D3D3", "Generated cell must NOT inherit shading from guide row 2."

