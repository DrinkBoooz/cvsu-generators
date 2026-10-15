import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


def sanitize_workspace_id(name_or_id: str) -> str:
    """Produces a clean, filesystem-safe workspace identifier."""
    if not name_or_id:
        return "default_workspace"
    # Replace null bytes and non-alphanumeric chars with hyphens
    clean = re.sub(r'[^a-zA-Z0-9]+', '-', str(name_or_id).strip())
    slug = re.sub(r'-+', '-', clean).strip('-')
    return slug.lower() or "workspace"


@dataclass
class SemesterWorkspace:
    """
    Encapsulates an isolated faculty teaching semester snapshot.
    Enables instant switching between academic semesters, terms, or faculty profiles.
    """
    name: str
    workspace_id: str = ""
    updated_at: str = ""
    created_at: str = ""
    schedule_path: str = ""
    roster_mappings: Dict[str, str] = field(default_factory=dict)
    rosters: List[str] = field(default_factory=list)
    output_dir: str = ""
    organization_preset: Dict[str, Any] = field(default_factory=dict)
    calendar_config: Dict[str, Any] = field(default_factory=dict)
    active_template_set: str = ""
    date_boundaries: Dict[str, Any] = field(default_factory=dict)
    selected_classes: List[str] = field(default_factory=list)
    class_type_overrides: Dict[str, str] = field(default_factory=dict)
    roster_configs: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.workspace_id:
            self.workspace_id = sanitize_workspace_id(self.name)
        else:
            self.workspace_id = sanitize_workspace_id(self.workspace_id)
        now_iso = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now_iso
        if not self.updated_at:
            self.updated_at = now_iso

    def validate(self) -> List[str]:
        """Validates schema and structural integrity of the workspace."""
        errors = []
        if not self.name or not str(self.name).strip():
            errors.append("Workspace name cannot be empty")
        if not self.workspace_id or not str(self.workspace_id).strip():
            errors.append("Workspace ID cannot be empty")
        if any(c in self.workspace_id for c in ('/', '\\', '\x00', '..')):
            errors.append("Workspace ID contains invalid characters or path traversal sequences")
        if not isinstance(self.roster_mappings, dict):
            errors.append("roster_mappings must be a dictionary")
        if not isinstance(self.rosters, list):
            errors.append("rosters must be a list of paths")
        if not isinstance(self.organization_preset, dict):
            errors.append("organization_preset must be a dictionary")
        if not isinstance(self.calendar_config, dict):
            errors.append("calendar_config must be a dictionary")
        if not isinstance(self.date_boundaries, dict):
            errors.append("date_boundaries must be a dictionary")
        if not isinstance(self.selected_classes, list):
            errors.append("selected_classes must be a list")
        if not isinstance(self.class_type_overrides, dict):
            errors.append("class_type_overrides must be a dictionary")
        if not isinstance(self.roster_configs, dict):
            errors.append("roster_configs must be a dictionary")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Serializes workspace snapshot to JSON-compatible dictionary."""
        return {
            "schema_version": "1.0",
            "workspace_id": self.workspace_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schedule_path": self.schedule_path,
            "roster_mappings": self.roster_mappings,
            "rosters": self.rosters,
            "output_dir": self.output_dir,
            "organization_preset": self.organization_preset,
            "calendar_config": self.calendar_config,
            "active_template_set": self.active_template_set,
            "date_boundaries": self.date_boundaries,
            "selected_classes": self.selected_classes,
            "class_type_overrides": self.class_type_overrides,
            "roster_configs": self.roster_configs,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemesterWorkspace":
        """Deserializes a workspace snapshot from a dictionary."""
        if not isinstance(data, dict):
            raise ValueError("Workspace data must be a dictionary")
        return cls(
            name=str(data.get("name") or data.get("workspace_id") or "Unnamed Workspace"),
            workspace_id=str(data.get("workspace_id") or ""),
            updated_at=str(data.get("updated_at") or ""),
            created_at=str(data.get("created_at") or ""),
            schedule_path=str(data.get("schedule_path") or ""),
            roster_mappings=dict(data.get("roster_mappings") or {}),
            rosters=list(data.get("rosters") or []),
            output_dir=str(data.get("output_dir") or ""),
            organization_preset=dict(data.get("organization_preset") or {}),
            calendar_config=dict(data.get("calendar_config") or {}),
            active_template_set=str(data.get("active_template_set") or ""),
            date_boundaries=dict(data.get("date_boundaries") or {}),
            selected_classes=list(data.get("selected_classes") or []),
            class_type_overrides=dict(data.get("class_type_overrides") or {}),
            roster_configs=dict(data.get("roster_configs") or {}),
            metadata=dict(data.get("metadata") or {}),
        )
