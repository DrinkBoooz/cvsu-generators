from ceit_generator import GeneratorFactory, ClassInfo, load_students
import os
students = load_students(r"C:\Users\danjo\OneDrive\CVSU GENERATORS\List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.xlsx")
info = ClassInfo(
    instructor='DAN JOSEPH A. ORTEGA',
    course_section='BSCS 1-4',
    schedule_code='202612040',
    subject='DCIT 21 - INTRODUCTION TO COMPUTING',
    time_days_room='05:00PM-07:00PM / M / LEC: ITC 402',
    semester_ay='1st Semester / 2026-2027',
    students=students,
)
factory = GeneratorFactory(os.path.join(os.path.dirname(__file__), '../templates'))
gen = factory.get_all()[0][0]  # SyllabusGenerator
out_dir = os.path.join(os.path.dirname(__file__), '../output','BSCS_1-4_debug2')
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'BSCS_1-4_SYLLABUS_ACCEPTANCE.docx')
# Let exception propagate to see full traceback
gen.generate(info, out_path)
print('Generated', out_path)
