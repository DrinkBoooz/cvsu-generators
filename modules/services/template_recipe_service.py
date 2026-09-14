#!/usr/bin/env python3
"""
modules/services/template_recipe_service.py

Shared Template Recipe Resolution Service for Authoritative Dynamic Template Discovery.
Manages absolute path resolution, SHA-256 fingerprinting, 3-tuple caching,
stale cache invalidation, inspector dispatch, and validation execution.
"""

import os
import hashlib
from typing import Dict, Tuple, Optional, Any, Callable

from modules.models.recipe import (
    TemplateError,
    GeneratorProfile,
    PROFILE_REGISTRY,
    PROFILE_ACADEMIC_DOCX,
    RawTemplateRecipeCandidate,
    ValidatedTemplateRecipe,
)
from modules.parsers.recipe_validator import RecipeValidator


class TemplateRecipeResolver:
    """
    Unified resolver service for template recipes.
    Keyed on: (absolute_path, profile_id, sha256_fingerprint).
    """

    def __init__(self):
        # Cache map: (absolute_path, profile_id, fingerprint) -> ValidatedTemplateRecipe
        self._cache: Dict[Tuple[str, str, str], ValidatedTemplateRecipe] = {}
        # Path index tracking latest fingerprint: (absolute_path, profile_id) -> fingerprint
        self._fingerprint_index: Dict[Tuple[str, str], str] = {}
        # Custom inspector overrides (useful for testing or specialized families)
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
        """Registers an inspector instance for a file extension (e.g. '.docx', '.xlsx')."""
        self._inspectors[extension.lower()] = inspector

    def get_inspector_for_path(self, file_path: str) -> Any:
        """Selects appropriate inspector based on file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self._inspectors:
            return self._inspectors[ext]

        if ext == ".docx":
            from modules.parsers.template_inspector import DocxTemplateInspector
            return DocxTemplateInspector()
        elif ext in (".xlsx", ".xls"):
            from modules.parsers.template_inspector import XlsxTemplateInspector
            return XlsxTemplateInspector()
        else:
            raise TemplateError(f"Unsupported template file extension '{ext}' for '{file_path}'")

    def resolve_recipe(
        self,
        template_path: str,
        profile_id: str = "academic_docx",
        force_reinspect: bool = False,
    ) -> ValidatedTemplateRecipe:
        """
        Resolves an authoritative ValidatedTemplateRecipe for the given template path and profile.
        Handles caching, fingerprint checks, stale cache invalidation, candidate inspection,
        and validation.
        """
        if not template_path:
            raise TemplateError("Template path cannot be empty")

        abs_path = os.path.abspath(template_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Template file not found: {abs_path}")

        current_fp = self.compute_fingerprint(abs_path)
        cache_key = (abs_path, profile_id, current_fp)
        path_key = (abs_path, profile_id)

        # Check for stale cache entry (fingerprint mismatch)
        if path_key in self._fingerprint_index:
            last_fp = self._fingerprint_index[path_key]
            if last_fp != current_fp:
                # Invalidate old cached recipe
                old_key = (abs_path, profile_id, last_fp)
                self._cache.pop(old_key, None)

        if not force_reinspect and cache_key in self._cache:
            return self._cache[cache_key]

        # Resolve generator profile
        profile = PROFILE_REGISTRY.get(profile_id, PROFILE_ACADEMIC_DOCX)

        # Select inspector
        inspector = self.get_inspector_for_path(abs_path)

        # 1. Inspector emits raw candidate observations only
        candidate: RawTemplateRecipeCandidate = inspector.inspect(abs_path, profile_id=profile_id)
        # Ensure candidate carries correct path and fingerprint
        candidate.template_path = abs_path
        candidate.fingerprint = current_fp
        candidate.profile_id = profile_id

        # 2. RecipeValidator produces authoritative ValidatedTemplateRecipe
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
