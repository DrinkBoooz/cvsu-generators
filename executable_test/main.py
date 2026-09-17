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
    "_setup_diagnostics",
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
    """
    Activates non-perturbing telemetry listeners when CVSU_DIAGNOSTIC_MODE=1 is set.
    Uses an in-memory deque buffer and background flusher thread.
    Callbacks perform ZERO synchronous file I/O and ZERO JSON serialization.
    """
    try:
        import datetime
        import json
        import threading
        import time
        from collections import deque

        diag_dir = Path(os.environ.get('TEMP', os.path.expanduser('~'))) / 'cvsu_diagnostics'
        diag_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = diag_dir / f"cvsu_exe_diag_{ts}.jsonl"

        event_buffer = deque()
        buffer_lock = threading.Lock()
        stop_event = threading.Event()

        # Initial startup record
        event_buffer.append({
            "event": "diagnostic_init",
            "timestamp": time.time(),
            "document_url": doc_url
        })

        def on_request(request):
            """Strictly read-only, non-mutating callback with zero synchronous I/O."""
            t = time.time()
            url = str(getattr(request, "url", request))
            method = str(getattr(request, "method", "GET"))
            with buffer_lock:
                event_buffer.append({
                    "event": "request_sent",
                    "timestamp": t,
                    "url": url,
                    "method": method
                })

        def on_response(response):
            """Strictly read-only callback accepting one Response object with zero synchronous I/O."""
            t = time.time()
            url = str(getattr(response, "url", response))
            status_code = getattr(response, "status_code", None)
            with buffer_lock:
                event_buffer.append({
                    "event": "response_received",
                    "timestamp": t,
                    "url": url,
                    "status_code": status_code
                })

        def flush_worker():
            """Asynchronously flushes buffered records to the diagnostic JSONL session file."""
            while not stop_event.is_set():
                items_to_write = []
                with buffer_lock:
                    while event_buffer:
                        items_to_write.append(event_buffer.popleft())
                if items_to_write:
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            for item in items_to_write:
                                f.write(json.dumps(item) + "\n")
                    except Exception:
                        pass
                stop_event.wait(0.2)

            # Final drain upon window close / stop
            items_to_write = []
            with buffer_lock:
                while event_buffer:
                    items_to_write.append(event_buffer.popleft())
            if items_to_write:
                try:
                    with open(log_path, "a", encoding="utf-8") as f:
                        for item in items_to_write:
                            f.write(json.dumps(item) + "\n")
                except Exception:
                    pass

        flusher = threading.Thread(target=flush_worker, daemon=True, name="CvSUDiagnosticFlusher")
        flusher.start()

        def on_closed():
            stop_event.set()
            flusher.join(timeout=1.0)

        window.events.request_sent += on_request
        window.events.response_received += on_response
        window.events.closed += on_closed

        # Store state object for inspection and unit testing
        window._diag_state = {
            "buffer": event_buffer,
            "lock": buffer_lock,
            "stop_event": stop_event,
            "log_path": log_path,
            "on_request": on_request,
            "on_response": on_response,
            "flusher": flusher
        }
        return window._diag_state
    except Exception:
        return None

if __name__ == '__main__':
    app_window, app_api = create_app()
    webview.start(setup_window_drag_and_drop, (app_window, app_api))
