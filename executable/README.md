# 🎓 CvSU Document Generator (User Guide)

A desktop application for Cavite State University (CvSU) faculty members to automatically generate complete, submission-ready academic documents in a single click:

- 📅 **Attendance Sheets (.docx)**: Monthly attendance logs with exact calendar days matching your schedule.
- 📋 **CEIT Department Forms (.docx)**: Syllabus Acceptance, Exam Returns (Midterm/Finals), and Table of Specifications (TOS).
- 📊 **Official CvSU Grade Sheets (.xlsx)**: Pre-formatted grade sheets for **Lecture** and **Lecture & Lab** courses, preserving all formulas, student data, and signature metadata.

---

## 💻 System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Dependencies**: **None!** The application is completely standalone. You do **not** need Python installed.
- **Office Software**: Microsoft Office (Word & Excel) or any compatible office suite to view/edit the generated documents.

---

## 🚀 How to Run

1. Locate **`CvSU Gen (Beta).exe`**.
2. Double-click **`CvSU Gen (Beta).exe`** to open the program.

> **Note on Windows Defender / SmartScreen:**
> Because this is a custom institutional tool, Windows may display a blue prompt stating _"Windows protected your PC"_.
> Simply click **"More info"** and then select **"Run anyway"**.

---

## 📁 Required Input Files

Before generating, make sure you have the following files ready:

### 1. Instructor Master Schedule (`.xls` or `.xlsx`)

- Download your official schedule spreadsheet from the faculty portal.
- The generator automatically extracts your instructor name, semester, academic year, class times, days, and rooms.
- _Note:_ Any schedule blocks labeled as `Async` or `Asynch` are automatically filtered out so only in-person sessions receive attendance columns.

### 2. Student Roster Files (`.xlsx`, `.xls`, or `.csv`)

- Download class student rosters directly from [registrar.cvsu.edu.ph](https://registrar.cvsu.edu.ph/).
- **Crucial:** Keep the official file naming format:

  ```text
  {Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx
  ```

  **Example:**

  ```text
  BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.xlsx
  ```

  _(The program uses this exact format to pair each student list with the corresponding block in your schedule)._

---

## 📝 Step-by-Step Instructions

1. **Step 1: Select Instructor Schedule**Click **"Browse File"** under Section 1 and select your master schedule `.xls` or `.xlsx`.
2. **Step 2: Select Student Rosters**Click **"Browse Data"** under Section 2. You can select **multiple files at once** by holding `Ctrl` or `Shift` to load all your class rosters together.
3. **Step 3: Confirm Detected Classes & Subject Types**Once your schedule and rosters are loaded, a panel will appear showing all detected classes:
   - **Lecture and Lab**: Uses `GRADING_LECTURE_LAB_TEMPLATE.xlsx` (includes Lecture, Laboratory, Consolidated, and Grading Sheet tabs).
   - **Lecture only**: Uses `GRADING_LECTURE_TEMPLATE.xlsx` (includes Lecture and Grading Sheet tabs).
     _The system automatically detects labs from your schedule hours, but you can change this anytime using the dropdown menu._

4. **Step 4: (Optional) Set Semester Date Boundaries**
   - If you want attendance sheets to cover only specific dates of the semester, select a **Start Date** and **End Date**.
   - If left blank, the app will generate sheets for the standard semester calendar (August–December for 1st Semester; January–May for 2nd Semester).

5. **Step 5: Choose Target Output Folder**Click **"Browse Path"** and select any destination folder on your computer where the files should be saved.
6. **Step 6: Initialize Workflow**
   Click the green **"Initialize Workflow"** button. Processing typically takes only a few seconds!

---

## 📂 Output Folder Structure

All files will be cleanly arranged into subfolders by course and section:

```text
<Your Selected Output Folder>/
└── BSCS 1-4/
    ├── Attendance/
    │   ├── BSCS1-4_202612040_ATTENDANCE_SEPTEMBER.docx
    │   ├── BSCS1-4_202612040_ATTENDANCE_OCTOBER.docx
    │   └── ...
    ├── CEIT_Forms/
    │   ├── BSCS1-4_202612040_SYLLABUS.docx
    │   ├── BSCS1-4_202612040_EXAM_MIDTERM.docx
    │   ├── BSCS1-4_202612040_EXAM_FINALS.docx
    │   ├── BSCS1-4_202612040_TOS_MIDTERM.docx
    │   └── BSCS1-4_202612040_TOS_FINALS.docx
    └── Grades/
        └── BSCS1-4_202612040_GRADE_SHEET.xlsx
```

---

## ❓ Frequently Asked Questions (FAQ)

#### Q: The app says a student roster was "skipped". Why?

Make sure the roster file name matches the official registrar naming convention:
`{Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx`
If the file name was altered, rename it back to match this pattern.

#### Q: Can I keep my Excel files open while generating?

Yes! The generator uses safe atomic writing techniques, meaning files won't get corrupted even if reference rosters are currently open. However, make sure the destination files in the output directory are not locked for editing.

#### Q: Where are error logs stored if something fails?

If you encounter an unexpected error, a detailed log file is automatically saved at:

```text
%APPDATA%/CVSU_Generators/logs/generator.log
```

You can press `Win + R`, paste the path above, and press Enter to view the log file or send it for technical assistance.
