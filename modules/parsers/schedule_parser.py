import os
import re
import glob
import xlrd
import openpyxl
import datetime
from modules.common.logger import logger
from modules.common.excel_utils import safe_temp_copy, parse_excel_time, get_long_path
from modules.parsers.ceit_directory import SUBJECT_PREFIXES
from modules.common.config_manager import config_manager

def get_day_name(col_idx: int) -> str:
    days = {3: "Mon", 4: "Tue", 5: "Wed", 6: "Thu", 7: "Fri", 8: "Sat"}
    return days.get(col_idx, "Unknown")

def get_subject_code(s: str) -> str:
    """Extracts base subject code, removing lab/lec modifiers, hyphens, and spaces."""
    if not s:
        return ""
    prefix = re.split(r'[-–—―−]', str(s))[0].upper()
    prefix = re.sub(r'\(.*?\)', '', prefix)
    return re.sub(r'[^a-zA-Z0-9]', '', prefix)

format_time = parse_excel_time

def find_schedule_file(project_dir: str) -> str:
    """Return the schedule spreadsheet path, ignoring student roster files."""
    candidates = []
    search_dirs = [project_dir, os.path.join(project_dir, "schedules")]
    
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for pattern in ("*.xls", "*.xlsx", "*.xlsm"):
            for path in glob.glob(os.path.join(search_dir, pattern)):
                name = os.path.basename(path)
                lower_name = name.lower()
                if "list of students for" in lower_name or lower_name.endswith(".csv"):
                    continue
                candidates.append(path)

    if not candidates:
        raise FileNotFoundError(
            f"No schedule spreadsheet found in {project_dir} or its schedules/ directory. "
            "Please ensure your schedule file is present (e.g., Mina.xlsx, Rosales.xls)."
        )

    preferred = [p for p in candidates if "schedule" in os.path.basename(p).lower()]
    if preferred:
        return sorted(preferred, key=lambda p: os.path.basename(p).lower())[0]
    return sorted(candidates, key=lambda p: os.path.basename(p).lower())[0]

def parse_schedule(schedule_path: str) -> list:
    """Parses an instructor schedule (.xls or .xlsx) and extracts timetable grids and headers."""
    if not os.path.exists(schedule_path):
        logger.error(f"Format parsing failed on invalid path {schedule_path}")
        return []
        
    parsed_sheets = []
    tmp_path = safe_temp_copy(schedule_path)

    try:
        if schedule_path.lower().endswith(".xls"):
            wb = xlrd.open_workbook(tmp_path, formatting_info=True)
            for sheet_idx in range(wb.nsheets):
                sheet = wb.sheet_by_index(sheet_idx)
                grid = []
                for rx in range(sheet.nrows):
                    row_vals = []
                    for cx in range(sheet.ncols):
                        val = sheet.cell_value(rx, cx)
                        c_type = sheet.cell_type(rx, cx)
                        if c_type == xlrd.XL_CELL_TEXT:
                            row_vals.append(str(val))
                        elif c_type == xlrd.XL_CELL_NUMBER:
                            row_vals.append(str(int(val)) if val.is_integer() else str(val))
                        elif c_type == xlrd.XL_CELL_DATE:
                            t = xlrd.xldate_as_tuple(val, wb.datemode)
                            row_vals.append(f"{t[3]:02d}:{t[4]:02d}")
                        else:
                            row_vals.append(str(val))
                    grid.append(row_vals)
                parsed_sheets.append(grid)
        else:
            wb = openpyxl.load_workbook(tmp_path, data_only=True)
            try:
                for sheet in wb.worksheets:
                    grid = []
                    for row in sheet.iter_rows(values_only=True):
                        row_vals = []
                        for val in row:
                            if val is None:
                                row_vals.append("")
                            elif isinstance(val, (datetime.time, datetime.datetime)):
                                row_vals.append(val.strftime("%H:%M"))
                            elif isinstance(val, float):
                                row_vals.append(str(int(val)) if val.is_integer() else str(val))
                            else:
                                row_vals.append(str(val))
                        grid.append(row_vals)
                    parsed_sheets.append(grid)
            finally:
                wb.close()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            
    results = []
    for grid in parsed_sheets:
        if not grid:
            continue
            
        sched_defaults = config_manager.get_schedule_defaults()
        instructor = sched_defaults.get("default_instructor", "DAN JOSEPH A. ORTEGA")
        semester = sched_defaults.get("default_semester", "FIRST SEMESTER, AY 2026 - 2027")
        college = sched_defaults.get("default_college", "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY")
        start_row = sched_defaults.get("start_row", 18)
        end_row = sched_defaults.get("end_row", 46)
        
        for r in range(len(grid)):
            for c in range(len(grid[r])):
                val = grid[r][c].upper()
                
                if "COLLEGE OF" in val:
                    college = grid[r][c].strip()
                    
                if "SEMESTER" in val and re.search(r'\b(SY|AY|A\.Y\.|S\.Y\.)\b', val):
                    semester = grid[r][c]
                    
                if val.replace(":", "").strip() == "NAME":
                    if c + 1 < len(grid[r]) and grid[r][c+1].strip():
                        instructor = grid[r][c+1]
                    elif c + 2 < len(grid[r]) and grid[r][c+2].strip():
                        instructor = grid[r][c+2]
                        
                if val.strip() == "TIME" or val.strip() == "MONDAY":
                    if r + 1 < len(grid):
                        start_row = r + 1
                        
                if "SUBJECT" in val or "COURSE/YR/SEC" in val.replace(" ", "") or "CONTACT HOURS" in val:
                    if r > start_row:
                        end_row = r - 1
                        
        results.append({
            "grid": grid,
            "instructor": instructor,
            "semester": semester,
            "college": college,
            "start_row": start_row,
            "end_row": end_row
        })
        
    return results

def find_blocks_for_section(grid, section, start_row, end_row):
    search_str = section.replace("CSCS", "CS")
    if search_str.upper().startswith("BS"):
        search_str = search_str[2:]
        
    search_str = re.sub(r'([a-zA-Z]+)(\d)', r'\1 \2', search_str)
    
    seen_noon = False
    row_is_pm = {}
    for r_idx in range(start_row, min(end_row + 1, len(grid))):
        t_val = grid[r_idx][1] if len(grid[r_idx]) > 1 else ""
        t_fmt = parse_excel_time(t_val)
        if ("12:" in t_val or t_val.startswith("12") or t_val in ("0.5", "0.5208333333333334")) or (t_fmt != "SEE SCHEDULE" and "PM" in t_fmt):
            seen_noon = True
        row_is_pm[r_idx] = seen_noon

    blocks = []
    subject_prefixes = config_manager.get_subject_prefixes()
    for c in range(3, 9):
        for r in range(start_row, end_row + 1):
            if c < len(grid[r]):
                cell = grid[r][c].strip()
                if search_str in cell:
                    subject_row = r
                    for i in range(r, start_row - 1, -1):
                        val = grid[i][c].strip()
                        if val.startswith(subject_prefixes):
                            subject_row = i
                            break
                    
                    room_row = r
                    for i in range(r, end_row + 1):
                        val = grid[i][c].strip()
                        if i > r and val.startswith(subject_prefixes):
                            break
                        if val:
                            room_row = i
                            
                    start_time = grid[subject_row][1]
                    end_time = grid[room_row][2]
                    
                    start_pm_hint = row_is_pm.get(subject_row, None)
                    start_time_fmt = parse_excel_time(start_time, is_pm_hint=start_pm_hint) if start_time else ""
                    
                    end_pm_hint = True if (start_time_fmt and "PM" in start_time_fmt) else row_is_pm.get(room_row, None)
                    end_time_fmt = parse_excel_time(end_time, is_pm_hint=end_pm_hint) if end_time else ""
                    
                    day = get_day_name(c)
                    
                    section_cell_parts = [p.strip() for p in grid[r][c].split('/')]
                    if len(section_cell_parts) > 1 and search_str.upper().replace(" ", "") in section_cell_parts[0].upper().replace(" ", ""):
                        room = section_cell_parts[1]
                    else:
                        room = grid[room_row][c].strip()
                    
                    type_str = ""
                    is_async = False
                    for i in range(subject_row, room_row + 1):
                        v = grid[i][c].strip().lower()
                        if i > subject_row:
                            if "async" in v or "online" in v or "virtual" in v:
                                is_async = True
                        if "lab" in v:
                            type_str = "LAB"
                        elif "lec" in v and not type_str:
                            type_str = "LEC"
                            
                    subject_title = grid[subject_row][c].strip()
                    if is_async:
                        continue
                    blocks.append({
                        'start_time': start_time_fmt,
                        'end_time': end_time_fmt,
                        'day': day,
                        'room': room,
                        'type': type_str,
                        'subject_title': subject_title,
                        'is_async': is_async
                    })
    return blocks

def inspect_schedule_file(schedule_path: str):
    """Parse schedule to extract instructor, college, semester, and sections from grid."""
    schedule_path = get_long_path(schedule_path)
    if not schedule_path or not os.path.exists(schedule_path):
        return None
    try:
        parsed = parse_schedule(schedule_path)
        if not parsed:
            return None
        
        primary = parsed[0]
        semester = primary.get("semester", "")
        college = primary.get("college", "")

        instructor = ""
        for s in parsed:
            inst = s.get("instructor", "").strip()
            if inst:
                if len(inst.split()) >= 2 and not any(code in inst.upper() for code in ["PT1", "PT2", "PT3", "DEPT", "FACULTY"]):
                    instructor = inst
                    if not semester and s.get("semester"):
                        semester = s.get("semester")
                    if not college and s.get("college"):
                        college = s.get("college")
                    break
                elif not instructor:
                    instructor = inst
        if not instructor:
            instructor = primary.get("instructor", "")
        
        sections = set()
        total_slots = 0
        for s in parsed:
            grid = s["grid"]
            start_row = s["start_row"]
            end_row = s["end_row"]
            for r in range(start_row, min(end_row + 1, len(grid))):
                for c in range(3, min(9, len(grid[r]))):
                    val = grid[r][c].strip()
                    if val:
                        total_slots += 1
                        matches = re.findall(r'\b(BS[A-Z]+|[A-Z]{2,4})\s*\d[-–]\d+\b', val, re.IGNORECASE)
                        for m in matches:
                            sections.add(m.upper())
                            
        return {
            "instructor": instructor,
            "college": college,
            "semester": semester,
            "total_slots": total_slots,
            "detected_sections": sorted(list(sections))
        }
    except Exception as e:
        logger.error(f"Error in inspect_schedule_file: {e}", exc_info=True)
        return None

def _find_class_details_by_schedule_code(parsed_schedules, schedule_code):
    """Search parsed schedules for a timetable cell containing schedule_code."""
    if not parsed_schedules or not schedule_code:
        return None
    code_str = str(schedule_code).strip()
    subject_prefixes = config_manager.get_subject_prefixes()
    for sched in parsed_schedules:
        grid = sched["grid"]
        start_row = sched["start_row"]
        end_row = sched["end_row"]
        for r in range(start_row, min(end_row + 1, len(grid))):
            for c in range(3, min(9, len(grid[r]))):
                val = grid[r][c].strip()
                if code_str in val:
                    subj_row = r
                    for i in range(r, start_row - 1, -1):
                        v = grid[i][c].strip()
                        if v.startswith(subject_prefixes):
                            subj_row = i
                            break
                    subject_name = grid[subj_row][c].strip()
                    m_sec = re.findall(r'\b(BS[A-Z]+|[A-Z]{2,4})\s*\d[-–]\d+\b', val, re.IGNORECASE)
                    c_sec = m_sec[0] if m_sec else ""
                    return {
                        "course_sec": c_sec,
                        "subject_name": subject_name,
                        "instructor": sched.get("instructor", ""),
                        "semester": sched.get("semester", ""),
                        "college": sched.get("college", "")
                    }
    return None

def _find_candidate_classes_from_hints(parsed_schedules, hints):
    """Search parsed schedules for classes matching section or subject hints from a loose filename."""
    if not parsed_schedules or not hints:
        return []

    matches = []
    seen_codes = set()

    hint_sec = (hints.get("course_sec") or "").replace(" ", "").upper()
    hint_prefix = (hints.get("subject_prefix") or "").upper()
    hint_code = (hints.get("subject_code") or "").replace(" ", "").upper()
    subject_prefixes = config_manager.get_subject_prefixes()

    for sched in parsed_schedules:
        grid = sched["grid"]
        start_row = sched["start_row"]
        end_row = sched["end_row"]
        for r in range(start_row, min(end_row + 1, len(grid))):
            for c in range(3, min(9, len(grid[r]))):
                val = grid[r][c].strip()
                m_code = re.search(r'\b(20\d{6,7}|\d{8,9})\b', val)
                if not m_code:
                    continue
                code_str = m_code.group(1)
                if code_str in seen_codes:
                    continue

                subj_row = r
                for i in range(r, start_row - 1, -1):
                    v = grid[i][c].strip()
                    if v.startswith(subject_prefixes):
                        subj_row = i
                        break
                subject_name = grid[subj_row][c].strip()

                m_sec = re.findall(r'\b(?:BS)?([A-Za-z]{2,4})\s*(\d[-–]\d+)\b', val, re.IGNORECASE)
                c_sec = f"{m_sec[0][0].upper()} {m_sec[0][1]}" if m_sec else ""

                score = 0
                norm_c_sec = c_sec.replace(" ", "").upper()
                norm_subj = subject_name.replace(" ", "").upper()

                if hint_sec:
                    h_dig = re.findall(r'\d-\d+', hint_sec)
                    s_dig = re.findall(r'\d-\d+', norm_c_sec)
                    if h_dig and s_dig and h_dig[0] == s_dig[0]:
                        score += 3
                    if hint_sec in norm_c_sec or norm_c_sec in hint_sec:
                        score += 3

                if hint_code and hint_code in norm_subj:
                    score += 4
                elif hint_prefix and hint_prefix in norm_subj:
                    score += 2

                if score >= 3:
                    seen_codes.add(code_str)
                    matches.append({
                        "schedule_code": code_str,
                        "course_sec": c_sec,
                        "subject_name": subject_name,
                        "score": score
                    })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches
