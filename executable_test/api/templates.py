import os
import tempfile
import base64
import webview
import process_schedule
from .base import sanitize_filename

class TemplateMixin:
    """Mixin handling custom template inspection and registration operations."""

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
            clean_filename = sanitize_filename(filename)
            cache_dir = os.path.join(tempfile.gettempdir(), "cvsu_cache", "custom_templates")
            os.makedirs(cache_dir, exist_ok=True)
            target_path = os.path.join(cache_dir, clean_filename)
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
