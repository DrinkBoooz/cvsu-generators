#!/usr/bin/env python3
"""
CvSU CLASS ATTENDANCE SHEET GENERATOR
Cavite State University — Don Severino delas Alas Campus

Strategy: Deep-copy the original template zip, then:
  1. Replace info-table cell text in-place (preserves all formatting)
  2. Rebuild only the attendance table rows (using cloned XML from original)

Usage:
    python attendance_generator.py
    python attendance_generator.py --csv students.xlsx
"""

import argparse, calendar, copy, csv, io, os, re, sys, zipfile
from datetime import date
from lxml import etree

# ── Namespaces ────────────────────────────────────────────────────────────────
W   = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

def w(tag):  return f"{{{W}}}{tag}"
def wt(tag): return f"{{{W14}}}{tag}"

MONTHS = {
    1:"JANUARY",2:"FEBRUARY",3:"MARCH",4:"APRIL",
    5:"MAY",6:"JUNE",7:"JULY",8:"AUGUST",
    9:"SEPTEMBER",10:"OCTOBER",11:"NOVEMBER",12:"DECEMBER"
}

# ── Date helpers ──────────────────────────────────────────────────────────────

def get_class_dates(months: list, year: int, weekday: int) -> list:
    dates = []
    for m in months:
        _, ndays = calendar.monthrange(year, m)
        for d in range(1, ndays + 1):
            dt = date(year, m, d)
            if dt.weekday() == weekday:
                dates.append(dt)
    return sorted(dates)

def dates_to_weeks(dates: list) -> list:
    from collections import OrderedDict
    buckets = OrderedDict()
    for d in dates:
        key = (d.isocalendar()[0], d.isocalendar()[1])
        buckets.setdefault(key, []).append(d)
    return list(buckets.values())

def month_label(months: list, year: int) -> str:
    names = [MONTHS[m] for m in months]
    return f"{names[0]} {year}" if len(names) == 1 else f"{names[0]} - {names[-1]} {year}"

def parse_weekday(s: str) -> int:
    mapping = {
        "mon":0,"monday":0,"tue":1,"tues":1,"tuesday":1,
        "wed":2,"wednesday":2,"thu":3,"thur":3,"thurs":3,"thursday":3,
        "fri":4,"friday":4,"sat":5,"saturday":5,"sun":6,"sunday":6,
    }
    s = s.strip().lower()
    if s in mapping: return mapping[s]
    try:
        v = int(s)
        if 0 <= v <= 6: return v
    except ValueError: pass
    raise ValueError(f"Unknown weekday: {s!r}")

def parse_months(s: str) -> list:
    month_map = {}
    for i, name in MONTHS.items():
        month_map[str(i)] = i
        month_map[name[:3].lower()] = i
        month_map[name.lower()] = i
    s = s.strip()
    if "-" in s:
        parts = [p.strip() for p in s.split("-")]
        if len(parts) == 2:
            a = month_map.get(parts[0].lower(), month_map.get(parts[0]))
            b = month_map.get(parts[1].lower(), month_map.get(parts[1]))
            if a and b: return list(range(a, b+1))
    if "," in s:
        result = []
        for p in s.split(","):
            p = p.strip()
            m = month_map.get(p.lower(), month_map.get(p))
            if m: result.append(m)
        return result
    m = month_map.get(s.lower(), month_map.get(s))
    if m: return [m]
    raise ValueError(f"Cannot parse month(s): {s!r}")

def extract_weekday_from_schedule(schedule: str):
    days = {
        "mon":0,"monday":0,"tue":1,"tues":1,"tuesday":1,
        "wed":2,"wednesday":2,"thu":3,"thur":3,"thurs":3,"thursday":3,
        "fri":4,"friday":4,"sat":5,"saturday":5,"sun":6,"sunday":6,
    }
    for token in re.split(r"[\s/,]+", schedule.lower()):
        if token in days: return days[token]
    return None

# ── XML text helpers ──────────────────────────────────────────────────────────

def get_full_text(el) -> str:
    """Get all text content from an element."""
    return "".join(t.text or "" for t in el.iter(w("t")))

def set_para_text(para, text: str):
    """
    Replace text content of a paragraph while preserving the formatting
    of the first run found. Removes all runs then writes one clean run.
    """
    # Find first run to clone its rPr
    first_run = para.find(w("r"))
    rpr_clone = None
    if first_run is not None:
        rpr = first_run.find(w("rPr"))
        if rpr is not None:
            rpr_clone = copy.deepcopy(rpr)

    # Remove all runs and bookmarks
    for child in list(para):
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag in ("r", "hyperlink", "ins", "del"):
            para.remove(child)

    # Build a new run
    r = etree.SubElement(para, w("r"))
    if rpr_clone is not None:
        r.insert(0, rpr_clone)
    t = etree.SubElement(r, w("t"))
    t.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

def find_para_by_text(body, search: str):
    """Find the first paragraph whose full text contains search string."""
    for p in body.iter(w("p")):
        if search in get_full_text(p):
            return p
    return None

def find_cell_para(table, row_idx: int, cell_idx: int) -> etree._Element:
    """Get the first paragraph in a specific table cell."""
    rows = table.findall(w("tr"))
    cells = rows[row_idx].findall(w("tc"))
    return cells[cell_idx].find(w("p"))

# ── PCT width helpers ─────────────────────────────────────────────────────────

def set_cell_width(tc, pct: int):
    """Update a cell's tcW to a new pct value."""
    tcpr = tc.find(w("tcPr"))
    if tcpr is None:
        tcpr = etree.SubElement(tc, w("tcPr"))
    tcw = tcpr.find(w("tcW"))
    if tcw is None:
        tcw = etree.SubElement(tcpr, w("tcW"))
    tcw.set(w("w"), str(pct))
    tcw.set(w("type"), "pct")

def set_gridspan(tc, span: int):
    tcpr = tc.find(w("tcPr"))
    if tcpr is None: return
    gs = tcpr.find(w("gridSpan"))
    if span > 1:
        if gs is None:
            gs = etree.SubElement(tcpr, w("gridSpan"))
        gs.set(w("val"), str(span))
    else:
        if gs is not None:
            tcpr.remove(gs)

# ── Clone a row from the original template ───────────────────────────────────

def clone_student_row(template_row) -> etree._Element:
    """Deep-copy a student row and clear name/stnum/attendance cell text."""
    row = copy.deepcopy(template_row)
    cells = row.findall(w("tc"))
    # Clear cells 1+ (keep NO. cell as-is for now; we'll set it separately)
    for tc in cells[1:]:
        for p in tc.findall(w("p")):
            for r in p.findall(w("r")):
                for t in r.findall(w("t")):
                    t.text = ""
    return row

# ── Core builder ─────────────────────────────────────────────────────────────

def build_attendance_sheet(
    template_path: str,
    output_path: str,
    course_code_title: str,
    class_schedule: str,
    semester_ay: str,
    room_assignment: str,
    instructor: str,
    months: list,
    year: int,
    weekday: int,
    students: list,          # [(name, student_number), ...]
    sessions_per_class: int = 2,
):
    class_dates = get_class_dates(months, year, weekday)
    if not class_dates:
        raise ValueError("No class dates found for the given months/year/weekday.")

    week_groups = dates_to_weeks(class_dates)
    n_weeks = len(week_groups)
    n_date_cols = n_weeks * sessions_per_class
    month_year_label = month_label(months, year)

    # ── Load & parse template ─────────────────────────────────────────────────
    with open(template_path, "rb") as fh:
        template_bytes = fh.read()

    zin = zipfile.ZipFile(io.BytesIO(template_bytes))
    doc_xml = zin.read("word/document.xml")
    root = etree.fromstring(doc_xml)
    body = root.find(w("body"))
    tables = body.findall(w("tbl"))
    info_tbl  = tables[0]
    attn_tbl  = tables[1]

    # ══ 1. Fill info table ════════════════════════════════════════════════════
    # Row 0: cell 1 = course code+title,  cell 4 = Month & Year value
    info_rows = info_tbl.findall(w("tr"))

    def info_cell_para(row_idx, cell_idx):
        cells = info_rows[row_idx].findall(w("tc"))
        return cells[cell_idx].find(w("p"))

    set_para_text(info_cell_para(0, 1), course_code_title)
    set_para_text(info_cell_para(0, 4), month_year_label)
    set_para_text(info_cell_para(1, 1), class_schedule)
    set_para_text(info_cell_para(2, 1), semester_ay)
    set_para_text(info_cell_para(3, 1), room_assignment)
    set_para_text(info_cell_para(4, 1), instructor)

    # ══ 2. Rebuild attendance table rows ═════════════════════════════════════
    #
    # Template has 4 weeks (8 date cols). We may have 3, 4, or 5 weeks.
    # Strategy:
    #   - Clone header rows from template, adjust gridSpan + pct widths
    #   - Clone student rows from template, clear and refill
    #
    # PCT layout (total = 5000):
    #   Fixed:  NO=248, NAME=1277, STNUM=499, LB=212, LC=208, R=133  → 2577
    #   Date pool: 5000 - 2577 = 2423 pct → divide among n_date_cols
    #   WEEK span cell = DATE_W * sessions_per_class pct
    #   Summary span cell (row 0) = LB+LC+R = 553 pct, gridSpan=3

    FIXED_PCT   = 248 + 1277 + 499 + 212 + 208 + 133   # 2577
    DATE_POOL   = 5000 - FIXED_PCT                       # 2423
    DATE_W      = DATE_POOL // n_date_cols
    # Absorb rounding remainder into NAME width
    remainder   = DATE_POOL - (DATE_W * n_date_cols)
    NO_W    = 248
    NAME_W  = 1277 + remainder
    STNUM_W = 499
    LB_W    = 212
    LC_W    = 208
    R_W     = 133
    WEEK_W  = DATE_W * sessions_per_class   # width of each WEEK header cell
    SUM_W   = LB_W + LC_W + R_W            # width of lb+lc+r header cell

    # ── Grab template rows to clone from ─────────────────────────────────────
    orig_rows = attn_tbl.findall(w("tr"))
    orig_header0   = orig_rows[0]   # WEEK header row
    orig_header1   = orig_rows[1]   # Date/lb/lc/r row
    orig_student   = orig_rows[2]   # First student row (use as clone source)

    # ── Remove ALL existing rows from table ───────────────────────────────────
    for tr in orig_rows:
        attn_tbl.remove(tr)

    # Update tblGrid
    tblgrid = attn_tbl.find(w("tblGrid"))
    if tblgrid is not None:
        attn_tbl.remove(tblgrid)
    tblgrid = etree.SubElement(attn_tbl, w("tblGrid"))
    for cw in [NO_W, NAME_W, STNUM_W] + [DATE_W]*n_date_cols + [LB_W, LC_W, R_W]:
        gc = etree.SubElement(tblgrid, w("gridCol"))
        gc.set(w("w"), str(cw))

    # ── ROW 0: WEEK header ────────────────────────────────────────────────────
    # Template row 0 structure (4 weeks):
    #   tc[0]=NO(vMerge restart), tc[1]=NAME(vMerge restart), tc[2]=STNUM(vMerge restart)
    #   tc[3]=WEEK1(gridSpan=2), tc[4]=WEEK2(gs=2), tc[5]=WEEK3(gs=2), tc[6]=WEEK4(gs=2)
    #   tc[7]=summary(gridSpan=3, empty)
    row0 = copy.deepcopy(orig_header0)
    row0_cells = row0.findall(w("tc"))

    # Fix fixed col widths
    set_cell_width(row0_cells[0], NO_W)
    set_cell_width(row0_cells[1], NAME_W)
    set_cell_width(row0_cells[2], STNUM_W)

    # Remove all WEEK cells (indices 3 .. len-2) and summary cell (last)
    for tc in row0_cells[3:]:
        row0.remove(tc)

    # Re-add WEEK cells: clone from template tc[3] for each week
    week_cell_template = row0_cells[3]
    for wi, wg in enumerate(week_groups, 1):
        tc = copy.deepcopy(week_cell_template)
        set_cell_width(tc, WEEK_W)
        set_gridspan(tc, sessions_per_class)
        # Set text to "WEEK N"
        p = tc.find(w("p"))
        if p is not None:
            set_para_text(p, f"WEEK {wi}")
        row0.append(tc)

    # Re-add summary cell (clone from template last cell)
    sum_tc = copy.deepcopy(row0_cells[-1])
    set_cell_width(sum_tc, SUM_W)
    set_gridspan(sum_tc, 3)
    # Clear text
    p = sum_tc.find(w("p"))
    if p is not None:
        set_para_text(p, "")
    row0.append(sum_tc)
    attn_tbl.append(row0)

    # ── ROW 1: Date numbers + lb/lc/r ─────────────────────────────────────────
    # Template row 1 structure (4 weeks = 8 date cols):
    #   tc[0]=NO(vMerge cont), tc[1]=NAME(vMerge cont), tc[2]=STNUM(vMerge cont)
    #   tc[3..10] = date cells (each has 2 paras: "Date" + day_number)
    #   tc[11]=lb, tc[12]=lc, tc[13]=r
    row1 = copy.deepcopy(orig_header1)
    row1_cells = row1.findall(w("tc"))

    # Fix fixed col widths
    set_cell_width(row1_cells[0], NO_W)
    set_cell_width(row1_cells[1], NAME_W)
    set_cell_width(row1_cells[2], STNUM_W)

    # Remove all date cells and summary cells, keep only first 3
    for tc in row1_cells[3:]:
        row1.remove(tc)

    # Date cell template = tc[3] from original
    date_cell_template = row1_cells[3]

    for wg in week_groups:
        day_num = str(wg[0].day) if wg else ""
        for _ in range(sessions_per_class):
            tc = copy.deepcopy(date_cell_template)
            set_cell_width(tc, DATE_W)
            # The date cell has 2 paragraphs: "Date" + the number
            paras = tc.findall(w("p"))
            if len(paras) >= 2:
                set_para_text(paras[0], "Date")
                set_para_text(paras[1], day_num)
            elif len(paras) == 1:
                set_para_text(paras[0], day_num)
            row1.append(tc)

    # Re-add lb/lc/r cells from original template
    lb_template = row1_cells[-3]
    lc_template = row1_cells[-2]
    r_template  = row1_cells[-1]
    for tc_tmpl, wval in [(lb_template, LB_W), (lc_template, LC_W), (r_template, R_W)]:
        tc = copy.deepcopy(tc_tmpl)
        set_cell_width(tc, wval)
        row1.append(tc)

    attn_tbl.append(row1)

    # ── Student rows (40 rows) ────────────────────────────────────────────────
    # Template student row structure:
    #   tc[0]=NO, tc[1]=NAME, tc[2]=STNUM,
    #   tc[3..10]=attendance cols (8 for 4 weeks)
    #   tc[11]=lb, tc[12]=lc, tc[13]=r
    orig_student_cells = orig_student.findall(w("tc"))
    att_cell_template  = orig_student_cells[3]   # blank attendance cell
    lb_s = orig_student_cells[-3]
    lc_s = orig_student_cells[-2]
    r_s  = orig_student_cells[-1]

    MAX_ROWS = 40
    for row_idx in range(MAX_ROWS):
        name, stnum = students[row_idx] if row_idx < len(students) else ("", "")

        tr = copy.deepcopy(orig_student)
        cells = tr.findall(w("tc"))

        # Fix fixed col widths
        set_cell_width(cells[0], NO_W)
        set_cell_width(cells[1], NAME_W)
        set_cell_width(cells[2], STNUM_W)

        # Set NO., name, stnum
        set_para_text(cells[0].find(w("p")), str(row_idx + 1))
        set_para_text(cells[1].find(w("p")), name)
        set_para_text(cells[2].find(w("p")), stnum)

        # Remove existing attendance + summary cells
        for tc in cells[3:]:
            tr.remove(tc)

        # Add correct number of attendance cols
        for _ in range(n_date_cols):
            tc = copy.deepcopy(att_cell_template)
            set_cell_width(tc, DATE_W)
            p = tc.find(w("p"))
            if p is not None:
                set_para_text(p, "")
            tr.append(tc)

        # Add lb/lc/r
        for tc_tmpl, wval in [(lb_s, LB_W), (lc_s, LC_W), (r_s, R_W)]:
            tc = copy.deepcopy(tc_tmpl)
            set_cell_width(tc, wval)
            p = tc.find(w("p"))
            if p is not None:
                set_para_text(p, "")
            tr.append(tc)

        attn_tbl.append(tr)

    # ── Serialize & save ──────────────────────────────────────────────────────
    new_doc_xml = etree.tostring(root, xml_declaration=True,
                                 encoding="UTF-8", standalone=True)
    zout_buf = io.BytesIO()
    zout = zipfile.ZipFile(zout_buf, "w", compression=zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        if item.filename == "word/document.xml":
            zout.writestr(item, new_doc_xml)
        else:
            zout.writestr(item, zin.read(item.filename))
    zout.close()
    zin.close()

    with open(output_path, "wb") as fh:
        fh.write(zout_buf.getvalue())
    print(f"  ✅  Saved: {output_path}")

# ── Student file loaders ──────────────────────────────────────────────────────

def load_students_excel(path: str) -> list:
    """Read Excel by parsing XML directly — no openpyxl dependency."""
    import zipfile as zf
    from xml.etree import ElementTree as ET

    NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns = {"x": NS}

    with zf.ZipFile(path) as z:
        names = z.namelist()
        shared_strings = []
        if "xl/sharedStrings.xml" in names:
            ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss_root.findall("x:si", ns):
                text = "".join(t.text or "" for t in si.iter(f"{{{NS}}}t"))
                shared_strings.append(text)

        sheet_file = next(
            (n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")),
            None
        )
        if not sheet_file:
            raise RuntimeError("No worksheet found in Excel file.")

        sheet_root = ET.fromstring(z.read(sheet_file))

        def cell_value(c) -> str:
            t = c.get("t", "")
            if t == "inlineStr":
                is_el = c.find("x:is", ns)
                if is_el is not None:
                    return "".join(t_el.text or "" for t_el in is_el.iter(f"{{{NS}}}t"))
                return ""
            v_el = c.find("x:v", ns)
            if v_el is None or v_el.text is None: return ""
            if t == "s":
                idx = int(v_el.text)
                return shared_strings[idx] if idx < len(shared_strings) else ""
            return v_el.text

        students = []
        for i, row_el in enumerate(sheet_root.findall(".//x:sheetData/x:row", ns)):
            cells = row_el.findall("x:c", ns)
            col_a = cell_value(cells[0]).strip() if cells else ""
            col_b = cell_value(cells[1]).strip() if len(cells) > 1 else ""
            if i == 0 and col_a.lower() in ("name", "student name", "full name"):
                continue
            if col_a:
                students.append((col_a, col_b))
    return students

def load_students_csv(path: str) -> list:
    students = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0 and row and row[0].lower() in ("name", "student name", "full name"):
                continue
            if len(row) >= 2:
                students.append((row[0].strip(), row[1].strip()))
            elif len(row) == 1 and row[0].strip():
                students.append((row[0].strip(), ""))
    return students

def load_students(path: str) -> list:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return load_students_excel(path)
    return load_students_csv(path)


def get_default_template_path() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root_template = os.path.join(script_dir, "template.docx")
    bundled_template = os.path.join(script_dir, "attendance", "template.docx")
    if os.path.exists(repo_root_template):
        return repo_root_template
    if os.path.exists(bundled_template):
        return bundled_template
    return repo_root_template

# ── CLI helpers ───────────────────────────────────────────────────────────────

def prompt(label: str, default: str = "") -> str:
    if default:
        val = input(f"  {label} [{default}]: ").strip()
        return val if val else default
    while True:
        val = input(f"  {label}: ").strip()
        if val: return val
        print("    (required — please enter a value)")

def main():
    parser = argparse.ArgumentParser(description="CvSU Attendance Sheet Generator")
    parser.add_argument("--csv", help="Path to student list (.xlsx or .csv)")
    parser.add_argument("--template", default=get_default_template_path(),
        help="Path to template .docx")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║   CvSU CLASS ATTENDANCE SHEET GENERATOR              ║")
    print("║   Cavite State University — VPAA-QF-09               ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    course    = prompt("Course Code and Title",
                       "DCIT25 - DATA STRUCTURES AND ALGORITHMS")
    schedule  = prompt("Class Schedule",
                       "07:00AM-09:00AM, 01:00PM-03:00PM / Thurs")
    sem_ay    = prompt("Semester & Academic Year",
                       "2nd Semester / A.Y. 2025-2026")
    room      = prompt("Room Assignment",
                       "LAB: CCL 204, LEC: ITC 404")
    instructor= prompt("Name of Instructor", "DAN JOSEPH ORTEGA")

    while True:
        try:
            months = parse_months(prompt("Month (e.g. February, Feb-Mar, 2-3)", "February"))
            break
        except ValueError as e:
            print(f"    ⚠  {e}")

    year = int(prompt("Year", "2026"))

    auto_wd = extract_weekday_from_schedule(schedule)
    wd_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    if auto_wd is not None:
        print(f"  (Auto-detected class day: {wd_names[auto_wd]})")
        wd_raw = input(f"  Class day [{wd_names[auto_wd]}]: ").strip()
        weekday = auto_wd if not wd_raw else parse_weekday(wd_raw)
    else:
        weekday = parse_weekday(prompt("Class day (Mon/Tue/Wed/Thu/Fri/Sat/Sun)"))

    sessions = max(1, int(prompt("Sessions per class day (2 = Lab+Lec, 1 = single)", "2")))

    # Student file
    student_file = args.csv
    if not student_file:
        print()
        while True:
            student_file = input("  Student list file (.xlsx or .csv): ").strip().strip('"').strip("'")
            if not student_file:
                print("    (required)")
                continue
            if not os.path.exists(student_file):
                print(f"    ⚠  File not found: {student_file!r}")
                continue
            break

    students = load_students(student_file)
    print(f"  ✔  Loaded {len(students)} students from {student_file}")

    # Output folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if len(months) > 1:
        default_folder = os.path.join(script_dir, "attendance_output")
        folder_raw = input(f"\n  Output folder [{default_folder}]: ").strip().strip('"').strip("'")
        out_folder = folder_raw if folder_raw else default_folder
    else:
        out_folder = script_dir
    os.makedirs(out_folder, exist_ok=True)

    # Summary
    print()
    for m in months:
        dates = get_class_dates([m], year, weekday)
        print(f"  📅  {MONTHS[m]} {year}: {len(dates)} class date(s)")
        for d in dates:
            print(f"       {d.strftime('%B %d, %Y (%A)')}")

    print(f"\n  👥  Students: {len(students)}")
    files_to_gen = []
    for m in months:
        fname = f"{MONTHS[m]}_{year}_ATTENDANCE.docx"
        fpath = os.path.join(out_folder, fname)
        print(f"  📄  {fpath}")
        files_to_gen.append((m, fpath))

    confirm = input("\n  Generate? [Y/n]: ").strip().lower()
    if confirm in ("n", "no"):
        print("  Cancelled.")
        sys.exit(0)

    # Validate template
    template = args.template
    if not os.path.exists(template):
        print(f"\n  ⚠  Template not found at: {template}")
        alt = input("  Enter path to template .docx: ").strip().strip('"').strip("'")
        if not alt or not os.path.exists(alt):
            print("  Template not found. Exiting.")
            sys.exit(1)
        template = alt

    print()
    for m, fpath in files_to_gen:
        build_attendance_sheet(
            template_path     = template,
            output_path       = fpath,
            course_code_title = course,
            class_schedule    = schedule,
            semester_ay       = sem_ay,
            room_assignment   = room,
            instructor        = instructor,
            months            = [m],
            year              = year,
            weekday           = weekday,
            students          = students,
            sessions_per_class= sessions,
        )

    print(f"\n✅  Done! {len(files_to_gen)} file(s) generated in: {out_folder}\n")

if __name__ == "__main__":
    main()