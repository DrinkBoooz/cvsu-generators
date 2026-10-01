#!/usr/bin/env python3
"""
modules/common/preferences_manager.py

First-class manager for User Preferences persistence, validation, and lifecycle.
Enforces:
  - Strict separation between User Preferences (UI / accessibility) and
    Application Configuration (curriculum, parser rules, templates).
  - Schema validation for theme ("dark" | "light") and accessibility
    (motion: "system" | "reduce" | "full", transparency: "system" | "reduce" | "glass").
  - Atomic writes to disk (%APPDATA%/CVSU_Generators/config/user_preferences.json).
  - Safe fallback on missing, malformed, or corrupted configuration files.
"""

import os
import json
import tempfile
from copy import deepcopy
from typing import Dict, Any, Optional

from modules.common.logger import logger

DEFAULT_USER_PREFERENCES: Dict[str, Any] = {
    "version": "1.0",
    "theme": "dark",
    "accessibility": {
        "motion": "system",
        "transparency": "system"
    }
}

VALID_THEMES = {"dark", "light"}
VALID_MOTION_PREFERENCES = {"system", "reduce", "full"}
VALID_TRANSPARENCY_PREFERENCES = {"system", "reduce", "glass"}


def get_default_preferences_dict() -> Dict[str, Any]:
    """Returns a fresh deep copy of default user preferences."""
    return deepcopy(DEFAULT_USER_PREFERENCES)


def validate_preferences(raw_data: Any) -> Dict[str, Any]:
    """
    Validates and normalizes raw preferences data against the schema.
    Safely falls back invalid or missing keys without discarding valid sibling fields.
    """
    defaults = get_default_preferences_dict()
    if not isinstance(raw_data, dict):
        return defaults

    validated = deepcopy(defaults)

    # 1. Version
    if "version" in raw_data and isinstance(raw_data["version"], (str, int, float)):
        validated["version"] = str(raw_data["version"]).strip() or "1.0"

    # 2. Theme validation
    theme_val = raw_data.get("theme")
    if isinstance(theme_val, str) and theme_val.strip().lower() in VALID_THEMES:
        validated["theme"] = theme_val.strip().lower()
    else:
        validated["theme"] = defaults["theme"]

    # 3. Accessibility validation
    acc_val = raw_data.get("accessibility")
    if isinstance(acc_val, dict):
        # Motion
        m_val = acc_val.get("motion")
        if isinstance(m_val, str) and m_val.strip().lower() in VALID_MOTION_PREFERENCES:
            validated["accessibility"]["motion"] = m_val.strip().lower()
        else:
            validated["accessibility"]["motion"] = defaults["accessibility"]["motion"]

        # Transparency
        t_val = acc_val.get("transparency")
        if isinstance(t_val, str) and t_val.strip().lower() in VALID_TRANSPARENCY_PREFERENCES:
            validated["accessibility"]["transparency"] = t_val.strip().lower()
        else:
            validated["accessibility"]["transparency"] = defaults["accessibility"]["transparency"]

    return validated


class PreferencesManager:
    """
    Authoritative manager for user preferences (theme, accessibility).
    Persists to %APPDATA%/CVSU_Generators/config/user_preferences.json.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = os.path.abspath(config_dir)
        else:
            app_data = os.getenv("APPDATA") or os.path.expanduser("~")
            self.config_dir = os.path.join(app_data, "CVSU_Generators", "config")

        self.preferences_file = os.path.join(self.config_dir, "user_preferences.json")
        self._cached_preferences: Optional[Dict[str, Any]] = None
        self._listeners = []
        self.load_preferences()

    def register_listener(self, callback):
        """Register a callback invoked when preferences change."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self):
        for cb in self._listeners:
            try:
                cb(self._cached_preferences)
            except Exception as e:
                logger.error(f"Error in preferences listener callback: {e}")

    def load_preferences(self) -> Dict[str, Any]:
        """
        Loads user preferences from disk.
        Returns defaults if file is missing, corrupt, or invalid.
        """
        defaults = get_default_preferences_dict()
        if not os.path.exists(self.preferences_file):
            self._cached_preferences = defaults
            self._notify_listeners()
            return self._cached_preferences

        try:
            with open(self.preferences_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            self._cached_preferences = validate_preferences(raw_data)
        except Exception as e:
            logger.warning(
                f"Failed to parse user preferences from {self.preferences_file}, using defaults: {e}"
            )
            self._cached_preferences = defaults

        self._notify_listeners()
        return self._cached_preferences

    def get_preferences(self) -> Dict[str, Any]:
        """Returns the active cached preferences."""
        if self._cached_preferences is None:
            self.load_preferences()
        return deepcopy(self._cached_preferences)

    def save_preferences(self, new_prefs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates, atomically writes to disk, and updates memory cache.
        """
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            validated = validate_preferences(new_prefs)

            # Atomic write via tempfile
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.config_dir, prefix="prefs_tmp_", suffix=".json"
            )
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(validated, f, indent=2, ensure_ascii=False)

            if os.path.exists(self.preferences_file):
                os.replace(temp_path, self.preferences_file)
            else:
                os.rename(temp_path, self.preferences_file)

            self._cached_preferences = validated
            self._notify_listeners()
            logger.info("Successfully updated and persisted user preferences.")
            return {"status": "success", "preferences": validated}
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")
            return {"status": "error", "message": str(e)}

    def reset_preferences(self) -> Dict[str, Any]:
        """
        Removes custom preferences file and resets to factory defaults.
        """
        try:
            if os.path.exists(self.preferences_file):
                os.remove(self.preferences_file)
            self._cached_preferences = get_default_preferences_dict()
            self._notify_listeners()
            logger.info("Reset user preferences to factory defaults.")
            return {"status": "success", "preferences": self._cached_preferences}
        except Exception as e:
            logger.error(f"Error resetting user preferences: {e}")
            return {"status": "error", "message": str(e)}

    def export_preferences(self, target_path: str) -> Dict[str, Any]:
        """Exports user preferences to a JSON file."""
        try:
            prefs = self.get_preferences()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2, ensure_ascii=False)
            return {"status": "success", "path": target_path}
        except Exception as e:
            logger.error(f"Failed to export preferences to {target_path}: {e}")
            return {"status": "error", "message": str(e)}

    def import_preferences(self, source_path: str) -> Dict[str, Any]:
        """Imports and validates user preferences from an external JSON file."""
        if not os.path.exists(source_path):
            return {"status": "error", "message": f"File not found: {source_path}"}
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return self.save_preferences(raw_data)
        except Exception as e:
            logger.error(f"Failed to import preferences from {source_path}: {e}")
            return {"status": "error", "message": str(e)}


# Global singleton instance
preferences_manager = PreferencesManager()
