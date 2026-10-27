"""
Unit and integration tests for Phase 7:
100% Offline, 3-Layer Dynamic Academic Calendar, Holiday & Suspension Engine.

Covers:
- Layer 1: Algorithmic Recurrence Rule Engine (fixed date, nth weekday across multi-year)
- Layer 2: Offline .ics (iCalendar) parser & Smart Announcement Text/CSV parser
- Layer 3: Per-Date Interactive Overrides and precedence resolution
- Attendance Generator Matrix Rendering:
  - Mode A: OMIT_COLUMN (removes non-working dates from columns)
  - Mode B: STAMP_COLUMN (keeps columns and stamps status labels in student rows)
"""

import os
import tempfile
from datetime import date
from lxml import etree
import pytest

from modules.models.calendar import (
    CalendarException,
    RecurrenceRule,
    CalendarExceptionCategory,
    CalendarExceptionMode,
)
from modules.parsers.calendar_resolver import (
    CalendarResolver,
    compute_nth_weekday,
    parse_ics_content,
    parse_announcement_lines,
    get_default_cavite_recurrence_rules,
)
from modules.generators.attendance_gen import (
    AttendanceGenerator,
    build_attendance_sheet,
    get_default_template_path,
)
from modules.services.template_recipe_service import TemplateRecipeResolver
from modules.common.docx_utils import load_docx, w, wt

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1: Algorithmic Recurrence Rule Engine Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_nth_weekday_last_monday_of_august():
    """National Heroes Day is celebrated on the last Monday of August."""
    # 2026: August 31 is the last Monday
    d_2026 = compute_nth_weekday(year=2026, month=8, weekday=0, nth="last")
    assert d_2026 == date(2026, 8, 31)

    # 2027: August 30 is the last Monday
    d_2027 = compute_nth_weekday(year=2027, month=8, weekday=0, nth="last")
    assert d_2027 == date(2027, 8, 30)

    # 2028: August 28 is the last Monday (leap year)
    d_2028 = compute_nth_weekday(year=2028, month=8, weekday=0, nth="last")
    assert d_2028 == date(2028, 8, 28)


def test_compute_nth_weekday_first_and_second_occurrences():
    """Verify 1st, 2nd, 3rd occurrence calculations."""
    # 1st Friday of January 2026: Jan 2
    first_fri = compute_nth_weekday(year=2026, month=1, weekday=4, nth=1)
    assert first_fri == date(2026, 1, 2)

    # 2nd Monday of February 2026: Feb 9
    sec_mon = compute_nth_weekday(year=2026, month=2, weekday=0, nth=2)
    assert sec_mon == date(2026, 2, 9)


def test_recurrence_rule_fixed_and_provincial_holidays():
    """Test resolution of fixed national holidays and Cavite Day (Sept 2)."""
    rules = get_default_cavite_recurrence_rules()
    resolver = CalendarResolver(rules=rules)
    
    # Check 2026 holidays
    holidays_2026 = resolver.get_recurring_holidays(2026)
    holiday_map_2026 = {h.start_date: h.label for h in holidays_2026}

    assert date(2026, 1, 1) in holiday_map_2026
    assert "New Year" in holiday_map_2026[date(2026, 1, 1)]

    assert date(2026, 6, 12) in holiday_map_2026
    assert "Independence" in holiday_map_2026[date(2026, 6, 12)]

    assert date(2026, 3, 22) in holiday_map_2026
    assert "Cavite Day" in holiday_map_2026[date(2026, 3, 22)]

    assert date(2026, 8, 31) in holiday_map_2026
    assert "National Heroes Day" in holiday_map_2026[date(2026, 8, 31)]

    # Check 2027 holidays without hardcoding
    holidays_2027 = resolver.get_recurring_holidays(2027)
    holiday_map_2027 = {h.start_date: h.label for h in holidays_2027}
    assert date(2027, 3, 22) in holiday_map_2027
    assert date(2027, 8, 30) in holiday_map_2027


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2: Offline .ics and Announcement Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_ics_offline():
    """Verify parsing standard iCalendar (.ics) format with folded lines and date ranges."""
    ics_sample = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CvSU//Academic Calendar//EN
BEGIN:VEVENT
UID:midterm-2026@cvsu.edu.ph
SUMMARY:Midterm Examination
  Week
DTSTART;VALUE=DATE:20261020
DTEND;VALUE=DATE:20261025
DESCRIPTION:Midterm Examination for All Colleges
END:VEVENT
BEGIN:VEVENT
UID:typhoon-20260824@cvsu.edu.ph
SUMMARY:Typhoon Suspension - Walang Pasok
DTSTART;VALUE=DATE:20260824
DTEND;VALUE=DATE:20260825
END:VEVENT
BEGIN:VEVENT
UID:all-souls-2026@cvsu.edu.ph
SUMMARY:All Souls' Day Special Non-Working Holiday
DTSTART:20261102T000000Z
END:VEVENT
END:VCALENDAR"""

    exceptions = parse_ics_content(ics_sample)
    assert len(exceptions) == 3

    # Event 1: Multi-day Midterm Exam (DTEND in iCal DATE is exclusive, so Oct 20-24)
    exam = exceptions[0]
    assert exam.label == "Midterm Examination Week"
    assert exam.start_date == date(2026, 10, 20)
    assert exam.end_date == date(2026, 10, 24)
    assert exam.category == "EXAM"

    # Event 2: Typhoon Suspension
    susp = exceptions[1]
    assert "Typhoon Suspension" in susp.label
    assert susp.start_date == date(2026, 8, 24)
    assert susp.end_date == date(2026, 8, 24)
    assert susp.category == CalendarExceptionCategory.SUSPENDED

    # Event 3: Single day holiday with timestamp
    hol = exceptions[2]
    assert "All Souls' Day" in hol.label
    assert hol.start_date == date(2026, 11, 2)
    assert hol.category == "HOLIDAY"


def test_parse_announcement_natural_text_and_csv():
    """Verify parsing natural memo announcements and CSV lines."""
    raw_text = """
    # Official CvSU Academic Announcements
    Oct 20-24, 2026: Midterm Examination Week
    Nov 2, 2026 - All Souls' Day (Special Non-Working Holiday)
    Aug 24, 2026: Typhoon Suspension due to Tropical Storm
    2026-09-02: Cavite Day
    2026-12-14 to 2026-12-18, Final Examination Week, EXAM, STAMP_COLUMN
    #WalangPasok: Sept 25, 2026 - Heavy Rain Suspension
    """
    exceptions = parse_announcement_lines(raw_text, default_year=2026)
    assert len(exceptions) == 6

    # Midterm exam range
    assert exceptions[0].start_date == date(2026, 10, 20)
    assert exceptions[0].end_date == date(2026, 10, 24)
    assert exceptions[0].category == "EXAM"

    # Single day holiday
    assert exceptions[1].start_date == date(2026, 11, 2)
    assert exceptions[1].category == "HOLIDAY"

    # Typhoon suspension
    assert exceptions[2].start_date == date(2026, 8, 24)
    assert exceptions[2].category == CalendarExceptionCategory.SUSPENDED

    # ISO date single day
    assert exceptions[3].start_date == date(2026, 9, 2)
    assert exceptions[3].category == "HOLIDAY"

    # CSV with explicit category and mode
    assert exceptions[4].start_date == date(2026, 12, 14)
    assert exceptions[4].end_date == date(2026, 12, 18)
    assert exceptions[4].category == "EXAM"
    assert exceptions[4].mode == "STAMP_COLUMN"

    # #WalangPasok hashtag
    assert exceptions[5].start_date == date(2026, 9, 25)
    assert exceptions[5].category == CalendarExceptionCategory.SUSPENDED


# ─────────────────────────────────────────────────────────────────────────────
# Layer 3: Interactive Overrides & Precedence Resolution Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_layer3_overrides_precedence():
    """Verify Layer 3 manual overrides take priority over Layer 1 & 2."""
    rules = get_default_cavite_recurrence_rules()
    resolver = CalendarResolver(rules=rules)
    
    # Layer 2 adds typhoon suspension on Aug 24, 2026
    resolver.add_exception(CalendarException(
        start_date=date(2026, 8, 24),
        end_date=date(2026, 8, 24),
        label="Typhoon Suspension",
        category="SUSPENSION",
        mode="OMIT_COLUMN",
    ))

    # Test baseline: Aug 24 is SUSPENDED, Mar 22 is HOLIDAY (Layer 1 Cavite Day)
    res_aug24 = resolver.resolve_date(date(2026, 8, 24))
    assert res_aug24.status == "SUSPENDED"

    res_mar22 = resolver.resolve_date(date(2026, 3, 22))
    assert res_mar22.status == "HOLIDAY"

    # Override 1: Instructor overrides Aug 24 to ACTIVE (make-up class / asynchronous session)
    resolver.set_date_override(date(2026, 8, 24), status="ACTIVE", label="Make-up Class")
    res_aug24_override = resolver.resolve_date(date(2026, 8, 24))
    assert res_aug24_override.status == "ACTIVE"
    assert res_aug24_override.label == "Make-up Class"

    # Override 2: Override regular active date to SUSPENDED
    res_aug25 = resolver.resolve_date(date(2026, 8, 25))
    assert res_aug25.status == "ACTIVE"

    resolver.set_date_override(date(2026, 8, 25), status="SUSPENDED", label="Transport Strike", mode="STAMP_COLUMN")
    res_aug25_override = resolver.resolve_date(date(2026, 8, 25))
    assert res_aug25_override.status == "SUSPENDED"
    assert res_aug25_override.label == "Transport Strike"
    assert res_aug25_override.mode == "STAMP_COLUMN"


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Matrix Rendering Modes (OMIT_COLUMN vs STAMP_COLUMN)
# ─────────────────────────────────────────────────────────────────────────────

def test_attendance_generation_omit_column_mode(tmp_path):
    """
    Mode A (OMIT_COLUMN): Exclude non-working dates from the column sequence
    so only active class meetings occupy columns.
    """
    template_path = get_default_template_path(has_lab=False)
    output_docx = str(tmp_path / "attendance_omit_mode.docx")

    # August 2026: Mondays are Aug 3, 10, 17, 24, 31 (5 Mondays).
    # Aug 31 is National Heroes Day (Holiday).
    # In OMIT_COLUMN mode, Aug 31 should NOT be in the column sequence (only 4 dates: 3, 10, 17, 24).
    resolver = CalendarResolver(rules=get_default_cavite_recurrence_rules())
    resolver.default_mode = "OMIT_COLUMN"

    students = [
        ("Ortega, Dan Joseph", "202010123"),
        ("Dela Cruz, Juan", "202010124"),
    ]

    recipe = TemplateRecipeResolver.get_instance().resolve(template_path, profile_id="attendance_docx")
    generator = AttendanceGenerator(template_path, recipe)
    
    generator.generate(
        output_path=output_docx,
        course_code_title="COSC 101 - Advanced Programming",
        class_schedule="7:00-10:00AM / Mon",
        semester_ay="First Semester / A.Y. 2026-2027",
        room_assignment="CL 1",
        instructor="Dan Joseph Ortega",
        months=[8],
        year=2026,
        weekdays=[0],  # Monday
        students=students,
        calendar_resolver=resolver,
    )

    assert os.path.exists(output_docx)
    zin, root, body = load_docx(output_docx)
    tables = body.findall(w("tbl"))
    matrix_tbl = tables[1]
    rows = matrix_tbl.findall(w("tr"))
    
    # Check header row 1 (dates)
    header1 = rows[1]
    cells = header1.findall(w("tc"))
    # Lead cols (3: No, Name, Stnum), then date columns, then summary cols (3: LB, LC, R)
    # With 4 Mondays, date cols = 4
    date_cells = cells[3:7]
    date_texts = ["".join(tc.itertext()).strip() for tc in date_cells]
    
    assert "3" in date_texts
    assert "10" in date_texts
    assert "17" in date_texts
    assert "24" in date_texts
    # Aug 31 was omitted
    assert "31" not in date_texts


def test_attendance_generation_stamp_column_mode(tmp_path):
    """
    Mode B (STAMP_COLUMN): Keep non-working dates in the header row and stamp
    compact status tags (HOLIDAY, SUSP., EXAM, EVENT) into student rows.
    """
    template_path = get_default_template_path(has_lab=False)
    output_docx = str(tmp_path / "attendance_stamp_mode.docx")

    resolver = CalendarResolver(rules=get_default_cavite_recurrence_rules())
    resolver.default_mode = "STAMP_COLUMN"
    # Aug 24: Typhoon suspension (SUSP.)
    resolver.set_date_override(date(2026, 8, 24), status="SUSPENDED", label="Typhoon", mode="STAMP_COLUMN")
    # Aug 31: National Heroes Day (HOLIDAY) via Layer 1

    students = [
        ("Ortega, Dan Joseph", "202010123"),
        ("Dela Cruz, Juan", "202010124"),
    ]

    recipe = TemplateRecipeResolver.get_instance().resolve(template_path, profile_id="attendance_docx")
    generator = AttendanceGenerator(template_path, recipe)
    
    generator.generate(
        output_path=output_docx,
        course_code_title="COSC 101 - Advanced Programming",
        class_schedule="7:00-10:00AM / Mon",
        semester_ay="First Semester / A.Y. 2026-2027",
        room_assignment="CL 1",
        instructor="Dan Joseph Ortega",
        months=[8],
        year=2026,
        weekdays=[0],  # Monday
        students=students,
        calendar_resolver=resolver,
    )

    assert os.path.exists(output_docx)
    zin, root, body = load_docx(output_docx)
    tables = body.findall(w("tbl"))
    matrix_tbl = tables[1]
    rows = matrix_tbl.findall(w("tr"))
    
    # Header row 1 should contain all 5 Mondays (3, 10, 17, 24, 31)
    header1 = rows[1]
    cells = header1.findall(w("tc"))
    date_cells = cells[3:8]
    date_texts = ["".join(tc.itertext()).strip() for tc in date_cells]
    assert date_texts == ["3", "10", "17", "24", "31"]

    # Student row 1 (row index 2) should have:
    # Col index 3 (Aug 3): ""
    # Col index 4 (Aug 10): ""
    # Col index 5 (Aug 17): ""
    # Col index 6 (Aug 24): "SUSP."
    # Col index 7 (Aug 31): "HOLIDAY"
    student_row1 = rows[2]
    student_cells = student_row1.findall(w("tc"))
    student_date_cells = student_cells[3:8]
    student_date_texts = ["".join(tc.itertext()).strip() for tc in student_date_cells]
    
    assert student_date_texts[0] == ""
    assert student_date_texts[1] == ""
    assert student_date_texts[2] == ""
    assert student_date_texts[3] == "Suspension (Typhoon)"
    assert student_date_texts[4] == "Holiday (National Heroes Day)"


def test_attendance_generation_leave_and_adm_stamping(tmp_path):
    """
    Verifies that AttendanceGenerator with STAMP_COLUMN mode correctly stamps
    'LEAVE' for instructor personal leaves and 'ADM' for alternative learning modalities.
    """
    template_path = get_default_template_path(has_lab=False)
    output_docx = str(tmp_path / "attendance_leave_adm_stamp.docx")

    exc_leave = CalendarException(
        start_date=date(2026, 10, 7),
        end_date=date(2026, 10, 7),
        label="Instructor On Leave",
        category=CalendarExceptionCategory.INSTRUCTOR_LEAVE,
        mode="STAMP_COLUMN",
    )
    exc_adm = CalendarException(
        start_date=date(2026, 10, 14),
        end_date=date(2026, 10, 14),
        label="Shift to ADM Modality",
        category=CalendarExceptionCategory.ADM_ASYNC,
        mode="STAMP_COLUMN",
    )
    resolver = CalendarResolver(rules=[], exceptions=[exc_leave, exc_adm], default_mode="STAMP_COLUMN")

    students = [
        ("Ortega, Dan Joseph", "202010123"),
    ]

    recipe = TemplateRecipeResolver.get_instance().resolve(template_path, profile_id="attendance_docx")
    generator = AttendanceGenerator(template_path, recipe)

    generator.generate(
        output_path=output_docx,
        course_code_title="COSC 101 - Advanced Programming",
        class_schedule="7:00-10:00AM / Wed",
        semester_ay="First Semester / A.Y. 2026-2027",
        room_assignment="CL 1",
        instructor="Dan Joseph Ortega",
        months=[10],
        year=2026,
        weekdays=[2],  # Wednesday (Oct 7, 14, 21, 28)
        students=students,
        calendar_resolver=resolver,
    )

    assert os.path.exists(output_docx)
    zin, root, body = load_docx(output_docx)
    tables = body.findall(w("tbl"))
    matrix_tbl = tables[1]
    rows = matrix_tbl.findall(w("tr"))

    # Header dates (Oct 7, 14, 21, 28)
    header1 = rows[1]
    cells = header1.findall(w("tc"))
    date_cells = cells[3:7]
    date_texts = ["".join(tc.itertext()).strip() for tc in date_cells]
    assert date_texts == ["7", "14", "21", "28"]

    # Student row: Oct 7 has "LEAVE", Oct 14 has "ADM", Oct 21 and 28 are active ("")
    student_row1 = rows[2]
    student_cells = student_row1.findall(w("tc"))
    student_date_cells = student_cells[3:7]
    student_date_texts = ["".join(tc.itertext()).strip() for tc in student_date_cells]

    assert student_date_texts[0] == "Leave (Instructor On Leave)"
    assert student_date_texts[1] == "ADM (Shift to ADM Modality)"
    assert student_date_texts[2] == ""
    assert student_date_texts[3] == ""


# ─────────────────────────────────────────────────────────────────────────────
# Bridge API & UI Accessibility Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_calendar_config_mixin_bridge_endpoints():
    """Verify PyWebView bridge methods for calendar configuration and date preview."""
    from executable_test.api.config import ConfigMixin
    
    bridge = ConfigMixin()
    
    # 1. get_calendar_config
    cal_cfg = bridge.get_calendar_config()
    assert isinstance(cal_cfg, dict)
    assert "default_mode" in cal_cfg
    assert "rules" in cal_cfg
    assert len(cal_cfg["rules"]) >= 10
    
    # 2. preview_calendar_dates
    preview = bridge.preview_calendar_dates({
        "year": 2026,
        "months": [8],
        "weekdays": [0],
        "calendar_config": {
            "default_mode": "OMIT_COLUMN",
            "rules": cal_cfg["rules"],
            "exceptions": [],
            "overrides": {"2026-08-24": "SUSPENDED"}
        }
    })
    assert preview["status"] == "success"
    dates = preview["dates"]
    assert len(dates) == 5
    aug24 = next(d for d in dates if d["date_str"] == "2026-08-24")
    assert aug24["category"] == "SUSPENDED"
    assert aug24["is_working"] is False

    # 3. parse_calendar_announcement
    parsed = bridge.parse_calendar_announcement(
        "Oct 20-24, 2026: Midterm Examination Week\nNov 2, 2026 - All Souls' Day"
    )
    assert parsed["status"] == "success"
    assert parsed["count"] >= 2
    exceptions = parsed["exceptions"]
    assert any(e["label"] == "Midterm Examination Week" for e in exceptions)


def test_ui_calendar_tab_and_accessibility_attributes():
    """Verify presence and accessibility contracts of the calendar UI in ui.html."""
    ui_path = os.path.join(REPO_ROOT, "executable_test", "ui.html")
    assert os.path.exists(ui_path)
    with open(ui_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Tab navigation button
    assert 'id="cfgTabCalendar"' in html
    assert "switchConfigTab('Calendar')" in html
    assert "Academic Calendar" in html

    # Tab content pane
    assert 'id="cfgPaneCalendar"' in html
    assert 'role="tabpanel"' in html
    assert 'aria-labelledby="cfgTabCalendar"' in html

    # Required controls
    assert 'id="calExceptionModeSelect"' in html
    assert "OMIT_COLUMN" in html
    assert "STAMP_COLUMN" in html

    assert 'id="calAnnouncementInput"' in html
    assert 'id="btnParseAnnouncement"' in html
    assert 'id="btnImportIcs"' in html
    assert 'id="btnClearCalendarExceptions"' in html
    assert 'id="btnResetCalendarOverrides"' in html

    assert 'id="calYearSelect"' in html
    assert 'id="calSemesterSelect"' in html
    assert 'id="calMeetingDaysSelect"' in html
    assert 'id="calDateStripContainer"' in html
    assert 'id="calDateStripStats"' in html
    assert 'id="calRecurrenceRulesList"' in html

    # New preset loader and structured exceptions table controls
    assert 'id="calPresetSelect"' in html
    assert 'id="btnLoadCalPreset"' in html
    assert 'id="calendarExceptionsTable"' in html
    assert 'id="calExceptionsTableBody"' in html
    assert 'id="calAddExceptionForm"' in html
    assert 'id="btnOpenAddExceptionModal"' in html


def test_time_aware_slot_sensitivity_and_suspension_thresholds():
    """
    Real-world verification using the historical CvSU Indang August 2026 data:
    - Aug 14, 2026: Executive Order No. 27 suspended classes from 12:00 NN onwards.
      Morning class (7:00-10:00 AM) finished completely without disruption -> ACTIVE.
      Afternoon class (1:00-4:00 PM) was disrupted -> SUSPENDED.
    - Aug 28, 2026: Memorandum Circular No. 132 suspended classes from 1:00 PM onwards.
      Morning class (7:00-10:00 AM) finished -> ACTIVE.
      Midday class (10:00 AM-1:00 PM) finished right at 1:00 PM -> ACTIVE.
      Afternoon class (1:00-4:00 PM) disrupted -> SUSPENDED.
    """
    from modules.models.calendar import CalendarTimeScope
    from modules.parsers.calendar_resolver import parse_class_time_range

    # Verify time range parser
    assert parse_class_time_range("07:00-10:00AM") == (420, 600)
    assert parse_class_time_range("7:00-10:00AM") == (420, 600)
    assert parse_class_time_range("1:00-4:00PM") == (780, 960)
    assert parse_class_time_range("10:00AM-1:00PM") == (600, 780)
    assert parse_class_time_range("12:00NN-3:00PM") == (720, 900)

    # Setup resolver with August 14 and August 28 exceptions
    exc_aug14 = CalendarException(
        start_date=date(2026, 8, 14),
        end_date=date(2026, 8, 14),
        label="Executive Order No. 27 (Suspension from 12:00 NN onwards)",
        category=CalendarExceptionCategory.SUSPENDED,
        time_scope=CalendarTimeScope.MIDDAY_ONWARDS,
    )
    exc_aug28 = CalendarException(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 28),
        label="Memorandum Circular No. 132 (Suspension from 1:00 PM onwards)",
        category=CalendarExceptionCategory.SUSPENDED,
        time_scope=CalendarTimeScope.AFTERNOON_1PM,
    )
    resolver = CalendarResolver(rules=[], exceptions=[exc_aug14, exc_aug28])

    # Aug 14: Morning class (7-10 AM) is unaffected
    res_morning_14 = resolver.resolve_date(date(2026, 8, 14), class_time_range="07:00-10:00AM")
    assert res_morning_14.is_working_session is True
    assert res_morning_14.status == CalendarExceptionCategory.ACTIVE

    # Aug 14: Afternoon class (1-4 PM) is suspended
    res_afternoon_14 = resolver.resolve_date(date(2026, 8, 14), class_time_range="1:00-4:00PM")
    assert res_afternoon_14.is_working_session is False
    assert res_afternoon_14.status == CalendarExceptionCategory.SUSPENDED
    assert "Executive Order No. 27" in res_afternoon_14.label

    # Aug 28: Morning class (7-10 AM) is unaffected
    res_morning_28 = resolver.resolve_date(date(2026, 8, 28), class_time_range="07:00-10:00AM")
    assert res_morning_28.is_working_session is True

    # Aug 28: Midday class (10 AM - 1 PM) is unaffected (finished before 1:00 PM cutoff)
    res_midday_28 = resolver.resolve_date(date(2026, 8, 28), class_time_range="10:00AM-1:00PM")
    assert res_midday_28.is_working_session is True

    # Aug 28: Afternoon class (1-4 PM) is suspended
    res_afternoon_28 = resolver.resolve_date(date(2026, 8, 28), class_time_range="1:00-4:00PM")
    assert res_afternoon_28.is_working_session is False
    assert res_afternoon_28.status == CalendarExceptionCategory.SUSPENDED


def test_instructor_leave_and_adm_modality():
    """Verify instructor leaves (Oct 7, 9) and ADM shift (Oct 14)."""
    exc_leave1 = CalendarException(
        start_date=date(2026, 10, 7),
        end_date=date(2026, 10, 7),
        label="Instructor Personal Leave",
        category=CalendarExceptionCategory.INSTRUCTOR_LEAVE,
    )
    exc_leave2 = CalendarException(
        start_date=date(2026, 10, 9),
        end_date=date(2026, 10, 9),
        label="Instructor On Leave",
        category=CalendarExceptionCategory.INSTRUCTOR_LEAVE,
    )
    exc_adm = CalendarException(
        start_date=date(2026, 10, 14),
        end_date=date(2026, 10, 14),
        label="Provincial Advisory (Shift to ADM Modality)",
        category=CalendarExceptionCategory.ADM_ASYNC,
    )
    resolver = CalendarResolver(rules=[], exceptions=[exc_leave1, exc_leave2, exc_adm])

    res_oct7 = resolver.resolve_date(date(2026, 10, 7))
    assert res_oct7.status == CalendarExceptionCategory.INSTRUCTOR_LEAVE
    assert res_oct7.display_tag == "LEAVE"
    assert res_oct7.is_working_session is False

    res_oct9 = resolver.resolve_date(date(2026, 10, 9))
    assert res_oct9.status == CalendarExceptionCategory.INSTRUCTOR_LEAVE
    assert res_oct9.display_tag == "LEAVE"

    res_oct14 = resolver.resolve_date(date(2026, 10, 14))
    assert res_oct14.status == CalendarExceptionCategory.ADM_ASYNC
    assert res_oct14.display_tag == "ADM"


def test_calendar_presets_api():
    """Verify built-in presets endpoint and preset loading."""
    from executable_test.api.config import ConfigMixin
    bridge = ConfigMixin()

    presets_res = bridge.get_calendar_presets()
    assert presets_res["status"] == "success"
    presets = presets_res["presets"]
    assert any(p["id"] == "cvsu_indang_2026_sem1" for p in presets)

    loaded = bridge.load_calendar_preset("cvsu_indang_2026_sem1")
    assert loaded["status"] == "success"
    assert len(loaded["preset"]["exceptions"]) >= 10
    # Confirm Aug 14 midday and Aug 28 1pm are encoded in preset
    exc_list = loaded["preset"]["exceptions"]
    assert any("2026-08-14" in (e.get("start_date") or "") for e in exc_list)
    assert any("2026-08-28" in (e.get("start_date") or "") for e in exc_list)


def test_attendance_generation_vertically_merged_columns_across_40_rows(tmp_path):
    """
    Verifies that when STAMP_COLUMN mode is active, non-working date columns are joined
    vertically from student row 1 through row 40 using OpenXML <w:vMerge>, preventing
    40 repeated text lines from stretching table row heights onto a 2nd page.
    """
    template_path = get_default_template_path(has_lab=False)
    output_docx = str(tmp_path / "attendance_vmerge_40_rows.docx")

    resolver = CalendarResolver(rules=get_default_cavite_recurrence_rules())
    resolver.default_mode = "STAMP_COLUMN"
    resolver.set_date_override(date(2026, 8, 24), status="SUSPENDED", label="Typhoon Kristine", mode="STAMP_COLUMN")

    # 40 students
    students = [(f"Student {i:02d}, Test", f"2026{i:05d}") for i in range(1, 41)]

    recipe = TemplateRecipeResolver.get_instance().resolve(template_path, profile_id="attendance_docx")
    generator = AttendanceGenerator(template_path, recipe)

    generator.generate(
        output_path=output_docx,
        course_code_title="COSC 101 - Advanced Programming",
        class_schedule="7:00-10:00AM / Mon",
        semester_ay="First Semester / A.Y. 2026-2027",
        room_assignment="CL 1",
        instructor="Dan Joseph Ortega",
        months=[8],
        year=2026,
        weekdays=[0],  # Monday: Aug 3, 10, 17, 24, 31
        students=students,
        calendar_resolver=resolver,
    )

    assert os.path.exists(output_docx)
    zin, root, body = load_docx(output_docx)
    tables = body.findall(w("tbl"))
    matrix_tbl = tables[1]
    rows = matrix_tbl.findall(w("tr"))
    assert len(rows) == 42  # header0, header1, and 40 student rows

    # Aug 24 is at col index 6 (lead cols 0, 1, 2, then dates Aug 3=col 3, Aug 10=col 4, Aug 17=col 5, Aug 24=col 6)
    # 1. Row index 2 (Student 1) must have <w:vMerge w:val="restart"/>, vertical text btLr, and tag "SUSP."
    student1_row = rows[2]
    student1_tc = student1_row.findall(w("tc"))[6]
    tcpr1 = student1_tc.find(w("tcPr"))
    assert tcpr1 is not None
    vmerge1 = tcpr1.find(w("vMerge"))
    assert vmerge1 is not None
    assert vmerge1.get(w("val")) == "restart"
    assert tcpr1.find(w("vAlign")).get(w("val")) == "center"
    assert tcpr1.find(w("textDirection")).get(w("val")) == "btLr"
    assert "".join(student1_tc.itertext()).strip() == "Suspension (Typhoon Kristine)"

    # 2. Rows index 3 through 41 (Students 2 through 40) must have <w:vMerge/> continuation and empty text
    for r_idx in range(3, 42):
        st_row = rows[r_idx]
        st_tc = st_row.findall(w("tc"))[6]
        tcpr = st_tc.find(w("tcPr"))
        assert tcpr is not None, f"Row {r_idx} missing tcPr"
        vmerge = tcpr.find(w("vMerge"))
        assert vmerge is not None, f"Row {r_idx} missing vMerge continuation"
        # OpenXML continuation has no val or val="continue"
        assert vmerge.get(w("val")) is None or vmerge.get(w("val")) == "continue"
        assert "".join(st_tc.itertext()).strip() == "", f"Row {r_idx} continuation cell must be empty"



