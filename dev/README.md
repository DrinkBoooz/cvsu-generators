# CvSU Unified Document Generator

This directory contains `process_schedule.py`, an automated orchestration script that perfectly bridges the gap between `attendancegen.py` and `ceit_generator.py` by seamlessly ingesting standard teacher schedules.

## Overview

Instead of manually typing class details via the CLI, the unified script automatically constructs the required metadata by pairing the official raw `.xls` schedule format alongside standardized student lists.

When executed, it natively parses your schedule, evaluates which student lists match your assigned sections, filters out any asynchronous constraints, and cleanly outputs 90+ targeted documents grouped by section directly inside this `dev` directory!

## Requirements

- Python 3.10+
- `xlrd` (`pip install xlrd`)
- `lxml` (`pip install lxml`)
- `openpyxl` (`pip install openpyxl`)

## How It Works

1. **Native Schedule Parsing (`ORTEGA_SCHEDULE.xls`)**
   - Uses `xlrd` / `openpyxl` to traverse the natively formatted Excel schedule blocks.
   - Extracts instructor name, college header, and the current academic semester automatically.
   - Traces the exact Class, Room, Times, and Day placements by analyzing block offsets against recognized prefixes (`CVSU`, `DCIT`, `COSC`).
   - **Async Intelligent Filtering**: Completely filters out blocks mapped as "Async" or "Asynch" to ensure offline output documents accurately reflect only face-to-face slotted sessions.

2. **Student List Extraction**
   - Automatically crawls the directory for `.xlsx` lists using the standard naming schema:
     `{Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx`
     _(Example: `BSCS1-4 List of Students for 202612040-DCIT 21A...xlsx`)_
   - **Column Requirement:** Roster files must contain **only** `Name` and `Student number` columns. Extra columns will cause parser errors.

3. **Categorized Document Output**
   - Using the extracted parameters, the script simultaneously triggers the generator factories.
   - Generated outputs are perfectly scoped and organized within nested categorical directories:
     ```
     dev/
      ├── BSCS 1-4/
      │     ├── Attendance/    (Monthly attendance lists with days)
      │     ├── CEIT_Forms/    (Syllabus, Exams, TOS, and Grade Discussion forms)
      │     └── Grades/        (Official Lecture or Lecture & Lab Grade Sheet)
      └── BSCS 1-6/
     ```

## Usage

Simply ensure your `.xls` schedule document lies inside `dev` alongside this file, and your student lists exist in the parent folder, then run:

```bash
python process_schedule.py
```
