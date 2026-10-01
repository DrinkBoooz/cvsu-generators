"""
Automated Test for Packaged Executable Theme Transition Diagnostics (Commit 200).
Validates that CvSU Gen.exe executes natively with EdgeChromium / WebView2,
supports document.startViewTransition and WAAPI pseudoElement ::view-transition-new(root),
and diagnoses the exact cause of runtime theme behavior in the Windows environment.
"""

import os
import sys
import json
import tempfile
import subprocess
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "dist", "CvSU Gen.exe")


def test_packaged_executable_theme_runtime_diagnosis():
    """
    Spawns CvSU Gen.exe in diagnostic mode, collects telemetry directly from
    the frozen WebView2 runtime container, and verifies all diagnostic criteria.
    """
    assert os.path.exists(EXE_PATH), f"CvSU Gen.exe not found at {EXE_PATH}"

    # Pre-clean lingering processes to prevent file locking
    subprocess.run(["taskkill", "/F", "/IM", "CvSU Gen.exe"], capture_output=True, check=False)

    report_path = os.path.join(tempfile.gettempdir(), f"test_cvsu_diag_{os.getpid()}.json")
    if os.path.exists(report_path):
        os.remove(report_path)

    env = os.environ.copy()
    env["CVSU_THEME_DIAGNOSTIC"] = "1"
    env["CVSU_DIAGNOSTIC_EXIT"] = "1"
    env["CVSU_DIAGNOSTIC_OUTPUT"] = report_path

    # Launch the packaged executable
    proc = subprocess.run([EXE_PATH], env=env, timeout=30, capture_output=True, text=True)
    assert proc.returncode == 0, f"CvSU Gen.exe exited with non-zero code {proc.returncode}"
    assert os.path.exists(report_path), f"Diagnostic report not generated at {report_path}"

    with open(report_path, "r", encoding="utf-8") as f:
        diag = json.load(f)

    # 1. Verify frozen packaged state
    assert diag.get("is_frozen") is True, "EXE must run in frozen mode"
    assert "CvSU Gen" in diag.get("url", "") or "ui.html" in diag.get("url", "")

    # 2. Verify Renderer Selection (Part 4)
    assert diag.get("renderer") == "edgechromium", f"Renderer must be edgechromium, got {diag.get('renderer')}"

    # 3. Verify Browser and WebView2 Versions (Part 5 & 6)
    assert "Edg/" in diag.get("userAgent", ""), "User-Agent must identify Edge/Chromium"
    wv2_version = diag.get("webview2_runtime_version")
    assert wv2_version is not None, "WebView2 runtime version must be detected"

    # 4. Verify API Availability (Part 5)
    assert diag.get("hasStartViewTransition") is True, "document.startViewTransition must be available"
    assert diag.get("hasElementAnimate") is True, "Element.prototype.animate must be available"
    assert diag.get("supportsVTName") is True, "view-transition-name: root must be supported"
    assert diag.get("supportsClipPath") is True, "circle clip-path must be supported"

    # 5. Verify Controlled Transition Promise Lifecycle (Part 7, 9, 10)
    ct = diag.get("controlled_transition")
    assert ct is not None, "Controlled transition diagnostics must be present"
    assert ct.get("transitionCreated") is True, "View Transition object must be created"
    assert ct.get("updateCallbackDone", {}).get("resolved") is True, "updateCallbackDone must resolve"
    assert ct.get("ready", {}).get("resolved") is True, "ready promise must resolve"
    assert ct.get("finished", {}).get("resolved") is True, "finished promise must resolve"

    # 6. Verify WAAPI on pseudo-element (Part 9)
    waapi = ct.get("waapi", {})
    assert waapi.get("created") is True, "WAAPI animation must be created on ::view-transition-new(root)"
    assert waapi.get("errorName") is None, f"WAAPI animate threw error: {waapi.get('errorName')}"
    assert waapi.get("playState") in ("running", "finished"), f"WAAPI playState unexpected: {waapi.get('playState')}"

    # 7. Expose Root Cause: prefers-reduced-motion status
    # The actual OS on this system has Animation effects disabled, which sets prefersReducedMotion to True.
    assert "natural_toggle" in diag
    assert diag["natural_toggle"]["theme"] == "light"

    # 7b. Verify Distinct Top-Level Telemetry Keys (Commit 202)
    assert "storedMotionPreference" in diag
    assert "effectiveMotionPreference" in diag
    assert "storedTransparencyPreference" in diag
    assert "effectiveTransparencyPreference" in diag
    assert "systemReducedMotion" in diag
    assert "systemReducedTransparency" in diag
    assert diag["storedMotionPreference"] in ("system", "reduce", "full")
    assert diag["effectiveMotionPreference"] in ("reduce", "no-preference")
    assert diag["storedTransparencyPreference"] in ("system", "reduce", "glass")
    assert diag["effectiveTransparencyPreference"] in ("reduce", "glass")

    # 8. Verify Accessibility Settings in Packaged DOM & Runtime (Commit 201)
    a11y_ui = diag.get("accessibility_ui", {})
    assert a11y_ui.get("hasTab") is True, "Packaged EXE must include cfgTabAccessibility button"
    assert a11y_ui.get("hasPane") is True, "Packaged EXE must include cfgPaneAccessibility pane"
    assert a11y_ui.get("hasMotionSelect") is True, "Packaged EXE must include accMotionSelect control"
    assert a11y_ui.get("hasTransparencySelect") is True, "Packaged EXE must include accTransparencySelect control"
    assert a11y_ui.get("dataAccMotion") in ("reduce", "no-preference")
    assert a11y_ui.get("dataAccTransparency") in ("reduce", "glass")

    # 9. Verify App-Level Override in Packaged Runtime
    assert "app_override_full_motion_toggle" in diag
    override = diag["app_override_full_motion_toggle"]
    assert override.get("effective_motion") == "no-preference", "Setting app motion to full must set effective motion to no-preference"
    assert override["theme"] == "dark", f"App override toggle must switch to dark, got {override['theme']}"

    # 10. Verify Bypassed Reduced Motion Toggle
    assert "bypassed_reduced_motion_toggle" in diag
    assert diag["bypassed_reduced_motion_toggle"]["theme"] == "light", f"Bypassed toggle must switch to light, got {diag['bypassed_reduced_motion_toggle']['theme']}"

    # Cleanup report file
    try:
        os.remove(report_path)
    except Exception:
        pass
