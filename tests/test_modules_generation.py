import os
import pytest

from modules.generators.ceit_gen import GeneratorFactory
from modules.generators.grade_gen import GradeGenerator
from modules.generators.attendance_gen import (
    build_schedule_meetings,
    get_class_dates_for_weekdays,
    parse_weekday,
)

def test_generator_factory_loads_all_7():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(repo_root, "templates")
    assert os.path.isdir(templates_dir)

    factory = GeneratorFactory(templates_dir)
    all_gens = factory.get_all(include_custom=False)
    assert len(all_gens) == 7

    suffixes = [suffix for _, suffix in all_gens]
    expected_suffixes = [
        "SYLLABUS_ACCEPTANCE",
        "EXAM_RETURNS_MIDTERM",
        "EXAM_RETURNS_FINALS",
        "TOS_MIDTERM",
        "TOS_FINALS",
        "GRADE_DISCUSSION_MIDTERM",
        "GRADE_DISCUSSION_FINALS",
    ]
    assert suffixes == expected_suffixes

    # Instantiate each generator to verify template integrity
    for gen_factory, suffix in all_gens:
        generator = gen_factory()
        assert generator is not None
        assert os.path.exists(generator.template_path)

def test_grade_gen_normalization():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(repo_root, "templates")
    gg = GradeGenerator.for_class(templates_dir, {})

    sem, year = gg._parse_semester_and_year("2nd Semester / 2025-2026")
    assert sem == "2nd Semester"
    assert year == "2025-2026"

    sem1, year1 = gg._parse_semester_and_year("First Semester 2026-2027")
    assert sem1 == "1st Semester"
    assert year1 == "2026-2027"

    code, title = gg._parse_subject("DCIT 21 - INTRODUCTION TO COMPUTING")
    assert code == "DCIT 21"
    assert title == "INTRODUCTION TO COMPUTING"

    code_dash, title_dash = gg._parse_subject("ITEC50 – WEB SYSTEMS AND TECHNOLOGY")
    assert "ITEC" in code_dash
    assert "WEB SYSTEMS" in title_dash

def test_attendance_schedule_meetings_and_dates():
    meetings = build_schedule_meetings("10:00AM-12:00AM / Mon")
    assert len(meetings) == 1
    assert meetings[0][0] == 0 # Monday
    assert meetings[0][1] == "10:00AM-12:00AM"

    # Multi-day schedule
    multi = build_schedule_meetings("07:00AM-09:00AM, 01:00PM-03:00PM / Thurs, Fri")
    assert len(multi) == 4

    # Class dates calculation
    feb_dates = get_class_dates_for_weekdays([2], 2026, [0]) # Mondays of Feb 2026
    assert len(feb_dates) == 4
    days = [d.day for d in feb_dates]
    assert days == [2, 9, 16, 23]
