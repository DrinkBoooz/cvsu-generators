#!/usr/bin/env python3
"""
modules/services/template_set_manager.py

First-class Service for Template Set persistence, lifecycle, and active resolution.
Enforces:
  INSPECTOR DISCOVERS WHERE.
  VALIDATOR VERIFIES WHERE.
  GENERATOR CONSUMES WHERE.
  NO LAYER MAY FABRICATE MISSING TEMPLATE COORDINATES.

Storage hierarchy:
  %APPDATA%/CVSU_Generators/
      active_template_set.json
      template_sets/
          <set_id>/
              manifest.json
              templates/
                  ...

Built-in default set ("builtin_cvsu" / "CvSU Official"):
  Read-only, points to bundled templates in project root.
  Cannot be modified, renamed, or deleted.
"""

from datetime import datetime, timezone
import json
import os
import re
import shutil
import sys
import tempfile
from typing import Dict, Any, List, Optional, Tuple
import zipfile

from modules.common.logger import logger
from modules.models.template_set import (
    CANONICAL_ROLES,
    ROLE_PROFILE_MAPPING,
    ROLE_FILE_TYPE_MAPPING,
    ROLE_DISPLAY_NAMES,
    TemplateSet,
    TemplateEntry,
    TemplateSetError,
    InvalidTemplateSetError,
    MissingTemplateRoleError,
)
from modules.parsers.template_role_detector import TemplateRoleDetector


BUILTIN_SET_ID = "builtin_cvsu"
BUILTIN_DISPLAY_NAME = "CvSU Official"
BUILTIN_DESCRIPTION = "Built-in Cavite State University academic forms, attendance sheets, and grading templates."


class TemplateSetManager:
    """
    Manages persistence, activation, validation, import/export, and resolution
    of Template Sets.
    """
    _instance: Optional["TemplateSetManager"] = None

    def __init__(
        self,
        base_dir: Optional[str] = None,
        templates_dir: Optional[str] = None,
        attendance_dir: Optional[str] = None,
    ):
        if base_dir:
            self.base_dir = os.path.abspath(base_dir)
        else:
            app_data = os.getenv("APPDATA") or os.path.expanduser("~")
            self.base_dir = os.path.join(app_data, "CVSU_Generators")

        self.template_sets_dir = os.path.join(self.base_dir, "template_sets")
        self.active_set_file = os.path.join(self.base_dir, "active_template_set.json")
        os.makedirs(self.template_sets_dir, exist_ok=True)

        project_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.default_templates_dir = os.path.abspath(templates_dir or os.path.join(project_dir, "templates"))
        self.default_attendance_dir = os.path.abspath(attendance_dir or os.path.join(project_dir, "attendance"))

        self._role_detector = TemplateRoleDetector()

    @classmethod
    def get_instance(cls) -> "TemplateSetManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    # ══ Built-in Template Set ═════════════════════════════════════════════════
    def get_builtin_set(self) -> TemplateSet:
        """Constructs the authoritative read-only built-in CvSU template set."""
        entries: Dict[str, TemplateEntry] = {}

        file_map = {
            "syllabus": (os.path.join(self.default_templates_dir, "template_syllabus.docx"), "docx", "syllabus"),
            "exam_returns_midterm": (os.path.join(self.default_templates_dir, "template_exam_midterm.docx"), "docx", "exam_returns"),
            "exam_returns_final": (os.path.join(self.default_templates_dir, "template_exam_finals.docx"), "docx", "exam_returns"),
            "tos_midterm": (os.path.join(self.default_templates_dir, "template_tos_midterm.docx"), "docx", "tos"),
            "tos_final": (os.path.join(self.default_templates_dir, "template_tos_finals.docx"), "docx", "tos"),
            "grade_discussion_midterm": (os.path.join(self.default_templates_dir, "Midterm-Grade-Discussion_LATEST.docx"), "docx", "grade_discussion"),
            "grade_discussion_final": (os.path.join(self.default_templates_dir, "Final-Grade-Discussion_LATEST.docx"), "docx", "grade_discussion"),
            "attendance_lecture": (os.path.join(self.default_attendance_dir, "template lec.docx"), "docx", "attendance_docx"),
            "attendance_lecture_lab": (os.path.join(self.default_attendance_dir, "template lab and lec.docx"), "docx", "attendance_docx"),
            "grade_sheet_lecture": (os.path.join(self.default_templates_dir, "GRADING_LECTURE_TEMPLATE.xlsx"), "xlsx", "grade_sheet_xlsx"),
            "grade_sheet_lecture_lab": (os.path.join(self.default_templates_dir, "GRADING_LECTURE_LAB_TEMPLATE.xlsx"), "xlsx", "grade_sheet_xlsx"),
        }

        for role, (p, ftype, profile) in file_map.items():
            if os.path.exists(p):
                entries[role] = TemplateEntry(
                    role=role,
                    file_path=os.path.normpath(p),
                    file_type=ftype,
                    profile_id=profile,
                    enabled=True,
                    display_metadata={"title": ROLE_DISPLAY_NAMES.get(role, role), "is_builtin": True},
                )

        is_active = (self.get_active_template_set_id() == BUILTIN_SET_ID)
        return TemplateSet(
            set_id=BUILTIN_SET_ID,
            display_name=BUILTIN_DISPLAY_NAME,
            description=BUILTIN_DESCRIPTION,
            version="1.0.0",
            source="builtin",
            is_active=is_active,
            fallback_to_default=False,
            templates=entries,
        )

    # ══ Listing & Retrieval ═══════════════════════════════════════════════════
    def list_template_sets(self) -> List[TemplateSet]:
        """Lists all template sets: Built-in CvSU Official first, followed by user sets."""
        active_id = self.get_active_template_set_id()
        sets: List[TemplateSet] = [self.get_builtin_set()]

        if os.path.exists(self.template_sets_dir):
            for d in sorted(os.listdir(self.template_sets_dir)):
                set_dir = os.path.join(self.template_sets_dir, d)
                manifest_path = os.path.join(set_dir, "manifest.json")
                if os.path.isdir(set_dir) and os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        ts = TemplateSet.from_dict(data, base_dir=set_dir)
                        ts.is_active = (ts.set_id == active_id)
                        sets.append(ts)
                    except Exception as e:
                        logger.error(f"Failed to load template set manifest from {manifest_path}: {e}")

        return sets

    def get_template_set(self, set_id: str) -> Optional[TemplateSet]:
        """Retrieves a template set by ID."""
        if set_id == BUILTIN_SET_ID:
            return self.get_builtin_set()

        self._validate_set_id(set_id)
        set_dir = os.path.join(self.template_sets_dir, set_id)
        manifest_path = os.path.join(set_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            ts = TemplateSet.from_dict(data, base_dir=set_dir)
            ts.is_active = (ts.set_id == self.get_active_template_set_id())
            return ts
        except Exception as e:
            logger.error(f"Error reading template set '{set_id}': {e}")
            return None

    # ══ Active Set Tracking ═══════════════════════════════════════════════════
    def get_active_template_set_id(self) -> str:
        """Returns the ID of the active template set (defaults to built-in)."""
        if os.path.exists(self.active_set_file):
            try:
                with open(self.active_set_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                active_id = data.get("active_set_id")
                if active_id:
                    # Verify existence
                    if active_id == BUILTIN_SET_ID or os.path.exists(os.path.join(self.template_sets_dir, active_id)):
                        return active_id
            except Exception as e:
                logger.error(f"Error reading active template set file: {e}")
        return BUILTIN_SET_ID

    def get_active_template_set(self) -> TemplateSet:
        """Returns the currently active TemplateSet object."""
        active_id = self.get_active_template_set_id()
        ts = self.get_template_set(active_id)
        if ts is None:
            ts = self.get_builtin_set()
        return ts

    def activate_template_set(self, set_id: str) -> TemplateSet:
        """Activates the specified template set."""
        if set_id != BUILTIN_SET_ID:
            self._validate_set_id(set_id)
            target = self.get_template_set(set_id)
            if not target:
                raise TemplateSetError(f"Cannot activate non-existent template set '{set_id}'")

        # Atomic write of active set pointer
        with tempfile.NamedTemporaryFile("w", dir=self.base_dir, delete=False, encoding="utf-8") as tf:
            json.dump({"active_set_id": set_id}, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.active_set_file)

        logger.info(f"Activated template set: '{set_id}'")
        return self.get_active_template_set()

    # ══ CRUD Operations ═══════════════════════════════════════════════════════
    def create_template_set(
        self,
        display_name: str,
        description: str = "",
        set_id: Optional[str] = None,
        fallback_to_default: bool = False,
    ) -> TemplateSet:
        """Creates a new user template set directory and manifest."""
        display_name = display_name.strip()
        if not display_name:
            raise InvalidTemplateSetError("Template set display name cannot be empty")

        if not set_id:
            # Generate slug from display name
            slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", display_name.lower()).strip("_")
            set_id = slug or "custom_set"
            # Ensure uniqueness
            candidate_id = set_id
            counter = 1
            while os.path.exists(os.path.join(self.template_sets_dir, candidate_id)) or candidate_id == BUILTIN_SET_ID:
                candidate_id = f"{set_id}_{counter}"
                counter += 1
            set_id = candidate_id

        self._validate_set_id(set_id)
        if set_id == BUILTIN_SET_ID:
            raise InvalidTemplateSetError(f"Cannot create template set with reserved ID '{BUILTIN_SET_ID}'")

        set_dir = os.path.join(self.template_sets_dir, set_id)
        if os.path.exists(set_dir):
            raise TemplateSetError(f"Template set '{set_id}' already exists")

        templates_subfolder = os.path.join(set_dir, "templates")
        os.makedirs(templates_subfolder, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        ts = TemplateSet(
            set_id=set_id,
            display_name=display_name,
            description=description,
            version="1.0.0",
            created_at=now,
            updated_at=now,
            source="user",
            is_active=False,
            fallback_to_default=fallback_to_default,
            templates={},
        )

        self._save_manifest(ts, set_dir)
        logger.info(f"Created template set '{set_id}' at {set_dir}")
        return ts

    def update_template_set(
        self,
        set_id: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        fallback_to_default: Optional[bool] = None,
    ) -> TemplateSet:
        """Updates metadata and fallback policy for an existing user template set."""
        if set_id == BUILTIN_SET_ID:
            raise TemplateSetError("Cannot modify read-only built-in CvSU Official template set")

        ts = self.get_template_set(set_id)
        if not ts:
            raise TemplateSetError(f"Template set '{set_id}' not found")

        if display_name is not None:
            dn = display_name.strip()
            if not dn:
                raise InvalidTemplateSetError("Display name cannot be empty")
            ts.display_name = dn

        if description is not None:
            ts.description = description

        if fallback_to_default is not None:
            ts.fallback_to_default = bool(fallback_to_default)

        ts.updated_at = datetime.now(timezone.utc).isoformat()
        set_dir = os.path.join(self.template_sets_dir, set_id)
        self._save_manifest(ts, set_dir)
        return ts

    def set_fallback_policy(self, set_id: str, fallback_to_default: bool) -> TemplateSet:
        """Explicitly toggles the fallback policy for a user template set."""
        return self.update_template_set(set_id, fallback_to_default=fallback_to_default)

    def delete_template_set(self, set_id: str) -> bool:
        """Deletes a user template set. Reverts active set to built-in if active."""
        if set_id == BUILTIN_SET_ID:
            raise TemplateSetError("Cannot delete read-only built-in CvSU Official template set")

        self._validate_set_id(set_id)
        set_dir = os.path.join(self.template_sets_dir, set_id)
        if not os.path.exists(set_dir):
            raise TemplateSetError(f"Template set '{set_id}' does not exist")

        if self.get_active_template_set_id() == set_id:
            logger.info(f"Active template set '{set_id}' deleted; reverting active set to '{BUILTIN_SET_ID}'")
            self.activate_template_set(BUILTIN_SET_ID)

        shutil.rmtree(set_dir)
        logger.info(f"Deleted template set '{set_id}'")
        return True

    def duplicate_template_set(self, source_set_id: str, new_name: str) -> TemplateSet:
        """Duplicates an existing template set (built-in or user) into a new user set."""
        source = self.get_template_set(source_set_id)
        if not source:
            raise TemplateSetError(f"Source template set '{source_set_id}' not found")

        new_ts = self.create_template_set(
            display_name=new_name,
            description=f"Duplicate of {source.display_name}",
            fallback_to_default=source.fallback_to_default,
        )

        for role, entry in source.templates.items():
            if os.path.exists(entry.file_path):
                self.add_template_to_set(
                    set_id=new_ts.set_id,
                    role=role,
                    file_path=entry.file_path,
                    display_metadata=entry.display_metadata,
                )

        return self.get_template_set(new_ts.set_id)

    # ══ Template Assignment & Validation ══════════════════════════════════════
    def add_template_to_set(
        self,
        set_id: str,
        role: str,
        file_path: str,
        display_metadata: Optional[Dict[str, Any]] = None,
    ) -> TemplateSet:
        """
        Validates and copies a physical template file into the specified template set.
        Enforces that declared role + physical inspection + RecipeValidator all pass.
        """
        if set_id == BUILTIN_SET_ID:
            raise TemplateSetError("Cannot add templates to the built-in CvSU Official set")

        if role not in CANONICAL_ROLES:
            raise InvalidTemplateSetError(f"Unknown canonical role '{role}'")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Template file not found: {file_path}")

        # 1. Authoritative physical validation
        sheet_selection = (display_metadata or {}).get("sheet_mapping")
        is_valid, err, validated = self._role_detector.validate_role(
            file_path, role, sheet_selection=sheet_selection
        )
        if not is_valid:
            raise InvalidTemplateSetError(
                f"File '{os.path.basename(file_path)}' failed physical recipe validation for role '{role}': {err}"
            )

        ts = self.get_template_set(set_id)
        if not ts:
            raise TemplateSetError(f"Template set '{set_id}' not found")

        set_dir = os.path.join(self.template_sets_dir, set_id)
        templates_subfolder = os.path.join(set_dir, "templates")
        os.makedirs(templates_subfolder, exist_ok=True)

        orig_fn = os.path.basename(file_path)
        ext = os.path.splitext(orig_fn)[1].lower()
        safe_role_fn = f"{role}_{re.sub(r'[^a-zA-Z0-9_.-]+', '_', orig_fn)}"
        dest_path = os.path.join(templates_subfolder, safe_role_fn)

        shutil.copy2(file_path, dest_path)

        meta = dict(display_metadata or {})
        meta["original_filename"] = orig_fn
        meta["file_size_bytes"] = os.path.getsize(dest_path)
        meta["verified_at"] = datetime.now(timezone.utc).isoformat()

        entry = TemplateEntry(
            role=role,
            file_path=os.path.normpath(dest_path),
            file_type=ROLE_FILE_TYPE_MAPPING[role],
            profile_id=ROLE_PROFILE_MAPPING[role],
            enabled=True,
            display_metadata=meta,
        )

        ts.templates[role] = entry
        ts.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_manifest(ts, set_dir)
        logger.info(f"Added template for role '{role}' to template set '{set_id}'")
        return ts

    def remove_template_from_set(self, set_id: str, role: str) -> TemplateSet:
        """Removes a template role entry and deletes its copy from the set."""
        if set_id == BUILTIN_SET_ID:
            raise TemplateSetError("Cannot remove templates from built-in CvSU Official set")

        ts = self.get_template_set(set_id)
        if not ts:
            raise TemplateSetError(f"Template set '{set_id}' not found")

        entry = ts.templates.get(role)
        if entry:
            if os.path.exists(entry.file_path):
                try:
                    os.remove(entry.file_path)
                except Exception as e:
                    logger.warning(f"Could not remove physical file {entry.file_path}: {e}")
            del ts.templates[role]
            ts.updated_at = datetime.now(timezone.utc).isoformat()
            set_dir = os.path.join(self.template_sets_dir, set_id)
            self._save_manifest(ts, set_dir)
            logger.info(f"Removed role '{role}' from template set '{set_id}'")

        return ts

    # ══ Active Template Resolution ════════════════════════════════════════════
    def resolve_template(
        self,
        role: str,
        active_set: Optional[TemplateSet] = None,
    ) -> TemplateEntry:
        """
        Resolves the physical template entry for the given role against the active set.
        Applies fallback policy strictly:
          - If active set provides the role -> returns user template.
          - If active set lacks the role AND fallback_to_default is True -> returns built-in template.
          - If active set lacks the role AND fallback_to_default is False -> raises MissingTemplateRoleError.
        """
        if role not in CANONICAL_ROLES:
            raise InvalidTemplateSetError(f"Cannot resolve unknown template role '{role}'")

        target_set = active_set or self.get_active_template_set()
        resolved = target_set.resolve(role)

        if resolved is not None:
            return resolved

        # Role is missing in target set
        if target_set.fallback_to_default or target_set.is_builtin:
            builtin = self.get_builtin_set()
            builtin_entry = builtin.resolve(role)
            if builtin_entry is not None:
                logger.debug(f"Falling back to built-in template for role '{role}'")
                return builtin_entry

        raise MissingTemplateRoleError(
            f"Active template set '{target_set.display_name}' lacks required template for role '{role}' "
            f"and fallback to CvSU default templates is disabled (Fallback: OFF)."
        )

    # ══ Import / Export ═══════════════════════════════════════════════════════
    def export_template_set(self, set_id: str, destination_path: str) -> str:
        """
        Exports a template set as a portable .cvstemplateset.zip package.
        Package contains manifest.json and physical templates/.
        Cached recipes are NOT authoritative in exported packages and will be rebuilt on import.
        """
        ts = self.get_template_set(set_id)
        if not ts:
            raise TemplateSetError(f"Template set '{set_id}' not found")

        dest_dir = os.path.dirname(os.path.abspath(destination_path))
        os.makedirs(dest_dir, exist_ok=True)

        with zipfile.ZipFile(destination_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write manifest
            manifest_data = ts.to_dict()
            # In exported manifest, ensure file paths are relative to package root
            for role, entry in ts.templates.items():
                if os.path.exists(entry.file_path):
                    arcname = f"templates/{role}_{os.path.basename(entry.file_path)}"
                    zf.write(entry.file_path, arcname)
                    manifest_data["templates"][role]["file_path"] = arcname

            zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))

        logger.info(f"Exported template set '{set_id}' to {destination_path}")
        return destination_path

    def import_template_set(self, source_zip_path: str) -> TemplateSet:
        """
        Imports a portable template-set zip package.
        Validates all physical templates through TemplateRoleDetector and RecipeValidator.
        Rebuilds recipes safely.
        """
        if not os.path.exists(source_zip_path):
            raise FileNotFoundError(f"Template package not found: {source_zip_path}")

        temp_dir = tempfile.mkdtemp(prefix="cvsu_import_")
        try:
            with zipfile.ZipFile(source_zip_path, "r") as zf:
                # Security: Check for path traversal in zip entries
                for member in zf.namelist():
                    norm = os.path.normpath(member)
                    if norm.startswith("..") or os.path.isabs(norm):
                        raise InvalidTemplateSetError(f"Path traversal detected in package member '{member}'")
                zf.extractall(temp_dir)

            manifest_path = os.path.join(temp_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                raise InvalidTemplateSetError("Package missing required manifest.json")

            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_set_id = data.get("set_id") or "imported_set"
            display_name = data.get("display_name") or "Imported Set"

            # Validate each physical template in package
            raw_templates = data.get("templates") or {}
            validated_entries = []

            for role, entry_dict in raw_templates.items():
                if role not in CANONICAL_ROLES:
                    continue
                rel_path = entry_dict.get("file_path", "")
                full_path = os.path.normpath(os.path.join(temp_dir, rel_path))
                if not os.path.exists(full_path):
                    continue

                meta_dict = entry_dict.get("display_metadata", {})
                sheet_sel = meta_dict.get("sheet_mapping") if isinstance(meta_dict, dict) else None
                is_valid, err, val_recipe = self._role_detector.validate_role(full_path, role, sheet_selection=sheet_sel)
                if not is_valid:
                    raise InvalidTemplateSetError(
                        f"Imported template for role '{role}' failed physical validation: {err}"
                    )
                validated_entries.append((role, full_path, meta_dict))

            # Create destination user set
            new_ts = self.create_template_set(
                display_name=display_name,
                description=data.get("description", "Imported template set"),
                fallback_to_default=bool(data.get("fallback_to_default", False)),
            )

            for role, full_path, meta in validated_entries:
                self.add_template_to_set(
                    set_id=new_ts.set_id,
                    role=role,
                    file_path=full_path,
                    display_metadata=meta,
                )

            logger.info(f"Successfully imported template set as '{new_ts.set_id}'")
            return self.get_template_set(new_ts.set_id)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ══ Internal Utilities ════════════════════════════════════════════════════
    def _validate_set_id(self, set_id: str):
        if not set_id or not re.match(r"^[a-zA-Z0-9_\-]+$", set_id):
            raise InvalidTemplateSetError(
                f"Invalid set_id '{set_id}'. Must be alphanumeric with hyphens or underscores only."
            )

    def _save_manifest(self, ts: TemplateSet, set_dir: str):
        manifest_path = os.path.join(set_dir, "manifest.json")
        with tempfile.NamedTemporaryFile("w", dir=set_dir, delete=False, encoding="utf-8") as tf:
            json.dump(ts.to_dict(base_dir=set_dir), tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, manifest_path)
