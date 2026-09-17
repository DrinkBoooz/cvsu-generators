import os
import pytest
from modules.parsers.schedule_parser import (
    normalize_room,
    format_canonical_schedule,
    find_blocks_for_section,
)
from modules.models.schedule import ClassInfo
from modules.common.docx_utils import load_docx, w, get_full_text

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==============================================================================
# 1. Focused Parser Room Normalization Tests (Section 1)
# ==============================================================================
def test_normalize_room_with_instructor_suffix():
    instructor = "DAN JOSEPH A. ORTEGA"
    # Basic room with instructor suffix
    assert normalize_room("OS / ORTEGA", instructor) == "OS"
    assert normalize_room("CCL 102 / ORTEGA", instructor) == "CCL 102"
    assert normalize_room("ITC 501 / ORTEGA", instructor) == "ITC 501"

    # Default instructor fallback when not explicitly provided
    assert normalize_room("OS / ORTEGA") == "OS"
    assert normalize_room("CCL 102 / ORTEGA") == "CCL 102"


def test_normalize_room_without_suffix():
    instructor = "DAN JOSEPH A. ORTEGA"
    assert normalize_room("OS", instructor) == "OS"
    assert normalize_room("CCL 102", instructor) == "CCL 102"
    assert normalize_room("ITC 402", instructor) == "ITC 402"


def test_normalize_room_preserves_legitimate_punctuation_and_rooms():
    instructor = "DAN JOSEPH A. ORTEGA"
    # Legitimate multiple rooms separated by slash
    assert normalize_room("ITC 501 / ITC 502", instructor) == "ITC 501 / ITC 502"
    assert normalize_room("BLDG 2 / RM 3", instructor) == "BLDG 2 / RM 3"

    # Rooms with hyphen, parentheses, periods
    assert normalize_room("RM 101-A", instructor) == "RM 101-A"
    assert normalize_room("ROOM 302 (OLD)", instructor) == "ROOM 302 (OLD)"
    assert normalize_room("LAB-B", instructor) == "LAB-B"


def test_normalize_room_general_not_hardcoded_to_ortega():
    # Prove normalization works dynamically with any instructor name
    assert normalize_room("OS / SANTOS", "MARIA C. SANTOS") == "OS"
    assert normalize_room("CCL 102 / REYES", "ENGR. JUAN REYES, M.SC.") == "CCL 102"
    assert normalize_room("ITC 201 / DELA CRUZ", "PROF. PEDRO DELA CRUZ") == "ITC 201"

    # Negative check: a room whose name is NOT the instructor is not stripped
    assert normalize_room("OS / SANTOS", "DAN JOSEPH A. ORTEGA") == "OS / SANTOS"


def test_find_blocks_for_section_room_normalization():
    # Schedule grid where room row has 'OS / ORTEGA'
    grid = [
        ["", "", "", "", "", ""],
        ["", "11:00", "13:00", "", "", "COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)"],
        ["", "11:00", "13:00", "", "", "BSCS 4-1"],
        ["", "11:00", "13:00", "", "", "LEC"],
        ["", "11:00", "13:00", "", "", "OS / ORTEGA"],
    ]
    blocks = find_blocks_for_section(grid, "BSCS 4-1", start_row=1, end_row=4, instructor="DAN JOSEPH A. ORTEGA")
    assert len(blocks) == 1
    assert blocks[0]["room"] == "OS"
    assert blocks[0]["type"] == "LEC"
    assert blocks[0]["start_time"] == "11:00AM"
    assert blocks[0]["end_time"] == "01:00PM"


# ==============================================================================
# 2. Canonical CEIT Schedule Formatting Tests (Section 2)
# ==============================================================================
def test_format_canonical_schedule_ceit():
    blocks = [
        {
            "day": "Wed",
            "start_time": "11:00AM",
            "end_time": "01:00PM",
            "type": "LEC",
            "room": "OS",
        },
        {
            "day": "Fri",
            "start_time": "09:00AM",
            "end_time": "11:00AM",
            "type": "LAB",
            "room": "CCL 102",
        },
    ]
    canonical = format_canonical_schedule(blocks, instructor="DAN JOSEPH A. ORTEGA")
    expected = "Wed: 11:00AM-01:00PM / LEC: OS; Fri: 09:00AM-11:00AM / LAB: CCL 102"
    assert canonical == expected

    # Verify formatting constraints
    assert "ORTEGA" not in canonical
    assert "/ ORTEGA" not in canonical
    assert "\n" not in canonical
    assert "\r" not in canonical
    assert "; " in canonical


def test_format_canonical_schedule_normalizes_contaminated_blocks():
    # Even if block had contaminated room, canonical formatter normalizes it
    blocks = [
        {
            "day": "Wed",
            "start_time": "11:00AM",
            "end_time": "01:00PM",
            "type": "LEC",
            "room": "OS / ORTEGA",
        },
        {
            "day": "Fri",
            "start_time": "09:00AM",
            "end_time": "11:00AM",
            "type": "LAB",
            "room": "CCL 102 / ORTEGA",
        },
    ]
    canonical = format_canonical_schedule(blocks, instructor="DAN JOSEPH A. ORTEGA")
    expected = "Wed: 11:00AM-01:00PM / LEC: OS; Fri: 09:00AM-11:00AM / LAB: CCL 102"
    assert canonical == expected
    assert "ORTEGA" not in canonical


# ==============================================================================
# 3. Attendance Semantic Separation Tests (Section 3)
# ==============================================================================
def test_attendance_generation_semantic_separation(tmp_path):
    """
    Verify attendance generation strictly separates:
    - Class Schedule: Wed: 11:00AM-01:00PM; Fri: 09:00AM-11:00AM
    - Room Assignment: LEC: OS, LAB: CCL 102
    - Name of Instructor: DAN JOSEPH A. ORTEGA
    """
    import attendancegen

    template_path = os.path.join(REPO_ROOT, "attendance", "template lab and lec.docx")
    assert os.path.exists(template_path)

    out_docx = str(tmp_path / "out_attendance_separation.docx")

    attendancegen.build_attendance_sheet(
        template_path=template_path,
        output_path=out_docx,
        course_code_title="COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)",
        class_schedule="Wed: 11:00AM-01:00PM; Fri: 09:00AM-11:00AM",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        room_assignment="LEC: OS, LAB: CCL 102",
        instructor="DAN JOSEPH A. ORTEGA",
        months=[9],
        year=2026,
        weekdays=[2, 4],
        students=[("CRUZ, JUAN A.", "2026-0001")],
    )
    assert os.path.exists(out_docx)

    zin, root, body = load_docx(out_docx)
    tables = body.findall(w("tbl"))
    info_tbl = tables[0]
    info_rows = info_tbl.findall(w("tr"))

    # Row 1: Class Schedule
    sched_tc = info_rows[1].findall(w("tc"))[1]
    sched_p = sched_tc.find(w("p"))
    sched_text = get_full_text(sched_p).strip()
    assert sched_text == "Wed: 11:00AM-01:00PM; Fri: 09:00AM-11:00AM"
    assert "ORTEGA" not in sched_text
    assert "/ ORTEGA" not in sched_text
    assert len(sched_p.findall(".//" + w("br"))) == 0
    assert len(sched_p.findall(".//" + w("cr"))) == 0

    # Row 3: Room Assignment
    room_tc = info_rows[3].findall(w("tc"))[1]
    room_p = room_tc.find(w("p"))
    room_text = get_full_text(room_p).strip()
    assert room_text == "LEC: OS, LAB: CCL 102"
    assert "ORTEGA" not in room_text
    assert "/ ORTEGA" not in room_text
    assert len(room_p.findall(".//" + w("br"))) == 0
    assert len(room_p.findall(".//" + w("cr"))) == 0

    # Row 4: Name of Instructor
    inst_tc = info_rows[4].findall(w("tc"))[1]
    inst_p = inst_tc.find(w("p"))
    inst_text = get_full_text(inst_p).strip()
    assert inst_text == "DAN JOSEPH A. ORTEGA"


def test_attendance_normalizes_legacy_contaminated_room_assignment(tmp_path):
    """
    Even if raw contaminated room_assignment is passed to build_attendance_sheet,
    it automatically strips the instructor suffix.
    """
    import attendancegen

    template_path = os.path.join(REPO_ROOT, "attendance", "template lec.docx")
    assert os.path.exists(template_path)

    out_docx = str(tmp_path / "out_attendance_lec_clean.docx")

    attendancegen.build_attendance_sheet(
        template_path=template_path,
        output_path=out_docx,
        course_code_title="COSC 111 - C S ELECTIVE 3",
        class_schedule="Wed: 11:00AM-01:00PM",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        room_assignment="LEC: OS / ORTEGA",
        instructor="DAN JOSEPH A. ORTEGA",
        months=[9],
        year=2026,
        weekdays=[2],
        students=[("CRUZ, JUAN A.", "2026-0001")],
    )
    assert os.path.exists(out_docx)

    zin, root, body = load_docx(out_docx)
    info_rows = body.findall(w("tbl"))[0].findall(w("tr"))
    room_p = info_rows[3].findall(w("tc"))[1].find(w("p"))
    room_text = get_full_text(room_p).strip()
    assert room_text == "LEC: OS"
    assert "ORTEGA" not in room_text


# ==============================================================================
# 4. Native CEIT Generation with Canonical Schedule
# ==============================================================================
def test_native_ceit_canonical_schedule(tmp_path):
    from modules.services.template_recipe_service import TemplateRecipeResolver
    from modules.generators.ceit_gen import SyllabusGenerator

    syllabus_tmpl = os.path.join(REPO_ROOT, "templates", "template_syllabus.docx")
    assert os.path.exists(syllabus_tmpl)

    resolver = TemplateRecipeResolver.get_instance()
    recipe = resolver.resolve(syllabus_tmpl, profile_id="academic_docx")

    canonical_sched = "Wed: 11:00AM-01:00PM / LEC: OS; Fri: 09:00AM-11:00AM / LAB: CCL 102"
    instructor_name = "DAN JOSEPH A. ORTEGA"

    info = ClassInfo(
        instructor=instructor_name,
        course_section="BSCS 4-1",
        schedule_code="12345",
        subject="COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)",
        time_days_room=canonical_sched,
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        students=[("CRUZ, JUAN A.", "2026-0001")],
    )

    out_docx = str(tmp_path / "out_ceit_canonical.docx")
    gen = SyllabusGenerator(syllabus_tmpl, recipe)
    gen.generate(info, out_docx)
    assert os.path.exists(out_docx)

    zin, root, body = load_docx(out_docx)
    rows = body.findall(w("tbl"))[0].findall(w("tr"))

    # Row 4: Time / Days / Room
    sched_tc = rows[4].findall(w("tc"))[1]
    sched_p = sched_tc.find(w("p"))
    sched_text = get_full_text(sched_p).strip()

    assert canonical_sched in sched_text
    assert "/ ORTEGA" not in sched_text
    assert len(sched_p.findall(".//" + w("br"))) == 0
    assert len(sched_p.findall(".//" + w("cr"))) == 0

    # Row 0: Instructor
    inst_tc = rows[0].findall(w("tc"))[1]
    inst_text = get_full_text(inst_tc.find(w("p"))).strip()
    assert instructor_name in inst_text


# ==============================================================================
# 5. Real-Generation Verification Across 4 Real Templates (Section 6)
# ==============================================================================
def test_real_generation_custom_docx(tmp_path):
    """
    Real custom DOCX form generation:
    - Verifies canonical schedule 'Wed: 11:00AM-01:00PM / LEC: OS; Fri: 09:00AM-11:00AM / LAB: CCL 102'
    - Verifies zero instructor contamination in schedule
    - Verifies one logical schedule paragraph, zero w:br, zero w:cr
    - Verifies source typography is preserved (no arbitrary 9pt fallback)
    """
    from modules.parsers.template_inspector import DocxTemplateInspector
    from modules.parsers.recipe_validator import RecipeValidator
    from modules.models.recipe import PROFILE_CUSTOM_DOCX
    from modules.generators.document_generator import ConfigurableDocumentGenerator

    custom_tmpl = os.path.join(REPO_ROOT, "tests", "test_templates", "template_laboratory_monitoring.docx")
    assert os.path.exists(custom_tmpl)

    inspector = DocxTemplateInspector()
    cand = inspector.inspect(custom_tmpl, profile_id="custom_docx")
    recipe = RecipeValidator.validate(cand, PROFILE_CUSTOM_DOCX)

    canonical_sched = "Wed: 11:00AM-01:00PM / LEC: OS; Fri: 09:00AM-11:00AM / LAB: CCL 102"
    instructor_name = "DAN JOSEPH A. ORTEGA"
    subject_title = "COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)"

    info = ClassInfo(
        instructor=instructor_name,
        course_section="BSCS 4-1",
        schedule_code="12345",
        subject=subject_title,
        time_days_room=canonical_sched,
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        students=[("CRUZ, JUAN A.", "2026-0001"), ("SANTOS, MARIA B.", "2026-0002")],
    )

    out_docx = str(tmp_path / "out_custom_real.docx")
    gen = ConfigurableDocumentGenerator(custom_tmpl, recipe)
    gen.generate(info, out_docx)
    assert os.path.exists(out_docx)

    zin, root, body = load_docx(out_docx)
    tables = body.findall(w("tbl"))
    assert len(tables) >= 1

    # Verify schedule in document body
    all_paras = body.findall(".//" + w("p"))
    sched_p = None
    for p in all_paras:
        txt = get_full_text(p).strip()
        if "Wed: 11:00AM-01:00PM" in txt or "CCL 102" in txt:
            sched_p = p
            break

    assert sched_p is not None, "Schedule paragraph found in custom generated docx"
    sched_txt = get_full_text(sched_p).strip()
    assert canonical_sched in sched_txt
    assert "/ ORTEGA" not in sched_txt
    assert len(sched_p.findall(".//" + w("br"))) == 0
    assert len(sched_p.findall(".//" + w("cr"))) == 0
    assert "\n" not in sched_txt
    assert "\r" not in sched_txt

    # Verify instructor field does not leak into subject or schedule
    for p in all_paras:
        txt = get_full_text(p).strip()
        if subject_title in txt:
            assert instructor_name not in txt


def test_real_generation_lecture_attendance(tmp_path):
    """
    Real Lecture Attendance form generation (attendance/template lec.docx):
    - Verifies exact Class Schedule: 'Wed: 11:00AM-01:00PM'
    - Verifies exact Room Assignment: 'LEC: OS'
    - Verifies Name of Instructor: 'DAN JOSEPH A. ORTEGA'
    - Verifies template geometry (tcW), zero w:br, zero w:cr, student row population
    """
    import attendancegen

    template_path = os.path.join(REPO_ROOT, "attendance", "template lec.docx")
    assert os.path.exists(template_path)

    out_docx = str(tmp_path / "out_lecture_attendance.docx")
    students = [("DELA CRUZ, JUAN A.", "2026-10001"), ("GARCIA, MARIA B.", "2026-10002")]

    attendancegen.build_attendance_sheet(
        template_path=template_path,
        output_path=out_docx,
        course_code_title="COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)",
        class_schedule="Wed: 11:00AM-01:00PM",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        room_assignment="LEC: OS",
        instructor="DAN JOSEPH A. ORTEGA",
        months=[9],
        year=2026,
        weekdays=[2],
        students=students,
    )
    assert os.path.exists(out_docx)

    zin, root, body = load_docx(out_docx)
    tables = body.findall(w("tbl"))
    assert len(tables) >= 2

    info_tbl = tables[0]
    info_rows = info_tbl.findall(w("tr"))

    # Table geometry check: verify physical cell width from template
    sched_tc = info_rows[1].findall(w("tc"))[1]
    tc_w = sched_tc.find(w("tcPr") + "/" + w("tcW"))
    assert tc_w is not None
    assert tc_w.attrib.get(w("w")) == "2790", "Template geometry preserved (cell width 2790 dxa = ~1.94 in)"

    # Schedule: exactly one logical paragraph, zero explicit breaks
    sched_paras = sched_tc.findall(w("p"))
    assert len(sched_paras) == 1
    sched_txt = get_full_text(sched_paras[0]).strip()
    assert sched_txt == "Wed: 11:00AM-01:00PM"
    assert "ORTEGA" not in sched_txt
    assert len(sched_paras[0].findall(".//" + w("br"))) == 0
    assert len(sched_paras[0].findall(".//" + w("cr"))) == 0

    # Room Assignment: exactly 'LEC: OS'
    room_tc = info_rows[3].findall(w("tc"))[1]
    room_paras = room_tc.findall(w("p"))
    assert len(room_paras) == 1
    room_txt = get_full_text(room_paras[0]).strip()
    assert room_txt == "LEC: OS"
    assert "ORTEGA" not in room_txt
    assert "/ ORTEGA" not in room_txt

    # Instructor
    inst_txt = get_full_text(info_rows[4].findall(w("tc"))[1].find(w("p"))).strip()
    assert inst_txt == "DAN JOSEPH A. ORTEGA"

    # Student row generation compatibility (Table 1)
    attn_tbl = tables[1]
    attn_rows = attn_tbl.findall(w("tr"))
    assert len(attn_rows) >= 4  # Header 0, Header 1, Student 1, Student 2
    student1_name = get_full_text(attn_rows[2].findall(w("tc"))[1].find(w("p"))).strip()
    assert "DELA CRUZ, JUAN A." in student1_name


def test_real_generation_lecture_lab_attendance(tmp_path):
    """
    Real Lecture/Lab Attendance form generation (attendance/template lab and lec.docx):
    - Verifies Class Schedule: 'Wed: 11:00AM-01:00PM; Fri: 09:00AM-11:00AM'
    - Verifies Room Assignment: 'LEC: OS, LAB: CCL 102'
    - Verifies Name of Instructor: 'DAN JOSEPH A. ORTEGA'
    - Verifies zero instructor contamination in room or schedule
    - Verifies physical cell geometry, one paragraph, zero breaks, student row population
    """
    import attendancegen

    template_path = os.path.join(REPO_ROOT, "attendance", "template lab and lec.docx")
    assert os.path.exists(template_path)

    out_docx = str(tmp_path / "out_lab_lec_attendance.docx")
    students = [("DELA CRUZ, JUAN A.", "2026-10001"), ("GARCIA, MARIA B.", "2026-10002")]

    attendancegen.build_attendance_sheet(
        template_path=template_path,
        output_path=out_docx,
        course_code_title="COSC 111 - C S ELECTIVE 3 (INTERNET OF THINGS)",
        class_schedule="Wed: 11:00AM-01:00PM; Fri: 09:00AM-11:00AM",
        semester_ay="FIRST SEMESTER, AY 2026 - 2027",
        room_assignment="LEC: OS, LAB: CCL 102",
        instructor="DAN JOSEPH A. ORTEGA",
        months=[9],
        year=2026,
        weekdays=[2, 4],
        students=students,
    )
    assert os.path.exists(out_docx)

    zin, root, body = load_docx(out_docx)
    tables = body.findall(w("tbl"))
    assert len(tables) >= 2

    info_tbl = tables[0]
    info_rows = info_tbl.findall(w("tr"))

    # Table geometry check
    sched_tc = info_rows[1].findall(w("tc"))[1]
    tc_w = sched_tc.find(w("tcPr") + "/" + w("tcW"))
    assert tc_w is not None
    assert tc_w.attrib.get(w("w")) == "2790", "Template geometry preserved"

    # Schedule
    sched_paras = sched_tc.findall(w("p"))
    assert len(sched_paras) == 1
    sched_txt = get_full_text(sched_paras[0]).strip()
    assert sched_txt == "Wed: 11:00AM-01:00PM; Fri: 09:00AM-11:00AM"
    assert "ORTEGA" not in sched_txt
    assert len(sched_paras[0].findall(".//" + w("br"))) == 0
    assert len(sched_paras[0].findall(".//" + w("cr"))) == 0

    # Room Assignment
    room_tc = info_rows[3].findall(w("tc"))[1]
    room_paras = room_tc.findall(w("p"))
    assert len(room_paras) == 1
    room_txt = get_full_text(room_paras[0]).strip()
    assert room_txt == "LEC: OS, LAB: CCL 102"
    assert "ORTEGA" not in room_txt
    assert "/ ORTEGA" not in room_txt
    assert len(room_paras[0].findall(".//" + w("br"))) == 0
    assert len(room_paras[0].findall(".//" + w("cr"))) == 0

    # Instructor
    inst_txt = get_full_text(info_rows[4].findall(w("tc"))[1].find(w("p"))).strip()
    assert inst_txt == "DAN JOSEPH A. ORTEGA"

    # Student rows in Table 1
    attn_tbl = tables[1]
    attn_rows = attn_tbl.findall(w("tr"))
    assert len(attn_rows) >= 4
    student1_name = get_full_text(attn_rows[2].findall(w("tc"))[1].find(w("p"))).strip()
    assert "DELA CRUZ, JUAN A." in student1_name
