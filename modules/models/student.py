from dataclasses import dataclass
from typing import Tuple, Dict

@dataclass(frozen=True)
class Student:
    name: str
    student_number: str
    row_idx: int = None

    def to_tuple(self) -> Tuple[str, str]:
        return (self.name, self.student_number)

    def to_dict(self) -> Dict[str, str]:
        d = {
            "name": self.name,
            "student_number": self.student_number
        }
        if self.row_idx is not None:
            d["row_idx"] = self.row_idx
        return d

    @classmethod
    def from_tuple(cls, t: Tuple[str, str]) -> "Student":
        return cls(name=str(t[0]).strip(), student_number=str(t[1]).strip())

    @classmethod
    def from_dict(cls, d: Dict[str, str]) -> "Student":
        return cls(
            name=str(d.get("name", "")).strip(),
            student_number=str(d.get("student_number", "")).strip()
        )
