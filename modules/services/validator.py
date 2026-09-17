import os
import re
import csv
from modules.common.logger import logger
from modules.parsers.schedule_parser import (
    parse_schedule, find_blocks_for_section, get_subject_code,
    _find_class_details_by_schedule_code, _find_candidate_classes_from_hints,
    format_canonical_schedule, normalize_room
)
from modules.parsers.roster_parser import load_students
from modules.parsers.ceit_directory import (
    parse_filename_hints, get_prefix_metadata, KNOWN_LAB_SUBJECT_CODES, is_known_lab_subject
)

def validate_rosters(schedule_path: str, roster_paths: list, roster_configs: dict = None) -> list:
    """
    Perform pre-flight validation on a list of student roster files:
    - Match against expected filename pattern or manual roster configuration
    - Check column counts and extract student count
    - Determine if schedule code matches schedule timetable
    - Attach CEIT subject prefix and department metadata
    - Provide intelligent suggested matches and recommended official filename for incomplete files
    """
    known_schedule_codes = set()
    parsed_schedules = []
    if schedule_path and os.path.exists(schedule_path):
        try:
            parsed_schedules = parse_schedule(schedule_path)
            for s in parsed_schedules:
                grid = s["grid"]
                for r in grid:
                    for cell in r:
                        codes = re.findall(r'\b20\d{7}\b', str(cell))
                        known_schedule_codes.update(codes)
        except Exception as e:
            logger.error(f"Error reading schedule codes for validation: {e}")

    results = []
    for path in roster_paths:
        filename = os.path.basename(path)
        if filename.startswith("~$"):
            continue
            
        cfg = (roster_configs or {}).get(path) or (roster_configs or {}).get(filename) or {}
        linked_code = str(cfg.get("linked_schedule_code") or cfg.get("schedule_code") or "").strip()
        user_course_sec = str(cfg.get("course_sec") or "").strip()
        user_subject_name = str(cfg.get("subject_name") or "").strip()

        hints = parse_filename_hints(filename)
        candidates = _find_candidate_classes_from_hints(parsed_schedules, hints) if parsed_schedules else []

        m = re.match(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', filename, re.IGNORECASE)
        has_custom_info = bool(linked_code and (user_course_sec or user_subject_name or _find_class_details_by_schedule_code(parsed_schedules, linked_code)))

        if not m and not has_custom_info and not linked_code:
            if candidates:
                top = candidates[0]
                rec_course = top["course_sec"].replace(" ", "")
                rec_code = top["schedule_code"]
                rec_subj = top["subject_name"]
                rec_filename = f"{rec_course} List of Students for {rec_code}-{rec_subj}.xlsx"
            else:
                rec_filename = hints.get("recommended_filename", "")

            student_count = 0
            try:
                students = load_students(
                    path,
                    name_col=cfg.get("name_col"),
                    id_col=cfg.get("id_col"),
                    header_row=cfg.get("header_row")
                )
                student_count = len(students)
            except Exception:
                student_count = 0

            col_count = 2
            ext = os.path.splitext(path)[1].lower()
            if ext == ".csv":
                try:
                    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                        sample = f.read(2048)
                        f.seek(0)
                        delimiter = ','
                        try:
                            delimiter = csv.Sniffer().sniff(sample).delimiter
                        except Exception:
                            delimiter = ','
                        rdr = csv.reader(f, delimiter=delimiter)
                        row0 = next(rdr, None)
                        if row0:
                            col_count = len(row0)
                except Exception:
                    col_count = 2

            has_hints = bool(candidates or hints.get("course_sec") or hints.get("subject_prefix") or hints.get("subject_code") or hints.get("schedule_code"))
            issue_type = "incomplete_filename" if has_hints else "invalid_filename"
            msg = ("Incomplete filename details (Missing Schedule Code or Subject Title). Recommendation: rename file to official format."
                   if has_hints else
                   f"Invalid filename: {filename}. Expected format: [Course/Sec] List of Students for [ScheduleCode]-[Subject].xlsx")

            results.append({
                "path": path,
                "filename": filename,
                "status": "warning" if candidates else "error",
                "issue": issue_type,
                "message": msg,
                "student_count": student_count,
                "course_sec": hints.get("course_sec", ""),
                "schedule_code": "",
                "subject_name": hints.get("subject_name", ""),
                "column_count": col_count,
                "in_timetable": False,
                "can_link": True,
                "ceit_metadata": hints.get("ceit_metadata") or get_prefix_metadata(filename),
                "filename_hints": hints,
                "suggested_matches": candidates,
                "recommended_filename": rec_filename,
                "active_config": cfg
            })
            continue

        if m:
            raw_course = m.group(1).strip()
            schedule_code = m.group(2).strip()
            subject_name = m.group(3).strip()

            letters = re.sub(r'[^A-Za-z]', '', raw_course).upper()
            if letters.startswith('BS'):
                letters = letters[2:]
            if letters == 'CSCS':
                letters = 'CS'
            digits = re.sub(r'[^0-9]', '', raw_course)
            if len(digits) >= 2:
                course_sec = f"{letters}{digits[0]}-{digits[1:]}"
            else:
                course_sec = re.sub(r'\s+', '', raw_course).replace("CSCS", "CS")
        else:
            schedule_code = linked_code
            course_sec = user_course_sec
            subject_name = user_subject_name
            if not course_sec or not subject_name:
                class_info = _find_class_details_by_schedule_code(parsed_schedules, schedule_code)
                if class_info:
                    if not course_sec:
                        course_sec = class_info["course_sec"]
                    if not subject_name:
                        subject_name = class_info["subject_name"]
            if not course_sec:
                course_sec = hints.get("course_sec") or "MANUAL"
            if not subject_name:
                subject_name = hints.get("subject_name") or os.path.splitext(filename)[0]

        student_count = 0
        try:
            students = load_students(
                path,
                name_col=cfg.get("name_col"),
                id_col=cfg.get("id_col"),
                header_row=cfg.get("header_row")
            )
            student_count = len(students)
        except Exception:
            student_count = 0

        col_count = 2
        ext = os.path.splitext(path)[1].lower()
        if ext == ".csv":
            try:
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                    rdr = csv.reader(f)
                    row0 = next(rdr, None)
                    if row0:
                        col_count = len(row0)
            except Exception:
                pass
        elif ext in (".xlsx", ".xls", ".xlsm"):
            try:
                import zipfile
                from xml.etree import ElementTree as ET
                with zipfile.ZipFile(path, 'r') as z:
                    for sname in z.namelist():
                        if sname.startswith('xl/worksheets/sheet1') or sname.startswith('xl/worksheets/sheet'):
                            xml = z.read(sname)
                            root = ET.fromstring(xml)
                            ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                            first_row = root.find('.//x:row', ns)
                            if first_row is not None:
                                cells = first_row.findall('x:c', ns)
                                col_count = len(cells)
                            break
            except Exception:
                pass

        status = "valid"
        issue = ""
        msg = f"{student_count} students ready"
        if student_count == 0:
            status = "warning"
            issue = "no_students"
            msg = "No students detected in roster file"
        elif col_count > 2:
            status = "warning"
            issue = "extra_columns"
            msg = f"{col_count} columns found (auto-cleaned to Name & Student number)"

        if linked_code and not m:
            issue = "custom_linked" if not issue else f"{issue},custom_linked"
            msg = f"{student_count} students ready (linked to {schedule_code})"

        in_timetable = (schedule_code in known_schedule_codes) if known_schedule_codes else True
        ceit_meta = get_prefix_metadata(subject_name) or get_prefix_metadata(filename)

        results.append({
            "path": path,
            "filename": filename,
            "status": status,
            "issue": issue,
            "message": msg,
            "student_count": student_count,
            "course_sec": course_sec,
            "schedule_code": schedule_code,
            "subject_name": subject_name,
            "column_count": col_count,
            "in_timetable": in_timetable,
            "can_link": True,
            "ceit_metadata": ceit_meta,
            "active_config": cfg
        })

    return results

def detect_classes(schedule_path: str, roster_paths: list, roster_configs: dict = None) -> list:
    """Matches uploaded student roster files with classes extracted from schedule timetable grid."""
    if not os.path.exists(schedule_path):
        return []
    
    parsed_schedules = parse_schedule(schedule_path)
    detected = []
    
    for student_file in roster_paths:
        filename = os.path.basename(student_file)
        if filename.startswith("~$") or filename == os.path.basename(schedule_path):
            continue

        cfg = (roster_configs or {}).get(student_file) or (roster_configs or {}).get(filename) or {}
        linked_code = str(cfg.get("linked_schedule_code") or "").strip()

        m = re.match(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', filename, re.IGNORECASE)
        if not m and not linked_code:
            continue
            
        if m:
            raw_course = m.group(1).strip()
            letters = re.sub(r'[^A-Za-z]', '', raw_course).upper()
            if letters.startswith('BS'):
                letters = letters[2:]
            if letters == 'CSCS':
                letters = 'CS'
                
            digits = re.sub(r'[^0-9]', '', raw_course)
            if len(digits) >= 2:
                course_sec = f"{letters}{digits[0]}-{digits[1:]}"
            else:
                course_sec = re.sub(r'\s+', '', raw_course).replace("CSCS", "CS")
                
            schedule_code = m.group(2)
            subject_name = m.group(3)
        else:
            schedule_code = linked_code
            course_sec = cfg.get("course_sec", "")
            subject_name = cfg.get("subject_name", "")
            if not course_sec or not subject_name:
                class_info = _find_class_details_by_schedule_code(parsed_schedules, schedule_code)
                if class_info:
                    if not course_sec:
                        course_sec = class_info["course_sec"]
                    if not subject_name:
                        subject_name = class_info["subject_name"]
            if not course_sec:
                course_sec = "MANUAL"
            if not subject_name:
                subject_name = os.path.splitext(filename)[0]
        
        blocks = []
        found_sched = None
        for sched in parsed_schedules:
            b = find_blocks_for_section(sched["grid"], course_sec, sched["start_row"], sched["end_row"], instructor=sched.get("instructor", ""))
            if b:
                blocks = b
                found_sched = sched
                break
        has_lab = any(b.get("type", "").upper() == "LAB" for b in blocks)
        if not blocks and ("LAB" in subject_name.upper() or "LABORATORY" in subject_name.upper()):
            has_lab = True
        base_code = get_subject_code(subject_name)
        if not has_lab and (is_known_lab_subject(subject_name) or base_code in KNOWN_LAB_SUBJECT_CODES):
            has_lab = True

        if blocks:
            raw_sched_title = blocks[0].get('subject_title', '')
            clean_sched_code = re.sub(r'\(.*?\)', '', raw_sched_title).strip()
            sched_norm = re.sub(r'[^A-Za-z0-9]', '', clean_sched_code).upper()
            intended_norm = get_subject_code(subject_name)
            if sched_norm and intended_norm != sched_norm and intended_norm.startswith(sched_norm):
                parts = re.split(r'([-–—―−].*)', subject_name, maxsplit=1)
                rest = parts[1] if len(parts) > 1 else ""
                subject_name = f"{clean_sched_code} {rest}".strip() if rest else clean_sched_code

            inst_hint = found_sched.get("instructor", "") if found_sched else ""
            time_days_room = format_canonical_schedule(blocks, instructor=inst_hint)
        else:
            time_days_room = "SEE SCHEDULE"

        ceit_meta = get_prefix_metadata(subject_name) or get_prefix_metadata(filename)

        detected.append({
            "id": f"{schedule_code}_{course_sec}",
            "schedule_code": schedule_code,
            "course_sec": course_sec,
            "subject_name": subject_name,
            "schedule_desc": time_days_room,
            "has_lab": has_lab,
            "detected_type": "lecture_lab" if has_lab else "lecture_only",
            "roster_file": student_file,
            "ceit_metadata": ceit_meta
        })
        
    return detected
