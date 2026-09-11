import webview
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process_schedule
import roster_parser

import threading
import json
import tempfile
import base64

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class ScriptAPI:
    def __init__(self):
        self._window = None
        self.schedule_path = ""
        self.output_dir = ""
        self.rosters = []
        self.roster_configs = {}
        self._is_processing = False
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

    def cancel_generation(self):
        with self._lock:
            if self._is_processing and self._cancel_event:
                self._cancel_event.set()
                process_schedule.logger.info("User requested generation cancellation.")
                return {"status": "success", "message": "Cancellation requested."}
        return {"status": "error", "message": "No active generation to cancel."}

    def browse_schedule(self):
        file_types = ('Excel files (*.xls;*.xlsx;*.xlsm)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            self.schedule_path = result[0]
            metadata = process_schedule.inspect_schedule_file(self.schedule_path)
            validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
            return {
                "path": self.schedule_path,
                "metadata": metadata,
                "validation": validation
            }
        return {"path": self.schedule_path, "metadata": None, "validation": []}

    def inspect_schedule(self, path=None):
        target = path or self.schedule_path
        if not target:
            return None
        return process_schedule.inspect_schedule_file(target)

    def handle_dropped_schedule(self, filename, base64_data=None, original_path=None):
        target_path = None
        if original_path and os.path.exists(original_path):
            target_path = original_path
        elif base64_data and filename:
            cache_dir = os.path.join(tempfile.gettempdir(), "cvsu_cache", "schedules")
            os.makedirs(cache_dir, exist_ok=True)
            target_path = os.path.join(cache_dir, filename)
            try:
                with open(target_path, "wb") as f:
                    f.write(base64.b64decode(base64_data))
            except Exception as e:
                process_schedule.logger.error(f"Failed to write dropped schedule {filename}: {e}")
                return {"path": "", "metadata": None, "validation": []}

        if target_path and os.path.exists(target_path):
            self.schedule_path = target_path
            metadata = process_schedule.inspect_schedule_file(self.schedule_path)
            validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
            return {
                "path": self.schedule_path,
                "metadata": metadata,
                "validation": validation
            }
        return {"path": "", "metadata": None, "validation": []}

    def browse_rosters(self, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        file_types = ('Student Lists (*.csv;*.xlsx;*.xls)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types
        )
        if result:
            # Merge while avoiding duplicate file paths
            existing = set(self.rosters)
            for r in result:
                if r not in existing:
                    self.rosters.append(r)
            validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            return {
                "count": len(self.rosters),
                "rosters": self.rosters,
                "validation": validation
            }
        return {
            "count": len(self.rosters),
            "rosters": self.rosters,
            "validation": process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
        }

    def handle_dropped_rosters(self, files_payload, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        cache_dir = os.path.join(tempfile.gettempdir(), "cvsu_cache", "rosters")
        os.makedirs(cache_dir, exist_ok=True)

        new_paths = []
        for item in files_payload:
            original_path = item.get("path")
            base64_data = item.get("data")
            filename = item.get("filename")

            if original_path and os.path.exists(original_path):
                new_paths.append(original_path)
            elif base64_data and filename:
                target_path = os.path.join(cache_dir, filename)
                try:
                    with open(target_path, "wb") as f:
                        f.write(base64.b64decode(base64_data))
                    new_paths.append(target_path)
                except Exception as e:
                    process_schedule.logger.error(f"Failed to write dropped roster {filename}: {e}")

        existing = set(self.rosters)
        for p in new_paths:
            if p not in existing:
                self.rosters.append(p)
                existing.add(p)

        validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
        return {
            "count": len(self.rosters),
            "rosters": self.rosters,
            "validation": validation
        }

    def remove_roster(self, path_or_index, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        if isinstance(path_or_index, int) and 0 <= path_or_index < len(self.rosters):
            self.rosters.pop(path_or_index)
        elif path_or_index in self.rosters:
            self.rosters.remove(path_or_index)
        return {
            "count": len(self.rosters),
            "rosters": self.rosters,
            "validation": process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
        }

    def clear_rosters(self):
        self.rosters = []
        return {"count": 0, "rosters": [], "validation": []}

    def validate_rosters(self, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        if not self.rosters:
            return []
        return process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)

    def inspect_roster(self, path_or_filename, overrides=None):
        target_path = None
        for r in self.rosters:
            if r == path_or_filename or os.path.basename(r) == path_or_filename:
                target_path = r
                break
        if not target_path and os.path.exists(path_or_filename):
            target_path = path_or_filename
        if not target_path:
            return {"status": "error", "message": f"File not found: {path_or_filename}"}
        return roster_parser.inspect_roster(target_path, overrides=overrides)

    def get_ceit_prefix_directory(self):
        from modules.common.config_manager import config_manager
        return config_manager.get_ceit_prefix_map()

    def get_parser_config(self):
        from modules.common.config_manager import config_manager
        return config_manager.get_config()

    def save_parser_config(self, config_dict):
        from modules.common.config_manager import config_manager
        res = config_manager.save_config(config_dict)
        validation = []
        detected_classes = []
        if self.rosters:
            try:
                validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                process_schedule.logger.error(f"Error re-validating rosters: {e}")
        if self.schedule_path and self.rosters:
            try:
                detected_classes = process_schedule.detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                process_schedule.logger.error(f"Error re-detecting classes: {e}")
        res["validation"] = validation
        res["detected_classes"] = detected_classes
        return res

    def reset_parser_config(self):
        from modules.common.config_manager import config_manager
        res = config_manager.reset_to_defaults()
        validation = []
        detected_classes = []
        if self.rosters:
            try:
                validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                process_schedule.logger.error(f"Error re-validating rosters: {e}")
        if self.schedule_path and self.rosters:
            try:
                detected_classes = process_schedule.detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                process_schedule.logger.error(f"Error re-detecting classes: {e}")
        res["validation"] = validation
        res["detected_classes"] = detected_classes
        return res

    def export_parser_config(self):
        if not self._window:
            return {"status": "error", "message": "Window context unavailable"}
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="cvsu_parser_config.json",
            file_types=('JSON files (*.json)', 'All files (*.*)')
        )
        if result:
            save_path = result if isinstance(result, str) else result[0]
            from modules.common.config_manager import config_manager
            return config_manager.export_config(save_path)
        return {"status": "cancelled"}

    def import_parser_config(self):
        if not self._window:
            return {"status": "error", "message": "Window context unavailable"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('JSON files (*.json)', 'All files (*.*)')
        )
        if result and len(result) > 0:
            import_path = result[0]
            from modules.common.config_manager import config_manager
            res = config_manager.import_config(import_path)
            validation = []
            detected_classes = []
            if self.rosters:
                try:
                    validation = process_schedule.validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
                except Exception as e:
                    process_schedule.logger.error(f"Error re-validating rosters: {e}")
            if self.schedule_path and self.rosters:
                try:
                    detected_classes = process_schedule.detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
                except Exception as e:
                    process_schedule.logger.error(f"Error re-detecting classes: {e}")
            res["validation"] = validation
            res["detected_classes"] = detected_classes
            return res
        return {"status": "cancelled"}

    def browse_custom_template(self):
        """File browser dialog for selecting a .docx template to inspect."""
        if not self._window:
            return {"status": "error", "message": "Window context unavailable"}
        file_types = ('Word Documents (*.docx)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            target_path = result[0]
            return self.inspect_custom_template(target_path)
        return {"status": "cancelled"}

    def handle_dropped_custom_template(self, filename, base64_data=None, original_path=None):
        """Handles drag-and-drop of a .docx template."""
        target_path = None
        if original_path and os.path.exists(original_path):
            target_path = original_path
        elif base64_data and filename:
            cache_dir = os.path.join(tempfile.gettempdir(), "cvsu_cache", "custom_templates")
            os.makedirs(cache_dir, exist_ok=True)
            target_path = os.path.join(cache_dir, filename)
            try:
                with open(target_path, "wb") as f:
                    f.write(base64.b64decode(base64_data))
            except Exception as e:
                process_schedule.logger.error(f"Failed to write dropped template {filename}: {e}")
                return {"status": "error", "message": str(e)}

        if target_path and os.path.exists(target_path):
            return self.inspect_custom_template(target_path)
        return {"status": "error", "message": "Target template file could not be resolved"}

    def inspect_custom_template(self, file_path):
        """Runs the deterministic heuristic inspector on the provided .docx template."""
        try:
            from modules.parsers.template_inspector import TemplateInspector
            inspector = TemplateInspector()
            recipe = inspector.inspect_docx(file_path)
            return {
                "status": "success",
                "file_path": file_path,
                "recipe": recipe
            }
        except Exception as e:
            process_schedule.logger.error(f"Failed to inspect custom template {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def save_custom_template(self, file_path, title, suffix, recipe):
        """Saves a custom template and registers its recipe in ParserConfigManager."""
        try:
            from modules.common.config_manager import config_manager
            res = config_manager.save_custom_template(file_path, title, suffix, recipe)
            return res
        except Exception as e:
            process_schedule.logger.error(f"Failed to save custom template: {e}")
            return {"status": "error", "message": str(e)}

    def get_custom_templates(self):
        """Retrieves list of active custom templates."""
        try:
            from modules.common.config_manager import config_manager
            return config_manager.get_custom_templates()
        except Exception as e:
            process_schedule.logger.error(f"Failed to get custom templates: {e}")
            return []

    def toggle_custom_template(self, template_id, enabled):
        """Toggles a custom template's enabled state."""
        try:
            from modules.common.config_manager import config_manager
            return config_manager.toggle_custom_template(template_id, enabled)
        except Exception as e:
            process_schedule.logger.error(f"Failed to toggle custom template: {e}")
            return {"status": "error", "message": str(e)}

    def delete_custom_template(self, template_id):
        """Deletes a custom template and its file."""
        try:
            from modules.common.config_manager import config_manager
            return config_manager.delete_custom_template(template_id)
        except Exception as e:
            process_schedule.logger.error(f"Failed to delete custom template: {e}")
            return {"status": "error", "message": str(e)}

    def browse_output(self):
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG
        )
        if result and len(result) > 0:
            self.output_dir = result[0]
        return self.output_dir

    def open_output_folder(self, folder_path=None):
        target = folder_path or self.output_dir
        if target and os.path.exists(target):
            try:
                os.startfile(target)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Directory does not exist"}

    def open_file(self, file_path):
        if file_path and os.path.exists(file_path):
            try:
                os.startfile(file_path)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "File not found"}

    def get_recent_logs(self, lines=120):
        app_data = os.getenv('APPDATA') or os.path.expanduser("~")
        log_file = os.path.join(app_data, "CVSU_Generators", "logs", "generator.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    return "".join(all_lines[-lines:])
            except Exception as e:
                return f"Could not read log file: {e}"
        return "No log entries found."

    def open_log_folder(self):
        app_data = os.getenv('APPDATA') or os.path.expanduser("~")
        log_dir = os.path.join(app_data, "CVSU_Generators", "logs")
        if os.path.exists(log_dir):
            try:
                os.startfile(log_dir)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Logs directory does not exist"}

    def detect_classes(self, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        if not self.schedule_path or not self.rosters:
            return []
        try:
            return process_schedule.detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
        except Exception as e:
            process_schedule.logger.error(f"Error in detect_classes: {e}")
            return []

    def run_generation(self, type_overrides=None, date_overrides=None, class_filter=None, engine_filter=None, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        with self._lock:
            if self._is_processing:
                return {"status": "error", "message": "A generation task is already in progress."}
            self._is_processing = True

        if not self.schedule_path:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Instructor Schedule. Please attach your Master Schedule .xls context."}
        if not self.rosters:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Student Rosters. Please attach the student list files."}
        if not self.output_dir:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Output Directory. Operations cannot resolve without an endpoint."}
        
        try:
            process_schedule.logger.info("Commencing Build Initialization with real-time telemetry...")
            process_schedule.logger.info(f"Loaded Schedule: {self.schedule_path}")
            process_schedule.logger.info(f"Loaded Rosters: {len(self.rosters)} file(s)")
            process_schedule.logger.info(f"Target Output Directory: {self.output_dir}")
            process_schedule.logger.info(f"Selected Engines: {engine_filter}")
            self._cancel_event.clear()

            def _progress_hook(info):
                try:
                    js_code = f"if (window.onGenerationProgress) window.onGenerationProgress({json.dumps(info)});"
                    self._window.evaluate_js(js_code)
                except Exception as pe:
                    process_schedule.logger.debug(f"Telemetry evaluate error: {pe}")

            def _thread_target():
                try:
                    results = process_schedule.process_all(
                        self.schedule_path,
                        self.rosters,
                        self.output_dir,
                        type_overrides=type_overrides,
                        date_overrides=date_overrides,
                        class_filter=class_filter,
                        engine_filter=engine_filter,
                        progress_callback=_progress_hook,
                        cancel_event=self._cancel_event,
                        roster_configs=self.roster_configs
                    )
                    
                    gen = results["generated"]
                    skp = results["skipped"]
                    err = results["errors"]
                    
                    total_generated = len(gen["attendance"]) + len(gen["grades"]) + len(gen["ceit"])
                    total_skipped = len(skp["attendance"]) + len(skp["grades"]) + len(skp["ceit"]) + len(skp["rosters"])
                    total_errors = len(err["attendance"]) + len(err["grades"]) + len(err["ceit"]) + len(err["rosters"])
                    
                    if results.get("cancelled"):
                        process_schedule.logger.info(
                            f"Build cancelled by user. {total_generated} file(s) generated."
                        )
                        payload = {
                            "status": "cancelled",
                            "message": f"Generation stopped by user. {total_generated} file(s) were generated.",
                            "stats": {
                                "generated": total_generated,
                                "errors": total_errors,
                                "skipped": total_skipped
                            },
                            "details": results,
                            "output_dir": self.output_dir
                        }
                    elif total_generated == 0:
                        process_schedule.logger.warning(
                            f"Build completed: 0 files generated (Skipped: {total_skipped}, Errors: {total_errors})."
                        )
                        payload = {
                            "status": "error",
                            "message": f"Generation blocked: 0 files generated. Skipped: {total_skipped}. Errors: {total_errors}.",
                            "details": results,
                            "output_dir": self.output_dir
                        }
                    else:
                        process_schedule.logger.info(
                            f"Build completed successfully! {total_generated} file(s) generated (CEIT: {len(gen['ceit'])}, Attendance: {len(gen['attendance'])}, Grades: {len(gen['grades'])})."
                        )
                        payload = {
                            "status": "success",
                            "message": f"Generation complete! {total_generated} files generated successfully.",
                            "stats": {
                                "generated": total_generated,
                                "errors": total_errors,
                                "skipped": total_skipped
                            },
                            "details": results,
                            "output_dir": self.output_dir
                        }
                except Exception as e:
                    process_schedule.logger.error(f"Error Pipeline Breakdown: {e}", exc_info=True)
                    payload = {"status": "error", "message": f"Fatal Generation Fault: {str(e)}", "details": None}
                finally:
                    with self._lock:
                        self._is_processing = False
                
                try:
                    js_code = f"if (window.onGenerationComplete) window.onGenerationComplete({json.dumps(payload)});"
                    self._window.evaluate_js(js_code)
                except Exception as e:
                    process_schedule.logger.error(f"Failed to execute UI callback: {e}")
                    try:
                        self._window.evaluate_js("if (window.onGenerationError) window.onGenerationError();")
                    except Exception:
                        pass

            threading.Thread(target=_thread_target, daemon=True).start()
            return None
            
        except Exception as e:
            with self._lock:
                self._is_processing = False
            process_schedule.logger.error(f"Error starting thread: {e}")
            return {"status": "error", "message": f"Failed to start generation thread: {str(e)}"}


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
        doc = window.dom.document

        def on_drag_ignore(e):
            pass

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

        if doc:
            doc.events.dragover += DOMEventHandler(on_drag_ignore, True, True, debounce=500)
            doc.events.drop += DOMEventHandler(on_doc_drop, True, True)

    except Exception as e:
        process_schedule.logger.error(f"Error binding pywebview DOM handlers: {e}")


if __name__ == '__main__':
    api = ScriptAPI()
    
    html_template = get_resource_path('ui.html')
    
    window = webview.create_window(
        title='CvSU Gen (Beta)',
        url=html_template,
        js_api=api,
        width=1120,
        height=780,
        min_size=(880, 640),
        text_select=True
    )
    api._window = window
    
    webview.start(setup_window_drag_and_drop, (window, api))

