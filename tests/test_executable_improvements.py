import os
import sys
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from executable.main import ScriptAPI, sanitize_filename

UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable", "ui.html")
MAIN_PY_PATH = os.path.join(WORKSPACE_DIR, "executable", "main.py")

def test_sanitize_filename():
    assert sanitize_filename("../../secret.txt") == "secret.txt"
    assert sanitize_filename("..\\..\\passwords.csv") == "passwords.csv"
    assert sanitize_filename("invalid:name*file?.xlsx") == "invalid_name_file_.xlsx"
    assert sanitize_filename("") == "unnamed_file"
    assert sanitize_filename("   ...   ") == "unnamed_file"
    assert sanitize_filename("valid_roster.xlsx") == "valid_roster.xlsx"

def test_script_api_clear_schedule():
    api = ScriptAPI()
    api.schedule_path = "some_path.xls"
    res = api.clear_schedule()
    assert res["status"] == "success"
    assert api.schedule_path == ""
    assert res["path"] == ""
    assert res["metadata"] is None

def test_script_api_browse_schedule_cancellation():
    class DummyWindow:
        def create_file_dialog(self, *args, **kwargs):
            return None

    api = ScriptAPI()
    api._window = DummyWindow()
    api.schedule_path = "existing_schedule.xls"

    res = api.browse_schedule()
    assert res["cancelled"] is True
    assert res["path"] == "existing_schedule.xls"

def test_script_api_browse_rosters_cancellation():
    class DummyWindow:
        def create_file_dialog(self, *args, **kwargs):
            return None

    api = ScriptAPI()
    api._window = DummyWindow()
    api.rosters = ["roster1.xlsx"]

    res = api.browse_rosters()
    assert res["cancelled"] is True
    assert res["count"] == 1
    assert res["rosters"] == ["roster1.xlsx"]

def test_script_api_open_nonexistent_paths():
    api = ScriptAPI()
    res_file = api.open_file("non_existent_folder_xyz/file.txt")
    assert res_file["status"] == "error"
    assert "File not found" in res_file["message"]

    res_folder = api.open_output_folder("non_existent_folder_xyz")
    assert res_folder["status"] == "error"
    assert "Directory does not exist" in res_folder["message"]

def test_ui_html_accessibility_and_roles():
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        ui = f.read()

    # Verify modal dialog roles
    assert 'id="modalParserSettingsBackdrop"' in ui
    assert 'role="dialog"' in ui
    assert 'aria-modal="true"' in ui
    assert 'aria-labelledby="settingsModalTitle"' in ui
    assert 'id="settingsModalTitle"' in ui
    assert 'aria-labelledby="mapModalFilename"' in ui

    # Verify drawer region roles
    assert 'id="logsDrawer"' in ui
    assert 'id="helpDrawer"' in ui
    assert 'role="region"' in ui
    assert 'aria-label="Execution and diagnostic logs"' in ui
    assert 'aria-label="Documentation and help drawer"' in ui

    # Verify icon button aria-labels
    assert 'aria-label="Reset master schedule"' in ui
    assert 'aria-label="Remove all imported rosters"' in ui
    assert 'aria-label="View Execution Diagnostics"' in ui
    assert 'aria-label="View User Guide & Rules"' in ui
    assert 'aria-label="Close settings modal"' in ui
    assert 'aria-label="Close roster mapping modal"' in ui
    assert 'aria-label="Copy recommended roster filename"' in ui
    assert 'aria-label="Initialize document generation workflow"' in ui

def test_ui_html_escape_key_dismisses_all_modals():
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        ui = f.read()

    assert 'modalParserSettingsBackdrop' in ui
    assert 'closeSettingsModal();' in ui
    assert 'modalRosterMappingBackdrop' in ui
    assert 'closeColumnMappingModal();' in ui

def test_ui_html_sync_and_error_handling():
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        ui = f.read()

    # Verify clear_schedule call in resetSchedule
    assert "clear_schedule" in ui

    # Verify cancellation check in loadSchedule and loadRosters
    assert "res.cancelled" in ui

    # Verify error toast handling on open operations
    assert 'showToast("Could Not Open File"' in ui
    assert 'showToast("Directory Error"' in ui
    assert 'showToast("Logs Directory"' in ui

def test_main_py_template_dropzone_and_window_closing():
    with open(MAIN_PY_PATH, "r", encoding="utf-8") as f:
        main_py = f.read()

    # Verify template dropzone registration
    assert "template_zone = window.dom.get_element('#templateDropzone')" in main_py
    assert "on_template_drop" in main_py
    assert "template_zone.events.drop +=" in main_py

    # Verify closing event registration
    assert "window.events.closing +=" in main_py

def test_apple_hig_confirm_modal_replaces_browser_confirm():
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        ui = f.read()

    # Zero window.confirm calls allowed in ui.html
    import re
    confirm_calls = re.findall(r'[^a-zA-Z0-9_]confirm\(', ui)
    assert len(confirm_calls) == 0, f"Found native browser confirm() calls: {confirm_calls}"

    # Verify Apple HIG modal structure
    assert 'id="modalAppleConfirmBackdrop"' in ui
    assert 'id="appleConfirmTitle"' in ui
    assert 'id="appleConfirmMessage"' in ui
    assert 'id="btnAppleConfirmProceed"' in ui
    assert 'id="btnAppleConfirmCancel"' in ui
    assert 'showAppleConfirm' in ui
    assert 'dismissAppleConfirm' in ui

