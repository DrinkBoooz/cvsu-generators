from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ScheduleMeeting:
    day: str
    start_time: str
    end_time: str
    room: str
    is_lab: bool = False
    is_async: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "room": self.room,
            "is_lab": self.is_lab,
            "is_async": self.is_async,
        }

@dataclass
class ScheduleBlock:
    subject_title: str
    day: str
    start_time: str
    end_time: str
    room: str
    type_str: str = ""
    is_async: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_title": self.subject_title,
            "day": self.day,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "room": self.room,
            "type_str": self.type_str,
            "is_async": self.is_async,
        }

LEGACY_DEFAULT_COLLEGE = "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"


@dataclass
class ClassInfo:
    """Encapsulates input data for a class; shared across document generators and validation."""
    instructor: str = ""
    course_section: str = ""
    schedule_code: str = ""
    subject: str = ""
    time_days_room: str = ""
    semester_ay: str = ""
    students: list = field(default_factory=list)
    college: Optional[str] = None
    has_lab: bool = False
    subject_code: str = ""
    subject_name: str = ""
    has_explicit_college: bool = field(default=False, init=False)

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        if name == "college" and "has_explicit_college" in self.__dict__:
            object.__setattr__(self, "has_explicit_college", value is not None)

    def __post_init__(self):
        if self.college is None:
            self.college = LEGACY_DEFAULT_COLLEGE
            self.has_explicit_college = False
        else:
            self.has_explicit_college = True

        if not self.subject_name and self.subject:
            self.subject_name = self.subject
        if not self.subject and self.subject_name:
            self.subject = self.subject_name
        if not self.course_sec:
            self.course_sec = self.course_section

    @property
    def course_sec(self) -> str:
        return self.course_section

    @course_sec.setter
    def course_sec(self, val: str):
        self.course_section = val

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instructor": self.instructor,
            "course_section": self.course_section,
            "course_sec": self.course_section,
            "schedule_code": self.schedule_code,
            "subject": self.subject,
            "subject_name": self.subject_name or self.subject,
            "subject_code": self.subject_code,
            "time_days_room": self.time_days_room,
            "semester_ay": self.semester_ay,
            "students": self.students,
            "college": self.college,
            "has_explicit_college": self.has_explicit_college,
            "has_lab": self.has_lab,
        }
