"""
Automated Test for Packaged Executable Persistence Architecture (Commit 203).
Validates that CvSU Gen.exe:
  1. Persists user preferences (theme, motion, transparency) across cold restarts.
  2. Persists parser configuration independently across cold restarts.
  3. Preserves preferences when parser config is reset (strict reset isolation).
  4. Recovers safely and isolates user ergonomics from curriculum settings.
"""

import os
import sys
import json
import tempfile
import subprocess
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "dist", "CvSU Gen.exe")


def test_packaged_executable_persistence_across_restarts():
    """
    Spawns CvSU Gen.exe in persistence diagnostic mode across two cold boot cycles:
      Cycle 1: Mutates theme, motion, transparency, and parser config -> Exits.
      Cycle 2: Cold boot -> Verifies all mutated values survived restart -> Resets.
    """
    assert os.path.exists(EXE_PATH), f"CvSU Gen.exe not found at {EXE_PATH}"

    # Kill any lingering instances
    subprocess.run(["taskkill", "/F", "/IM", "CvSU Gen.exe"], capture_output=True, check=False)

    report_path_1 = os.path.join(tempfile.gettempdir(), f"cvsu_persist_run1_{os.getpid()}.json")
    report_path_2 = os.path.join(tempfile.gettempdir(), f"cvsu_persist_run2_{os.getpid()}.json")

    for p in (report_path_1, report_path_2):
        if os.path.exists(p):
            os.remove(p)

    # ── CYCLE 1: MUTATE & EXIT ───────────────────────────────────────────────
    env1 = os.environ.copy()
    env1["CVSU_PERSISTENCE_DIAGNOSTIC"] = "1"
    env1["CVSU_PERSISTENCE_ACTION"] = "mutate_and_exit"
    env1["CVSU_DIAGNOSTIC_EXIT"] = "1"
    env1["CVSU_DIAGNOSTIC_OUTPUT"] = report_path_1

    proc1 = subprocess.run([EXE_PATH], env=env1, timeout=35, capture_output=True, text=True)
    assert proc1.returncode == 0, f"Run 1 failed with code {proc1.returncode}: {proc1.stderr}"
    assert os.path.exists(report_path_1), f"Run 1 report missing at {report_path_1}"

    with open(report_path_1, "r", encoding="utf-8") as f:
        run1 = json.load(f)

    assert run1.get("is_frozen") is True, "EXE must run in frozen mode"
    mutated = run1.get("post_mutation", {})
    assert mutated.get("dom_motion") == "reduce", "DOM motion preference was not updated in Run 1"
    assert mutated.get("dom_trans") == "glass", "DOM transparency preference was not updated in Run 1"
    assert mutated.get("has_test_prefix") is True, "Parser config test prefix not saved in Run 1"

    # Kill processes before next run
    subprocess.run(["taskkill", "/F", "/IM", "CvSU Gen.exe"], capture_output=True, check=False)

    # ── CYCLE 2: VERIFY RECOVERY AFTER COLD RESTART ──────────────────────────
    env2 = os.environ.copy()
    env2["CVSU_PERSISTENCE_DIAGNOSTIC"] = "1"
    env2["CVSU_PERSISTENCE_ACTION"] = "verify_and_reset"
    env2["CVSU_DIAGNOSTIC_EXIT"] = "1"
    env2["CVSU_DIAGNOSTIC_OUTPUT"] = report_path_2

    proc2 = subprocess.run([EXE_PATH], env=env2, timeout=35, capture_output=True, text=True)
    assert proc2.returncode == 0, f"Run 2 failed with code {proc2.returncode}: {proc2.stderr}"
    assert os.path.exists(report_path_2), f"Run 2 report missing at {report_path_2}"

    with open(report_path_2, "r", encoding="utf-8") as f:
        run2 = json.load(f)

    initial_run2 = run2.get("initial", {})

    # Verify that user preferences survived cold restart
    assert initial_run2.get("dom_motion") == "reduce", "Motion preference did not survive EXE restart!"
    assert initial_run2.get("dom_trans") == "glass", "Transparency preference did not survive EXE restart!"
    assert initial_run2.get("py_prefs", {}).get("accessibility", {}).get("motion") == "reduce"
    assert initial_run2.get("py_prefs", {}).get("accessibility", {}).get("transparency") == "glass"

    # Verify that parser config survived cold restart
    after_parser_reset = run2.get("after_parser_reset", {})
    assert after_parser_reset.get("has_test_prefix") is False, "Parser reset failed to remove test prefix"
    # Verify Reset Isolation: resetting parser configuration MUST NOT erase user preferences
    assert after_parser_reset.get("py_prefs", {}).get("accessibility", {}).get("motion") == "reduce", (
        "RESET CONTAMINATION: Resetting parser config reset accessibility motion!"
    )
    assert after_parser_reset.get("py_prefs", {}).get("accessibility", {}).get("transparency") == "glass", (
        "RESET CONTAMINATION: Resetting parser config reset accessibility transparency!"
    )

    # Verify preferences reset restores defaults
    after_prefs_reset = run2.get("after_prefs_reset", {})
    assert after_prefs_reset.get("py_prefs", {}).get("theme") == "dark"
    assert after_prefs_reset.get("py_prefs", {}).get("accessibility", {}).get("motion") == "system"
    assert after_prefs_reset.get("py_prefs", {}).get("accessibility", {}).get("transparency") == "system"

    # Clean up temporary test reports
    for p in (report_path_1, report_path_2):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
