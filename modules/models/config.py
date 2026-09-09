from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class RosterConfig:
    course_sec: str = ""
    schedule_code: str = ""
    subject_name: str = ""
    header_row: Optional[int] = None
    name_col: Optional[str] = None
    id_col: Optional[str] = None
    linked_schedule_code: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_sec": self.course_sec,
            "schedule_code": self.schedule_code,
            "subject_name": self.subject_name,
            "header_row": self.header_row,
            "name_col": self.name_col,
            "id_col": self.id_col,
            "linked_schedule_code": self.linked_schedule_code or self.schedule_code,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RosterConfig":
        return cls(
            course_sec=d.get("course_sec", ""),
            schedule_code=d.get("schedule_code", "") or d.get("linked_schedule_code", ""),
            subject_name=d.get("subject_name", ""),
            header_row=d.get("header_row"),
            name_col=d.get("name_col"),
            id_col=d.get("id_col"),
            linked_schedule_code=d.get("linked_schedule_code", "") or d.get("schedule_code", ""),
        )
