import sys, os
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#!/usr/bin/env python3
"""Verify generated DOCX files contain expected headers and student rows."""
import sys, os, zipfile
from lxml import etree
import argparse
import ceit_generator

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def w(t): return f"{{{W}}}{t}"


def inspect_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = etree.fromstring(xml)
    body = root.find(w('body'))
    paras = ["".join((t.text or "") for t in p.iter(w('t'))) for p in body.findall('.//'+w('p'))]
    tbls = body.findall('.//'+w('tbl'))
    return paras, tbls


def find_any(paras, sub):
    sub = sub.strip()
    for p in paras:
        if sub and sub in p:
            return True
    return False


def verify_folder(doc_folder, students, info):
    ok = True
    files = [f for f in os.listdir(doc_folder) if f.lower().endswith('.docx')]
    if not files:
        print('No .docx files found in', doc_folder)
        return False
    for f in files:
        path = os.path.join(doc_folder, f)
        print('\nInspecting', path)
        paras, tbls = inspect_docx(path)
        # check headers
        checks = [info.instructor, info.course_section, info.schedule_code, info.subject, info.semester_ay]
        for c in checks:
            if not find_any(paras, c):
                print(f"  ⚠  Header missing '{c}' in {f}")
                ok = False
        # check student rows in first table
        if not tbls:
            print('  ⚠  No tables found')
            ok = False
            continue
        rows = tbls[0].findall(w('tr'))
        n_students_in_table = max(0, len(rows) - 1)
        if n_students_in_table != len(students):
            print(f"  ⚠  Student count mismatch in {f}: table has {n_students_in_table}, expected {len(students)}")
            ok = False
        else:
            print(f"  ✔  Student count OK ({len(students)})")
        # check first student present
        if students:
            first_name, first_num = students[0]
            found_name = any(first_name in ''.join((t.text or '') for t in cell.iter(w('t'))) for cell in tbls[0].findall('.//'+w('tc')))
            found_num = any(first_num in ''.join((t.text or '') for t in cell.iter(w('t'))) for cell in tbls[0].findall('.//'+w('tc')))
            if not found_name:
                print(f"  ⚠  First student name '{first_name}' not found in table cells of {f}")
                ok = False
            if first_num and not found_num:
                print(f"  ⚠  First student number '{first_num}' not found in table cells of {f}")
                ok = False
    return ok


def main():
    parser = argparse.ArgumentParser(description='Verify generated DOCX outputs')
    parser.add_argument('--students', required=True, help='Students file (.xlsx or .csv)')
    parser.add_argument('--outdir', required=True, help='Output folder containing generated files (safe_section subfolder)')
    args = parser.parse_args()

    students = ceit_generator.load_students(args.students)
    print(f'Loaded {len(students)} students from {args.students}')

    # load info from a best-effort by reading one of the generated files' headers
    # Instead, ask user to supply minimal info via env or defaults — for now, reuse defaults from prior run
    info = ceit_generator.ClassInfo(
        instructor = ceit_generator.prompt('','') if False else 'DAN JOSEPH A. ORTEGA',
        course_section = 'BSCS 1-4',
        schedule_code = '202612040',
        subject = 'DCIT 21 - INTRODUCTION TO COMPUTING',
        time_days_room = '',
        semester_ay = '1st Semester / 2026-2027',
        students = students,
    )

    ok = verify_folder(args.outdir, students, info)
    if ok:
        print('\nAll checks passed.')
        sys.exit(0)
    else:
        print('\nSome checks failed.')
        sys.exit(2)

if __name__ == '__main__':
    main()
