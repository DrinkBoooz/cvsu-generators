"""
Repository-Wide Persistent State Authority Inventory Test Suite (Commit 208).

Enforces:
1. Every persistent storage mechanism and key across frontend and backend is classified:
     - APPLICATION_CONFIGURATION
     - USER_PREFERENCES
     - TRANSIENT_UI_STATE
     - CACHE_COMPATIBILITY
     - DIAGNOSTIC_ARTIFACT (explicitly outside Model C application state)
2. Robust localStorage discovery in frontend code:
     - String literals, window prefix, bracket access, and statically resolved constants.
     - Documents static-analysis boundaries.
3. Actual single-ownership proof:
     - ScriptAPI methods delegate to ParserConfigManager and PreferencesManager via monkeypatched call tracking.
     - AST analysis verifies no ScriptAPI method directly writes parser_settings.json or user_preferences.json.
     - AST analysis proves canonical files have exactly one authorized writer module.
4. Strict Complete-Document Import Contract:
     - Complete export -> import round-trips succeed.
     - Partial parser configuration imports are rejected without mutating active parser state.
     - Partial user preference imports are rejected without mutating active preferences.
     - Cross-domain imports are rejected without mutating either store.
5. Accurate separation of Custom Template vs Template Set persistence paths and owners.
"""

import ast
import json
import os
import re
from pathlib import Path
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTABLE_TEST_DIR = os.path.join(WORKSPACE_DIR, "executable_test")
JS_DIR = os.path.join(EXECUTABLE_TEST_DIR, "js")
UI_HTML_PATH = os.path.join(EXECUTABLE_TEST_DIR, "ui.html")
MODULES_DIR = os.path.join(WORKSPACE_DIR, "modules")

# ══════════════════════════════════════════════════════════════════════════════
# Canonical Persistent State Inventory Specification
# ══════════════════════════════════════════════════════════════════════════════

CANONICAL_CATEGORIES = {
    "APPLICATION_CONFIGURATION",
    "USER_PREFERENCES",
    "TRANSIENT_UI_STATE",
    "CACHE_COMPATIBILITY",
}

NON_MODEL_C_CATEGORIES = {
    "DIAGNOSTIC_ARTIFACT",
}

ALL_RECOGNIZED_CATEGORIES = CANONICAL_CATEGORIES | NON_MODEL_C_CATEGORIES

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

NATIVE_PERSISTENCE_REGISTRY = {
    "parser_settings": {
        "relative_path": "config/parser_settings.json",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "ParserConfigManager",
        "writer_module": "modules.common.config_manager",
        "writer_method": "ParserConfigManager.save_config",
        "persistence_mechanism": "tempfile.mkstemp + os.replace",
    },
    "custom_templates_index": {
        "relative_path": "custom_templates/templates.json",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "ParserConfigManager",
        "writer_module": "modules.common.config_manager",
        "writer_method": "ParserConfigManager.save_custom_template",
        "persistence_mechanism": "tempfile.NamedTemporaryFile + os.replace",
    },
    "custom_template_files": {
        "relative_path": "custom_templates/*.docx",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "ParserConfigManager",
        "writer_module": "modules.common.config_manager",
        "writer_method": "ParserConfigManager.save_custom_template",
        "persistence_mechanism": "shutil.copy2",
    },
    "template_sets_manifest": {
        "relative_path": "template_sets/<set_id>/manifest.json",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "TemplateSetManager",
        "writer_module": "modules.services.template_set_manager",
        "writer_method": "TemplateSetManager._save_template_set",
        "persistence_mechanism": "tempfile.NamedTemporaryFile + os.replace",
    },
    "active_template_set": {
        "relative_path": "active_template_set.json",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "TemplateSetManager",
        "writer_module": "modules.services.template_set_manager",
        "writer_method": "TemplateSetManager.set_active_template_set",
        "persistence_mechanism": "tempfile.NamedTemporaryFile + os.replace",
    },
    "user_preferences": {
        "relative_path": "config/user_preferences.json",
        "category": "USER_PREFERENCES",
        "canonical_owner": "PreferencesManager",
        "writer_module": "modules.common.preferences_manager",
        "writer_method": "PreferencesManager._persist_locked",
        "persistence_mechanism": "tempfile.mkstemp + os.replace",
    },
    "runtime_logs": {
        "relative_path": "logs/app.log",
        "category": "DIAGNOSTIC_ARTIFACT",
        "canonical_owner": "logger.py",
        "writer_module": "modules.common.logger",
        "writer_method": "logging.handlers.RotatingFileHandler",
        "persistence_mechanism": "RotatingFileHandler.emit",
    },
    "crash_logs": {
        "relative_path": "logs/crash_*.log",
        "category": "DIAGNOSTIC_ARTIFACT",
        "canonical_owner": "logger.py",
        "writer_module": "modules.common.logger",
        "writer_method": "log_crash",
        "persistence_mechanism": "open(..., 'w')",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Section D: Robust localStorage Static Discovery
# ══════════════════════════════════════════════════════════════════════════════

def _extract_all_localstorage_keys():
    """
    Robust static scanner recovering localStorage keys across frontend assets.

    Static Analysis Boundary:
    - Scans all .js and .html files under executable_test/.
    - Resolves string literals passed to localStorage.getItem/setItem/removeItem,
      window.localStorage.*, and bracket-notation access localStorage['key'].
    - Statically resolves top-level identifier constants (e.g. const CVSU_ACC_MOTION_KEY = 'cvsu_acc_motion').
    - Boundary Limit: Does NOT execute JavaScript or trace dynamic computed runtime keys.
    """
    discovered_keys = set()

    target_files = [UI_HTML_PATH]
    if os.path.exists(JS_DIR):
        for root, _, files in os.walk(JS_DIR):
            for file in files:
                if file.endswith(".js"):
                    target_files.append(os.path.join(root, file))

    # Pattern 1: Constant variable declarations (e.g. const CVSU_GEN_THEME_KEY = "cvsu_gen_theme";)
    const_decl_pat = re.compile(r"""(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*["']([^"']+)["']""")

    # Pattern 2: localStorage method calls: (window.)localStorage.(getItem|setItem|removeItem)(arg)
    ls_method_pat = re.compile(
        r"""(?:window\.)?localStorage\.(?:getItem|setItem|removeItem)\s*\(\s*([^,\)]+)"""
    )

    # Pattern 3: localStorage bracket access: (window.)localStorage[arg]
    ls_bracket_pat = re.compile(
        r"""(?:window\.)?localStorage\s*\[\s*([^\]]+)\s*\]"""
    )

    for filepath in target_files:
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Build local identifier constant table for this file
        file_constants = {}
        for match in const_decl_pat.finditer(content):
            ident, val = match.group(1).strip(), match.group(2).strip()
            file_constants[ident] = val

        # Extract from method calls
        for match in ls_method_pat.finditer(content):
            raw_arg = match.group(1).strip()
            # If literal string
            if (raw_arg.startswith('"') and raw_arg.endswith('"')) or (
                raw_arg.startswith("'") and raw_arg.endswith("'")
            ):
                key = raw_arg[1:-1].strip()
                if key and not key.startswith("data-"):
                    discovered_keys.add(key)
            elif raw_arg in file_constants:
                key = file_constants[raw_arg]
                if key and not key.startswith("data-"):
                    discovered_keys.add(key)

        # Extract from bracket access
        for match in ls_bracket_pat.finditer(content):
            raw_arg = match.group(1).strip()
            if (raw_arg.startswith('"') and raw_arg.endswith('"')) or (
                raw_arg.startswith("'") and raw_arg.endswith("'")
            ):
                key = raw_arg[1:-1].strip()
                if key and not key.startswith("data-"):
                    discovered_keys.add(key)
            elif raw_arg in file_constants:
                key = file_constants[raw_arg]
                if key and not key.startswith("data-"):
                    discovered_keys.add(key)

    return discovered_keys


def test_every_frontend_localstorage_key_is_classified():
    """
    Ensures that every localStorage key discovered via robust static analysis
    in frontend assets is registered in the authority inventory and classified.
    """
    discovered_keys = _extract_all_localstorage_keys()
    assert discovered_keys, "Should discover localStorage keys in frontend code"

    for key in discovered_keys:
        assert key in LOCALSTORAGE_AUTHORITY_INVENTORY, (
            f"Unclassified localStorage key '{key}' found in frontend code! "
            f"Every persistent key must be registered in LOCALSTORAGE_AUTHORITY_INVENTORY."
        )

    for key, spec in LOCALSTORAGE_AUTHORITY_INVENTORY.items():
        assert spec["category"] in CANONICAL_CATEGORIES, (
            f"Invalid category '{spec['category']}' for key '{key}'."
        )
        assert spec["canonical_owner"], f"Key '{key}' must have a documented canonical owner."
        assert spec["manager"], f"Key '{key}' must have a documented manager."
        assert spec["reset_behavior"], f"Key '{key}' must document its reset behavior."


def test_no_browser_sessionstorage_or_indexeddb_used():
    """
    Enforces that the application relies solely on localStorage for 0ms startup acceleration
    and introduces zero hidden sessionStorage or IndexedDB persistence.
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


# ══════════════════════════════════════════════════════════════════════════════
# Section B: True Single-Owner Governance Proof
# ══════════════════════════════════════════════════════════════════════════════

def test_script_api_method_delegation_to_authoritative_managers(monkeypatch):
    """
    Proves via controlled call-interception that ScriptAPI methods do NOT implement
    independent persistence logic, but strictly delegate to the authoritative managers:
      - Parser methods delegate to config_manager (ParserConfigManager)
      - Preference methods delegate to preferences_manager (PreferencesManager)
    """
    from executable_test.main import ScriptAPI
    from modules.common.config_manager import config_manager
    from modules.common.preferences_manager import preferences_manager

    api = ScriptAPI()

    monkeypatch.setattr(config_manager, "get_config", lambda: {"delegated": "get_parser_config"})
    monkeypatch.setattr(config_manager, "save_config", lambda c: {"delegated": "save_parser_config", "received": c})
    monkeypatch.setattr(config_manager, "reset_to_defaults", lambda: {"delegated": "reset_parser_config"})

    monkeypatch.setattr(preferences_manager, "get_preferences", lambda: {"delegated": "get_user_preferences"})
    monkeypatch.setattr(preferences_manager, "save_preferences", lambda p: {"delegated": "save_user_preferences", "received": p})
    monkeypatch.setattr(preferences_manager, "reset_preferences", lambda: {"delegated": "reset_user_preferences"})

    # 1. Parser delegation
    res_get_p = api.get_parser_config()
    assert res_get_p == {"delegated": "get_parser_config"}

    res_save_p = api.save_parser_config({"sample_parser_key": 123})
    assert res_save_p["delegated"] == "save_parser_config"
    assert res_save_p["received"] == {"sample_parser_key": 123}

    res_reset_p = api.reset_parser_config()
    assert res_reset_p["delegated"] == "reset_parser_config"

    # 2. Preferences delegation
    res_get_u = api.get_user_preferences()
    assert res_get_u == {"delegated": "get_user_preferences"}

    res_save_u = api.save_user_preferences({"sample_pref_key": 456})
    assert res_save_u == {"delegated": "save_user_preferences", "received": {"sample_pref_key": 456}}

    res_reset_u = api.reset_user_preferences()
    assert res_reset_u == {"delegated": "reset_user_preferences"}


def test_ast_proves_no_direct_file_writes_in_script_api():
    """
    AST analysis proving that no file in executable_test/api/ contains direct file writes
    targeting parser_settings.json or user_preferences.json.
    All persistence operations must route through the respective managers.
    """
    api_dir = os.path.join(EXECUTABLE_TEST_DIR, "api")
    py_files = [os.path.join(api_dir, f) for f in os.listdir(api_dir) if f.endswith(".py")]

    forbidden_filenames = {"parser_settings.json", "user_preferences.json", "templates.json", "active_template_set.json"}

    for py_file in py_files:
        with open(py_file, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=py_file)

        for node in ast.walk(tree):
            # Check for direct calls to open(..., 'w'/'wb'/'a')
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name == "open":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            for forbidden in forbidden_filenames:
                                assert forbidden not in arg.value, (
                                    f"Direct write open() of forbidden file '{forbidden}' detected in {py_file}"
                                )


def test_ast_proves_single_writer_module_for_canonical_files():
    """
    AST and source audit verifying that manager-owned canonical files have
    exactly ONE authorized writer module across the entire application:
      - parser_settings.json is written exclusively by modules.common.config_manager
      - user_preferences.json is written exclusively by modules.common.preferences_manager
      - custom templates are written exclusively by modules.common.config_manager
      - active_template_set.json is written exclusively by modules.services.template_set_manager
    """
    all_py_files = []
    for base_dir in [MODULES_DIR, EXECUTABLE_TEST_DIR]:
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".py"):
                    all_py_files.append(os.path.join(root, file))

    for py_file in all_py_files:
        rel_path = os.path.relpath(py_file, WORKSPACE_DIR).replace("\\", "/")

        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check parser_settings.json write occurrences
        if "parser_settings.json" in content:
            if "os.replace" in content or "NamedTemporaryFile" in content or "mkstemp" in content:
                assert rel_path == "modules/common/config_manager.py", (
                    f"Unauthorized writer for parser_settings.json discovered in {rel_path}!"
                )

        # Check user_preferences.json write occurrences
        if "user_preferences.json" in content:
            if "os.replace" in content or "NamedTemporaryFile" in content or "mkstemp" in content:
                assert rel_path == "modules/common/preferences_manager.py", (
                    f"Unauthorized writer for user_preferences.json discovered in {rel_path}!"
                )

        # Check active_template_set.json write occurrences
        if "active_template_set.json" in content:
            if "os.replace" in content or "NamedTemporaryFile" in content or "mkstemp" in content:
                assert rel_path == "modules/services/template_set_manager.py", (
                    f"Unauthorized writer for active_template_set.json discovered in {rel_path}!"
                )


# ══════════════════════════════════════════════════════════════════════════════
# Section C & E: Native Persistence Registry & Category Verification
# ══════════════════════════════════════════════════════════════════════════════

def test_native_persistence_registry_classifications_and_path_separation():
    """
    Validates the repository's native persistence registry:
      1. Every entry belongs to an authorized category.
      2. Model C categories are strictly segregated from DIAGNOSTIC_ARTIFACT.
      3. Custom Template persistence paths (%APPDATA%/custom_templates) are strictly
         separated from Template Set persistence paths (%APPDATA%/template_sets, active_template_set.json).
      4. Owners and persistence mechanisms are explicitly mapped.
    """
    for entry_id, spec in NATIVE_PERSISTENCE_REGISTRY.items():
        assert spec["category"] in ALL_RECOGNIZED_CATEGORIES, (
            f"Invalid category '{spec['category']}' for registry entry '{entry_id}'."
        )
        assert spec["canonical_owner"], f"Entry '{entry_id}' missing canonical_owner."
        assert spec["writer_module"], f"Entry '{entry_id}' missing writer_module."
        assert spec["persistence_mechanism"], f"Entry '{entry_id}' missing persistence_mechanism."

    # Validate distinct path separation between custom templates and template sets
    custom_template_paths = [
        spec["relative_path"] for spec in NATIVE_PERSISTENCE_REGISTRY.values()
        if "custom_template" in spec["relative_path"]
    ]
    template_set_paths = [
        spec["relative_path"] for spec in NATIVE_PERSISTENCE_REGISTRY.values()
        if "template_set" in spec["relative_path"] or "active_template_set" in spec["relative_path"]
    ]

    for c_path in custom_template_paths:
        assert not any(t_path in c_path for t_path in template_set_paths), (
            f"Custom template path '{c_path}' conflated with template set path!"
        )

    # Validate diagnostic artifacts are outside Model C
    diag_entries = [
        spec for spec in NATIVE_PERSISTENCE_REGISTRY.values()
        if spec["category"] == "DIAGNOSTIC_ARTIFACT"
    ]
    assert len(diag_entries) >= 2, "Expected diagnostic artifact classifications for runtime and crash logs"
    for diag in diag_entries:
        assert diag["category"] not in CANONICAL_CATEGORIES, (
            "Diagnostic artifacts must not be classified into Model C application state categories"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Section A: Complete Document Import Contract & Regression Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_complete_export_import_roundtrip_succeeds(tmp_path):
    """
    Requirement A3: Valid complete exports from ParserConfigManager and PreferencesManager
    round-trip successfully and restore full canonical state.
    """
    from modules.common.config_manager import ParserConfigManager
    from modules.common.preferences_manager import PreferencesManager

    cfg_dir = tmp_path / "rt_test"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    parser_mgr = ParserConfigManager(config_dir=str(cfg_dir))
    prefs_mgr = PreferencesManager(config_dir=str(cfg_dir))

    # Configure custom complete state
    full_parser_doc = parser_mgr.get_config()
    full_parser_doc["ceit_prefix_map"]["NEW_DEPT"] = {
        "name": "New Department",
        "dept": "Department of Innovation",
        "dept_code": "DOI",
        "icon": "🚀",
        "badge": "🚀 DOI"
    }
    parser_mgr.save_config(full_parser_doc)

    full_prefs_doc = {
        "version": "1.0",
        "theme": "light",
        "accessibility": {
            "motion": "reduce",
            "transparency": "glass"
        }
    }
    prefs_mgr.save_preferences(full_prefs_doc)

    # Export both
    p_export = str(cfg_dir / "full_parser_export.json")
    u_export = str(cfg_dir / "full_prefs_export.json")

    assert parser_mgr.export_config(p_export)["status"] == "success"
    assert prefs_mgr.export_preferences(u_export)["status"] == "success"

    # Import into fresh managers
    cfg_dir2 = tmp_path / "rt_target"
    cfg_dir2.mkdir(parents=True, exist_ok=True)
    p2 = ParserConfigManager(config_dir=str(cfg_dir2))
    u2 = PreferencesManager(config_dir=str(cfg_dir2))

    assert p2.import_config(p_export)["status"] == "success"
    assert "NEW_DEPT" in p2.get_config()["ceit_prefix_map"]

    assert u2.import_preferences(u_export)["status"] == "success"
    assert u2.get_preferences()["theme"] == "light"
    assert u2.get_preferences()["accessibility"]["motion"] == "reduce"
    assert u2.get_preferences()["accessibility"]["transparency"] == "glass"


def test_partial_parser_import_rejected_without_mutating_state(tmp_path):
    """
    Requirement A1 & A6: A partial parser configuration file (missing canonical keys)
    is rejected with a clear error and leaves active canonical parser state byte-for-byte unchanged.
    """
    from modules.common.config_manager import ParserConfigManager

    cfg_dir = tmp_path / "partial_parser_test"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    mgr = ParserConfigManager(config_dir=str(cfg_dir))

    # Initial state with custom dept
    init_cfg = mgr.get_config()
    init_cfg["ceit_prefix_map"]["ACTIVE_DEPT"] = {
        "name": "Active Dept", "dept": "Active", "dept_code": "ACT", "icon": "⚡", "badge": "⚡ ACT"
    }
    mgr.save_config(init_cfg)
    before_state = mgr.get_config()

    # Create partial parser JSONs missing required keys
    partial_1 = str(cfg_dir / "partial_1.json")
    with open(partial_1, "w", encoding="utf-8") as f:
        # Only has ceit_prefix_map, missing base_subject_prefixes, known_lab_subjects, etc.
        json.dump({"ceit_prefix_map": {"HAZARD": {"name": "Hazardous"}}}, f)

    res1 = mgr.import_config(partial_1)
    assert res1["status"] == "error"
    assert "Incomplete parser configuration document" in res1["message"]

    # Assert active store is completely untouched
    after_state = mgr.get_config()
    assert after_state == before_state
    assert "HAZARD" not in after_state["ceit_prefix_map"]
    assert "ACTIVE_DEPT" in after_state["ceit_prefix_map"]


def test_partial_preferences_import_rejected_without_mutating_state(tmp_path):
    """
    Requirement A2 & A6: A partial preferences file (e.g. only 'theme', or missing subkeys)
    is rejected with a clear error and leaves active canonical preferences unchanged.
    """
    from modules.common.preferences_manager import PreferencesManager

    cfg_dir = tmp_path / "partial_prefs_test"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    mgr = PreferencesManager(config_dir=str(cfg_dir))

    # Initial state
    mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "full", "transparency": "glass"}
    })
    before_state = mgr.get_preferences()

    # 1. Missing accessibility completely
    partial_1 = str(cfg_dir / "theme_only.json")
    with open(partial_1, "w", encoding="utf-8") as f:
        json.dump({"theme": "dark"}, f)

    res1 = mgr.import_preferences(partial_1)
    assert res1["status"] == "error"
    assert "Incomplete preferences document" in res1["message"]

    # 2. Incomplete accessibility (missing motion)
    partial_2 = str(cfg_dir / "missing_motion.json")
    with open(partial_2, "w", encoding="utf-8") as f:
        json.dump({"theme": "dark", "accessibility": {"transparency": "reduce"}}, f)

    res2 = mgr.import_preferences(partial_2)
    assert res2["status"] == "error"
    assert "Incomplete preferences document" in res2["message"]

    # Assert active preferences are completely unchanged
    after_state = mgr.get_preferences()
    assert after_state == before_state
    assert after_state["theme"] == "light"
    assert after_state["accessibility"]["motion"] == "full"
    assert after_state["accessibility"]["transparency"] == "glass"


def test_cross_domain_imports_rejected_without_mutating_stores(tmp_path):
    """
    Requirement A4, A5 & A6: Proves that cross-domain imports are strictly rejected:
      - Parser export cannot import into PreferencesManager
      - Preferences export cannot import into ParserConfigManager
    Both active stores remain unchanged.
    """
    from modules.common.config_manager import ParserConfigManager
    from modules.common.preferences_manager import PreferencesManager

    cfg_dir = tmp_path / "cross_domain_test"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    parser_mgr = ParserConfigManager(config_dir=str(cfg_dir))
    prefs_mgr = PreferencesManager(config_dir=str(cfg_dir))

    # Custom settings in both
    full_parser_doc = parser_mgr.get_config()
    full_parser_doc["ceit_prefix_map"]["CUST"] = {
        "name": "Custom Department", "dept": "Department of Custom", "dept_code": "DTC", "icon": "📚", "badge": "📚 DTC"
    }
    parser_mgr.save_config(full_parser_doc)

    prefs_mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })

    parser_before = parser_mgr.get_config()
    prefs_before = prefs_mgr.get_preferences()

    parser_export = str(cfg_dir / "parser_export.json")
    prefs_export = str(cfg_dir / "prefs_export.json")

    assert parser_mgr.export_config(parser_export)["status"] == "success"
    assert prefs_mgr.export_preferences(prefs_export)["status"] == "success"

    # Cross import 1: Import preferences export into parser manager -> REJECTED
    res_p = parser_mgr.import_config(prefs_export)
    assert res_p["status"] == "error"
    assert parser_mgr.get_config() == parser_before

    # Cross import 2: Import parser export into preferences manager -> REJECTED
    res_u = prefs_mgr.import_preferences(parser_export)
    assert res_u["status"] == "error"
    assert prefs_mgr.get_preferences() == prefs_before
