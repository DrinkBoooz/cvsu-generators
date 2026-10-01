#!/usr/bin/env python3
"""
tests/test_user_preferences_architecture.py

Test Suite for User Preferences Persistence, Two-Tier Caching, Schema Validation,
Safe Fallbacks, Migration, and Reset Isolation.
"""

import os
import json
import pytest
from pathlib import Path
from modules.common.preferences_manager import (
    PreferencesManager,
    validate_preferences,
    get_default_preferences_dict,
    DEFAULT_USER_PREFERENCES
)
from modules.common.config_manager import ParserConfigManager
from executable_test.main import ScriptAPI


# ── 1. PreferencesManager Unit Tests ──────────────────────────────────────────

def test_preferences_manager_defaults(tmp_path):
    """Missing user_preferences.json should safely return factory defaults."""
    mgr = PreferencesManager(config_dir=str(tmp_path))
    prefs = mgr.get_preferences()

    assert prefs["version"] == "1.0"
    assert prefs["theme"] == "dark"
    assert prefs["accessibility"]["motion"] == "system"
    assert prefs["accessibility"]["transparency"] == "system"
    assert not os.path.exists(mgr.preferences_file)


def test_preferences_manager_save_and_reload(tmp_path):
    """Valid preferences must be atomically saved and reloaded from disk."""
    mgr = PreferencesManager(config_dir=str(tmp_path))
    new_prefs = {
        "version": "1.0",
        "theme": "light",
        "accessibility": {
            "motion": "reduce",
            "transparency": "glass"
        }
    }
    res = mgr.save_preferences(new_prefs)
    assert res["status"] == "success"
    assert os.path.exists(mgr.preferences_file)

    # Create second manager to simulate new application session
    mgr2 = PreferencesManager(config_dir=str(tmp_path))
    loaded = mgr2.get_preferences()
    assert loaded["theme"] == "light"
    assert loaded["accessibility"]["motion"] == "reduce"
    assert loaded["accessibility"]["transparency"] == "glass"


def test_preferences_manager_schema_validation_and_fallback():
    """Invalid enum values must fall back safely to defaults without raising."""
    # Complete garbage input
    assert validate_preferences("not a dict") == DEFAULT_USER_PREFERENCES
    assert validate_preferences(None) == DEFAULT_USER_PREFERENCES

    # Invalid theme
    bad_theme = validate_preferences({"theme": "neon-green"})
    assert bad_theme["theme"] == "dark"

    # Valid theme, invalid motion
    bad_motion = validate_preferences({
        "theme": "light",
        "accessibility": {"motion": "hyperspeed", "transparency": "glass"}
    })
    assert bad_motion["theme"] == "light"
    assert bad_motion["accessibility"]["motion"] == "system"
    assert bad_motion["accessibility"]["transparency"] == "glass"

    # Valid motion, invalid transparency
    bad_trans = validate_preferences({
        "theme": "dark",
        "accessibility": {"motion": "full", "transparency": "invisible"}
    })
    assert bad_trans["accessibility"]["motion"] == "full"
    assert bad_trans["accessibility"]["transparency"] == "system"


def test_preferences_manager_corrupted_file_recovery(tmp_path):
    """Corrupt or truncated JSON on disk must fall back safely without crashing."""
    corrupt_file = tmp_path / "user_preferences.json"
    corrupt_file.write_text("{malformed_json: true, unterminated", encoding="utf-8")

    mgr = PreferencesManager(config_dir=str(tmp_path))
    prefs = mgr.get_preferences()
    assert prefs["theme"] == "dark"
    assert prefs["accessibility"]["motion"] == "system"
    assert prefs["accessibility"]["transparency"] == "system"


def test_preferences_manager_reset_to_defaults(tmp_path):
    """Reset must remove user_preferences.json and restore factory defaults."""
    mgr = PreferencesManager(config_dir=str(tmp_path))
    mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "reduce"}
    })
    assert os.path.exists(mgr.preferences_file)

    reset_res = mgr.reset_preferences()
    assert reset_res["status"] == "success"
    assert not os.path.exists(mgr.preferences_file)
    assert mgr.get_preferences()["theme"] == "dark"
    assert mgr.get_preferences()["accessibility"]["motion"] == "system"


def test_preferences_manager_export_and_import(tmp_path):
    """Export and import must preserve portable user preferences across files."""
    cfg1 = tmp_path / "cfg1"
    cfg2 = tmp_path / "cfg2"
    mgr1 = PreferencesManager(config_dir=str(cfg1))
    mgr1.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "full", "transparency": "glass"}
    })

    export_file = str(tmp_path / "exported_prefs.json")
    exp_res = mgr1.export_preferences(export_file)
    assert exp_res["status"] == "success"
    assert os.path.exists(export_file)

    mgr2 = PreferencesManager(config_dir=str(cfg2))
    assert mgr2.get_preferences()["theme"] == "dark"

    imp_res = mgr2.import_preferences(export_file)
    assert imp_res["status"] == "success"
    assert mgr2.get_preferences()["theme"] == "light"
    assert mgr2.get_preferences()["accessibility"]["motion"] == "full"
    assert mgr2.get_preferences()["accessibility"]["transparency"] == "glass"


# ── 2. Reset Semantic Isolation Tests ─────────────────────────────────────────

def test_reset_parser_config_does_not_mutate_preferences(tmp_path, monkeypatch):
    """
    Crucial Architectural Contract:
    Resetting parser configuration MUST NOT touch user preferences.
    """
    config_dir = tmp_path / "app_config"
    parser_mgr = ParserConfigManager(config_dir=str(config_dir))
    prefs_mgr = PreferencesManager(config_dir=str(config_dir))

    # 1. Customize parser config
    pcfg = parser_mgr.get_config()
    pcfg["base_subject_prefixes"].append("TESTPREFIX")
    parser_mgr.save_config(pcfg)

    # 2. Customize user preferences
    prefs_mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })

    # 3. Reset parser configuration
    parser_mgr.reset_to_defaults()

    # 4. Verify parser config reverted
    assert "TESTPREFIX" not in parser_mgr.get_config()["base_subject_prefixes"]

    # 5. Verify user preferences are COMPLETELY UNTOUCHED
    active_prefs = prefs_mgr.get_preferences()
    assert active_prefs["theme"] == "light"
    assert active_prefs["accessibility"]["motion"] == "reduce"
    assert active_prefs["accessibility"]["transparency"] == "glass"
    assert os.path.exists(prefs_mgr.preferences_file)


def test_script_api_user_preferences_lifecycle(tmp_path, monkeypatch):
    """Verify ScriptAPI bridge exposes user preferences operations cleanly."""
    test_mgr = PreferencesManager(config_dir=str(tmp_path / "config"))
    monkeypatch.setattr("modules.common.preferences_manager.preferences_manager", test_mgr)

    api = ScriptAPI()

    # 1. Default preferences
    initial = api.get_user_preferences()
    assert initial["theme"] == "dark"
    assert initial["accessibility"]["motion"] == "system"

    # 2. Save preferences via API
    save_res = api.save_user_preferences({
        "theme": "light",
        "accessibility": {"motion": "full", "transparency": "reduce"}
    })
    assert save_res["status"] == "success"

    # 3. Reload via API
    reloaded = api.get_user_preferences()
    assert reloaded["theme"] == "light"
    assert reloaded["accessibility"]["motion"] == "full"
    assert reloaded["accessibility"]["transparency"] == "reduce"

    # 4. Reset preferences via API
    reset_res = api.reset_user_preferences()
    assert reset_res["status"] == "success"
    assert api.get_user_preferences()["theme"] == "dark"
