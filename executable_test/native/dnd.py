import os
import json
import process_schedule

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
        process_schedule.logger.debug(f"WinForms AllowDrop setup: {e}")

    # 2. Bind DOM Drag and Drop handlers to capture pywebviewFullPath
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
                for f in files:
                    full_path = f.get('pywebviewFullPath')
                    if full_path and os.path.exists(full_path):
                        ext = os.path.splitext(full_path)[1].lower()
                        if ext == '.docx':
                            res = api.inspect_custom_template(full_path)
                            window.evaluate_js(f"if (window.renderCustomTemplateInspection) window.renderCustomTemplateInspection({json.dumps(res)});")
                            break
            except Exception as err:
                process_schedule.logger.error(f"Error handling template drop: {err}")

        def on_schedule_drop(e):
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return
                for f in files:
                    full_path = f.get('pywebviewFullPath')
                    if full_path and os.path.exists(full_path):
                        ext = os.path.splitext(full_path)[1].lower()
                        if ext in ('.xls', '.xlsx', '.xlsm'):
                            res = api.handle_dropped_schedule(os.path.basename(full_path), original_path=full_path)
                            window.evaluate_js(f"if (window.onScheduleLoaded) window.onScheduleLoaded({json.dumps(res)});")
                            break
            except Exception as err:
                process_schedule.logger.error(f"Error handling schedule drop: {err}")

        def on_rosters_drop(e):
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return
                payloads = []
                for f in files:
                    full_path = f.get('pywebviewFullPath')
                    if full_path and os.path.exists(full_path):
                        base = os.path.basename(full_path)
                        ext = os.path.splitext(base)[1].lower()
                        if not base.startswith('~$') and ext in ('.xlsx', '.xls', '.csv'):
                            payloads.append({
                                'filename': base,
                                'path': full_path,
                                'data': None
                            })
                if payloads:
                    res = api.handle_dropped_rosters(payloads)
                    window.evaluate_js(f"if (window.onRostersLoaded) window.onRostersLoaded({json.dumps(res)});")
            except Exception as err:
                process_schedule.logger.error(f"Error handling rosters drop: {err}")

        def on_doc_drop(e):
            try:
                files = e.get('dataTransfer', {}).get('files', [])
                if not files:
                    return

                excel_schedules = []
                roster_items = []
                for f in files:
                    full_path = f.get('pywebviewFullPath')
                    if not full_path or not os.path.exists(full_path):
                        continue
                    base = os.path.basename(full_path)
                    ext = os.path.splitext(base)[1].lower()
                    if base.startswith('~$'):
                        continue
                    if ext in ('.xls', '.xlsx', '.xlsm'):
                        meta = process_schedule.inspect_schedule_file(full_path)
                        if meta and meta.get('total_slots', 0) > 0 and (not api.schedule_path or 'List of Students' not in base):
                            excel_schedules.append((base, full_path))
                        else:
                            roster_items.append({'filename': base, 'path': full_path, 'data': None})
                    elif ext == '.csv':
                        roster_items.append({'filename': base, 'path': full_path, 'data': None})

                if excel_schedules and not api.schedule_path:
                    base, path = excel_schedules[0]
                    res = api.handle_dropped_schedule(base, original_path=path)
                    window.evaluate_js(f"if (window.onScheduleLoaded) window.onScheduleLoaded({json.dumps(res)});")
                    for b, p in excel_schedules[1:]:
                        roster_items.append({'filename': b, 'path': p, 'data': None})

                if roster_items:
                    res = api.handle_dropped_rosters(roster_items)
                    window.evaluate_js(f"if (window.onRostersLoaded) window.onRostersLoaded({json.dumps(res)});")
            except Exception as err:
                process_schedule.logger.error(f"Error handling document drop: {err}")

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
        process_schedule.logger.error(f"Error binding pywebview DOM handlers: {e}")
