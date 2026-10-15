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

