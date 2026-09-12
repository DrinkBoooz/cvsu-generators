import os
import tempfile
import base64
import uuid
import webview
from modules.common.logger import logger
from modules.parsers.schedule_parser import inspect_schedule_file
from modules.services.validator import validate_rosters, detect_classes
import roster_parser
from .base import sanitize_filename

class ScheduleRosterMixin:
    """Mixin handling instructor schedule and student roster operations."""

    def clear_schedule(self):
        with self._lock:
            self.schedule_path = ""
        validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
        return {"status": "success", "path": "", "metadata": None, "validation": validation}

    def browse_schedule(self):
        file_types = ('Excel files (*.xls;*.xlsx;*.xlsm)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            with self._lock:
                self.schedule_path = result[0]
            metadata = inspect_schedule_file(self.schedule_path)
            validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
            return {
                "cancelled": False,
                "path": self.schedule_path,
                "metadata": metadata,
                "validation": validation
            }
        return {"cancelled": True, "path": self.schedule_path}

    def inspect_schedule(self, path=None):
        target = path or self.schedule_path
        if not target:
            return None
        return inspect_schedule_file(target)

    def handle_dropped_schedule(self, filename, original_path=None):
        target_path = None
        if original_path and os.path.exists(original_path):
            target_path = original_path

        if target_path and os.path.exists(target_path):
            with self._lock:
                self.schedule_path = target_path
            metadata = inspect_schedule_file(self.schedule_path)
            validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
            return {
                "cancelled": False,
                "path": self.schedule_path,
                "metadata": metadata,
                "validation": validation
            }
        return {"cancelled": False, "path": "", "metadata": None, "validation": []}

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
            validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
            return {
                "cancelled": False,
                "count": len(self.rosters),
                "rosters": self.rosters,
                "validation": validation
            }
        return {
            "cancelled": True,
            "count": len(self.rosters),
            "rosters": self.rosters,
            "validation": validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
        }

    def handle_dropped_rosters(self, files_payload, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs

        new_paths = []
        for item in files_payload:
            original_path = item.get("path")
            if original_path and os.path.exists(original_path):
                new_paths.append(original_path)

        existing = set(self.rosters)
        for p in new_paths:
            if p not in existing:
                self.rosters.append(p)
                existing.add(p)

        validation = validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
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
            "validation": validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs) if self.rosters else []
        }

    def clear_rosters(self):
        self.rosters = []
        return {"count": 0, "rosters": [], "validation": []}

    def validate_rosters(self, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        if not self.rosters:
            return []
        return validate_rosters(self.schedule_path, self.rosters, roster_configs=self.roster_configs)

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

    def detect_classes(self, roster_configs=None):
        if roster_configs is not None:
            self.roster_configs = roster_configs
        if not self.schedule_path or not self.rosters:
            return []
        try:
            return detect_classes(self.schedule_path, self.rosters, roster_configs=self.roster_configs)
        except Exception as e:
            logger.error(f"Error in detect_classes: {e}")
            return []
