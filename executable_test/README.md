# 🎓 CvSU Document Generator (User Guide & Build Architecture)

A desktop application for Cavite State University (CvSU) faculty members to automatically generate complete, submission-ready academic documents in a single click:

- 📅 **Attendance Sheets (.docx)**: Monthly attendance logs with exact calendar days matching your schedule, featuring an offline 3-layer dynamic calendar engine with multi-year recurrence rules, memo announcement parsing, and `#WalangPasok` weather suspension handling.
- 📋 **CEIT Department Forms (.docx)**: 7 complete forms including Syllabus Acceptance, Exam Returns (Midterm/Finals), Table of Specifications (TOS - Midterm/Finals), and Grade Discussion Forms (Midterm/Finals).
- 📊 **Official CvSU Grade Sheets (.xlsx)**: Pre-formatted grade sheets for **Lecture** and **Lecture & Lab** courses, preserving all formulas, student data, dynamic college title, and signature metadata.

---

## 💻 System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python / Python Packages**: None required on target machines. The application is packaged into a clean standalone distribution (`dist\CvSU Gen\`) or single-file installer (`dist\CvSU_Gen_Setup_v1.1.0.exe`).
- **Microsoft Edge WebView2 Evergreen Runtime**: Included with Windows 11 and updated Windows 10 versions.
- **.NET Framework 4.7.2+ Baseline**: Required for the Win32/Python.NET (`pythonnet`) desktop host and OLE drag-and-drop integration (`native/dnd.py`).
- **Office Software**: Microsoft Office (Word & Excel) or compatible office suite (only needed for viewing or editing generated documents).

---

## 🚀 How to Run & Install

### Option A: Setup Wizard (Recommended)
1. Run **`CvSU_Gen_Setup_v1.1.0.exe`**.
2. Follow the setup wizard. Installation runs with per-user privileges (`PrivilegesRequired=lowest`), so faculty members do **not** require Windows Administrator rights.
3. Launch from the Start Menu or Desktop shortcut.

### Option B: Portable Directory (`--onedir`)
1. Open the **`dist\CvSU Gen\`** folder.
2. Double-click **`CvSU Gen.exe`**.

> **Note on Windows Defender / SmartScreen & VirusTotal Heuristics:**
> - **Zero-Dropper `--onedir` Architecture**: Unlike legacy `--onefile` packaging, the app does **not** extract executables to `%TEMP%\_MEIxxxxxx` on startup, preventing dropper heuristics and drastically improving launch speed.
> - **Verified PE Metadata**: Complete `VS_VERSION_INFO` headers (`version_info.txt`) authenticate the binary name, product version, and institutional copyright (**Cavite State University - CEIT**).
> - **Clean Heuristic Baseline**: The binary is unsigned by default to avoid triggering VirusTotal heuristic penalties on untrusted self-signed root certificates. Developers may pass `--self-sign` to sign locally.

---

## 🛠️ Build Pipeline & Antivirus Hardening

The build pipeline has been hardened to eliminate common false positives from machine-learning antivirus scanners and VirusTotal:

| Antivirus Trigger | Root Cause | Implemented Solution |
| :--- | :--- | :--- |
| **Dropper Heuristic** | `--onefile` unpacking into `%TEMP%\_MEIxxxxxx` | Converted to `--onedir` + Inno Setup wizard (`installer.iss`) |
| **Heuristic / UPX Flag** | UPX packer stub signatures | Disabled UPX compression (`upx=False`) in PyInstaller spec |
| **Missing PE Headers** | Blank or partial Windows resource tables | Embeds canonical `VSVersionInfo` block via `version_info.txt` |
| **Untrusted Root Cert** | Self-signed Authenticode certificates | Default build leaves binary clean/unsigned; signing is `--self-sign` opt-in |
| **AST / Scanners** | Bare `eval()` calls in webview runtime | Replaced with `ast.literal_eval()` with strict type guards |
| **Process Injection** | `subprocess.Popen(['explorer', '/select,', ...])` | Native `ctypes.windll.shell32` (`SHOpenFolderAndSelectItems`) |
| **Dynamic Filesystem Imports**| Runtime `spec_from_file_location` imports | Static import hooks bundled directly into PyInstaller `PYZ` archive |
| **Untrusted DLL / MotW (`0x80131515`)** | Windows blocks `Python.Runtime.dll` in downloaded ZIP or OneDrive | Bundles `CvSU Gen.exe.config` enabling `<loadFromRemoteSources enabled="true"/>` |

### Compiling the Standalone Application

Run `build.bat` from `executable_test/`:

```bat
cd executable_test
build.bat
```

Command-line flags:
- `build.bat`: Clean `--onedir` build, unsigned PE headers, auto-invokes Inno Setup if `ISCC.exe` is found on PATH.
- `build.bat --self-sign`: Signs the compiled binary with the local institutional Authenticode certificate.
- `build.bat --nopause`: Suppresses the terminal pause for headless or automated CI execution.

---

## 📁 Required Input Files

Before generating, make sure you have the following files ready:

### 1. Instructor Master Schedule (`.xls` or `.xlsx`)
- Download your official schedule spreadsheet from the faculty portal.
- The generator automatically extracts your instructor name, college header, semester, academic year, class times, days, and rooms.
- _Note:_ Any schedule blocks labeled as `Async` or `Asynch` are automatically filtered out so only in-person sessions receive attendance columns.

### 2. Student Roster Files (`.xlsx`, `.xls`, or `.csv`)
- Download class student rosters directly from [registrar.cvsu.edu.ph](https://registrar.cvsu.edu.ph/).
- Standard naming format:
  ```text
  {Course/Sec} List of Students for {ScheduleCode}-{Subject}.xlsx
  ```
  **Example:**
  ```text
  BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.xlsx
  ```

### 3. Unified Smart Ingest & Named Workspaces
- Drag and drop any supported file (`.xlsx`, `.xls`, `.csv`, `.docx`, `.ics`, `.cvsu-org.json`, `.cvsu-workspace.json`) directly into the window or dropzones; the system auto-routes each file.
- Mid-semester roster diffing previews added, dropped, and modified students.
- Named workspaces allow instant switching between academic semesters or instructor profiles.

---

## 📂 Output Folder Structure

Generated files are arranged cleanly by course and section:

```text
<Selected Output Folder>/
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

## 🏷️ Version History

- **Release v1.1.0**:
  - **Antivirus & False-Positive Hardening**: Replaced `--onefile` packaging with `--onedir` distribution bundled via Inno Setup (`installer.iss`), eliminating `%TEMP%\_MEIxxxxxx` dropper heuristics and startup extraction latency.
  - **Sanitized Python Runtime**: Replaced bare `eval()` with `ast.literal_eval()`, refactored generator module loading to static `PYZ` bytecode, and switched Explorer integration from `subprocess.Popen` to native `ctypes.windll.shell32` (`SHOpenFolderAndSelectItems`).
  - **Opt-in Code Signing**: Made local self-signed certificate signing opt-in (`--self-sign`) while embedding valid Windows PE `VS_VERSION_INFO` metadata (`version_info.txt`), eliminating untrusted root certificate penalties on VirusTotal.
  - **Apple HIG Preferences Redesign**: Transformed Faculty Defaults into an Apple Human Interface Guidelines Inset Grouped List (`.apple-hig-group`) featuring themed squircle icon tiles (👤 Instructor, 🏛️ College, 🗓️ Term).
  - **Document Header Live Preview**: Integrated an interactive macOS Quick Look-style header simulation card with a glowing `• LIVE SYNC` badge.
  - **Uniform Modal Geometry & Multi-Breakpoint Adaptation**: Standardized dialog boundaries, fluid grids, and compact viewports.
- **Release v1.0.1**:
  - WCAG 2.1 AA accessibility hardening pass, keyboard navigation, focus management, Windows high-contrast support, and ARIA live regions.
- **Release v1.0.0**:
  - Modularized UI and script architecture, native drag-and-drop, and official production release.
