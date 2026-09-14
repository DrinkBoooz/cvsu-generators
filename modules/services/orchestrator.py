import os
import re
import sys
import datetime
from collections import defaultdict

from modules.common.logger import logger
from modules.common.excel_utils import get_long_path, sanitize_filename
from modules.models.schedule import ClassInfo
from modules.parsers.schedule_parser import (
    parse_schedule,
    find_blocks_for_section,
    get_subject_code,
    _find_class_details_by_schedule_code,
)
from modules.parsers.roster_parser import load_students
from modules.parsers.ceit_directory import parse_filename_hints, KNOWN_LAB_SUBJECT_CODES, is_known_lab_subject
from modules.generators.grade_gen import GradeGenerator
from modules.generators.attendance_gen import generate_attendance_for_month



def process_all(
    schedule_path,
    xlsx_files,
    output_dir_base,
    type_overrides=None,
    date_overrides=None,
    class_filter=None,
    engine_filter=None,
    progress_callback=None,
    cancel_event=None,
    roster_configs=None,
):
    """
    Core end-to-end orchestration service. Processes timetable schedules and student rosters,
    generating CEIT forms, attendance sheets, and grading spreadsheets.
    """
    schedule_path = get_long_path(schedule_path)
    output_dir_base = get_long_path(output_dir_base)
    xlsx_files = [get_long_path(f) for f in xlsx_files]
    
    results = {
        "generated": {"attendance": [], "grades": [], "ceit": []},
        "skipped": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
        "errors": {"attendance": [], "grades": [], "ceit": [], "rosters": []},
        "by_class": {},
        "cancelled": False
    }
    project_dir = get_long_path(getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    parsed_schedules = parse_schedule(schedule_path)
    if not parsed_schedules:
        logger.error("No valid schedules found.")
        return results
        
    templates_dir = get_long_path(os.path.join(project_dir, "templates"))
    if not os.path.exists(templates_dir):
        logger.error(f"Templates directory not found at {templates_dir}")
        return results
        
    from modules.generators.ceit_gen import GeneratorFactory
    factory = GeneratorFactory(templates_dir)
    enabled_engines = set(engine_filter) if engine_filter else {"attendance", "ceit", "grades"}
    
    # Pre-calculate exact total steps for precise progress reporting
    num_ceit_generators = len(factory.get_all()) if "ceit" in enabled_engines else 0
    total_estimated_steps = 0

    for student_file in xlsx_files:
        fn = os.path.basename(student_file)
        if fn.startswith("~$") or fn == os.path.basename(schedule_path):
            continue
        cfg = (roster_configs or {}).get(student_file) or (roster_configs or {}).get(fn) or {}
        linked_code = str(cfg.get("linked_schedule_code") or "").strip()

        m = re.match(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', fn, re.IGNORECASE)
        if not m and not linked_code:
            continue

        if m:
            raw_c = m.group(1).strip()
            let = re.sub(r'[^A-Za-z]', '', raw_c).upper()
            if let.startswith('BS'):
                let = let[2:]
            if let == 'CSCS':
                let = 'CS'

            dig = re.sub(r'[^0-9]', '', raw_c)
            if len(dig) >= 2:
                c_sec = f"{let}{dig[0]}-{dig[1:]}"
            else:
                c_sec = re.sub(r'\s+', '', raw_c).replace("CSCS", "CS")
            s_code = m.group(2)
            s_name = m.group(3)
        else:
            s_code = linked_code
            c_sec = cfg.get("course_sec", "")
            s_name = cfg.get("subject_name", "")
            if not c_sec or not s_name:
                c_info = _find_class_details_by_schedule_code(parsed_schedules, s_code)
                if c_info:
                    if not c_sec: c_sec = c_info["course_sec"]
                    if not s_name: s_name = c_info["subject_name"]
            if not c_sec: c_sec = "MANUAL"
            if not s_name: s_name = os.path.splitext(fn)[0]

        c_id = f"{s_code}_{c_sec}"
        if class_filter and (c_id not in class_filter and s_code not in class_filter and c_sec not in class_filter):
            continue

        pre_blocks = []
        pre_best_sched = parsed_schedules[0]
        for sched in parsed_schedules:
            b = find_blocks_for_section(sched["grid"], c_sec, sched["start_row"], sched["end_row"])
            if b:
                pre_blocks = b
                pre_best_sched = sched
                break

        int_code = get_subject_code(s_name)
        flt_blocks = [b for b in pre_blocks if int_code in get_subject_code(b['subject_title']) or get_subject_code(b['subject_title']) in int_code]
        if not flt_blocks and linked_code and pre_blocks:
            flt_blocks = pre_blocks
        if not flt_blocks:
            continue

        # CEIT tasks count
        total_estimated_steps += num_ceit_generators

        # Attendance tasks count
        if "attendance" in enabled_engines:
            pre_sem = pre_best_sched["semester"]
            sem_low = pre_sem.lower()
            if 'second' in sem_low or '2nd' in sem_low:
                class_months = [2, 3, 4, 5, 6]
                is_second = True
            else:
                class_months = [8, 9, 10, 11, 12]
                is_second = False

            pre_years = re.findall(r'20\d{2}', pre_sem)
            has_year = bool((date_overrides and date_overrides.get('startYear')) or pre_years)

            if date_overrides and date_overrides.get('startMonth') and date_overrides.get('startDay') and date_overrides.get('endMonth') and date_overrides.get('endDay'):
                s_m = int(date_overrides['startMonth'])
                e_m = int(date_overrides['endMonth'])
                class_months = []
                cur = s_m
                while True:
                    class_months.append(cur)
                    if cur == e_m:
                        break
                    cur += 1
                    if cur > 12:
                        cur = 1

            if has_year:
                pre_grouped = defaultdict(list)
                for b in flt_blocks:
                    pre_grouped[get_subject_code(b['subject_title'])].append(b)
                total_estimated_steps += len(pre_grouped) * len(class_months)

        # Grades task count
        if "grades" in enabled_engines:
            total_estimated_steps += 1

    total_estimated_steps = max(1, total_estimated_steps)
    current_step = 0

    def _notify(current_class, current_task):
        nonlocal current_step, total_estimated_steps
        current_step += 1
        if current_step > total_estimated_steps:
            total_estimated_steps = current_step
        if progress_callback:
            try:
                pct = int(min(99, (current_step / total_estimated_steps) * 100))
                progress_callback({
                    "percent": pct,
                    "current_class": current_class,
                    "current_task": current_task,
                    "step": current_step,
                    "total_steps": total_estimated_steps
                })
            except Exception as pe:
                logger.debug(f"Progress callback error: {pe}")
    
    for student_file in xlsx_files:
        if cancel_event and cancel_event.is_set():
            logger.info("Generation cancelled by user signal.")
            results["cancelled"] = True
            break

        filename = os.path.basename(student_file)
        if filename.startswith("~$") or filename == os.path.basename(schedule_path):
            continue

        cfg = (roster_configs or {}).get(student_file) or (roster_configs or {}).get(filename) or {}
        linked_code = str(cfg.get("linked_schedule_code") or "").strip()

        m = re.match(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', filename, re.IGNORECASE)
        if not m and not linked_code:
            results["skipped"]["rosters"].append(filename)
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
                c_info = _find_class_details_by_schedule_code(parsed_schedules, schedule_code)
                if c_info:
                    if not course_sec: course_sec = c_info["course_sec"]
                    if not subject_name: subject_name = c_info["subject_name"]
            if not course_sec: course_sec = "MANUAL"
            if not subject_name: subject_name = os.path.splitext(filename)[0]

        class_id = f"{schedule_code}_{course_sec}"
        if class_filter and (class_id not in class_filter and schedule_code not in class_filter and course_sec not in class_filter):
            continue
        
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
        college = best_sched.get("college", "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY")
        
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

        start_bound = None
        end_bound = None
        if date_overrides and date_overrides.get('startMonth') and date_overrides.get('startDay') and date_overrides.get('endMonth') and date_overrides.get('endDay'):
            s_month = int(date_overrides['startMonth'])
            s_day = int(date_overrides['startDay'])
            e_month = int(date_overrides['endMonth'])
            e_day = int(date_overrides['endDay'])
            
            start_bound = (s_month, s_day)
            end_bound = (e_month, e_day)
            
            months = []
            cur = s_month
            while True:
                months.append(cur)
                if cur == e_month:
                    break
                cur += 1
                if cur > 12:
                    cur = 1
            
        intended_code = get_subject_code(subject_name)
        filtered_blocks = [b for b in blocks if intended_code in get_subject_code(b['subject_title']) or get_subject_code(b['subject_title']) in intended_code]
        if not filtered_blocks and linked_code and blocks:
            filtered_blocks = blocks
        
        if not filtered_blocks:
            msg = f"Skipping {course_sec} - {subject_name} because no blocks matched its subject code."
            logger.info(msg)
            continue
            
        blocks = filtered_blocks

        # Reconcile subject_name with canonical schedule block code if matched (e.g. COSC 111A -> COSC 111)
        if blocks:
            raw_sched_title = blocks[0].get('subject_title', '')
            clean_sched_code = re.sub(r'\(.*?\)', '', raw_sched_title).strip()
            sched_norm = re.sub(r'[^A-Za-z0-9]', '', clean_sched_code).upper()
            intended_norm = get_subject_code(subject_name)
            if sched_norm and intended_norm != sched_norm and intended_norm.startswith(sched_norm):
                parts = re.split(r'([-–—―−].*)', subject_name, maxsplit=1)
                rest = parts[1] if len(parts) > 1 else ""
                subject_name = f"{clean_sched_code} {rest}".strip() if rest else clean_sched_code

        if blocks:
            parts = []
            for b in blocks:
                typ = f"{b['type']}: " if b['type'] else ""
                parts.append(f"{b['day']}: {b['start_time']}-{b['end_time']} / {typ}{b['room']}")
            time_days_room = "; ".join(parts)
        else:
            time_days_room = "SEE SCHEDULE"
            
        logger.info(f"Processing {course_sec} ({schedule_code}) - {subject_name}")
        logger.info(f"  Schedule: {time_days_room}")
        logger.info(f"  Instructor: {instructor}")
        
        students = load_students(
            student_file,
            name_col=cfg.get("name_col"),
            id_col=cfg.get("id_col"),
            header_row=cfg.get("header_row")
        )
        info = ClassInfo(
            instructor=instructor,
            course_section=course_sec,
            schedule_code=schedule_code,
            subject=subject_name,
            time_days_room=time_days_room,
            semester_ay=semester_ay,
            students=students,
            college=college
        )
        
        course_sec_safe = sanitize_filename(course_sec)
        schedule_code_safe = sanitize_filename(schedule_code)
        
        course_dir = os.path.join(output_dir_base, course_sec_safe)
        os.makedirs(course_dir, exist_ok=True)
        
        ceit_dir = os.path.join(course_dir, "CEIT_Forms")
        attendance_dir = os.path.join(course_dir, "Attendance")
        
        os.makedirs(ceit_dir, exist_ok=True)
        os.makedirs(attendance_dir, exist_ok=True)
        
        auto_has_lab = any(b.get("type", "").upper() == "LAB" for b in blocks)
        if not blocks and ("LAB" in subject_name.upper() or "LABORATORY" in subject_name.upper()):
            auto_has_lab = True
        base_code = get_subject_code(subject_name)
        if not auto_has_lab and (is_known_lab_subject(subject_name) or base_code in KNOWN_LAB_SUBJECT_CODES):
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
        
        if course_sec not in results["by_class"]:
            results["by_class"][course_sec] = {"ceit": [], "attendance": [], "grades": []}

        if "ceit" in enabled_engines:
            for gen_factory, suffix in factory.get_all():
                if cancel_event and cancel_event.is_set():
                    results["cancelled"] = True
                    break
                safe_suffix = sanitize_filename(suffix)
                out_name = f"{course_sec_safe}_{schedule_code_safe}_{safe_suffix}.docx"
                out_path = os.path.join(ceit_dir, out_name)
                try:
                    generator = gen_factory()
                    generator.generate(info, out_path)
                    results["generated"]["ceit"].append(out_name)
                    results["by_class"][course_sec]["ceit"].append({"name": out_name, "path": out_path})
                    _notify(course_sec, f"Created {suffix}")
                except Exception as e:
                    err_msg = f"Failed CEIT ({suffix}): {str(e)}"
                    logger.error(err_msg, exc_info=True)
                    results["errors"]["ceit"].append(err_msg)
                    _notify(course_sec, f"Error {suffix}")
            
        if cancel_event and cancel_event.is_set():
            results["cancelled"] = True
            break

        if "attendance" in enabled_engines:
            logger.info("  -> Generating Attendance...")
            if att_year is not None:
                grouped_blocks = defaultdict(list)
                for b in blocks:
                    grouped_blocks[get_subject_code(b['subject_title'])].append(b)
                    
                for subj_title, subj_blocks in grouped_blocks.items():
                    if cancel_event and cancel_event.is_set():
                        results["cancelled"] = True
                        break

                    sched_parts = []
                    room_parts = []
                    days_set = []
                    safe_days = []
                    for b in subj_blocks:
                        typ = f"{b['type']}: " if b['type'] else ""
                        sched_parts.append(f"{b['day']}: {b['start_time']}-{b['end_time']}")
                        room_parts.append(f"{typ}{b['room']}")
                        if b['day'] not in days_set:
                            days_set.append(b['day'])
                            safe_days.append(sanitize_filename(b['day']))

                    combined_schedule = "; ".join(sched_parts)
                    combined_room = ", ".join(room_parts)
                    combined_days = ", ".join(days_set)
                    combined_safe_days = "_".join(safe_days)

                    att_info = {
                        "course": course_sec,
                        "schedule": combined_schedule,
                        "semester": semester_ay,
                        "room": combined_room,
                        "instructor": instructor,
                        "subject": subject_name
                    }
                    
                    for m in months:
                        if cancel_event and cancel_event.is_set():
                            results["cancelled"] = True
                            break
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
                            res = generate_attendance_for_month(
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
                            if res == "skipped_empty":
                                results["skipped"]["attendance"].append(f"{month_out_name} (0 days)")
                            else:
                                results["generated"]["attendance"].append(month_out_name)
                                results["by_class"][course_sec]["attendance"].append({"name": month_out_name, "path": month_out_path})
                            _notify(course_sec, f"Attendance {month_name}")
                        except Exception as e:
                            err_msg = f"Failed Attendance ({month_out_name}): {str(e)}"
                            logger.error(err_msg, exc_info=True)
                            results["errors"]["attendance"].append(err_msg)
                            _notify(course_sec, f"Error Attendance {month_name}")

        if cancel_event and cancel_event.is_set():
            results["cancelled"] = True
            break

        if "grades" in enabled_engines:
            logger.info("  -> Generating Grading Sheet...")
            grade_dir = os.path.join(course_dir, "Grades")
            os.makedirs(grade_dir, exist_ok=True)

            grade_info = {
                "instructor": instructor,
                "course": course_sec,
                "sched": schedule_code,
                "subject": subject_name,
                "semester": semester_ay,
                "time": time_days_room,
                "has_lab": has_lab,
                "college": college
            }
            
            try:
                grade_gen = GradeGenerator(templates_dir)
                grade_out_name = f"{course_sec_safe}_{schedule_code_safe}_GRADING_SHEET.xlsx"
                grade_out_path = os.path.join(grade_dir, grade_out_name)
                grade_gen.generate(grade_info, students, grade_out_path)
                results["generated"]["grades"].append(grade_out_name)
                results["by_class"][course_sec]["grades"].append({"name": grade_out_name, "path": grade_out_path})
                _notify(course_sec, "Grading Sheet")
            except Exception as e:
                err_msg = f"Failed Grades ({course_sec}_{schedule_code}): {str(e)}"
                logger.error(err_msg, exc_info=True)
                results["errors"]["grades"].append(err_msg)
                _notify(course_sec, "Error Grades")

    return results
