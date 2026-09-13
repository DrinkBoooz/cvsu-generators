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
