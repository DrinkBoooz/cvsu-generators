import os
import webview
from modules.common.logger import logger
from .base import sanitize_filename
from modules.services.template_set_manager import TemplateSetManager
from modules.parsers.template_role_detector import TemplateRoleDetector
from modules.models.template_set import CANONICAL_ROLES, ROLE_DISPLAY_NAMES, ROLE_PROFILE_MAPPING

class TemplateMixin:
    """
    Mixin handling both complete institutional Template Sets and
    individual Custom Document Forms.
    """

    # ══ Template Sets API ═════════════════════════════════════════════════════
    def get_template_sets(self):
        """Retrieves list of all available template sets (built-in + user sets)."""
        try:
            mgr = TemplateSetManager.get_instance()
            sets = mgr.list_template_sets()
            active_id = mgr.get_active_template_set_id()
            result = []
            for s in sets:
                d = s.to_dict()
                d["status"] = s.status()
                d["is_complete"] = s.is_complete()
                d["missing_roles"] = s.missing_roles()
                d["is_active"] = (s.set_id == active_id)
                d["total_roles"] = len(CANONICAL_ROLES)
                d["configured_roles"] = len(s.templates)
                result.append(d)
            return {"status": "success", "template_sets": result, "active_set_id": active_id}
        except Exception as e:
            logger.error(f"Failed to list template sets: {e}")
            return {"status": "error", "message": str(e)}

    def get_active_template_set(self):
        """Retrieves the currently active template set."""
        try:
            mgr = TemplateSetManager.get_instance()
            s = mgr.get_active_template_set()
            d = s.to_dict()
            d["status"] = s.status()
            d["is_complete"] = s.is_complete()
            d["missing_roles"] = s.missing_roles()
            d["total_roles"] = len(CANONICAL_ROLES)
            d["configured_roles"] = len(s.templates)
            return {"status": "success", "active_set": d}
        except Exception as e:
            logger.error(f"Failed to get active template set: {e}")
            return {"status": "error", "message": str(e)}

    def create_template_set(self, display_name, description="", fallback_to_default=False):
        """Creates a new user template set."""
        try:
            mgr = TemplateSetManager.get_instance()
            ts = mgr.create_template_set(
                display_name=display_name,
                description=description,
                fallback_to_default=bool(fallback_to_default),
            )
            d = ts.to_dict()
            d["status"] = ts.status()
            d["is_complete"] = ts.is_complete()
            d["missing_roles"] = ts.missing_roles()
            return {"status": "success", "template_set": d}
        except Exception as e:
            logger.error(f"Failed to create template set: {e}")
            return {"status": "error", "message": str(e)}

    def update_template_set(self, set_id, display_name=None, description=None, fallback_to_default=None):
        """Updates user template set metadata or fallback policy."""
        try:
            mgr = TemplateSetManager.get_instance()
            ts = mgr.update_template_set(
                set_id=set_id,
                display_name=display_name,
                description=description,
                fallback_to_default=fallback_to_default,
            )
            d = ts.to_dict()
            d["status"] = ts.status()
            d["is_complete"] = ts.is_complete()
            d["missing_roles"] = ts.missing_roles()
            return {"status": "success", "template_set": d}
        except Exception as e:
            logger.error(f"Failed to update template set {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def activate_template_set(self, set_id):
        """Activates the specified template set."""
        try:
            mgr = TemplateSetManager.get_instance()
            ts = mgr.activate_template_set(set_id)
            return {"status": "success", "active_set_id": ts.set_id}
        except Exception as e:
            logger.error(f"Failed to activate template set {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def set_template_set_fallback(self, set_id, fallback_to_default):
        """Toggles the fallback-to-default policy for a template set."""
        try:
            mgr = TemplateSetManager.get_instance()
            ts = mgr.set_fallback_policy(set_id, bool(fallback_to_default))
            return {"status": "success", "fallback_to_default": ts.fallback_to_default}
        except Exception as e:
            logger.error(f"Failed to set fallback policy for {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def delete_template_set(self, set_id):
        """Deletes a user template set."""
        try:
            mgr = TemplateSetManager.get_instance()
            mgr.delete_template_set(set_id)
            return {"status": "success", "deleted_set_id": set_id}
        except Exception as e:
            logger.error(f"Failed to delete template set {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def duplicate_template_set(self, set_id, new_name):
        """Duplicates a template set."""
        try:
            mgr = TemplateSetManager.get_instance()
            ts = mgr.duplicate_template_set(set_id, new_name)
            d = ts.to_dict()
            d["status"] = ts.status()
            d["is_complete"] = ts.is_complete()
            d["missing_roles"] = ts.missing_roles()
            return {"status": "success", "template_set": d}
        except Exception as e:
            logger.error(f"Failed to duplicate template set {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def browse_template_set_files(self):
        """File browser dialog for selecting multiple .docx/.xlsx templates for inspection."""
        if not self._window:
            return {"status": "error", "message": "Window context unavailable"}
        file_types = ('Document Templates (*.docx;*.xlsx)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types
        )
        if result and len(result) > 0:
            return self.inspect_template_set_files(list(result))
        return {"status": "cancelled"}

    def inspect_template_set_files(self, file_paths):
        """Runs dynamic physical role detection and inspection on multiple files."""
        try:
            from modules.parsers.template_analyzer import DeterministicTemplateAnalyzer
            analyzer = DeterministicTemplateAnalyzer.get_instance()
            detector = TemplateRoleDetector()
            inspections = []
            for p in file_paths:
                if not isinstance(p, str) or not p.strip() or "\x00" in p:
                    continue
                abs_p = os.path.abspath(p.strip())
                if not os.path.isfile(abs_p):
                    inspections.append({
                        "file_path": p,
                        "file_name": os.path.basename(p),
                        "file_type": "unknown",
                        "status": "unsupported",
                        "error": "File does not exist",
                    })
                    continue

                ext = os.path.splitext(abs_p)[1].lower()
                if ext not in (".docx", ".xlsx", ".xls"):
                    inspections.append({
                        "file_path": p,
                        "file_name": os.path.basename(p),
                        "file_type": ext,
                        "status": "unsupported",
                        "error": f"Unsupported template format '{ext}'",
                    })
                    continue

                res = detector.detect_role(abs_p)
                d = res.to_dict()
                try:
                    m = analyzer.analyze(abs_p)
                    d["manifest_summary"] = {
                        "content_hash": m.content_hash,
                        "is_ready": m.is_ready,
                        "template_type": m.template_type,
                        "slots_count": len(m.slots),
                        "roster_capacity": m.roster_table.data_rows_capacity if m.roster_table else 0,
                        "diagnostics": m.get_diagnostics(),
                    }
                except Exception as m_err:
                    logger.debug(f"Manifest analysis skipped for {abs_p}: {m_err}")
                inspections.append(d)

            return {"status": "success", "inspections": inspections}
        except Exception as e:
            logger.error(f"Failed to inspect template set files: {e}")
            return {"status": "error", "message": str(e)}

    def save_template_set(self, set_id, display_name, description, fallback_to_default, template_assignments):
        """
        Creates or updates a template set and validates/assigns its physical templates.
        Enforces: declared role + physical inspection + RecipeValidator.
        """
        try:
            mgr = TemplateSetManager.get_instance()
            ts = mgr.get_template_set(set_id)
            if not ts:
                ts = mgr.create_template_set(
                    display_name=display_name,
                    description=description,
                    set_id=set_id,
                    fallback_to_default=bool(fallback_to_default),
                )
            else:
                ts = mgr.update_template_set(
                    set_id=set_id,
                    display_name=display_name,
                    description=description,
                    fallback_to_default=bool(fallback_to_default),
                )

            # Assign templates
            if template_assignments and isinstance(template_assignments, list):
                for item in template_assignments:
                    role = item.get("role")
                    file_path = item.get("file_path")
                    meta = item.get("display_metadata") or {}
                    if role and file_path and os.path.exists(file_path):
                        mgr.add_template_to_set(
                            set_id=ts.set_id,
                            role=role,
                            file_path=file_path,
                            display_metadata=meta,
                        )

            refreshed = mgr.get_template_set(ts.set_id)
            d = refreshed.to_dict()
            d["status"] = refreshed.status()
            d["is_complete"] = refreshed.is_complete()
            d["missing_roles"] = refreshed.missing_roles()
            d["total_roles"] = len(CANONICAL_ROLES)
            d["configured_roles"] = len(refreshed.templates)
            return {"status": "success", "template_set": d}
        except Exception as e:
            logger.error(f"Failed to save template set {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def export_template_set(self, set_id, destination_path=None):
        """Exports a template set package (.cvstemplateset.zip)."""
        try:
            mgr = TemplateSetManager.get_instance()
            if not destination_path and self._window:
                result = self._window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=f"{sanitize_filename(set_id)}.cvstemplateset.zip",
                    file_types=('Template Set Package (*.cvstemplateset.zip)', 'All files (*.*)')
                )
                if result:
                    destination_path = result if isinstance(result, str) else result[0]
                else:
                    return {"status": "cancelled"}

            if not destination_path:
                return {"status": "error", "message": "No destination path provided"}

            out_path = mgr.export_template_set(set_id, destination_path)
            return {"status": "success", "file_path": out_path}
        except Exception as e:
            logger.error(f"Failed to export template set {set_id}: {e}")
            return {"status": "error", "message": str(e)}

    def import_template_set(self, source_zip_path=None):
        """Imports a template set package (.cvstemplateset.zip or .zip)."""
        try:
            mgr = TemplateSetManager.get_instance()
            if not source_zip_path and self._window:
                result = self._window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=False,
                    file_types=('Template Set Package (*.cvstemplateset.zip;*.zip)', 'All files (*.*)')
                )
                if result and len(result) > 0:
                    source_zip_path = result[0]
                else:
                    return {"status": "cancelled"}

            if not source_zip_path or not os.path.exists(source_zip_path):
                return {"status": "error", "message": "Package file not found"}

            ts = mgr.import_template_set(source_zip_path)
            d = ts.to_dict()
            d["status"] = ts.status()
            d["is_complete"] = ts.is_complete()
            d["missing_roles"] = ts.missing_roles()
            return {"status": "success", "template_set": d}
        except Exception as e:
            logger.error(f"Failed to import template set from {source_zip_path}: {e}")
            return {"status": "error", "message": str(e)}

    # ══ Individual Custom Templates API (100% Backward Compatible) ════════════
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

    def handle_dropped_custom_template(self, filename, original_path=None):
        """Handles drag-and-drop of a .docx template."""
        target_path = None
        if original_path and os.path.exists(original_path):
            target_path = original_path

        if target_path and os.path.exists(target_path):
            return self.inspect_custom_template(target_path)
        return {"status": "error", "message": "Target template file could not be resolved"}

    def inspect_custom_template(self, file_path):
        """Runs the deterministic heuristic inspector and analyzer on the provided .docx/.xlsx template."""
        try:
            if not isinstance(file_path, str) or not file_path.strip():
                return {"status": "error", "message": "Template file path must be a non-empty string"}

            if "\x00" in file_path:
                return {"status": "error", "message": "Invalid file path (null byte detected)"}

            abs_path = os.path.abspath(file_path.strip())
            ext = os.path.splitext(abs_path)[1].lower()
            if ext not in (".docx", ".xlsx", ".xls"):
                return {"status": "error", "message": f"Unsupported template file format '{ext}'. Only .docx and .xlsx are supported."}

            if not os.path.isfile(abs_path):
                return {"status": "error", "message": f"Template file does not exist: {file_path}"}

            # 1. Authoritative Deterministic Template Analyzer (with thread-safe SHA-256 caching)
            from modules.parsers.template_analyzer import DeterministicTemplateAnalyzer
            analyzer = DeterministicTemplateAnalyzer.get_instance()
            manifest = analyzer.analyze(abs_path)

            # 2. Legacy recipe compatibility facade for existing UI and storage pipeline
            from modules.parsers.template_inspector import TemplateInspector
            inspector = TemplateInspector()
            recipe = inspector.inspect(abs_path) if ext in (".xlsx", ".xls") else inspector.inspect_docx(abs_path)

            manifest_summary = {
                "content_hash": manifest.content_hash,
                "is_ready": manifest.is_ready,
                "template_type": manifest.template_type,
                "suggested_title": manifest.suggested_title,
                "suggested_suffix": manifest.suggested_suffix,
                "slots_count": len(manifest.slots),
                "slots": [
                    {
                        "field": s.field,
                        "slot_type": s.slot_type,
                        "strategy": s.strategy,
                        "target_coordinates": (s.target_row_index, s.target_col_index) if s.slot_type == "table_cell" else s.paragraph_index,
                    }
                    for s in manifest.slots
                ],
                "roster_table": {
                    "table_index": manifest.roster_table.table_index,
                    "capacity": manifest.roster_table.data_rows_capacity,
                    "columns": manifest.roster_table.columns,
                    "first_data_row": manifest.roster_table.first_data_row_index,
                    "total_rows": manifest.roster_table.total_rows,
                    "total_cols": manifest.roster_table.total_cols,
                } if manifest.roster_table else None,
                "organizational_context": manifest.organizational_context.to_dict() if manifest.organizational_context else None,
                "signatory_slots": [s.to_dict() for s in manifest.signatory_slots] if manifest.signatory_slots else [],
                "diagnostics": manifest.get_diagnostics(),
            }

            return {
                "status": "success",
                "file_path": abs_path,
                "recipe": recipe,
                "manifest": manifest.to_dict(),
                "manifest_summary": manifest_summary,
            }
        except Exception as e:
            logger.error(f"Failed to inspect custom template {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def save_custom_template(self, file_path, title, suffix, recipe):
        """Saves a custom template and registers its recipe in ParserConfigManager."""
        try:
            from modules.common.config_manager import config_manager
            res = config_manager.save_custom_template(file_path, title, suffix, recipe)
            return res
        except Exception as e:
            logger.error(f"Failed to save custom template: {e}")
            return {"status": "error", "message": str(e)}

    def get_custom_templates(self):
        """Retrieves list of active custom templates."""
        try:
            from modules.common.config_manager import config_manager
            return config_manager.get_custom_templates()
        except Exception as e:
            logger.error(f"Failed to get custom templates: {e}")
            return []

    def toggle_custom_template(self, template_id, enabled):
        """Toggles a custom template's enabled state."""
        try:
            from modules.common.config_manager import config_manager
            return config_manager.toggle_custom_template(template_id, enabled)
        except Exception as e:
            logger.error(f"Failed to toggle custom template: {e}")
            return {"status": "error", "message": str(e)}

    def delete_custom_template(self, template_id):
        """Deletes a custom template and its file."""
        try:
            from modules.common.config_manager import config_manager
            return config_manager.delete_custom_template(template_id)
        except Exception as e:
            logger.error(f"Failed to delete custom template: {e}")
            return {"status": "error", "message": str(e)}

    # ══ 2D Grid Serialization & Visual Slot Overrides ═════════════════════════
    def get_template_grid_preview(self, file_path, max_rows=15):
        """Returns 2D grid table serialization for visual slot inspection and overrides."""
        try:
            if not isinstance(file_path, str) or not file_path.strip():
                return {"status": "error", "message": "Template file path must be a non-empty string"}

            abs_path = os.path.abspath(file_path.strip())
            if not os.path.isfile(abs_path):
                return {"status": "error", "message": f"Template file does not exist: {file_path}"}

            from modules.parsers.template_analyzer import DeterministicTemplateAnalyzer
            analyzer = DeterministicTemplateAnalyzer.get_instance()
            preview = analyzer.serialize_grid_preview(abs_path, max_rows=int(max_rows))
            return {"status": "success", "preview": preview}
        except Exception as e:
            logger.error(f"Failed to generate template grid preview for {file_path}: {e}")
            return {"status": "error", "message": str(e)}

    def save_template_slot_overrides(self, file_path, overrides_dict):
        """Saves user-defined slot overrides for the given template."""
        try:
            if not isinstance(file_path, str) or not file_path.strip():
                return {"status": "error", "message": "Template file path must be a non-empty string"}

            if not isinstance(overrides_dict, dict):
                return {"status": "error", "message": "Overrides must be a JSON object mapping slot fields to cell coordinates"}

            abs_path = os.path.abspath(file_path.strip())
            file_key = os.path.basename(abs_path)

            from modules.common.config_manager import config_manager
            cfg = config_manager.get_config()
            all_overrides = cfg.setdefault("template_slot_overrides", {})
            all_overrides[file_key] = overrides_dict
            all_overrides[abs_path] = overrides_dict
            config_manager.save_config(cfg)

            # Invalidate analyzer cache for this template
            from modules.parsers.template_analyzer import DeterministicTemplateAnalyzer
            analyzer = DeterministicTemplateAnalyzer.get_instance()
            analyzer.invalidate(abs_path)

            return {
                "status": "success",
                "file_path": abs_path,
                "overrides_count": len(overrides_dict),
                "overrides": overrides_dict,
            }
        except Exception as e:
            logger.error(f"Failed to save slot overrides for {file_path}: {e}")
            return {"status": "error", "message": str(e)}

