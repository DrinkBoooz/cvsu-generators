import pytest
import os
import zipfile
import shutil
import tempfile
import openpyxl
from unittest.mock import patch
import process_schedule
import ceit_generator
import attendancegen
import grade_generator

@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as td:
        yield td

# 1. OS-Level Path Constraints (MAX_PATH and sanitization)
def test_sanitize_filename_extreme():
    # Entirely illegal characters
    res = process_schedule.sanitize_filename('<>:"/\\|?*')
    # Shouldn't be empty string
    assert len(res) > 0

def test_atomic_write_max_path(temp_env):
    # Test atomic write doesn't crash on very long path
    # Windows MAX_PATH is 260. Let's make a 250 char path and append .tmp
    long_name = "A" * 240 + ".docx"
    long_path = os.path.join(temp_env, long_name)
    if os.name == 'nt' and not long_path.startswith("\\\\?\\"):
        long_path = "\\\\?\\" + os.path.abspath(long_path)
    
    from modules.services.template_recipe_service import TemplateRecipeResolver
    real_template = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "template_syllabus.docx")
    recipe = TemplateRecipeResolver.get_instance().resolve(real_template, "academic_docx")
    gen = ceit_generator.SyllabusGenerator(real_template, recipe)
    info = ceit_generator.ClassInfo("I", "C", "S", "Sub", "Sem", "T", [])
    gen.generate(info, long_path)
    assert os.path.exists(long_path)
    assert not os.path.exists(long_path + ".tmp")

# 2. Extreme Template Malformations
def test_empty_student_roster(temp_env):
    # Roster Excel is completely empty (0 students)
    roster_path = os.path.join(temp_env, "BSIT 1-1 list of students for 1234 - ITEC 50.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Student Number", "Student Name", "Course", "Gender"])
    # No students added
    wb.save(roster_path)
    
    # Generate schedule
    sched_path = os.path.join(temp_env, "sched.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["SEMESTER", "FIRST SEMESTER, AY 2026 - 2027"])
    ws.append(["NAME", "DAN"])
    ws.append(["TIME", "", "", "MONDAY", "", "", "", "", ""])
    ws.append(["07:00-10:00", "", "", "ITEC 50", "", "", "", "", ""])
    ws.append(["", "", "", "BSIT 1-1", "", "", "", "", ""])
    ws.append(["", "", "", "LEC", "", "", "", "", ""])
    ws.append(["", "", "", "Rm 1", "", "", "", "", ""])
    for _ in range(40):
        ws.append([""] * 10)
    wb.save(sched_path)
    
    # Process all - should not crash, should skip or create empty lists
    results = process_schedule.process_all(sched_path, [roster_path], temp_env)
    assert len(results["errors"]["ceit"]) == 0
    assert len(results["errors"]["attendance"]) == 0
    assert len(results["errors"]["grades"]) == 0
    assert len(results["generated"]["attendance"]) > 0

def test_corrupt_template(temp_env):
    # Template is 0-byte file
    fake_template = os.path.join(temp_env, "fake.docx")
    with open(fake_template, "wb") as f:
        pass
        
    from modules.services.template_recipe_service import TemplateRecipeResolver
    # Resolving recipe or generating from 0-byte file should raise an Exception gracefully
    with pytest.raises(Exception):
        recipe = TemplateRecipeResolver.get_instance().resolve(fake_template, "academic_docx")
        gen = ceit_generator.SyllabusGenerator(fake_template, recipe)
        info = ceit_generator.ClassInfo("I", "C", "S", "Sub", "Sem", "T", [])
        gen.generate(info, os.path.join(temp_env, "out.docx"))

# 3. Path & Encoding Anomalies
def test_encoding_anomalies(temp_env):
    # Roster with special characters
    roster_path = os.path.join(temp_env, "BSIT 1-1 list of students for 1234 - ITEC 50.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Student Number", "Student Name", "Course", "Gender"])
    ws.append(["123", "Niño, Peña", "BSIT", "Male"]) # 'ñ'
    ws.append(["124", "O’Connor, John", "BSIT", "Male"]) # special apostrophe
    wb.save(roster_path)
    
    parsed_schedules = process_schedule.parse_schedule(os.path.join(temp_env, "fake.xlsx")) # just need it to load_roster
    # We can directly test load_students
    try:
        students = ceit_generator.load_students(roster_path)
        assert students[0] == ("Niño, Peña", "123")
        assert students[1] == ("O’Connor, John", "124")
    except Exception as e:
        pytest.fail(f"Encoding failed: {e}")
