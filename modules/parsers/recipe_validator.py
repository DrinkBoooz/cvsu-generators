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
    PROFILE_ATTENDANCE_DOCX,
    RawTemplateRecipeCandidate,
    RawAttendanceTemplateRecipeCandidate,
    ValidatedRecipeBase,
    ValidatedTemplateRecipe,
    ValidatedAttendanceTemplateRecipe,
    AttendanceInfoBinding,
    AttendanceMatrixBinding,
)
from modules.parsers.semantic_registry import (
    ROLE_INSTRUCTOR_SIGNATURE,
    FIELD_INSTRUCTOR,
)
from modules.common.path_utils import validate_output_folder


class RecipeValidator:
    """
    Sole authority that transforms RawTemplateRecipeCandidate or schema v2 dict
    into ValidatedTemplateRecipe.
    """

    @classmethod
    def validate(
        cls,
        candidate: Union[RawTemplateRecipeCandidate, RawAttendanceTemplateRecipeCandidate],
        profile: Union[GeneratorProfile, str],
    ) -> ValidatedRecipeBase:
        """
        Validates raw candidate observations against profile requirements and structural invariants.
        Returns authoritative ValidatedRecipeBase (ValidatedTemplateRecipe or ValidatedAttendanceTemplateRecipe).
        """
        if not candidate:
            raise InvalidRecipeError("Cannot validate empty candidate")

        if isinstance(profile, str):
            profile = PROFILE_REGISTRY.get(profile, PROFILE_ACADEMIC_DOCX)

        if isinstance(candidate, RawAttendanceTemplateRecipeCandidate):
            if profile.profile_id not in ("attendance_docx", "attendance"):
                raise TemplateError(
                    f"Template '{os.path.basename(candidate.template_path)}' is an attendance candidate "
                    f"and cannot be validated against profile '{profile.profile_id}'."
                )
            return cls._validate_attendance(candidate, profile)

        # Non-attendance candidate with attendance profile -> E18 fail closed
        if profile.profile_id in ("attendance_docx", "attendance"):
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' fails profile '{profile.profile_id}': "
                f"Candidate is {type(candidate).__name__} without required attendance matrix structure (E18)."
            )

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

        # 7. Ensure output_folder is validated in metadata
        metadata = dict(candidate.metadata)
        output_folder = metadata.get("output_folder", "CEIT_Forms")
        metadata["output_folder"] = validate_output_folder(output_folder, default="CEIT_Forms")

        # 8. Construct Authoritative ValidatedTemplateRecipe
        return ValidatedTemplateRecipe(
            schema_version=RECIPE_SCHEMA_VERSION,
            profile_id=profile.profile_id,
            fingerprint=candidate.fingerprint,
            template_path=candidate.template_path,
            roster_binding=roster_binding,
            header_bindings=header_bindings,
            signature_bindings=signature_bindings,
            metadata=metadata,
            verified_safe=True,
            _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
        )

    @classmethod
    def _validate_attendance(
        cls,
        candidate: RawAttendanceTemplateRecipeCandidate,
        profile: GeneratorProfile,
    ) -> ValidatedAttendanceTemplateRecipe:
        if candidate.collisions:
            raise AmbiguousTemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' has conflicting structural candidates: "
                f"{candidate.collisions}"
            )

        if not candidate.info_candidate:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' is missing required information table (E13)."
            )

        if not candidate.matrix_candidate:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' is missing required attendance matrix table (E11)."
            )

        info_cand = candidate.info_candidate
        tbl_idx = info_cand.get("table_index")
        bindings = info_cand.get("bindings", {})
        if tbl_idx is None or not bindings:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' information table bindings are invalid."
            )

        matrix_cand = candidate.matrix_candidate
        m_tbl_idx = matrix_cand.get("table_index")
        if m_tbl_idx is None:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' matrix table index is missing."
            )

        # E12: check student name and student number columns
        name_col = matrix_cand.get("name_col")
        id_col = matrix_cand.get("id_col")
        if name_col is None or id_col is None:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' missing student name or student number column (E12)."
            )

        # Check geometry
        date_start = matrix_cand.get("date_columns_start")
        if date_start is None or date_start < 0:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' has invalid date columns start (E16)."
            )

        session_capacity = matrix_cand.get("template_session_capacity", 0)
        if session_capacity <= 0:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' has invalid session capacity (E16)."
            )

        student_row_idx = matrix_cand.get("student_template_row_index")
        if student_row_idx is None or student_row_idx < 0:
            raise TemplateError(
                f"Template '{os.path.basename(candidate.template_path)}' has invalid student template row (E16)."
            )

        info_binding = AttendanceInfoBinding(
            table_index=tbl_idx,
            bindings=bindings,
        )

        total_cols = date_start + session_capacity + matrix_cand.get("summary_columns_count", 3)
        default_summary_indices = tuple(range(date_start + session_capacity, total_cols))

        matrix_binding = AttendanceMatrixBinding(
            table_index=m_tbl_idx,
            header_row0_index=matrix_cand.get("header_row0_index", 0),
            header_row1_index=matrix_cand.get("header_row1_index", 1),
            student_template_row_index=student_row_idx,
            no_col=matrix_cand.get("no_col", 0),
            name_col=name_col,
            id_col=id_col,
            date_columns_start=date_start,
            summary_columns_count=matrix_cand.get("summary_columns_count", 3),
            summary_column_names=tuple(matrix_cand.get("summary_column_names", ("lb", "lc", "r"))),
            template_session_capacity=session_capacity,
            template_student_row_capacity=matrix_cand.get("template_student_row_capacity", 40),
            week_template_cell_col=matrix_cand.get("week_template_cell_col", date_start),
            summary_header0_cell_col=matrix_cand.get("summary_header0_cell_col", default_summary_indices[0] if default_summary_indices else date_start + session_capacity),
            date_template_cell_col=matrix_cand.get("date_template_cell_col", date_start),
            summary_column_indices=tuple(matrix_cand.get("summary_column_indices", default_summary_indices)),
            summary_header1_cell_cols=tuple(matrix_cand.get("summary_header1_cell_cols", default_summary_indices)),
            student_date_template_cell_col=matrix_cand.get("student_date_template_cell_col", date_start),
            student_summary_cell_cols=tuple(matrix_cand.get("student_summary_cell_cols", default_summary_indices)),
        )

        metadata = dict(candidate.metadata)
        if "output_folder" not in metadata:
            metadata["output_folder"] = "Attendance"

        return ValidatedAttendanceTemplateRecipe(
            schema_version=RECIPE_SCHEMA_VERSION,
            profile_id=profile.profile_id if hasattr(profile, "profile_id") else "attendance_docx",
            fingerprint=candidate.fingerprint,
            template_path=candidate.template_path,
            info_binding=info_binding,
            matrix_binding=matrix_binding,
            metadata=metadata,
            verified_safe=True,
            _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
        )

    @classmethod
    def with_metadata(
        cls,
        recipe: ValidatedRecipeBase,
        extra_metadata: Dict[str, Any],
    ) -> ValidatedRecipeBase:
        """
        Produces a new ValidatedRecipe with extra/overridden metadata without mutating the original.
        """
        if isinstance(recipe, ValidatedTemplateRecipe):
            merged_meta = dict(recipe.metadata)
            merged_meta.update(extra_metadata)
            if "output_folder" in merged_meta:
                merged_meta["output_folder"] = validate_output_folder(merged_meta["output_folder"], default="CEIT_Forms")
            return ValidatedTemplateRecipe(
                schema_version=recipe.schema_version,
                profile_id=recipe.profile_id,
                fingerprint=recipe.fingerprint,
                template_path=recipe.template_path,
                roster_binding=recipe.roster_binding,
                header_bindings=dict(recipe.header_bindings),
                signature_bindings=dict(recipe.signature_bindings),
                metadata=merged_meta,
                verified_safe=recipe.verified_safe,
                _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
            )
        elif isinstance(recipe, ValidatedAttendanceTemplateRecipe):
            merged_meta = dict(recipe.metadata)
            merged_meta.update(extra_metadata)
            return ValidatedAttendanceTemplateRecipe(
                schema_version=recipe.schema_version,
                profile_id=recipe.profile_id,
                fingerprint=recipe.fingerprint,
                template_path=recipe.template_path,
                info_binding=recipe.info_binding,
                matrix_binding=recipe.matrix_binding,
                metadata=merged_meta,
                verified_safe=recipe.verified_safe,
                _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
            )
        raise TypeError(f"Unsupported recipe type: {type(recipe)}")

    @classmethod
    def validate_dict(
        cls,
        data: Dict[str, Any],
        profile: Optional[GeneratorProfile] = None,
    ) -> ValidatedRecipeBase:
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

        requested_prof = profile if profile is not None else clean_data.get("profile_id", "academic_docx")
        if isinstance(requested_prof, GeneratorProfile):
            profile = requested_prof
        elif isinstance(requested_prof, str):
            prof_key = requested_prof.strip().lower()
            if prof_key not in PROFILE_REGISTRY:
                raise TemplateError(f"Unknown generator profile ID '{requested_prof}'")
            profile = PROFILE_REGISTRY[prof_key]
        else:
            raise InvalidRecipeError(f"Invalid profile specification: {profile}")

        # Attendance deserialization & profile compatibility enforcement
        is_attendance_profile = profile.profile_id in ("attendance_docx", "attendance")
        has_attendance_bindings = "info_binding" in clean_data or "matrix_binding" in clean_data

        if not is_attendance_profile and has_attendance_bindings:
            raise InvalidRecipeError(
                f"Attendance data supplied with non-attendance profile '{profile.profile_id}'."
            )

        if is_attendance_profile:
            if not has_attendance_bindings:
                raise InvalidRecipeError(
                    f"Academic data supplied with attendance profile '{profile.profile_id}'."
                )

            info_d = clean_data.get("info_binding")
            matrix_d = clean_data.get("matrix_binding")
            if not isinstance(info_d, dict):
                raise InvalidRecipeError("Attendance recipe requires dictionary 'info_binding'.")
            if not isinstance(matrix_d, dict):
                raise InvalidRecipeError("Attendance recipe requires dictionary 'matrix_binding'.")

            # Check collisions
            if clean_data.get("collisions"):
                raise AmbiguousTemplateError(
                    f"Serialized recipe contains unresolved collisions: {clean_data['collisions']}"
                )

            tbl_idx = info_d.get("table_index")
            if tbl_idx is None or not isinstance(tbl_idx, int) or tbl_idx < 0:
                raise InvalidRecipeError("Attendance info_binding missing or invalid non-negative table_index.")

            bindings = info_d.get("bindings")
            if not bindings or not isinstance(bindings, dict):
                raise InvalidRecipeError("Attendance info_binding missing or empty bindings dictionary.")

            m_tbl_idx = matrix_d.get("table_index")
            if m_tbl_idx is None or not isinstance(m_tbl_idx, int) or m_tbl_idx < 0:
                raise InvalidRecipeError("Attendance matrix_binding missing or invalid non-negative table_index.")

            if tbl_idx == m_tbl_idx:
                raise AmbiguousTemplateError(
                    f"Table identity collision: info table and matrix table target identical index {tbl_idx}."
                )

            name_col = matrix_d.get("name_col")
            id_col = matrix_d.get("id_col")
            if name_col is None or not isinstance(name_col, int) or name_col < 0:
                raise InvalidRecipeError("Attendance matrix missing or invalid name_col.")
            if id_col is None or not isinstance(id_col, int) or id_col < 0:
                raise InvalidRecipeError("Attendance matrix missing or invalid id_col.")

            date_start = matrix_d.get("date_columns_start")
            if date_start is None or not isinstance(date_start, int) or date_start < 0:
                raise InvalidRecipeError("Attendance matrix missing or invalid date_columns_start.")

            session_cap = matrix_d.get("template_session_capacity", 0)
            if not isinstance(session_cap, int) or session_cap <= 0:
                raise InvalidRecipeError("Attendance matrix template_session_capacity must be an integer > 0.")

            st_row = matrix_d.get("student_template_row_index")
            if st_row is None or not isinstance(st_row, int) or st_row < 0:
                raise InvalidRecipeError("Attendance matrix missing or invalid student_template_row_index.")

            info_binding = AttendanceInfoBinding.from_dict(info_d)
            matrix_binding = AttendanceMatrixBinding.from_dict(matrix_d)
            metadata = dict(clean_data.get("metadata", {}))
            if "output_folder" not in metadata:
                metadata["output_folder"] = "Attendance"
            metadata["output_folder"] = validate_output_folder(metadata["output_folder"], default="Attendance")

            return ValidatedAttendanceTemplateRecipe(
                schema_version=RECIPE_SCHEMA_VERSION,
                profile_id=profile.profile_id,
                fingerprint=clean_data.get("fingerprint", ""),
                template_path=clean_data.get("template_path", ""),
                info_binding=info_binding,
                matrix_binding=matrix_binding,
                metadata=metadata,
                verified_safe=clean_data.get("verified_safe", True),
                _construction_token=_PRIVATE_CONSTRUCTION_SENTINEL,
            )

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
                "output_folder": clean_data.get("output_folder", "CEIT_Forms"),
                "placeholders": clean_data.get("placeholders", []),
            }
        else:
            meta = dict(meta)
            if "output_folder" not in meta and "output_folder" in clean_data:
                meta["output_folder"] = clean_data["output_folder"]

        # Construct candidate to run full validation checks
        candidate = RawTemplateRecipeCandidate(
            template_path=clean_data.get("template_path", ""),
            profile_id=profile.profile_id,
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

        worksheet_name = roster_data.get("worksheet_name")
        if worksheet_name is not None and not isinstance(worksheet_name, str):
            raise TemplateError("Roster binding worksheet_name must be a string")

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

        # Validate multi-row header structure if specified
        header_row_idx = roster_data.get("header_row_index", 0)
        header_row_cnt = roster_data.get("header_row_count", 1)
        if header_row_cnt < 1:
            raise TemplateError(f"header_row_count must be >= 1, got {header_row_cnt}")
        if first_row < header_row_idx + header_row_cnt:
            raise TemplateError(
                f"first_data_row_index ({first_row}) cannot precede headers "
                f"(header_row_index {header_row_idx} + count {header_row_cnt})"
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

            # Respect profile allowed_fields restriction if defined
            if profile.allowed_fields is not None and field not in profile.allowed_fields:
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
