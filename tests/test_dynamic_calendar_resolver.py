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

    assert date(2026, 9, 2) in holiday_map_2026
    assert "Cavite Day" in holiday_map_2026[date(2026, 9, 2)]

    assert date(2026, 8, 31) in holiday_map_2026
    assert "National Heroes Day" in holiday_map_2026[date(2026, 8, 31)]

    # Check 2027 holidays without hardcoding
    holidays_2027 = resolver.get_recurring_holidays(2027)
    holiday_map_2027 = {h.start_date: h.label for h in holidays_2027}
    assert date(2027, 9, 2) in holiday_map_2027
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

    # Test baseline: Aug 24 is SUSPENDED, Sep 2 is HOLIDAY (Layer 1 Cavite Day)
    res_aug24 = resolver.resolve_date(date(2026, 8, 24))
    assert res_aug24.status == "SUSPENDED"

    res_sep2 = resolver.resolve_date(date(2026, 9, 2))
    assert res_sep2.status == "HOLIDAY"

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
    assert student_date_texts[3] == "SUSP."
    assert student_date_texts[4] == "HOLIDAY"


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

