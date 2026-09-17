"""
CvSU Document Automation Suite — Desktop Executable Entrypoint.
Initializes the pywebview desktop container with the modular ScriptAPI and native OLE Drag-and-Drop.
"""

import os
import sys
from pathlib import Path

# Ensure repository root and package directory are on sys.path
if getattr(sys, 'frozen', False):
    CURR_DIR = sys._MEIPASS
    if CURR_DIR not in sys.path:
        sys.path.insert(0, CURR_DIR)
else:
    CURR_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(CURR_DIR)
    for p in (CURR_DIR, REPO_ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)

import webview

try:
    from .api import ScriptAPI, get_resource_path, sanitize_filename
    from .native import setup_window_drag_and_drop
except (ImportError, ValueError):
    from api import ScriptAPI, get_resource_path, sanitize_filename
    from native import setup_window_drag_and_drop

__all__ = [
    "ScriptAPI",
    "get_resource_path",
    "setup_window_drag_and_drop",
    "sanitize_filename",
    "create_app",
    "main",
]

def create_app():
    """Initializes ScriptAPI and creates the pywebview main application window."""
    api = ScriptAPI()
    html_template = get_resource_path('ui.html')
    document_url = Path(html_template).resolve().as_uri()

    window = webview.create_window(
        title='CvSU Gen',
        url=document_url,
        js_api=api,
        width=1120,
        height=780,
        min_size=(880, 640),
        text_select=True
    )
    api._window = window

    def on_window_closing():
        api._is_window_closed = True
        api.cancel_generation()

    def on_window_closed():
        api._is_window_closed = True

    window.events.closing += on_window_closing
    window.events.closed += on_window_closed

    if os.environ.get('CVSU_DIAGNOSTIC_MODE') == '1':
        _setup_diagnostics(window, document_url)

    return window, api

def _setup_diagnostics(window, doc_url):
    """Activates non-perturbing telemetry listeners when CVSU_DIAGNOSTIC_MODE=1 is set."""
    try:
        import datetime
        import json
        diag_dir = Path(os.environ.get('TEMP', os.path.expanduser('~'))) / 'cvsu_diagnostics'
        diag_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = diag_dir / f"cvsu_exe_diag_{ts}.jsonl"

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "diagnostic_init", "document_url": doc_url}) + "\n")

        def on_request(req):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"event": "request_sent", "url": getattr(req, "url", str(req))}) + "\n")
            except Exception:
                pass

        def on_response(req, resp):
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"event": "response_received", "url": getattr(req, "url", str(req)), "status": getattr(resp, "status", None)}) + "\n")
            except Exception:
                pass

        window.events.request_sent += on_request
        window.events.response_received += on_response
    except Exception:
        pass

if __name__ == '__main__':
    app_window, app_api = create_app()
    webview.start(setup_window_drag_and_drop, (app_window, app_api))
