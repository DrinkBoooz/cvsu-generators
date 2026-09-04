import csv
import glob
import os
import re
import datetime
from collections import defaultdict
from ceit_generator import GeneratorFactory
import ceit_generator
import attendancegen
import sys
import xlrd
import openpyxl 
import traceback
from grade_generator import GradeGenerator
import logging
from logging.handlers import RotatingFileHandler

def get_logger():
    app_data = os.getenv('APPDATA') or os.path.expanduser("~")
    log_dir = os.path.join(app_data, "CVSU_Generators", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "generator.log")
    
    logger = logging.getLogger("cvsu_generators")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = get_logger()

def get_long_path(p: str) -> str:
    if not p:
        return p
    p = os.path.abspath(p)
    if os.name == 'nt' and not p.startswith('\\\\?\\'):
        return '\\\\?\\' + p
    return p

def sanitize_filename(name: str) -> str:
    """Remove illegal characters for Windows/Linux file paths and prevent directory traversal."""
    if not name:
        return "Unknown"
    name = str(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Prevent path traversal by neutralizing consecutive dots
    name = re.sub(r'\.{2,}', '_', name).strip()
    name = name.strip('. ')
    if not name:
        return "Unknown"
        
    base = name.split('.')[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if base in reserved:
        name = name + "_"
        
    return name

def get_subject_code(s: str) -> str:
    """Extracts base subject code, removing lab/lec modifiers, hyphens, and spaces."""
    if not s:
        return ""
    prefix = s.split('-')[0].upper()
    prefix = re.sub(r'\(.*?\)', '', prefix)
    return re.sub(r'[^a-zA-Z0-9]', '', prefix)

def format_time(t_str, is_pm_hint=None):
    t_str = str(t_str).strip()
    if not t_str:
        return "SEE SCHEDULE"
    
    try:
        # Check if it's an Excel float string like '0.2916666666666667'
        if ':' not in t_str:
            val = float(t_str)
            if 0 <= val < 1:
                total_minutes = round(val * 24 * 60)
                h = total_minutes // 60
                m = total_minutes % 60
            else:
                return "SEE SCHEDULE"
        else:
            t_str_clean = t_str.upper().replace('AM', '').replace('PM', '').strip()
            h, m = map(int, t_str_clean.split(':'))
    except ValueError:
        return "SEE SCHEDULE"
        
    has_pm_suffix = 'PM' in t_str.upper()
    has_am_suffix = 'AM' in t_str.upper()
    
    if has_pm_suffix:
        is_pm = True
    elif has_am_suffix:
        is_pm = False
    elif (1 <= h <= 6) or h >= 12:
        is_pm = True
    elif is_pm_hint is not None:
        is_pm = bool(is_pm_hint)
    else:
        is_pm = False
        
    h12 = h % 12
    if h12 == 0:
        h12 = 12
        
    ampm = "PM" if is_pm else "AM"
    return f"{h12:02d}:{m:02d}{ampm}"

def get_day_name(col_idx):
    days = {3: "Mon", 4: "Tue", 5: "Wed", 6: "Thu", 7: "Fri", 8: "Sat"}
    return days.get(col_idx, "Unknown")

def find_schedule_file(project_dir):
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
                # Ignore roster files
                if "list of students for" in lower_name:
                    continue
                if lower_name.endswith(".csv"):
                    continue
                candidates.append(path)

    if not candidates:
        raise FileNotFoundError(
            f"No schedule spreadsheet found in {project_dir} or its schedules/ directory. "
            "Please ensure your schedule file is present (e.g., Mina.xlsx, Rosales.xls) and that it doesn't contain 'list of students for' in the name."
        )

    # Prefer files that actually have 'schedule' in the name if there are multiple spreadsheets
    preferred = [p for p in candidates if "schedule" in os.path.basename(p).lower()]
    
    if preferred:
        return sorted(preferred, key=lambda p: os.path.basename(p).lower())[0]
    return sorted(candidates, key=lambda p: os.path.basename(p).lower())[0]


def parse_schedule(schedule_path):
    if not os.path.exists(schedule_path):
        print(f"Error: Format parsing failed on invalid path {schedule_path}")
        return []
        
    xls_path = schedule_path
    parsed_sheets = []
    
    import uuid
    import shutil
    ext = os.path.splitext(xls_path)[1]
    tmp_path = xls_path + f".{uuid.uuid4().hex[:8]}.tmp{ext}"
    shutil.copy2(xls_path, tmp_path)

    try:
        if xls_path.lower().endswith(".xls"):
            wb = xlrd.open_workbook(tmp_path, formatting_info=True)
            for sheet_idx in range(wb.nsheets):
                sheet = wb.sheet_by_index(sheet_idx)
                grid = []
                for rx in range(sheet.nrows):
                    row_vals = []
                    for cx in range(sheet.ncols):
                        val = sheet.cell_value(rx, cx)
                        if sheet.cell_type(rx, cx) == xlrd.XL_CELL_TEXT:
                            row_vals.append(str(val))
                        elif sheet.cell_type(rx, cx) == xlrd.XL_CELL_NUMBER:
                            row_vals.append(str(int(val)) if val.is_integer() else str(val))
                        elif sheet.cell_type(rx, cx) == xlrd.XL_CELL_DATE:
                            t = xlrd.xldate_as_tuple(val, wb.datemode)
                            row_vals.append(f"{t[3]:02d}:{t[4]:02d}")
                        else:
                            row_vals.append(str(val))
                    grid.append(row_vals)
                parsed_sheets.append(grid)
        else:
            import openpyxl
            import datetime
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
            
        instructor = "DAN JOSEPH A. ORTEGA"
        semester = "FIRST SEMESTER, AY 2026 - 2027"
        start_row = 18
        end_row = 46
        
        for r in range(len(grid)):
            for c in range(len(grid[r])):
                val = grid[r][c].upper()
                
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
            "start_row": start_row,
            "end_row": end_row
        })
        
    return results

def find_blocks_for_section(grid, section, start_row, end_row):
    search_str = section.replace("CSCS", "CS")
    if search_str.upper().startswith("BS"):
        search_str = search_str[2:]
        
    search_str = re.sub(r'([a-zA-Z]+)(\d)', r'\1 \2', search_str)
    
    # Map each schedule row to whether it falls in the afternoon/evening (PM).
    # Schedules start in the morning (e.g. 7:00 AM). Once 12:00 or 12:30 is reached,
    # all subsequent rows are afternoon/evening.
    seen_noon = False
    row_is_pm = {}
    for r_idx in range(start_row, min(end_row + 1, len(grid))):
        t_val = grid[r_idx][1] if len(grid[r_idx]) > 1 else ""
        t_fmt = format_time(t_val)
        if ("12:" in t_val or t_val.startswith("12") or t_val in ("0.5", "0.5208333333333334")) or (t_fmt != "SEE SCHEDULE" and "PM" in t_fmt):
            seen_noon = True
        row_is_pm[r_idx] = seen_noon

    blocks = []
    for c in range(3, 9):
        for r in range(start_row, end_row + 1):
            if c < len(grid[r]):
                cell = grid[r][c].strip()
                if search_str in cell:
                    SUBJECT_PREFIXES = (
                        "CVSU", "DCIT", "COSC", "ITEC", "INSY", "GNED", "MATH", "STAT",
                        "FITT", "NSTP", "PHYS", "PHED", "ECON", "BAMG", "ENGR", "BSCE",
                        "COEN", "ELET", "MECH", "AENG", "CHEM", "BIOL", "FILI", "HIST",
                        "COMM", "SOCS", "HUMA", "AGRI", "CRIM", "BMGT"
                    )
                    subject_row = r
                    for i in range(r, start_row-1, -1):
                        val = grid[i][c].strip()
                        if val.startswith(SUBJECT_PREFIXES):
                            subject_row = i
                            break
                    
                    room_row = r
                    for i in range(r, end_row+1):
                        val = grid[i][c].strip()
                        if i > r and val.startswith(SUBJECT_PREFIXES):
                            break
                        if val:
                            room_row = i
                            
                    start_time = grid[subject_row][1]
                    end_time = grid[room_row][2]
                    
                    start_pm_hint = row_is_pm.get(subject_row, None)
                    start_time_fmt = format_time(start_time, is_pm_hint=start_pm_hint) if start_time else ""
                    
                    # If start time is in the afternoon/evening (PM), end time is guaranteed to be PM
                    end_pm_hint = True if (start_time_fmt and "PM" in start_time_fmt) else row_is_pm.get(room_row, None)
                    end_time_fmt = format_time(end_time, is_pm_hint=end_pm_hint) if end_time else ""
                    
                    day = get_day_name(c)
                    
                    # The cell where we found the section might contain the room too (e.g. "BSCS 4-2 / ITC 201")
                    section_cell_parts = [p.strip() for p in grid[r][c].split('/')]
                    if len(section_cell_parts) > 1 and search_str.upper().replace(" ", "") in section_cell_parts[0].upper().replace(" ", ""):
                        room = section_cell_parts[1]
                    else:
                        room = grid[room_row][c].strip()
                    
                    type_str = ""
                    is_async = False
                    for i in range(subject_row, room_row + 1):
                        v = grid[i][c].strip().lower()
                        # Only check for async/online keywords in room or modality rows (exclude subject title row)
                        if i > subject_row:
                            if "async" in v or "online" in v or "virtual" in v:
                                is_async = True
                        if v.upper() in ["LAB", "LEC"]:
                            type_str = v.upper()
                            
                    subject_title = grid[subject_row][c].strip()
                    if is_async:
                        continue
                            
                    blocks.append({
                        'start_time': start_time_fmt,
                        'end_time': end_time_fmt,
                        'day': day,
                        'room': room,
                        'type': type_str,
                        'subject_title': subject_title
                    })
    return blocks

def detect_classes(schedule_path, roster_paths):
    if not os.path.exists(schedule_path):
        return []
    
    parsed_schedules = parse_schedule(schedule_path)
    detected = []
    
    for student_file in roster_paths:
        filename = os.path.basename(student_file)
        if filename.startswith("~$") or filename == os.path.basename(schedule_path):
            continue
        m = re.match(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', filename, re.IGNORECASE)
        if not m:
            continue
            
        raw_course = m.group(1).strip()
        
        # Robustly parse course and section (e.g., BS_CS_1_4 -> CS 1-4)
        letters = re.sub(r'[^A-Za-z]', '', raw_course).upper()
        if letters.startswith('BS'):
            letters = letters[2:]
        if letters == 'CSCS':
            letters = 'CS'
            
        digits = re.sub(r'[^0-9]', '', raw_course)
        if len(digits) >= 2:
            course_sec = f"{letters}{digits[0]}-{digits[1:]}" # Output like CS1-4 for searching
        else:
            course_sec = re.sub(r'\s+', '', raw_course).replace("CSCS", "CS")
            
        schedule_code = m.group(2)
        subject_name = m.group(3)
        
        blocks = []
        for sched in parsed_schedules:
            b = find_blocks_for_section(sched["grid"], course_sec, sched["start_row"], sched["end_row"])
            if b:
                blocks = b
                break
        has_lab = any(b.get("type", "").upper() == "LAB" for b in blocks)
        if not blocks and ("LAB" in subject_name.upper() or "LABORATORY" in subject_name.upper()):
            has_lab = True
            
        if blocks:
            parts = []
            for b in blocks:
                typ = f"{b['type']}: " if b['type'] else ""
                parts.append(f"{b['day']}: {b['start_time']}-{b['end_time']} / {typ}{b['room']}")
            time_days_room = "; ".join(parts)
        else:
            time_days_room = "SEE SCHEDULE"
            
        detected.append({
            "id": f"{schedule_code}_{course_sec}",
            "schedule_code": schedule_code,
            "course_sec": course_sec,
            "subject_name": subject_name,
            "schedule_desc": time_days_room,
            "has_lab": has_lab,
            "detected_type": "lecture_lab" if has_lab else "lecture_only"
        })
        
    return detected

def process_all(schedule_path, xlsx_files, output_dir_base, type_overrides=None, date_overrides=None):
    schedule_path = get_long_path(schedule_path)
    output_dir_base = get_long_path(output_dir_base)
    xlsx_files = [get_long_path(f) for f in xlsx_files]
    
    results = {
        "generated": {"attendance": [], "grades": [], "ceit": []},
        "skipped": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
        "errors": {"attendance": [], "grades": [], "ceit": [], "rosters": []}
    }
    project_dir = get_long_path(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))))
    parsed_schedules = parse_schedule(schedule_path)
    if not parsed_schedules:
        print("Error: No valid schedules found.")
        return results
        
    templates_dir = get_long_path(os.path.join(project_dir, "templates"))
    if not os.path.exists(templates_dir):
        print(f"Error: Templates directory not found at {templates_dir}")
        return results
        
    factory = GeneratorFactory(templates_dir)
    
    for student_file in xlsx_files:
        filename = os.path.basename(student_file)
        if filename.startswith("~$") or filename == os.path.basename(schedule_path):
            continue
        m = re.match(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', filename, re.IGNORECASE)
        if not m:
            results["skipped"]["rosters"].append(filename)
            continue
            
        raw_course = m.group(1).strip()
        
        # Robustly parse course and section (e.g., BS_CS_1_4 -> CS 1-4)
        letters = re.sub(r'[^A-Za-z]', '', raw_course).upper()
        if letters.startswith('BS'):
            letters = letters[2:]
        if letters == 'CSCS':
            letters = 'CS'
            
        digits = re.sub(r'[^0-9]', '', raw_course)
        if len(digits) >= 2:
            course_sec = f"{letters}{digits[0]}-{digits[1:]}" # Output like CS1-4 for searching
        else:
            course_sec = re.sub(r'\s+', '', raw_course).replace("CSCS", "CS")
        schedule_code = m.group(2)
        subject_name = m.group(3)
        
        blocks = []
        best_sched = parsed_schedules[0]
        for sched in parsed_schedules:
            b = find_blocks_for_section(sched["grid"], course_sec, sched["start_row"], sched["end_row"])
            if b:
                blocks = b
                best_sched = sched
                break
                
        instructor = best_sched["instructor"]
        semester_ay = best_sched["semester"]
        
        sem_lower = semester_ay.lower()
        if 'second' in sem_lower or '2nd' in sem_lower:
            months = [2, 3, 4, 5, 6]
            is_second = True
        else:
            months = [8, 9, 10, 11, 12]
            is_second = False
            
        years = re.findall(r'20\d{2}', semester_ay)
        att_year = None
        if date_overrides and date_overrides.get('startYear'):
            att_year = int(date_overrides['startYear'])
        elif not years:
            results["errors"]["attendance"].append(f"{course_sec} ({schedule_code}): Could not parse year from '{semester_ay}'")
        elif len(years) > 1 and is_second:
            att_year = int(years[1])
        else:
            att_year = int(years[0])

        # Date boundary logic
        start_bound = None
        end_bound = None
        if date_overrides and date_overrides.get('startMonth') and date_overrides.get('startDay') and date_overrides.get('endMonth') and date_overrides.get('endDay'):
            s_month = int(date_overrides['startMonth'])
            s_day = int(date_overrides['startDay'])
            e_month = int(date_overrides['endMonth'])
            e_day = int(date_overrides['endDay'])
            
            start_bound = (s_month, s_day)
            end_bound = (e_month, e_day)
            
            # Construct strict months array between start and end
            months = []
            cur = s_month
            while True:
                months.append(cur)
                if cur == e_month:
                    break
                cur += 1
                if cur > 12:
                    cur = 1
            
        # Filter blocks by the intended subject early to prevent CEIT/Grades for mismatched subjects
        intended_code = get_subject_code(subject_name)
        # Use substring match to allow 'DCIT21' to match 'DCIT21A'
        filtered_blocks = [b for b in blocks if intended_code in get_subject_code(b['subject_title']) or get_subject_code(b['subject_title']) in intended_code]
        
        if not filtered_blocks:
            msg = f"Skipping {course_sec} - {subject_name} because no blocks matched its subject code."
            print(f"\n{msg}")
            logger.info(msg)
            continue
            
        blocks = filtered_blocks
            
        if blocks:
            parts = []
            for b in blocks:
                typ = f"{b['type']}: " if b['type'] else ""
                parts.append(f"{b['day']}: {b['start_time']}-{b['end_time']} / {typ}{b['room']}")
            time_days_room = "; ".join(parts)
        else:
            time_days_room = "SEE SCHEDULE"
            
        print(f"\nProcessing {course_sec} ({schedule_code}) - {subject_name}")
        print(f"  Schedule: {time_days_room}")
        print(f"  Instructor: {instructor}")
        
        students = ceit_generator.load_students(student_file)
        info = ceit_generator.ClassInfo(
            instructor=instructor,
            course_section=course_sec,
            schedule_code=schedule_code,
            subject=subject_name,
            time_days_room=time_days_room,
            semester_ay=semester_ay,
            students=students
        )
        
        course_sec_safe = sanitize_filename(course_sec)
        schedule_code_safe = sanitize_filename(schedule_code)
        
        course_dir = os.path.join(output_dir_base, course_sec_safe)
        os.makedirs(course_dir, exist_ok=True)
        
        ceit_dir = os.path.join(course_dir, "CEIT_Forms")
        attendance_dir = os.path.join(course_dir, "Attendance")
        
        os.makedirs(ceit_dir, exist_ok=True)
        os.makedirs(attendance_dir, exist_ok=True)
        
        # Determine subject type: use override if specified, else auto-detect from schedule/subject
        auto_has_lab = any(b.get("type", "").upper() == "LAB" for b in blocks)
        if not blocks and ("LAB" in subject_name.upper() or "LABORATORY" in subject_name.upper()):
            auto_has_lab = True
            
        chosen_type = None
        if type_overrides:
            chosen_type = (
                type_overrides.get(f"{schedule_code}_{course_sec}")
                or type_overrides.get(schedule_code)
                or type_overrides.get(course_sec)
            )
            
        if chosen_type:
            has_lab = (chosen_type == "lecture_lab")
        else:
            has_lab = auto_has_lab
            
        if has_lab:
            attendance_template = get_long_path(os.path.join(project_dir, "attendance", "template lab and lec.docx"))
        else:
            attendance_template = get_long_path(os.path.join(project_dir, "attendance", "template lec.docx"))
        

        for gen_factory, suffix in factory.get_all():
            safe_suffix = sanitize_filename(suffix)
            out_name = f"{course_sec_safe}_{schedule_code_safe}_{safe_suffix}.docx"
            out_path = os.path.join(ceit_dir, out_name)
            try:
                generator = gen_factory()
                generator.generate(info, out_path)
                results["generated"]["ceit"].append(out_name)
            except Exception as e:
                err_msg = f"Failed CEIT ({suffix}): {str(e)}"
                logger.error(err_msg, exc_info=True)
                results["errors"]["ceit"].append(err_msg)
                print(f"    -> [ERROR] {err_msg}")
            
        print("    -> Passing to Attendance Generator...")
        if att_year is not None:
            # Group blocks by subject title (now normalized)
            from collections import defaultdict
            grouped_blocks = defaultdict(list)
            for b in blocks:
                grouped_blocks[get_subject_code(b['subject_title'])].append(b)
                
            for subj_title, subj_blocks in grouped_blocks.items():
                print(f"DEBUG: Matched {subj_title} == {intended_code}, months to process: {months}")

                # Consolidate schedule, room, and days
                sched_parts = []
                room_parts = []
                days_set = []
                safe_days = []
                for b in subj_blocks:
                    typ = f"{b['type']}: " if b['type'] else ""
                    # Format strictly as Day: Time for accurate Lab/Lec column matching in attendancegen
                    sched_parts.append(f"{b['day']}: {b['start_time']}-{b['end_time']}")
                    room_parts.append(f"{typ}{b['room']}")
                    if b['day'] not in days_set:
                        days_set.append(b['day'])
                        safe_days.append(sanitize_filename(b['day']))

                combined_schedule = "; ".join(sched_parts)
                combined_room = ", ".join(room_parts)
                combined_days = ", ".join(days_set)
                combined_safe_days = "_".join(safe_days)

                att_out_name = f"{course_sec_safe}_{schedule_code_safe}_ATTENDANCE_{combined_safe_days}.docx"
                att_out_path = os.path.join(attendance_dir, att_out_name)
                
                att_info = {
                    "course": course_sec,
                    "schedule": combined_schedule,
                    "semester": semester_ay,
                    "room": combined_room,
                    "instructor": instructor,
                    "subject": subject_name
                }
                
                for m in months:
                    month_name = datetime.date(2026, m, 1).strftime('%B')
                    safe_month = sanitize_filename(month_name)
                    month_out_name = f"{course_sec_safe}_{schedule_code_safe}_ATTENDANCE_{combined_safe_days}_{safe_month}.docx"
                    month_out_path = os.path.join(attendance_dir, month_out_name)
                    
                    year_for_month = (
                        att_year + 1
                        if (start_bound and end_bound and start_bound[0] > end_bound[0] and m < start_bound[0])
                        else att_year
                    )
                    try:
                        res = attendancegen.generate_attendance_for_month(
                            template_path=attendance_template,
                            output_path=month_out_path,
                            info=att_info,
                            students=students,
                            month=month_name,
                            year=str(year_for_month),
                            class_day=combined_days,
                            start_bound=start_bound,
                            end_bound=end_bound
                        )
                        print(f"DEBUG: generate_attendance_for_month for {month_name} returned {res}")
                        if res == "skipped_empty":
                            results["skipped"]["attendance"].append(f"{month_out_name} (0 days)")
                        else:
                            results["generated"]["attendance"].append(month_out_name)
                    except Exception as e:
                        err_msg = f"Failed Attendance ({month_out_name}): {str(e)}"
                        logger.error(err_msg, exc_info=True)
                        results["errors"]["attendance"].append(err_msg)
                        print(f"    -> [ERROR] {err_msg}")

        print("    -> Passing to Grade Generator...")
        grade_dir = os.path.join(course_dir, "Grades")
        os.makedirs(grade_dir, exist_ok=True)

        grade_info = {

            "instructor": instructor,
            "course": course_sec,
            "sched": schedule_code,
            "subject": subject_name,
            "semester": semester_ay,
            "time": time_days_room,
            "has_lab": has_lab
        }
        
        try:
            grade_gen = GradeGenerator(templates_dir)
            grade_out_name = f"{course_sec_safe}_{schedule_code_safe}_GRADING_SHEET.xlsx"
            grade_out_path = os.path.join(grade_dir, grade_out_name)
            grade_gen.generate(grade_info, students, grade_out_path)
            results["generated"]["grades"].append(grade_out_name)
            print("    -> Grades generated successfully.")
        except ValueError as e:
            err_msg = f"Failed Grades ({course_sec}_{schedule_code}): {str(e)}"
            logger.error(err_msg, exc_info=True)
            results["errors"]["grades"].append(err_msg)
            print(f"    -> [ERROR] {err_msg}")
        except Exception as e:
            err_msg = f"Failed Grades ({course_sec}_{schedule_code}): {str(e)}"
            logger.error(err_msg, exc_info=True)
            results["errors"]["grades"].append(err_msg)
            print(f"    -> [ERROR] {err_msg}")

    return results

if __name__ == "__main__":
    pass
