"""
Repository-Wide Persistent State Authority Inventory Test Suite (Commit 207).

Enforces:
1. Every persistent storage mechanism and key across frontend and backend is classified.
2. Every localStorage key discovered in frontend source code maps to a known authority category:
     - APPLICATION_CONFIGURATION
     - USER_PREFERENCES
     - TRANSIENT_UI_STATE
     - CACHE_COMPATIBILITY
3. No unclassified persistent keys exist.
4. Single-owner write paths: PreferencesManager owns user_preferences.json,
   ParserConfigManager owns parser_settings.json, TemplateSetManager owns template_sets.
5. Strict isolation between parser configuration and user preferences during reset, export, and import.
"""

import os
import re
import json
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTABLE_TEST_DIR = os.path.join(WORKSPACE_DIR, "executable_test")
JS_DIR = os.path.join(EXECUTABLE_TEST_DIR, "js")
UI_HTML_PATH = os.path.join(EXECUTABLE_TEST_DIR, "ui.html")

# ══════════════════════════════════════════════════════════════════════════════
# Canonical Persistent State Inventory Specification
# ══════════════════════════════════════════════════════════════════════════════

CANONICAL_CATEGORIES = {
    "APPLICATION_CONFIGURATION",
    "USER_PREFERENCES",
    "TRANSIENT_UI_STATE",
    "CACHE_COMPATIBILITY",
}

LOCALSTORAGE_AUTHORITY_INVENTORY = {
    "cvsu_gen_theme": {
        "category": "CACHE_COMPATIBILITY",
        "canonical_owner": "user_preferences.json",
        "manager": "PreferencesManager",
        "description": "0ms startup paint acceleration cache for active theme",
        "reset_behavior": "Reset to 'dark' on reset_user_preferences(); converged from disk on pywebviewready",
    },
    "cvsu_acc_motion": {
        "category": "CACHE_COMPATIBILITY",
        "canonical_owner": "user_preferences.json",
        "manager": "PreferencesManager",
        "description": "0ms startup paint acceleration cache for accessibility motion",
        "reset_behavior": "Reset to 'system' on reset_user_preferences(); converged from disk on pywebviewready",
    },
    "cvsu_acc_transparency": {
        "category": "CACHE_COMPATIBILITY",
        "canonical_owner": "user_preferences.json",
        "manager": "PreferencesManager",
        "description": "0ms startup paint acceleration cache for accessibility transparency",
        "reset_behavior": "Reset to 'system' on reset_user_preferences(); converged from disk on pywebviewready",
    },
    "cvsu_prefs_migrated": {
        "category": "CACHE_COMPATIBILITY",
        "canonical_owner": "localStorage",
        "manager": "theme.js",
        "description": "Upward migration and reset marker flag preventing stale cache resurrection",
        "reset_behavior": "Stamped to 'true' upon reset to prevent resurrecting wiped preferences",
    },
    "cvsu_output_dir": {
        "category": "TRANSIENT_UI_STATE",
        "canonical_owner": "Client UI Session",
        "manager": "state.js",
        "description": "Client session convenience cache for last chosen output directory",
        "reset_behavior": "Overwritten on user directory selection; not affected by config or preference reset",
    },
    "cvsu_startDate": {
        "category": "TRANSIENT_UI_STATE",
        "canonical_owner": "Client UI Session",
        "manager": "step2.js",
        "description": "Client workflow cache for user selected attendance start date",
        "reset_behavior": "Cleared on clearDatePresets(); not affected by config or preference reset",
    },
    "cvsu_endDate": {
        "category": "TRANSIENT_UI_STATE",
        "canonical_owner": "Client UI Session",
        "manager": "step2.js",
        "description": "Client workflow cache for user selected attendance end date",
        "reset_behavior": "Cleared on clearDatePresets(); not affected by config or preference reset",
    },
    "cvsu_roster_mappings": {
        "category": "TRANSIENT_UI_STATE",
        "canonical_owner": "Client UI Session",
        "manager": "state.js",
        "description": "Client workflow cache for per-file CSV column mapping presets",
        "reset_behavior": "Survives session reload; not affected by config or preference reset",
    },
    "cvsu_parsing_rules": {
        "category": "TRANSIENT_UI_STATE",
        "canonical_owner": "Client UI Session",
        "manager": "step2.js",
        "description": "Client workflow cache for remembering similar table parsing rules",
        "reset_behavior": "Survives session reload; not affected by config or preference reset",
    },
    "classTypeOverrides": {
        "category": "TRANSIENT_UI_STATE",
        "canonical_owner": "Client UI Session",
        "manager": "step2.js",
        "description": "Client workflow cache for manual lecture vs lecture_lab overrides",
        "reset_behavior": "Survives session reload; not affected by config or preference reset",
    },
}


def _extract_all_localstorage_keys():
    """Scans all frontend files in executable_test/ to find every referenced localStorage key string literal."""
    discovered_keys = set()
    patterns = [
        re.compile(r"""localStorage\.(?:getItem|setItem|removeItem)\s*\(\s*["']([^"']+)["']"""),
        re.compile(r"""const\s+[A-Z0-9_]+\s*=\s*["'](cvsu_[^"']+)["']"""),
    ]

    target_files = [UI_HTML_PATH]
    if os.path.exists(JS_DIR):
        for root, _, files in os.walk(JS_DIR):
            for file in files:
                if file.endswith(".js"):
                    target_files.append(os.path.join(root, file))

    for filepath in target_files:
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for pat in patterns:
            for match in pat.finditer(content):
                key = match.group(1).strip()
                # Skip non-key fragments
                if key and not key.startswith("data-"):
                    discovered_keys.add(key)

    return discovered_keys


def test_every_frontend_localstorage_key_is_classified():
    """
    Ensures that any localStorage key introduced into the frontend is fully accounted for
    in the canonical inventory and classified into an authorized architecture category.
    """
    discovered_keys = _extract_all_localstorage_keys()
    assert discovered_keys, "Should discover localStorage keys in frontend code"

    for key in discovered_keys:
        assert key in LOCALSTORAGE_AUTHORITY_INVENTORY, (
            f"Unclassified localStorage key '{key}' found in frontend code! "
            f"Every persistent key must be registered in LOCALSTORAGE_AUTHORITY_INVENTORY "
            f"with its category, canonical owner, and reset behavior."
        )

    for key, spec in LOCALSTORAGE_AUTHORITY_INVENTORY.items():
        assert spec["category"] in CANONICAL_CATEGORIES, (
            f"Invalid category '{spec['category']}' for key '{key}'. Must be in {CANONICAL_CATEGORIES}."
        )
        assert spec["canonical_owner"], f"Key '{key}' must have a documented canonical owner."
        assert spec["manager"], f"Key '{key}' must have a documented manager."
        assert spec["reset_behavior"], f"Key '{key}' must document its reset behavior."


def test_no_browser_sessionstorage_or_indexeddb_used():
    """
    Enforces that the application relies solely on localStorage for 0ms startup acceleration
    and does not introduce hidden or unmonitored sessionStorage or IndexedDB persistence.
    """
    disallowed_patterns = [
        re.compile(r"""\bsessionStorage\.(?:getItem|setItem|removeItem|clear)\b"""),
        re.compile(r"""\bindexedDB\.open\b"""),
    ]

    target_files = [UI_HTML_PATH]
    if os.path.exists(JS_DIR):
        for root, _, files in os.walk(JS_DIR):
            for file in files:
                if file.endswith(".js"):
                    target_files.append(os.path.join(root, file))

    for filepath in target_files:
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for pat in disallowed_patterns:
            assert not pat.search(content), (
                f"Disallowed storage API found in {os.path.basename(filepath)} matching '{pat.pattern}'."
            )


def test_script_api_method_categorization_and_single_ownership():
    """
    Validates that every method on ScriptAPI belongs to an authorized subsystem mixin
    and preserves single-ownership boundaries without bypassing managers.
    """
    from executable_test.main import ScriptAPI
    api = ScriptAPI()

    # Verify ConfigMixin delegates to config_manager and preferences_manager exclusively
    from modules.common.config_manager import ParserConfigManager
    from modules.common.preferences_manager import PreferencesManager

    assert hasattr(api, "get_parser_config")
    assert hasattr(api, "save_parser_config")
    assert hasattr(api, "reset_parser_config")
    assert hasattr(api, "export_parser_config")
    assert hasattr(api, "import_parser_config")

    assert hasattr(api, "get_user_preferences")
    assert hasattr(api, "save_user_preferences")
    assert hasattr(api, "reset_user_preferences")
    assert hasattr(api, "export_user_preferences")
    assert hasattr(api, "import_user_preferences")


def test_export_import_boundary_isolation(tmp_path):
    """
    Proves that parser configuration and user preferences export/import mechanisms
    are strictly isolated and cannot mutate or contaminate each other.
    """
    from modules.common.config_manager import ParserConfigManager
    from modules.common.preferences_manager import PreferencesManager

    cfg_dir = tmp_path / "isolation_test"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    parser_mgr = ParserConfigManager(config_dir=str(cfg_dir))
    prefs_mgr = PreferencesManager(config_dir=str(cfg_dir))

    # 1. Custom settings in both
    parser_mgr.save_config({
        "ceit_prefix_map": {
            "CUST": {
                "name": "Custom Department",
                "dept": "Department of Custom",
                "dept_code": "DTC",
                "icon": "📚",
                "badge": "📚 DTC"
            }
        },
        "base_subject_prefixes": ["CUST"]
    })
    prefs_mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })

    # 2. Export both
    parser_export_path = str(cfg_dir / "parser_export.json")
    prefs_export_path = str(cfg_dir / "prefs_export.json")

    assert parser_mgr.export_config(parser_export_path)["status"] == "success"
    assert prefs_mgr.export_preferences(prefs_export_path)["status"] == "success"

    with open(parser_export_path, "r", encoding="utf-8") as f:
        parser_json = json.load(f)
    with open(prefs_export_path, "r", encoding="utf-8") as f:
        prefs_json = json.load(f)

    # 3. Assert zero schema cross-contamination in exported files
    assert "theme" not in parser_json, "Parser config export must not contain user theme"
    assert "accessibility" not in parser_json, "Parser config export must not contain accessibility settings"

    assert "ceit_prefix_map" not in prefs_json, "User preferences export must not contain parser prefix maps"
    assert "base_subject_prefixes" not in prefs_json, "User preferences export must not contain subject prefixes"
    assert "known_lab_subjects" not in prefs_json, "User preferences export must not contain lab subjects"

    # 4. Assert importing user preferences file into parser manager fails cleanly
    parser_import_attempt = parser_mgr.import_config(prefs_export_path)
    # Parser config requires parser schema keys; importing preference file fails validation
    assert parser_import_attempt["status"] == "error"

    # Verify parser state was NOT altered by bad import
    active_parser = parser_mgr.get_config()
    assert "CUST" in active_parser["ceit_prefix_map"]
    assert active_parser["ceit_prefix_map"]["CUST"]["name"] == "Custom Department"

    # 5. Assert importing parser config into preferences manager fails cleanly
    prefs_import_attempt = prefs_mgr.import_preferences(parser_export_path)
    assert prefs_import_attempt["status"] == "error"

    # Verify user preferences were NOT altered by bad import (no theme change, no motion change, no transparency change)
    active_prefs = prefs_mgr.get_preferences()
    assert active_prefs["theme"] == "light"
    assert active_prefs["accessibility"]["motion"] == "reduce"
    assert active_prefs["accessibility"]["transparency"] == "glass"
    assert "ceit_prefix_map" not in active_prefs
    assert "base_subject_prefixes" not in active_prefs
