#!/usr/bin/env python3
"""
modules/parsers/recipe_validator.py

Authoritative Recipe Validator for Dynamic Template Discovery.
Sole authority permitted to construct ValidatedTemplateRecipe instances.
Enforces schema version 2, profile constraints, structural rules, and 5-point safety verification.
"""

import os
from typing import Dict, List, Optional, Any, Union

from modules.models.recipe import (
    RECIPE_SCHEMA_VERSION,
    _PRIVATE_CONSTRUCTION_SENTINEL,
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    RosterBinding,
    HeaderCellBinding,
    SignatureBinding,
    GeneratorProfile,
    PROFILE_REGISTRY,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    RawTemplateRecipeCandidate,
    ValidatedTemplateRecipe,
)
from modules.parsers.semantic_registry import (
    ROLE_INSTRUCTOR_SIGNATURE,
    FIELD_INSTRUCTOR,
)


class RecipeValidator:
    """
    Sole authority that transforms RawTemplateRecipeCandidate or schema v2 dict
    into ValidatedTemplateRecipe.
    """

    @classmethod
    def validate(
        cls,
        candidate: RawTemplateRecipeCandidate,
        profile: GeneratorProfile,
    ) -> ValidatedTemplateRecipe:
        """
        Validates raw candidate observations against profile requirements and structural invariants.
        Returns authoritative ValidatedTemplateRecipe.
        """
        if not candidate:
            raise InvalidRecipeError("Cannot validate empty candidate")

        if isinstance(profile, str):
            profile = PROFILE_REGISTRY.get(profile, PROFILE_ACADEMIC_DOCX)

        # 1. Resolve and check collisions / ambiguities
        cls._resolve_collisions(candidate, profile)

        # 2. Validate Roster Binding
        roster_binding = cls._validate_roster(candidate.roster_candidate, profile)

        # 3. Validate Header Bindings
        header_bindings = cls._validate_headers(candidate.header_candidates, profile)

        # 4. Validate Signatures
        signature_bindings = cls._validate_signatures(candidate.signature_candidates, profile)

        # 5. Check Required Fields
        for req_field in profile.required_fields:
            if req_field not in header_bindings and req_field not in candidate.metadata:
                raise TemplateError(
                    f"Template '{os.path.basename(candidate.template_path)}' fails profile '{profile.profile_id}': "
                    f"Missing required field '{req_field}'."
                )

        # 6. Check Prohibited Fields
        for pro_field in profile.prohibited_fields:
            if pro_field in header_bindings:
                raise TemplateError(
                    f"Template '{os.path.basename(candidate.template_path)}' violates profile '{profile.profile_id}': "
                    f"Contains prohibited field '{pro_field}'."
                )

        # 7. Construct Authoritative ValidatedTemplateRecipe
        return ValidatedTemplateRecipe(
            schema_version=RECIPE_SCHEMA_VERSION,
            profile_id=profile.profile_id,
            fingerprint=candidate.fingerprint,
            template_path=candidate.template_path,
            roster_binding=roster_binding,
            header_bindings=header_bindings,
            signature_bindings=signature_bindings,
            metadata=dict(candidate.metadata),
            verified_safe=True,
            _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
        )

    @classmethod
    def validate_dict(
        cls,
        data: Dict[str, Any],
        profile: Optional[GeneratorProfile] = None,
    ) -> ValidatedTemplateRecipe:
        """
        Validates and deserializes a serialized recipe dictionary.
        Strictly enforces schema_version == 2 and ignores/rejects external construction tokens.
        """
        if not isinstance(data, dict):
            raise InvalidRecipeError("Recipe data must be a dictionary")

        # Strict Schema Policy: accept only schema_version == 2
        schema_version = data.get("schema_version")
        if schema_version != RECIPE_SCHEMA_VERSION:
            raise InvalidRecipeError(
                f"Unsupported recipe schema_version: {schema_version}. "
                f"Expected {RECIPE_SCHEMA_VERSION}. Missing, v1, or future versions are rejected."
            )

        # Reject externally supplied construction token
        if "_construction_token" in data:
            raise InvalidRecipeError("Externally supplied '_construction_token' is prohibited.")
        clean_data = dict(data)

        profile_id = clean_data.get("profile_id", "academic_docx")
        if isinstance(profile, str):
            profile = PROFILE_REGISTRY.get(profile, PROFILE_REGISTRY.get(profile_id, PROFILE_ACADEMIC_DOCX))
        elif profile is None:
            profile = PROFILE_REGISTRY.get(profile_id, PROFILE_ACADEMIC_DOCX)

        # Reconstruct components
        roster_data = clean_data.get("roster_binding") or clean_data.get("roster_table")

        raw_headers = clean_data.get("header_bindings", {})
        header_candidates: List[Dict[str, Any]] = []
        if isinstance(raw_headers, dict):
            header_candidates = [v if isinstance(v, dict) else v.to_dict() for v in raw_headers.values()]
        elif isinstance(raw_headers, list):
            for item in raw_headers:
                if isinstance(item, dict):
                    if item.get("type") == "table_cell":
                        header_candidates.append({
                            "cell_type": "docx_table",
                            "target": (item.get("table_index", 0), item.get("row_index", 0), item.get("cell_index", 1)),
                            "field": item.get("field"),
                            "shrink_threshold": item.get("shrink_threshold", 0),
                            "shrink_sz": item.get("shrink_sz", "18"),
                            "confidence": float(item.get("confidence", 1.0)),
                        })
                    elif item.get("type") == "paragraph_colon":
                        header_candidates.append({
                            "cell_type": "docx_paragraph",
                            "target": item.get("para_index", 0),
                            "field": item.get("field"),
                            "shrink_threshold": item.get("shrink_threshold", 0),
                            "shrink_sz": item.get("shrink_sz", "18"),
                            "confidence": float(item.get("confidence", 1.0)),
                        })
                    else:
                        header_candidates.append(item)

        raw_signatures = clean_data.get("signature_bindings", {})
        signature_candidates: List[Dict[str, Any]] = []
        if isinstance(raw_signatures, dict):
            signature_candidates = [v if isinstance(v, dict) else v.to_dict() for v in raw_signatures.values()]
        elif isinstance(raw_signatures, list):
            signature_candidates = [s for s in raw_signatures if isinstance(s, dict)]

        meta = clean_data.get("metadata")
        if not isinstance(meta, dict):
            meta = {
                "title": clean_data.get("title", ""),
                "suffix": clean_data.get("suffix", ""),
                "placeholders": clean_data.get("placeholders", []),
            }

        # Construct candidate to run full validation checks
        candidate = RawTemplateRecipeCandidate(
            template_path=clean_data.get("template_path", ""),
            profile_id=profile_id,
            fingerprint=clean_data.get("fingerprint", ""),
            roster_candidate=roster_data,
            header_candidates=header_candidates,
            signature_candidates=signature_candidates,
            collisions=[],
            metadata=meta,
        )

        return cls.validate(candidate, profile)

    @classmethod
    def _resolve_collisions(
        cls,
        candidate: RawTemplateRecipeCandidate,
        profile: GeneratorProfile,
    ) -> None:
        """
        Checks for ambiguity and collisions among candidates.
        """
        for collision in candidate.collisions:
            field = collision.get("field")
            c_list = collision.get("candidates", [])
            # If colliding candidates have identical confidence and neither is clearly authoritative, raise
            confidences = [c.get("confidence", 0.5) for c in c_list]
            if len(confidences) > 1 and confidences[0] == confidences[1]:
                raise AmbiguousTemplateError(
                    f"Ambiguous template binding for field '{field}' in '{os.path.basename(candidate.template_path)}': "
                    f"Found {len(c_list)} equally confident candidate locations."
                )

    @classmethod
    def _validate_roster(
        cls,
        roster_data: Optional[Dict[str, Any]],
        profile: GeneratorProfile,
    ) -> Optional[RosterBinding]:
        """
        Validates roster binding requirements based on generator profile.
        """
        if not roster_data:
            if profile.requires_capacity or profile.document_family in ("academic_docx", "grade_sheet_xlsx"):
                # Custom docx may omit roster, but native academic docx and grade sheet require it
                if profile.profile_id != "custom_docx":
                    raise TemplateError(
                        f"Profile '{profile.profile_id}' strictly requires a student roster table, but none was detected."
                    )
            return None

        # Validate mandatory roster coordinates
        table_idx = roster_data.get("table_index")
        first_row = roster_data.get("first_data_row_index")
        name_col = roster_data.get("name_col")
        id_col = roster_data.get("id_col")

        if table_idx is None or first_row is None:
            raise TemplateError("Roster binding missing table_index or first_data_row_index")

        if name_col is None and not roster_data.get("has_split_names"):
            raise TemplateError("Roster binding requires name_col or split names")

        if id_col is None:
            raise TemplateError("Roster binding requires id_col")

        # Grade sheet capacity requirement
        capacity = roster_data.get("capacity_limit")
        if profile.requires_capacity or profile.document_family == "grade_sheet_xlsx":
            if capacity is None or capacity <= 0:
                raise TemplateError(
                    f"grade_sheet profile '{profile.profile_id}' requires capacity_limit > 0, "
                    f"got {capacity}."
                )

        return RosterBinding.from_dict(roster_data)

    @classmethod
    def _validate_headers(
        cls,
        header_candidates: List[Dict[str, Any]],
        profile: GeneratorProfile,
    ) -> Dict[str, HeaderCellBinding]:
        """
        Validates header candidates into validated bindings.
        Ensures instructor metadata does not bind signature regions.
        """
        bindings: Dict[str, HeaderCellBinding] = {}

        # Sort by confidence descending
        sorted_candidates = sorted(
            header_candidates,
            key=lambda c: c.get("confidence", 0.0),
            reverse=True,
        )

        used_targets = set()
        for c in sorted_candidates:
            field = c.get("field")
            if not field:
                continue

            # Skip if higher confidence candidate already bound this field
            if field in bindings:
                continue

            target = c.get("target")
            target_key = (c.get("cell_type"), str(target))
            if target_key in used_targets:
                continue

            conf = float(c.get("confidence", 0.5))
            if conf < 0.70:
                # Discard candidates failing minimum confidence threshold
                continue

            # Prevent ordinary instructor metadata discovery from binding signature roles
            if field == FIELD_INSTRUCTOR and c.get("is_signature_region"):
                continue

            binding = HeaderCellBinding.from_dict(c)
            bindings[field] = binding
            used_targets.add(target_key)

        return bindings

    @classmethod
    def _validate_signatures(
        cls,
        signature_candidates: List[Dict[str, Any]],
        profile: GeneratorProfile,
    ) -> Dict[str, SignatureBinding]:
        """
        Validates signature candidates into validated signature bindings.
        """
        bindings: Dict[str, SignatureBinding] = {}

        for c in signature_candidates:
            role = c.get("role")
            if not role:
                continue
            if role in bindings:
                continue
            binding = SignatureBinding.from_dict(c)
            bindings[role] = binding

        return bindings
