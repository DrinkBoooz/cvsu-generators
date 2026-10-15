"""
Native Windows OLE Drag-and-Drop integration for CvSU Document Generator.

Part E Hardening:
  * A per-session drop-deduplication set (with time-bucketed keys) prevents the
    same physical file from being processed twice when both the specific zone
    handler AND the document-level fallback handler fire for the same drop event.
  * All window.evaluate_js calls are guarded via _safe_evaluate_js to avoid
    races during window teardown.
  * os.path.isfile() guards reject directories before passing to API handlers.
  * A threading.Lock protects the dedup set from concurrent access.

The document-level on_doc_drop fires for drops that land outside a specific
zone. Zone-specific handlers have stopPropagation=True (the third arg to
DOMEventHandler), which in pywebview prevents the event reaching the document
handler for zone-targeted drops on most WebView2 builds. The dedup set provides
an additional safety net regardless of bubbling behaviour.
"""

import os
import json
import time
import threading
from modules.common.logger import logger
from modules.parsers.schedule_parser import inspect_schedule_file


# ---------------------------------------------------------------------------
# Module-level safe evaluate_js (mirrors generation.py helper — kept local to
# avoid circular imports between the native and api packages).
# ---------------------------------------------------------------------------

def _safe_evaluate_js(window, js_code: str, *, window_state: str = "OPEN",
                      context: str = "") -> bool:
    """Lifecycle-aware evaluate_js — returns False and logs on any failure."""
    if window_state in ("CLOSING", "CLOSED"):
        return False
    if window is None:
        return False
    try:
        window.evaluate_js(js_code)
        return True
    except Exception as e:
        logger.debug(
            f"dnd: evaluate_js suppressed ({context}): {type(e).__name__}: {e}"
        )
        return False


def setup_window_drag_and_drop(window, api):
    """
    Initializes native Windows Forms AllowDrop and binds pywebview DOMEventHandler
    listeners to handle file drag-and-drop seamlessly in Microsoft Edge WebView2.
    """
    try:
        window.events.loaded.wait(10)
    except Exception:
        pass

    # 1. Enable Windows Forms AllowDrop on the UI thread for native OLE support
    try:
        import clr
        clr.AddReference('System.Windows.Forms')
        import System.Windows.Forms as WinForms

        def _enable_native_dnd():
            if window.native:
                window.native.AllowDrop = True
                browser = getattr(window.native, 'browser', None)
                wv = getattr(browser, 'webview', None)
                if wv:
                    wv.AllowDrop = True

        if window.native:
            window.native.Invoke(WinForms.MethodInvoker(_enable_native_dnd))
    except Exception as e:
        logger.debug(f"WinForms AllowDrop setup: {e}")

    # 2. Per-session drop deduplication (Part E)
    #    Key = frozenset of file paths + time bucket (500 ms window).
    _dedup_lock = threading.Lock()
    _seen_drops: set = set()

    def _make_dedup_key(paths: list) -> tuple:
        bucket = int(time.monotonic() * 2)  # 500 ms buckets
        return (frozenset(paths), bucket)

    def _is_duplicate_drop(paths: list) -> bool:
        """Returns True if this exact set of paths was already processed within 500 ms."""
        if not paths:
            return False
        key = _make_dedup_key(paths)
        with _dedup_lock:
            if key in _seen_drops:
                return True
            _seen_drops.add(key)
        return False

    def _get_window_state() -> str:
        return getattr(api, "_window_state", "OPEN")

    # 3. Bind DOM Drag and Drop handlers to capture pywebviewFullPath
    try:
        from webview.dom import DOMEventHandler

        sched_zone = window.dom.get_element('#scheduleDropzone')
        rosters_zone = window.dom.get_element('#rostersDropzone')
        template_zone = window.dom.get_element('#templateDropzone')
        doc = window.dom.document

        def on_drag_ignore(e):
            pass

        def on_template_drop(e):
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return
                paths = [
                    f.get('pywebviewFullPath') for f in files
                    if f.get('pywebviewFullPath') and os.path.isfile(f.get('pywebviewFullPath'))
                ]
                if not paths or _is_duplicate_drop(paths):
                    return
                for full_path in paths:
                    ext = os.path.splitext(full_path)[1].lower()
                    if ext == '.docx':
                        res = api.inspect_custom_template(full_path)
                        _safe_evaluate_js(
                            window,
                            f"if (window.renderCustomTemplateInspection) window.renderCustomTemplateInspection({json.dumps(res)});",
                            window_state=_get_window_state(),
                            context="template_drop"
                        )
                        break
            except Exception as err:
                logger.error(f"Error handling template drop: {err}")

        def on_schedule_drop(e):
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return
                paths = [
                    f.get('pywebviewFullPath') for f in files
                    if f.get('pywebviewFullPath') and os.path.isfile(f.get('pywebviewFullPath'))
                ]
                if not paths or _is_duplicate_drop(paths):
                    return
                for full_path in paths:
                    ext = os.path.splitext(full_path)[1].lower()
                    if ext in ('.xls', '.xlsx', '.xlsm'):
                        # Emit diagnostic milestone
                        try:
                            emit = getattr(window, "_diag_emit", None)
                            if callable(emit):
                                emit("dnd_event_received", handler="schedule_drop", path=full_path)
                        except Exception:
                            pass
                        res = api.handle_dropped_schedule(os.path.basename(full_path), original_path=full_path)
                        _safe_evaluate_js(
                            window,
                            f"if (window.onScheduleLoaded) window.onScheduleLoaded({json.dumps(res)});",
                            window_state=_get_window_state(),
                            context="schedule_drop"
                        )
                        break
            except Exception as err:
                logger.error(f"Error handling schedule drop: {err}")

        def on_rosters_drop(e):
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return
                payloads = []
                raw_paths = []
                for f in files:
                    full_path = f.get('pywebviewFullPath')
                    if not full_path or not os.path.isfile(full_path):
                        continue
                    base = os.path.basename(full_path)
                    ext = os.path.splitext(base)[1].lower()
                    if not base.startswith('~$') and ext in ('.xlsx', '.xls', '.csv'):
                        raw_paths.append(full_path)
                        payloads.append({
                            'filename': base,
                            'path': full_path,
                            'data': None
                        })
                if not payloads or _is_duplicate_drop(raw_paths):
                    return
                # Emit diagnostic milestone
                try:
                    emit = getattr(window, "_diag_emit", None)
                    if callable(emit):
                        emit("dnd_event_received", handler="rosters_drop", count=len(payloads))
                except Exception:
                    pass
                res = api.handle_dropped_rosters(payloads)
                _safe_evaluate_js(
                    window,
                    f"if (window.onRostersLoaded) window.onRostersLoaded({json.dumps(res)});",
                    window_state=_get_window_state(),
                    context="rosters_drop"
                )
            except Exception as err:
                logger.error(f"Error handling rosters drop: {err}")

        def on_doc_drop(e):
            """
            Document-level fallback handler for drops that land outside a specific zone.
            Zone handlers have stopPropagation=True, so in well-behaved WebView2 builds
            zone drops do NOT reach here. The dedup set prevents double-processing on
            builds where propagation is not reliably stopped.
            """
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return

                excel_schedules = []
                roster_items = []
                all_paths = []
                for f in files:
                    full_path = f.get('pywebviewFullPath')
                    if not full_path or not os.path.isfile(full_path):
                        continue
                    base = os.path.basename(full_path)
                    ext = os.path.splitext(base)[1].lower()
                    if base.startswith('~$'):
                        continue
                    all_paths.append(full_path)
                    if ext in ('.xls', '.xlsx', '.xlsm'):
                        meta = inspect_schedule_file(full_path)
                        if meta and meta.get('total_slots', 0) > 0 and (not api.schedule_path or 'List of Students' not in base):
                            excel_schedules.append((base, full_path))
                        else:
                            roster_items.append({'filename': base, 'path': full_path, 'data': None})
                    elif ext == '.csv':
                        roster_items.append({'filename': base, 'path': full_path, 'data': None})

                if not all_paths or _is_duplicate_drop(all_paths):
                    return

                # Emit diagnostic milestone
                try:
                    emit = getattr(window, "_diag_emit", None)
                    if callable(emit):
                        emit("dnd_event_received", handler="doc_drop",
                             schedules=len(excel_schedules), rosters=len(roster_items))
                except Exception:
                    pass

                if excel_schedules and not api.schedule_path:
                    base, path = excel_schedules[0]
                    res = api.handle_dropped_schedule(base, original_path=path)
                    _safe_evaluate_js(
                        window,
                        f"if (window.onScheduleLoaded) window.onScheduleLoaded({json.dumps(res)});",
                        window_state=_get_window_state(),
                        context="doc_drop_schedule"
                    )
                    for b, p in excel_schedules[1:]:
                        roster_items.append({'filename': b, 'path': p, 'data': None})

                if roster_items:
                    res = api.handle_dropped_rosters(roster_items)
                    _safe_evaluate_js(
                        window,
                        f"if (window.onRostersLoaded) window.onRostersLoaded({json.dumps(res)});",
                        window_state=_get_window_state(),
                        context="doc_drop_rosters"
                    )
            except Exception as err:
                logger.error(f"Error handling document drop: {err}")

        if sched_zone:
            sched_zone.events.dragenter += DOMEventHandler(on_drag_ignore, True, True)
            sched_zone.events.dragover += DOMEventHandler(on_drag_ignore, True, True, debounce=200)
            sched_zone.events.drop += DOMEventHandler(on_schedule_drop, True, True)

        if rosters_zone:
            rosters_zone.events.dragenter += DOMEventHandler(on_drag_ignore, True, True)
            rosters_zone.events.dragover += DOMEventHandler(on_drag_ignore, True, True, debounce=200)
            rosters_zone.events.drop += DOMEventHandler(on_rosters_drop, True, True)

        if template_zone:
            template_zone.events.dragenter += DOMEventHandler(on_drag_ignore, True, True)
            template_zone.events.dragover += DOMEventHandler(on_drag_ignore, True, True, debounce=200)
            template_zone.events.drop += DOMEventHandler(on_template_drop, True, True)

        if doc:
            doc.events.dragover += DOMEventHandler(on_drag_ignore, True, True, debounce=500)
            doc.events.drop += DOMEventHandler(on_doc_drop, True, True)

    except Exception as e:
        logger.error(f"Error binding pywebview DOM handlers: {e}")
