import pytest
import os
import shutil
import tempfile
import zipfile
import threading
from unittest.mock import patch, MagicMock

import process_schedule
import ceit_generator
import attendancegen
import grade_generator

@pytest.fixture
def temp_env():
    # Setup temporary directories for testing
    with tempfile.TemporaryDirectory() as td:
        yield td

def test_sanitize_filename():
    assert process_schedule.sanitize_filename("ITEC 50 - WEB SYSTEMS: AND TECH") == "ITEC 50 - WEB SYSTEMS_ AND TECH"
    assert process_schedule.sanitize_filename("CON") == "CON" # Windows handles CON differently at lower levels, but we replace special chars.
    assert process_schedule.sanitize_filename("foo/bar\\baz?*\"<>|") == "foo_bar_baz______"

def test_ceit_generator_missing_table(temp_env):
    fake_template = os.path.join(temp_env, "fake_template.docx")
    with zipfile.ZipFile(fake_template, "w") as zf:
        zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p><w:r><w:t>Hello</w:t></w:r></w:p>
            </w:body>
        </w:document>""")

    class TestGenerator(ceit_generator.DocumentGenerator):
        def fill_header(self, body, info):
            pass
        def _fill_student_row(self, row, student, idx):
            pass

    gen = TestGenerator(fake_template)
    info = ceit_generator.ClassInfo("Instructor", "Course", "Sched", "Subject", "Semester", "Time", [])
    
    with pytest.raises(ceit_generator.TemplateError, match="Could not find the student list table in the template."):
        gen.generate(info, os.path.join(temp_env, "out.docx"))

def test_ceit_generator_syllabus_missing_table(temp_env):
    fake_template = os.path.join(temp_env, "fake_template.docx")
    with zipfile.ZipFile(fake_template, "w") as zf:
        zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p/></w:body>
        </w:document>""")

    gen = ceit_generator.SyllabusGenerator(fake_template)
    info = ceit_generator.ClassInfo("I", "C", "S", "Sub", "Sem", "T", [])
    
    with pytest.raises(ceit_generator.TemplateError, match="Could not find the student list table in the syllabus template."):
        gen.generate(info, os.path.join(temp_env, "out.docx"))

def test_ceit_generator_paragraph_bounds(temp_env):
    fake_template = os.path.join(temp_env, "fake_template.docx")
    with zipfile.ZipFile(fake_template, "w") as zf:
        zf.writestr("word/document.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p/></w:body>
        </w:document>""")

    gen = ceit_generator.ExamReturnsGenerator(fake_template, "Midterm")
    info = ceit_generator.ClassInfo("I", "C", "S", "Sub", "Sem", "T", [])
    
    with pytest.raises(ceit_generator.TemplateError, match="Exam Returns template missing required paragraphs"):
        gen.generate(info, os.path.join(temp_env, "out.docx"))

    gen = ceit_generator.TOSGenerator(fake_template, "Midterm")
    with pytest.raises(ceit_generator.TemplateError, match="TOS template missing required paragraphs"):
        gen.generate(info, os.path.join(temp_env, "out.docx"))

def test_process_all_catches_ceit_errors(temp_env):
    class FailingGenerator:
        def generate(self, info, out_path):
            raise Exception("simulated failure")
            
    with patch('process_schedule.GeneratorFactory.get_all', return_value=[(lambda: FailingGenerator(), "suffix")]):
        sched_path = os.path.join(temp_env, "sched.xlsx")
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        # Setup basic headers to ensure start_row gets parsed
        ws.append(["SEMESTER", "FIRST SEMESTER, AY 2026 - 2027"])
        ws.append(["NAME", "DAN"])
        ws.append(["TIME", "", "", "MONDAY", "", "", "", "", ""]) # Provide enough columns
        
        # Add the class in column 3 (index 3)
        ws.append(["07:00-10:00", "", "", "ITEC 50", "", "", "", "", ""])
        ws.append(["", "", "", "BSIT 1-1", "", "", "", "", ""])
        ws.append(["", "", "", "LEC", "", "", "", "", ""])
        ws.append(["", "", "", "Rm 1", "", "", "", "", ""])
        
        # Fill remaining rows up to 47 so index is not out of bounds
        for _ in range(40):
            ws.append([""] * 10)
            
        wb.save(sched_path)
        
        # Need to provide a rosters dict that matches regex: ^(.*?)\s*list of students for\s+(\d+)\s*-\s*(.+?)\.(xlsx|xls|csv)
        # raw_course="BSIT 1-1", schedule_code="1234", subject="ITEC 50"
        roster_path = os.path.join(temp_env, "BSIT 1-1 list of students for 1234 - ITEC 50.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Student Number", "Student Name", "Course", "Gender"])
        ws.append(["123", "SMITH, JOHN", "BSIT", "Male"])
        wb.save(roster_path)
        
        results = process_schedule.process_all(sched_path, [roster_path], temp_env)
        
        assert len(results["errors"]["ceit"]) > 0
        assert "simulated failure" in results["errors"]["ceit"][0]
