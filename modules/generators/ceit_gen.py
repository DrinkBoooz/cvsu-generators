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

from typing import Optional, Any, Union, Dict, List, Tuple
from modules.models.recipe import ValidatedTemplateRecipe
from modules.services.template_recipe_service import TemplateRecipeResolver, recipe_resolver

class TemplateError(Exception):
    """Raised when a docx template structure does not match expectations."""
    pass



# ══ Abstract base class ═══════════════════════════════════════════════════════
class DocumentGenerator(ABC):
    """
    Abstract base — defines the template method pattern.
    Pure execution engine driven by an authoritative ValidatedTemplateRecipe.
    Contains no heuristic template scanning or discovery.
    """

    def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe):
        if not isinstance(recipe, ValidatedTemplateRecipe):
            raise TypeError(
                f"DocumentGenerator requires a ValidatedTemplateRecipe instance, got {type(recipe).__name__}"
            )
        self._template_path = template_path
        self._recipe = recipe

    @property
    def template_path(self) -> str:
        return self._template_path

    @property
    def recipe(self) -> ValidatedTemplateRecipe:
        return self._recipe

    def fill_header(self, body, info: ClassInfo) -> None:
        """Fills header fields driven strictly by recipe header_bindings and placeholders."""
        tables = body.findall(w("tbl"))
        paras = body.findall(w("p"))

        field_values = {
            "instructor": info.instructor or "",
            "course_section": info.course_section or "",
            "schedule_code": info.schedule_code or "",
            "subject": info.subject or "",
            "time_days_room": info.time_days_room or "",
            "semester_ay": info.semester_ay or "",
            "date": "",
        }

        for field_name, b in self._recipe.header_bindings.items():
            val = field_values.get(field_name, "")
            thresh = b.shrink_threshold
            sz = b.shrink_sz or "18"

            if b.cell_type == "docx_table":
                t = b.target
                if isinstance(t, (tuple, list)) and len(t) == 3:
                    tbl_idx, r_idx, c_idx = t
                    if tbl_idx < len(tables):
                        rows = tables[tbl_idx].findall(w("tr"))
                        if r_idx < len(rows):
                            cells = rows[r_idx].findall(w("tc"))
                            if c_idx < len(cells):
                                set_cell_text(cells[c_idx], val, shrink_threshold=thresh, shrink_sz=sz)
            elif b.cell_type == "docx_paragraph":
                p_idx = b.target
                if isinstance(p_idx, int) and p_idx < len(paras):
                    replace_after_colon(paras[p_idx], val, shrink_threshold=thresh, shrink_sz=sz)

        # Placeholders if present in metadata
        placeholders = self._recipe.metadata.get("placeholders", [])
        if placeholders:
            for p_holder in placeholders:
                token = p_holder.get("tag") or f"{{{{{p_holder.get('raw_token', '')}}}}}"
                field_name = p_holder.get("field")
                val = field_values.get(field_name, "")
                if not token or not val:
                    continue
                for t in body.iter(w("t")):
                    if t.text and token in t.text:
                        t.text = t.text.replace(token, val)
                for p in body.iter(w("p")):
                    runs = p.findall(w("r"))
                    p_txt = "".join(r.findtext(w("t")) or "" for r in runs)
                    if token in p_txt:
                        new_p_txt = p_txt.replace(token, val)
                        if runs:
                            t0 = runs[0].find(w("t"))
                            if t0 is not None:
                                t0.text = new_p_txt
                            for r in runs[1:]:
                                for t_node in r.findall(w("t")):
                                    t_node.text = ""

    def _is_student_table(self, tbl) -> bool:
        """Deprecated legacy student table locator; prefer recipe.roster_binding."""
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
        """Fills student roster table driven strictly by recipe roster_binding."""
        rb = self._recipe.roster_binding
        if rb is None:
            return

        tables = body.findall(w("tbl"))
        if rb.table_index >= len(tables):
            raise TemplateError(
                f"Roster table index {rb.table_index} not found in template ({len(tables)} tables present)."
            )

        target = tables[rb.table_index]
        rows = target.findall(w("tr"))
        if len(rows) <= rb.first_data_row_index:
            raise TemplateError(
                f"Student list table must have at least {rb.first_data_row_index + 1} rows."
            )

        template_row = rows[rb.first_data_row_index]

        for tr in rows[rb.first_data_row_index:]:
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

    def _fill_student_row(self, cells: list, idx: int, name: str, stnum: str) -> None:
        """Fills one student row's cells based on recipe."""
        rb = self._recipe.roster_binding
        if rb is None:
            return
        if self._recipe.profile_id == "custom_docx" and rb.index_col is not None and rb.index_col < len(cells):
            set_cell_text(cells[rb.index_col], str(idx + 1))
        if rb.name_col is not None and rb.name_col < len(cells):
            set_cell_text(cells[rb.name_col], name, shrink_threshold=32, shrink_sz="18")
        if rb.id_col is not None and rb.id_col < len(cells):
            set_cell_text(cells[rb.id_col], stnum)

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
    Pure recipe-driven execution; zero positional fallbacks.
    """

    def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe):
        super().__init__(template_path, recipe)


# ══ Exam Returns Generator ════════════════════════════════════════════════════
class ExamReturnsGenerator(DocumentGenerator):
    """
    CEIT-QF-03 — Exam Returns Form
    Pure recipe-driven execution; zero positional fallbacks.
    """

    def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe = None, period: str = "MIDTERM", **kwargs):
        if isinstance(period, ValidatedTemplateRecipe) and isinstance(recipe, str):
            recipe, period = period, recipe
        elif "recipe" in kwargs and isinstance(kwargs["recipe"], ValidatedTemplateRecipe):
            if isinstance(recipe, str):
                period = recipe
            recipe = kwargs["recipe"]
        if not isinstance(recipe, ValidatedTemplateRecipe):
            raise TypeError("ExamReturnsGenerator requires a ValidatedTemplateRecipe instance")
        super().__init__(template_path, recipe)
        self._period = period

    @property
    def period(self) -> str:
        return self._period


# ══ TOS Generator ════════════════════════════════════════════════════════════
class TOSGenerator(DocumentGenerator):
    """
    TOS Acknowledgment Form
    Pure recipe-driven execution; appends period to semester_ay field.
    """

    def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe = None, period: str = "Midterm", **kwargs):
        if isinstance(period, ValidatedTemplateRecipe) and isinstance(recipe, str):
            recipe, period = period, recipe
        elif "recipe" in kwargs and isinstance(kwargs["recipe"], ValidatedTemplateRecipe):
            if isinstance(recipe, str):
                period = recipe
            recipe = kwargs["recipe"]
        if not isinstance(recipe, ValidatedTemplateRecipe):
            raise TypeError("TOSGenerator requires a ValidatedTemplateRecipe instance")
        super().__init__(template_path, recipe)
        self._period = period

    @property
    def period(self) -> str:
        return self._period

    def fill_header(self, body, info: ClassInfo) -> None:
        info_with_period = ClassInfo(
            instructor=info.instructor,
            course_section=info.course_section,
            schedule_code=info.schedule_code,
            subject=info.subject,
            time_days_room=info.time_days_room,
            semester_ay=f"{info.semester_ay} ({self._period})",
            students=info.students,
        )
        super().fill_header(body, info_with_period)


# ══ Grade Discussion Generator ════════════════════════════════════════════════
class GradeDiscussionGenerator(DocumentGenerator):
    """
    Grade Discussion Form (Midterm / Finals)
    Pure recipe-driven execution; zero positional fallbacks.
    """

    def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe = None, period: str = "Midterm", **kwargs):
        if isinstance(period, ValidatedTemplateRecipe) and isinstance(recipe, str):
            recipe, period = period, recipe
        elif "recipe" in kwargs and isinstance(kwargs["recipe"], ValidatedTemplateRecipe):
            if isinstance(recipe, str):
                period = recipe
            recipe = kwargs["recipe"]
        if not isinstance(recipe, ValidatedTemplateRecipe):
            raise TypeError("GradeDiscussionGenerator requires a ValidatedTemplateRecipe instance")
        super().__init__(template_path, recipe)
        self._period = period

    @property
    def period(self) -> str:
        return self._period



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

    PROFILE_MAPPING = {
        "syllabus":       "syllabus",
        "exam_midterm":   "exam_returns",
        "exam_finals":    "exam_returns",
        "tos_midterm":    "tos",
        "tos_finals":     "tos",
        "grade_midterm":  "grade_discussion",
        "grade_finals":   "grade_discussion",
    }

    def __init__(self, templates_dir: str, config_manager=None, resolver: Optional[TemplateRecipeResolver] = None):
        self._dir = templates_dir
        self._config_manager = config_manager
        self._resolver = resolver or TemplateRecipeResolver.get_instance()

    def _path(self, key: str) -> str:
        p = os.path.join(self._dir, self.TEMPLATE_FILES[key])
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"Template not found: {p}\n"
                f"Expected file: {self.TEMPLATE_FILES[key]}"
            )
        return p

    def _get_validated_recipe(self, key: str, template_path: str) -> ValidatedTemplateRecipe:
        profile_id = self.PROFILE_MAPPING.get(key, "academic_docx")
        return self._resolver.resolve(template_path, profile_id=profile_id)

    def get_all(self, include_custom: bool = True) -> list:
        """Return list of (generator_factory, output_suffix) tuples.
        The factory is a callable that returns the instantiated generator."""
        generators = [
            (lambda: SyllabusGenerator(
                self._path("syllabus"),
                self._get_validated_recipe("syllabus", self._path("syllabus")),
             ), "SYLLABUS_ACCEPTANCE"),
            (lambda: ExamReturnsGenerator(
                self._path("exam_midterm"),
                self._get_validated_recipe("exam_midterm", self._path("exam_midterm")),
                "MIDTERM",
             ), "EXAM_RETURNS_MIDTERM"),
            (lambda: ExamReturnsGenerator(
                self._path("exam_finals"),
                self._get_validated_recipe("exam_finals", self._path("exam_finals")),
                "FINAL",
             ), "EXAM_RETURNS_FINALS"),
            (lambda: TOSGenerator(
                self._path("tos_midterm"),
                self._get_validated_recipe("tos_midterm", self._path("tos_midterm")),
                "Midterm",
             ), "TOS_MIDTERM"),
            (lambda: TOSGenerator(
                self._path("tos_finals"),
                self._get_validated_recipe("tos_finals", self._path("tos_finals")),
                "Finals",
             ), "TOS_FINALS"),
            (lambda: GradeDiscussionGenerator(
                self._path("grade_midterm"),
                self._get_validated_recipe("grade_midterm", self._path("grade_midterm")),
                "Midterm",
             ), "GRADE_DISCUSSION_MIDTERM"),
            (lambda: GradeDiscussionGenerator(
                self._path("grade_finals"),
                self._get_validated_recipe("grade_finals", self._path("grade_finals")),
                "Finals",
             ), "GRADE_DISCUSSION_FINALS"),
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
                        recipe_data = ct.get("recipe") or {}
                        suffix = ct.get("suffix") or "CUSTOM_FORM"
                        profile_id = ct.get("profile_id") or recipe_data.get("profile_id") or "custom_docx"
                        if t_path and os.path.exists(t_path):
                            validated = self._resolver.resolve(t_path, profile_id=profile_id)
                            def _make_custom_gen(p=t_path, v=validated):
                                return ConfigurableDocumentGenerator(p, v)

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
