#!/usr/bin/env python3
"""
modules/services/template_recipe_service.py

Shared Template Recipe Resolution Service for Authoritative Dynamic Template Discovery.
Manages absolute path resolution, SHA-256 fingerprinting, 3-tuple caching,
stale cache invalidation, inspector dispatch, and validation execution.
"""

import os
import hashlib
from typing import Dict, Tuple, Optional, Any, Callable, Union

from modules.models.recipe import (
    RECIPE_SCHEMA_VERSION,
    TemplateError,
    GeneratorProfile,
    PROFILE_REGISTRY,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_ATTENDANCE_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    PROFILE_CUSTOM_DOCX,
    RawTemplateRecipeCandidate,
    RawAttendanceTemplateRecipeCandidate,
    ValidatedRecipeBase,
    ValidatedTemplateRecipe,
    ValidatedAttendanceTemplateRecipe,
)
from modules.parsers.recipe_validator import RecipeValidator


class TemplateRecipeResolver:
    """
    Unified resolver service for template recipes.
    Keyed on 4-tuple: (absolute_path, profile_id, sha256_fingerprint, RECIPE_SCHEMA_VERSION).
    Dispatches inspectors using 4-tier profile-aware precedence.
    """

    # Canonical profile-to-inspector mapping
    CANONICAL_INSPECTORS = {
        (".docx", "attendance_docx"): "AttendanceTemplateInspector",
        (".docx", "attendance"): "AttendanceTemplateInspector",
        (".docx", "academic_docx"): "DocxTemplateInspector",
        (".docx", "custom_docx"): "DocxTemplateInspector",
        (".docx", "syllabus"): "DocxTemplateInspector",
        (".docx", "exam_midterm"): "DocxTemplateInspector",
        (".docx", "exam_finals"): "DocxTemplateInspector",
        (".docx", "tos_midterm"): "DocxTemplateInspector",
        (".docx", "tos_finals"): "DocxTemplateInspector",
        (".docx", "grade_midterm"): "DocxTemplateInspector",
        (".docx", "grade_finals"): "DocxTemplateInspector",
        (".xlsx", "grade_sheet_xlsx"): "XlsxTemplateInspector",
        (".xlsx", "grade_sheet"): "XlsxTemplateInspector",
        (".xls", "grade_sheet_xlsx"): "XlsxTemplateInspector",
        (".xls", "grade_sheet"): "XlsxTemplateInspector",
    }

    def __init__(self):
        # Cache map: (absolute_path, profile_id, fingerprint, schema_version) -> ValidatedRecipeBase
        self._cache: Dict[Tuple[str, str, str, int], ValidatedRecipeBase] = {}
        # Path index tracking latest fingerprint: (absolute_path, profile_id, schema_version) -> fingerprint
        self._fingerprint_index: Dict[Tuple[str, str, int], str] = {}
        # Exact registrations: (extension, profile_id) -> inspector instance or class
        self._exact_inspectors: Dict[Tuple[str, str], Any] = {}
        # Legacy extension-only overrides: extension -> inspector instance or class
        self._inspectors: Dict[str, Any] = {}

    @staticmethod
    def compute_fingerprint(file_path: str) -> str:
        """Calculates SHA-256 hex digest of the physical template file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Template file not found for fingerprinting: {file_path}")
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def register_inspector(self, extension: str, inspector: Any) -> None:
        """Registers a legacy inspector instance for a file extension (e.g. '.docx', '.xlsx')."""
        self._inspectors[extension.lower()] = inspector

    def register_profile_inspector(self, extension: str, profile_id: str, inspector: Any) -> None:
        """Registers an explicit (extension, profile_id) inspector override."""
        self._exact_inspectors[(extension.lower(), profile_id.lower())] = inspector

    def get_inspector(self, file_path: str, profile_id: str = "academic_docx") -> Any:
        """
        Selects inspector following authoritative 4-tier precedence:
        1. Exact (extension, profile_id) registration
        2. Canonical profile mapping
        3. Legacy extension-only registration
        4. Unsupported -> TemplateError
        """
        ext = os.path.splitext(file_path)[1].lower()
        prof = str(profile_id).strip().lower()

        # 1. Exact (extension, profile_id) registration override
        if (ext, prof) in self._exact_inspectors:
            insp = self._exact_inspectors[(ext, prof)]
            return insp() if isinstance(insp, type) else insp

        # 2. Explicit extension registration override
        if ext in self._inspectors:
            insp = self._inspectors[ext]
            return insp() if isinstance(insp, type) else insp

        # 3. Canonical profile mapping
        if (ext, prof) in self.CANONICAL_INSPECTORS:
            name = self.CANONICAL_INSPECTORS[(ext, prof)]
            if name == "AttendanceTemplateInspector":
                from modules.parsers.template_inspector import AttendanceTemplateInspector
                return AttendanceTemplateInspector()
            elif name == "DocxTemplateInspector":
                from modules.parsers.template_inspector import DocxTemplateInspector
                return DocxTemplateInspector()
            elif name == "XlsxTemplateInspector":
                from modules.parsers.template_inspector import XlsxTemplateInspector
                return XlsxTemplateInspector()

        # Check by document_family in profile registry
        profile_obj = PROFILE_REGISTRY.get(prof)
        if profile_obj and (ext, profile_obj.document_family.lower()) in self.CANONICAL_INSPECTORS:
            name = self.CANONICAL_INSPECTORS[(ext, profile_obj.document_family.lower())]
            if name == "AttendanceTemplateInspector":
                from modules.parsers.template_inspector import AttendanceTemplateInspector
                return AttendanceTemplateInspector()
            elif name == "DocxTemplateInspector":
                from modules.parsers.template_inspector import DocxTemplateInspector
                return DocxTemplateInspector()
            elif name == "XlsxTemplateInspector":
                from modules.parsers.template_inspector import XlsxTemplateInspector
                return XlsxTemplateInspector()

        # Extension fallbacks for backward compatibility
        if ext == ".docx":
            from modules.parsers.template_inspector import DocxTemplateInspector
            return DocxTemplateInspector()
        elif ext in (".xlsx", ".xls"):
            from modules.parsers.template_inspector import XlsxTemplateInspector
            return XlsxTemplateInspector()

        # 4. Unsupported -> TemplateError
        raise TemplateError(
            f"Unsupported template combination: extension '{ext}', profile '{profile_id}' for '{file_path}'"
        )

    def get_inspector_for_path(self, file_path: str) -> Any:
        """Backward-compatible extension-only inspector selector."""
        return self.get_inspector(file_path, profile_id="academic_docx")

    def resolve_recipe(
        self,
        template_path: str,
        profile_id: str = "academic_docx",
        force_reinspect: bool = False,
    ) -> ValidatedRecipeBase:
        """
        Resolves an authoritative ValidatedRecipeBase for the given template path and profile.
        Handles caching with 4-tuple key (abs_path, profile_id, sha256, schema_version),
        fingerprint checks, stale cache invalidation, candidate inspection, and validation.
        """
        if not template_path:
            raise TemplateError("Template path cannot be empty")

        abs_path = os.path.abspath(template_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Template file not found: {abs_path}")

        current_fp = self.compute_fingerprint(abs_path)
        cache_key = (abs_path, profile_id, current_fp, RECIPE_SCHEMA_VERSION)
        path_key = (abs_path, profile_id, RECIPE_SCHEMA_VERSION)

        # Check for stale cache entry (fingerprint mismatch)
        if path_key in self._fingerprint_index:
            last_fp = self._fingerprint_index[path_key]
            if last_fp != current_fp:
                # Invalidate old cached recipe
                old_key = (abs_path, profile_id, last_fp, RECIPE_SCHEMA_VERSION)
                self._cache.pop(old_key, None)

        if not force_reinspect and cache_key in self._cache:
            return self._cache[cache_key]

        # Resolve generator profile
        profile = PROFILE_REGISTRY.get(profile_id, PROFILE_ACADEMIC_DOCX)

        # Select inspector using 4-tier profile-aware dispatch
        inspector = self.get_inspector(abs_path, profile_id=profile_id)

        # 1. Inspector emits raw candidate observations only
        candidate = inspector.inspect(abs_path, profile_id=profile_id)
        candidate.template_path = abs_path
        candidate.fingerprint = current_fp
        candidate.profile_id = profile_id

        # 2. RecipeValidator produces authoritative ValidatedRecipeBase
        validated_recipe = RecipeValidator.validate(candidate, profile)

        # 3. Cache validated recipe
        self._cache[cache_key] = validated_recipe
        self._fingerprint_index[path_key] = current_fp

        return validated_recipe

    def invalidate(self, template_path: Optional[str] = None, profile_id: Optional[str] = None) -> None:
        """Invalidates cache entries for a specific path, profile, or clears entire cache."""
        if template_path is None:
            self._cache.clear()
            self._fingerprint_index.clear()
            return

        abs_path = os.path.abspath(template_path)
        keys_to_remove = [
            k for k in self._cache.keys()
            if k[0] == abs_path and (profile_id is None or k[1] == profile_id)
        ]
        for k in keys_to_remove:
            self._cache.pop(k, None)

        idx_keys = [
            k for k in self._fingerprint_index.keys()
            if k[0] == abs_path and (profile_id is None or k[1] == profile_id)
        ]
        for k in idx_keys:
            self._fingerprint_index.pop(k, None)

    resolve = resolve_recipe

    @classmethod
    def get_instance(cls) -> "TemplateRecipeResolver":
        """Returns the global shared TemplateRecipeResolver singleton."""
        return recipe_resolver


# Global singleton instance
recipe_resolver = TemplateRecipeResolver()
