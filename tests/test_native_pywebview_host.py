"""
Native PyWebView Host Integration & Smoke Test Suite.

Exercises the real native Windows PyWebView container and WebView2 host:
  1. Real `create_app()` from `executable_test.main`.
  2. Real `webview.start(...)` desktop event loop.
  3. Real WebView2 initialization and `file:///` DOM bootstrap.
  4. Real two-way Python <-> JavaScript native bridge IPC.
  5. Real Drag-and-Drop listener binding.
  6. Clean native window destruction and lifecycle state transition to CLOSED.

Note:
  This test exercises the NATIVE DESKTOP HOST (pywebview/WebView2),
  which is distinct from Playwright browser-hosted bridge tests.
"""

import os
import sys
import pytest
import webview
from pathlib import Path

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from executable_test.main import create_app, setup_window_drag_and_drop
from webview.dom import _dnd_state


@pytest.mark.desktop_integration
def test_native_pywebview_host_lifecycle():
    """
    Launch native PyWebView window via create_app(), evaluate DOM state and
    bidirectional API bridge, verify DnD binding, and trigger clean shutdown.
    """
    results = {}
    errors = []

    def runner(window, api):
        try:
            # 1. Window properties
            results["title"] = getattr(window, "title", None)
            results["initial_state"] = getattr(api, "_window_state", None)

            # 2. Native DOM execution & app initialization verification
            results["protocol"] = window.evaluate_js("window.location.protocol")
            results["app_initialized"] = window.evaluate_js("window.__app_initialized__")
            results["has_pywebview"] = window.evaluate_js("typeof window.pywebview === 'object'")
            results["has_pywebview_api"] = window.evaluate_js(
                "typeof window.pywebview === 'object' && typeof window.pywebview.api === 'object'"
            )

            # 3. Two-way bridge call into real Python ScriptAPI from inside WebView2
            results["has_get_parser_config"] = window.evaluate_js("typeof window.pywebview.api.get_parser_config === 'function'")
            results["has_get_template_sets"] = window.evaluate_js("typeof window.pywebview.api.get_template_sets === 'function'")
            results["has_run_generation"] = window.evaluate_js("typeof window.pywebview.api.run_generation === 'function'")

            # Execute real JS -> Python ScriptAPI -> JS Promise resolution round trip
            window.evaluate_js("""
                window.__bridge_roundtrip_done = false;
                window.__bridge_roundtrip_err = null;
                window.__bridge_roundtrip_res = null;

                window.pywebview.api.get_parser_config().then(cfg => {
                    window.__bridge_roundtrip_res = cfg;
                    window.__bridge_roundtrip_done = true;
                }).catch(err => {
                    window.__bridge_roundtrip_err = String(err);
                    window.__bridge_roundtrip_done = true;
                });
            """)

            # Poll for JS promise completion from inside the host
            import time
            for _ in range(40):
                time.sleep(0.05)
                if window.evaluate_js("window.__bridge_roundtrip_done"):
                    break

            results["bridge_done"] = window.evaluate_js("window.__bridge_roundtrip_done")
            results["bridge_err"] = window.evaluate_js("window.__bridge_roundtrip_err")
            results["bridge_has_prefixes"] = window.evaluate_js(
                "Boolean(window.__bridge_roundtrip_res && Array.isArray(window.__bridge_roundtrip_res.base_subject_prefixes))"
            )
            results["bridge_version"] = window.evaluate_js(
                "window.__bridge_roundtrip_res ? window.__bridge_roundtrip_res.version : null"
            )

            # 4. Drag-and-Drop listener registration
            setup_window_drag_and_drop(window, api)
            results["has_schedule_callback"] = window.evaluate_js("typeof window.onScheduleLoaded === 'function'")
            results["has_rosters_callback"] = window.evaluate_js("typeof window.onRostersLoaded === 'function'")
            results["dnd_listeners_count"] = _dnd_state.get("num_listeners", 0)

        except Exception as e:
            errors.append(str(e))
        finally:
            # Clean native host shutdown
            window.destroy()

    app_window, app_api = create_app()
    assert app_window is not None, "create_app() must return a valid webview Window"
    assert app_api is not None, "create_app() must return a valid ScriptAPI instance"

    # Start native pywebview event loop requesting Windows WebView2 (edgechromium) backend
    try:
        webview.start(runner, (app_window, app_api), gui="edgechromium")
    except Exception:
        webview.start(runner, (app_window, app_api))

    # Assert no errors encountered inside the native thread
    assert not errors, f"Native host runner encountered errors: {errors}"

    # Verify native host execution assertions
    assert results.get("title") == "CvSU Gen", f"Expected title 'CvSU Gen', got {results.get('title')}"
    assert results.get("initial_state") == "OPEN", f"Expected initial state 'OPEN', got {results.get('initial_state')}"
    assert results.get("protocol") == "file:", f"Expected protocol 'file:', got {results.get('protocol')}"
    assert results.get("app_initialized") is True, "window.__app_initialized__ must be True in native host"
    assert results.get("has_pywebview") is True, "window.pywebview must exist in native host"
    assert results.get("has_pywebview_api") is True, "window.pywebview.api bridge must exist in native host"
    assert results.get("has_get_parser_config") is True, "window.pywebview.api.get_parser_config must exist in native host"
    assert results.get("has_get_template_sets") is True, "window.pywebview.api.get_template_sets must exist in native host"
    assert results.get("bridge_done") is True, f"Native bridge call timed out. Error: {results.get('bridge_err')}"
    assert results.get("bridge_err") is None, f"Native bridge call raised JS exception: {results.get('bridge_err')}"
    assert results.get("bridge_has_prefixes") is True, "Bridge call returned payload must be verified directly inside JavaScript"
    assert results.get("has_schedule_callback") is True, "window.onScheduleLoaded must exist after DnD setup"
    assert results.get("has_rosters_callback") is True, "window.onRostersLoaded must exist after DnD setup"
    assert results.get("dnd_listeners_count", 0) > 0, "Native DnD listeners must be registered"

    # Verify real Python API output
    py_config = app_api.get_parser_config()
    assert isinstance(py_config, dict), "app_api.get_parser_config() must return dict"
    assert "base_subject_prefixes" in py_config, "app_api config must have base_subject_prefixes"

    # Verify post-destruction lifecycle state
    assert getattr(app_api, "_window_state", None) == "CLOSED", (
        f"Window state must transition to 'CLOSED' after destroy(), got {getattr(app_api, '_window_state', None)}"
    )
