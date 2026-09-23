#!/usr/bin/env python3
"""
modules/models/template_set.py

Domain models and canonical roles for the User Template Set subsystem.
Preserves the architectural invariant:
  INSPECTOR DISCOVERS WHERE.
  VALIDATOR VERIFIES WHERE.
  GENERATOR CONSUMES WHERE.
  NO LAYER MAY FABRICATE MISSING TEMPLATE COORDINATES.

Template sets store manifest metadata and file references only.
Structural coordinates are NEVER stored in manifests and remain strictly
derived from physical templates via the authoritative inspector/validator pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import re
from typing import Dict, Any, List, Optional, Tuple


# ══ Canonical Roles ═══════════════════════════════════════════════════════════
ROLE_SYLLABUS = "syllabus"
ROLE_EXAM_RETURNS_MIDTERM = "exam_returns_midterm"
ROLE_EXAM_RETURNS_FINAL = "exam_returns_final"
ROLE_TOS_MIDTERM = "tos_midterm"
ROLE_TOS_FINAL = "tos_final"
ROLE_GRADE_DISCUSSION_MIDTERM = "grade_discussion_midterm"
ROLE_GRADE_DISCUSSION_FINAL = "grade_discussion_final"
ROLE_ATTENDANCE_LECTURE = "attendance_lecture"
ROLE_ATTENDANCE_LECTURE_LAB = "attendance_lecture_lab"
ROLE_GRADE_SHEET_LECTURE = "grade_sheet_lecture"
ROLE_GRADE_SHEET_LECTURE_LAB = "grade_sheet_lecture_lab"

CANONICAL_ROLES: Tuple[str, ...] = (
    ROLE_SYLLABUS,
    ROLE_EXAM_RETURNS_MIDTERM,
    ROLE_EXAM_RETURNS_FINAL,
    ROLE_TOS_MIDTERM,
    ROLE_TOS_FINAL,
    ROLE_GRADE_DISCUSSION_MIDTERM,
    ROLE_GRADE_DISCUSSION_FINAL,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_ATTENDANCE_LECTURE_LAB,
    ROLE_GRADE_SHEET_LECTURE,
    ROLE_GRADE_SHEET_LECTURE_LAB,
)

ACADEMIC_CEIT_ROLES: Tuple[str, ...] = (
    ROLE_SYLLABUS,
    ROLE_EXAM_RETURNS_MIDTERM,
    ROLE_EXAM_RETURNS_FINAL,
    ROLE_TOS_MIDTERM,
    ROLE_TOS_FINAL,
    ROLE_GRADE_DISCUSSION_MIDTERM,
    ROLE_GRADE_DISCUSSION_FINAL,
)

ATTENDANCE_ROLES: Tuple[str, ...] = (
    ROLE_ATTENDANCE_LECTURE,
    ROLE_ATTENDANCE_LECTURE_LAB,
)

GRADE_SHEET_ROLES: Tuple[str, ...] = (
    ROLE_GRADE_SHEET_LECTURE,
    ROLE_GRADE_SHEET_LECTURE_LAB,
)

ROLE_PROFILE_MAPPING: Dict[str, str] = {
    ROLE_SYLLABUS: "syllabus",
    ROLE_EXAM_RETURNS_MIDTERM: "exam_returns",
    ROLE_EXAM_RETURNS_FINAL: "exam_returns",
    ROLE_TOS_MIDTERM: "tos",
    ROLE_TOS_FINAL: "tos",
    ROLE_GRADE_DISCUSSION_MIDTERM: "grade_discussion",
    ROLE_GRADE_DISCUSSION_FINAL: "grade_discussion",
    ROLE_ATTENDANCE_LECTURE: "attendance_docx",
    ROLE_ATTENDANCE_LECTURE_LAB: "attendance_docx",
    ROLE_GRADE_SHEET_LECTURE: "grade_sheet_xlsx",
    ROLE_GRADE_SHEET_LECTURE_LAB: "grade_sheet_xlsx",
}

ROLE_FILE_TYPE_MAPPING: Dict[str, str] = {
    ROLE_SYLLABUS: "docx",
    ROLE_EXAM_RETURNS_MIDTERM: "docx",
    ROLE_EXAM_RETURNS_FINAL: "docx",
    ROLE_TOS_MIDTERM: "docx",
    ROLE_TOS_FINAL: "docx",
    ROLE_GRADE_DISCUSSION_MIDTERM: "docx",
    ROLE_GRADE_DISCUSSION_FINAL: "docx",
    ROLE_ATTENDANCE_LECTURE: "docx",
    ROLE_ATTENDANCE_LECTURE_LAB: "docx",
    ROLE_GRADE_SHEET_LECTURE: "xlsx",
    ROLE_GRADE_SHEET_LECTURE_LAB: "xlsx",
}

ROLE_DISPLAY_NAMES: Dict[str, str] = {
    ROLE_SYLLABUS: "Syllabus Acceptance",
    ROLE_EXAM_RETURNS_MIDTERM: "Exam Returns (Midterm)",
    ROLE_EXAM_RETURNS_FINAL: "Exam Returns (Final)",
    ROLE_TOS_MIDTERM: "Table of Specifications (Midterm)",
    ROLE_TOS_FINAL: "Table of Specifications (Final)",
    ROLE_GRADE_DISCUSSION_MIDTERM: "Grade Discussion (Midterm)",
    ROLE_GRADE_DISCUSSION_FINAL: "Grade Discussion (Final)",
    ROLE_ATTENDANCE_LECTURE: "Attendance Sheet (Lecture)",
    ROLE_ATTENDANCE_LECTURE_LAB: "Attendance Sheet (Lecture + Lab)",
    ROLE_GRADE_SHEET_LECTURE: "Grading Sheet (Lecture)",
    ROLE_GRADE_SHEET_LECTURE_LAB: "Grading Sheet (Lecture + Lab)",
}


# ══ Exceptions ════════════════════════════════════════════════════════════════
class TemplateSetError(Exception):
    """Base exception for Template Set operations."""
    pass


class InvalidTemplateSetError(TemplateSetError):
    """Raised when a template set manifest or structure is invalid."""
    pass


class MissingTemplateRoleError(TemplateSetError):
    """Raised when an active template set lacks a required role with fallback disabled."""
    pass


# ══ Domain Classes ════════════════════════════════════════════════════════════
@dataclass
class TemplateEntry:
    """
    Metadata representation of an individual template in a Template Set.
    Does NOT store structural coordinates.
    """
    role: str
    file_path: str
    file_type: str
    profile_id: str
    variant: Optional[str] = None
    enabled: bool = True
    display_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, relative_to: Optional[str] = None) -> Dict[str, Any]:
        p = self.file_path
        if relative_to and os.path.isabs(p):
            try:
                p = os.path.relpath(p, relative_to)
            except ValueError:
                p = self.file_path
        return {
            "role": self.role,
            "variant": self.variant,
            "file_path": p.replace("\\", "/"),
            "file_type": self.file_type,
            "profile_id": self.profile_id,
            "enabled": self.enabled,
            "display_metadata": dict(self.display_metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Optional[str] = None) -> "TemplateEntry":
        role = data.get("role")
        if not role or role not in CANONICAL_ROLES:
            raise InvalidTemplateSetError(f"Invalid or unrecognized template role: '{role}'")

        raw_path = data.get("file_path", "")
        if not raw_path:
            raise InvalidTemplateSetError(f"Missing file_path for template role '{role}'")

        # Path traversal guard
        if ".." in raw_path.replace("\\", "/").split("/"):
            raise InvalidTemplateSetError(f"Path traversal detected in template file_path: '{raw_path}'")

        if base_dir and not os.path.isabs(raw_path):
            abs_path = os.path.normpath(os.path.join(base_dir, raw_path))
        else:
            abs_path = os.path.normpath(raw_path)

        file_type = data.get("file_type") or ROLE_FILE_TYPE_MAPPING.get(role, "docx")
        expected_type = ROLE_FILE_TYPE_MAPPING.get(role)
        if expected_type and file_type != expected_type:
            raise InvalidTemplateSetError(
                f"Role '{role}' expects file_type '{expected_type}', got '{file_type}'"
            )

        profile_id = data.get("profile_id") or ROLE_PROFILE_MAPPING.get(role, "academic_docx")

        return cls(
            role=role,
            file_path=abs_path,
            file_type=file_type,
            profile_id=profile_id,
            variant=data.get("variant"),
            enabled=data.get("enabled", True),
            display_metadata=data.get("display_metadata") or {},
        )


@dataclass
class TemplateSet:
    """
    First-class model representing an institutional or departmental Template Set.
    Can be the read-only built-in default or a user-created set.
    """
    set_id: str
    display_name: str
    description: str = ""
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "user"  # "builtin" or "user"
    is_active: bool = False
    fallback_to_default: bool = False
    templates: Dict[str, TemplateEntry] = field(default_factory=dict)

    def __post_init__(self):
        # Validate set_id syntax: alphanumeric, dashes, underscores
        if not self.set_id or not re.match(r"^[a-zA-Z0-9_\-]+$", self.set_id):
            raise InvalidTemplateSetError(
                f"Invalid template set_id '{self.set_id}'. Must be non-empty and contain only letters, numbers, dashes, or underscores."
            )

    @property
    def is_builtin(self) -> bool:
        return self.source == "builtin"

    def resolve(self, role: str) -> Optional[TemplateEntry]:
        """Resolves an entry for the specified role if present and enabled."""
        entry = self.templates.get(role)
        if entry and entry.enabled and os.path.exists(entry.file_path):
            return entry
        return None

    def has_role(self, role: str) -> bool:
        return self.resolve(role) is not None

    def missing_roles(self) -> List[str]:
        """Returns the list of canonical roles not provided by this set."""
        missing = []
        for role in CANONICAL_ROLES:
            if not self.has_role(role):
                missing.append(role)
        return missing

    def is_complete(self) -> bool:
        """True if all 11 canonical roles are satisfied by valid physical files."""
        return len(self.missing_roles()) == 0

    def status(self) -> str:
        """Reports 'Complete', 'Incomplete', or 'Invalid'."""
        for role, entry in self.templates.items():
            if not os.path.exists(entry.file_path):
                return "Invalid"
        if self.is_complete():
            return "Complete"
        return "Incomplete"

    def to_dict(self, base_dir: Optional[str] = None) -> Dict[str, Any]:
        """Serializes manifest dictionary. Never serializes structural coordinates."""
        return {
            "set_id": self.set_id,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "is_active": self.is_active,
            "fallback_to_default": self.fallback_to_default,
            "templates": {
                role: entry.to_dict(relative_to=base_dir)
                for role, entry in self.templates.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Optional[str] = None) -> "TemplateSet":
        set_id = data.get("set_id")
        if not set_id:
            raise InvalidTemplateSetError("Manifest missing required 'set_id'")

        display_name = data.get("display_name") or set_id
        description = data.get("description", "")
        version = data.get("version", "1.0.0")
        created_at = data.get("created_at") or datetime.now(timezone.utc).isoformat()
        updated_at = data.get("updated_at") or datetime.now(timezone.utc).isoformat()
        source = data.get("source", "user")
        is_active = bool(data.get("is_active", False))
        fallback_to_default = bool(data.get("fallback_to_default", False))

        raw_templates = data.get("templates") or {}
        entries: Dict[str, TemplateEntry] = {}
        for role, entry_dict in raw_templates.items():
            if role in CANONICAL_ROLES and isinstance(entry_dict, dict):
                entries[role] = TemplateEntry.from_dict(entry_dict, base_dir=base_dir)

        return cls(
            set_id=set_id,
            display_name=display_name,
            description=description,
            version=version,
            created_at=created_at,
            updated_at=updated_at,
            source=source,
            is_active=is_active,
            fallback_to_default=fallback_to_default,
            templates=entries,
        )
