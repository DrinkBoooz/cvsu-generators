import pytest

def test_modules_common_imports():
    from modules.common.logger import logger, IsolatedLogger
    from modules.common.excel_utils import (
        safe_get_column_letter,
        safe_temp_copy,
        parse_excel_time,
        get_long_path,
        sanitize_filename,
    )
    from modules.common.docx_utils import (
        w, wt, get_full_text, auto_scale_font, set_run_text,
        replace_after_colon, replace_value_run, collapse_runs_after_colon,
        set_cell_text, load_docx, save_docx,
    )
    assert callable(safe_get_column_letter)
    assert callable(safe_temp_copy)
    assert callable(parse_excel_time)
    assert callable(get_long_path)
    assert callable(sanitize_filename)
    assert callable(w)
    assert callable(set_cell_text)
    assert hasattr(logger, "info")

def test_modules_models_imports():
    from modules.models.student import Student
    from modules.models.schedule import ScheduleMeeting, ScheduleBlock, ClassInfo
    from modules.models.config import RosterConfig

    s = Student(name="Dela Cruz, Juan", student_number="202210001", row_idx=5)
    assert s.to_dict()["name"] == "Dela Cruz, Juan"
    assert s.to_tuple() == ("Dela Cruz, Juan", "202210001")

    ci = ClassInfo(
        instructor="DAN JOSEPH A. ORTEGA",
        course_section="BSCS 1-4",
        schedule_code="202522383",
        subject="ITEC50 – WEB SYSTEMS AND TECHNOLOGY",
        time_days_room="10:00AM-12:00AM / M / LAB: CCL 305",
        semester_ay="2nd Semester / 2025-2026",
        students=[("Juan Dela Cruz", "202210001")]
    )
    assert ci.instructor == "DAN JOSEPH A. ORTEGA"
    assert len(ci.students) == 1

def test_modules_parsers_imports():
    from modules.parsers.ceit_directory import (
        CEIT_PREFIX_MAP,
        BASE_SUBJECT_PREFIXES,
        SUBJECT_PREFIXES,
        get_prefix_metadata,
        parse_filename_hints,
    )
    from modules.parsers.roster_parser import (
        load_students,
        inspect_roster,
        sanitize_name,
        sanitize_stnum,
    )
    from modules.parsers.schedule_parser import (
        parse_schedule,
        find_blocks_for_section,
        get_subject_code,
    )
    assert "DCIT" in CEIT_PREFIX_MAP
    assert "COSC" in SUBJECT_PREFIXES
    assert callable(parse_filename_hints)
    assert callable(load_students)
    assert callable(parse_schedule)

def test_modules_generators_imports():
    from modules.generators.grade_gen import GradeGenerator
    from modules.generators.attendance_gen import (
        build_attendance_sheet,
        generate_attendance_for_month,
    )
    from modules.generators.ceit_gen import (
        DocumentGenerator,
        SyllabusGenerator,
        ExamReturnsGenerator,
        TOSGenerator,
        GradeDiscussionGenerator,
        GeneratorFactory,
    )
    assert callable(build_attendance_sheet)
    assert callable(generate_attendance_for_month)
    assert issubclass(SyllabusGenerator, DocumentGenerator)
    assert issubclass(ExamReturnsGenerator, DocumentGenerator)
    assert issubclass(TOSGenerator, DocumentGenerator)
    assert issubclass(GradeDiscussionGenerator, DocumentGenerator)

def test_modules_services_imports():
    from modules.services.validator import validate_rosters, detect_classes
    from modules.services.orchestrator import process_all
    assert callable(validate_rosters)
    assert callable(detect_classes)
    assert callable(process_all)

def test_root_facades_backward_compatibility():
    import roster_parser
    import process_schedule
    import attendancegen
    import ceit_generator
    import grade_generator

    assert hasattr(roster_parser, "load_students")
    assert hasattr(roster_parser, "inspect_roster")
    assert hasattr(roster_parser, "get_prefix_metadata")
    assert hasattr(roster_parser, "parse_filename_hints")
    assert hasattr(roster_parser, "CEIT_PREFIX_MAP")

    assert hasattr(process_schedule, "process_all")
    assert hasattr(process_schedule, "parse_schedule")
    assert hasattr(process_schedule, "validate_rosters")
    assert hasattr(process_schedule, "detect_classes")
    assert hasattr(process_schedule, "logger")

    assert hasattr(attendancegen, "build_attendance_sheet")
    assert hasattr(attendancegen, "generate_attendance_for_month")
    assert hasattr(attendancegen, "get_class_dates")

    assert hasattr(ceit_generator, "ClassInfo")
    assert hasattr(ceit_generator, "GeneratorFactory")
    assert hasattr(ceit_generator, "SyllabusGenerator")

    assert hasattr(grade_generator, "GradeGenerator")
