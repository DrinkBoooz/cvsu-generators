import os
import json
import tempfile
import pytest
from modules.models.workspace import SemesterWorkspace, sanitize_workspace_id
from modules.models.student import Student
from modules.common.config_manager import ParserConfigManager
from modules.parsers.smart_ingest import (
    SmartIngestClassifier,
    CATEGORY_SCHEDULE,
    CATEGORY_ROSTER,
    CATEGORY_TEMPLATE,
    CATEGORY_CALENDAR,
    CATEGORY_ORG_PRESET,
    CATEGORY_WORKSPACE,
    CATEGORY_UNKNOWN,
)
from modules.parsers.roster_parser import compute_roster_diff
from executable_test.api.config import ConfigMixin
from executable_test.api.schedule_roster import ScheduleRosterMixin
from executable_test.api.base import BaseAPI


class DummyMockAPI(BaseAPI, ConfigMixin, ScheduleRosterMixin):
    """Mock API harness combining BaseAPI, ConfigMixin, and ScheduleRosterMixin for unit testing."""
    def __init__(self):
        super().__init__()
        self.active_template_set = "builtin_cvsu"


@pytest.fixture
def temp_config_manager(tmp_path):
    """Provides an isolated ParserConfigManager in a temporary directory."""
    cfg_dir = str(tmp_path / "config")
    os.makedirs(cfg_dir, exist_ok=True)
    mgr = ParserConfigManager(config_dir=cfg_dir)
    return mgr


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SemesterWorkspace Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_semester_workspace_initialization():
    ws = SemesterWorkspace(
        name="1st Sem AY 2026-2027",
        schedule_path="C:/CvSU/schedule.xlsx",
        rosters=["C:/CvSU/roster1.xlsx", "C:/CvSU/roster2.xlsx"],
        output_dir="C:/CvSU/Output",
    )
    assert ws.name == "1st Sem AY 2026-2027"
    assert ws.workspace_id == "1st-sem-ay-2026-2027"
    assert len(ws.rosters) == 2
    assert ws.created_at != ""
    assert ws.updated_at != ""
    assert ws.validate() == []


def test_semester_workspace_sanitize_id():
    assert sanitize_workspace_id("1st Sem / AY 2026..2027") == "1st-sem-ay-2026-2027"
    assert sanitize_workspace_id("") == "default_workspace"
    assert sanitize_workspace_id("test\x00malicious") == "test-malicious"


def test_semester_workspace_validation_errors():
    ws = SemesterWorkspace(name="", workspace_id="")
    errors = ws.validate()
    assert any("Workspace name cannot be empty" in e for e in errors)

    ws_bad_types = SemesterWorkspace(
        name="Valid",
        rosters="not-a-list",  # invalid
        organization_preset="not-a-dict",  # invalid
    )
    errors = ws_bad_types.validate()
    assert any("rosters must be a list" in e for e in errors)
    assert any("organization_preset must be a dictionary" in e for e in errors)


def test_semester_workspace_serialization_round_trip():
    ws = SemesterWorkspace(
        name="2nd Sem AY 2026-2027",
        schedule_path="C:/CvSU/sched.xlsx",
        rosters=["C:/CvSU/r1.xlsx"],
        organization_preset={"campus": "Main Campus", "signatories": []},
        calendar_config={"rules": [], "exceptions": []},
        selected_classes=["cls_1", "cls_2"],
        class_type_overrides={"cls_1": "lecture_only"},
    )
    d = ws.to_dict()
    assert d["name"] == "2nd Sem AY 2026-2027"
    assert d["class_type_overrides"]["cls_1"] == "lecture_only"

    restored = SemesterWorkspace.from_dict(d)
    assert restored.name == ws.name
    assert restored.workspace_id == ws.workspace_id
    assert restored.selected_classes == ["cls_1", "cls_2"]
    assert restored.organization_preset["campus"] == "Main Campus"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ConfigManager Workspace Persistence Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_config_manager_workspace_crud(temp_config_manager):
    mgr = temp_config_manager

    # 1. Initially empty
    workspaces = mgr.list_workspaces()
    assert workspaces == []

    # 2. Save workspace
    save_res = mgr.save_workspace("Midyear 2026", {
        "schedule_path": "C:/CvSU/midyear_sched.xlsx",
        "rosters": ["C:/CvSU/r1.xlsx"],
        "output_dir": "C:/CvSU/Out",
    })
    assert save_res["status"] == "success"
    ws_id = save_res["workspace"]["workspace_id"]
    assert ws_id == "midyear-2026"

    # 3. List contains newly saved workspace
    workspaces = mgr.list_workspaces()
    assert len(workspaces) == 1
    assert workspaces[0]["name"] == "Midyear 2026"
    assert workspaces[0]["rosters_count"] == 1

    # 4. Get by ID and by Name
    by_id = mgr.get_workspace("midyear-2026")
    assert by_id is not None
    assert by_id["name"] == "Midyear 2026"

    by_name = mgr.get_workspace("Midyear 2026")
    assert by_name is not None
    assert by_name["workspace_id"] == "midyear-2026"

    # 5. Delete workspace
    del_res = mgr.delete_workspace("midyear-2026")
    assert del_res["status"] == "success"
    assert mgr.list_workspaces() == []


def test_config_manager_workspace_export_import(temp_config_manager, tmp_path):
    mgr = temp_config_manager
    mgr.save_workspace("Fall AY 2026", {
        "schedule_path": "C:/CvSU/fall.xlsx",
        "rosters": ["C:/CvSU/r1.xlsx", "C:/CvSU/r2.xlsx"],
    })

    export_path = str(tmp_path / "export_test.cvsu-workspace.json")

    # Export
    exp_res = mgr.export_workspace_file(export_path, workspace_id_or_name="fall-ay-2026")
    assert exp_res["status"] == "success"
    assert os.path.isfile(export_path)

    # Rejection of invalid extension
    bad_ext = str(tmp_path / "malicious.exe")
    bad_res = mgr.export_workspace_file(bad_ext, workspace_id_or_name="fall-ay-2026")
    assert bad_res["status"] == "error"

    # Import into a second isolated ConfigManager
    other_dir = str(tmp_path / "other_mgr" / "config")
    other_mgr = ParserConfigManager(config_dir=other_dir)
    assert other_mgr.list_workspaces() == []

    imp_res = other_mgr.import_workspace_file(export_path)
    assert imp_res["status"] == "success"
    assert imp_res["workspace"]["name"] == "Fall AY 2026"

    # Verify second manager now has it stored
    assert len(other_mgr.list_workspaces()) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SmartIngestClassifier Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_smart_ingest_classification(tmp_path):
    classifier = SmartIngestClassifier()

    # Workspace snapshot
    ws_file = str(tmp_path / "test.cvsu-workspace.json")
    with open(ws_file, "w", encoding="utf-8") as f:
        json.dump({"workspace_id": "test-ws", "name": "Test Workspace", "schedule_path": ""}, f)
    res = classifier.classify_file(ws_file)
    assert res["category"] == CATEGORY_WORKSPACE

    # Org preset
    org_file = str(tmp_path / "preset.cvsu-org.json")
    with open(org_file, "w", encoding="utf-8") as f:
        json.dump({"campus": "Main", "college": "CEIT", "signatories": []}, f)
    res = classifier.classify_file(org_file)
    assert res["category"] == CATEGORY_ORG_PRESET

    # iCalendar
    ics_file = str(tmp_path / "calendar.ics")
    with open(ics_file, "w", encoding="utf-8") as f:
        f.write("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR")
    res = classifier.classify_file(ics_file)
    assert res["category"] == CATEGORY_CALENDAR

    # Word template
    docx_file = str(tmp_path / "template.docx")
    with open(docx_file, "w", encoding="utf-8") as f:
        f.write("fake docx")
    res = classifier.classify_file(docx_file)
    assert res["category"] == CATEGORY_TEMPLATE

    # Tabular: Schedule filename
    sched_file = str(tmp_path / "FACULTY_SCHEDULE_2026.xlsx")
    with open(sched_file, "w", encoding="utf-8") as f:
        f.write("fake xlsx")
    res = classifier.classify_file(sched_file)
    assert res["category"] == CATEGORY_SCHEDULE

    # Tabular: Roster filename
    roster_file = str(tmp_path / "COSC 101 List of Students for 12345.xlsx")
    with open(roster_file, "w", encoding="utf-8") as f:
        f.write("fake xlsx")
    res = classifier.classify_file(roster_file)
    assert res["category"] == CATEGORY_ROSTER

    # Unknown
    unknown_file = str(tmp_path / "notes.txt")
    with open(unknown_file, "w", encoding="utf-8") as f:
        f.write("hello")
    res = classifier.classify_file(unknown_file)
    assert res["category"] == CATEGORY_UNKNOWN


def test_smart_ingest_batch_routing(tmp_path):
    classifier = SmartIngestClassifier()
    api = DummyMockAPI()

    sched_file = str(tmp_path / "FACULTY_SCHEDULE.xlsx")
    with open(sched_file, "w", encoding="utf-8") as f:
        f.write("fake")

    roster_file = str(tmp_path / "Students_Roster.xlsx")
    with open(roster_file, "w", encoding="utf-8") as f:
        f.write("fake")

    res = classifier.ingest_files([sched_file, roster_file], app_api=api)
    assert res["status"] == "success"
    assert len(res["classified_items"]) == 2
    assert res["summary"]["schedule"] == "FACULTY_SCHEDULE.xlsx"
    assert res["summary"]["rosters_added"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Smart Roster Diffing Engine Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_compute_roster_diff_additions_and_drops():
    old_students = [
        ("Juan Dela Cruz", "20241001"),
        ("Maria Santos", "20241002"),
        ("Pedro Reyes", "20241003"),
    ]
    # Mid-semester update: Pedro dropped, Ana Lim added
    new_students = [
        ("Juan Dela Cruz", "20241001"),
        ("Maria Santos", "20241002"),
        ("Ana Lim", "20241004"),
    ]

    diff = compute_roster_diff(old_students, new_students)
    assert diff["has_changes"] is True
    assert diff["counts"]["added"] == 1
    assert diff["counts"]["removed"] == 1
    assert diff["counts"]["modified"] == 0
    assert diff["counts"]["unchanged"] == 2

    assert diff["added"][0]["name"] == "Ana Lim"
    assert diff["added"][0]["student_number"] == "20241004"
    assert diff["removed"][0]["name"] == "Pedro Reyes"
    assert diff["removed"][0]["student_number"] == "20241003"


def test_compute_roster_diff_modified_name_or_id():
    old_students = [
        Student(name="Juan Dela Cruz", student_number="20241001"),
        Student(name="Corrupted Name Ã±", student_number="20241002"),
    ]
    new_students = [
        # Student 1: same ID, corrected name spelling (e.g. married name or middle initial)
        {"name": "Juan M. Dela Cruz", "student_number": "20241001"},
        # Student 2: name fixed from portal corrupt encoding
        {"name": "Corrupted Name Ñ", "student_number": "20241002"},
    ]

    diff = compute_roster_diff(old_students, new_students)
    assert diff["has_changes"] is True
    assert diff["counts"]["modified"] == 1  # Juan M. Dela Cruz has modified alphanumeric token
    assert diff["counts"]["unchanged"] == 1  # Corrupted Name Ñ and Ã± normalize identically!
    assert diff["counts"]["added"] == 0
    assert diff["counts"]["removed"] == 0


def test_compute_roster_diff_identical():
    students = [
        ("Santos, Maria A.", "20230001"),
        ("Dela Cruz, Juan B.", "20230002"),
    ]
    diff = compute_roster_diff(students, students)
    assert diff["has_changes"] is False
    assert diff["counts"]["added"] == 0
    assert diff["counts"]["removed"] == 0
    assert diff["counts"]["modified"] == 0
    assert diff["counts"]["unchanged"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Bridge API Methods Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_bridge_workspace_and_diff_endpoints(tmp_path):
    api = DummyMockAPI()

    # Test save_workspace & list_workspaces
    save_res = api.save_workspace("Semester 1", {
        "schedule_path": "C:/path/to/sched.xlsx",
        "rosters": ["C:/path/to/roster.xlsx"],
        "output_dir": "C:/CvSU/Output",
    })
    assert save_res["status"] == "success"

    ws_list = api.list_workspaces()
    assert len(ws_list) >= 1
    assert any(w["name"] == "Semester 1" for w in ws_list)

    # Test load_workspace
    load_res = api.load_workspace("semester-1")
    assert load_res["status"] == "success"
    assert api.schedule_path == "C:/path/to/sched.xlsx"
    assert api.output_dir == "C:/CvSU/Output"
    assert len(api.rosters) == 1

    # Test delete_workspace
    del_res = api.delete_workspace("semester-1")
    assert del_res["status"] == "success"

    # Test preview_roster_diff with missing file
    diff_err = api.preview_roster_diff("COSC 101", "non_existent_file.xlsx")
    assert diff_err["status"] == "error"
