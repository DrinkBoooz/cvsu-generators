"""
CvSU Document Automation Suite — Desktop Executable Entrypoint.
Initializes the pywebview desktop container with the modular ScriptAPI and native OLE Drag-and-Drop.
"""

import os
import sys
from pathlib import Path

# ── Crash hooks must be installed BEFORE any other import so that import-time
#    errors are captured in the log files.
# ── In windowed/frozen mode sys.stderr is None; without this, unhandled
#    exceptions in startup code are completely silent.
if not ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ):
    try:
        # Ensure repository root / _MEIPASS on path first so the import works
        if getattr(sys, "frozen", False):
            _boot_dir = sys._MEIPASS
        else:
            _boot_dir = os.path.dirname(os.path.abspath(__file__))
            _repo_root = os.path.dirname(_boot_dir)
            for _p in (_boot_dir, _repo_root):
                if _p not in sys.path:
                    sys.path.insert(0, _p)
        from modules.common.logger import install_global_hooks
        install_global_hooks()
    except Exception:
        pass  # Hooks couldn't be installed — proceed; at least pywebview will log to console

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

    # ── Window Lifecycle State (Part B)
    # Transitions: OPEN → CLOSING → CLOSED
    # No new evaluate_js/WebView operation may start once CLOSING begins.
    def on_window_closing():
        """
        Fired synchronously on the UI thread before the window is destroyed.
        Transitions state to CLOSING so that in-flight workers stop dispatching
        to the WebView before the COM object is torn down.
        """
        api._window_state = "CLOSING"
        api._is_window_closed = True   # legacy bool kept for backwards compat
        api.cancel_generation()

    def on_window_closed():
        """
        Fired after the window has been destroyed.
        Transitions state to CLOSED — any attempt to call evaluate_js is now a bug.
        """
        api._window_state = "CLOSED"
        api._is_window_closed = True   # legacy bool kept for backwards compat

    # Set initial lifecycle state
    api._window_state = "OPEN"

    window.events.closing += on_window_closing
    window.events.closed += on_window_closed

    if os.environ.get('CVSU_DIAGNOSTIC_MODE') == '1':
        _setup_diagnostics(window, document_url, api)

    return window, api

def _setup_diagnostics(window, doc_url, api=None):
    """
    Activates non-perturbing telemetry listeners when CVSU_DIAGNOSTIC_MODE=1 is set.
    Uses an in-memory deque buffer and background flusher thread.
    Callbacks perform ZERO synchronous file I/O and ZERO JSON serialization.

    Part H — records all required lifecycle milestones.
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

        def _emit(event_name: str, **kwargs):
            """Zero-I/O, zero-serialization emit into the ring buffer."""
            entry = {"event": event_name, "timestamp": time.time()}
            entry.update(kwargs)
            with buffer_lock:
                event_buffer.append(entry)

        # Part H milestone: startup
        _emit("startup",
              document_url=doc_url,
              pid=os.getpid(),
              frozen=getattr(sys, "frozen", False),
              python_version=sys.version)

        def on_loaded():
            _emit("webview_initialized")

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

        def on_closing_diag():
            _emit("window_closing",
                  window_state=getattr(api, "_window_state", "unknown") if api else "unknown")

        def on_closed():
            _emit("window_closed")
            stop_event.set()
            flusher.join(timeout=1.0)

        _ev = window.events
        if hasattr(_ev, "loaded"):
            _ev.loaded += on_loaded
        if hasattr(_ev, "request_sent"):
            _ev.request_sent += on_request
        if hasattr(_ev, "response_received"):
            _ev.response_received += on_response
        if hasattr(_ev, "closing"):
            _ev.closing += on_closing_diag
        if hasattr(_ev, "closed"):
            _ev.closed += on_closed

        # Expose emit function so generation.py can log milestones
        window._diag_emit = _emit

        # Store state object for inspection and unit testing
        window._diag_state = {
            "buffer": event_buffer,
            "lock": buffer_lock,
            "stop_event": stop_event,
            "log_path": log_path,
            "on_request": on_request,
            "on_response": on_response,
            "flusher": flusher,
            "emit": _emit,
        }
        return window._diag_state
    except Exception:
        return None

if __name__ == '__main__':
    app_window, app_api = create_app()
    webview.start(setup_window_drag_and_drop, (app_window, app_api))
