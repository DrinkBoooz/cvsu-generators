#!/usr/bin/env python3
"""
modules/models/organization.py

Data models for Dynamic Organizational Topology & N-Tier Signatory Chains.
Enables campus-agnostic and unit-agnostic document generation for any Cavite State University
academic unit, department, or satellite campus without hardcoded college/campus lists or
fixed "Chair/Dean" assumptions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OrganizationalContext:
    """
    Introspected institutional and collegiate topology for a template.
    Discovered dynamically from document banners and header tables.
    """
    institution: str = "CAVITE STATE UNIVERSITY"
    campus: Optional[str] = None
    college: Optional[str] = None
    department: Optional[str] = None
    raw_headers: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrganizationalContext:
        clean = dict(data)
        return cls(**clean)


@dataclass
class SignatorySlot:
    """
    Declarative binding slot for an N-tier signatory role in a document template.
    Captures role labels (e.g. 'Recommending Approval:'), target coordinates for the signatory's
    name and signature line, default title (e.g. 'Campus Administrator', 'Department Chairperson'),
    and the bound context key.
    """
    slot_id: str
    role_label: str
    default_title: str = ""
    bound_key: str = ""
    slot_type: str = "table_cell"  # "table_cell" | "paragraph" | "excel_cell"
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    target_row_index: Optional[int] = None
    target_col_index: Optional[int] = None
    paragraph_index: Optional[int] = None
    target_paragraph_index: Optional[int] = None
    title_row_index: Optional[int] = None
    title_col_index: Optional[int] = None
    title_paragraph_index: Optional[int] = None
    sheet_name: Optional[str] = None
    cell_coord: Optional[str] = None
    target_cell_coord: Optional[str] = None
    title_cell_coord: Optional[str] = None
    strategy: str = "set_cell_text"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SignatorySlot:
        clean = dict(data)
        return cls(**clean)


@dataclass
class OrganizationPreset:
    """
    Shareable, persistent configuration preset (.cvsu-org.json) representing an
    academic unit's organizational hierarchy and signatory chain.
    """
    version: str = "1.0"
    campus: str = ""
    college: str = ""
    department: str = ""
    signatories: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OrganizationPreset:
        clean = dict(data)
        return cls(
            version=clean.get("version", "1.0"),
            campus=clean.get("campus", ""),
            college=clean.get("college", ""),
            department=clean.get("department", ""),
            signatories=clean.get("signatories", []),
        )

    def validate(self) -> List[str]:
        """Validates the preset data, returning a list of validation errors if any."""
        errors: List[str] = []
        if not isinstance(self.campus, str):
            errors.append("Campus must be a string.")
        if not isinstance(self.college, str):
            errors.append("College must be a string.")
        if not isinstance(self.department, str):
            errors.append("Department must be a string.")
        if not isinstance(self.signatories, list):
            errors.append("Signatories must be a list of signatory definitions.")
        else:
            for idx, sig in enumerate(self.signatories):
                if not isinstance(sig, dict):
                    errors.append(f"Signatory #{idx + 1} must be a dictionary.")
                elif not sig.get("label") and not sig.get("slot_id"):
                    errors.append(f"Signatory #{idx + 1} is missing both 'label' and 'slot_id'.")
        return errors


__all__ = [
    "OrganizationalContext",
    "SignatorySlot",
    "OrganizationPreset",
]
