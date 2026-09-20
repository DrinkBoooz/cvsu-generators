#!/usr/bin/env python3
"""
modules/models/recipe.py

Template recipe data models and domain entities for Authoritative Dynamic Template Discovery.
Strictly implements Schema Version 2 and private construction token guards.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Union


from types import MappingProxyType
from collections.abc import Mapping

RECIPE_SCHEMA_VERSION = 2

# Private construction sentinel known only within recipe_validator and this module.
_PRIVATE_CONSTRUCTION_SENTINEL = object()


def freeze_value(val: Any) -> Any:
    """Recursively converts dict -> MappingProxyType, list -> tuple, set -> frozenset."""
    if isinstance(val, (dict, Mapping)):
        return MappingProxyType({k: freeze_value(v) for k, v in val.items()})
    elif isinstance(val, (list, tuple)):
        return tuple(freeze_value(v) for v in val)
    elif isinstance(val, (set, frozenset)):
        return frozenset(freeze_value(v) for v in val)
    return val


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
class AttendanceInfoBinding:
    """Encapsulates discovered information table coordinates and field targets."""
    table_index: int
    bindings: Dict[str, Tuple[int, int]]  # field_name -> (row_idx, col_idx)

    def __post_init__(self):
        object.__setattr__(self, "bindings", freeze_value(dict(self.bindings)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_index": self.table_index,
            "bindings": {k: list(v) for k, v in self.bindings.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AttendanceInfoBinding":
        return cls(
            table_index=d["table_index"],
            bindings={k: tuple(v) for k, v in d.get("bindings", {}).items()},
        )


@dataclass(frozen=True)
class AttendanceMatrixBinding:
    """Encapsulates discovered attendance matrix table geometry and column indices."""
    table_index: int
    header_row0_index: int
    header_row1_index: int
    student_template_row_index: int
    no_col: int
    name_col: int
    id_col: int
    date_columns_start: int
    summary_columns_count: int
    summary_column_names: Tuple[str, ...]
    template_session_capacity: int
    template_student_row_capacity: int
    week_template_cell_col: int = 3
    summary_header0_cell_col: int = 7
    date_template_cell_col: int = 3
    summary_column_indices: Tuple[int, ...] = (7, 8, 9)
    summary_header1_cell_cols: Tuple[int, ...] = (7, 8, 9)
    student_date_template_cell_col: int = 3
    student_summary_cell_cols: Tuple[int, ...] = (7, 8, 9)
    summary_column_widths: Tuple[int, ...] = (212, 208, 133)
    row0_cell_count: Optional[int] = None
    row1_cell_count: Optional[int] = None
    student_row_cell_count: Optional[int] = None

    def __post_init__(self):
        object.__setattr__(self, "summary_column_names", tuple(self.summary_column_names))
        object.__setattr__(self, "summary_column_indices", tuple(self.summary_column_indices))
        object.__setattr__(self, "summary_header1_cell_cols", tuple(self.summary_header1_cell_cols))
        object.__setattr__(self, "student_summary_cell_cols", tuple(self.student_summary_cell_cols))
        object.__setattr__(self, "summary_column_widths", tuple(self.summary_column_widths))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "table_index": self.table_index,
            "header_row0_index": self.header_row0_index,
            "header_row1_index": self.header_row1_index,
            "student_template_row_index": self.student_template_row_index,
            "no_col": self.no_col,
            "name_col": self.name_col,
            "id_col": self.id_col,
            "date_columns_start": self.date_columns_start,
            "summary_columns_count": self.summary_columns_count,
            "summary_column_names": list(self.summary_column_names),
            "template_session_capacity": self.template_session_capacity,
            "template_student_row_capacity": self.template_student_row_capacity,
            "week_template_cell_col": self.week_template_cell_col,
            "summary_header0_cell_col": self.summary_header0_cell_col,
            "date_template_cell_col": self.date_template_cell_col,
            "summary_column_indices": list(self.summary_column_indices),
            "summary_header1_cell_cols": list(self.summary_header1_cell_cols),
            "student_date_template_cell_col": self.student_date_template_cell_col,
            "student_summary_cell_cols": list(self.student_summary_cell_cols),
            "summary_column_widths": list(self.summary_column_widths),
        }
        if self.row0_cell_count is not None:
            d["row0_cell_count"] = self.row0_cell_count
        if self.row1_cell_count is not None:
            d["row1_cell_count"] = self.row1_cell_count
        if self.student_row_cell_count is not None:
            d["student_row_cell_count"] = self.student_row_cell_count
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AttendanceMatrixBinding":
        date_start = d.get("date_columns_start", 3)
        session_cap = d.get("template_session_capacity", 4)
        summary_count = d.get("summary_columns_count", 3)
        summary_names = tuple(d.get("summary_column_names", ("lb", "lc", "r")))
        total_cols = date_start + session_cap + summary_count
        default_summary_indices = tuple(range(date_start + session_cap, total_cols))
        default_sum_w_map = {"lb": 212, "lc": 208, "r": 133}
        default_widths = tuple(default_sum_w_map.get(str(sn).lower(), 200) for sn in summary_names)
        summary_widths = tuple(d.get("summary_column_widths", default_widths))

        return cls(
            table_index=d["table_index"],
            header_row0_index=d.get("header_row0_index", 0),
            header_row1_index=d.get("header_row1_index", 1),
            student_template_row_index=d.get("student_template_row_index", 2),
            no_col=d.get("no_col", 0),
            name_col=d.get("name_col", 1),
            id_col=d.get("id_col", 2),
            date_columns_start=date_start,
            summary_columns_count=summary_count,
            summary_column_names=summary_names,
            template_session_capacity=session_cap,
            template_student_row_capacity=d.get("template_student_row_capacity", 40),
            week_template_cell_col=d.get("week_template_cell_col", date_start),
            summary_header0_cell_col=d.get("summary_header0_cell_col", default_summary_indices[0] if default_summary_indices else date_start + session_cap),
            date_template_cell_col=d.get("date_template_cell_col", date_start),
            summary_column_indices=tuple(d.get("summary_column_indices", default_summary_indices)),
            summary_header1_cell_cols=tuple(d.get("summary_header1_cell_cols", default_summary_indices)),
            student_date_template_cell_col=d.get("student_date_template_cell_col", date_start),
            student_summary_cell_cols=tuple(d.get("student_summary_cell_cols", default_summary_indices)),
            summary_column_widths=summary_widths,
            row0_cell_count=d.get("row0_cell_count"),
            row1_cell_count=d.get("row1_cell_count"),
            student_row_cell_count=d.get("student_row_cell_count"),
        )


@dataclass(frozen=True)
class RosterBinding:
    """Encapsulates student roster table coordinates and columns."""
    table_index: int
    first_data_row_index: int
    name_col: int
    id_col: int
    worksheet_name: Optional[str] = None
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
        if self.worksheet_name is not None:
            d["worksheet_name"] = self.worksheet_name
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
            worksheet_name=d.get("worksheet_name"),
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
    document_family: str  # "academic_docx", "grade_sheet_xlsx", "custom_docx", "attendance_docx"
    required_fields: Tuple[str, ...]
    prohibited_fields: Tuple[str, ...] = ()
    requires_capacity: bool = False
    supports_auto_scaling: bool = True
    allowed_fields: Optional[Tuple[str, ...]] = None
    canonical_inspector: str = "DocxTemplateInspector"


# Predefined generator profiles
PROFILE_ACADEMIC_DOCX = GeneratorProfile(
    profile_id="academic_docx",
    document_family="academic_docx",
    required_fields=("instructor", "course_section", "schedule_code", "subject"),
    prohibited_fields=(),
    requires_capacity=False,
    supports_auto_scaling=True,
    allowed_fields=(
        "instructor",
        "course_section",
        "schedule_code",
        "subject",
        "subject_code",
        "subject_title",
        "time_days_room",
        "semester_ay",
        "semester",
        "school_year",
        "college",
        "date",
        "period",
        "units",
    ),
    canonical_inspector="DocxTemplateInspector",
)

PROFILE_GRADE_SHEET_XLSX = GeneratorProfile(
    profile_id="grade_sheet_xlsx",
    document_family="grade_sheet_xlsx",
    required_fields=("instructor", "course_section", "schedule_code"),
    prohibited_fields=(),
    requires_capacity=True,
    supports_auto_scaling=False,
    canonical_inspector="XlsxTemplateInspector",
)

PROFILE_CUSTOM_DOCX = GeneratorProfile(
    profile_id="custom_docx",
    document_family="custom_docx",
    required_fields=(),
    prohibited_fields=(),
    requires_capacity=False,
    supports_auto_scaling=True,
    canonical_inspector="DocxTemplateInspector",
)

PROFILE_ATTENDANCE_DOCX = GeneratorProfile(
    profile_id="attendance_docx",
    document_family="attendance_docx",
    required_fields=("course_code_title", "class_schedule", "semester_ay", "instructor", "month_year"),
    prohibited_fields=(),
    requires_capacity=True,
    supports_auto_scaling=True,
    canonical_inspector="AttendanceTemplateInspector",
)

PROFILE_REGISTRY: Dict[str, GeneratorProfile] = {
    "academic_docx": PROFILE_ACADEMIC_DOCX,
    "grade_sheet_xlsx": PROFILE_GRADE_SHEET_XLSX,
    "grade_sheet": PROFILE_GRADE_SHEET_XLSX,
    "custom_docx": PROFILE_CUSTOM_DOCX,
    "attendance_docx": PROFILE_ATTENDANCE_DOCX,
    "attendance": PROFILE_ATTENDANCE_DOCX,
    # Specific subprofiles mapping to academic_docx
    "syllabus": PROFILE_ACADEMIC_DOCX,
    "exam_returns": PROFILE_ACADEMIC_DOCX,
    "exam_midterm": PROFILE_ACADEMIC_DOCX,
    "exam_finals": PROFILE_ACADEMIC_DOCX,
    "tos": PROFILE_ACADEMIC_DOCX,
    "tos_midterm": PROFILE_ACADEMIC_DOCX,
    "tos_finals": PROFILE_ACADEMIC_DOCX,
    "grade_discussion": PROFILE_ACADEMIC_DOCX,
    "grade_midterm": PROFILE_ACADEMIC_DOCX,
    "grade_finals": PROFILE_ACADEMIC_DOCX,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Inspection Candidates (Unvalidated)
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


@dataclass
class RawAttendanceTemplateRecipeCandidate:
    """
    Unvalidated candidate observations emitted strictly by AttendanceTemplateInspector.
    Inspectors NEVER construct or return ValidatedAttendanceTemplateRecipe.
    """
    template_path: str
    profile_id: str
    fingerprint: str
    info_candidate: Optional[Dict[str, Any]] = None
    matrix_candidate: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    collisions: List[Dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Validated Recipes (Authoritative)
# ═══════════════════════════════════════════════════════════════════════════════

class ValidatedRecipeBase:
    """
    Abstract base class for all authoritative validated template recipes.
    Protects instance immutability and enforces private construction sentinel token.
    """

    __slots__ = (
        "schema_version",
        "profile_id",
        "fingerprint",
        "template_path",
        "metadata",
        "verified_safe",
    )

    def __init__(
        self,
        schema_version: int,
        profile_id: str,
        fingerprint: str,
        template_path: str,
        metadata: Dict[str, Any],
        verified_safe: bool = True,
        _construction_token: Any = None,
    ):
        if _construction_token is not _PRIVATE_CONSTRUCTION_SENTINEL:
            raise PermissionError(
                f"{self.__class__.__name__} can only be constructed via RecipeValidator.validate(). "
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
        object.__setattr__(self, "metadata", freeze_value(dict(metadata)))
        object.__setattr__(self, "verified_safe", verified_safe)

    def __setattr__(self, key, value):
        raise TypeError(f"{self.__class__.__name__} is immutable; cannot modify {key}")

    def __delattr__(self, key):
        raise TypeError(f"{self.__class__.__name__} is immutable; cannot delete {key}")

    def with_metadata(self, extra_metadata: Dict[str, Any]) -> "ValidatedRecipeBase":
        from modules.parsers.recipe_validator import RecipeValidator
        return RecipeValidator.with_metadata(self, extra_metadata)


class ValidatedTemplateRecipe(ValidatedRecipeBase):
    """
    Authoritative, validated template recipe for Academic/Custom DOCX and Grading XLSX.
    Can ONLY be constructed via RecipeValidator.validate().
    Protected by private construction sentinel and AST lint rules.
    """

    __slots__ = (
        "roster_binding",
        "header_bindings",
        "signature_bindings",
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
        super().__init__(
            schema_version=schema_version,
            profile_id=profile_id,
            fingerprint=fingerprint,
            template_path=template_path,
            metadata=metadata,
            verified_safe=verified_safe,
            _construction_token=_construction_token,
        )

        object.__setattr__(self, "roster_binding", roster_binding)
        object.__setattr__(self, "header_bindings", freeze_value(dict(header_bindings)))
        object.__setattr__(self, "signature_bindings", freeze_value(dict(signature_bindings)))

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes recipe to plain dictionary for caching, persistence, or IPC.
        CRITICAL: _construction_token is NEVER included.
        """
        def _unfreeze(v):
            if isinstance(v, Mapping):
                return {k: _unfreeze(val) for k, val in v.items()}
            elif isinstance(v, tuple):
                return [_unfreeze(val) for val in v]
            return v

        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "fingerprint": self.fingerprint,
            "template_path": self.template_path,
            "roster_binding": self.roster_binding.to_dict() if self.roster_binding else None,
            "header_bindings": {k: v.to_dict() for k, v in self.header_bindings.items()},
            "signature_bindings": {k: v.to_dict() for k, v in self.signature_bindings.items()},
            "metadata": _unfreeze(self.metadata),
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


class ValidatedAttendanceTemplateRecipe(ValidatedRecipeBase):
    """
    Authoritative, validated template recipe for Attendance DOCX.
    Can ONLY be constructed via RecipeValidator.validate().
    Protected by private construction sentinel and AST lint rules.
    """

    __slots__ = (
        "info_binding",
        "matrix_binding",
    )

    def __init__(
        self,
        schema_version: int,
        profile_id: str,
        fingerprint: str,
        template_path: str,
        info_binding: AttendanceInfoBinding,
        matrix_binding: AttendanceMatrixBinding,
        metadata: Dict[str, Any],
        verified_safe: bool = True,
        _construction_token: Any = None,
    ):
        super().__init__(
            schema_version=schema_version,
            profile_id=profile_id,
            fingerprint=fingerprint,
            template_path=template_path,
            metadata=metadata,
            verified_safe=verified_safe,
            _construction_token=_construction_token,
        )

        object.__setattr__(self, "info_binding", info_binding)
        object.__setattr__(self, "matrix_binding", matrix_binding)

    def to_dict(self) -> Dict[str, Any]:
        def _unfreeze(v):
            if isinstance(v, Mapping):
                return {k: _unfreeze(val) for k, val in v.items()}
            elif isinstance(v, tuple):
                return [_unfreeze(val) for val in v]
            return v

        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "fingerprint": self.fingerprint,
            "template_path": self.template_path,
            "info_binding": self.info_binding.to_dict(),
            "matrix_binding": self.matrix_binding.to_dict(),
            "metadata": _unfreeze(self.metadata),
            "verified_safe": self.verified_safe,
        }

