import csv
import glob
import os
import re
import subprocess
import sys
import datetime

import ceit_generator
import attendancegen

import xlrd

def format_time(t_str):
    t_str = t_str.strip()
    if not t_str:
        return ""
    h, m = map(int, t_str.split(':'))
    ampm = "PM" if (1 <= h <= 6 or h == 12) else "AM"
    h12 = 12 if h == 12 else (h if h < 12 else h - 12)
    return f"{h12:02d}:{m:02d}{ampm}"

def get_day_name(col_idx):
    days = {3: "Mon", 4: "Tue", 5: "Wed", 6: "Thu", 7: "Fri", 8: "Sat"}
    return days.get(col_idx, "Unknown")

def parse_schedule(project_dir):
    xls_path = os.path.join(project_dir, "ORTEGA_SCHEDULE.xls")
    wb = xlrd.open_workbook(xls_path, formatting_info=True)
    sheet = wb.sheet_by_index(0)
    
    grid = []
    for rx in range(sheet.nrows):
        row_vals = []
        for cx in range(sheet.ncols):
            val = sheet.cell_value(rx, cx)
            if sheet.cell_type(rx, cx) == xlrd.XL_CELL_TEXT:
                row_vals.append(str(val))
            elif sheet.cell_type(rx, cx) == xlrd.XL_CELL_NUMBER:
                row_vals.append(str(int(val)) if val.is_integer() else str(val))
            else:
                row_vals.append(str(val))
        grid.append(row_vals)
        
    instructor = "DAN JOSEPH A. ORTEGA"
    semester = "FIRST SEMESTER, AY 2026 - 2027"
    start_row = 18
    end_row = 46
    
    for r in range(len(grid)):
        for c in range(len(grid[r])):
            val = grid[r][c].upper()
            
            if "SEMESTER" in val and ("SY " in val or "AY " in val):
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
                    
    return grid, instructor, semester, start_row, end_row

def find_blocks_for_section(grid, section, start_row, end_row):
    search_str = section.replace("BSCS", "CS ").replace("BSIT", "IT ")
    search_str = re.sub(r'([A-Z]+)(\d)', r'\1 \2', search_str)
    
    blocks = []
    for c in range(3, 9):
        for r in range(start_row, end_row + 1):
            if c < len(grid[r]):
                cell = grid[r][c].strip()
                if search_str in cell:
                    subject_row = r
                    for i in range(r, start_row-1, -1):
                        val = grid[i][c].strip()
                        if val.startswith("CVSU") or val.startswith("DCIT") or val.startswith("COSC"):
                            subject_row = i
                            break
                    
                    room_row = r
                    for i in range(r, end_row+1):
                        val = grid[i][c].strip()
                        if i > r and (val.startswith("CVSU") or val.startswith("DCIT") or val.startswith("COSC")):
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
                        v = grid[i][c].strip()
                        if "async" in v.lower():
                            is_async = True
                        if v in ["LAB", "LEC"]:
                            type_str = v
                            
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

def process_all():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    grid, instructor, semester_ay, s_row, e_row = parse_schedule(project_dir)
    
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
        
    xlsx_files = glob.glob(os.path.join(project_dir, "*.xlsx"))
    
    templates_dir = os.path.join(project_dir, "templates")
    if not os.path.exists(templates_dir):
        print(f"Error: Templates directory not found at {templates_dir}")
        return
        
    factory = ceit_generator.GeneratorFactory(templates_dir)
    attendance_template = os.path.join(project_dir, "attendance", "template.docx")
    
    for student_file in xlsx_files:
        filename = os.path.basename(student_file)
        m = re.match(r'^([A-Z0-9\-]+).*for\s+(\d+)\s*-\s*(.+?)\.xlsx', filename)
        if not m:
            continue
            
        course_sec = m.group(1).replace("CSCS", "CS")
        schedule_code = m.group(2)
        subject_name = m.group(3)
        
        blocks = find_blocks_for_section(grid, course_sec, s_row, e_row)
        
        if blocks:
            parts = []
            for b in blocks:
                typ = f"{b['type']}: " if b['type'] else ""
                parts.append(f"{b['start_time']}-{b['end_time']} / {b['day']} / {typ}{b['room']}")
            time_days_room = ", ".join(parts)
        else:
            time_days_room = "SEE SCHEDULE"
            
        print(f"\\nProcessing {course_sec} ({schedule_code}) - {subject_name}")
        print(f"  Schedule: {time_days_room}")
        
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
        
        section_dir = os.path.join(project_dir, "output", course_sec)
        ceit_dir = os.path.join(section_dir, "CEIT_Forms")
        attendance_dir = os.path.join(section_dir, "Attendance")
        
        os.makedirs(ceit_dir, exist_ok=True)
        os.makedirs(attendance_dir, exist_ok=True)
        
        for generator, suffix in factory.get_all():
            out_name = f"{course_sec}_{schedule_code}_{suffix}.docx"
            out_path = os.path.join(ceit_dir, out_name)
            generator.generate(info, out_path)
            
        days = []
        for b in blocks:
            day_idx = attendancegen.parse_weekday(b['day'])
            if day_idx not in days:
                days.append(day_idx)
        if not days:
            days = [0]
            
        for m_num in months:
            out_name = f"{course_sec}_{schedule_code}_ATTENDANCE_{attendancegen.MONTHS[m_num]}_{att_year}.docx"
            out_path = os.path.join(attendance_dir, out_name)
            try:
                attendancegen.build_attendance_sheet(
                    template_path=attendance_template,
                    output_path=out_path,
                    course_code_title=f"{subject_name.split(' - ')[0]} - {subject_name}",
                    class_schedule=time_days_room,
                    semester_ay=semester_ay,
                    room_assignment=", ".join([b['room'] for b in blocks]) if blocks else "N/A",
                    instructor=instructor,
                    months=[m_num],
                    year=att_year,
                    weekdays=days,
                    students=students
                )
            except ValueError as e:
                pass

if __name__ == "__main__":
    process_all()
