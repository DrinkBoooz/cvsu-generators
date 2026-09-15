#!/usr/bin/env python3
"""
modules/models/recipe.py

Template recipe data models and domain entities for Authoritative Dynamic Template Discovery.
Strictly implements Schema Version 2 and private construction token guards.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Union


RECIPE_SCHEMA_VERSION = 2

# Private construction sentinel known only within recipe_validator and this module.
_PRIVATE_CONSTRUCTION_SENTINEL = object()


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Exceptions
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateError(Exception):
    """Base exception for all template parsing, inspection, and validation errors."""
    pass


class AmbiguousTemplateError(TemplateError):
    """Raised when conflicting candidate bindings are observed and cannot be resolved."""
    pass


class InvalidRecipeError(TemplateError):
    """Raised when a template recipe fails schema, structural, or safety validation."""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Recipe Component Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RosterBinding:
    """Encapsulates student roster table coordinates and columns."""
    table_index: int
    first_data_row_index: int
    name_col: int
    id_col: int
    has_split_names: bool = False
    last_name_col: Optional[int] = None
    first_name_col: Optional[int] = None
    middle_name_col: Optional[int] = None
    index_col: Optional[int] = None
    signature_col: Optional[int] = None
    capacity_limit: Optional[int] = None
    header_row_index: int = 0
    header_row_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "table_index": self.table_index,
            "first_data_row_index": self.first_data_row_index,
            "name_col": self.name_col,
            "id_col": self.id_col,
            "has_split_names": self.has_split_names,
            "header_row_index": self.header_row_index,
            "header_row_count": self.header_row_count,
        }
        if self.last_name_col is not None:
            d["last_name_col"] = self.last_name_col
        if self.first_name_col is not None:
            d["first_name_col"] = self.first_name_col
        if self.middle_name_col is not None:
            d["middle_name_col"] = self.middle_name_col
        if self.index_col is not None:
            d["index_col"] = self.index_col
        if self.signature_col is not None:
            d["signature_col"] = self.signature_col
        if self.capacity_limit is not None:
            d["capacity_limit"] = self.capacity_limit
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RosterBinding":
        return cls(
            table_index=d["table_index"],
            first_data_row_index=d.get("first_data_row_index", d.get("first_data_row", 1)),
            name_col=d["name_col"],
            id_col=d["id_col"],
            has_split_names=d.get("has_split_names", False),
            last_name_col=d.get("last_name_col"),
            first_name_col=d.get("first_name_col"),
            middle_name_col=d.get("middle_name_col"),
            index_col=d.get("index_col"),
            signature_col=d.get("signature_col"),
            capacity_limit=d.get("capacity_limit"),
            header_row_index=d.get("header_row_index", 0),
            header_row_count=d.get("header_row_count", 1),
        )


@dataclass(frozen=True)
class HeaderCellBinding:
    """Encapsulates a verified metadata cell/paragraph binding."""
    cell_type: str  # "docx_table", "docx_paragraph", "xlsx_cell"
    target: Any     # Tuple[int, int, int] (tbl, r, c), or int (para_idx), or str ("C1")
    field: str
    confidence: float = 1.0
    pattern: Optional[str] = None
    shrink_threshold: int = 0
    shrink_sz: str = "18"

    def to_dict(self) -> Dict[str, Any]:
        t = self.target
        if isinstance(t, tuple):
            t = list(t)
        return {
            "cell_type": self.cell_type,
            "target": t,
            "field": self.field,
            "confidence": self.confidence,
            "pattern": self.pattern,
            "shrink_threshold": self.shrink_threshold,
            "shrink_sz": self.shrink_sz,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HeaderCellBinding":
        t = d["target"]
        if isinstance(t, list):
            t = tuple(t)
        return cls(
            cell_type=d["cell_type"],
            target=t,
            field=d["field"],
            confidence=float(d.get("confidence", 1.0)),
            pattern=d.get("pattern"),
            shrink_threshold=int(d.get("shrink_threshold", 0)),
            shrink_sz=str(d.get("shrink_sz", "18")),
        )


@dataclass(frozen=True)
class SignatureBinding:
    """Encapsulates a verified signature target."""
    role: str
    target: Any     # Tuple[int, int, int], or int, or str
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        t = self.target
        if isinstance(t, tuple):
            t = list(t)
        return {
            "role": self.role,
            "target": t,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SignatureBinding":
        t = d["target"]
        if isinstance(t, list):
            t = tuple(t)
        return cls(
            role=d["role"],
            target=t,
            confidence=float(d.get("confidence", 1.0)),
        )


@dataclass(frozen=True)
class GeneratorProfile:
    """Defines requirements, constraints, and validation rules for a generator family."""
    profile_id: str
    document_family: str  # "academic_docx", "grade_sheet_xlsx", "custom_docx"
    required_fields: Tuple[str, ...]
    prohibited_fields: Tuple[str, ...] = ()
    requires_capacity: bool = False
    supports_auto_scaling: bool = True


# Predefined generator profiles
PROFILE_ACADEMIC_DOCX = GeneratorProfile(
    profile_id="academic_docx",
    document_family="academic_docx",
    required_fields=("instructor", "course_section", "schedule_code", "subject"),
    prohibited_fields=(),
    requires_capacity=False,
    supports_auto_scaling=True,
)

PROFILE_GRADE_SHEET_XLSX = GeneratorProfile(
    profile_id="grade_sheet_xlsx",
    document_family="grade_sheet_xlsx",
    required_fields=("instructor", "course_section", "schedule_code"),
    prohibited_fields=(),
    requires_capacity=True,
    supports_auto_scaling=False,
)

PROFILE_CUSTOM_DOCX = GeneratorProfile(
    profile_id="custom_docx",
    document_family="custom_docx",
    required_fields=(),
    prohibited_fields=(),
    requires_capacity=False,
    supports_auto_scaling=True,
)

PROFILE_REGISTRY: Dict[str, GeneratorProfile] = {
    "academic_docx": PROFILE_ACADEMIC_DOCX,
    "grade_sheet_xlsx": PROFILE_GRADE_SHEET_XLSX,
    "grade_sheet": PROFILE_GRADE_SHEET_XLSX,
    "custom_docx": PROFILE_CUSTOM_DOCX,
    # Specific subprofiles mapping to academic_docx
    "syllabus": PROFILE_ACADEMIC_DOCX,
    "exam_midterm": PROFILE_ACADEMIC_DOCX,
    "exam_finals": PROFILE_ACADEMIC_DOCX,
    "tos_midterm": PROFILE_ACADEMIC_DOCX,
    "tos_finals": PROFILE_ACADEMIC_DOCX,
    "grade_midterm": PROFILE_ACADEMIC_DOCX,
    "grade_finals": PROFILE_ACADEMIC_DOCX,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Inspection Candidate (Unvalidated)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class RawTemplateRecipeCandidate:
    """
    Unvalidated candidate observations emitted strictly by Template Inspectors.
    Inspectors NEVER construct or return ValidatedTemplateRecipe.
    """
    template_path: str
    profile_id: str
    fingerprint: str
    roster_candidate: Optional[Dict[str, Any]] = None
    header_candidates: List[Dict[str, Any]] = field(default_factory=list)
    signature_candidates: List[Dict[str, Any]] = field(default_factory=list)
    collisions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Validated Recipe (Authoritative)
# ═══════════════════════════════════════════════════════════════════════════════

class ValidatedTemplateRecipe:
    """
    Authoritative, validated template recipe.
    Can ONLY be constructed via RecipeValidator.validate().
    Protected by private construction sentinel and AST lint rules.
    """

    __slots__ = (
        "schema_version",
        "profile_id",
        "fingerprint",
        "template_path",
        "roster_binding",
        "header_bindings",
        "signature_bindings",
        "metadata",
        "verified_safe",
    )

    def __init__(
        self,
        schema_version: int,
        profile_id: str,
        fingerprint: str,
        template_path: str,
        roster_binding: Optional[RosterBinding],
        header_bindings: Dict[str, HeaderCellBinding],
        signature_bindings: Dict[str, SignatureBinding],
        metadata: Dict[str, Any],
        verified_safe: bool = True,
        _construction_token: Any = None,
    ):
        if _construction_token is not _PRIVATE_CONSTRUCTION_SENTINEL:
            raise PermissionError(
                "ValidatedTemplateRecipe can only be constructed via RecipeValidator.validate(). "
                "Direct instantiation is forbidden."
            )

        if schema_version != RECIPE_SCHEMA_VERSION:
            raise InvalidRecipeError(
                f"Unsupported recipe schema_version: {schema_version}. Expected {RECIPE_SCHEMA_VERSION}."
            )

        object.__setattr__(self, "schema_version", schema_version)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "fingerprint", fingerprint)
        object.__setattr__(self, "template_path", template_path)
        object.__setattr__(self, "roster_binding", roster_binding)
        object.__setattr__(self, "header_bindings", header_bindings)
        object.__setattr__(self, "signature_bindings", signature_bindings)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "verified_safe", verified_safe)

    def __setattr__(self, key, value):
        raise TypeError(f"ValidatedTemplateRecipe is immutable; cannot modify {key}")

    def __delattr__(self, key):
        raise TypeError(f"ValidatedTemplateRecipe is immutable; cannot delete {key}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes recipe to plain dictionary for caching, persistence, or IPC.
        CRITICAL: _construction_token is NEVER included.
        """
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "fingerprint": self.fingerprint,
            "template_path": self.template_path,
            "roster_binding": self.roster_binding.to_dict() if self.roster_binding else None,
            "header_bindings": {k: v.to_dict() for k, v in self.header_bindings.items()},
            "signature_bindings": {k: v.to_dict() for k, v in self.signature_bindings.items()},
            "metadata": dict(self.metadata),
            "verified_safe": self.verified_safe,
        }

    def get_header_binding(self, field_name: str) -> Optional[HeaderCellBinding]:
        return self.header_bindings.get(field_name)

    def get_header_target(self, field_name: str) -> Optional[Any]:
        b = self.header_bindings.get(field_name)
        return b.target if b else None

    def get_signature_target(self, role: str) -> Optional[Any]:
        b = self.signature_bindings.get(role)
        return b.target if b else None
