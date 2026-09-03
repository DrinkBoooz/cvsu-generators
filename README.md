# CvSU Gen (Beta)

Standardized academic document generation suite for Cavite State University (CvSU) faculty members. The system automatically reads an instructor's official master schedule and student rosters to produce attendance sheets, department forms, and official grade sheets with zero manual data entry.

Available as both a **standalone modern desktop application** (GUI) and a **Python CLI / batch pipeline**.

---

## 📑 Generated Document Types

The suite concurrently drives three specialized generation engines:

1. **Monthly Attendance Sheets (`.docx`)**
   - Generates individual attendance documents for each active month in the semester (e.g., August to December, or January to May).
   - Matches official university layout and automatically populates class dates corresponding to your specific weekly lecture/lab days (e.g., Mondays, Thursdays/Fridays).
   - Filters dates strictly within user-specified semester start and end dates.

2. **CEIT Department Forms (`.docx`)**
   - **Course Syllabus Acceptance Form** — with full student roster table, schedule information, and course details.
   - **Midterm Examination Returns Form** — complete student acknowledgement checklist.
   - **Final Examination Returns Form** — complete student acknowledgement checklist.
   - **Table of Specifications (TOS) Acknowledgment — Midterm**
   - **Table of Specifications (TOS) Acknowledgment — Finals**

3. **Official CvSU Grading Sheets (`.xlsx`)**
   - Generates native Excel workbooks based on official university grading templates:
     - **Lecture and Lab Template (`GRADING_LECTURE_LAB_TEMPLATE.xlsx`)**: Populates `Lecture`, `Laboratory`, `Consolidated`, and `Grading Sheet` sheets.
     - **Lecture Only Template (`GRADING_LECTURE_TEMPLATE.xlsx`)**: Populates `Lecture` and `Grading Sheet` sheets.
   - Automatically writes Course & Section, Subject Code & Title, Schedule Code, Units, Semester, Academic Year, and Instructor Signature (`BI60`/`BI57`).
   - Fills Student Names and Student Numbers while strictly preserving internal Excel grading formulas.
   - Includes automatic formula injection sanitization.

---

## 🖥️ Desktop Application (Recommended)

The easiest way to generate documents is using the standalone desktop GUI application.

### Running the Standalone Application
1. Navigate to `executable/dist/CvSU Gen (Beta).exe`.
2. Double-click **`CvSU Gen (Beta).exe`** (no Python installation required).

### Step-by-Step User Instructions
1. **Step 1: Instructor Schedule (Excel)**
   - Click **Browse File** and select your master schedule file (`.xls` or `.xlsx`).
   - *Requirement:* Exported from the university faculty portal.
   - *Note:* Any schedule blocks marked as `"Async"` or `"Asynch"` are automatically filtered out to ensure offline documents only target face-to-face sessions.
2. **Step 2: Student Rosters (XLSX)**
   - Click **Browse Data** and select one or more student roster files. You can select multiple files at once.
   - *Requirement:* Exported directly from [registrar.cvsu.edu.ph](https://registrar.cvsu.edu.ph/).
   - *Naming Format:* Must strictly follow:
     ```text
     {Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx
     ```
     *Example:* `BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.xlsx`
3. **Step 3: Review Detected Classes & Subject Types**
   - Once both Schedule and Rosters are loaded, the **Detected Classes & Subject Types** section automatically appears.
   - For each class found, the system intelligently auto-detects whether the course is **Lecture and Lab** (if schedule has lab rooms/hours) or **Lecture only**.
   - Use the dropdown on each class to manually override the type if necessary.
4. **Step 4: Semester Date Boundaries (Optional)**
   - **Start Date:** The official starting date of classes for the semester.
   - **End Date:** The official ending date of classes.
   - *Behavior:* When both dates are provided, attendance sheets will only generate attendance check columns for calendar days falling strictly between Start and End. If left blank, standard monthly calendars derived from the semester are used.
5. **Step 5: Target Output Environment**
   - Click **Browse Path** and select the destination folder where generated documents should be saved.
6. **Step 6: Initialize Workflow**
   - Click **Initialize Workflow**. The process runs asynchronously in the background. A confirmation alert will report total generated files, skipped classes, or errors upon completion.

---

## 📁 Output Directory Organization

All outputs are automatically sorted and grouped into clean subdirectories by course and section:

```text
<Output Directory>/
└── BSCS 1-4/
    ├── Attendance/
    │   ├── BSCS 1-4_202612040_ATTENDANCE_AUGUST.docx
    │   ├── BSCS 1-4_202612040_ATTENDANCE_SEPTEMBER.docx
    │   ├── BSCS 1-4_202612040_ATTENDANCE_OCTOBER.docx
    │   ├── BSCS 1-4_202612040_ATTENDANCE_NOVEMBER.docx
    │   └── BSCS 1-4_202612040_ATTENDANCE_DECEMBER.docx
    ├── CEIT_Forms/
    │   ├── BSCS 1-4_202612040_SYLLABUS.docx
    │   ├── BSCS 1-4_202612040_EXAM_MIDTERM.docx
    │   ├── BSCS 1-4_202612040_EXAM_FINALS.docx
    │   ├── BSCS 1-4_202612040_TOS_MIDTERM.docx
    │   └── BSCS 1-4_202612040_TOS_FINALS.docx
    └── Grades/
        └── BSCS 1-4_202612040_GRADE_SHEET.xlsx
```

---

## ⚙️ Developer Setup & CLI Usage

If you prefer to run or modify the Python source code directly:

### 1. Prerequisites
- **Python 3.10+** (64-bit recommended)
- Git

### 2. Environment Installation
```bash
# Clone the repository
git clone https://github.com/DrinkBoooz/cvsu-generators.git
cd cvsu-generators

# Create and activate virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux / macOS:
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
pip install pywebview
```

### 3. Run Automated Tests
```bash
python -m unittest discover -s tests -v
```
*(All 16 unit test suites should pass cleanly)*

### 4. Running the Unified Batch Pipeline via Python
Place your `.xls` master schedule and student roster files in the project folder, then run:

```bash
python process_schedule.py
```

### 5. Running the Desktop UI via Python
```bash
python executable/main.py
```

### 6. Compiling the Standalone Executable
To package the app into a single, self-contained Windows executable with icons and embedded templates:

```cmd
cd executable
.\build.bat
```
The output binary will be generated at `executable/dist/CvSU Gen (Beta).exe`.

---

## 🔒 Security & Reliability Features

- **XSS Sanitization:** The desktop user interface strictly sanitizes all student, subject, and section strings before rendering to prevent HTML injection.
- **XXE Hardened:** XML template parsers (`lxml.etree`) strictly disable entity resolution (`resolve_entities=False`) to prevent external entity vulnerabilities.
- **Excel Formula Injection Guard:** Any student name starting with formula triggers (`=`, `+`, `-`, `@`) is automatically escaped with an apostrophe prefix (`'`).
- **File Lock Resilience:** All writes utilize randomized temporary files (`uuid.uuid4()`) and atomic replacements (`os.replace`). If an existing output or roster file is open in Microsoft Excel, the system gracefully handles the lock without corrupting files.
- **Diagnostics Logging:** System logs are persistently written with automatic rotation to:
  ```text
  %APPDATA%/CVSU_Generators/logs/generator.log
  ```
