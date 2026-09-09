import os
import glob
import re
import pytest
from lxml import etree
import docx

import roster_parser
from modules.common.docx_utils import get_student_name_font_sz, W
from modules.parsers.roster_parser import _fix_encoding, _is_name_header
from modules.parsers.ceit_directory import is_known_lab_subject
from modules.generators.ceit_gen import GeneratorFactory, GradeDiscussionGenerator
from modules.models import ClassInfo
import process_schedule
import attendancegen

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEDULE_PATH = os.path.join(WORKSPACE_DIR, "ORTEGA_SCHEDULE.xls")
SCHEDULES_DIR = os.path.join(WORKSPACE_DIR, "schedules")


def test_roster_parser_retains_student_with_surname_name():
    """Verify students whose surname is 'NAME' (e.g. NAME, ZULEIKAH MARIJ C.) are not discarded as headers."""
    it11_roster = os.path.join(
        SCHEDULES_DIR,
        "BSIT1-1 List of Students for 202612075-CVSU 101 - INSTITUTIONAL ORIENTATION.xlsx"
    )
    assert os.path.exists(it11_roster), f"Roster file {it11_roster} must exist"

    students = roster_parser.load_students(it11_roster)
    assert len(students) == 40, f"Expected 40 students in BSIT1-1, got {len(students)}"

    # Check that Zuleikah Name is present
    name_student = [s for s in students if "NAME" in s[0].upper() and "ZULEIKAH" in s[0].upper()]
    assert len(name_student) == 1, "Student NAME, ZULEIKAH MARIJ C. must be retained"
    assert name_student[0][0] == "NAME, ZULEIKAH MARIJ C."
    assert name_student[0][1] == "261010315"

    # Verify unit function _is_name_header behavior
    assert _is_name_header("NAME") is True
    assert _is_name_header("Student Name") is True
    assert _is_name_header("NAME, ZULEIKAH MARIJ C.") is False
    assert _is_name_header("NAME ZULEIKAH") is False


def test_roster_parser_fixes_portal_enye_corruption():
    """Verify UTF-8 / ASCII portal encoding glitches like SAÃEZ are corrected to SAÑEZ."""
    cs16_roster = os.path.join(
        SCHEDULES_DIR,
        "BSCS1-6 List of Students for 202612058-DCIT 21 - INTRODUCTION TO COMPUTING.xlsx"
    )
    assert os.path.exists(cs16_roster), f"Roster file {cs16_roster} must exist"

    students = roster_parser.load_students(cs16_roster)
    sanez_student = [s for s in students if "261017240" in s[1]]
    assert len(sanez_student) == 1
    assert "Ã" not in sanez_student[0][0]
    assert sanez_student[0][0] == "SAÑEZ, KEVIN C."

    # Unit test encoding normalization
    assert _fix_encoding("SAÃEZ, KEVIN C.") == "SAÑEZ, KEVIN C."
    assert _fix_encoding("CAÃETE, JOSHUA") == "CAÑETE, JOSHUA"
    assert _fix_encoding("PEÃA, MARIA") == "PEÑA, MARIA"


def test_dynamic_font_scaling_ladder():
    """
    Verify font size scaling ladder matching reference SCHOOL FILES 2026:
      - <= 30 characters: 8pt (sz="16")
      - 31-35 characters: 7pt (sz="14")
      - > 35 characters: 6pt (sz="12")
    """
    assert get_student_name_font_sz("CRUZ, JUAN A.") == "16"                 # 13 chars <= 30 -> 8pt
    assert get_student_name_font_sz("1234567890123456789012345") == "16"     # 25 chars <= 30 -> 8pt
    assert get_student_name_font_sz("12345678901234567890123456") == "16"    # 26 chars <= 30 -> 8pt
    assert get_student_name_font_sz("ALCANTARA, CHRISTINE ANNE C.") == "16"  # 28 chars <= 30 -> 8pt
    assert get_student_name_font_sz("123456789012345678901234567890") == "16" # 30 chars <= 30 -> 8pt
    assert get_student_name_font_sz("DE RUEDA, ALELHY ALLESSANDRA M.") == "14" # 31 chars 31-35 -> 7pt
    assert get_student_name_font_sz("CRISOSTOMO, NEIL ANGELO MARQUEZ JR.") == "14" # 35 chars 31-35 -> 7pt
    assert get_student_name_font_sz("123456789012345678901234567890123456") == "12" # 36 chars > 35 -> 6pt
    assert get_student_name_font_sz("DE LOS REYES, MA. CONCEPCION DELA CRUZ") == "12" # 39 chars > 35 -> 6pt


def test_grade_discussion_template_and_generator_row_count(tmp_path):
    """Verify Grade Discussion templates and generated outputs have exactly 6 rows in Table 0 without orphan row."""
    templates = [
        os.path.join(WORKSPACE_DIR, "templates", "Final-Grade-Discussion_LATEST.docx"),
        os.path.join(WORKSPACE_DIR, "templates", "Finals-Grade-Discussion_LATEST.docx"),
        os.path.join(WORKSPACE_DIR, "templates", "Midterm-Grade-Discussion_LATEST.docx"),
    ]
    for tmpl in templates:
        assert os.path.exists(tmpl), f"Template {tmpl} must exist"
        doc = docx.Document(tmpl)
        t0 = doc.tables[0]
        assert len(t0.rows) == 6, f"Template {os.path.basename(tmpl)} must have exactly 6 rows in Table 0, got {len(t0.rows)}"

    # Test generation with GradeDiscussionGenerator
    finals_tmpl = os.path.join(WORKSPACE_DIR, "templates", "Final-Grade-Discussion_LATEST.docx")
    finals_gen = GradeDiscussionGenerator(finals_tmpl, "Finals")
    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        course_section="BSCS 4-1",
        schedule_code="202612731",
        subject="COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)",
        time_days_room="Fri: 07:00AM-12:00PM / CL2",
        semester_ay="1st Semester 2026-2027",
        students=[("DELA CRUZ, JUAN A.", "202110001")]
    )
    out_docx = str(tmp_path / "test_grade_discussion.docx")
    finals_gen.generate(info, out_docx)

    gen_doc = docx.Document(out_docx)
    gen_t0 = gen_doc.tables[0]
    assert len(gen_t0.rows) == 6, f"Generated Grade Discussion must have 6 rows in Table 0, got {len(gen_t0.rows)}"
    # Check labels
    row_texts = [r.cells[0].text.strip() for r in gen_t0.rows]
    assert any("INSTRUCTOR" in t for t in row_texts)
    assert any("COURSE" in t for t in row_texts)
    assert any("SCHEDULE CODE" in t for t in row_texts)
    assert any("SUBJECT" in t for t in row_texts)
    assert any("SEMESTER" in t for t in row_texts)
    assert any("DATE" in t for t in row_texts)
    # Ensure no empty unlabeled row
    assert all(len(t) > 0 for t in row_texts)


def test_cs14_lab_auto_detection():
    """Verify hybrid lab course CS1-4 DCIT 21 is detected as lecture_lab and is_known_lab_subject is True."""
    assert is_known_lab_subject("DCIT 21 - INTRODUCTION TO COMPUTING") is True
    assert is_known_lab_subject("DCIT 21") is True
    assert is_known_lab_subject("DCIT21") is True
    assert is_known_lab_subject("CVSU 101 - INSTITUTIONAL ORIENTATION") is False

    rosters = glob.glob(os.path.join(SCHEDULES_DIR, "*.xlsx"))
    classes = process_schedule.detect_classes(SCHEDULE_PATH, rosters)
    cs14 = [c for c in classes if c["course_sec"] == "CS1-4"][0]
    assert cs14["has_lab"] is True, "CS1-4 DCIT 21 must be detected as having lab"
    assert cs14["detected_type"] == "lecture_lab"


def test_cs41_subject_reconciliation():
    """Verify CS4-1 subject title reconciles from COSC 111A to canonical COSC 111."""
    rosters = glob.glob(os.path.join(SCHEDULES_DIR, "*.xlsx"))
    classes = process_schedule.detect_classes(SCHEDULE_PATH, rosters)
    cs41 = [c for c in classes if c["course_sec"] == "CS4-1"][0]
    assert cs41["subject_name"] == "COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)"


def test_attendance_formatting_parity(tmp_path):
    """Verify generated Attendance sheets preserve Table 0 headers (sz=22, sz=18) and Table 1 (sz=16)."""
    from modules.generators.attendance_gen import build_attendance_sheet, get_default_template_path
    
    tmpl = get_default_template_path(has_lab=True)
    out_docx = str(tmp_path / "test_attendance.docx")
    
    build_attendance_sheet(
        template_path=tmpl,
        output_path=out_docx,
        course_code_title="DCIT 21 - INTRODUCTION TO COMPUTING",
        class_schedule="Mon: 05:00PM-07:00PM",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        room_assignment="LEC: ITC 402 / ORTEGA",
        instructor="DAN JOSEPH A. ORTEGA",
        months=[9],
        year=2026,
        weekdays=[0],
        students=[("ARCA, BRENCH LORENZ B.", "261014253"), ("BERNAL, RUTHERFORD Q.", "261013992")]
    )
    
    doc = docx.Document(out_docx)
    W_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    # Check Table 0 Month/Year sz="22"
    m_sz = [r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz").attrib.get(f"{{{W_URI}}}val") if r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz") is not None else "def" for r in doc.tables[0].rows[0].cells[4]._tc.findall(f".//{{{W_URI}}}r")]
    assert "22" in m_sz, f"Month/Year in Table 0 must have sz=22, got {m_sz}"
    
    # Check Table 0 Schedule sz="18"
    s_sz = [r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz").attrib.get(f"{{{W_URI}}}val") if r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz") is not None else "def" for r in doc.tables[0].rows[1].cells[1]._tc.findall(f".//{{{W_URI}}}r")]
    assert "18" in s_sz, f"Schedule in Table 0 must have sz=18, got {s_sz}"
    
    # Check Table 1 student ID sz="16"
    id_sz = [r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz").attrib.get(f"{{{W_URI}}}val") if r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz") is not None else "def" for r in doc.tables[1].rows[2].cells[2]._tc.findall(f".//{{{W_URI}}}r")]
    assert "16" in id_sz, f"Student ID in Table 1 must have sz=16, got {id_sz}"


def test_grade_discussion_finals_formatting_parity(tmp_path):
    """Verify Finals Grade Discussion has sz=22 for Table 0 labels, Table 1 header, and Paragraph 3."""
    from modules.generators.ceit_gen import GradeDiscussionGenerator
    
    tmpl = os.path.join(WORKSPACE_DIR, "templates", "Final-Grade-Discussion_LATEST.docx")
    out_docx = str(tmp_path / "test_gd_finals.docx")
    
    gen = GradeDiscussionGenerator(tmpl, "Finals")
    info = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        course_section="CS1-4",
        schedule_code="202612040",
        subject="DCIT 21 - INTRODUCTION TO COMPUTING",
        time_days_room="Mon: 05:00PM-07:00PM / ITC 402",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        students=[("ARCA, BRENCH LORENZ B.", "261014253")]
    )
    gen.generate(info, out_docx)
    
    doc = docx.Document(out_docx)
    W_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    # Table 0 label sz="22"
    t0_lbl_sz = [r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz").attrib.get(f"{{{W_URI}}}val") if r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz") is not None else "def" for r in doc.tables[0].rows[0].cells[0]._tc.findall(f".//{{{W_URI}}}r")]
    assert "22" in t0_lbl_sz, f"Table 0 label must have sz=22, got {t0_lbl_sz}"
    
    # Table 1 header sz="22"
    t1_hdr_sz = [r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz").attrib.get(f"{{{W_URI}}}val") if r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz") is not None else "def" for r in doc.tables[1].rows[0].cells[0]._tc.findall(f".//{{{W_URI}}}r")]
    assert "22" in t1_hdr_sz, f"Table 1 header must have sz=22, got {t1_hdr_sz}"
    
    # Paragraph 3 sz="22"
    p3_sz = [r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz").attrib.get(f"{{{W_URI}}}val") if r.find(f"{{{W_URI}}}rPr/{{{W_URI}}}sz") is not None else "def" for r in doc.paragraphs[3]._p.findall(f".//{{{W_URI}}}r")]
    assert "22" in p3_sz, f"Paragraph 3 must have sz=22, got {p3_sz}"

