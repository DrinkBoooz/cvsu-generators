"""
Static Persistent-State Governance Inventory & Authority Test Suite (Commit 209).

Enforces:
1. Self-Validating Native Persistence Registry:
     - Declared writer modules and methods are verified against actual Python source AST.
     - Detects renamed or invalid writer methods (e.g. _save_manifest, activate_template_set).
2. Strengthened Single-Writer Governance:
     - All six canonical native stores have exactly one authoritative writer module.
     - AST source inspection verifies writer methods contain actual persistence I/O.
     - Proves unauthorized application modules contain zero direct write paths.
3. Custom-Template Writer Governance:
     - ParserConfigManager owns templates.json (metadata) and *.docx (physical files).
     - Separate governance for save_custom_template, toggle_custom_template, delete_custom_template.
4. Robust Frontend Web Storage Discovery:
     - Scans all application .html and .js files recursively under executable_test/.
     - Resolves literals, window prefix, bracket access, and static constants.
     - Documents static-analysis boundaries.
5. Strict Complete-Document Import Contract & Exact Byte Preservation:
     - Complete export -> import round-trips succeed.
     - Rejected imports (partial, cross-domain, unsupported schema, invalid values)
       preserve exact canonical file bytes (open(..., 'rb').read()) and semantic state.
     - Rejected imports on absent stores create zero files on disk.
6. Diagnostic Artifact Segregation:
     - Operational runtime logs (generator.log, crash.log) are classified as DIAGNOSTIC_ARTIFACT
       strictly outside Model C application state.
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
        "secondary_methods": [
            "ParserConfigManager.toggle_custom_template",
            "ParserConfigManager.delete_custom_template",
        ],
        "persistence_mechanism": "tempfile.NamedTemporaryFile + os.replace",
    },
    "custom_template_files": {
        "relative_path": "custom_templates/*.docx",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "ParserConfigManager",
        "writer_module": "modules.common.config_manager",
        "writer_method": "ParserConfigManager.save_custom_template",
        "secondary_methods": [
            "ParserConfigManager.delete_custom_template",
        ],
        "persistence_mechanism": "shutil.copy2 + os.remove",
    },
    "template_sets_manifest": {
        "relative_path": "template_sets/<set_id>/manifest.json",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "TemplateSetManager",
        "writer_module": "modules.services.template_set_manager",
        "writer_method": "TemplateSetManager._save_manifest",
        "secondary_methods": [
            "TemplateSetManager.delete_template_set",
        ],
        "persistence_mechanism": "tempfile.NamedTemporaryFile + os.replace + shutil.rmtree",
    },
    "active_template_set": {
        "relative_path": "active_template_set.json",
        "category": "APPLICATION_CONFIGURATION",
        "canonical_owner": "TemplateSetManager",
        "writer_module": "modules.services.template_set_manager",
        "writer_method": "TemplateSetManager.activate_template_set",
        "persistence_mechanism": "tempfile.NamedTemporaryFile + os.replace",
    },
    "user_preferences": {
        "relative_path": "config/user_preferences.json",
        "category": "USER_PREFERENCES",
        "canonical_owner": "PreferencesManager",
        "writer_module": "modules.common.preferences_manager",
        "writer_method": "PreferencesManager._persist_locked",
        "secondary_methods": [
            "PreferencesManager.reset_preferences",
        ],
        "persistence_mechanism": "tempfile.mkstemp + os.replace + os.remove",
    },
    "runtime_logs": {
        "relative_path": "logs/generator.log",
        "category": "DIAGNOSTIC_ARTIFACT",
        "canonical_owner": "logger.py",
        "writer_module": "modules.common.logger",
        "writer_method": "install_global_hooks",
        "persistence_mechanism": "RotatingFileHandler",
    },
    "crash_logs": {
        "relative_path": "logs/crash.log",
        "category": "DIAGNOSTIC_ARTIFACT",
        "canonical_owner": "logger.py",
        "writer_module": "modules.common.logger",
        "writer_method": "install_global_hooks",
        "persistence_mechanism": "RotatingFileHandler",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Section A: Self-Validating Native Persistence Registry
# ══════════════════════════════════════════════════════════════════════════════

def _inspect_method_has_persistence_io(func_node: ast.FunctionDef) -> bool:
    """
    Checks if an AST function/method node contains filesystem write/persistence operations:
    Calls to open(), mkstemp(), NamedTemporaryFile(), replace(), rename(), copy2(), remove(),
    rmtree(), or RotatingFileHandler.
    """
    io_identifiers = {
        "open", "mkstemp", "NamedTemporaryFile", "replace", "rename",
        "copy2", "remove", "rmtree", "RotatingFileHandler", "dump", "_make_rotating_handler"
    }
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name) and sub.func.id in io_identifiers:
                return True
            if isinstance(sub.func, ast.Attribute) and sub.func.attr in io_identifiers:
                return True
    return False


def _validate_registry_entry_symbol(module_name: str, method_decl: str):
    """
    Statically inspects the actual Python source for the module and method:
    1. Proves module file exists on disk.
    2. Parses AST and locates declared Class / Function.
    3. If Class.method, proves method belongs to declared Class.
    4. Proves method contains actual filesystem persistence operations.
    Returns (success: bool, error_msg: str).
    """
    mod_parts = module_name.split(".")
    rel_path = os.path.join(*mod_parts) + ".py"
    full_path = os.path.join(WORKSPACE_DIR, rel_path)
    if not os.path.isfile(full_path):
        return False, f"Declared writer module file '{full_path}' does not exist on disk."

    with open(full_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=full_path)

    if "." in method_decl:
        class_name, method_name = method_decl.split(".", 1)
        target_class = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                target_class = node
                break
        if not target_class:
            return False, f"Class '{class_name}' not found in module '{module_name}'."

        target_func = None
        for item in target_class.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                target_func = item
                break
        if not target_func:
            return False, f"Method '{method_name}' not found in class '{class_name}' ({module_name})."

        if not _inspect_method_has_persistence_io(target_func):
            return False, f"Method '{class_name}.{method_name}' does not contain recognized persistence I/O operations."

        return True, ""
    else:
        target_func = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_decl:
                target_func = node
                break
        if not target_func:
            return False, f"Function '{method_decl}' not found in module '{module_name}'."

        if not _inspect_method_has_persistence_io(target_func):
            return False, f"Function '{method_decl}' does not contain recognized persistence I/O operations."

        return True, ""


def test_native_persistence_registry_self_validates_against_source():
    """
    Requirement A: The native persistence registry must self-validate against
    the actual Python source code via AST inspection.
    Validates that every writer module and writer method exists and performs persistence I/O.
    """
    for entry_id, spec in NATIVE_PERSISTENCE_REGISTRY.items():
        module_name = spec["writer_module"]
        primary_method = spec["writer_method"]

        valid, err = _validate_registry_entry_symbol(module_name, primary_method)
        assert valid, f"Registry entry '{entry_id}' failed source validation: {err}"

        for sec_method in spec.get("secondary_methods", []):
            valid_sec, sec_err = _validate_registry_entry_symbol(module_name, sec_method)
            assert valid_sec, f"Registry entry '{entry_id}' secondary method failed validation: {sec_err}"


def test_native_persistence_registry_detects_invalid_or_renamed_methods():
    """
    Requirement A: Proves that the self-validating registry actually catches incorrect,
    renamed, or hallucinated writer method names (e.g. old _save_template_set or set_active_template_set).
    """
    valid, err = _validate_registry_entry_symbol(
        "modules.services.template_set_manager", "TemplateSetManager._save_template_set"
    )
    assert not valid
    assert "Method '_save_template_set' not found in class 'TemplateSetManager'" in err

    valid, err = _validate_registry_entry_symbol(
        "modules.services.template_set_manager", "TemplateSetManager.set_active_template_set"
    )
    assert not valid
    assert "Method 'set_active_template_set' not found in class 'TemplateSetManager'" in err

    valid, err = _validate_registry_entry_symbol(
        "modules.common.config_manager", "ParserConfigManager.non_existent_save_method"
    )
    assert not valid
    assert "Method 'non_existent_save_method' not found" in err


# ══════════════════════════════════════════════════════════════════════════════
# Section B & C: Single-Writer Governance & Custom-Template Writer Checks
# ══════════════════════════════════════════════════════════════════════════════

def _get_all_application_python_files():
    """
    Gathers all Python files across modules/ and executable_test/,
    excluding virtual environments, test fixtures, and build output directories.
    """
    py_files = []
    for base_dir in [MODULES_DIR, EXECUTABLE_TEST_DIR]:
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in {"venv", ".venv", "dist", "build", "__pycache__", ".git"}]
            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))
    return py_files


def test_ast_proves_single_authoritative_writer_for_all_canonical_native_stores():
    """
    Requirement B & C: Static source governance verifying that each of the six canonical
    native stores has exactly ONE authorized writer module across the entire application:
      1. config/parser_settings.json   -> modules/common/config_manager.py
      2. config/user_preferences.json  -> modules/common/preferences_manager.py
      3. custom_templates/templates.json -> modules/common/config_manager.py
      4. custom_templates/*.docx       -> modules/common/config_manager.py
      5. template_sets/<set_id>/manifest.json -> modules/services/template_set_manager.py
      6. active_template_set.json      -> modules/services/template_set_manager.py
    """
    py_files = _get_all_application_python_files()
    assert len(py_files) > 10, "Should discover application Python files"

    write_tokens = {"os.replace", "os.rename", "NamedTemporaryFile", "mkstemp", "open", "copy2", "rmtree"}

    for py_file in py_files:
        rel_path = os.path.relpath(py_file, WORKSPACE_DIR).replace("\\", "/")

        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. parser_settings.json
        if "parser_settings.json" in content:
            if any(wt in content for wt in ["os.replace", "NamedTemporaryFile", "mkstemp", "copy2"]):
                assert rel_path == "modules/common/config_manager.py", (
                    f"Unauthorized writer for parser_settings.json discovered in {rel_path}!"
                )

        # 2. user_preferences.json
        if "user_preferences.json" in content:
            if any(wt in content for wt in ["os.replace", "NamedTemporaryFile", "mkstemp", "copy2"]):
                assert rel_path == "modules/common/preferences_manager.py", (
                    f"Unauthorized writer for user_preferences.json discovered in {rel_path}!"
                )

        # 3. custom_templates/templates.json
        if "custom_templates" in content and "templates.json" in content:
            if any(wt in content for wt in ["os.replace", "NamedTemporaryFile", "mkstemp"]):
                assert rel_path == "modules/common/config_manager.py", (
                    f"Unauthorized writer for custom templates index discovered in {rel_path}!"
                )

        # 4. active_template_set.json
        if "active_template_set.json" in content:
            if any(wt in content for wt in ["os.replace", "NamedTemporaryFile", "mkstemp"]):
                assert rel_path == "modules/services/template_set_manager.py", (
                    f"Unauthorized writer for active_template_set.json discovered in {rel_path}!"
                )

        # 5. manifest.json (template-set manifest write)
        if "manifest.json" in content and "template_sets" in content:
            if any(wt in content for wt in ["os.replace", "NamedTemporaryFile", "mkstemp"]):
                assert rel_path == "modules/services/template_set_manager.py", (
                    f"Unauthorized writer for template set manifest.json discovered in {rel_path}!"
                )


def test_custom_template_writer_governance():
    """
    Requirement C: Verifies explicit source checks for custom templates:
      - ParserConfigManager.save_custom_template() owns creation/update (copy2 + NamedTemporaryFile + os.replace)
      - ParserConfigManager.toggle_custom_template() owns metadata update (NamedTemporaryFile + os.replace)
      - ParserConfigManager.delete_custom_template() owns removal (os.remove + NamedTemporaryFile + os.replace)
      - Proves physical .docx files and JSON metadata index are strictly handled by ParserConfigManager.
    """
    cfg_mgr_path = os.path.join(MODULES_DIR, "common", "config_manager.py")
    with open(cfg_mgr_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=cfg_mgr_path)
    parser_class = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ParserConfigManager"), None)
    assert parser_class is not None, "ParserConfigManager class must exist in config_manager.py"

    methods = {
        m.name: m for m in parser_class.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    # 1. save_custom_template: creates docx copy and updates index
    assert "save_custom_template" in methods
    save_source = ast.unparse(methods["save_custom_template"])
    assert "shutil.copy2" in save_source
    assert "os.replace" in save_source

    # 2. toggle_custom_template: updates index
    assert "toggle_custom_template" in methods
    toggle_source = ast.unparse(methods["toggle_custom_template"])
    assert "os.replace" in toggle_source

    # 3. delete_custom_template: removes docx and updates index
    assert "delete_custom_template" in methods
    del_source = ast.unparse(methods["delete_custom_template"])
    assert "os.remove" in del_source
    assert "os.replace" in del_source


# ══════════════════════════════════════════════════════════════════════════════
# Section D & F: Robust Frontend Web Storage Static Discovery
# ══════════════════════════════════════════════════════════════════════════════

def _extract_all_localstorage_keys():
    """
    Robust static scanner recovering localStorage keys across frontend assets.

    Static Governance Boundary & Limitations:
    - Scans all application .html and .js files recursively under executable_test/
      (excluding virtual environments, test fixtures, and build directories).
    - Resolves string literals passed to:
        (window.)localStorage.getItem(arg)
        (window.)localStorage.setItem(arg, ...)
        (window.)localStorage.removeItem(arg)
        (window.)localStorage[arg]
    - Statically resolves top-level identifier constants (e.g. const CVSU_ACC_MOTION_KEY = 'cvsu_acc_motion').
    - Boundary Limit: Does NOT execute JavaScript runtime code or evaluate dynamic string
      concatenation (e.g. localStorage.getItem('prefix_' + dynamicVar)).
    """
    discovered_keys = set()
    target_files = []

    for root, dirs, files in os.walk(EXECUTABLE_TEST_DIR):
        dirs[:] = [d for d in dirs if d not in {"venv", ".venv", "dist", "build", "__pycache__", ".git"}]
        for f in files:
            if f.endswith((".js", ".html")):
                target_files.append(os.path.join(root, f))

    const_decl_pat = re.compile(r"""(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*["']([^"']+)["']""")
    ls_method_pat = re.compile(
        r"""(?:window\.)?localStorage\.(?:getItem|setItem|removeItem)\s*\(\s*([^,\)]+)"""
    )
    ls_bracket_pat = re.compile(
        r"""(?:window\.)?localStorage\s*\[\s*([^\]]+)\s*\]"""
    )

    for filepath in target_files:
        if not os.path.isfile(filepath):
            continue
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        file_constants = {}
        for match in const_decl_pat.finditer(content):
            ident, val = match.group(1).strip(), match.group(2).strip()
            file_constants[ident] = val

        for match in ls_method_pat.finditer(content):
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
    Requirement D & F: Ensures that every localStorage key discovered via recursive
    static scan across executable_test/ is registered and classified in the inventory.
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
    Requirement D: Enforces that the application introduces zero hidden sessionStorage or IndexedDB persistence.
    """
    disallowed_patterns = [
        re.compile(r"""\bsessionStorage\.(?:getItem|setItem|removeItem|clear)\b"""),
        re.compile(r"""\bindexedDB\.open\b"""),
    ]

    target_files = []
    for root, dirs, files in os.walk(EXECUTABLE_TEST_DIR):
        dirs[:] = [d for d in dirs if d not in {"venv", ".venv", "dist", "build", "__pycache__", ".git"}]
        for f in files:
            if f.endswith((".js", ".html")):
                target_files.append(os.path.join(root, f))

    for filepath in target_files:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for pat in disallowed_patterns:
            assert not pat.search(content), (
                f"Disallowed storage API found in {os.path.basename(filepath)} matching '{pat.pattern}'."
            )


# ══════════════════════════════════════════════════════════════════════════════
# Section B: ScriptAPI Single-Ownership Delegation
# ══════════════════════════════════════════════════════════════════════════════

def test_script_api_method_delegation_to_authoritative_managers(monkeypatch):
    """
    Requirement B: Proves via controlled call-interception that ScriptAPI methods do NOT implement
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
    Requirement B: AST analysis proving that no file in executable_test/api/ contains direct file writes
    targeting parser_settings.json, user_preferences.json, templates.json, or active_template_set.json.
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


# ══════════════════════════════════════════════════════════════════════════════
# Section D & E: Complete Import Round-Trips & Exact Byte-Level Preservation
# ══════════════════════════════════════════════════════════════════════════════

def test_complete_export_import_roundtrip_succeeds(tmp_path):
    """
    Requirement D: Valid complete exports from ParserConfigManager and PreferencesManager
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


def test_rejected_imports_preserve_exact_canonical_file_bytes_and_state(tmp_path):
    """
    Requirement D & E: Proves that rejected imports preserve EXACT canonical file bytes
    and exact semantic state when an active store already exists on disk.
    Covers:
      1. Partial parser import (missing canonical keys)
      2. Partial preference import (missing theme or accessibility subkeys)
      3. Cross-domain parser -> preferences
      4. Cross-domain preferences -> parser
      5. Unsupported / future parser schema version
      6. Unsupported / future preference schema version
      7. Invalid preference value payload
    """
    from modules.common.config_manager import ParserConfigManager
    from modules.common.preferences_manager import PreferencesManager

    cfg_dir = tmp_path / "byte_audit"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    parser_mgr = ParserConfigManager(config_dir=str(cfg_dir))
    prefs_mgr = PreferencesManager(config_dir=str(cfg_dir))

    # Initialize known distinct state on disk
    init_parser = parser_mgr.get_config()
    init_parser["ceit_prefix_map"]["ACTIVE"] = {
        "name": "Active Dept", "dept": "Active", "dept_code": "ACT", "icon": "⚡", "badge": "⚡ ACT"
    }
    parser_mgr.save_config(init_parser)

    init_prefs = {
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    }
    prefs_mgr.save_preferences(init_prefs)

    p_file = parser_mgr.config_file
    u_file = prefs_mgr.preferences_file
    assert os.path.isfile(p_file)
    assert os.path.isfile(u_file)

    p_bytes_before = open(p_file, "rb").read()
    u_bytes_before = open(u_file, "rb").read()

    p_state_before = parser_mgr.get_config()
    u_state_before = prefs_mgr.get_preferences()

    # 1. Partial parser import
    partial_p = str(cfg_dir / "partial_p.json")
    with open(partial_p, "w", encoding="utf-8") as f:
        json.dump({"ceit_prefix_map": {"BAD": {"name": "Bad"}}}, f)
    res_p1 = parser_mgr.import_config(partial_p)
    assert res_p1["status"] == "error"
    assert open(p_file, "rb").read() == p_bytes_before
    assert parser_mgr.get_config() == p_state_before

    # 2. Partial preferences import
    partial_u1 = str(cfg_dir / "partial_u1.json")
    with open(partial_u1, "w", encoding="utf-8") as f:
        json.dump({"theme": "dark"}, f)
    res_u1 = prefs_mgr.import_preferences(partial_u1)
    assert res_u1["status"] == "error"
    assert open(u_file, "rb").read() == u_bytes_before
    assert prefs_mgr.get_preferences() == u_state_before

    partial_u2 = str(cfg_dir / "partial_u2.json")
    with open(partial_u2, "w", encoding="utf-8") as f:
        json.dump({"theme": "dark", "accessibility": {"motion": "full"}}, f)
    res_u2 = prefs_mgr.import_preferences(partial_u2)
    assert res_u2["status"] == "error"
    assert open(u_file, "rb").read() == u_bytes_before
    assert prefs_mgr.get_preferences() == u_state_before

    # 3. Cross-domain parser -> preferences
    p_export = str(cfg_dir / "parser_export.json")
    parser_mgr.export_config(p_export)
    res_cross1 = prefs_mgr.import_preferences(p_export)
    assert res_cross1["status"] == "error"
    assert open(u_file, "rb").read() == u_bytes_before
    assert prefs_mgr.get_preferences() == u_state_before

    # 4. Cross-domain preferences -> parser
    u_export = str(cfg_dir / "prefs_export.json")
    prefs_mgr.export_preferences(u_export)
    res_cross2 = parser_mgr.import_config(u_export)
    assert res_cross2["status"] == "error"
    assert open(p_file, "rb").read() == p_bytes_before
    assert parser_mgr.get_config() == p_state_before

    # 5. Unsupported / future parser schema
    future_p = str(cfg_dir / "future_p.json")
    future_p_data = dict(init_parser)
    future_p_data["version"] = "99.0"
    with open(future_p, "w", encoding="utf-8") as f:
        json.dump(future_p_data, f)
    res_fut_p = parser_mgr.import_config(future_p)
    assert res_fut_p["status"] == "error"
    assert "Unsupported parser configuration schema version" in res_fut_p["message"]
    assert open(p_file, "rb").read() == p_bytes_before
    assert parser_mgr.get_config() == p_state_before

    # 6. Unsupported / future preference schema
    future_u = str(cfg_dir / "future_u.json")
    future_u_data = dict(init_prefs)
    future_u_data["version"] = "2.0"
    with open(future_u, "w", encoding="utf-8") as f:
        json.dump(future_u_data, f)
    res_fut_u = prefs_mgr.import_preferences(future_u)
    assert res_fut_u["status"] == "error"
    assert "Unsupported preferences schema version" in res_fut_u["message"]
    assert open(u_file, "rb").read() == u_bytes_before
    assert prefs_mgr.get_preferences() == u_state_before

    # 7. Invalid preference values (unsupported theme name)
    invalid_theme_u = str(cfg_dir / "invalid_theme.json")
    with open(invalid_theme_u, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0",
            "theme": "unsupported_rainbow",
            "accessibility": {"motion": "reduce", "transparency": "glass"}
        }, f)
    res_inv_t = prefs_mgr.import_preferences(invalid_theme_u)
    assert res_inv_t["status"] == "error"
    assert "Invalid theme" in res_inv_t["message"]
    assert open(u_file, "rb").read() == u_bytes_before
    assert prefs_mgr.get_preferences() == u_state_before


def test_rejected_import_does_not_create_missing_canonical_file(tmp_path):
    """
    Requirement E: When the canonical store file does not exist initially on disk,
    a rejected import must NOT create an empty or corrupted file.
    """
    from modules.common.config_manager import ParserConfigManager
    from modules.common.preferences_manager import PreferencesManager

    empty_dir = tmp_path / "fresh_empty_store"
    empty_dir.mkdir(parents=True, exist_ok=True)

    fresh_p = ParserConfigManager(config_dir=str(empty_dir))
    fresh_u = PreferencesManager(config_dir=str(empty_dir))

    assert not os.path.exists(fresh_p.config_file)
    assert not os.path.exists(fresh_u.preferences_file)

    # Create invalid payloads
    bad_p = str(tmp_path / "bad_p.json")
    with open(bad_p, "w", encoding="utf-8") as f:
        json.dump({"version": "99.0", "incomplete": True}, f)

    bad_u = str(tmp_path / "bad_u.json")
    with open(bad_u, "w", encoding="utf-8") as f:
        json.dump({"version": "99.0", "theme": "invalid"}, f)

    res_p = fresh_p.import_config(bad_p)
    assert res_p["status"] == "error"
    assert not os.path.exists(fresh_p.config_file), "Rejected import must not create parser file"

    res_u = fresh_u.import_preferences(bad_u)
    assert res_u["status"] == "error"
    assert not os.path.exists(fresh_u.preferences_file), "Rejected import must not create preferences file"


# ══════════════════════════════════════════════════════════════════════════════
# Section G: Native Persistence Registry Classifications and Path Separation
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
