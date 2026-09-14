#!/usr/bin/env python3
"""
CvSU CEIT Document Generator
Generates forms from a single set of inputs using OOP principles:
  - Course Syllabus Acceptance Form   (VPAA-QF-12)
  - Exam Returns Form — Midterm       (CEIT-QF-03)
  - Exam Returns Form — Finals        (CEIT-QF-03)
  - TOS Acknowledgment — Midterm
  - TOS Acknowledgment — Finals
  - Grade Discussion Form — Midterm
  - Grade Discussion Form — Finals
"""

import argparse
import copy
import json
import os
import sys
from abc import ABC, abstractmethod
from lxml import etree

from modules.common.logger import logger
from modules.common.docx_utils import (
    W,
    w,
    wt,
    get_full_text,
    auto_scale_font,
    _auto_scale_font,
    set_run_text,
    replace_after_colon,
    replace_value_run,
    collapse_runs_after_colon,
    set_cell_text,
    load_docx,
    save_docx,
)
from modules.models.schedule import ClassInfo
from modules.parsers.roster_parser import (
    load_students,
    load_students_excel,
    load_students_csv,
    _fix_encoding,
    _is_id_header,
    _is_name_header,
    _detect_roster_columns,
)

class TemplateError(Exception):
    """Raised when a docx template structure does not match expectations."""
    pass


# ══ Abstract base class ═══════════════════════════════════════════════════════
class DocumentGenerator(ABC):
    """
    Abstract base — defines the template method pattern.
    Subclasses implement fill_header() and (optionally) fill_table().
    """

    def __init__(self, template_path: str):
        self._template_path = template_path

    @property
    def template_path(self) -> str:
        return self._template_path

    @abstractmethod
    def fill_header(self, body, info: ClassInfo) -> None:
        """Fill header fields specific to this document type."""

    def _is_student_table(self, tbl) -> bool:
        """Return True only for the actual student roster table."""
        rows = tbl.findall(w("tr"))
        if not rows:
            return False
        cells = rows[0].findall(w("tc"))
        if not cells:
            return False
        hdr = " ".join("".join((t.text or '') for t in c.iter(w('t'))) for c in cells).lower()
        if any(k in hdr for k in ("instructor", "course /", "schedule code", "subject code", "semester /", "time / days / room")):
            return False
        return ("student" in hdr or "name of student" in hdr or "name of students" in hdr or "no." in hdr) and (
            "signature" in hdr or "student number" in hdr or "studentnumber" in hdr or "name of student" in hdr
        )

    def fill_table(self, body, info: ClassInfo) -> None:
        """
        Default table fill: clone first student row as template,
        remove existing student rows, then write info.students.
        Works for all CEIT document types.
        """
        tables = body.findall(w("tbl"))
        target = None
        for tbl in tables:
            if self._is_student_table(tbl):
                target = tbl
                break
        if target is None:
            raise TemplateError("Could not find the student list table in the template.")
        rows = target.findall(w("tr"))
        if len(rows) < 2:
            raise TemplateError("Student list table must have at least 2 rows (1 header, 1 student).")
        header_row = rows[0]
        template_row = rows[1]

        for tr in rows[1:]:
            target.remove(tr)

        for idx, (name, stnum) in enumerate(info.students):
            tr = copy.deepcopy(template_row)
            for tc in tr.findall(w("tc")):
                for p in tc.findall(w("p")):
                    for r in p.findall(w("r")):
                        for t in r.findall(w("t")):
                            t.text = ""
            cells = tr.findall(w("tc"))
            while len(cells) < 3:
                new_tc = etree.Element(w("tc"))
                tr.append(new_tc)
                cells = tr.findall(w("tc"))
            self._fill_student_row(cells, idx, name, stnum)
            target.append(tr)

    @abstractmethod
    def _fill_student_row(self, cells: list, idx: int,
                           name: str, stnum: str) -> None:
        """Fill one student row's cells. Signature differs by doc type."""

    def generate(self, info: ClassInfo, output_path: str) -> None:
        """Template method — orchestrates the full generation pipeline."""
        zin, root, body = load_docx(self._template_path)
        self.fill_header(body, info)
        self.fill_table(body, info)
        save_docx(zin, root, output_path)
        logger.info(f"Generated {os.path.basename(output_path)}")


# ══ Syllabus Generator ════════════════════════════════════════════════════════
class SyllabusGenerator(DocumentGenerator):
    """
    VPAA-QF-12 — Course Syllabus Acceptance Form
    Columns: No. | Name of Student | Student Number | Signature
    Header fields: Instructor, Course/Section, Schedule Code,
                   Subject, Time/Days/Room, Semester/AY
    """

    def fill_header(self, body, info: ClassInfo) -> None:
        tables = body.findall(w("tbl"))
        if not tables:
            return
        info_tbl = tables[0]
        rows = info_tbl.findall(w("tr"))
        mapping = [
            (0, info.instructor, 30),
            (1, info.course_section, 0),
            (2, info.schedule_code, 0),
            (3, info.subject, 35),
            (4, info.time_days_room, 45),
            (5, info.semester_ay, 0),
        ]
        for row_idx, val, thresh in mapping:
            if row_idx < len(rows):
                cells = rows[row_idx].findall(w("tc"))
                if len(cells) > 1:
                    set_cell_text(cells[1], val, shrink_threshold=thresh, shrink_sz="18")

    def _fill_student_row(self, cells, idx, name, stnum):
        set_cell_text(cells[1], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[2], stnum)

    def fill_table(self, body, info: ClassInfo) -> None:
        tbls = body.findall(w("tbl"))
        target = None
        for tbl in tbls:
            if self._is_student_table(tbl):
                target = tbl
                break
        if target is None:
            raise TemplateError("Could not find the student list table in the syllabus template.")

        rows = target.findall(w("tr"))
        if len(rows) < 2:
            raise TemplateError("Syllabus student list table must have at least 2 rows (1 header, 1 student).")
        header_row = rows[0]
        template_row = rows[1]

        for tr in rows[1:]:
            target.remove(tr)

        for idx, (name, stnum) in enumerate(info.students):
            tr = copy.deepcopy(template_row)
            for tc in tr.findall(w("tc")):
                for p in tc.findall(w("p")):
                    for r in p.findall(w("r")):
                        for t in r.findall(w("t")):
                            t.text = ""
            cells = tr.findall(w("tc"))
            while len(cells) < 3:
                new_tc = etree.Element(w("tc"))
                tr.append(new_tc)
                cells = tr.findall(w("tc"))
            self._fill_student_row(cells, idx, name, stnum)
            target.append(tr)


# ══ Exam Returns Generator ════════════════════════════════════════════════════
class ExamReturnsGenerator(DocumentGenerator):
    """
    CEIT-QF-03 — Exam Returns Form
    Columns: Name of Students | Student Number | Signature
    Header fields: Instructor, Course/Section, Schedule Code,
                   Subject, Semester/AY
    """

    def __init__(self, template_path: str, period: str):
        super().__init__(template_path)
        self._period = period   # "MIDTERM" or "FINAL"

    @property
    def period(self) -> str:
        return self._period

    def fill_header(self, body, info: ClassInfo) -> None:
        tables = body.findall(w("tbl"))
        if tables:
            info_tbl = tables[0]
            rows = info_tbl.findall(w("tr"))
            mapping = [
                (0, info.instructor, 30),
                (1, info.course_section, 0),
                (2, info.schedule_code, 0),
                (3, info.subject, 35),
                (4, info.semester_ay, 0),
            ]
            for row_idx, val, thresh in mapping:
                if row_idx < len(rows):
                    cells = rows[row_idx].findall(w("tc"))
                    if len(cells) > 1:
                        set_cell_text(cells[1], val, shrink_threshold=thresh, shrink_sz="18")
        else:
            paras = body.findall(w("p"))
            if len(paras) < 10:
                raise TemplateError("Exam Returns template missing required paragraphs for the header.")
            replace_value_run(paras[1], 2, info.instructor, shrink_threshold=30, shrink_sz="18")
            replace_value_run(paras[2], 3, info.course_section)
            replace_value_run(paras[3], 6, info.schedule_code)
            replace_value_run(paras[4], 3, info.subject, shrink_threshold=35, shrink_sz="18")
            collapse_runs_after_colon(paras[5], info.semester_ay)
            runs = paras[9].findall(w("r"))
            if runs:
                set_run_text(runs[0], f"{self._period} EXAMINATION")
                for r in runs[1:]:
                    paras[9].remove(r)

    def _fill_student_row(self, cells, idx, name, stnum):
        set_cell_text(cells[0], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[1], stnum)


# ══ TOS Generator ════════════════════════════════════════════════════════════
class TOSGenerator(DocumentGenerator):
    """
    TOS Acknowledgment Form
    Columns: Name of Students | Student Number | Signature
    Header fields: Instructor, Course/Section, Schedule Code,
                   Subject, Time/Days/Room, Semester/AY + (Midterm/Finals)
    """

    def __init__(self, template_path: str, period: str):
        super().__init__(template_path)
        self._period = period   # "Midterm" or "Finals"

    @property
    def period(self) -> str:
        return self._period

    def fill_header(self, body, info: ClassInfo) -> None:
        tables = body.findall(w("tbl"))
        if tables:
            info_tbl = tables[0]
            rows = info_tbl.findall(w("tr"))
            mapping = [
                (0, info.instructor, 30),
                (1, info.course_section, 0),
                (2, info.schedule_code, 0),
                (3, info.subject, 35),
                (4, info.time_days_room, 45),
                (5, f"{info.semester_ay} ({self._period})", 0),
            ]
            for row_idx, val, thresh in mapping:
                if row_idx < len(rows):
                    cells = rows[row_idx].findall(w("tc"))
                    if len(cells) > 1:
                        set_cell_text(cells[1], val, shrink_threshold=thresh, shrink_sz="18")
        else:
            paras = body.findall(w("p"))
            if len(paras) < 7:
                raise TemplateError("TOS template missing required paragraphs for the header.")
            replace_after_colon(paras[1], info.instructor, shrink_threshold=30, shrink_sz="18")
            replace_value_run(paras[2], 2, info.course_section)
            replace_value_run(paras[3], 4, info.schedule_code)
            replace_after_colon(paras[4], info.subject, shrink_threshold=35, shrink_sz="18")
            replace_after_colon(paras[5], info.time_days_room, shrink_threshold=45, shrink_sz="18")
            collapse_runs_after_colon(
                paras[6], f"{info.semester_ay} ({self._period})"
            )

    def _fill_student_row(self, cells, idx, name, stnum):
        set_cell_text(cells[0], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[1], stnum)


# ══ Grade Discussion Generator ════════════════════════════════════════════════
class GradeDiscussionGenerator(DocumentGenerator):
    """
    Grade Discussion Form (Midterm / Finals)
    Columns: Name of Students | Student Number | Signature
    Header fields: Instructor, Course/Section, Schedule Code,
                   Subject, Time/Days/Room, Semester/AY, Date
    """

    def __init__(self, template_path: str, period: str = "Midterm"):
        super().__init__(template_path)
        self._period = period   # "Midterm" or "Finals"

    @property
    def period(self) -> str:
        return self._period

    def fill_header(self, body, info: ClassInfo) -> None:
        tables = body.findall(w("tbl"))
        if not tables:
            return
        info_tbl = tables[0]
        rows = info_tbl.findall(w("tr"))
        
        for r_idx, row in enumerate(rows):
            cells = row.findall(w("tc"))
            if len(cells) < 3:
                continue
            label = get_full_text(cells[0]).upper().strip()
            val = None
            thresh = 0
            if "INSTRUCTOR" in label:
                val = info.instructor
                thresh = 30
            elif "COURSE" in label or "SECTION" in label:
                val = info.course_section
            elif "SCHEDULE" in label:
                val = info.schedule_code
            elif "SUBJECT" in label:
                val = info.subject
                thresh = 35
            elif "SEMESTER" in label or "ACADEMIC" in label:
                val = info.semester_ay
            elif "TIME" in label or "ROOM" in label or "DAY" in label:
                val = info.time_days_room
                thresh = 45
            elif "DATE" in label:
                val = None  # Left blank for manual date/signing
            else:
                if r_idx == 0:
                    val = info.instructor
                    thresh = 30
                elif r_idx == 1:
                    val = info.course_section
                elif r_idx == 2:
                    val = info.schedule_code
                elif r_idx == 3:
                    val = info.subject
                    thresh = 35
                elif r_idx == 4:
                    val = info.semester_ay
                elif r_idx == 5:
                    val = None

            if val is not None:
                set_cell_text(cells[2], val, shrink_threshold=thresh, shrink_sz="18")

    def _fill_student_row(self, cells, idx, name, stnum):
        set_cell_text(cells[0], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[1], stnum)


# ══ GeneratorFactory ══════════════════════════════════════════════════════════
class GeneratorFactory:
    """
    Creates generators from a templates directory.
    Encapsulates the mapping of document type → template file → generator.
    """

    TEMPLATE_FILES = {
        "syllabus":       "template_syllabus.docx",
        "exam_midterm":   "template_exam_midterm.docx",
        "exam_finals":    "template_exam_finals.docx",
        "tos_midterm":    "template_tos_midterm.docx",
        "tos_finals":     "template_tos_finals.docx",
        "grade_midterm":  "Midterm-Grade-Discussion_LATEST.docx",
        "grade_finals":   "Final-Grade-Discussion_LATEST.docx",
    }

    def __init__(self, templates_dir: str, config_manager=None):
        self._dir = templates_dir
        self._config_manager = config_manager

    def _path(self, key: str) -> str:
        p = os.path.join(self._dir, self.TEMPLATE_FILES[key])
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"Template not found: {p}\n"
                f"Expected file: {self.TEMPLATE_FILES[key]}"
            )
        return p

    def get_all(self, include_custom: bool = True) -> list:
        """Return list of (generator_factory, output_suffix) tuples.
        The factory is a callable that returns the instantiated generator."""
        generators = [
            (lambda: SyllabusGenerator(self._path("syllabus")),
             "SYLLABUS_ACCEPTANCE"),
            (lambda: ExamReturnsGenerator(self._path("exam_midterm"), "MIDTERM"),
             "EXAM_RETURNS_MIDTERM"),
            (lambda: ExamReturnsGenerator(self._path("exam_finals"),  "FINAL"),
             "EXAM_RETURNS_FINALS"),
            (lambda: TOSGenerator(self._path("tos_midterm"), "Midterm"),
             "TOS_MIDTERM"),
            (lambda: TOSGenerator(self._path("tos_finals"),  "Finals"),
             "TOS_FINALS"),
            (lambda: GradeDiscussionGenerator(self._path("grade_midterm"), "Midterm"),
             "GRADE_DISCUSSION_MIDTERM"),
            (lambda: GradeDiscussionGenerator(self._path("grade_finals"),  "Finals"),
             "GRADE_DISCUSSION_FINALS"),
        ]

        if include_custom:
            try:
                from modules.common.config_manager import config_manager as default_cm
                cm = self._config_manager or default_cm
                from modules.generators.generic_doc_gen import ConfigurableDocumentGenerator

                custom_templates = cm.get_custom_templates()
                for ct in custom_templates:
                    if ct.get("enabled", True):
                        t_path = ct.get("file_path")
                        recipe = ct.get("recipe") or {}
                        suffix = ct.get("suffix") or "CUSTOM_FORM"
                        if t_path and os.path.exists(t_path):
                            def _make_custom_gen(p=t_path, r=recipe):
                                return ConfigurableDocumentGenerator(p, r)

                            generators.append((_make_custom_gen, suffix))
            except Exception as e:
                logger.error(f"Failed to load custom templates in GeneratorFactory: {e}")

        return generators


# ══ CLI ═══════════════════════════════════════════════════════════════════════
def prompt(label: str, default: str = "") -> str:
    if default:
        val = input(f"  {label} [{default}]: ").strip()
        return val if val else default
    while True:
        val = input(f"  {label}: ").strip()
        if val: return val
        print("    (required)")


def prompt_choice(label: str, options: list[str], default: str = "") -> str:
    if not options:
        return default
    default_idx = options.index(default) if default in options else 0
    print(f"  {label}")
    for idx, value in enumerate(options, start=1):
        marker = "*" if idx - 1 == default_idx else " "
        print(f"    {marker}[{idx}] {value}")
    while True:
        try:
            raw = input(f"  Select option [{default_idx + 1}]: ").strip()
        except EOFError:
            return options[default_idx]
        if not raw:
            return options[default_idx]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        lowered = {o.lower(): o for o in options}
        if raw.lower() in lowered:
            return lowered[raw.lower()]
        print("    Please choose a valid option number.")


def _build_preset_map() -> dict:
    return {
        "default": {
            "course": "BSCS 1-4",
            "subject": "ITEC50 – WEB SYSTEMS AND TECHNOLOGY",
            "time": "10:00AM-12:00AM, 01:00PM-03:00PM / M / LAB: CCL 305, LEC: ITC 401",
            "semester": "2nd Semester / 2025-2026",
            "schedule": "202522383",
            "instructor": "DAN JOSEPH A. ORTEGA",
        },
        "dcit21": {
            "course": "BSCS 1-4",
            "subject": "DCIT 21 - INTRODUCTION TO COMPUTING",
            "time": "05:00PM-07:00PM / M / LEC: ITC 402",
            "semester": "1st Semester / 2026-2027",
            "schedule": "202612040",
            "instructor": "DAN JOSEPH A. ORTEGA",
        },
        "custom": {
            "course": "",
            "subject": "",
            "time": "",
            "semester": "",
            "schedule": "",
            "instructor": "",
        },
    }


def parse_class_payload(raw: str) -> dict:
    raw = raw.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    data = {}
    for part in raw.split(";"):
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            data[key.strip().lower()] = value.strip()
    return data


def read_class_payload(path_or_text: str) -> dict:
    text = path_or_text.strip()
    if os.path.exists(text):
        with open(text, "r", encoding="utf-8") as fh:
            return parse_class_payload(fh.read())
    return parse_class_payload(text)


def collect_class_info(args) -> ClassInfo:
    presets = _build_preset_map()

    payload = {}
    if getattr(args, "class_data", None):
        payload = read_class_payload(args.class_data)
    elif getattr(args, "class_file", None):
        payload = read_class_payload(args.class_file)

    if payload:
        instructor = args.instructor or payload.get("instructor") or payload.get("instructor_name") or ""
        course_sec = args.course or payload.get("course_section") or payload.get("course") or ""
        sched_code = args.sched or payload.get("schedule_code") or payload.get("schedule") or ""
        subject = args.subject or payload.get("subject") or payload.get("subject_code") or ""
        time_room = args.time or payload.get("time_days_room") or payload.get("time") or ""
        semester_ay = args.semester or payload.get("semester_ay") or payload.get("semester") or ""
        if not all([instructor, course_sec, sched_code, subject, time_room, semester_ay]):
            missing = [k for k, v in {
                "Instructor": instructor,
                "Course / Year / Section": course_sec,
                "Schedule Code": sched_code,
                "Subject": subject,
                "Time / Days / Room": time_room,
                "Semester / Academic Year": semester_ay,
            }.items() if not v]
            raise ValueError(f"Missing required class fields: {', '.join(missing)}")
        return ClassInfo(
            instructor=instructor,
            course_section=course_sec,
            schedule_code=sched_code,
            subject=subject,
            time_days_room=time_room,
            semester_ay=semester_ay,
            students=[],
        )

    if args.preset and args.preset in presets:
        preset_choice = args.preset
    else:
        print("  Choose a quick preset or enter values manually.\n")
        preset_choice = prompt_choice(
            "Quick class preset",
            ["default", "dcit21", "custom"],
            args.preset or "default",
        )
    chosen = presets[preset_choice]

    instructor = args.instructor or chosen["instructor"] or prompt("Instructor Name", "DAN JOSEPH A. ORTEGA")
    course_sec = args.course or chosen["course"] or prompt("Course / Year / Section", "BSCS 1-4")
    sched_code = args.sched or chosen["schedule"] or prompt("Schedule Code", "202522383")
    subject = args.subject or chosen["subject"] or prompt("Subject Code / Title", "ITEC50 – WEB SYSTEMS AND TECHNOLOGY")
    time_room = args.time or chosen["time"] or prompt("Time / Days / Room No.", "10:00AM-12:00AM, 01:00PM-03:00PM / M / LAB: CCL 305, LEC: ITC 401")
    semester_ay = args.semester or chosen["semester"] or prompt("Semester / Academic Year", "2nd Semester / 2025-2026")

    return ClassInfo(
        instructor=instructor,
        course_section=course_sec,
        schedule_code=sched_code,
        subject=subject,
        time_days_room=time_room,
        semester_ay=semester_ay,
        students=[],
    )


def main():
    parser = argparse.ArgumentParser(description="CvSU CEIT Document Generator")
    parser.add_argument("--csv",       help="Student list (.xlsx or .csv)")
    parser.add_argument("--instructor", help="Instructor name")
    parser.add_argument("--course",     help="Course / Year / Section")
    parser.add_argument("--sched",      help="Schedule Code")
    parser.add_argument("--subject",    help="Subject Code / Title")
    parser.add_argument("--time",       help="Time / Days / Room No.")
    parser.add_argument("--semester",   help="Semester / Academic Year")
    parser.add_argument("--preset", choices=["default", "dcit21", "custom"],
                        help="Choose a common class preset for quick input")
    parser.add_argument("--class-data", help="Single JSON payload or key=value string with all class fields")
    parser.add_argument("--class-file", help="Path to a JSON file containing class fields")
    parser.add_argument("--templates", help="Folder containing template .docx files",
                        default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                             "templates"))
    parser.add_argument("--output",    help="Output folder",
                        default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                             "output"))
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   CvSU CEIT DOCUMENT GENERATOR                       ║")
    print("║   Generates all 5 forms from a single input set      ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    info = collect_class_info(args)

    student_file = args.csv
    if not student_file:
        while True:
            student_file = input("  Student list file (.xlsx or .csv): ").strip().strip('"').strip("'")
            if not student_file:
                continue
            if not os.path.exists(student_file):
                print(f"    File not found: {student_file!r}")
                continue
            break

    students = load_students(student_file)
    info.students = students

    templates_dir = args.templates.strip().strip('"').strip("'")
    if not os.path.isdir(templates_dir):
        print(f"Templates folder not found: {templates_dir!r}")
        sys.exit(1)

    safe_section = info.course_section.replace("/", "-").replace(" ", "_")
    out_dir = os.path.join(args.output, safe_section)
    os.makedirs(out_dir, exist_ok=True)

    factory = GeneratorFactory(templates_dir)
    generators = factory.get_all()

    for gen_factory, suffix in generators:
        out_path = os.path.join(out_dir, f"{safe_section}_{suffix}.docx")
        try:
            gen = gen_factory()
            gen.generate(info, out_path)
        except Exception as e:
            logger.error(f"Failed {suffix}: {e}")

    print(f"\n[DONE] All documents saved to: {out_dir}\n")


if __name__ == "__main__":
    main()
