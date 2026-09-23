"""
API Inventory Consistency Test Suite.
Enforces that the Python backend (ScriptAPI), Playwright mock layer (rawMockApi),
and frontend JavaScript callers adhere to a canonical, synchronized API contract.
"""

import os
import re
import inspect
import pytest
from executable_test.main import ScriptAPI

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_DIR = os.path.join(WORKSPACE_DIR, "executable_test", "js")
PLAYWRIGHT_E2E_PATH = os.path.join(WORKSPACE_DIR, "tests", "test_playwright_e2e.py")

# Canonical source of truth for the pywebview bridge API surface
EXPECTED_API = {
    "activate_template_set",
    "browse_custom_template",
    "browse_output",
    "browse_rosters",
    "browse_schedule",
    "browse_template_set_files",
    "cancel_generation",
    "clear_rosters",
    "clear_schedule",
    "create_template_set",
    "delete_custom_template",
    "delete_template_set",
    "detect_classes",
    "duplicate_template_set",
    "export_parser_config",
    "export_template_set",
    "get_active_template_set",
    "get_ceit_prefix_directory",
    "get_custom_templates",
    "get_parser_config",
    "get_recent_logs",
    "get_template_sets",
    "handle_dropped_custom_template",
    "handle_dropped_rosters",
    "handle_dropped_schedule",
    "import_parser_config",
    "import_template_set",
    "inspect_custom_template",
    "inspect_roster",
    "inspect_schedule",
    "inspect_template_set_files",
    "open_file",
    "open_log_folder",
    "open_output_folder",
    "remove_roster",
    "reset_parser_config",
    "run_generation",
    "save_custom_template",
    "save_parser_config",
    "save_template_set",
    "set_template_set_fallback",
    "toggle_custom_template",
    "update_template_set",
    "validate_rosters",
}


def get_script_api_public_methods():
    """Extracts all public callable methods declared on or inherited by ScriptAPI."""
    methods = set()
    for name, member in inspect.getmembers(ScriptAPI, predicate=inspect.isfunction):
        if not name.startswith("_"):
            methods.add(name)
    return methods


def get_raw_mock_api_methods():
    """Parses rawMockApi object keys declared in tests/test_playwright_e2e.py."""
    with open(PLAYWRIGHT_E2E_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Find rawMockApi block
    match = re.search(r"const\s+rawMockApi\s*=\s*\{([\s\S]*?)\n\};", content)
    assert match, "rawMockApi declaration not found in test_playwright_e2e.py"
    body = match.group(1)

    # Match method keys (e.g. `browse_schedule: async () => ...` or `open_file: async ...`)
    methods = set(re.findall(r"^\s*([a-zA-Z0-9_]+)\s*:", body, re.MULTILINE))
    return methods


def discover_js_api_calls():
    """
    Statically scans all executable_test/js/*.js files to discover all pywebview API method calls.
    Supports patterns like:
      - window.pywebview.api.<method>(...)
      - pywebview.api.<method>(...)
      - window.pywebview['api']['<method>'](...)
    """
    discovered = set()
    patterns = [
        r"(?:window\.)?pywebview\.api\.([a-zA-Z0-9_]+)\s*\(",
        r"(?:window\.)?pywebview\s*\[\s*['\"]api['\"]\s*\]\s*\[\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\]\s*\(",
        r"(?:window\.)?pywebview\.api\s*\[\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\]\s*\(",
    ]

    for fname in os.listdir(JS_DIR):
        if fname.endswith(".js"):
            fpath = os.path.join(JS_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            for pat in patterns:
                matches = re.findall(pat, content)
                discovered.update(matches)

    return discovered


def test_script_api_matches_canonical_inventory():
    """Layer 1: ScriptAPI public methods must match EXPECTED_API exactly."""
    script_api_methods = get_script_api_public_methods()
    missing_from_scriptapi = EXPECTED_API - script_api_methods
    extra_in_scriptapi = script_api_methods - EXPECTED_API

    assert script_api_methods == EXPECTED_API, (
        f"ScriptAPI inventory mismatch.\n"
        f"Missing from ScriptAPI: {sorted(list(missing_from_scriptapi))}\n"
        f"Unexpected extra in ScriptAPI: {sorted(list(extra_in_scriptapi))}"
    )


def test_playwright_mock_api_matches_canonical_inventory():
    """Layer 2: Playwright rawMockApi must declare every method in EXPECTED_API."""
    mock_methods = get_raw_mock_api_methods()
    missing_from_mock = EXPECTED_API - mock_methods
    extra_in_mock = mock_methods - EXPECTED_API

    assert mock_methods == EXPECTED_API, (
        f"Playwright rawMockApi inventory mismatch.\n"
        f"Missing from Mock: {sorted(list(missing_from_mock))}\n"
        f"Unexpected extra in Mock: {sorted(list(extra_in_mock))}"
    )


def test_js_frontend_calls_are_subset_of_canonical_inventory():
    """Layer 3: Every pywebview API method invoked by frontend JS must exist in EXPECTED_API."""
    js_calls = discover_js_api_calls()
    undefined_calls = js_calls - EXPECTED_API

    assert undefined_calls == set(), (
        f"Frontend JavaScript calls undeclared bridge methods: {sorted(list(undefined_calls))}"
    )
    # Sanity check: confirm JS actually exercises core workflows
    assert "run_generation" in js_calls
    assert "browse_schedule" in js_calls
    assert "browse_rosters" in js_calls
    assert "detect_classes" in js_calls
    assert "cancel_generation" in js_calls
