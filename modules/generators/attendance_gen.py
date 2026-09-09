#!/usr/bin/env python3
"""
CvSU Class Attendance Sheet Generator
Cavite State University — Don Severino delas Alas Campus

Generates attendance sheets from Word templates (.docx) with dynamic week
columns, session groupings, date boundaries, and font scaling.
"""

import argparse
import calendar
import copy
import io
import os
import re
import sys
import zipfile
from datetime import date
from lxml import etree

from modules.common.docx_utils import (
    W,
    W14,
    w,
    wt,
    get_full_text,
    auto_scale_font,
    _auto_scale_font,
    load_docx,
    save_docx,
)
from modules.common.logger import logger
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
    pass

class EmptyDateError(Exception):
    pass

MONTHS = {
    1: "JANUARY", 2: "FEBRUARY", 3: "MARCH", 4: "APRIL",
    5: "MAY", 6: "JUNE", 7: "JULY", 8: "AUGUST",
    9: "SEPTEMBER", 10: "OCTOBER", 11: "NOVEMBER", 12: "DECEMBER"
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

def parse_schedule_days(schedule: str) -> list:
    days = {
        "mon":0,"monday":0,"tue":1,"tues":1,"tuesday":1,
        "wed":2,"wednesday":2,"thu":3,"thur":3,"thurs":3,"thursday":3,
        "fri":4,"friday":4,"sat":5,"saturday":5,"sun":6,"sunday":6,
    }
    day_part = schedule.split("/", 1)[1] if "/" in schedule else schedule
    parsed = []
    for token in re.split(r"[\s,]+", day_part.lower()):
        token = token.strip()
        if token in days and days[token] not in parsed:
            parsed.append(days[token])

    if parsed:
        return parsed

    fallback = extract_weekday_from_schedule(schedule)
    return [fallback] if fallback is not None else []

def parse_schedule_slots(schedule: str) -> list:
    if "/" not in schedule:
        return []
    time_part = schedule.split("/", 1)[0]
    return [slot.strip() for slot in time_part.split(",") if slot.strip()]

def parse_explicit_schedule_meetings(schedule: str) -> list:
    if ":" not in schedule:
        return []

    days = {
        "mon":0,"monday":0,"tue":1,"tues":1,"tuesday":1,
        "wed":2,"wednesday":2,"thu":3,"thur":3,"thurs":3,"thursday":3,
        "fri":4,"friday":4,"sat":5,"saturday":5,"sun":6,"sunday":6,
    }
    meetings = []
    for segment in re.split(r"[;\n|]+", schedule):
        segment = segment.strip()
        if not segment or ":" not in segment:
            continue
        day_part, slot_part = segment.split(":", 1)
        slot_label = slot_part.strip()
        day_tokens = [tok.strip().lower() for tok in re.split(r"[\s,]+", day_part) if tok.strip()]
        matched_days = [days[tok] for tok in day_tokens if tok in days]
        if not matched_days or not slot_label:
            continue
        for day_idx in matched_days:
            meetings.append((day_idx, slot_label))

    return meetings

def build_schedule_meetings(schedule: str) -> list:
    explicit = parse_explicit_schedule_meetings(schedule)
    if explicit:
        return explicit

    days = parse_schedule_days(schedule)
    slots = parse_schedule_slots(schedule) or [""]
    return [(day_idx, slot_label) for day_idx in days for slot_label in slots]

def build_schedule_label(schedule: str) -> str:
    meetings = build_schedule_meetings(schedule)
    if not meetings:
        return schedule

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if ":" in schedule:
        return "; ".join(f"{day_names[d]}: {slot}" for d, slot in meetings)

    days = []
    slots = []
    for day_idx, slot_label in meetings:
        if day_idx not in days:
            days.append(day_idx)
        if slot_label and slot_label not in slots:
            slots.append(slot_label)

    day_text = ", ".join(day_names[d] for d in days) if days else ""
    slot_text = ", ".join(slots) if slots else ""
    if day_text and slot_text:
        return f"{slot_text} / {day_text}"
    return day_text or slot_text or schedule

def build_semester_label(semester_term: str, year: int) -> str:
    return f"{semester_term} Semester / A.Y. {year - 1}-{year}"

def get_class_dates_for_weekdays(months: list, year: int, weekdays: list, start_bound=None, end_bound=None) -> list:
    weekday_set = set(weekdays)
    dates = []
    
    first_m = months[0] if months else 1
    for m in months:
        y = year + 1 if m < first_m else year
        _, ndays = calendar.monthrange(y, m)
        for d in range(1, ndays + 1):
            if start_bound and m == start_bound[0] and d < start_bound[1]:
                continue
            if end_bound and m == end_bound[0] and d > end_bound[1]:
                continue
                
            dt = date(y, m, d)
            if dt.weekday() in weekday_set:
                dates.append(dt)
    return sorted(dates)

# ── XML text helpers ──────────────────────────────────────────────────────────

def _auto_scale_attendance_name(r_el, text: str, para=None):
    """
    Progressively scale font for student names in the attendance table
    according to the dynamic font ladder:
      - <= 25 chars: 9pt (sz="18")
      - 26-30 chars: 8pt (sz="16")
      - 31-35 chars: 7pt (sz="14")
      - > 35 chars: 6pt (sz="12")
    """
    length = len(text.strip())
    unbold = False
    if length <= 25:
        target_sz = "18"  # 9pt
    elif length <= 30:
        target_sz = "16"  # 8pt
    elif length <= 35:
        target_sz = "14"  # 7pt
    else:
        target_sz = "12"  # 6pt
        unbold = True

    rpr = r_el.find(w("rPr"))
    if rpr is None:
        rpr = etree.Element(w("rPr"))
        r_el.insert(0, rpr)
    sz = rpr.find(w("sz"))
    if sz is None:
        sz = etree.SubElement(rpr, w("sz"))
    sz.set(w("val"), target_sz)
    sz_cs = rpr.find(w("szCs"))
    if sz_cs is None:
        sz_cs = etree.SubElement(rpr, w("szCs"))
    sz_cs.set(w("val"), target_sz)

    if unbold:
        b = rpr.find(w("b"))
        if b is not None:
            rpr.remove(b)
        b_cs = rpr.find(w("bCs"))
        if b_cs is not None:
            rpr.remove(b_cs)

    if para is not None:
        ppr = para.find(w("pPr"))
        if ppr is not None:
            ppr_rpr = ppr.find(w("rPr"))
            if ppr_rpr is not None:
                psz = ppr_rpr.find(w("sz"))
                if psz is not None:
                    psz.set(w("val"), target_sz)
                psz_cs = ppr_rpr.find(w("szCs"))
                if psz_cs is not None:
                    psz_cs.set(w("val"), target_sz)
                if unbold:
                    pb = ppr_rpr.find(w("b"))
                    if pb is not None:
                        ppr_rpr.remove(pb)
                    pb_cs = ppr_rpr.find(w("bCs"))
                    if pb_cs is not None:
                        ppr_rpr.remove(pb_cs)

def set_para_text(para, text: str, shrink_threshold: int = 0, shrink_sz: str = "18", is_attendance_student: bool = False):
    for t in para.findall(w("r")):
        para.remove(t)
    r = etree.SubElement(para, w("r"))
    
    if is_attendance_student:
        _auto_scale_attendance_name(r, text, para=para)
    else:
        _auto_scale_font(r, text, shrink_threshold, shrink_sz)
        
    t = etree.SubElement(r, w("t"))
    t.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

def set_cell_width(tc, pct: int):
    tcpr = tc.find(w("tcPr"))
    if tcpr is None: return
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

def clone_student_row(template_row) -> etree._Element:
    row = copy.deepcopy(template_row)
    cells = row.findall(w("tc"))
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
    weekdays: list,
    students: list,
    start_bound=None,
    end_bound=None
):
    class_dates = get_class_dates_for_weekdays(months, year, weekdays, start_bound=start_bound, end_bound=end_bound)
    if not class_dates:
        raise EmptyDateError("No class dates found for the given months/year/weekdays.")

    week_groups = dates_to_weeks(class_dates)
    n_weeks = len(week_groups)
    schedule_meetings = build_schedule_meetings(class_schedule)
    if not schedule_meetings:
        schedule_meetings = [(day_idx, "") for day_idx in (weekdays or [0])]
    session_count = len(schedule_meetings)
    n_date_cols = n_weeks * session_count
    month_year_label = month_label(months, year)
    schedule_label = build_schedule_label(class_schedule)

    zin, root, body = load_docx(template_path)
    tables = body.findall(w("tbl"))
    if len(tables) < 2:
        raise TemplateError("Attendance template must contain at least two tables.")
    
    info_tbl  = tables[0]
    attn_tbl  = tables[1]

    info_rows = info_tbl.findall(w("tr"))
    if len(info_rows) < 5:
        raise TemplateError("Attendance template info table must have at least 5 rows.")

    def info_cell_para(row_idx, cell_idx):
        try:
            cells = info_rows[row_idx].findall(w("tc"))
            return cells[cell_idx].find(w("p"))
        except IndexError:
            raise TemplateError(f"Info table structure invalid: missing cell at row {row_idx}, col {cell_idx}.")

    set_para_text(info_cell_para(0, 1), course_code_title, shrink_threshold=40, shrink_sz="18")
    set_para_text(info_cell_para(0, 4), month_year_label)
    set_para_text(info_cell_para(1, 1), schedule_label, shrink_threshold=45, shrink_sz="18")
    set_para_text(info_cell_para(2, 1), semester_ay)
    set_para_text(info_cell_para(3, 1), room_assignment)
    set_para_text(info_cell_para(4, 1), instructor, shrink_threshold=35, shrink_sz="18")

    FIXED_PCT   = 248 + 1277 + 499 + 212 + 208 + 133
    DATE_POOL   = 5000 - FIXED_PCT
    DATE_W      = DATE_POOL // n_date_cols
    remainder   = DATE_POOL - (DATE_W * n_date_cols)
    NO_W    = 248
    NAME_W  = 1277 + remainder
    STNUM_W = 499
    LB_W    = 212
    LC_W    = 208
    R_W     = 133
    WEEK_W  = DATE_W * session_count
    SUM_W   = LB_W + LC_W + R_W

    orig_rows = attn_tbl.findall(w("tr"))
    if len(orig_rows) < 3:
        raise TemplateError("Attendance template attendance table must have at least 3 rows (2 headers, 1 student row).")
        
    orig_header0   = orig_rows[0]
    orig_header1   = orig_rows[1]
    orig_student   = orig_rows[2]

    for tr in orig_rows:
        attn_tbl.remove(tr)

    tblgrid = attn_tbl.find(w("tblGrid"))
    if tblgrid is not None:
        attn_tbl.remove(tblgrid)
    tblgrid = etree.SubElement(attn_tbl, w("tblGrid"))
    for cw in [NO_W, NAME_W, STNUM_W] + [DATE_W]*n_date_cols + [LB_W, LC_W, R_W]:
        gc = etree.SubElement(tblgrid, w("gridCol"))
        gc.set(w("w"), str(cw))

    row0 = copy.deepcopy(orig_header0)
    row0_cells = row0.findall(w("tc"))

    set_cell_width(row0_cells[0], NO_W)
    set_cell_width(row0_cells[1], NAME_W)
    set_cell_width(row0_cells[2], STNUM_W)

    for tc in row0_cells[3:]:
        row0.remove(tc)

    week_cell_template = row0_cells[3]
    for wi, wg in enumerate(week_groups, 1):
        tc = copy.deepcopy(week_cell_template)
        set_cell_width(tc, WEEK_W)
        set_gridspan(tc, session_count)
        p = tc.find(w("p"))
        if p is not None:
            set_para_text(p, f"WEEK {wi}")
        row0.append(tc)

    sum_tc = copy.deepcopy(row0_cells[-1])
    set_cell_width(sum_tc, SUM_W)
    set_gridspan(sum_tc, 3)
    p = sum_tc.find(w("p"))
    if p is not None:
        set_para_text(p, "")
    row0.append(sum_tc)
    attn_tbl.append(row0)

    row1 = copy.deepcopy(orig_header1)
    row1_cells = row1.findall(w("tc"))

    set_cell_width(row1_cells[0], NO_W)
    set_cell_width(row1_cells[1], NAME_W)
    set_cell_width(row1_cells[2], STNUM_W)

    for tc in row1_cells[3:]:
        row1.remove(tc)

    date_cell_template = row1_cells[3]

    for wg in week_groups:
        week_dates = {dt.weekday(): dt for dt in wg}
        for session_idx, (day_idx, slot_label) in enumerate(schedule_meetings, 1):
            dt = week_dates.get(day_idx)
            day_num = str(dt.day) if dt is not None else ""
            tc = copy.deepcopy(date_cell_template)
            set_cell_width(tc, DATE_W)
            paras = tc.findall(w("p"))
            if len(paras) >= 2:
                set_para_text(paras[0], day_num)
                set_para_text(paras[1], "")
            elif len(paras) == 1:
                set_para_text(paras[0], day_num)
            row1.append(tc)

    lb_template = row1_cells[-3]
    lc_template = row1_cells[-2]
    r_template  = row1_cells[-1]
    for tc_tmpl, wval in [(lb_template, LB_W), (lc_template, LC_W), (r_template, R_W)]:
        tc = copy.deepcopy(tc_tmpl)
        set_cell_width(tc, wval)
        row1.append(tc)

    attn_tbl.append(row1)

    orig_student_cells = orig_student.findall(w("tc"))
    att_cell_template  = orig_student_cells[3]
    lb_s = orig_student_cells[-3]
    lc_s = orig_student_cells[-2]
    r_s  = orig_student_cells[-1]

    MAX_ROWS = 40
    target_rows = max(MAX_ROWS, len(students))
    for row_idx in range(target_rows):
        name, stnum = students[row_idx] if row_idx < len(students) else ("", "")

        tr = copy.deepcopy(orig_student)
        cells = tr.findall(w("tc"))

        set_cell_width(cells[0], NO_W)
        set_cell_width(cells[1], NAME_W)
        set_cell_width(cells[2], STNUM_W)

        tcpr1 = cells[1].find(w("tcPr"))
        if tcpr1 is not None:
            tcmar = tcpr1.find(w("tcMar"))
            if tcmar is None:
                tcmar = etree.SubElement(tcpr1, w("tcMar"))
            left = tcmar.find(w("left"))
            if left is None:
                left = etree.SubElement(tcmar, w("left"))
            left.set(w("w"), "50")
            left.set(w("type"), "dxa")
            right = tcmar.find(w("right"))
            if right is None:
                right = etree.SubElement(tcmar, w("right"))
            right.set(w("w"), "50")
            right.set(w("type"), "dxa")

        trpr = tr.find(w("trPr"))
        if trpr is None:
            trpr = etree.SubElement(tr, w("trPr"))
        if trpr.find(w("cantSplit")) is None:
            etree.SubElement(trpr, w("cantSplit"))

        set_para_text(cells[0].find(w("p")), str(row_idx + 1))
        set_para_text(cells[1].find(w("p")), name, is_attendance_student=True)
        set_para_text(cells[2].find(w("p")), stnum)

        for tc in cells[3:]:
            tr.remove(tc)

        for _ in range(n_date_cols):
            tc = copy.deepcopy(att_cell_template)
            set_cell_width(tc, DATE_W)
            p = tc.find(w("p"))
            if p is not None:
                set_para_text(p, "")
            tr.append(tc)

        for tc_tmpl, wval in [(lb_s, LB_W), (lc_s, LC_W), (r_s, R_W)]:
            tc = copy.deepcopy(tc_tmpl)
            set_cell_width(tc, wval)
            p = tc.find(w("p"))
            if p is not None:
                set_para_text(p, "")
            tr.append(tc)

        attn_tbl.append(tr)

    save_docx(zin, root, output_path)
    logger.info(f"Generated attendance sheet: {output_path}")


def get_default_template_path(has_lab: bool = False) -> str:
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    template_name = "template lab and lec.docx" if has_lab else "template lec.docx"
    repo_root_template = os.path.join(script_dir, template_name)
    bundled_template = os.path.join(script_dir, "attendance", template_name)
    if os.path.exists(repo_root_template):
        return repo_root_template
    if os.path.exists(bundled_template):
        return bundled_template
    return bundled_template


def generate_attendance_for_month(template_path, output_path, info, students, month, year, class_day, start_bound=None, end_bound=None):
    """
    Wrapper for process_schedule.py / orchestrator to generate a single month attendance sheet.
    info: dict containing course, schedule, semester, room, instructor, subject
    """
    try:
        months = parse_months(month)
    except ValueError:
        months = [1]
        for k, v in MONTHS.items():
            if v.lower() == month.lower():
                months = [k]
                break
                
    schedule_days = []
    for d in class_day.split(","):
        try:
            schedule_days.append(parse_weekday(d.strip()))
        except ValueError:
            pass
    if not schedule_days:
        schedule_days = [0]
    year_int = int(year)
    
    try:
        build_attendance_sheet(
            template_path=template_path,
            output_path=output_path,
            course_code_title=f"{info.get('course', '')} - {info.get('subject', '')}",
            class_schedule=info.get('schedule', ''),
            semester_ay=info.get('semester', ''),
            room_assignment=info.get('room', ''),
            instructor=info.get('instructor', ''),
            months=months,
            year=year_int,
            weekdays=schedule_days,
            students=students,
            start_bound=start_bound,
            end_bound=end_bound
        )
        return "generated"
    except EmptyDateError:
        return "skipped_empty"


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
                       "07:00AM-09:00AM, 01:00PM-03:00PM / Thurs, Fri")
    semester_term = prompt("Semester (1st/2nd)", "2nd")
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
    sem_ay = build_semester_label(semester_term, year)

    schedule_days = parse_schedule_days(schedule)
    if not schedule_days:
        schedule_days = [day_idx for day_idx, _ in build_schedule_meetings(schedule) if day_idx is not None]
    if schedule_days:
        wd_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        print(f"  (Detected class day(s): {', '.join(wd_names[d] for d in schedule_days)})")
    else:
        auto_wd = extract_weekday_from_schedule(schedule)
        wd_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        if auto_wd is not None:
            print(f"  (Auto-detected class day: {wd_names[auto_wd]})")
            wd_raw = input(f"  Class day [{wd_names[auto_wd]}]: ").strip()
            schedule_days = [auto_wd if not wd_raw else parse_weekday(wd_raw)]
        else:
            schedule_days = [parse_weekday(prompt("Class day (Mon/Tue/Wed/Thu/Fri/Sat/Sun)"))]

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

    script_dir = os.path.dirname(os.path.abspath(__file__))
    if len(months) > 1:
        default_folder = os.path.join(script_dir, "attendance_output")
        folder_raw = input(f"\n  Output folder [{default_folder}]: ").strip().strip('"').strip("'")
        out_folder = folder_raw if folder_raw else default_folder
    else:
        out_folder = script_dir
    os.makedirs(out_folder, exist_ok=True)

    print()
    for m in months:
        dates = get_class_dates_for_weekdays([m], year, schedule_days)
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
            weekdays          = schedule_days,
            students          = students,
        )

    print(f"\n[DONE] All {len(files_to_gen)} file(s) generated in: {out_folder}\n")


if __name__ == "__main__":
    main()
