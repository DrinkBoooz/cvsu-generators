"""
End-to-End Playwright UI Test Suite for CvSU Document Generator.
Verifies the complete desktop user interface workflow (ui.html + js controllers)
against a strict, controlled, and monitored window.pywebview.api mock boundary.
"""

import os
import re
import json
import pytest
from playwright.sync_api import sync_playwright, expect

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

# ── Structured Data Payloads ───────────────────────────────────────────

VALID_SCHEDULE_RESPONSE = {
    "cancelled": False,
    "path": "C:/CvSU/Schedules/Instructor_Schedule.xlsx",
    "metadata": {
        "instructor": "Dan Joseph Ortega",
        "college": "College of Engineering and Information Technology",
        "semester": "1st Semester AY 2025-2026",
        "total_slots": 5,
    },
    "validation": [],
}

INVALID_SCHEDULE_RESPONSE = {
    "cancelled": False,
    "path": "",
    "metadata": None,
    "validation": [],
}

VALID_ROSTERS_RESPONSE = {
    "cancelled": False,
    "count": 2,
    "rosters": [
        "C:/CvSU/Rosters/COSC 101 List of Students for 1001-Computer Programming 1.xlsx",
        "C:/CvSU/Rosters/ITEC 50 List of Students for 1002-Web Development.csv",
    ],
    "validation": [
        {
            "filename": "COSC 101 List of Students for 1001-Computer Programming 1.xlsx",
            "file": "COSC 101 List of Students for 1001-Computer Programming 1.xlsx",
            "status": "ok",
            "student_count": 28,
            "matched_class": "COSC 101 - BSCS 1-1",
            "warnings": [],
        },
        {
            "filename": "ITEC 50 List of Students for 1002-Web Development.csv",
            "file": "ITEC 50 List of Students for 1002-Web Development.csv",
            "status": "ok",
            "student_count": 32,
            "matched_class": "ITEC 50 - BSIT 2-1",
            "warnings": [],
        },
    ],
}

VALID_CLASSES_RESPONSE = [
    {
        "id": "cls_1",
        "course_sec": "BSCS 1-1",
        "schedule_code": "1001",
        "subject_name": "Computer Programming 1",
        "schedule_desc": "TF 07:00-09:00",
        "detected_type": "lecture_lab",
        "ceit_metadata": {
            "prefix": "COSC",
            "department_code": "DIT",
            "department_name": "Department of Information Technology",
        },
    },
    {
        "id": "cls_2",
        "course_sec": "BSIT 2-1",
        "schedule_code": "1002",
        "subject_name": "Web Development",
        "schedule_desc": "WS 10:00-12:00",
        "detected_type": "lecture_only",
        "ceit_metadata": {
            "prefix": "ITEC",
            "department_code": "DIT",
            "department_name": "Department of Information Technology",
        },
    },
]

CORRUPT_TEMPLATE_RESPONSE = {
    "status": "error",
    "message": "Corrupted XML package: missing document body",
}

SUCCESS_GENERATION_PAYLOAD = {
    "status": "success",
    "message": "Generation complete! 3 files generated successfully.",
    "stats": {"generated": 3, "errors": 0, "skipped": 0},
    "details": {
        "generated": {
            "ceit": ["BSCS 1-1_1001_CEIT_FORM.docx"],
            "attendance": ["BSCS 1-1_1001_ATTENDANCE.docx"],
            "grades": ["BSCS 1-1_1001_GRADING_SHEET.xlsx"],
        },
        "skipped": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
        "errors": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
    },
    "output_dir": "C:/CvSU/Output",
}

CANCELLED_GENERATION_PAYLOAD = {
    "status": "cancelled",
    "message": "Generation stopped by user. 0 file(s) were generated.",
    "stats": {"generated": 0, "errors": 0, "skipped": 0},
    "details": {
        "generated": {"ceit": [], "attendance": [], "grades": []},
        "skipped": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
        "errors": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
    },
    "output_dir": "C:/CvSU/Output",
}

ERROR_GENERATION_PAYLOAD = {
    "status": "error",
    "message": "Fatal Generation Fault: Permission denied",
    "details": None,
}

# ── Pre-Navigation Mock Initialization Script ─────────────────────────

MOCK_API_INIT_SCRIPT = """
window.__apiCalls = [];
window.__mockResponses = {
    browse_schedule: """ + json.dumps(VALID_SCHEDULE_RESPONSE) + """,
    inspect_schedule: null,
    browse_rosters: """ + json.dumps(VALID_ROSTERS_RESPONSE) + """,
    detect_classes: """ + json.dumps(VALID_CLASSES_RESPONSE) + """,
    browse_output: "C:/CvSU/Output",
    run_generation: null,
    cancel_generation: { status: "success", message: "Cancellation requested." },
    browse_custom_template: { status: "cancelled" }
};

const rawMockApi = {
    browse_schedule: async () => window.__mockResponses.browse_schedule,
    inspect_schedule: async (p) => window.__mockResponses.inspect_schedule || null,
    clear_schedule: async () => ({ status: "success", path: "", metadata: null, validation: [] }),
    browse_rosters: async (cfg) => window.__mockResponses.browse_rosters,
    handle_dropped_rosters: async (f, cfg) => window.__mockResponses.handle_dropped_rosters || window.__mockResponses.browse_rosters,
    remove_roster: async (p, cfg) => window.__mockResponses.remove_roster || { count: 0, rosters: [], validation: [] },
    clear_rosters: async () => ({ count: 0, rosters: [], validation: [] }),
    inspect_roster: async (p, o) => window.__mockResponses.inspect_roster || { status: "ok", format: "excel", raw_rows: [], available_columns: [] },
    detect_classes: async (cfg) => window.__mockResponses.detect_classes,
    browse_output: async () => window.__mockResponses.browse_output,
    open_output_folder: async (f) => ({ status: "success" }),
    open_file: async (f) => ({ status: "success" }),
    get_recent_logs: async (l) => "No log entries found.",
    open_log_folder: async () => ({ status: "success" }),
    get_custom_templates: async () => window.__mockResponses.get_custom_templates || [],
    browse_custom_template: async () => window.__mockResponses.browse_custom_template,
    inspect_custom_template: async (p) => window.__mockResponses.inspect_custom_template || { status: "error", message: "Not implemented" },
    save_custom_template: async (p, t, s, r) => window.__mockResponses.save_custom_template || { status: "success" },
    toggle_custom_template: async (id, e) => ({ status: "success" }),
    delete_custom_template: async (id) => ({ status: "success" }),
    run_generation: async (to, do_, sc, ee, rc) => {
        if (window.__mockResponses.run_generation_reject) {
            throw new Error(window.__mockResponses.run_generation_reject);
        }
        return window.__mockResponses.run_generation;
    },
    cancel_generation: async () => window.__mockResponses.cancel_generation,
    get_parser_config: async () => ({ prefixes: {}, lab_courses: [] }),
    save_prefix_mapping: async (p, c, n) => ({ status: "success" }),
    delete_prefix_mapping: async (p) => ({ status: "success" }),
    save_lab_course: async (c) => ({ status: "success" }),
    delete_lab_course: async (c) => ({ status: "success" }),
    reset_parser_config: async () => ({ status: "success" }),
    export_parser_config: async () => ({ status: "success" }),
    import_parser_config: async () => ({ status: "success" })
};

const allowedProbes = new Set(["then", "toJSON"]);

window.pywebview = {
    api: new Proxy(rawMockApi, {
        get(target, property) {
            if (typeof property === "symbol" || allowedProbes.has(property)) {
                return target[property];
            }
            if (!(property in target)) {
                throw new Error(`Unexpected API call: ${String(property)}`);
            }
            return async (...args) => {
                window.__apiCalls.push({
                    method: property,
                    args: JSON.parse(JSON.stringify(args))
                });
                return target[property](...args);
            };
        }
    })
};
"""


# ── Test Fixtures & Workflow Helpers ───────────────────────────────────

@pytest.fixture
def app_page():
    """Initializes Playwright browser page with the pre-navigation strict mock API."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_init_script(MOCK_API_INIT_SCRIPT)
        page.goto(FILE_URL)
        yield page
        browser.close()


def expect_step_ready(page, step_num: int, is_ready: bool = True):
    """Asserts that a given stepper chip reflects the expected readiness state."""
    chip = page.locator(f"#chipStep{step_num}")
    if is_ready:
        expect(chip).to_have_class(re.compile(r"\bready\b"))
    else:
        expect(chip).not_to_have_class(re.compile(r"\bready\b"))


def expect_toast(page, title_text: str, toast_type: str = None):
    """Asserts that a non-blocking toast notification is displayed with matching title."""
    if toast_type:
        toast = page.locator(f".toast.toast-{toast_type}", has_text=title_text)
    else:
        toast = page.locator(".toast", has_text=title_text)
    expect(toast).to_be_visible()


def complete_steps_1_to_5(page):
    """
    Executes and milestone-gates Steps 1 through 5 through user actions.
    Asserts intermediate milestone states to isolate any workflow breakdowns.
    """
    # Step 1: Browse Schedule
    page.click("#scheduleDropzone")
    expect_step_ready(page, 1, True)
    expect(page.locator("#scheduleFilename")).to_have_text("Instructor_Schedule.xlsx")
    expect(page.locator("#instructorBanner")).to_be_visible()

    # Step 2: Browse Rosters
    page.click("#rostersDropzone")
    expect_step_ready(page, 2, True)
    expect(page.locator("#rosterRowsContainer .roster-row")).to_have_count(2)

    # Step 3: Class Detection & Package Selection
    expect_step_ready(page, 3, True)
    expect(page.locator("#classesSection")).to_be_visible()
    expect(page.locator(".class-card")).to_have_count(2)

    # Step 4: Semester Dates (Optional)
    page.fill("#startDate", "2026-01-15")
    page.fill("#endDate", "2026-05-30")
    expect(page.locator("#startDate")).to_have_value("2026-01-15")
    expect(page.locator("#endDate")).to_have_value("2026-05-30")

    # Step 5: Target Output Path
    page.click("button:has-text('Browse Path')")
    expect_step_ready(page, 5, True)
    expect(page.locator("#outputDisplay")).to_have_value("C:/CvSU/Output")

    # Step 6 Readiness Milestone
    expect_step_ready(page, 6, True)
    expect(page.locator("#processBtn")).to_be_enabled()


def get_api_calls(page, method: str = None):
    """Retrieves recorded API calls from window.__apiCalls, optionally filtering by method."""
    calls = page.evaluate("() => window.__apiCalls || []")
    if method:
        return [c for c in calls if c.get("method") == method]
    return calls


# ── Test Scenarios ─────────────────────────────────────────────────────

def test_playwright_e2e_happy_path_workflow(app_page):
    """
    Scenario 1: Complete happy path workflow.
    Executes Steps 1 to 6 through user actions, verifies strict API argument payloads,
    asserts double-click debounce and active re-entry guards, verifies real-time telemetry,
    and checks clean reset for subsequent generation readiness.
    """
    page = app_page

    # 1. Startup & Initial UI State
    expect(page.locator(".badge-version").first).to_have_text("Release v1.0.1")
    expect_step_ready(page, 1, False)
    expect_step_ready(page, 2, False)
    expect_step_ready(page, 5, False)
    expect_step_ready(page, 6, False)
    expect(page.locator("#processBtnLabel")).to_have_text("Initialize Workflow")

    # 2. Step 1: Select Schedule
    page.click("#scheduleDropzone")
    expect_step_ready(page, 1, True)
    expect(page.locator("#scheduleFilename")).to_have_text("Instructor_Schedule.xlsx")
    expect(page.locator("#scheduleFormatBadge")).to_have_text(".XLSX")
    expect(page.locator("#instructorName")).to_have_text("Dan Joseph Ortega")
    expect(page.locator("#instructorInitials")).to_have_text("DJ")
    expect_toast(page, "Schedule Loaded", "success")

    # Verify API call
    sched_calls = get_api_calls(page, "browse_schedule")
    assert len(sched_calls) == 1
    assert sched_calls[0]["args"] == []

    # 3. Step 2: Select Rosters
    page.click("#rostersDropzone")
    expect_step_ready(page, 2, True)
    expect(page.locator("#rosterRowsContainer .roster-row")).to_have_count(2)
    expect(page.locator("#rosterCountBadge")).to_have_text("2")
    expect_toast(page, "Rosters Loaded", "success")

    roster_calls = get_api_calls(page, "browse_rosters")
    assert len(roster_calls) == 1

    # 4. Step 3: Class Detection & Packages
    expect_step_ready(page, 3, True)
    expect(page.locator("#classesSection")).to_be_visible()
    expect(page.locator("#classesCountDisplay")).to_have_text("2")
    expect(page.locator(".class-card")).to_have_count(2)
    expect(page.locator(".badge-ceit-pill").first).to_contain_text("COSC")

    detect_calls = get_api_calls(page, "detect_classes")
    assert len(detect_calls) >= 1

    # 5. Step 4 & 5: Dates & Output Folder
    page.fill("#startDate", "2026-01-15")
    page.fill("#endDate", "2026-05-30")
    page.click("button:has-text('Browse Path')")
    expect_step_ready(page, 5, True)
    expect(page.locator("#outputDisplay")).to_have_value("C:/CvSU/Output")

    output_calls = get_api_calls(page, "browse_output")
    assert len(output_calls) == 1

    # 6. Readiness Verification
    expect_step_ready(page, 6, True)
    expect(page.locator("#connector1to2")).to_have_class(re.compile(r"\bready\b"))
    expect(page.locator("#connector2to3")).to_have_class(re.compile(r"\bready\b"))
    expect(page.locator("#processBtn")).to_be_enabled()

    # 7. Step 6: Generate Execution & Double-Click Debounce
    # Rapid double click via DOM dispatch
    page.locator("#processBtn").dispatch_event("click")
    page.locator("#processBtn").dispatch_event("click")

    gen_calls = get_api_calls(page, "run_generation")
    assert len(gen_calls) == 1, "Rapid double-click must debounce to exactly 1 run_generation call"

    # Assert exact structured API arguments
    args = gen_calls[0]["args"]
    assert len(args) == 5
    type_overrides, date_overrides, selected_classes, enabled_engines, roster_configs = args
    assert type_overrides == {"cls_1": "lecture_lab", "cls_2": "lecture_only"}
    assert date_overrides == {
        "startYear": 2026, "startMonth": 1, "startDay": 15,
        "endYear": 2026, "endMonth": 5, "endDay": 30
    }
    assert set(selected_classes) == {"cls_1", "cls_2"}
    assert set(enabled_engines) == {"attendance", "ceit", "grades"}
    assert isinstance(roster_configs, dict), "Argument 5 (roster_configs) must be a dictionary"
    assert roster_configs == {}, "Argument 5 (roster_configs) must be empty dict when no custom mappings configured"

    # Verify generation active UI state
    expect(page.locator("#processBtn")).to_be_disabled()
    expect(page.locator("#processBtnLabel")).to_have_text("Compiling Documents...")
    expect(page.locator("#progressContainer")).to_be_visible()
    expect(page.locator("#btnCancelGeneration")).to_be_visible()

    # Active Re-Entry Guard Assertion: triggering generate again while running must not call API
    page.evaluate("startGeneration()")
    assert len(get_api_calls(page, "run_generation")) == 1, "Active generation must block re-entry"

    # 8. Real-Time Telemetry Updates
    telemetry_payload = {
        "percent": 50,
        "current_class": "BSCS 1-1",
        "current_task": "Generating CEIT Forms",
        "step": 3,
        "total_steps": 6,
    }
    page.evaluate(f"window.onGenerationProgress({json.dumps(telemetry_payload)})")
    expect(page.locator("#progressFill")).to_have_attribute("style", re.compile(r"width:\s*50%"))
    expect(page.locator("#progressPercent")).to_have_text("50%")
    expect(page.locator("#progressTaskLabel")).to_have_text("BSCS 1-1: Generating CEIT Forms (3/6)")
    expect(page.locator("#progressContainer")).to_have_attribute("aria-valuenow", "50")

    # 9. Completion & Subsequent Generation Readiness
    page.evaluate(f"window.onGenerationComplete({json.dumps(SUCCESS_GENERATION_PAYLOAD)})")
    expect(page.locator("#progressFill")).to_have_attribute("style", re.compile(r"width:\s*100%"))
    expect(page.locator("#resultsCard")).to_be_visible()
    expect(page.locator("#resultsCard")).to_have_class(re.compile(r"\bresults-success\b"))
    expect(page.locator("#resultsTitleText")).to_have_text("Document Generation Succeeded!")
    expect(page.locator("#resultsMetricsPills")).to_contain_text("3 Total Files")
    expect_toast(page, "Documents Ready", "success")

    # Ready for subsequent generation
    expect(page.locator("#btnCancelGeneration")).to_be_hidden()
    expect(page.locator("#processBtn")).to_be_enabled()
    expect(page.locator("#processBtnLabel")).to_have_text("Initialize Workflow")


def test_playwright_failure_path_invalid_schedule(app_page):
    """
    Scenario 2: Failure paths for invalid or missing schedule.
    Asserts warning toasts and strict state integrity (no advancement, no run_generation).
    """
    page = app_page

    # Case A: Attempting to generate with empty schedule
    page.evaluate("startGeneration()")
    expect_toast(page, "Schedule Required", "warning")

    # State & API Integrity
    expect_step_ready(page, 1, False)
    expect_step_ready(page, 6, False)
    assert len(get_api_calls(page, "run_generation")) == 0, "run_generation must not be called without schedule"

    # Case B: Ingesting corrupt schedule where backend returns null metadata
    page.evaluate(f"window.__mockResponses.browse_schedule = {json.dumps(INVALID_SCHEDULE_RESPONSE)}")
    page.click("#scheduleDropzone")

    # State Integrity
    expect_step_ready(page, 1, False)
    expect(page.locator("#instructorBanner")).to_be_hidden()
    expect_step_ready(page, 6, False)
    assert len(get_api_calls(page, "run_generation")) == 0


def test_playwright_failure_path_missing_rosters(app_page):
    """
    Scenario 3: Failure path when schedule is loaded but rosters array is empty.
    Asserts generation blocked, warning toast, and state integrity.
    """
    page = app_page

    # Load schedule only
    page.click("#scheduleDropzone")
    expect_step_ready(page, 1, True)
    expect_step_ready(page, 2, False)

    # Attempt to generate
    page.evaluate("startGeneration()")
    expect_toast(page, "Rosters Required", "warning")

    # State & API Integrity
    expect_step_ready(page, 1, True)
    expect_step_ready(page, 2, False)
    expect_step_ready(page, 6, False)
    assert len(get_api_calls(page, "run_generation")) == 0


def test_playwright_failure_path_corrupt_template(app_page):
    """
    Scenario 4: Failure path when inspecting a corrupt or unsupported Word template.
    Asserts analysis error toast and template preview isolation.
    """
    page = app_page

    # Open Settings Modal and switch to Custom Templates tab
    page.click("#btnOpenSettings")
    expect(page.locator("#modalParserSettingsBackdrop")).to_be_visible()
    page.click("#cfgTabCustomTemplates")
    expect(page.locator("#cfgPaneCustomTemplates")).to_be_visible()

    # Configure mock browse_custom_template to return corrupt error
    page.evaluate(f"window.__mockResponses.browse_custom_template = {json.dumps(CORRUPT_TEMPLATE_RESPONSE)}")

    # Click Browse Template in dropzone
    page.click("#templateDropzone")
    expect_toast(page, "Analysis Error", "error")

    # State Integrity: preview card remains hidden and template is not saved
    expect(page.locator("#customTemplateResultCard")).to_be_hidden()
    assert len(get_api_calls(page, "save_custom_template")) == 0


def test_playwright_failure_path_no_packages_selected(app_page):
    """
    Scenario 5: Failure path when user deselects all packages (Attendance, CEIT, Grades).
    Asserts Step 3 marked incomplete, generate blocked, and toast warning.
    """
    page = app_page
    complete_steps_1_to_5(page)

    # Uncheck all three packages
    page.uncheck("#checkAttendance")
    page.uncheck("#checkCeit")
    page.uncheck("#checkGrades")

    # State Integrity: Step 3 and Step 6 become incomplete
    expect_step_ready(page, 3, False)
    expect_step_ready(page, 6, False)

    # Attempt to generate
    page.evaluate("startGeneration()")
    expect_toast(page, "No Packages Selected", "warning")
    assert len(get_api_calls(page, "run_generation")) == 0


def test_playwright_edge_case_duplicate_files(app_page):
    """
    Scenario 6: 3-layer duplicate file handling and schedule reset.
    Asserts API response, state.rosters, and rendered DOM table rows.
    """
    page = app_page

    # 1. Ingest duplicate roster paths (same absolute path)
    dup_response = {
        "cancelled": False,
        "count": 1,
        "rosters": ["C:/CvSU/Rosters/COSC 101.xlsx"],
        "validation": [
            {
                "filename": "COSC 101.xlsx",
                "file": "COSC 101.xlsx",
                "status": "ok",
                "student_count": 30,
                "matched_class": "COSC 101",
                "warnings": [],
            }
        ],
    }
    page.evaluate(f"window.__mockResponses.browse_rosters = {json.dumps(dup_response)}")
    page.click("#rostersDropzone")

    # 3-Layer Check:
    # Layer 1: API returned 1 de-duplicated item
    # Layer 2: state.rosters has exactly 1 item
    roster_count = page.evaluate("() => state.rosters.length")
    assert roster_count == 1
    # Layer 3: Rendered table has exactly 1 row
    expect(page.locator("#rosterRowsContainer .roster-row")).to_have_count(1)

    # 2. Distinct paths with same basename are preserved as 2 distinct items
    distinct_response = {
        "cancelled": False,
        "count": 2,
        "rosters": [
            "C:/DeptA/Rosters/COSC 101.xlsx",
            "C:/DeptB/Rosters/COSC 101.xlsx",
        ],
        "validation": [
            {"filename": "COSC 101.xlsx", "file": "COSC 101.xlsx", "status": "ok", "student_count": 25, "matched_class": "COSC 101", "warnings": []},
            {"filename": "COSC 101.xlsx", "file": "COSC 101.xlsx", "status": "ok", "student_count": 28, "matched_class": "COSC 101", "warnings": []},
        ],
    }
    page.evaluate(f"window.__mockResponses.browse_rosters = {json.dumps(distinct_response)}")
    page.click("#rostersDropzone")

    assert page.evaluate("() => state.rosters.length") == 2
    expect(page.locator("#rosterRowsContainer .roster-row")).to_have_count(2)

    # 3. Schedule Reset Button
    page.click("#scheduleDropzone")  # load schedule first
    expect_step_ready(page, 1, True)
    expect(page.locator("#btnResetSchedule")).to_be_visible()

    page.click("#btnResetSchedule")
    expect_step_ready(page, 1, False)
    expect(page.locator("#instructorBanner")).to_be_hidden()
    expect(page.locator("#scheduleFilename")).to_be_hidden()
    expect_step_ready(page, 6, False)


def test_playwright_failure_path_generation_cancellation(app_page):
    """
    Scenario 7: User-requested generation cancellation.
    Asserts cancel button transition, cancel_generation API call, and results-error presentation.
    """
    page = app_page
    complete_steps_1_to_5(page)

    # Start generation
    page.click("#processBtn")
    expect(page.locator("#btnCancelGeneration")).to_be_visible()

    # Click Cancel Generation
    page.click("#btnCancelGeneration")
    expect(page.locator("#btnCancelGeneration")).to_be_disabled()
    expect(page.locator("#btnCancelGeneration")).to_contain_text("Cancelling...")
    expect_toast(page, "Cancelling Generation", "warning")

    cancel_calls = get_api_calls(page, "cancel_generation")
    assert len(cancel_calls) == 1
    assert cancel_calls[0]["args"] == []

    # Python thread signals cancellation
    page.evaluate(f"window.onGenerationComplete({json.dumps(CANCELLED_GENERATION_PAYLOAD)})")
    expect(page.locator("#resultsCard")).to_be_visible()
    expect(page.locator("#resultsCard")).to_have_class(re.compile(r"\bresults-error\b"))
    expect(page.locator("#resultsTitleText")).to_have_text("Generation Cancelled")
    expect(page.locator("#resultsMessage")).to_contain_text("Generation stopped by user")


def test_playwright_failure_path_generation_failure(app_page):
    """
    Scenario 8: Backend generation fault & bridge rejection recovery.
    Asserts:
      A. Promise rejection/throw from window.pywebview.api.run_generation() is caught,
         error results card and toast are shown, and _isGenerationRunning is safely reset.
      B. Subsequent generation retry succeeds and transmits custom roster_configs schema.
      C. Background thread error payload via window.onGenerationComplete presents errors.
    """
    page = app_page
    complete_steps_1_to_5(page)

    # Sub-case A: Bridge rejection (Promise throws/rejects an error)
    page.evaluate("window.__mockResponses.run_generation_reject = 'PyWebView bridge connection severed'")
    page.click("#processBtn")

    # Assert error presentation from caught rejected promise
    expect(page.locator("#resultsCard")).to_be_visible()
    expect(page.locator("#resultsCard")).to_have_class(re.compile(r"\bresults-error\b"))
    expect(page.locator("#resultsTitleText")).to_have_text("Generation Encountered Issues")
    expect(page.locator("#resultsMessage")).to_contain_text("Generation failed: PyWebView bridge connection severed")
    expect_toast(page, "Generation Encountered Issues", "error")

    # Verify recovery: concurrency lock is cleared and button is re-enabled
    assert page.evaluate("() => window._isGenerationRunning") is False
    expect(page.locator("#processBtn")).to_be_enabled()
    expect(page.locator("#processBtnLabel")).to_have_text("Initialize Workflow")

    # Sub-case B: Retry subsequent generation with populated rosterConfigs (Argument 5 schema verification)
    expected_custom_mappings = {
        "COSC 101 List of Students for 1001-Computer Programming 1.xlsx": {
            "linked_schedule_code": "1001",
            "schedule_code": "1001",
            "course_sec": "BSCS 1-1",
            "subject_name": "Computer Programming 1"
        }
    }
    page.evaluate(f"""() => {{
        window.__mockResponses.run_generation_reject = null;
        window.__mockResponses.run_generation = null;
        state.rosterConfigs = {json.dumps(expected_custom_mappings)};
    }}""")
    page.click("#processBtn")

    # Verify that run_generation was invoked again (not blocked) with exact populated rosterConfigs
    gen_calls = get_api_calls(page, "run_generation")
    assert len(gen_calls) == 2, "Retry must dispatch second run_generation call"
    second_call_args = gen_calls[1]["args"]
    assert len(second_call_args) == 5
    _, _, _, _, retried_roster_configs = second_call_args
    assert retried_roster_configs == expected_custom_mappings, "Argument 5 must match configured rosterConfigs schema"

    # Sub-case C: Background thread returns explicit error payload via onGenerationComplete
    page.evaluate(f"window.onGenerationComplete({json.dumps(ERROR_GENERATION_PAYLOAD)})")
    expect(page.locator("#resultsCard")).to_be_visible()
    expect(page.locator("#resultsCard")).to_have_class(re.compile(r"\bresults-error\b"))
    expect(page.locator("#resultsTitleText")).to_have_text("Generation Encountered Issues")
    expect(page.locator("#resultsMessage")).to_have_text("Fatal Generation Fault: Permission denied")

    # Final recovery check: concurrency lock cleared
    assert page.evaluate("() => window._isGenerationRunning") is False
    expect(page.locator("#processBtn")).to_be_enabled()


def test_playwright_lifecycle_window_close_cleanup():
    """
    Scenario 9: Browser teardown lifecycle safety.
    Verifies that page destruction during active generation does not produce
    uncaught application exceptions or timer errors before teardown.
    """
    uncaught_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda err: uncaught_errors.append(str(err)))

        page.add_init_script(MOCK_API_INIT_SCRIPT)
        page.goto(FILE_URL)

        # Start workflow into active generation
        complete_steps_1_to_5(page)
        page.click("#processBtn")
        expect(page.locator("#progressContainer")).to_be_visible()

        # Simulate ongoing stopwatch timer and progress ticks
        page.evaluate("""
            window.onGenerationProgress({
                percent: 30,
                current_class: 'BSCS 1-1',
                current_task: 'Writing CEIT Forms',
                step: 2,
                total_steps: 6
            });
        """)

        # Capture and verify no application errors occurred before teardown
        pre_teardown_errors = list(uncaught_errors)
        assert pre_teardown_errors == [], f"Application errors occurred before teardown: {pre_teardown_errors}"

        # Close/destroy page during active workflow
        page.close()
        browser.close()

    # Distinguish expected navigation/context-destruction messages from genuine application exceptions
    def is_expected_teardown_msg(msg: str) -> bool:
        expected_patterns = [
            "Target page, context or browser has been closed",
            "Execution context was destroyed",
            "Session closed",
        ]
        return any(pat in msg for pat in expected_patterns)

    app_errors = [e for e in uncaught_errors if not is_expected_teardown_msg(e)]
    assert app_errors == [], f"Unexpected application errors during teardown: {app_errors}"
