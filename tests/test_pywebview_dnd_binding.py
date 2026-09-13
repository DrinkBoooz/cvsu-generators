import os
import sys
import webview
from webview.dom import _dnd_state

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from executable_test.main import ScriptAPI, setup_window_drag_and_drop

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
