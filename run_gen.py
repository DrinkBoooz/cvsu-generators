import process_schedule
import glob
import os
import shutil

output_dir = "test_output_gen5"
if os.path.exists(output_dir):
    shutil.rmtree(output_dir, ignore_errors=True)
os.makedirs(output_dir, exist_ok=True)

schedule_path = process_schedule.find_schedule_file(os.getcwd())
rosters = glob.glob('schedules/*List of Students*.xlsx')

print(f"Using schedule: {schedule_path}")
print(f"Found {len(rosters)} rosters")

# Added date_overrides to include January as in the test-1 templates
date_overrides = {
    'startYear': '2026',
    'startMonth': '8',
    'startDay': '10',
    'endMonth': '1',
    'endDay': '31'
}

type_overrides = {
    'CS1-4': 'lecture_lab',
    'CS1-6': 'lecture_lab',
    'CS3-1': 'lecture_lab',
    'CS4-1': 'lecture_lab',
    'CS4-2': 'lecture_lab',
    'CS4-3': 'lecture_lab',
    'CS4-4': 'lecture_lab',
    'CS4-5': 'lecture_lab'
}

process_schedule.process_all(schedule_path, rosters, output_dir, date_overrides=date_overrides, type_overrides=type_overrides)

import glob
generated = glob.glob(os.path.join(output_dir, "**", "*.*"), recursive=True)
files = [f for f in generated if os.path.isfile(f)]
print(f"Generated {len(files)} files.")
