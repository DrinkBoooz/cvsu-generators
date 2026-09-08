import os
import sys
import pytest

# Ensure workspace root is on sys.path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

import process_schedule
from executable.main import ScriptAPI

def test_inspect_schedule_file_valid():
    schedule_path = os.path.join(WORKSPACE_DIR, "ORTEGA_SCHEDULE.xls")
    assert os.path.exists(schedule_path), "Test schedule ORTEGA_SCHEDULE.xls must exist"

    info = process_schedule.inspect_schedule_file(schedule_path)
    assert info is not None
    assert "DAN JOSEPH A. ORTEGA" in info["instructor"]
    assert "COLLEGE OF ENGINEERING" in info["college"].upper()
    assert info["total_slots"] > 0
    assert len(info["detected_sections"]) > 0

def test_inspect_schedule_file_invalid():
    res = process_schedule.inspect_schedule_file("non_existent_file.xls")
    assert res is None

def test_validate_rosters_valid_and_invalid(tmp_path):
    schedule_path = os.path.join(WORKSPACE_DIR, "ORTEGA_SCHEDULE.xls")
    
    # Valid filename
    valid_roster = tmp_path / "BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.csv"
    valid_roster.write_text("Name,Student number\nDoe, John,20261001\nSmith, Jane,20261002\n", encoding="utf-8")

    # Invalid filename
    invalid_roster = tmp_path / "Random_Student_List.csv"
    invalid_roster.write_text("Name,Student number\nDoe, John,20261001\n", encoding="utf-8")

    # Extra columns roster
    extra_col_roster = tmp_path / "BSCS3-1 List of Students for 202612041-ITEC 50 - WEB SYSTEMS.csv"
    extra_col_roster.write_text("Name,Student number,Email,Remarks\nDoe, John,20261001,john@cvsu.edu.ph,Regular\n", encoding="utf-8")

    reports = process_schedule.validate_rosters(schedule_path, [
        str(valid_roster),
        str(invalid_roster),
        str(extra_col_roster)
    ])

    assert len(reports) == 3

    # Report 0: Valid
    assert reports[0]["status"] == "valid"
    assert reports[0]["student_count"] == 2
    assert reports[0]["course_sec"] == "CS1-4"
    assert reports[0]["schedule_code"] == "202612040"

    # Report 1: Invalid filename
    assert reports[1]["status"] == "error"
    assert reports[1]["issue"] == "invalid_filename"

    # Report 2: Extra columns warning
    assert reports[2]["status"] == "warning"
    assert reports[2]["issue"] == "extra_columns"
    assert reports[2]["column_count"] == 4
    assert reports[2]["student_count"] == 1

def test_script_api_methods(tmp_path):
    api = ScriptAPI()
    assert api.schedule_path == ""
    assert api.rosters == []
    assert api.output_dir == ""

    # Test clear and remove roster
    api.rosters = ["path1.xlsx", "path2.xlsx", "path3.xlsx"]
    res = api.remove_roster(1)
    assert res["count"] == 2
    assert api.rosters == ["path1.xlsx", "path3.xlsx"]

    res = api.clear_rosters()
    assert res["count"] == 0
    assert api.rosters == []

def test_process_all_engine_and_class_filter(tmp_path):
    schedule_path = os.path.join(WORKSPACE_DIR, "ORTEGA_SCHEDULE.xls")
    
    roster_file = tmp_path / "BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.csv"
    roster_file.write_text("Name,Student number\nOrtega, Dan,20261001\n", encoding="utf-8")

    out_dir = tmp_path / "output"
    out_dir.mkdir()

    progress_events = []
    def on_progress(event):
        progress_events.append(event)

    # Test running ONLY grade sheet generator
    results = process_schedule.process_all(
        schedule_path=schedule_path,
        xlsx_files=[str(roster_file)],
        output_dir_base=str(out_dir),
        class_filter=["202612040_CS1-4"],
        engine_filter=["grades"],
        progress_callback=on_progress
    )

    assert len(results["generated"]["grades"]) == 1
    assert len(results["generated"]["ceit"]) == 0
    assert len(results["generated"]["attendance"]) == 0
    assert len(progress_events) > 0
    assert progress_events[-1]["percent"] > 0

def test_handle_dropped_schedule_and_rosters(tmp_path):
    import base64
    schedule_path = os.path.join(WORKSPACE_DIR, "ORTEGA_SCHEDULE.xls")
    
    api = ScriptAPI()
    
    # 1. Test dropped schedule with direct path
    res = api.handle_dropped_schedule(
        filename="ORTEGA_SCHEDULE.xls",
        original_path=schedule_path
    )
    assert res["path"] == schedule_path
    assert res["metadata"] is not None
    assert "ORTEGA" in res["metadata"]["instructor"]

    # 2. Test dropped schedule with base64 payload
    with open(schedule_path, "rb") as f:
        b64_sched = base64.b64encode(f.read()).decode("utf-8")
    
    res2 = api.handle_dropped_schedule(
        filename="dropped_sched.xls",
        base64_data=b64_sched
    )
    assert res2["path"] != ""
    assert os.path.exists(res2["path"])
    assert res2["metadata"] is not None

    # 3. Test dropped rosters with base64 payload
    roster_content = b"Name,Student number\nTest Student,20261234\n"
    b64_roster = base64.b64encode(roster_content).decode("utf-8")

    roster_filename = "BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.csv"
    res3 = api.handle_dropped_rosters([
        {
            "filename": roster_filename,
            "data": b64_roster,
            "path": None
        }
    ])
    assert res3["count"] == 1
    assert len(res3["rosters"]) == 1
    assert os.path.exists(res3["rosters"][0])
    assert len(res3["validation"]) == 1
    assert res3["validation"][0]["status"] == "valid"

