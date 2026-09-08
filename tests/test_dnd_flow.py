import os
import sys
import json
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

import process_schedule
from executable.main import ScriptAPI

def test_dnd_schedule_detection():
    api = ScriptAPI()
    schedule_path = os.path.join(WORKSPACE_DIR, "ORTEGA_SCHEDULE.xls")
    assert os.path.exists(schedule_path)

    # Simulate dropped schedule path
    res = api.handle_dropped_schedule("ORTEGA_SCHEDULE.xls", original_path=schedule_path)
    assert res["path"] == schedule_path
    assert res["metadata"] is not None
    assert "ORTEGA" in res["metadata"]["instructor"]

def test_dnd_rosters_detection(tmp_path):
    api = ScriptAPI()
    roster_file = tmp_path / "BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.csv"
    roster_file.write_text("Name,Student number\nTest,2026001\n", encoding="utf-8")

    res = api.handle_dropped_rosters([
        {
            "filename": roster_file.name,
            "path": str(roster_file),
            "data": None
        }
    ])
    assert res["count"] == 1
    assert str(roster_file) in res["rosters"]
