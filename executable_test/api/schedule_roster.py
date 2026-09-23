import os
import base64
import tempfile
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

    def handle_dropped_schedule(self, filename, original_path=None, base64_data=None):
        target_path = None
        if original_path and os.path.exists(original_path):
            target_path = original_path
        elif base64_data and filename:
            clean_filename = sanitize_filename(filename)
            cache_dir = os.path.join(tempfile.gettempdir(), "cvsu_cache", "schedules")
            os.makedirs(cache_dir, exist_ok=True)
            target_path = os.path.join(cache_dir, clean_filename)
            try:
                with open(target_path, "wb") as f:
                    f.write(base64.b64decode(base64_data))
            except Exception as e:
                logger.error(f"Failed to write dropped schedule {filename}: {e}")
                return {"cancelled": False, "path": "", "metadata": None, "validation": []}

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
            with self._lock:
                self.roster_configs = roster_configs
        file_types = ('Student Lists (*.csv;*.xlsx;*.xls)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types
        )
        if result:
            # Part D: acquire lock to merge new paths atomically
            with self._lock:
                existing = set(self.rosters)
                for r in result:
                    if r not in existing:
                        self.rosters.append(r)
                        existing.add(r)
                current_rosters = list(self.rosters)
            validation = validate_rosters(self.schedule_path, current_rosters, roster_configs=self.roster_configs)
            return {
                "cancelled": False,
                "count": len(current_rosters),
                "rosters": current_rosters,
                "validation": validation
            }
        with self._lock:
            current_rosters = list(self.rosters)
        return {
            "cancelled": True,
            "count": len(current_rosters),
            "rosters": current_rosters,
            "validation": validate_rosters(self.schedule_path, current_rosters, roster_configs=self.roster_configs) if current_rosters else []
        }

    def handle_dropped_rosters(self, files_payload, roster_configs=None):
        if roster_configs is not None:
            with self._lock:
                self.roster_configs = roster_configs

        cache_dir = os.path.join(tempfile.gettempdir(), "cvsu_cache", "rosters")
        os.makedirs(cache_dir, exist_ok=True)

        # Resolve file paths OUTSIDE the lock (may involve disk I/O)
        new_paths = []
        for item in files_payload:
            original_path = item.get("path")
            base64_data = item.get("data")
            filename = sanitize_filename(item.get("filename", ""))

            if original_path and os.path.isfile(original_path):
                new_paths.append(original_path)
            elif base64_data and filename:
                target_path = os.path.join(cache_dir, filename)
                try:
                    with open(target_path, "wb") as f:
                        f.write(base64.b64decode(base64_data))
                    new_paths.append(target_path)
                except Exception as e:
                    logger.error(f"Failed to write dropped roster {filename}: {e}")

        # Part D: acquire lock to merge resolved paths atomically
        with self._lock:
            existing = set(self.rosters)
            for p in new_paths:
                if p not in existing:
                    self.rosters.append(p)
                    existing.add(p)
            current_rosters = list(self.rosters)

        validation = validate_rosters(self.schedule_path, current_rosters, roster_configs=self.roster_configs)
        return {
            "count": len(current_rosters),
            "rosters": current_rosters,
            "validation": validation
        }

    def remove_roster(self, path_or_index, roster_configs=None):
        if roster_configs is not None:
            with self._lock:
                self.roster_configs = roster_configs
        # Part D: lock around list mutation
        with self._lock:
            if isinstance(path_or_index, int) and 0 <= path_or_index < len(self.rosters):
                self.rosters.pop(path_or_index)
            elif path_or_index in self.rosters:
                self.rosters.remove(path_or_index)
            current_rosters = list(self.rosters)
        return {
            "count": len(current_rosters),
            "rosters": current_rosters,
            "validation": validate_rosters(self.schedule_path, current_rosters, roster_configs=self.roster_configs) if current_rosters else []
        }

    def clear_rosters(self):
        with self._lock:
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
