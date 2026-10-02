#!/usr/bin/env python3
"""
tests/test_user_preferences_architecture.py

Test Suite for User Preferences Persistence, Two-Tier Caching, Schema Validation,
Safe Fallbacks, Migration, and Reset Isolation.
"""

import os
import sys
import json
import threading
from copy import deepcopy
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


# ── 4. Additional Hardening Tests (Scenarios A, B, C, D) ──────────────────────

def test_corrupted_user_preferences_file_starts_with_defaults_scenario_b(tmp_path, monkeypatch):
    """
    Scenario B:
    Corrupted user_preferences.json on disk must cause application to start with defaults.
    """
    config_dir = tmp_path / "corrupt_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    corrupt_file = config_dir / "user_preferences.json"
    corrupt_file.write_text("{\n  \"theme\": \"light\",\n  BROKEN_UNTERMINATED_SYNTAX", encoding="utf-8")

    test_mgr = PreferencesManager(config_dir=str(config_dir))
    monkeypatch.setattr("modules.common.preferences_manager.preferences_manager", test_mgr)

    api = ScriptAPI()
    prefs = api.get_user_preferences()

    # Must start with defaults cleanly without raising
    assert prefs["theme"] == "dark"
    assert prefs["accessibility"]["motion"] == "system"
    assert prefs["accessibility"]["transparency"] == "system"


def test_parser_reset_preserves_preferences_removes_prefix_scenario_c(tmp_path, monkeypatch):
    """
    Scenario C:
    Parser reset:
      Before: theme=light, motion=reduce, custom prefix exists
      After: theme=light, motion=reduce, custom prefix removed
    """
    config_dir = tmp_path / "scenario_c"
    config_dir.mkdir(parents=True, exist_ok=True)

    test_prefs_mgr = PreferencesManager(config_dir=str(config_dir))
    test_parser_mgr = ParserConfigManager(config_dir=str(config_dir))
    monkeypatch.setattr(sys.modules["modules.common.preferences_manager"], "preferences_manager", test_prefs_mgr)
    monkeypatch.setattr(sys.modules["modules.common.config_manager"], "config_manager", test_parser_mgr)

    api = ScriptAPI()

    # Before: Set theme=light, motion=reduce, and add custom prefix
    api.save_user_preferences({
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "system"}
    })
    cfg = api.get_parser_config()
    cfg["base_subject_prefixes"].append("SCENARIOC")
    api.save_parser_config(cfg)

    # Verify precondition
    assert api.get_user_preferences()["theme"] == "light"
    assert api.get_user_preferences()["accessibility"]["motion"] == "reduce"
    assert "SCENARIOC" in api.get_parser_config()["base_subject_prefixes"]

    # Action: Reset parser configuration
    api.reset_parser_config()

    # After: theme=light, motion=reduce preserved; custom prefix removed
    post_prefs = api.get_user_preferences()
    assert post_prefs["theme"] == "light"
    assert post_prefs["accessibility"]["motion"] == "reduce"
    assert "SCENARIOC" not in api.get_parser_config()["base_subject_prefixes"]


def test_user_preference_reset_preserves_parser_config_scenario_d(tmp_path, monkeypatch):
    """
    Scenario D:
    User preference reset:
      Before: theme=light, motion=full, custom prefix exists
      After: theme=dark, motion=system, parser configuration untouched
    """
    config_dir = tmp_path / "scenario_d"
    config_dir.mkdir(parents=True, exist_ok=True)

    test_prefs_mgr = PreferencesManager(config_dir=str(config_dir))
    test_parser_mgr = ParserConfigManager(config_dir=str(config_dir))
    monkeypatch.setattr(sys.modules["modules.common.preferences_manager"], "preferences_manager", test_prefs_mgr)
    monkeypatch.setattr(sys.modules["modules.common.config_manager"], "config_manager", test_parser_mgr)

    api = ScriptAPI()

    # Before: Set theme=light, motion=full, and add custom prefix
    api.save_user_preferences({
        "theme": "light",
        "accessibility": {"motion": "full", "transparency": "glass"}
    })
    cfg = api.get_parser_config()
    cfg["base_subject_prefixes"].append("SCENARIOD")
    api.save_parser_config(cfg)

    # Verify precondition
    assert api.get_user_preferences()["theme"] == "light"
    assert api.get_user_preferences()["accessibility"]["motion"] == "full"
    assert "SCENARIOD" in api.get_parser_config()["base_subject_prefixes"]

    # Action: Reset user preferences
    api.reset_user_preferences()

    # After: theme=dark, motion=system; parser configuration completely untouched
    post_prefs = api.get_user_preferences()
    assert post_prefs["theme"] == "dark"
    assert post_prefs["accessibility"]["motion"] == "system"
    assert post_prefs["accessibility"]["transparency"] == "system"
    assert "SCENARIOD" in api.get_parser_config()["base_subject_prefixes"]


# ── 5. Finalized Persistence Contract Tests (Commit 205) ─────────────────────

def test_export_preferences_produces_exact_canonical_schema_without_metadata(tmp_path):
    """
    Issue A:
    Exported user preferences must strictly match the canonical schema.
    _persisted and diagnostic metadata must NEVER be exported or written to disk.
    """
    mgr = PreferencesManager(config_dir=str(tmp_path))
    mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })

    # 1. Verify get_preferences() is pure canonical
    active = mgr.get_preferences()
    assert "_persisted" not in active
    assert set(active.keys()) == {"version", "theme", "accessibility"}
    assert set(active["accessibility"].keys()) == {"motion", "transparency"}

    # 2. Verify get_preferences_with_metadata() includes metadata
    meta_prefs = mgr.get_preferences_with_metadata()
    assert meta_prefs.get("_persisted") is True

    # 3. Export to file and inspect raw JSON on disk
    export_path = str(tmp_path / "exported_canonical.json")
    res = mgr.export_preferences(export_path)
    assert res["status"] == "success"

    with open(export_path, "r", encoding="utf-8") as f:
        exported = json.load(f)

    assert "_persisted" not in exported
    assert exported == {
        "version": "1.0",
        "theme": "light",
        "accessibility": {
            "motion": "reduce",
            "transparency": "glass"
        }
    }

    # 4. Verify disk store itself also has zero _persisted
    with open(mgr.preferences_file, "r", encoding="utf-8") as f:
        disk_content = json.load(f)
    assert "_persisted" not in disk_content


def test_save_preferences_enforces_complete_document_contract(tmp_path):
    """
    Issue B:
    save_preferences() represents a complete validated document replacement.
    Partial documents missing required fields must be explicitly rejected.
    """
    mgr = PreferencesManager(config_dir=str(tmp_path))

    # Reject missing accessibility
    err1 = mgr.save_preferences({"theme": "light"})
    assert err1["status"] == "error"
    assert "Incomplete preferences document" in err1["message"]

    # Reject missing accessibility.transparency
    err2 = mgr.save_preferences({
        "theme": "light",
        "accessibility": {"motion": "reduce"}
    })
    assert err2["status"] == "error"
    assert "Incomplete preferences document" in err2["message"]

    # Reject non-dict payload
    err3 = mgr.save_preferences(["not", "a", "dict"])
    assert err3["status"] == "error"


def test_update_preferences_merges_partial_update_correctly(tmp_path):
    """
    Issue B:
    update_preferences() is the explicit contract for partial updates,
    merging onto active preferences without destroying sibling fields.
    """
    mgr = PreferencesManager(config_dir=str(tmp_path))

    # Initial state is default dark / system / system
    assert mgr.get_preferences()["theme"] == "dark"

    # 1. Update only theme
    up1 = mgr.update_preferences({"theme": "light"})
    assert up1["status"] == "success"
    p1 = mgr.get_preferences()
    assert p1["theme"] == "light"
    assert p1["accessibility"]["motion"] == "system"
    assert p1["accessibility"]["transparency"] == "system"

    # 2. Update only motion
    up2 = mgr.update_preferences({"accessibility": {"motion": "reduce"}})
    assert up2["status"] == "success"
    p2 = mgr.get_preferences()
    assert p2["theme"] == "light"
    assert p2["accessibility"]["motion"] == "reduce"
    assert p2["accessibility"]["transparency"] == "system"

    # 3. Update only transparency
    up3 = mgr.update_preferences({"accessibility": {"transparency": "glass"}})
    assert up3["status"] == "success"
    p3 = mgr.get_preferences()
    assert p3["theme"] == "light"
    assert p3["accessibility"]["motion"] == "reduce"
    assert p3["accessibility"]["transparency"] == "glass"

    # 4. Update combined theme and motion
    up4 = mgr.update_preferences({"theme": "dark", "accessibility": {"motion": "full"}})
    assert up4["status"] == "success"
    p4 = mgr.get_preferences()
    assert p4["theme"] == "dark"
    assert p4["accessibility"]["motion"] == "full"
    assert p4["accessibility"]["transparency"] == "glass"

    # 5. Invalid partial update (non-dict)
    up_inv = mgr.update_preferences("not a dict")
    assert up_inv["status"] == "error"

    # 6. Verify canonical disk file after operations
    with open(mgr.preferences_file, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data == p4


def test_concurrent_partial_updates_do_not_lose_independent_fields(tmp_path):
    """
    Phase 2:
    update_preferences() must be a serialized read-modify-write transaction under self._lock.
    Concurrent partial updates from separate threads targeting independent fields
    (theme, accessibility.motion, accessibility.transparency) must NOT overwrite or lose each other.
    """
    mgr = PreferencesManager(config_dir=str(tmp_path))
    barrier = threading.Barrier(3)
    results = {}
    errors = []

    def update_theme():
        try:
            barrier.wait()
            results["theme"] = mgr.update_preferences({"theme": "light"})
        except Exception as e:
            errors.append(f"theme error: {e}")

    def update_motion():
        try:
            barrier.wait()
            results["motion"] = mgr.update_preferences({"accessibility": {"motion": "reduce"}})
        except Exception as e:
            errors.append(f"motion error: {e}")

    def update_transparency():
        try:
            barrier.wait()
            results["transparency"] = mgr.update_preferences({"accessibility": {"transparency": "glass"}})
        except Exception as e:
            errors.append(f"transparency error: {e}")

    threads = [
        threading.Thread(target=update_theme),
        threading.Thread(target=update_motion),
        threading.Thread(target=update_transparency),
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert not errors, f"Encountered concurrency worker errors: {errors}"
    assert results["theme"]["status"] == "success"
    assert results["motion"]["status"] == "success"
    assert results["transparency"]["status"] == "success"

    # Final in-memory state must retain all three independent fields
    final_prefs = mgr.get_preferences()
    assert final_prefs["theme"] == "light"
    assert final_prefs["accessibility"]["motion"] == "reduce"
    assert final_prefs["accessibility"]["transparency"] == "glass"

    # Final disk state on a fresh manager must also retain all three independent fields
    reloaded_mgr = PreferencesManager(config_dir=str(tmp_path))
    reloaded_prefs = reloaded_mgr.get_preferences()
    assert reloaded_prefs["theme"] == "light"
    assert reloaded_prefs["accessibility"]["motion"] == "reduce"
    assert reloaded_prefs["accessibility"]["transparency"] == "glass"


def test_schema_version_handling():
    """
    Phase 6:
    Schema version handling policy:
    - missing version -> current supported schema (1.0), theme and accessibility preserved.
    - exact supported version (1.0) -> version 1.0, theme and accessibility preserved.
    - unsupported/future version (2.0, 2.5-beta) -> safe canonical defaults.
    - invalid type (list, dict) -> safe canonical defaults.
    """
    # 1. Missing version: assumes supported schema version, preserves valid fields
    p_missing = validate_preferences({
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert p_missing["version"] == "1.0"
    assert p_missing["theme"] == "light"
    assert p_missing["accessibility"]["motion"] == "reduce"
    assert p_missing["accessibility"]["transparency"] == "glass"

    # 2. Exact current supported version "1.0"
    p_valid = validate_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert p_valid["version"] == "1.0"
    assert p_valid["theme"] == "light"

    # 3. Unsupported future version "2.0": conservative fallback to safe canonical defaults
    p_v2 = validate_preferences({
        "version": "2.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert p_v2["version"] == "1.0"
    assert p_v2["theme"] == "dark"
    assert p_v2["accessibility"]["motion"] == "system"
    assert p_v2["accessibility"]["transparency"] == "system"

    # 4. Future beta version "2.5-beta": conservative fallback to safe canonical defaults
    p_beta = validate_preferences({
        "version": "2.5-beta",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert p_beta["version"] == "1.0"
    assert p_beta["theme"] == "dark"
    assert p_beta["accessibility"]["motion"] == "system"

    # 5. Invalid type for version: list or dict
    p_invalid_type_list = validate_preferences({
        "version": [1, 0],
        "theme": "light"
    })
    assert p_invalid_type_list["version"] == "1.0"
    assert p_invalid_type_list["theme"] == "dark"

    p_invalid_type_dict = validate_preferences({
        "version": {"major": 1, "minor": 0},
        "theme": "light"
    })
    assert p_invalid_type_dict["version"] == "1.0"
    assert p_invalid_type_dict["theme"] == "dark"


def test_import_strips_unknown_metadata(tmp_path):
    """
    Issue H & Phase 9:
    Importing preferences containing unknown metadata or _persisted
    must safely normalize them away without corrupting durable state.
    """
    mgr = PreferencesManager(config_dir=str(tmp_path))
    dirty_import_path = str(tmp_path / "dirty_import.json")

    dirty_payload = {
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "full", "transparency": "glass"},
        "_persisted": True,
        "phantom_field": "corrupt",
        "internal_token": 12345
    }
    with open(dirty_import_path, "w", encoding="utf-8") as f:
        json.dump(dirty_payload, f)

    res = mgr.import_preferences(dirty_import_path)
    assert res["status"] == "success"

    imported = mgr.get_preferences()
    assert imported["theme"] == "light"
    assert imported["accessibility"]["motion"] == "full"
    assert imported["accessibility"]["transparency"] == "glass"
    assert "_persisted" not in imported
    assert "phantom_field" not in imported
    assert "internal_token" not in imported


def test_listener_defensive_copies_and_exception_safety(tmp_path):
    """
    Phase 3:
    Listeners receive independent defensive copies of the canonical preference document.
    Mutating a listener payload cannot mutate manager state or affect other listeners.
    Listener exceptions must be caught and isolated without interrupting persistence.
    """
    mgr = PreferencesManager(config_dir=str(tmp_path))
    listener_a_payloads = []
    listener_b_payloads = []

    def failing_listener(prefs):
        raise RuntimeError("Listener exploded!")

    def mutating_listener_a(prefs):
        # Mutate the received dictionary directly
        prefs["theme"] = "mutated_by_listener_a"
        prefs["tampered"] = True
        prefs["accessibility"]["motion"] = "mutated_motion"
        listener_a_payloads.append(deepcopy(prefs))

    def observer_listener_b(prefs):
        listener_b_payloads.append(deepcopy(prefs))

    mgr.register_listener(failing_listener)
    mgr.register_listener(mutating_listener_a)
    mgr.register_listener(observer_listener_b)

    # Save preferences - must succeed despite failing_listener
    res = mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert res["status"] == "success"

    # 1. Verify mutating_listener_a received notification and modified its copy
    assert len(listener_a_payloads) == 1
    assert listener_a_payloads[0]["theme"] == "mutated_by_listener_a"
    assert listener_a_payloads[0]["tampered"] is True

    # 2. Verify observer_listener_b received an unaffected canonical copy
    assert len(listener_b_payloads) == 1
    assert listener_b_payloads[0]["theme"] == "light"
    assert listener_b_payloads[0]["accessibility"]["motion"] == "reduce"
    assert listener_b_payloads[0]["accessibility"]["transparency"] == "glass"
    assert "tampered" not in listener_b_payloads[0]

    # 3. Verify manager's internal cached preferences were NOT mutated
    cached = mgr.get_preferences()
    assert cached["theme"] == "light"
    assert cached["accessibility"]["motion"] == "reduce"
    assert cached["accessibility"]["transparency"] == "glass"
    assert "tampered" not in cached


def test_reset_lifecycle_prevents_stale_local_storage_resurrection(tmp_path):
    """
    Phase 10:
    Reset user preferences removes disk file and leaves memory in factory defaults.
    Subsequent cold boot starts with defaults without resurrecting deleted preferences.
    """
    config_dir = tmp_path / "reset_test"
    mgr1 = PreferencesManager(config_dir=str(config_dir))

    # 1. User had custom settings
    mgr1.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert os.path.exists(mgr1.preferences_file)

    # 2. User clicks Reset User Preferences
    reset_res = mgr1.reset_preferences()
    assert reset_res["status"] == "success"
    assert not os.path.exists(mgr1.preferences_file)

    # 3. Simulate process termination and cold restart
    mgr2 = PreferencesManager(config_dir=str(config_dir))
    fresh = mgr2.get_preferences()
    assert fresh["theme"] == "dark"
    assert fresh["accessibility"]["motion"] == "system"
    assert fresh["accessibility"]["transparency"] == "system"
    assert mgr2.has_persisted_file() is False


def test_disk_store_state_distinction_missing_valid_corrupt(tmp_path):
    """
    Phase 5 / Forensic:
    Explicitly proves that the system distinguishes between:
      1. Missing disk store
      2. Valid disk store
      3. Corrupt disk store
    """
    config_dir = tmp_path / "state_distinction"
    mgr = PreferencesManager(config_dir=str(config_dir))

    # 1. Missing disk store
    assert not os.path.exists(mgr.preferences_file)
    assert mgr.has_persisted_file() is False
    meta_missing = mgr.get_preferences_with_metadata()
    assert meta_missing["_persisted"] is False
    assert meta_missing["theme"] == "dark"

    # 2. Valid disk store
    mgr.save_preferences({
        "version": "1.0",
        "theme": "light",
        "accessibility": {"motion": "reduce", "transparency": "glass"}
    })
    assert os.path.exists(mgr.preferences_file)
    assert mgr.has_persisted_file() is True
    meta_valid = mgr.get_preferences_with_metadata()
    assert meta_valid["_persisted"] is True
    assert meta_valid["theme"] == "light"

    # 3. Corrupt disk store (file physically exists on disk, but content is corrupt)
    with open(mgr.preferences_file, "w", encoding="utf-8") as f:
        f.write("{ INVALID_JSON_DATA_CORRUPTED: [ }")

    # Reload from disk
    reloaded = mgr.load_preferences()
    assert os.path.exists(mgr.preferences_file)
    assert mgr.has_persisted_file() is True, "Physical file still exists"
    meta_corrupt = mgr.get_preferences_with_metadata()
    assert meta_corrupt["_persisted"] is True, "_persisted metadata reflects physical file presence"
    assert meta_corrupt["theme"] == "dark", "Corrupt disk store deterministically falls back to defaults"
    assert meta_corrupt["accessibility"]["motion"] == "system"
    assert meta_corrupt["accessibility"]["transparency"] == "system"
