#!/usr/bin/env python3
"""
CvSU CEIT Document Generator
Generates 5 forms from a single set of inputs using OOP principles:
  - Course Syllabus Acceptance Form   (VPAA-QF-12)
  - Exam Returns Form — Midterm       (CEIT-QF-03)
  - Exam Returns Form — Finals        (CEIT-QF-03)
  - TOS Acknowledgment — Midterm
  - TOS Acknowledgment — Finals

OOP structure:
  DocumentGenerator (abstract base)
    ├── SyllabusGenerator
    ├── ExamReturnsGenerator  (parameterised: Midterm / Finals)
    └── TOSGenerator          (parameterised: Midterm / Finals)

Usage:
    python ceit_generator.py
    python ceit_generator.py --csv students.xlsx
"""

import argparse, copy, csv, io, json, os, sys, zipfile
from abc import ABC, abstractmethod
from lxml import etree

# ══ Namespace helpers ══════════════════════════════════════════════════════════
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def w(tag: str) -> str:
    return f"{{{W}}}{tag}"

# ══ Data class ════════════════════════════════════════════════════════════════
class ClassInfo:
    """
    Encapsulates all input data for a class.
    Single source of truth shared by every generator.
    """
    def __init__(
        self,
        instructor:    str,
        course_section: str,   # e.g. "BSCS 1-4"
        schedule_code: str,    # e.g. "202522383"
        subject:       str,    # e.g. "ITEC50 – WEB SYSTEMS AND TECHNOLOGY"
        time_days_room: str,   # e.g. "10:00AM-12:00AM / M / LAB: CCL 305"
        semester_ay:   str,    # e.g. "2nd Semester / 2025-2026"
        students:      list,   # [(name, student_number), ...]
    ):
        self.instructor     = instructor
        self.course_section = course_section
        self.schedule_code  = schedule_code
        self.subject        = subject
        self.time_days_room = time_days_room
        self.semester_ay    = semester_ay
        self.students       = students

# ══ XML utilities (module-level, shared by all generators) ════════════════════
def get_full_text(el) -> str:
    return "".join(t.text or "" for t in el.iter(w("t")))

def _auto_scale_font(r_el, text: str, shrink_threshold: int, sz_val: str):
    """Automatically scale the font of a run if the text exceeds a given length."""
    if shrink_threshold > 0 and len(text) > shrink_threshold:
        rpr = r_el.find(w("rPr"))
        if rpr is None:
            rpr = etree.Element(w("rPr"))
            r_el.insert(0, rpr)
        sz = rpr.find(w("sz"))
        if sz is None:
            sz = etree.SubElement(rpr, w("sz"))
        sz.set(w("val"), sz_val)
        sz_cs = rpr.find(w("szCs"))
        if sz_cs is None:
            sz_cs = etree.SubElement(rpr, w("szCs"))
        sz_cs.set(w("val"), sz_val)

def set_run_text(run, text: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """Replace text in a single run, preserving its rPr, and optionally scaling font."""
    for t in run.findall(w("t")):
        run.remove(t)
        
    _auto_scale_font(run, text, shrink_threshold, shrink_sz)
        
    t_el = etree.SubElement(run, w("t"))
    t_el.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

def replace_after_colon(para, value: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """
    Keep the label run (up to and including ':'), set the last run to value,
    and remove all runs in between. Works for 1-run and multi-run paragraphs.
    """
    runs = para.findall(w("r"))
    if not runs:
        return
    full = get_full_text(para)
    if ":" not in full:
        set_run_text(runs[-1], value)
        return
    # Find which run contains the colon
    pos = 0
    colon_run_idx = 0
    colon_abs = full.index(":")
    for i, r in enumerate(runs):
        rt = get_full_text(r)
        if pos + len(rt) > colon_abs:
            colon_run_idx = i
            break
        pos += len(rt)
    # Truncate the colon run to just label text up to and including ':'
    colon_run = runs[colon_run_idx]
    run_text_so_far = full[:pos]
    local_colon = colon_abs - pos
    label_in_run = get_full_text(colon_run)[:local_colon + 1]
    for t in colon_run.findall(w("t")):
        colon_run.remove(t)
    t_lbl = etree.SubElement(colon_run, w("t"))
    t_lbl.text = label_in_run
    # Remove all runs after colon_run
    for r in runs[colon_run_idx + 1:]:
        para.remove(r)
    # Append a value run cloned from colon_run's rPr
    rpr_src = colon_run.find(w("rPr"))
    r_val = etree.SubElement(para, w("r"))
    if rpr_src is not None:
        r_val.insert(0, copy.deepcopy(rpr_src))
    t_val = etree.SubElement(r_val, w("t"))
    # Ensure there's a separating space after the ':' unless the caller
    # intentionally provided it (some callsites already do so).
    if value and not value.startswith(" "):
        t_val.text = " " + value
    else:
        t_val.text = value
    if t_val.text and t_val.text[0] == " ":
        t_val.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        
    _auto_scale_font(r_val, value, shrink_threshold, shrink_sz)
    # Remove paragraph-level hanging indent if present — templates sometimes
    # use a hanging indent for label/value pairs which causes inconsistent
    # visual spacing when we replace runs. Clearing it produces a consistent
    # inline label:value appearance.
    ppr = para.find(w("pPr"))
    if ppr is not None:
        ind = ppr.find(w("ind"))
        if ind is not None:
            ppr.remove(ind)

def replace_value_run(para, run_index: int, value: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """
    Keep runs [0..run_index-1] as-is (label), set run[run_index] to value,
    and remove all runs after run_index.
    """
    runs = para.findall(w("r"))
    if not runs:
        return
    # Clamp run_index
    run_index = min(run_index, len(runs) - 1)
    # Remove all runs after run_index
    for r in runs[run_index + 1:]:
        para.remove(r)
    # If the runs before the target end with a colon, ensure a separating
    # space before the value so text doesn't concatenate with the label.
    prefix = "".join(get_full_text(r) for r in runs[:run_index])
    if prefix.rstrip().endswith(":") and value and not value.startswith(" "):
        value = " " + value

    # Set the target run
    set_run_text(runs[run_index], value, shrink_threshold, shrink_sz)
    # Also clear paragraph indent for consistency
    p = para
    ppr = p.find(w("pPr"))
    if ppr is not None:
        ind = ppr.find(w("ind"))
        if ind is not None:
            ppr.remove(ind)

def collapse_runs_after_colon(para, value: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """
    For semester paragraphs that have multiple runs (e.g. superscript 'nd').
    Collapses everything after the colon into one run.
    Handles tab-separated paragraphs (Exam Returns) and text-colon paragraphs.
    """
    runs = para.findall(w("r"))
    if not runs:
        return

    # Find the run whose <w:t> contains ':' — ignore tab-only runs
    colon_run_idx = None
    for i, r in enumerate(runs):
        txt = "".join(t.text or "" for t in r.findall(w("t")))
        if ":" in txt:
            colon_run_idx = i
            break

    if colon_run_idx is None:
        # No colon text found — replace last text-bearing run
        for r in reversed(runs):
            if r.find(w("t")) is not None:
                set_run_text(r, value)
                return
        return

    # Remove all runs after the colon run
    for r in runs[colon_run_idx + 1:]:
        para.remove(r)

    # Trim the colon run to only text up to and including ':'
    colon_run = para.findall(w("r"))[colon_run_idx]
    rpr_src = colon_run.find(w("rPr"))
    for t_el in list(colon_run.findall(w("t"))):
        txt = t_el.text or ""
        if ":" in txt:
            t_el.text = txt[:txt.index(":") + 1]
        else:
            colon_run.remove(t_el)

    # Append a fresh value run
    r_val = etree.SubElement(para, w("r"))
    if rpr_src is not None:
        r_val.insert(0, copy.deepcopy(rpr_src))
    t_val = etree.SubElement(r_val, w("t"))
    # Ensure a separating space after the ':' unless the caller provided one.
    if value and not value.startswith(" "):
        t_val.text = " " + value
    else:
        t_val.text = value
    if t_val.text and t_val.text[0] == " ":
        t_val.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        
    _auto_scale_font(r_val, value, shrink_threshold, shrink_sz)
        
    ppr = para.find(w("pPr"))
    if ppr is not None:
        ind = ppr.find(w("ind"))
        if ind is not None:
            ppr.remove(ind)

def set_cell_text(tc, text: str, remove_num: bool = False, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """Replace text in first paragraph of a cell, preserving run formatting.

    If `remove_num` is True, remove any paragraph-level `w:numPr` so an
    automatic list number won't render next to our explicit cell text.
    """
    p = tc.find(w("p"))
    if p is None:
        return
    # Optionally remove automatic numbering from the paragraph so Word
    # doesn't render an extra list number next to our explicit cell text.
    if remove_num:
        ppr = p.find(w("pPr"))
        if ppr is not None:
            numpr = ppr.find(w("numPr"))
            if numpr is not None:
                ppr.remove(numpr)
    runs = p.findall(w("r"))
    if not runs:
        r = etree.SubElement(p, w("r"))
        t = etree.SubElement(r, w("t"))
        t.text = text
        return
    # Preserve first run's rPr, collapse all runs into one
    first_rpr = runs[0].find(w("rPr"))
    for r in runs:
        p.remove(r)
    r_new = etree.SubElement(p, w("r"))
    if first_rpr is not None:
        r_new.insert(0, copy.deepcopy(first_rpr))
        
    _auto_scale_font(r_new, text, shrink_threshold, shrink_sz)
        
    t = etree.SubElement(r_new, w("t"))
    t.text = text
    if text and text[0] == " ":
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

def load_docx(path: str):
    """Load a docx and return (zin, root, body)."""
    with open(path, "rb") as fh:
        data = fh.read()
    zin = zipfile.ZipFile(io.BytesIO(data))
    root = etree.fromstring(zin.read("word/document.xml"))
    body = root.find(w("body"))
    return zin, root, body

def save_docx(zin, root, output_path: str):
    """Serialize root back into a docx zip."""
    new_xml = etree.tostring(root, xml_declaration=True,
                              encoding="UTF-8", standalone=True)
    buf = io.BytesIO()
    zout = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        zout.writestr(item, new_xml if item.filename == "word/document.xml"
                      else zin.read(item.filename))
    zout.close()
    zin.close()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as fh:
        fh.write(buf.getvalue())
    print(f"  ✅  {output_path}")

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
        # The metadata header tables contain labels like Instructor / Course /
        # Schedule / Subject / Semester and may include the word "name" in the
        # title, but they do not include the roster columns used by the student list.
        if any(k in hdr for k in ("instructor", "course /", "schedule code", "subject code", "semester /", "time / days / room")):
            return False
        return ("student" in hdr or "name of student" in hdr or "name of students" in hdr or "no." in hdr) and (
            "signature" in hdr or "student number" in hdr or "studentnumber" in hdr or "name of student" in hdr
        )

    def fill_table(self, body, info: ClassInfo) -> None:
        """
        Default table fill: clone first student row as template,
        remove existing student rows, then write info.students.
        Works for all three document types.
        """
        # Find the table that contains the student list.
        tables = body.findall(w("tbl"))
        target = None
        for tbl in tables:
            if self._is_student_table(tbl):
                target = tbl
                break
        if target is None:
            return
        rows = target.findall(w("tr"))
        if len(rows) < 2:
            return
        header_row = rows[0]
        template_row = rows[1]   # first student row = formatting reference

        # Remove all existing student rows (keep only header)
        for tr in rows[1:]:
            target.remove(tr)

        for idx, (name, stnum) in enumerate(info.students):
            tr = copy.deepcopy(template_row)
            # Clear any existing text in cloned row cells to avoid duplicated
            # numbering or leftover template text, then fill.
            for tc in tr.findall(w("tc")):
                for p in tc.findall(w("p")):
                    for r in p.findall(w("r")):
                        for t in r.findall(w("t")):
                            t.text = ""
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

# ══ Syllabus Generator ════════════════════════════════════════════════════════
class SyllabusGenerator(DocumentGenerator):
    """
    VPAA-QF-12 — Course Syllabus Acceptance Form
    Columns: No. | Name of Student | Student Number | Signature
    Header fields: Instructor, Course/Section, Schedule Code,
                   Subject, Time/Days/Room, Semester/AY
    """

    def fill_header(self, body, info: ClassInfo) -> None:
        # The syllabus template stores header fields in the first table (two-column)
        # where column 0 = label and column 1 = value. Write values directly
        # into the second cell of each header row to preserve formatting.
        tables = body.findall(w("tbl"))
        if not tables:
            return
        info_tbl = tables[0]
        rows = info_tbl.findall(w("tr"))
        # Expected order: Instructor, Course/Section, Schedule Code,
        # Subject, Time/Days/Room, Semester/AY
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
        # cells: [No., Name, StudentNumber, Signature]
        # Use template's automatic numbering: do not write an explicit
        # digit into the first cell (the template's paragraph `w:numPr`
        # will produce the visible number). Leave the cell text empty.
        # Extreme names shrink to 9pt to prevent line-wrapping
        set_cell_text(cells[1], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[2], stnum)
        # cells[3] = Signature — leave blank

    def fill_table(self, body, info: ClassInfo) -> None:
        """Syllabus-specific table fill: find the student list table by
        locating a table whose first row contains the roster columns and
        populate it. This template stores the header in a separate table,
        so the student table may not be the first table in the document."""
        tbls = body.findall(w("tbl"))
        target = None
        for tbl in tbls:
            if self._is_student_table(tbl):
                target = tbl
                break
        if target is None:
            return

        rows = target.findall(w("tr"))
        if len(rows) < 2:
            return
        header_row = rows[0]
        template_row = rows[1]

        # Remove existing student rows
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
            # Ensure we have at least 3 cells; if not, pad with empty cells
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
    Note: No Time/Days/Room field. Has exam type label (Midterm/Finals).

    Polymorphism: period parameter ("Midterm"/"Finals") changes
    the exam label without changing the interface.
    """

    def __init__(self, template_path: str, period: str):
        super().__init__(template_path)
        self._period = period   # "MIDTERM" or "FINAL"

    @property
    def period(self) -> str:
        return self._period

    def fill_header(self, body, info: ClassInfo) -> None:
        # Prefer filling header from the first table if present (table rows:
        # Instructor, Course/Section, Schedule Code, Subject, Semester/AY).
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
        # cells: [Name, StudentNumber, Signature]
        set_cell_text(cells[0], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[1], stnum)
        # cells[2] = Signature — leave blank

# ══ TOS Generator ════════════════════════════════════════════════════════════
class TOSGenerator(DocumentGenerator):
    """
    TOS Acknowledgment Form
    Columns: Name of Students | Student Number | Signature
    Header fields: Instructor, Course/Section, Schedule Code,
                   Subject, Time/Days/Room, Semester/AY + (Midterm/Finals)

    Polymorphism: period parameter appended to semester field.
    """

    def __init__(self, template_path: str, period: str):
        super().__init__(template_path)
        self._period = period   # "Midterm" or "Finals"

    @property
    def period(self) -> str:
        return self._period

    def fill_header(self, body, info: ClassInfo) -> None:
        # Prefer filling header from the first table when available
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
            replace_after_colon(paras[1], info.instructor, shrink_threshold=30, shrink_sz="18")
            replace_value_run(paras[2], 2, info.course_section)
            replace_value_run(paras[3], 4, info.schedule_code)
            replace_after_colon(paras[4], info.subject, shrink_threshold=35, shrink_sz="18")
            replace_after_colon(paras[5], info.time_days_room, shrink_threshold=45, shrink_sz="18")
            collapse_runs_after_colon(
                paras[6], f"{info.semester_ay} ({self._period})"
            )

    def _fill_student_row(self, cells, idx, name, stnum):
        # cells: [Name, StudentNumber, Signature]
        set_cell_text(cells[0], name, shrink_threshold=32, shrink_sz="18")
        set_cell_text(cells[1], stnum)
        # cells[2] = Signature — leave blank

# ══ GeneratorFactory ══════════════════════════════════════════════════════════
class GeneratorFactory:
    """
    Creates all 5 generators from a templates directory.
    Encapsulates the mapping of document type → template file → generator.
    """

    TEMPLATE_FILES = {
        "syllabus":       "template_syllabus.docx",
        "exam_midterm":   "template_exam_midterm.docx",
        "exam_finals":    "template_exam_finals.docx",
        "tos_midterm":    "template_tos_midterm.docx",
        "tos_finals":     "template_tos_finals.docx",
    }

    def __init__(self, templates_dir: str):
        self._dir = templates_dir

    def _path(self, key: str) -> str:
        p = os.path.join(self._dir, self.TEMPLATE_FILES[key])
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"Template not found: {p}\n"
                f"Expected file: {self.TEMPLATE_FILES[key]}"
            )
        return p

    def get_all(self) -> list:
        """Return list of (generator, output_suffix) tuples."""
        return [
            (SyllabusGenerator(self._path("syllabus")),
             "SYLLABUS_ACCEPTANCE"),
            (ExamReturnsGenerator(self._path("exam_midterm"), "MIDTERM"),
             "EXAM_RETURNS_MIDTERM"),
            (ExamReturnsGenerator(self._path("exam_finals"),  "FINAL"),
             "EXAM_RETURNS_FINALS"),
            (TOSGenerator(self._path("tos_midterm"), "Midterm"),
             "TOS_MIDTERM"),
            (TOSGenerator(self._path("tos_finals"),  "Finals"),
             "TOS_FINALS"),
        ]

# ══ Student file loaders ══════════════════════════════════════════════════════
def load_students_excel(path: str) -> list:
    """Read Excel via ZIP/XML — avoids openpyxl style compatibility bugs."""
    from xml.etree import ElementTree as ET
    NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns = {"x": NS}

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("x:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS}}}t")))

        sheet = next((n for n in names
                      if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")), None)
        if not sheet:
            raise RuntimeError("No worksheet found.")

        def cell_val(c):
            t = c.get("t", "")
            if t == "inlineStr":
                is_el = c.find("x:is", ns)
                if is_el is not None:
                    return "".join(x.text or "" for x in is_el.iter(f"{{{NS}}}t"))
                return ""
            v = c.find("x:v", ns)
            if v is None or v.text is None: return ""
            return shared[int(v.text)] if t == "s" else v.text

        students = []
        for i, row in enumerate(
                ET.fromstring(z.read(sheet)).findall(".//x:sheetData/x:row", ns)):
            cells = row.findall("x:c", ns)
            a = cell_val(cells[0]).strip() if cells else ""
            b = cell_val(cells[1]).strip() if len(cells) > 1 else ""
            if i == 0 and a.lower() in ("name", "student name", "full name"):
                continue
            if a:
                students.append((a, b))
    return students

def load_students_csv(path: str) -> list:
    students = []
    encodings = ["utf-8", "utf-16", "utf-8-sig", "cp1252"]
    for enc in encodings:
        try:
            with open(path, newline="", encoding=enc) as f:
                for i, row in enumerate(csv.reader(f)):
                    if i == 0 and row and row[0].lower() in ("name","student name","full name"):
                        continue
                    if len(row) >= 2:
                        students.append((row[0].strip(), row[1].strip()))
                    elif len(row) == 1 and row[0].strip():
                        students.append((row[0].strip(), ""))
            return students
        except (UnicodeDecodeError, csv.Error):
            continue
    raise RuntimeError(f"Could not parse CSV {path} with any known encoding.")


def load_students(path: str) -> list:
    ext = os.path.splitext(path)[1].lower()
    return load_students_excel(path) if ext in (".xlsx", ".xls", ".xlsm") \
           else load_students_csv(path)

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
    """Prompt the user to pick a numbered option from a list."""
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
    """Parse a JSON payload or simple key=value payload into a class data dict."""
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
    """Read either a JSON file path or the JSON payload text itself."""
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
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "templates"))
    parser.add_argument("--output",    help="Output folder",
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             "output"))
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   CvSU CEIT DOCUMENT GENERATOR                       ║")
    print("║   Generates all 5 forms from a single input set      ║")
    print("╚══════════════════════════════════════════════════════╝\n")
    print("  Fill in the class details below.\n")

    info = collect_class_info(args)

    # Student file
    student_file = args.csv
    if not student_file:
        print()
        while True:
            student_file = input("  Student list file (.xlsx or .csv): ") \
                           .strip().strip('"').strip("'")
            if not student_file:
                print("    (required)"); continue
            if not os.path.exists(student_file):
                print(f"    ⚠  File not found: {student_file!r}"); continue
            break

    students = load_students(student_file)
    print(f"  ✔  Loaded {len(students)} students\n")
    info.students = students

    # Templates folder check
    templates_dir = args.templates.strip().strip('"').strip("'")
    if not os.path.isdir(templates_dir):
        print(f"  ⚠  Templates folder not found: {templates_dir!r}")
        templates_dir = input("  Enter path to templates folder: ") \
                        .strip().strip('"').strip("'")
        if not os.path.isdir(templates_dir):
            print("  Templates folder not found. Exiting.")
            sys.exit(1)

    # Build output folder name from course section (sanitised)
    safe_section = info.course_section.replace("/", "-").replace(" ", "_")
    out_dir = os.path.join(args.output, safe_section)
    os.makedirs(out_dir, exist_ok=True)

    print(f"  📁  Output folder: {out_dir}\n")

    confirm = input("  Generate all 5 documents? [Y/n]: ").strip().lower()
    if confirm in ("n", "no"):
        print("  Cancelled.")
        sys.exit(0)

    print()
    factory = GeneratorFactory(templates_dir)
    try:
        generators = factory.get_all()
    except FileNotFoundError as e:
        print(f"\n  ❌  {e}")
        sys.exit(1)

    for gen, suffix in generators:
        out_path = os.path.join(out_dir, f"{safe_section}_{suffix}.docx")
        try:
            gen.generate(info, out_path)
        except Exception as e:
            print(f"  ❌  Failed {suffix}: {e}")

    print(f"\n✅  Done! All documents saved to: {out_dir}\n")

if __name__ == "__main__":
    main()
