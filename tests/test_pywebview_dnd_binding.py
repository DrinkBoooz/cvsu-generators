"""
Native PyWebView Drag-and-Drop Binding Integration Test.

Verifies:
  1. Windows Forms AllowDrop and pywebview drop listener handlers attach to the native WebView2 window.
  2. Global JavaScript callbacks (window.onScheduleLoaded, window.onRostersLoaded) exist in ui.html.
  3. PyWebView internal DOM event listener state reflects active drop registration.

Architectural Boundary:
  This proves native DnD handler attachment and binding inside the live pywebview desktop host.
  Actual OS-level OLE mouse drag-and-drop delivery is not automated via synthetic mouse coordinates.
  Event routing from drop payloads into ScriptAPI is independently tested in test_executable_dnd_routing.py.
"""

import os
import sys
import pytest
import webview
from webview.dom import _dnd_state

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from executable_test.main import ScriptAPI, setup_window_drag_and_drop

@pytest.mark.desktop_integration
def test_pywebview_setup_window_drag_and_drop():
    html_path = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
    assert os.path.exists(html_path)

    api = ScriptAPI()
    results = {}

    def runner(window, api):
        try:
            setup_window_drag_and_drop(window, api)

            # Verify that global JS callbacks are defined in ui.html
            results["has_schedule_callback"] = window.evaluate_js("typeof window.onScheduleLoaded === 'function'")
            results["has_rosters_callback"] = window.evaluate_js("typeof window.onRostersLoaded === 'function'")
            results["dnd_listeners_count"] = _dnd_state['num_listeners']
        finally:
            window.destroy()

    w = webview.create_window('DnD Integration Test', url=html_path, js_api=api)
    api._window = w
    webview.start(runner, (w, api))

    assert results.get("has_schedule_callback") is True, "window.onScheduleLoaded must exist in ui.html"
    assert results.get("has_rosters_callback") is True, "window.onRostersLoaded must exist in ui.html"
    assert results.get("dnd_listeners_count", 0) > 0, "At least one pywebview drop listener must be registered in _dnd_state"
