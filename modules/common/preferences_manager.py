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
import threading
from copy import deepcopy
from typing import Dict, Any, Optional

from modules.common.logger import logger

SUPPORTED_SCHEMA_VERSION = "1.0"

DEFAULT_USER_PREFERENCES: Dict[str, Any] = {
    "version": SUPPORTED_SCHEMA_VERSION,
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
    Validates and normalizes raw preferences data against the canonical schema.
    Safely falls back invalid or missing keys without discarding valid sibling fields.
    Strips any internal or unknown metadata (such as '_persisted').
    """
    defaults = get_default_preferences_dict()
    if not isinstance(raw_data, dict):
        return defaults

    validated = deepcopy(defaults)

    # 1. Version validation
    # Reserved for future schema migrations. Currently supports version "1.0".
    if "version" in raw_data and raw_data["version"] is not None:
        raw_version = raw_data["version"]
        if isinstance(raw_version, (str, int, float)):
            v_str = str(raw_version).strip()
            if v_str != SUPPORTED_SCHEMA_VERSION:
                logger.warning(
                    f"Unsupported user preferences schema version '{v_str}'. "
                    f"Version '{SUPPORTED_SCHEMA_VERSION}' is the only supported version. "
                    "Reverting to safe canonical defaults."
                )
                return defaults
            validated["version"] = SUPPORTED_SCHEMA_VERSION
        else:
            logger.warning(
                f"Invalid type for schema version: {type(raw_version).__name__}. "
                "Reverting to safe canonical defaults."
            )
            return defaults
    else:
        # Missing version: assume current supported schema and validate fields
        validated["version"] = SUPPORTED_SCHEMA_VERSION

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
    Thread-safe and guaranteed to maintain pure canonical schema on disk and in exports.
    """

    def __init__(self, config_dir: Optional[str] = None):
        self._lock = threading.RLock()
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
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def _notify_listeners(self):
        """
        Notify registered listeners with an independent defensive copy of canonical preferences.
        Mutating a listener payload cannot mutate manager state.
        """
        with self._lock:
            payload = deepcopy(self._cached_preferences)
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(deepcopy(payload))
            except Exception as e:
                logger.error(f"Error in preferences listener callback: {e}")

    def _load_under_lock(self) -> Dict[str, Any]:
        """Loads preferences under lock without triggering listeners."""
        defaults = get_default_preferences_dict()
        if not os.path.exists(self.preferences_file):
            self._cached_preferences = defaults
        else:
            try:
                with open(self.preferences_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                self._cached_preferences = validate_preferences(raw_data)
            except Exception as e:
                logger.warning(
                    f"Failed to parse user preferences from {self.preferences_file}, using defaults: {e}"
                )
                self._cached_preferences = defaults
        return deepcopy(self._cached_preferences)

    def load_preferences(self) -> Dict[str, Any]:
        """
        Loads user preferences from disk.
        Returns defaults if file is missing, corrupt, or invalid.
        Guarantees thread safety and atomic memory caching.
        """
        with self._lock:
            result = self._load_under_lock()

        self._notify_listeners()
        return result

    def has_persisted_file(self) -> bool:
        """Returns True if user_preferences.json physically exists on disk."""
        with self._lock:
            return os.path.exists(self.preferences_file)

    def get_preferences(self) -> Dict[str, Any]:
        """
        Returns the active cached preferences as a pure canonical document.
        Free of diagnostic metadata or internal tracking flags.
        Returns an independent defensive copy.
        """
        with self._lock:
            if self._cached_preferences is None:
                self._load_under_lock()
            return deepcopy(self._cached_preferences)

    def get_preferences_with_metadata(self) -> Dict[str, Any]:
        """
        Returns the canonical preference document enriched with diagnostic metadata.
        Used strictly by diagnostic probes and startup reconciliation hooks.
        """
        prefs = self.get_preferences()
        prefs["_persisted"] = self.has_persisted_file()
        return prefs

    def _persist_locked(self, validated: Dict[str, Any]) -> None:
        """
        Internal persistence helper.
        MUST be called while self._lock is acquired.
        Atomically writes to disk and updates in-memory cache.
        """
        os.makedirs(self.config_dir, exist_ok=True)
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

    def save_preferences(self, new_prefs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Complete validated document replacement.
        Requires all canonical keys ('theme' and 'accessibility' with 'motion' and 'transparency').
        Rejects partial updates with an error directing callers to update_preferences().
        Atomically writes to disk and updates memory cache.
        """
        if not isinstance(new_prefs, dict):
            return {"status": "error", "message": "Preferences payload must be a JSON object"}

        # Enforce complete document contract
        if "theme" not in new_prefs or "accessibility" not in new_prefs:
            return {
                "status": "error",
                "message": (
                    "Incomplete preferences document. Complete replacement requires 'theme' "
                    "and 'accessibility' ('motion', 'transparency'). Use update_preferences() for partial updates."
                )
            }

        acc = new_prefs.get("accessibility")
        if not isinstance(acc, dict) or "motion" not in acc or "transparency" not in acc:
            return {
                "status": "error",
                "message": (
                    "Incomplete preferences document. 'accessibility' must include both 'motion' "
                    "and 'transparency'. Use update_preferences() for partial updates."
                )
            }

        try:
            with self._lock:
                validated = validate_preferences(new_prefs)
                self._persist_locked(validated)
                saved_copy = deepcopy(validated)

            self._notify_listeners()
            logger.info("Successfully updated and persisted user preferences.")
            return {"status": "success", "preferences": saved_copy}
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")
            return {"status": "error", "message": str(e)}

    def update_preferences(self, partial_prefs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Explicit partial preference update executed as a single atomic transaction.
        Merges provided keys into the active canonical document, validates,
        and atomically persists the replacement document under self._lock.
        """
        if not isinstance(partial_prefs, dict):
            return {"status": "error", "message": "Partial preferences must be a JSON object"}

        try:
            with self._lock:
                if self._cached_preferences is None:
                    self._load_under_lock()

                current = deepcopy(self._cached_preferences)
                merged = deepcopy(current)

                if "version" in partial_prefs:
                    merged["version"] = partial_prefs["version"]

                if "theme" in partial_prefs:
                    merged["theme"] = partial_prefs["theme"]

                if "accessibility" in partial_prefs and isinstance(partial_prefs["accessibility"], dict):
                    acc_partial = partial_prefs["accessibility"]
                    if "motion" in acc_partial:
                        merged["accessibility"]["motion"] = acc_partial["motion"]
                    if "transparency" in acc_partial:
                        merged["accessibility"]["transparency"] = acc_partial["transparency"]

                validated = validate_preferences(merged)
                self._persist_locked(validated)
                saved_copy = deepcopy(validated)

            self._notify_listeners()
            logger.info("Successfully merged and persisted partial user preferences.")
            return {"status": "success", "preferences": saved_copy}
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return {"status": "error", "message": str(e)}

    def reset_preferences(self) -> Dict[str, Any]:
        """
        Removes custom preferences file and resets in-memory state to factory defaults.
        Guarantees subsequent get_preferences() returns pure canonical defaults.
        """
        try:
            with self._lock:
                if os.path.exists(self.preferences_file):
                    os.remove(self.preferences_file)
                self._cached_preferences = get_default_preferences_dict()

            self._notify_listeners()
            logger.info("Reset user preferences to factory defaults.")
            return {"status": "success", "preferences": self.get_preferences()}
        except Exception as e:
            logger.error(f"Error resetting user preferences: {e}")
            return {"status": "error", "message": str(e)}

    def export_preferences(self, target_path: str) -> Dict[str, Any]:
        """
        Exports user preferences to a JSON file.
        Guaranteed to export ONLY the pure canonical schema without diagnostic metadata.
        """
        try:
            prefs = self.get_preferences()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2, ensure_ascii=False)
            return {"status": "success", "path": target_path}
        except Exception as e:
            logger.error(f"Failed to export preferences to {target_path}: {e}")
            return {"status": "error", "message": str(e)}

    def import_preferences(self, source_path: str) -> Dict[str, Any]:
        """
        Imports and validates user preferences from an external JSON file.
        Safely normalizes schema and strips any unknown fields or metadata.
        Enforces complete canonical document contract.
        """
        if not os.path.exists(source_path):
            return {"status": "error", "message": f"File not found: {source_path}"}
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            if not isinstance(raw_data, dict):
                return {"status": "error", "message": "Import file must contain a JSON object"}

            # Enforce complete canonical document contract
            if "theme" not in raw_data or "accessibility" not in raw_data:
                return {
                    "status": "error",
                    "message": (
                        "Incomplete preferences document: import requires a complete preference document "
                        "containing 'theme' and 'accessibility' ('motion', 'transparency')."
                    )
                }

            acc = raw_data.get("accessibility")
            if not isinstance(acc, dict) or "motion" not in acc or "transparency" not in acc:
                return {
                    "status": "error",
                    "message": (
                        "Incomplete preferences document: 'accessibility' must include both 'motion' "
                        "and 'transparency'."
                    )
                }

            validated = validate_preferences(raw_data)
            return self.save_preferences(validated)
        except Exception as e:
            logger.error(f"Failed to import preferences from {source_path}: {e}")
            return {"status": "error", "message": str(e)}


# Global singleton instance
preferences_manager = PreferencesManager()
