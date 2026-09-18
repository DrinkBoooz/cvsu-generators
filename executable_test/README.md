# 🎓 CvSU Document Generator (User Guide)

A desktop application for Cavite State University (CvSU) faculty members to automatically generate complete, submission-ready academic documents in a single click:

- 📅 **Attendance Sheets (.docx)**: Monthly attendance logs with exact calendar days matching your schedule.
- 📋 **CEIT Department Forms (.docx)**: 7 complete forms including Syllabus Acceptance, Exam Returns (Midterm/Finals), Table of Specifications (TOS - Midterm/Finals), and Grade Discussion Forms (Midterm/Finals).
- 📊 **Official CvSU Grade Sheets (.xlsx)**: Pre-formatted grade sheets for **Lecture** and **Lecture & Lab** courses, preserving all formulas, student data, dynamic college title, and signature metadata.

---

## 💻 System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python / Python Packages**: None required for the packaged executable. The Python runtime and application dependencies are embedded in `CvSU Gen.exe`.
- **Microsoft Edge WebView2 Runtime**: Required system prerequisite. WebView2 is included with Windows 11. Most Windows 10 systems have the Evergreen Runtime pre-installed (Windows 10 v1803+ with November 2022 update baseline), though certain LTSC, managed, or clean installations may lack it. If missing, WebView2 must be installed or reported by the system (the application does not bundle an automatic installer).
- **.NET Framework 4.7.2+ Baseline**: Supported Windows baseline for the Python.NET (`pythonnet`) WinForms desktop host and OLE drag-and-drop integration (`native/dnd.py`). While Python.NET supports older runtimes, 4.7.2+ is the repository's tested baseline.
- **Office Software**: Microsoft Office (Word & Excel) or any compatible office suite (only needed for opening/editing generated DOCX/XLSX files; the application generates files natively without requiring Office).

---

## 🚀 How to Run

1. Locate **`CvSU Gen.exe`**.
2. Double-click **`CvSU Gen.exe`** to open the program.

> **Note on Windows Defender / SmartScreen & Publisher Identity:**
> Because this is a custom institutional tool developed specifically for Cavite State University, Windows may display a prompt stating _"Windows protected your PC"_.
> - **Verified Author & Copyright**: You can right-click **`CvSU Gen.exe`** &rarr; **Properties** &rarr; **Details** or **Digital Signatures** tab to verify the official copyright, company, and developer signature (**Dan Joseph Ortega**).
> - **Standard Launch**: Simply click **"More info"** and then select **"Run anyway"**.
> - **Permanent Trust (Optional)**: Run **`install_trusted_publisher.bat`** once to add the verified institutional publisher certificate to your computer, permanently enabling clean launches without SmartScreen warnings.


---

## 📁 Required Input Files

Before generating, make sure you have the following files ready:

### 1. Instructor Master Schedule (`.xls` or `.xlsx`)

- Download your official schedule spreadsheet from the faculty portal.
- The generator automatically extracts your instructor name, college header, semester, academic year, class times, days, and rooms.
- _Note:_ Any schedule blocks labeled as `Async` or `Asynch` are automatically filtered out so only in-person sessions receive attendance columns.

### 2. Student Roster Files (`.xlsx`, `.xls`, or `.csv`)

- Download class student rosters directly from [registrar.cvsu.edu.ph](https://registrar.cvsu.edu.ph/).

> [!TIP]
> **Roster Column Guidelines:** Roster files require `Name` and `Student number` in Columns A & B. Extra portal columns (such as Email, Course, Year, Section, Status, or Remarks) are automatically cleaned and ignored by the generator.

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
    │   ├── BSCS1-4_202612040_ATTENDANCE_Mon_September.docx
    │   ├── BSCS1-4_202612040_ATTENDANCE_Mon_October.docx
    │   └── ...
    ├── CEIT_Forms/
    │   ├── BSCS1-4_202612040_SYLLABUS_ACCEPTANCE.docx
    │   ├── BSCS1-4_202612040_EXAM_RETURNS_MIDTERM.docx
    │   ├── BSCS1-4_202612040_EXAM_RETURNS_FINALS.docx
    │   ├── BSCS1-4_202612040_TOS_MIDTERM.docx
    │   ├── BSCS1-4_202612040_TOS_FINALS.docx
    │   ├── BSCS1-4_202612040_GRADE_DISCUSSION_MIDTERM.docx
    │   └── BSCS1-4_202612040_GRADE_DISCUSSION_FINALS.docx
    └── Grades/
        └── BSCS1-4_202612040_GRADING_SHEET.xlsx
```

---

## ❓ Frequently Asked Questions (FAQ)

#### Q: The app says a student roster was "skipped" or failed with an error. Why?

1. **File Naming:** Make sure the roster file name matches the official registrar naming convention:
   `{Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx`
2. **Column Headers:** Verify that your file contains **only** two columns: `Name` and `Student number`. If any additional columns are present (such as Email, Course, Remarks, etc.), the parser will encounter an error. Delete any extra columns and save the file.

#### Q: Can I keep my Excel files open while generating?

Yes! The generator uses safe atomic writing techniques, meaning files won't get corrupted even if reference rosters are currently open. However, make sure the destination files in the output directory are not locked for editing.

#### Q: Where are error logs stored if something fails?

If you encounter an unexpected error, a detailed log file is automatically saved at:

```text
%APPDATA%/CVSU_Generators/logs/generator.log
```

You can press `Win + R`, paste the path above, and press Enter to view the log file.

Please send the error logs, screenshots, and description of issue to **danjoseph.ortega@cvsu.edu.ph** with the subject formatting:

```text
[CvSU Gen (Beta) - <Issue>]
```

_(e.g., `[CvSU Gen (Beta) - Schedule Parsing Error]`)_

---

## 🏷️ Version History
 
- **Release v1.1.0**:
  - **Apple HIG Preferences Redesign**: Transformed Faculty Defaults into an Apple Human Interface Guidelines Inset Grouped List (`.apple-hig-group`) featuring themed squircle icon tiles (👤 Instructor, 🏛️ College, 🗓️ Term), semibold primary labels with descriptive subtitles, and right-aligned controls with smooth focus rings.
  - **Document Header Live Preview**: Integrated an interactive macOS Quick Look-style header simulation card with a glowing `• LIVE SYNC` badge that reflects typography, university branding, and metadata changes in real-time as the user types.
  - **Uniform Modal Geometry & Elastic Components**: Stabilized Curriculum & Parser Settings across all 6 sections at `width: min(920px, calc(100vw - 32px))` and `height: min(680px, 88vh)`, eliminating tab switching height jitter. Data table wrappers (`#cfgPanePrefixes`, `#cfgPaneDegrees`) and keyword token clouds stretch elastically to fill the dialog body down to the action footer.
  - **Dynamic Step 4 Dates Stepper Chip**: Converted Step 4 from static ready state to dynamic evaluation based on `startDate` and `endDate` boundaries, displaying a neutral `•` indicator until dates are configured or semester presets applied.
  - **Multi-Breakpoint Responsive Adaptation**: Added fluid 3x2 tablet and 2x3 mobile tab grids, stacked 2-row dialog footers, and compact viewport support (`<= 640px height`).
- **Release v1.0.1**:
  - **WCAG 2.1 AA Accessibility Hardening Pass**: Implemented comprehensive WCAG 2.1 AA accessibility hardening across the desktop application, including full keyboard navigation, focus management, ARIA semantics, live announcements, and Windows forced-colors support.
  - **Focus Trapping & Focus Restoration**: Implemented stack-aware modal and slide-over drawer focus traps (`FocusTrapManager`) ensuring Tab stays bounded within open dialogs and restores focus to the triggering element upon dismissal.
  - **Windows High-Contrast / Forced-Colors Mode**: Dedicated `@media (forced-colors: active)` styling enforcing high-contrast `Highlight` focus indicators, `ButtonBorder` boundaries, and dashed `CanvasText` dropzone borders.
  - **Accessible Table & Progress Semantics**: Upgraded data preview grids and directories with explicit `scope="col"` and `scope="row"` headers, non-color status tags, and progress bar live updates.
  - **ARIA Live Regions & Screen Reader Support**: Added polite live region announcers for toast notifications, step readiness changes, and document compilation milestones.
- **Release v1.0.0**:
  - **Modularized UI & Script Architecture**: Completely decoupled monolith UI into cleanly structured CSS modules (`css/tokens.css`, `components.css`, `drawers.css`, etc.) and JavaScript controllers (`js/state.js`, `step1.js`, `settings.js`, etc.) with zero performance regression.
  - **Native Drag-and-Drop & Resilient File Bridge**: Integrated native OLE Win32 drag-and-drop alongside pywebview HTML5 dropzones with memory caching for drag operations.
  - **Official Production Release**: Transitioned from Beta to production Release v1.0.0 (`CvSU Gen.exe`).
- **v1.8 Beta**:
  - **Apple HIG Spatial Rhythm & Responsive Layout Refinement**: Eliminated layout compression and horizontal overflow dead-zones across small screens and Windows Snap Assist views with fluid `minmax(0, 1fr)` columns and a standardized 8pt spacing grid.
  - **Illuminated Stepper Connectors & Active Indicators**: Introduced dynamic gradient-illuminated stepper progress lines connecting workflow steps, real-time scroll-spy step tracking, and macOS-style segmented indicator lines on the slide drawer navigation tabs.
  - **Adaptive Bottom Sheet**: Re-engineered floating bottom action bar into an anchored bottom sheet on viewports `< 768px` to prevent pill wrapping distortions.
  - **Robustness & Interaction Polish**: Hardened roster matching attributes against quotes and special characters, added global Escape key dismissal for drawers and modals, confirmation safeguard for roster clearing, and resilient local storage handlers.
- **v1.7 Beta**:
  - **Apple HIG UI Cleanup & Spacious Redesign**: Eliminated visual density and cramped layout by adopting macOS Human Interface Guidelines—progressive disclosure accordions (`<details class="step-disclosure">`) for technical formatting rules, spacious layout rhythm, and SF Pro system typography.
  - **Apple-Style Segmented Controls & Feature Tiles**: Re-architected package toggles into modern tactile feature tiles with glowing active borders, replaced legacy chip filters with frictionless Apple-style sliding capsule segmented controls (`.segmented-control`), and refined the floating bottom dock into a sleek floating macOS capsule island.
  - **Optimized Window Canvas (1120x780)**: Expanded default desktop window dimensions from `920x720` to `1120x780` (min `880x640`), providing immediate breathing room, eliminating vertical compression, and preventing premature column collapse.
- **v1.6 Beta**:
  - **Zero-Lag Theme Engine & View Transitions**: Eliminated light-to-dark mode transition stutter and frame drops using the modern View Transitions API (`document.startViewTransition`) for silky smooth, GPU-composited cross-fades.
  - **Transition Storm Elimination**: Resolved runaway cascade of 720+ concurrent CSS transition events across scrollbars, borders, text colors, and backgrounds during theme toggles by introducing synchronous `.theme-transitioning` transition suppression.
  - **Backdrop-Filter Compositor Optimization**: Prevented GPU shader thrashing across frosted glass containers (`.top-nav-bar`, `.bottom-action-bar`, `.glass-card`), replacing wildcard `transition: all` rules across ~35 UI components with targeted GPU-friendly property transitions (`transform`, `box-shadow`, `border-color`).
- **v1.5 Beta**:
  - **Modularized Architecture (`modules/`)**: Re-architected the entire Python backend into a cleanly structured single package (`modules/common`, `modules/models`, `modules/parsers`, `modules/generators`, `modules/services`) with backward-compatible facades at the root.
  - **Output Parity & Roster Preservation**: Eliminated false header rejection ensuring students with surnames matching header keywords (e.g. `NAME, ZULEIKAH MARIJ C.`) are preserved, and normalized university portal enye encoding glitches (e.g. `SAÃEZ` $\rightarrow$ `SAÑEZ`).
  - **Dynamic Student Name Font Scaling**: Standardized student name font scaling ladder across all CEIT forms and Attendance sheets ($\le 25 \rightarrow 9\text{pt}$, $26\text{--}30 \rightarrow 8\text{pt}$, $31\text{--}35 \rightarrow 7\text{pt}$, $> 35 \rightarrow 6\text{pt}$).
  - **Template Hygiene & Lab Auto-Detection**: Restored clean 6-row Table 0 layout in Grade Discussion forms, curriculum-aware lab auto-detection for hybrid subjects (`DCIT 21`), and canonical schedule code reconciliation (`COSC 111A` $\rightarrow$ `COSC 111`).
  - **Enhanced Parsing & Resilience**: Robust OpenPyXL column letter calculation beyond 52/702 columns (`AA`..`ZZ`), automated CSV delimiter detection (`csv.Sniffer`), sandboxed temporary file handling in OS temp directory to eliminate file lock collisions, and unified CEIT directory heuristic extraction.
  - **Full PyInstaller Bundle**: Standalone binary compilation with comprehensive submodules packaging.
- **v1.4 Beta**:
  - **Modern Studio Split-Grid Dashboard**: Re-architected the main workspace into a responsive two-column dashboard layout (Data Ingestion on the left, Configuration & Document Packages Control Deck on the right) providing zero-scroll efficiency on standard 1080p+ viewports.
  - **Floating Bottom Action Deck**: Pinned frosted glassmorphism dock featuring real-time system readiness checklist pills (`Schedule`, `Rosters`, `Output`) and an immediate **Initialize Workflow** primary CTA accessible from anywhere on screen.
  - **Visual Polish & Glassmorphism Depth**: Enhanced frosted glass backdrop filters (`backdrop-filter: blur(24px)`), gradient borders, glowing micro-interactions, responsive dropzone hover states, and streamlined layout density.
- **v1.3 Beta**:
  - **Smart Roster Parsing & Interactive Column Mapping**: Unified roster parsing engine with raw row inspection, custom header row selection, configurable Student Name and Student Number columns, and live parsed preview modal.
  - **Offline Local Persistence**: Automatically saves custom column mappings and class linkages in browser `localStorage` (`cvsu_roster_mappings`, `cvsu_parsing_rules`) across sessions.
  - **Complete CEIT Department & Subject Directory**: Integrated all 15 official CEIT prefixes (`AGEN`, `ABEN`, `ARCH`, `CENG`, `CIVL`, `COSC`, `CPEN`, `DCEE`, `DCIT`, `ECEN`, `EENG`, `IENG`, `INDT`, `SMT`, `ITEC`) with department badges and dedicated Help Drawer directory.
  - **Manual Timetable Linking**: Non-standard roster filenames can be linked directly to timetable classes using an inline dropdown or the mapping modal.
  - **Theme System Overhaul**: Declared native `color-scheme` support for both Dark and Light themes, high-contrast calendar picker indicators, glassmorphism scrollbars, and dynamic Sun/Moon toggle.
- **v1.2 Beta**:
  - Initial beta release with Stepper readiness tracker, toast notification engine, responsive help drawer, and graceful execution cancellation.
