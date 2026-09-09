import os
import csv
import tempfile
import pytest

from modules.common.excel_utils import safe_get_column_letter, safe_temp_copy
from modules.parsers.roster_parser import load_students_csv, inspect_roster
from modules.parsers.ceit_directory import parse_filename_hints

def test_safe_get_column_letter_beyond_52():
    assert safe_get_column_letter(1) == "A"
    assert safe_get_column_letter(26) == "Z"
    assert safe_get_column_letter(27) == "AA"
    assert safe_get_column_letter(52) == "AZ"
    assert safe_get_column_letter(53) == "BA"
    assert safe_get_column_letter(702) == "ZZ"
    assert safe_get_column_letter(703) == "AAA"

def test_safe_temp_copy_sandboxed_in_temp_dir():
    temp_dir = tempfile.gettempdir()
    # Create a dummy file in a mock source directory
    with tempfile.TemporaryDirectory() as src_dir:
        src_file = os.path.join(src_dir, "test_schedule.xlsx")
        with open(src_file, "wb") as fh:
            fh.write(b"mock schedule payload")

        tmp_copy = safe_temp_copy(src_file)
        try:
            assert os.path.exists(tmp_copy)
            assert os.path.dirname(os.path.abspath(tmp_copy)).startswith(os.path.abspath(temp_dir))
            # Verify source dir has no leftover tmp file
            files_in_src = os.listdir(src_dir)
            assert len(files_in_src) == 1
            assert files_in_src[0] == "test_schedule.xlsx"
        finally:
            if os.path.exists(tmp_copy):
                os.remove(tmp_copy)

def test_csv_sniffer_delimiters():
    delimiters = [",", "\t", ";", "|"]
    
    for delim in delimiters:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8") as fh:
            fh.write(f"Student No{delim}Student Name\n")
            fh.write(f"202210001{delim}Dela Cruz, Juan\n")
            fh.write(f"202210002{delim}Santos, Maria\n")
            temp_path = fh.name

        try:
            students = load_students_csv(temp_path)
            assert len(students) == 2
            assert students[0][1] == "202210001"
            assert "Dela Cruz" in students[0][0]
            assert students[1][1] == "202210002"
            assert "Santos" in students[1][0]
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

def test_parse_filename_hints_heuristic_cases():
    # 1. Standard pattern
    h1 = parse_filename_hints("BSCS 1-4 List of Students for 202522383 - ITEC 50.xlsx")
    assert h1["schedule_code"] == "202522383"
    assert "BSCS" in h1["course_sec"]
    assert "1-4" in h1["course_sec"]

    # 2. Incomplete filename
    h2 = parse_filename_hints("CS1-4 DCIT21.xlsx")
    assert "1-4" in h2["course_sec"]
    assert h2["subject_prefix"] == "DCIT"
    assert h2["subject_code"] == "DCIT 21"

    # 3. Department recognition
    h3 = parse_filename_hints("BSCPE 3-2 CPEN 65.csv")
    assert "BSCPE" in h3["course_sec"]
    assert h3["ceit_metadata"] is not None
    assert h3["ceit_metadata"]["dept_code"] == "DCEE"
