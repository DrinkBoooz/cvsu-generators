# Cavite State University (CvSU) Document Generator

[![Release](https://img.shields.io/badge/version-v2.0%20Beta-blue.svg)](file:///c:/Users/danjo/OneDrive/CVSU%20GENERATORS/executable/ui.html)
[![Tests](<https://img.shields.io/badge/tests-153%20passed%20(100%25)-brightgreen.svg>)](file:///c:/Users/danjo/OneDrive/CVSU%20GENERATORS/tests)
[![Platform](<https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(x64)-lightgrey.svg>)](file:///c:/Users/danjo/OneDrive/CVSU%20GENERATORS/executable)
[![License](https://img.shields.io/badge/copyright-%C2%A9%202026%20Dan%20Joseph%20Ortega-purple.svg)](file:///c:/Users/danjo/OneDrive/CVSU%20GENERATORS/executable/file_version_info.txt)
[![Authenticode](<https://img.shields.io/badge/Authenticode-Digitally%20Signed%20(DigiCert%20RFC%203161)-success.svg>)](file:///c:/Users/danjo/OneDrive/CVSU%20GENERATORS/executable/sign_exe.ps1)

A high-performance, institutional desktop application and automation engine engineered for Cavite State University (CvSU) faculty members. The system ingests raw instructor master schedules (`.xls`/`.xlsx`) and student rosters (`.xlsx`/`.xls`/`.csv`) to automatically generate submission-ready, standardized academic forms, monthly attendance sheets, Excel grading sheets with preserved mathematical formulas, and custom dynamic documents via an offline heuristic analysis engine.

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Technology Stack &amp; Dependencies](#technology-stack--dependencies)
3. [Repository File Map](#repository-file-map)
4. [Package &amp; Module Deep Dive](#package--module-deep-dive)
   - [modules.common](#modulescommon)
   - [modules.models](#modulesmodels)
   - [modules.parsers](#modulesparsers)
   - [modules.generators](#modulesgenerators)
   - [modules.services](#modulesservices)
   - [executable Desktop Application](#executable-desktop-application)
5. [End-to-End Processing Logic &amp; Data Pipelines](#end-to-end-processing-logic--data-pipelines)
   - [1. Schedule Ingestion &amp; Async Filtering](#1-schedule-ingestion--async-filtering)
   - [2. Roster Parsing &amp; Fuzzy Schedule Pairing](#2-roster-parsing--fuzzy-schedule-pairing)
   - [3. Deterministic Structural Template Inspection](#3-deterministic-structural-template-inspection)
   - [4. Dynamic Document Generation &amp; OpenXML AST Injection](#4-dynamic-document-generation--openxml-ast-injection)
   - [5. Grading Sheet OpenXML Formula Preservation](#5-grading-sheet-openxml-formula-preservation)
6. [User Configuration &amp; Custom Templates Store](#user-configuration--custom-templates-store)
7. [Comprehensive Verification &amp; Automated Testing Suite](#comprehensive-verification--automated-testing-suite)
8. [Standalone Compilation &amp; Authenticode Code Signing](#standalone-compilation--authenticode-code-signing)
9. [Command-Line &amp; Programmatic Usage](#command-line--programmatic-usage)

---

## Architectural Overview

CvSU Document Generator is designed as a decoupled, modular system adhering to Clean Architecture principles:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Desktop GUI (PyWebView + HTML5/CSS3)                     │
│               Dark/Light Theme · Stepper UI · Live Settings · D&D Dropzones            │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ PyWebView JS API Bridge
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             Application API Gateway (executable/main.py)              │
│               File Dialogs · Config Bridge · Thread Worker · Cancellation Engine       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Generation Orchestrator (modules/services)                      │
│            Pre-flight Validation · Telemetry · Progress Step Calculations              │
└───────────────┬───────────────────────────┬────────────────────────────┬───────────────┘
                │                           │                            │
                ▼                           ▼                            ▼
┌───────────────────────────────┐ ┌───────────────────┐ ┌────────────────────────────────┐
│       modules.parsers         │ │   modules.common  │ │       modules.generators       │
│  - ScheduleParser             │ │ - ConfigManager   │ │ - AttendanceGenerator (.docx)  │
│  - RosterParser               │ │ - DocxUtils (XML) │ │ - CEIT DocumentGens (.docx)    │
│  - CeitDirectory (Curriculum) │ │ - ExcelUtils      │ │ - GradeGenerator (.xlsx)       │
│  - TemplateInspector (Zero-AI)│ │ - Logger          │ │ - ConfigurableDocGen (Dynamic) │
└───────────────────────────────┘ └───────────────────┘ └────────────────────────────────┘
                │                           │                            │
                └───────────────────────────┼────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   Target Categorized Output Tree (<Output>/<Section>/)                  │
│       ├── Attendance/          (Monthly Word sheets with calendar dates)               │
│       ├── CEIT_Forms/          (7 standardized department forms + Custom Forms)        │
│       └── <Section>_GRADING_SHEET.xlsx  (Lecture or Lecture+Lab grade workbook)        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack & Dependencies

| Component              | Technology / Library                   | Purpose                                                                |
| :--------------------- | :------------------------------------- | :--------------------------------------------------------------------- |
| **Core Runtime**       | Python 3.10 – 3.14 (x64)               | Primary execution engine                                               |
| **GUI Framework**      | `pywebview` + `pythonnet`              | Native Windows webview host (Edge Chromium / WebView2) & WinForms CLR  |
| **Frontend UI**        | HTML5, Vanilla CSS3, Modern JavaScript | Responsive interface with modular CSS design tokens                    |
| **Word Processing**    | OpenXML AST via `lxml.etree`           | High-speed XML AST manipulation (<20ms per document)                   |
| **Spreadsheet Engine** | `openpyxl` + `xlrd`                    | Native reading of `.xls` (BIFF8) and `.xlsx` formula workbooks         |
| **Packaging**          | `PyInstaller`                          | Bundles runtime, Python standard library, assets into standalone `.exe`|
| **Security & Signing** | Microsoft `signtool.exe` + DigiCert    | Authenticode digital signing with RFC 3161 SHA-256 timestamping        |
| **Automated Testing**  | `pytest`, `python-docx`, `playwright`  | Comprehensive unit, integration, template parity, and UI automation    |

### Windows System Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python / Python Packages**: None required on the target machine for the packaged executable. The Python runtime and application packages are embedded in `CvSU Gen.exe`.
- **Microsoft Edge WebView2 Evergreen Runtime**: Required host prerequisite. WebView2 is included with Windows 11; Microsoft documents Windows 10 version 1803+ with the November 2022 update as the preinstalled baseline, though certain Windows 10, LTSC, managed, or clean systems may lack the Runtime. The packaged application does not bundle an automatic WebView2 installer, and no explicit application-level runtime detector was verified in the current source.
- **.NET Framework 4.7.2+ Project Baseline**: Supported Windows baseline for the Python.NET WinForms host and OLE drag-and-drop integration (`executable_test/native/dnd.py`). While Python.NET supports older .NET Framework versions, 4.7.2+ is the repository's verified project baseline.
- **Office Software**: Microsoft Office (Word & Excel) or compatible office suite (only needed for opening/editing generated DOCX/XLSX files).

### Dependency Manifests
The repository uses four distinct manifests with exact direct-dependency pins:
- `requirements-runtime.txt`: Core production runtime (`pywebview`, `pythonnet`, `lxml`, `openpyxl`, `xlrd`).
- `requirements-test.txt`: Testing & development suite (`pytest`, `python-docx`, `playwright` + runtime).
- `requirements-build.txt`: Executable packaging (`pyinstaller` + runtime).
- `requirements.txt`: Aggregate developer manifest (`-r requirements-test.txt` and `-r requirements-build.txt`).


---

## Repository File Map

```text
CVSU GENERATORS/
├── attendance/                         # Source templates for monthly attendance sheets
│   └── template_attendance.docx
├── executable/                         # Standalone desktop application source & build scripts
│   ├── build.bat                       # Compilation and automated Authenticode signing script
│   ├── CvSU Gen (Beta).spec            # PyInstaller build specification
│   ├── file_version_info.txt           # Windows PE 32-bit/64-bit metadata and version resource
│   ├── main.py                         # Desktop GUI entrypoint & PyWebView API bridge
│   ├── sign_exe.ps1                    # Authenticode code-signing script using SignTool & SHA-256
│   ├── ui.html                         # Apple HIG responsive frontend interface (v2.0 Beta)
│   ├── dist/                           # Compiled standalone executable (CvSU Gen (Beta).exe)
│   └── README.md                       # End-user operational guide
├── modules/                            # Core modular Python architecture
│   ├── common/                         # Shared utilities, configuration, and XML helpers
│   │   ├── config_manager.py           # Persistent user configuration & custom template store
│   │   ├── docx_utils.py               # OpenXML AST parsing, run manipulation, font auto-scaling
│   │   ├── excel_utils.py              # Shared string parsing and numeric sanitation
│   │   └── logger.py                   # Centralized application logging
│   ├── models/                         # Domain models and typing structures
│   │   ├── config.py                   # Configuration schema models
│   │   ├── schedule.py                 # ClassInfo, ScheduleEntry, TimeSlot, RoomAssignment
│   │   └── student.py                  # Student dataclass & name normalization
│   ├── parsers/                        # Document & schedule ingestion parsers
│   │   ├── ceit_directory.py           # Department mapping, subject prefixes, lab detectors
│   │   ├── roster_parser.py            # Roster file parser (.xlsx, .xls, .csv)
│   │   ├── schedule_parser.py          # Master schedule parser (.xls, .xlsx)
│   │   └── template_inspector.py       # Deterministic Structural Template Inspector (Zero-AI)
│   ├── generators/                     # Document generation engines
│   │   ├── attendance_gen.py           # Monthly attendance sheet generator (.docx)
│   │   ├── ceit_gen.py                 # 7 CEIT departmental forms & GeneratorFactory
│   │   ├── generic_doc_gen.py          # Configurable generic document generator
│   │   └── grade_gen.py                # Official grading workbook generator (.xlsx)
│   └── services/                       # Orchestration and validation services
│       ├── orchestrator.py             # Generation pipeline orchestrator & telemetry engine
│       └── validator.py                # Pre-flight data integrity validation
├── templates/                          # Source Word (.docx) and Excel (.xlsx) templates
│   ├── template_syllabus.docx          # VPAA-QF-12 Course Syllabus Acceptance
│   ├── template_exam_midterm.docx      # Midterm Exam Returns
│   ├── template_exam_finals.docx       # Final Exam Returns
│   ├── template_tos_midterm.docx       # Midterm Table of Specifications (TOS)
│   ├── template_tos_finals.docx        # Final Table of Specifications (TOS)
│   ├── Midterm-Grade-Discussion_LATEST.docx  # Midterm Grade Discussion Form
│   ├── Final-Grade-Discussion_LATEST.docx    # Final Grade Discussion Form
│   ├── GRADING_LECTURE_TEMPLATE.xlsx         # Lecture Grading Sheet
│   └── GRADING_LECTURE_LAB_TEMPLATE.xlsx     # Lecture + Laboratory Grading Sheet
├── test_templates/                     # Sample multi-format Word templates for testing & UI D&D
│   ├── README.md                       # Guide for test templates
│   ├── template_consultation_log.docx  # 2-column table metadata + 4-col student roster
│   ├── template_guidance_advising.docx # 3-column colon table + 5-col student roster
│   ├── template_tag_placeholders.docx  # {{TAG}} placeholders + 3-col student roster
│   ├── template_laboratory_monitoring.docx # 4-column multi-label table + 6-col roster
│   └── template_faculty_eval.docx      # Paragraph colons + Filipino column tokens
├── tests/                              # Comprehensive test suite (153+ automated tests)
│   ├── test_templates/                 # Template analyzer verification test suite
│   │   ├── create_templates.py         # Deterministic test template synthesis
│   │   └── test_diverse_templates.py   # Multi-format inspection & generation tests
│   ├── test_attendance_*.py            # Attendance generator & scheduling tests
│   ├── test_config_manager.py          # Configuration persistence & fallback tests
│   ├── test_custom_template_pipeline.py# Custom template registration & factory tests
│   ├── test_generic_doc_gen.py         # ConfigurableDocumentGenerator unit tests
│   ├── test_grade_*.py                 # Excel grading sheet formula preservation tests
│   ├── test_modules_*.py               # Parser and generator module integrity tests
│   ├── test_pe_version_info.py         # Windows binary PE version resource tests
│   ├── test_playwright_*.py            # Playwright UI automated interactions
│   ├── test_template_inspector.py      # Heuristic inspection engine tests
│   └── test_ui_*.py                    # UI API bridge and visual consistency tests
├── AGENTS.md                           # Strict agent rules & testing protocol
└── pytest.ini                          # Pytest configuration
```

---

## Package & Module Deep Dive

### `modules.common`

#### 1. `config_manager.py` (`ParserConfigManager`)

- **Persistence Location**: `%APPDATA%/CVSU_Generators/config/parser_settings.json` and `%APPDATA%/CVSU_Generators/custom_templates/`.
- **Key Responsibilities**:
  - Maintains persistent overrides for subject prefixes, lab-bearing subjects, degree aliases, column header keywords, and fallback schedule defaults.
  - Implements an **atomic file write pattern** via `tempfile.NamedTemporaryFile` and `os.replace` to prevent JSON corruption during power failure or process interruptions.
  - Provides a **Custom Template Store** (`save_custom_template`, `get_custom_templates`, `toggle_custom_template`, `delete_custom_template`) to register custom `.docx` templates along with their declarative heuristic recipes.
  - Exposes in-memory query helpers: `get_ceit_prefix_map()`, `get_subject_prefixes()`, `is_lab_subject()`, `get_roster_keywords()`.
  - Implements listener callbacks (`register_listener`) to notify active components when user settings change.

#### 2. `docx_utils.py`

- **Low-Level OpenXML Manipulation**:
  - `load_docx(path)`: Unpacks `.docx` container via `zipfile.ZipFile`, reads `word/document.xml`, parses into an `lxml.etree` element tree, and returns `(zin, root, body)`.
  - `save_docx(zin, root, output_path)`: Recompresses all original media, styles, and headers, serializing the modified `word/document.xml` with XML declaration and UTF-8 encoding.
  - `set_cell_text(cell, text, shrink_threshold, shrink_sz)`: Clears existing paragraph runs and writes new text, automatically applying font size scaling if text length exceeds `shrink_threshold` (e.g. shrinking from 11pt to 9pt for long student names).
  - `replace_after_colon(para, value, shrink_threshold, shrink_sz)`: Discovers colons (`:`) within multi-run paragraphs, preserves the label run, and replaces succeeding runs with the assigned value without altering paragraph bullet or indentation properties.
  - `auto_scale_font(run, text, threshold, shrink_sz)`: Dynamically injects `<w:sz w:val="...">` and `<w:szCs w:val="...">` into `<w:rPr>` to prevent undesirable line wraps.

#### 3. `excel_utils.py`

- Direct ZIP/XML parsing helpers for legacy workbooks and shared string tables, bypassing `openpyxl` locks when inspecting workbook metadata.

#### 4. `logger.py`

- Structured logging service writing to standard output and local rotating logs (`%APPDATA%/CVSU_Generators/logs/`).

---

### `modules.models`

#### 1. `schedule.py`

- `ClassInfo`: Domain representation of an academic section:
  ```python
  @dataclass
  class ClassInfo:
      instructor: str
      course_section: str
      schedule_code: str
      subject: str
      time_days_room: str
      semester_ay: str
      students: List[Tuple[str, str]]  # List of (Student Name, Student Number)
      college: str = "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"
      has_lab: bool = False
      subject_code: str = ""
      subject_name: str = ""
  ```
- `ScheduleEntry`: Represents an individual timeslot block parsed from teacher schedules (`day`, `time_start`, `time_end`, `room`, `class_name`, `subject_code`, `is_async`).

#### 2. `student.py`

- `Student`: Normalized student record with helper methods for capitalisation, surname-first formatting, and student number sanitation.

---

### `modules.parsers`

#### 1. `schedule_parser.py` (`ScheduleParser`)

- Ingests raw teacher schedule spreadsheets (`.xls` via `xlrd`, `.xlsx` via `openpyxl`).
- **AST Block Tracking**: Discovers instructor name from cell labels (`"Instructor:"`, `"Name:"`), college header (`"COLLEGE OF ..."`), and semester/AY (`"1st Semester..."`).
- Scans timetable grid coordinates, extracting days (`Monday`–`Sunday`), time intervals (`07:00AM-10:00AM`), room assignments, schedule codes, and subject titles.
- **Async Intelligent Filtering**: Detects `Async` or `Asynch` tags, filtering out remote blocks so attendance sheets only generate columns for physical meetings.

#### 2. `roster_parser.py` (`RosterParser`)

- Ingests student enrollment lists downloaded from `registrar.cvsu.edu.ph` (`.xlsx`, `.xls`, `.csv`).
- **Dynamic Header Detection**: Scans the first 10 rows to locate header columns using token recognition (`Name`, `Student Number`, `ID`, `Student's Name`).
- **Fault-Tolerant Extra Column Stripping**: Automatically detects and strips auxiliary portal columns (e.g. Email, Gender, Remarks) without failing.
- **Roster File Naming Parsing**: Extracts metadata hints from standard filenames:
  `{Course_Sec} List of Students for {SchedCode}-{Subject}.xlsx`

#### 3. `ceit_directory.py`

- University curriculum registry mapping course prefixes to academic departments:
  - `COSC`, `DCIT`, `ITEC` &rarr; Department of Information Technology (DIT)
  - `CENG`, `CIVL` &rarr; Department of Civil Engineering (DCE)
  - `AGEN`, `ABEN` &rarr; Department of Agricultural and Food Engineering (DAFE)
  - `CPEN` &rarr; Department of Computer Engineering
- Identifies whether a subject contains laboratory sessions by cross-referencing user configuration and catalog defaults.

#### 4. `semantic_registry.py` (`SemanticRegistry`)

- Pure lexical and semantic registry for normalization, alias matching, candidate extraction, and collision observations across DOCX and XLSX templates.
- Does not authorize bindings or make final validity decisions.

#### 5. `template_inspector.py` (`DocxTemplateInspector`, `XlsxTemplateInspector`, `TemplateInspector`)

- **Deterministic Template Inspection Layer**: Analyzes Word (`.docx`) and Excel (`.xlsx`) templates.
- **Inspector Non-Authority Invariant**: Inspectors emit candidate observations (`RawTemplateRecipeCandidate`) and **never** construct or return `ValidatedTemplateRecipe`.
- **Analyzes**:
  1. **Metadata Candidates**: Locates where `Instructor`, `Course/Section`, `Schedule Code`, `Subject`, `Time/Days/Room`, and `Semester/AY` live across table cells, colon paragraphs, and discrete spreadsheet cells.
  2. **Tag Placeholders**: Discovers template tags such as `{{INSTRUCTOR}}`, `{{COURSE_SECTION}}`, `{{SCHEDULE_CODE}}`, `{{SUBJECT}}`.
  3. **Student Roster Candidate**: Scans tables and worksheets to detect student rows, classifying columns for `index`, `id_number`, `student_name`, `signature`, and `capacity_limit`.
  4. **Structural Merged Signature Geometry**: Discovers instructor signature targets in Excel by merged cell geometry above signature labels (Mutation M8).
- `TemplateInspector`: Backward-compatible public API facade running inspection & validation.

#### 6. `recipe_validator.py` (`RecipeValidator`)

- **Sole Authority**: Transforms `RawTemplateRecipeCandidate` into immutable `ValidatedTemplateRecipe`.
- Enforces strict `schema_version == 2`, profile constraints (`required_fields`, `prohibited_fields`, `capacity_limit`), collision resolutions, and verified safe assertions.
- Protects `ValidatedTemplateRecipe` with private construction sentinel and AST static analysis.

---

### `modules.generators`

#### 1. `ceit_gen.py`

- Base class `DocumentGenerator(ABC)` orchestrating pure recipe-driven execution:
  ```python
  def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe):
      ...
  def generate(self, info: ClassInfo, output_path: str) -> None:
      zin, root, body = load_docx(self.template_path)
      self.fill_header(body, info)
      self.fill_table(body, info)
      save_docx(zin, root, output_path)
  ```
- **7 Built-in CEIT Generators** (all consume validated recipes and zero hardcoded coordinates):
  1. `SyllabusGenerator`: Course Syllabus Acceptance Form (`VPAA-QF-12`).
  2. `ExamReturnsGenerator`: Midterm Examination Returns (`period="MIDTERM"`).
  3. `ExamReturnsGenerator`: Final Examination Returns (`period="FINAL"`).
  4. `TOSGenerator`: Table of Specifications (`period="Midterm"`).
  5. `TOSGenerator`: Table of Specifications (`period="Finals"`).
  6. `GradeDiscussionGenerator`: Midterm Grade Discussion Form (`period="Midterm"`).
  7. `GradeDiscussionGenerator`: Final Grade Discussion Form (`period="Finals"`).
- `GeneratorFactory`: Factory class resolving recipes through `TemplateRecipeResolver` and instantiating built-in and custom generators.

#### 2. `attendance_gen.py` (`AttendanceGenerator`)

- Generates monthly attendance sheets (`.docx`) for each month across the semester.
- **Calendar Engine**: Calculates the exact calendar meeting dates based on the class's scheduled days.
- **Multi-Slot Times**: Combines lecture and lab meeting times on the header.
- Formats table columns with meeting dates, populating student rows with auto-scaled font widths.

#### 3. `grade_gen.py` (`GradeGenerator`)

- Generates official CvSU Excel grading workbooks (`.xlsx`) using pure recipe-driven execution.
- Strictly requires `ValidatedTemplateRecipe` in `__init__`; zero hardcoded cell coordinates.
- **Capacity Clamping**: Dynamically clamps student entries to `recipe.roster_binding.capacity_limit` (40 students max based on verified template formulas).
- **Structural Signature Discovery**: Injects instructor signature into dynamically resolved merged cell coordinates based on structural geometry above signature labels.

#### 4. `generic_doc_gen.py` (`ConfigurableDocumentGenerator`)

- Dynamic generator that consumes `ValidatedTemplateRecipe` to populate arbitrary Word documents with `ClassInfo` and student rosters according to detected bindings and tag placeholders.

---

### `modules.services`

#### 1. `template_recipe_service.py` (`TemplateRecipeResolver`)

- Centralized shared recipe resolution service utilized by both `GeneratorFactory` and `orchestrator.py`.
- Owns absolute path resolution, SHA-256 template fingerprinting, 3-tuple caching `(absolute_path, profile_id, fingerprint)`, stale cache invalidation, inspector dispatch, and `RecipeValidator` execution.

#### 2. `orchestrator.py` (`GenerationOrchestrator`)

- Coordinates the complete batch execution:
  1. Validates inputs and pairs schedules with rosters.
  2. Dynamically calculates total progress steps:
     $\text{Total Steps} = \text{Sections} \times (\text{Num CEIT Gens} + \text{Num Attendance Months} + 1 \text{ Grade Sheet})$.
  3. Dispatches async generation tasks with real-time percentage and status telemetry callbacks.
  4. Supports thread-safe cancellation via `threading.Event`.

#### 2. `validator.py` (`PreflightValidator`)

- Performs sanity checks before generation begins:
  - Verifies presence and readability of all template files.
  - Flags orphaned student rosters that do not match any schedule block.
  - Warns if schedule blocks lack matching student rosters.

---

### `executable` Desktop Application

#### 1. `main.py`

- PyWebView application controller and native Python-to-JavaScript bridge.
- Methods exposed to UI:
  - `browse_schedule()`, `browse_rosters()`, `browse_output_dir()`
  - `start_generation(options)`, `cancel_generation()`
  - `get_parser_config()`, `save_parser_config()`, `reset_parser_config()`
  - `inspect_custom_template()`, `save_custom_template()`, `delete_custom_template()`

#### 2. `ui.html`

- Modern, Apple HIG-inspired single-page desktop UI.
- Features:
  - **Dark / Light Theme Engine**: System-responsive palette with instantaneous transitions.
  - **4-Step Workflow**: Visual cards for Schedule, Rosters, Output Folder, and Launch.
  - **6-Tab Settings Modal**: Full management for Subject Prefixes, Lab Subjects, Degree Aliases, Column Keywords, Schedule Defaults, and Custom Templates.
  - **Live Heuristic Inspection Card**: Displays real-time template confidence, detected fields, and mapped columns when a user drops a `.docx` template.

---

## End-to-End Processing Logic & Data Pipelines

### 1. Schedule Ingestion & Async Filtering

```text
Schedule File (.xls/.xlsx)
       │
       ▼
Extract Metadata (Instructor, College, Sem/AY)
       │
       ▼
Scan Timetable Grid Coordinates
       │
       ▼
Filter out "Async" / "Asynch" blocks
       │
       ▼
Group into Assigned Classes (Section, Subject, Days, Times, Rooms)
```

### 2. Roster Parsing & Fuzzy Schedule Pairing

Each roster file is parsed and paired with a schedule entry using a 3-tier matching heuristic:

1. **Schedule Code Match**: If the filename or internal cell contains `202612040`, pair with the matching schedule entry.
2. **Normalized Section & Subject Match**: Matches section (`BSCS 1-4` &rarr; `BSCS1-4`) and subject code (`DCIT 21`).
3. **Program Alias Match**: Resolves informal abbreviations (e.g. `CS 1-4` &rarr; `BSCS 1-4`) via `ceit_directory.py`.

### 3. Deterministic Structural Template Inspection

CvSU Document Generator enforces a strict architectural invariant across all template generation:
```text
INSPECTOR DETERMINES WHERE.
GENERATOR DETERMINES WHAT.
VALIDATOR DETERMINES WHETHER THE WHERE IS SAFE.
```

When templates (`.docx` or `.xlsx`) are inspected and processed:

1. **Deterministic Structural Discovery**: Examines physical geometry (tables, rows, cells, merged ranges, and paragraphs). Uses structural evidence (merged boxes, direct adjacency, and unambiguous token mapping) rather than arbitrary positional offsets or positional defaults.
2. **Ambiguity Rejection**: If multiple distinct physical targets satisfy a semantic field or roster without a unique structural discriminator, discovery fails closed and raises `AmbiguousTemplateError` instead of arbitrarily picking a candidate by confidence score.
3. **Fail-Closed Physical Geometry Validation**: `RecipeValidator` enforces strict bounds checks against physical OpenXML/DOCX and openpyxl structures. Every table, row, cell, column, paragraph, and worksheet index must be verified within physical limits before a `ValidatedTemplateRecipe` is issued.
4. **Zero Generator-Side Structural Invention**: Production generators consume only immutable validated recipes and fail closed with `TemplateError` if an invalid or out-of-bounds coordinate reaches execution. Generators never invent coordinates, assume positions, or attempt positional fallbacks.

### 4. Dynamic Document Generation & OpenXML AST Injection

During generation with `ConfigurableDocumentGenerator` or built-in generators:

- Metadata is written to bound table cells and paragraph colons using `replace_after_colon()`.
- Placeholder tokens `{{...}}` are replaced in direct runs and across fragmented paragraph runs.
- The template student row is cloned for each student in `info.students`.
- Long student names automatically receive font scaling (`auto_scale_font`) to prevent awkward cell wrapping.

### 5. Grading Sheet OpenXML Formula Preservation

- Uses `openpyxl` with `data_only=False` to preserve all formulas.
- Injects student rosters into the Lecture and Laboratory sheets.
- Updates header metadata cells in all sheets.
- Formulas referencing student scores (e.g. `=AVERAGE(D12:D45)`, `=SUM(...)`) remain intact.

---

## User Configuration & Custom Templates Store

User settings are saved in `%APPDATA%/CVSU_Generators/`:

- `config/parser_settings.json`: User overrides for prefixes, lab subjects, aliases, keywords, and fallbacks.
- `custom_templates/templates.json`: Index of registered custom templates and recipes.
- `custom_templates/<template_id>.docx`: Persisted template files.

---

## Comprehensive Verification & Automated Testing Suite

The repository includes **153+ automated tests** under `tests/` verifying 100% pass rates:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0
collected 157 items / 4 deselected / 153 selected

tests/test_attendance_default_template.py .                              [  0%]
tests/test_attendance_name_scaling.py .                                  [  1%]
tests/test_attendance_schedule_parsing.py .............                  [  9%]
tests/test_config_manager.py ....                                        [ 12%]
tests/test_custom_template_pipeline.py ...                               [ 14%]
tests/test_dnd_flow.py ..                                                [ 15%]
tests/test_edge_cases.py .....                                           [ 18%]
tests/test_generic_doc_gen.py ..                                         [ 20%]
tests/test_grade_discussion_generator.py ...                             [ 22%]
tests/test_grade_generator.py ...........                                [ 29%]
tests/test_modules_generation.py ...                                     [ 31%]
tests/test_modules_integrity.py ......                                   [ 35%]
tests/test_modules_parsing.py ....                                       [ 37%]
tests/test_output_parity.py ........                                     [ 43%]
tests/test_parser_user_config.py ....                                    [ 45%]
tests/test_pe_version_info.py .....                                      [ 49%]
tests/test_pywebview_dnd_binding.py .                                    [ 49%]
tests/test_regression.py .....                                           [ 52%]
tests/test_roster_parser.py ..........                                   [ 59%]
tests/test_scroll_aware_dock.py .                                        [ 60%]
tests/test_simulate_unknown.py .....                                     [ 63%]
tests/test_stepper_2col_scroll.py ...                                    [ 65%]
tests/test_template_inspector.py ....                                    [ 67%]
tests/test_templates/test_diverse_templates.py ......................... [ 84%]
tests/test_theme_consistency.py .....                                    [ 88%]
tests/test_theme_transition_perf.py .                                    [ 89%]
tests/test_ui_api_bridge.py ............                                 [ 97%]
tests/test_ui_consistency.py ....                                        [100%]

===================== 153 passed, 4 deselected in 17.48s ======================
```

### Running the Tests

```bash
# Run all automated tests (excluding Playwright UI headless browser)
pytest tests/ -k "not test_playwright"

# Run only the multi-format template verification suite
pytest tests/test_templates/ -v

# Run Playwright UI browser tests
pytest tests/ -k "test_playwright"
```

---

## Standalone Compilation & Authenticode Code Signing

The application packages into a standalone Windows binary (`CvSU Gen (Beta).exe`):

1. **PE Version Metadata**: `executable/file_version_info.txt` defines Windows Explorer Properties, copyright, and product versions (`2.0.0.0`).
2. **PyInstaller Compilation**: Executed via `executable/build.bat`, bundling assets, templates, and runtime.
3. **Authenticode Signing**: Automatically executed post-build via `executable/sign_exe.ps1`:
   - Uses Microsoft `signtool.exe`.
   - Signs with SHA-256 certificate (`CN=Dan Joseph Ortega`).
   - Timestamps with DigiCert RFC 3161 server (`http://timestamp.digicert.com`).
   - Ensures Windows SmartScreen and UAC identify the publisher as **Dan Joseph Ortega**.

---

## Command-Line & Programmatic Usage

### 1. Python API Usage

```python
from modules.models.schedule import ClassInfo
from modules.parsers.template_inspector import TemplateInspector
from modules.generators.generic_doc_gen import ConfigurableDocumentGenerator

# 1. Inspect any Word template
inspector = TemplateInspector()
recipe = inspector.inspect_docx("path/to/template.docx")
print(f"Confidence: {recipe['confidence']}%")

# 2. Populate with class details
info = ClassInfo(
    instructor="Dan Joseph A. Ortega",
    course_section="BSCS 3-1",
    schedule_code="202612040",
    subject="DCIT 55 - Advanced Database Systems",
    time_days_room="MTh 1:00-3:00 PM CL4",
    semester_ay="First Semester, A.Y. 2026-2027",
    students=[
        ("Dela Cruz, Juan M.", "202310001"),
        ("Santos, Maria Clara", "202310002"),
    ],
)

# 3. Generate output
generator = ConfigurableDocumentGenerator("path/to/template.docx", recipe)
generator.generate(info, "output/BSCS_3-1_CUSTOM_FORM.docx")
```

### 2. Launching Desktop Application

```bash
# From python environment
python executable/main.py

# Or launch standalone binary directly
./executable/dist/CvSU\ Gen\ (Beta).exe
```

---

## Author & Copyright

**Developer**: Dan Joseph Ortega
**Institution**: Cavite State University (CvSU)
**Copyright**: © 2026 Dan Joseph Ortega. All rights reserved.
