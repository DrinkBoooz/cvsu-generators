# CVSU Generators

This repository contains Python scripts for generating standardized CvSU academic documents from a single class dataset and a set of Word templates.

## Included files

- `ceit_generator.py` — generates the 7 CEIT/departmental document types from one student list and class metadata.
- `grade_generator.py` — generates official CvSU Grade Sheets (`.xlsx`) for Lecture and Lecture & Lab courses preserving formulas.
- `attendancegen.py` — monthly attendance sheet generator (`.docx`).
- `process_schedule.py` — unified orchestration script that parses master teacher schedules and rosters to generate all documents automatically.
- `executable/` — standalone desktop GUI application (`CvSU Gen (Beta)`) built with `pywebview` and `PyInstaller`.
- `templates/` — source Word (`.docx`) and Excel (`.xlsx`) templates used by the document generators.
- `output/` — generated document output folders.
- `tests/` — automated test suites for generators and parsers.

## CEIT document generator

The main generator is `ceit_generator.py`. It creates the following 7 documents from one class input:

- Course Syllabus Acceptance Form
- Exam Returns Form — Midterm
- Exam Returns Form — Finals
- TOS Acknowledgment — Midterm
- TOS Acknowledgment — Finals
- Grade Discussion Form — Midterm
- Grade Discussion Form — Finals

## Prerequisites

- Python 3.10+
- `lxml` installed in the active environment

Example install:

```bash
pip install lxml
```

## Quick start

Run the script interactively:

```bash
python ceit_generator.py
```

Then enter the required values when prompted, or choose a quick preset.

## Command-line usage

### Basic run

```bash
python ceit_generator.py --csv "C:\Users\YourName\Documents\students.xlsx"
```

### Pre-filled values

```bash
python ceit_generator.py \
  --csv "C:\Users\YourName\Documents\students.xlsx" \
  --instructor "DAN JOSEPH A. ORTEGA" \
  --course "BSCS 1-4" \
  --sched "202612040" \
  --subject "DCIT 21 - INTRODUCTION TO COMPUTING" \
  --time "05:00PM-07:00PM / M / LEC: ITC 402" \
  --semester "1st Semester / 2026-2027"
```

### Preset option

```bash
python ceit_generator.py --csv "students.xlsx" --preset dcit21
```

Available presets:

- `default`
- `dcit21`
- `custom`

## Interactive flow

When you run the script without all arguments, it will:

1. show a preset selector
2. prompt for class details
3. prompt for the student list file
4. confirm the template folder and output folder
5. ask for final confirmation before generating all 7 documents

## Output folder

Generated files are saved under:

```text
output/<CourseSection>/<CourseSection>_DOCUMENT_NAME.docx
```

Example:

```text
output/BSCS_1-4/BSCS_1-4_TOS_MIDTERM.docx
```

## Template behavior

The generator uses the Word templates in the `templates/` folder. It fills:

- the header metadata table
- the subject and schedule rows
- the student roster table

It is designed to keep the metadata table separate from the student list table so that the class information is not overwritten by roster data.

## Verification status

The generator has been verified to produce all five document types successfully in a fresh output folder using real student lists.

The final verification checked that the generated files contain the expected header values and that the metadata and student roster tables remain correctly separate.

## Notes

- The script reads Excel files by parsing the XML inside the workbook, which avoids some openpyxl compatibility issues.
- The script also accepts CSV student lists if the file is not Excel.
- **Roster File Columns:** Student lists from `registrar.cvsu.edu.ph` must contain **strictly two columns: `Name` and `Student number`**. Any extra columns (e.g. Email, Course, Remarks) will cause parser errors.
- If the template folder is missing, the script prompts for a valid path before generation continues.

## Run the Attendance Generator

```powershell
python .\attendancegen.py --csv "path\to\students.xlsx"
```

The script will prompt you for:

- course title and code
- class schedule
- semester and academic year
- room assignment
- instructor name
- month/year and class day
- student list file if you did not pass `--csv`

Generated output files are saved in the `attendance_output/` folder or the selected output folder.

## Run the CEIT Document Generator

```powershell
python .\ceit_generator.py --csv "path\to\students.xlsx"
```

The script will prompt you for the class details and then generate the documents into the `output/` folder.

## Optional Arguments

- Attendance generator

  ````powershell
  python .\attendancegen.py --csv "path\to\students.xlsx" --template "path\to\template.docx"
  ```powershell
  ````

- CEIT generator

  ````powershell
  python .\ceit_generator.py --csv "path\to\students.xlsx" --templates "templates" --output "output"
  ```powershell
  ````

## Example input sets

### Attendance Generator

- Lecture OR Lab only

```powershell
   Course Code and Title: DCIT25 - DATA STRUCTURES AND ALGORITHMS
   Class Schedule: 07:00AM-10:00AM / Mon
   Semester: 1st
   Room Assignment: LEC: ITC 404
   Name of Instructor: DAN JOSEPH ORTEGA
   Month: February
   Year: 2026
```

- Lecture and Lab on the same day

```powershell
   Course Code and Title: DCIT25 - DATA STRUCTURES AND ALGORITHMS
   Class Schedule: 07:00AM-09:00AM, 01:00PM-03:00PM / Thurs
   Semester: 2nd
   Room Assignment: LAB: CCL 204, LEC: ITC 404
   Name of Instructor: DAN JOSEPH ORTEGA
   Month: February
   Year: 2026
```

- Lecture and Lab on separate days

```powershell
   Course Code and Title: DCIT25 - DATA STRUCTURES AND ALGORITHMS
   Class Schedule: Thu: 07:00AM-09:00AM; Fri: 01:00PM-03:00PM
   Semester: 2nd
   Room Assignment: LAB: CCL 204, LEC: ITC 404
   Name of Instructor: DAN JOSEPH ORTEGA
   Month: February
   Year: 2026
```

- Lecture + 2 labs

```powershell
   Course Code and Title: DCIT25 - DATA STRUCTURES AND ALGORITHMS
   Class Schedule: Mon: 07:00AM-09:00AM; Wed: 01:00PM-03:00PM; Fri: 03:00PM-05:00PM
   Semester: 1st
   Room Assignment: LAB 1: CCL 204, LAB 2: CCL 205, LEC: ITC 404
   Name of Instructor: DAN JOSEPH ORTEGA
   Month: February
   Year: 2026
```

### CEIT Generator

- Lecture OR Lab only

```powershell
   Instructor Name: DAN JOSEPH A. ORTEGA
   Course / Year / Section: BSCS 1-4
   Schedule Code: 202612040
   Subject: DCIT 25 - DATA STRUCTURES AND ALGORITHMS
   Time / Days / Room: 07:00AM-10:00AM / M / LEC: ITC 404
   Semester / Academic Year: 1st Semester / 2026-2027
```

- Lecture and Lab on the same day

```powershell
   Instructor Name: DAN JOSEPH A. ORTEGA
   Course / Year / Section: BSCS 2-1
   Schedule Code: 202612041
   Subject: DCIT 25 - DATA STRUCTURES AND ALGORITHMS
   Time / Days / Room: 07:00AM-09:00AM, 01:00PM-03:00PM / Th / LAB: CCL 204, LEC: ITC 404
   Semester / Academic Year: 2nd Semester / 2026-2027
```

- Lecture and Lab on separate days

```powershell
   Instructor Name: DAN JOSEPH A. ORTEGA
   Course / Year / Section: BSCS 2-1
   Schedule Code: 202612042
   Subject: DCIT 25 - DATA STRUCTURES AND ALGORITHMS
   Time / Days / Room: Th: 07:00AM-09:00AM; F: 01:00PM-03:00PM / LAB: CCL 204, LEC: ITC 404
   Semester / Academic Year: 2nd Semester / 2026-2027
```

- Lecture + 2 labs

```powershell
   Instructor Name: DAN JOSEPH A. ORTEGA
   Course / Year / Section: BSCS 2-1
   Schedule Code: 202612043
   Subject: DCIT 25 - DATA STRUCTURES AND ALGORITHMS
   Time / Days / Room: M: 07:00AM-09:00AM; W: 01:00PM-03:00PM; F: 03:00PM-05:00PM / LAB 1: CCL 204, LAB 2: CCL 205, LEC: ITC 404
   Semester / Academic Year: 1st Semester / 2026-2027
```

# CvSU Unified Document Generator

This directory contains `process_schedule.py`, an automated orchestration script that perfectly bridges the gap between `attendancegen.py` and `ceit_generator.py` by seamlessly ingesting standard teacher schedules.

## Overview

Instead of manually typing class details via the CLI, the unified script automatically constructs the required metadata by pairing the official raw `.xls` schedule format alongside standardized student lists.

When executed, it natively parses your schedule, evaluates which student lists match your assigned sections, filters out any asynchronous constraints, and cleanly outputs 90+ targeted documents grouped by section directly inside this `dev` directory!

## Requirements

- Python 3.10+
- `lxml` (`pip install lxml`)
- `xlrd` (`pip install xlrd`)
- `openpyxl` (`pip install openpyxl`)
- `pywebview` (for desktop GUI app)

## How It Works

1. **Native Schedule Parsing (`ORTEGA_SCHEDULE.xls`)**
   - Uses `xlrd` / `openpyxl` to traverse the schedule blocks.
   - Extracts instructor name, college header (e.g. `"COLLEGE OF ..."`), semester, and academic year automatically.
   - Traces the exact Class, Room, Times, and Day placements by analyzing block offsets against recognized prefixes (`CVSU`, `DCIT`, `COSC`).
   - **Async Intelligent Filtering**: Completely filters out blocks mapped as "Async" or "Asynch" to ensure offline output documents accurately reflect only face-to-face slotted sessions.

2. **Student List Extraction**
   - Automatically crawls for `.xlsx` lists using the standard naming schema:
     `{Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx`
     _(Example: `BSCS1-4 List of Students for 202612040-DCIT 21A...xlsx`)_
   - **Header Requirement:** Roster files must strictly contain `Name` and `Student number` columns only.

3. **Categorized Document Output**
   - Using the extracted parameters, the script simultaneously triggers the generator factories.
   - Generated outputs are scoped and organized within nested categorical directories:
     ```
     output/
     └── BSCS 1-4/
         ├── Attendance/    (Monthly attendance sheets with scheduled days)
         ├── CEIT_Forms/    (Syllabus, Exams, TOS, and Grade Discussion forms)
         └── Grades/        (Official CvSU Lecture or Lecture & Lab Grade Sheet)
     ```

## Usage

Simply ensure your `.xls` schedule document lies inside your root folder alongside this file, and your student lists exist in the same folder, then run:

```bash
python process_schedule.py
```
