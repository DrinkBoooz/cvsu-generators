import os
import re
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable", "ui.html")
README_PATH = os.path.join(WORKSPACE_DIR, "executable", "README.md")

def test_ui_html_matches_readme_instructions():
    assert os.path.exists(UI_HTML_PATH), "ui.html must exist"
    assert os.path.exists(README_PATH), "README.md must exist"

    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        ui_content = f.read()

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_content = f.read()

    # Verify all 6 step titles are represented in ui.html
    expected_steps = [
        "Select Instructor Schedule",
        "Select Student Rosters",
        "Confirm Detected Classes & Subject Types",
        "(Optional) Set Semester Date Boundaries",
        "Choose Target Output Folder",
        "Initialize Workflow"
    ]
    for step in expected_steps:
        normalized_step = step.replace("&", "&amp;")
        assert (step.lower() in ui_content.lower() or normalized_step.lower() in ui_content.lower()), (
            f"Step '{step}' must be explicitly present in ui.html"
        )

    # Verify exact button action names from README.md
    assert "Browse File" in ui_content, "Browse File button must be present in Step 1"
    assert "Browse Data" in ui_content, "Browse Data button must be present in Step 2"
    assert "Browse Path" in ui_content, "Browse Path button must be present in Step 5"
    assert "Initialize Workflow" in ui_content, "Initialize Workflow button must be present in Step 6"

    # Verify strict column requirement caution from README.md
    assert "Strict Column Requirement" in ui_content
    assert "Name" in ui_content and "Student number" in ui_content
    assert "Remove all extra columns before importing" in ui_content

    # Verify official roster naming format from README.md
    assert "{Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx" in ui_content

    # Verify help drawer contains README sections
    assert "System Requirements" in ui_content
    assert "Windows protected your PC" in ui_content
    assert "Frequently Asked Questions" in ui_content or "FAQ" in ui_content
    assert "danjoseph.ortega@cvsu.edu.ph" in ui_content
    assert "[CvSU Gen (Beta) - <Issue>]".replace("<", "&lt;").replace(">", "&gt;") in ui_content

def test_ui_html_element_ids_complete():
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        ui_content = f.read()

    # Extract all IDs defined in HTML
    html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', ui_content))

    # Extract all getElementById calls in JS
    js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', ui_content))

    # All getElementById targets must exist in HTML
    missing = js_ids - html_ids
    assert not missing, f"Missing element IDs in ui.html: {missing}"
