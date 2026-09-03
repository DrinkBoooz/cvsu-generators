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

def format_time(t_str):
    t_str = str(t_str).strip()
    if not t_str:
        return ""
    
    try:
        # Check if it's an Excel float string like '0.2916666666666667'
        if ':' not in t_str:
            val = float(t_str)
            if 0 <= val < 1:
                total_minutes = round(val * 24 * 60)
                h = total_minutes // 60
                m = total_minutes % 60
            else:
                return t_str
        else:
            t_str_clean = t_str.upper().replace('AM', '').replace('PM', '').strip()
            h, m = map(int, t_str_clean.split(':'))
    except ValueError:
        return t_str
        
    has_pm_suffix = 'PM' in t_str.upper()
    has_am_suffix = 'AM' in t_str.upper()
    
    if has_pm_suffix:
        is_pm = True
    elif has_am_suffix:
        is_pm = False
    elif h >= 12:
        is_pm = True
    elif 1 <= h <= 6:
        is_pm = True
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

    if xls_path.lower().endswith(".xls"):
        wb = xlrd.open_workbook(xls_path, formatting_info=True)
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
        wb = openpyxl.load_workbook(xls_path, data_only=True)
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
    
    blocks = []
    for c in range(3, 9):
        for r in range(start_row, end_row + 1):
            if c < len(grid[r]):
                cell = grid[r][c].strip()
                if search_str in cell:
                    subject_row = r
                    for i in range(r, start_row-1, -1):
                        val = grid[i][c].strip()
                        SUBJECT_PREFIXES = ("CVSU", "DCIT", "COSC", "ITEC", "INSY", "GNED", "MATH", "STAT", "FITT", "NSTP", "PHYS", "PHED", "ECON", "BAMG")
                        if val.startswith(SUBJECT_PREFIXES):
                            subject_row = i
                            break
                    
                    room_row = r
                    for i in range(r, end_row+1):
                        val = grid[i][c].strip()
                        SUBJECT_PREFIXES = ("CVSU", "DCIT", "COSC", "ITEC", "INSY", "GNED", "MATH", "STAT", "FITT", "NSTP", "PHYS", "PHED", "ECON", "BAMG")
                        if i > r and val.startswith(SUBJECT_PREFIXES):
                            break
                        if val:
                            room_row = i
                            
                    start_time = grid[subject_row][1]
                    end_time = grid[room_row][2]
                    
                    start_time_fmt = format_time(start_time) if start_time else ""
                    end_time_fmt = format_time(end_time) if end_time else ""
                    
                    day = get_day_name(c)
                    room = grid[room_row][c].split('/')[0].strip()
                    
                    type_str = ""
                    is_async = False
                    for i in range(subject_row, room_row + 1):
                        v = grid[i][c].strip().lower()
                        if "async" in v or "online" in v or "virtual" in v:
                            is_async = True
                        if v.upper() in ["LAB", "LEC"]:
                            type_str = v.upper()
                            
                    if is_async:
                        continue
                            
                    blocks.append({
                        'start_time': start_time_fmt,
                        'end_time': end_time_fmt,
                        'day': day,
                        'room': room,
                        'type': type_str
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
    project_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    parsed_schedules = parse_schedule(schedule_path)
    if not parsed_schedules:
        print("Error: No valid schedules found.")
        return
        
    templates_dir = os.path.join(project_dir, "templates")
    if not os.path.exists(templates_dir):
        print(f"Error: Templates directory not found at {templates_dir}")
        return
        
    factory = GeneratorFactory(templates_dir)
    attendance_template = os.path.join(project_dir, "attendance", "template.docx")
    
    for student_file in xlsx_files:
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
        if not years:
            att_year = 2026
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
        
        course_dir = os.path.join(output_dir_base, course_sec)
        os.makedirs(course_dir, exist_ok=True)
        ceit_dir = os.path.join(course_dir, "CEIT_Forms")
        attendance_dir = os.path.join(course_dir, "Attendance")
        
        os.makedirs(ceit_dir, exist_ok=True)
        os.makedirs(attendance_dir, exist_ok=True)
        
        for generator, suffix in factory.get_all():
            out_name = f"{course_sec}_{schedule_code}_{suffix}.docx"
            out_path = os.path.join(ceit_dir, out_name)
            generator.generate(info, out_path)
            
        print("    -> Passing to Attendance Generator...")
        for b in blocks:
            att_out_name = f"{course_sec}_{schedule_code}_ATTENDANCE_{b['day']}.docx"
            att_out_path = os.path.join(attendance_dir, att_out_name)
            
            att_info = {
                "course": course_sec,
                "schedule": f"{b['start_time']}-{b['end_time']} / {b['day']}",
                "semester": semester_ay,
                "room": f"{b['type']}: {b['room']}" if b['type'] else b['room'],
                "instructor": instructor,
                "subject": subject_name
            }
            
            for m in months:
                month_name = datetime.date(2026, m, 1).strftime('%B')
                month_out_path = os.path.join(attendance_dir, f"{course_sec}_{schedule_code}_ATTENDANCE_{b['day']}_{month_name}.docx")
                try:
                    attendancegen.generate_attendance_for_month(
                        template_path=attendance_template,
                        output_path=month_out_path,
                        info=att_info,
                        students=students,
                        month=month_name,
                        year=str(att_year),
                        class_day=b['day'],
                        start_bound=start_bound,
                        end_bound=end_bound
                    )
                except Exception as e:
                    pass

        print("    -> Passing to Grade Generator...")
        grade_dir = os.path.join(course_dir, "Grades")
        os.makedirs(grade_dir, exist_ok=True)
        
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
            grade_out_name = f"{course_sec}_{schedule_code}_GRADING_SHEET.xlsx"
            grade_out_path = os.path.join(grade_dir, grade_out_name)
            grade_gen.generate(grade_info, students, grade_out_path)
            print("    -> Grades generated successfully.")
        except Exception as e:
            traceback.print_exc()

if __name__ == "__main__":
    pass
