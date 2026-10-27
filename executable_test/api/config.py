import webview
from modules.common.logger import logger
from modules.services.validator import validate_rosters, detect_classes

class ConfigMixin:
    """Mixin handling curriculum and parser configuration operations."""

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
                validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                logger.error(f"Error re-validating rosters: {e}")
        if self.schedule_path and self.rosters:
            try:
                detected_classes = detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                logger.error(f"Error re-detecting classes: {e}")
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
                validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                logger.error(f"Error re-validating rosters: {e}")
        if self.schedule_path and self.rosters:
            try:
                detected_classes = detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            except Exception as e:
                logger.error(f"Error re-detecting classes: {e}")
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
                    validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
                except Exception as e:
                    logger.error(f"Error re-validating rosters: {e}")
            if self.schedule_path and self.rosters:
                try:
                    detected_classes = detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
                except Exception as e:
                    logger.error(f"Error re-detecting classes: {e}")
            res["validation"] = validation
            res["detected_classes"] = detected_classes
            return res
        return {"status": "cancelled"}

    # ── User Preferences Bridge (Theme & Accessibility) ───────────────────────
    def get_user_preferences(self, include_metadata: bool = False):
        from modules.common.preferences_manager import preferences_manager
        if include_metadata:
            return preferences_manager.get_preferences_with_metadata()
        return preferences_manager.get_preferences()

    def save_user_preferences(self, prefs_dict):
        from modules.common.preferences_manager import preferences_manager
        return preferences_manager.save_preferences(prefs_dict)

    def reset_user_preferences(self):
        from modules.common.preferences_manager import preferences_manager
        res = preferences_manager.reset_preferences()
        # Synchronize UI presentation layer and localStorage cache if window is active
        if getattr(self, "_window", None) and not getattr(self, "_is_window_closed", False):
            try:
                js_code = """
                if (typeof window.applyUserPreferencesReset === 'function') {
                    window.applyUserPreferencesReset();
                }
                """
                self._window.evaluate_js(js_code)
            except Exception:
                pass
        return res

    def export_user_preferences(self):
        if not self._window:
            return {"status": "error", "message": "Window context unavailable"}
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename="cvsu_user_preferences.json",
            file_types=('JSON files (*.json)', 'All files (*.*)')
        )
        if result:
            save_path = result if isinstance(result, str) else result[0]
            from modules.common.preferences_manager import preferences_manager
            return preferences_manager.export_preferences(save_path)
        return {"status": "cancelled"}

    def import_user_preferences(self):
        if not self._window:
            return {"status": "error", "message": "Window context unavailable"}
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('JSON files (*.json)', 'All files (*.*)')
        )
        if result and len(result) > 0:
            import_path = result[0]
            from modules.common.preferences_manager import preferences_manager
            return preferences_manager.import_preferences(import_path)
        return {"status": "cancelled"}

    # ── Organizational Topology & Signatory Presets (.cvsu-org.json) ─────────
    def export_org_preset(self, path: str = None, preset_data: dict = None):
        """
        Exports an organizational topology and signatory preset (.cvsu-org.json).
        Enforces strict path validation and schema integrity.
        """
        import os
        import json
        from modules.models.organization import OrganizationPreset

        if path is None:
            if not getattr(self, "_window", None):
                return {"status": "error", "message": "Window context unavailable"}
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="cvsu_organization_preset.cvsu-org.json",
                file_types=('CvSU Organization Preset (*.cvsu-org.json;*.json)', 'All files (*.*)')
            )
            if not result:
                return {"status": "cancelled"}
            path = result if isinstance(result, str) else result[0]

        # Security check: null bytes
        if "\x00" in str(path):
            return {"status": "error", "message": "Invalid characters in path"}

        # Security check: file extension
        lower_path = str(path).lower()
        if not lower_path.endswith(".json") and not lower_path.endswith(".cvsu-org.json"):
            return {"status": "error", "message": "Invalid file extension. Expected .json or .cvsu-org.json"}

        preset_dict = preset_data or {}
        preset_obj = OrganizationPreset.from_dict(preset_dict)
        errors = preset_obj.validate()
        if errors:
            return {"status": "error", "message": "; ".join(errors)}

        try:
            abs_path = os.path.abspath(path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                json.dump(preset_obj.to_dict(), f, indent=2)
            logger.info(f"Exported organization preset to {abs_path}")
            return {"status": "success", "file_path": abs_path}
        except Exception as e:
            logger.error(f"Failed to export organization preset: {e}")
            return {"status": "error", "message": str(e)}

    def import_org_preset(self, path: str = None):
        """
        Imports an organizational topology and signatory preset (.cvsu-org.json).
        Enforces strict path validation and schema integrity.
        """
        import os
        import json
        from modules.models.organization import OrganizationPreset

        if path is None:
            if not getattr(self, "_window", None):
                return {"status": "error", "message": "Window context unavailable"}
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('CvSU Organization Preset (*.cvsu-org.json;*.json)', 'All files (*.*)')
            )
            if not result or len(result) == 0:
                return {"status": "cancelled"}
            path = result[0]

        # Security check: null bytes
        if "\x00" in str(path):
            return {"status": "error", "message": "Invalid characters in path"}

        # Security check: file extension
        lower_path = str(path).lower()
        if not lower_path.endswith(".json") and not lower_path.endswith(".cvsu-org.json"):
            return {"status": "error", "message": "Invalid file extension. Expected .json or .cvsu-org.json"}

        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            return {"status": "error", "message": f"File does not exist: {abs_path}"}

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to parse JSON preset from {abs_path}: {e}")
            return {"status": "error", "message": f"Malformed JSON: {e}"}

        if not isinstance(raw_data, dict):
            return {"status": "error", "message": "Preset data must be a JSON object"}

        preset_obj = OrganizationPreset.from_dict(raw_data)
        errors = preset_obj.validate()
        if errors:
            return {"status": "error", "message": "; ".join(errors)}

        return {"status": "success", "preset": preset_obj.to_dict(), "file_path": abs_path}

    def get_org_preset(self):
        """Retrieves active organizational topology and signatory settings."""
        from modules.common.config_manager import config_manager
        cfg = config_manager.get_config()
        return cfg.get("organization_preset", {
            "version": "1.0",
            "campus": cfg.get("schedule_config", {}).get("default_campus", "Main Campus"),
            "college": cfg.get("schedule_config", {}).get("default_college", "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"),
            "department": "Department of Information Technology",
            "signatories": [
                {
                    "slot_id": "prepared_by",
                    "label": "Prepared by:",
                    "name": cfg.get("schedule_config", {}).get("default_instructor", ""),
                    "title": "Instructor"
                },
                {
                    "slot_id": "reviewed_by",
                    "label": "Reviewed by:",
                    "name": cfg.get("department_chair", ""),
                    "title": "Department Chairperson"
                },
                {
                    "slot_id": "approved_by",
                    "label": "Approved by:",
                    "name": cfg.get("college_dean", ""),
                    "title": "College Dean"
                }
            ]
        })

    def save_org_preset(self, preset_data):
        """Saves active organizational topology and signatory settings."""
        from modules.common.config_manager import config_manager
        from modules.models.organization import OrganizationPreset
        preset_obj = OrganizationPreset.from_dict(preset_data)
        errors = preset_obj.validate()
        if errors:
            return {"status": "error", "message": "; ".join(errors)}

        cfg = config_manager.get_config()
        cfg["organization_preset"] = preset_obj.to_dict()
        for sig in preset_obj.signatories:
            sid = sig.get("slot_id") or ""
            title = (sig.get("title") or "").lower()
            name = sig.get("name") or ""
            if "chair" in sid or "chair" in title or sid in ("reviewed_by", "recommending_approval"):
                cfg["department_chair"] = name
            elif "dean" in sid or "dean" in title or "admin" in title or sid == "approved_by":
                cfg["college_dean"] = name
        return config_manager.save_config(cfg)

    def get_calendar_config(self):
        """Retrieves active academic calendar and holiday suspension configuration."""
        from modules.common.config_manager import config_manager
        from modules.parsers.calendar_resolver import get_default_cavite_recurrence_rules
        cfg = config_manager.get_config()
        cal_cfg = cfg.get("calendar_config")
        if not cal_cfg:
            cal_cfg = {
                "default_mode": "OMIT_COLUMN",
                "rules": [r.to_dict() for r in get_default_cavite_recurrence_rules()],
                "exceptions": [],
                "overrides": {},
            }
        return cal_cfg

    def save_calendar_config(self, calendar_dict):
        """Persists updated calendar configuration."""
        from modules.common.config_manager import config_manager
        if not isinstance(calendar_dict, dict):
            return {"status": "error", "message": "Calendar configuration must be a dictionary"}
        cfg = config_manager.get_config()
        cfg["calendar_config"] = calendar_dict
        return config_manager.save_config(cfg)

    def get_calendar_presets(self):
        """Returns available built-in academic calendar presets."""
        from modules.models.calendar import CALENDAR_PRESETS
        preset_list = []
        for pid, pdata in CALENDAR_PRESETS.items():
            preset_list.append({
                "id": pid,
                "name": pdata.get("name", pid),
                "description": pdata.get("description", ""),
                "count": len(pdata.get("exceptions", [])),
            })
        return {"status": "success", "presets": preset_list}

    def load_calendar_preset(self, preset_id: str):
        """Retrieves exceptions from a designated calendar preset."""
        from modules.models.calendar import CALENDAR_PRESETS
        preset = CALENDAR_PRESETS.get(preset_id)
        if not preset:
            return {"status": "error", "message": f"Preset '{preset_id}' not found"}
        return {
            "status": "success",
            "preset": {
                "id": preset_id,
                "name": preset.get("name", preset_id),
                "description": preset.get("description", ""),
                "exceptions": preset.get("exceptions", []),
            }
        }

    def preview_calendar_dates(self, params):
        """Calculates candidate meeting dates for a schedule and month range."""
        from modules.parsers.calendar_resolver import CalendarResolver
        from modules.common.config_manager import config_manager
        if not isinstance(params, dict):
            return {"status": "error", "message": "Parameters must be a dictionary"}
        year = int(params.get("year", 2026))
        months = params.get("months", [8, 9, 10, 11, 12])
        weekdays = params.get("weekdays", [0])
        start_bound = params.get("start_bound")
        end_bound = params.get("end_bound")
        class_time_range = params.get("class_time_range")

        cal_cfg = params.get("calendar_config") or config_manager.get_config().get("calendar_config")
        resolver = CalendarResolver.from_dict(cal_cfg) if cal_cfg else CalendarResolver()
        dates_preview = resolver.preview_semester_dates(
            year=year,
            months=months,
            weekdays=weekdays,
            start_bound=tuple(start_bound) if start_bound else None,
            end_bound=tuple(end_bound) if end_bound else None,
            class_time_range=class_time_range,
        )
        return {"status": "success", "dates": dates_preview}

    def import_calendar_ics(self, file_path=None):
        """Parses an iCalendar (.ics) file offline into CalendarException objects."""
        import os
        import webview
        from modules.parsers.calendar_resolver import parse_ics_content
        if not file_path:
            if not self._window:
                return {"status": "error", "message": "Window context unavailable"}
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=('iCalendar files (*.ics)', 'All files (*.*)')
            )
            if not result or len(result) == 0:
                return {"status": "cancelled"}
            file_path = result[0]

        if not os.path.isfile(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            exceptions = parse_ics_content(content)
            return {
                "status": "success",
                "count": len(exceptions),
                "file_path": file_path,
                "exceptions": [e.to_dict() for e in exceptions],
            }
        except Exception as e:
            logger.error(f"Failed parsing .ics file {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def parse_calendar_announcement(self, text, default_year=None):
        """Parses natural text or CSV memo lines into CalendarException objects."""
        from modules.parsers.calendar_resolver import parse_announcement_lines
        try:
            exceptions = parse_announcement_lines(text or "", default_year=default_year)
            return {
                "status": "success",
                "count": len(exceptions),
                "exceptions": [e.to_dict() for e in exceptions],
            }
        except Exception as e:
            logger.error(f"Failed parsing announcement text: {e}")
            return {"status": "error", "message": str(e)}

    # ── Named Semester Workspaces (.cvsu-workspace.json) ──────────────────────

    def list_workspaces(self):
        """Returns list of saved semester workspace snapshots."""
        from modules.common.config_manager import config_manager
        return config_manager.list_workspaces()

    def save_workspace(self, name: str, workspace_dict: dict = None):
        """Saves current state or provided dictionary as a named semester workspace snapshot."""
        from modules.common.config_manager import config_manager
        if workspace_dict is None:
            lock = getattr(self, "_lock", None)
            if lock:
                with lock:
                    current_sched = getattr(self, "schedule_path", "")
                    current_rosters = list(getattr(self, "rosters", []))
                    current_roster_configs = dict(getattr(self, "roster_configs", {}))
                    current_output = getattr(self, "output_dir", "")
            else:
                current_sched = getattr(self, "schedule_path", "")
                current_rosters = list(getattr(self, "rosters", []))
                current_roster_configs = dict(getattr(self, "roster_configs", {}))
                current_output = getattr(self, "output_dir", "")

            cfg = config_manager.get_config()
            workspace_dict = {
                "name": name,
                "schedule_path": current_sched,
                "rosters": current_rosters,
                "roster_configs": current_roster_configs,
                "output_dir": current_output,
                "organization_preset": cfg.get("organization_preset", {}),
                "calendar_config": cfg.get("calendar_config", {}),
                "active_template_set": getattr(self, "active_template_set", ""),
            }
        return config_manager.save_workspace(name, workspace_dict)

    def load_workspace(self, workspace_id_or_name: str):
        """Loads a semester workspace snapshot and applies state to active session."""
        from modules.common.config_manager import config_manager
        from modules.services.validator import validate_rosters
        ws = config_manager.get_workspace(workspace_id_or_name)
        if not ws:
            return {"status": "error", "message": f"Workspace '{workspace_id_or_name}' not found"}

        lock = getattr(self, "_lock", None)
        if lock:
            with lock:
                self.schedule_path = ws.get("schedule_path", "")
                self.rosters = list(ws.get("rosters", []))
                self.roster_configs = dict(ws.get("roster_configs", {}))
                self.output_dir = ws.get("output_dir", "")
        else:
            self.schedule_path = ws.get("schedule_path", "")
            self.rosters = list(ws.get("rosters", []))
            self.roster_configs = dict(ws.get("roster_configs", {}))
            self.output_dir = ws.get("output_dir", "")

        cfg_modified = False
        cfg = config_manager.get_config()
        if ws.get("organization_preset"):
            cfg["organization_preset"] = ws["organization_preset"]
            cfg_modified = True
        if ws.get("calendar_config"):
            cfg["calendar_config"] = ws["calendar_config"]
            cfg_modified = True
        if cfg_modified:
            config_manager.save_config(cfg)

        validation = []
        if getattr(self, "rosters", None):
            try:
                validation = validate_rosters(
                    self.schedule_path,
                    self.rosters,
                    roster_configs=getattr(self, "roster_configs", {})
                )
            except Exception as e:
                logger.warning(f"Validation error upon workspace load: {e}")

        logger.info(f"Loaded workspace: {ws.get('name')}")
        return {
            "status": "success",
            "workspace": ws,
            "validation": validation,
        }

    def delete_workspace(self, workspace_id_or_name: str):
        """Deletes a saved semester workspace."""
        from modules.common.config_manager import config_manager
        return config_manager.delete_workspace(workspace_id_or_name)

    def export_workspace_file(self, file_path: str = None, workspace_id_or_name: str = None):
        """Exports a workspace snapshot to an external .cvsu-workspace.json file."""
        import webview
        from modules.common.config_manager import config_manager

        if file_path is None:
            if not getattr(self, "_window", None):
                return {"status": "error", "message": "Window context unavailable"}
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="semester_workspace.cvsu-workspace.json",
                file_types=('CvSU Workspace (*.cvsu-workspace.json;*.json)', 'All files (*.*)')
            )
            if not result:
                return {"status": "cancelled"}
            file_path = result if isinstance(result, str) else result[0]

        ws_dict = None
        if not workspace_id_or_name:
            # Snapshot active state
            lock = getattr(self, "_lock", None)
            if lock:
                with lock:
                    current_sched = getattr(self, "schedule_path", "")
                    current_rosters = list(getattr(self, "rosters", []))
                    current_roster_configs = dict(getattr(self, "roster_configs", {}))
                    current_output = getattr(self, "output_dir", "")
            else:
                current_sched = getattr(self, "schedule_path", "")
                current_rosters = list(getattr(self, "rosters", []))
                current_roster_configs = dict(getattr(self, "roster_configs", {}))
                current_output = getattr(self, "output_dir", "")

            cfg = config_manager.get_config()
            ws_dict = {
                "name": "Exported Workspace Snapshot",
                "schedule_path": current_sched,
                "rosters": current_rosters,
                "roster_configs": current_roster_configs,
                "output_dir": current_output,
                "organization_preset": cfg.get("organization_preset", {}),
                "calendar_config": cfg.get("calendar_config", {}),
                "active_template_set": getattr(self, "active_template_set", ""),
            }

        return config_manager.export_workspace_file(
            file_path,
            workspace_id_or_name=workspace_id_or_name,
            workspace_dict=ws_dict
        )

    def import_workspace_file(self, file_path: str = None):
        """Imports an external .cvsu-workspace.json file."""
        import webview
        from modules.common.config_manager import config_manager

        if file_path is None:
            if not getattr(self, "_window", None):
                return {"status": "error", "message": "Window context unavailable"}
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('CvSU Workspace (*.cvsu-workspace.json;*.json)', 'All files (*.*)')
            )
            if not result or len(result) == 0:
                return {"status": "cancelled"}
            file_path = result[0]

        return config_manager.import_workspace_file(file_path)



