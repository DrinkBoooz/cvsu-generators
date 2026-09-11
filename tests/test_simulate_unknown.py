#!/usr/bin/env python3
"""Simulate: What happens when a roster filename has no course/section prefix?

Tests and demonstrates roster filename parsing behavior, showing why filenames
lacking the {Course/Sec} prefix produce 'Unknown' output folders and filenames.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.common.excel_utils import sanitize_filename

# The regex the orchestrator uses to parse roster filenames
PATTERN = re.compile(r'^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)', re.IGNORECASE)

test_filenames = [
    # Standard format (works)
    "BSCS2-3 List of Students for 202612681-COSC 60A - DIGITAL LOGIC DESIGN.xlsx",
    # Missing course/section prefix entirely
    "List of Students for 202612681-COSC 60A - DIGITAL LOGIC DESIGN.xlsx",
    # Only spaces before
    "  List of Students for 202612681-COSC 60A - DIGITAL LOGIC DESIGN.xlsx",
    # Just the schedule code in name
    "202612681-COSC 60.xlsx",
    # Non-standard but has partial info
    "COSC 60 List of Students for 202612681-COSC 60A.xlsx",
]

def parse_roster_filename_sim(fn: str):
    m = PATTERN.match(fn)
    if not m:
        return None
    raw_course = m.group(1).strip()
    schedule_code = m.group(2)
    subject_name = m.group(3)

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

    course_sec_safe = sanitize_filename(course_sec)
    sched_safe = sanitize_filename(schedule_code)
    output_name = f"{course_sec_safe}_{sched_safe}_GRADE_DISCUSSION_FINALS.docx"

    return {
        "raw_course": raw_course,
        "letters": letters,
        "digits": digits,
        "course_sec": course_sec,
        "course_sec_safe": course_sec_safe,
        "schedule_code": schedule_code,
        "subject_name": subject_name,
        "output_name": output_name,
    }

def test_standard_filename_parses_section():
    res = parse_roster_filename_sim("BSCS2-3 List of Students for 202612681-COSC 60A - DIGITAL LOGIC DESIGN.xlsx")
    assert res is not None
    assert res["course_sec"] == "CS2-3"
    assert res["course_sec_safe"] == "CS2-3"
    assert res["output_name"] == "CS2-3_202612681_GRADE_DISCUSSION_FINALS.docx"

def test_missing_course_sec_produces_unknown():
    res = parse_roster_filename_sim("List of Students for 202612681-COSC 60A - DIGITAL LOGIC DESIGN.xlsx")
    assert res is not None
    assert res["raw_course"] == ""
    assert res["course_sec"] == ""
    assert res["course_sec_safe"] == "Unknown"
    assert res["output_name"] == "Unknown_202612681_GRADE_DISCUSSION_FINALS.docx"

def test_whitespace_only_prefix_produces_unknown():
    res = parse_roster_filename_sim("  List of Students for 202612681-COSC 60A - DIGITAL LOGIC DESIGN.xlsx")
    assert res is not None
    assert res["raw_course"] == ""
    assert res["course_sec"] == ""
    assert res["course_sec_safe"] == "Unknown"
    assert res["output_name"] == "Unknown_202612681_GRADE_DISCUSSION_FINALS.docx"

def test_bare_schedule_code_does_not_match():
    res = parse_roster_filename_sim("202612681-COSC 60.xlsx")
    assert res is None

def test_subject_as_prefix_normalizes():
    res = parse_roster_filename_sim("COSC 60 List of Students for 202612681-COSC 60A.xlsx")
    assert res is not None
    assert res["course_sec_safe"] == "COSC6-0"
    assert res["output_name"] == "COSC6-0_202612681_GRADE_DISCUSSION_FINALS.docx"

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 90)
    print("ROSTER FILENAME PARSING SIMULATION")
    print("=" * 90)

    for fn in test_filenames:
        info = parse_roster_filename_sim(fn)
        if info:
            print(f"\n  Filename:      {fn}")
            print(f"  raw_course:    '{info['raw_course']}'")
            print(f"  letters:       '{info['letters']}'")
            print(f"  digits:        '{info['digits']}'")
            print(f"  course_sec:    '{info['course_sec']}'")
            print(f"  sanitized:     '{info['course_sec_safe']}'")
            print(f"  OUTPUT NAME:   {info['output_name']}")
            if info['course_sec_safe'] == "Unknown":
                print(f"  >>> THIS PRODUCES 'Unknown' <<<")
        else:
            print(f"\n  Filename:      {fn}")
            print(f"  REGEX:         NO MATCH (file would be skipped)")

    print("\n" + "=" * 90)
