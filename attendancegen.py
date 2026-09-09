#!/usr/bin/env python3
"""
CvSU Class Attendance Sheet Generator Facade
Re-exports from modules.generators.attendance_gen for 100% backward compatibility.
"""

from modules.generators.attendance_gen import (
    TemplateError,
    EmptyDateError,
    MONTHS,
    get_class_dates,
    dates_to_weeks,
    month_label,
    parse_weekday,
    parse_months,
    extract_weekday_from_schedule,
    parse_schedule_days,
    parse_schedule_slots,
    parse_explicit_schedule_meetings,
    build_schedule_meetings,
    build_schedule_label,
    build_semester_label,
    get_class_dates_for_weekdays,
    _auto_scale_attendance_name,
    set_para_text,
    set_cell_width,
    set_gridspan,
    clone_student_row,
    build_attendance_sheet,
    get_default_template_path,
    generate_attendance_for_month,
    prompt,
    main,
)

# Re-export roster loaders for any legacy scripts importing from attendancegen
from modules.parsers.roster_parser import (
    load_students,
    load_students_excel,
    load_students_csv,
    _fix_encoding,
    _is_id_header,
    _is_name_header,
    _detect_roster_columns,
)

__all__ = [
    "TemplateError",
    "EmptyDateError",
    "MONTHS",
    "get_class_dates",
    "dates_to_weeks",
    "month_label",
    "parse_weekday",
    "parse_months",
    "extract_weekday_from_schedule",
    "parse_schedule_days",
    "parse_schedule_slots",
    "parse_explicit_schedule_meetings",
    "build_schedule_meetings",
    "build_schedule_label",
    "build_semester_label",
    "get_class_dates_for_weekdays",
    "_auto_scale_attendance_name",
    "set_para_text",
    "set_cell_width",
    "set_gridspan",
    "clone_student_row",
    "build_attendance_sheet",
    "get_default_template_path",
    "generate_attendance_for_month",
    "prompt",
    "main",
    "load_students",
    "load_students_excel",
    "load_students_csv",
    "_fix_encoding",
    "_is_id_header",
    "_is_name_header",
    "_detect_roster_columns",
]

if __name__ == "__main__":
    main()