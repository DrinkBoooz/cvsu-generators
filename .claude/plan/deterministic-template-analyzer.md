# Implementation Plan: In-App Deterministic Heuristic Template Analyzer & Dynamic Generator

## Executive Summary
This plan details the design and implementation of an entirely **100% native, offline, deterministic heuristic analysis engine** built directly into the CvSU Document Generator. 

It allows end users to import any arbitrary Microsoft Word (`.docx`) template directly into the application. Without calling any AI model, LLM, API, or cloud service, the program's built-in Python algorithms inspect the document's XML table and paragraph hierarchy in **under 20 milliseconds**, deduce the locations of header metadata (Instructor, Course, Section, Subject, Schedule Code) and student roster tables (Name, Student Number, Row Index), and generate the document automatically during batch processing.

---

## User Review Required

> [!IMPORTANT]
> **100% Offline & Pure Python**: This feature requires **ZERO AI**, no OpenAI/Gemini API keys, no internet connection, and no external binary dependencies. It executes using `python-docx` and `lxml`, already bundled inside the application executable.

> [!NOTE]
> **Scope**: The heuristic analyzer focuses on **Microsoft Word (`.docx`)** document forms (which account for all CEIT academic forms, acceptance forms, and clearance slips). Excel (`.xlsx`) grading sheets with interconnected calculation formulas remain handled by `grade_gen.py`.

---

## Architectural Workflow

```
┌────────────────────────────────────────────────────────┐
│ 1. User Uploads / Drops New .docx Template in UI       │
└───────────────────────────┬────────────────────────────┘
                            │ (Local PyWebView Bridge)
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. Deterministic Heuristic Inspection (< 20ms)         │
│    `modules/parsers/template_inspector.py`             │
│    - Scan Key-Value Tables for Academic Metadata       │
│    - Scan Paragraphs for Colon-Delimited Labels        │
│    - Locate & Classify Student Roster Grid             │
│    - Detect Column Positions (Name, ID, Signature)     │
└───────────────────────────┬────────────────────────────┘
                            │ (Returns Inspection Summary)
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. UI Visual Review Card & 1-Click Confirmation        │
│    User reviews detected fields & assigns a Form Name  │
└───────────────────────────┬────────────────────────────┘
                            │ (User clicks "Add to My Forms")
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. Recipe Persistence (%APPDATA%/custom_templates/)    │
│    - Saves template .docx and .json recipe             │
│    - ConfigManager registers template dynamically      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. Generation Execution (Orchestrator Loop)            │
│    `GeneratorFactory` dynamically loads custom forms   │
│    `ConfigurableDocumentGenerator` produces outputs    │
└────────────────────────────────────────────────────────┘
```

---

## Deterministic Analysis Algorithm (The "Inspector")

### Algorithm 1: Header & Metadata Field Detection
The algorithm scans `doc.tables` and `doc.paragraphs`:
1. **Keyword Dictionaries**:
   ```python
   METADATA_PATTERNS = {
       "instructor": r"(instructor|faculty|professor|teacher|adviser)\b",
       "course_section": r"(course\s*(&|and)?\s*sec(tion)?|yr\s*(&|and)?\s*sec|program\s*(&|and)?\s*sec)\b",
       "schedule_code": r"(sched(ule)?\s*code|class\s*code)\b",
       "subject": r"(subject(\s*title)?|course\s*title|descriptive\s*title)\b",
       "time_days_room": r"(time\s*/?\s*day(s)?\s*/?\s*room|schedule|class\s*schedule)\b",
       "semester_ay": r"(semester\s*/?\s*(ay|academic\s*year)|term|sem)\b"
   }
   ```
2. **Table Traversal**:
   - For each table, if total rows < 15 and cols between 2 and 4:
     - Check each cell for a regex match in `METADATA_PATTERNS`.
     - If matched in Cell `[r, c]`:
       - If Cell `[r, c+1]` is a colon `":"`, target Cell `[r, c+2]`.
       - If Cell `[r, c+1]` is non-colon, target Cell `[r, c+1]`.
       - Strategy: `set_cell_text` with font auto-scaling.
3. **Paragraph Traversal (Fallback)**:
   - If metadata is not in a table, scan paragraphs.
   - If paragraph text contains `Label + ":"`, record paragraph index and strategy `replace_after_colon`.

### Algorithm 2: Student Roster Table Classification
How the inspector finds the student roster table with 100% certainty:
1. **Header Row Identification**:
   - Loops through each table in the document.
   - For rows 0, 1, 2, evaluates cell text against token sets:
     - **Name Tokens**: `{"name", "student name", "name of student", "pangalan"}`
     - **ID Tokens**: `{"student number", "student no", "id number", "stud no", "lrn"}`
     - **Index Tokens**: `{"no.", "no", "#", "item"}`
     - **Signature Tokens**: `{"signature", "lagda", "sign"}`
2. **Confidence Scoring**:
   - If a table row has both a **Name Column** and an **ID or Signature Column**, it is definitively identified as the Roster Table.
3. **Template Row Extraction**:
   - Header row index = `h_idx`.
   - First student data row = `h_idx + 1`.
   - The cell formatting (font family, font size, cell alignment, borders) of the first student row is cached as the replication stamp.
   - Existing sample rows are measured to establish row capacity.

---

## Proposed Changes

### 1. Core Module Additions

#### [NEW] `modules/parsers/template_inspector.py`
- Implements `TemplateInspector`:
  - `inspect_docx(template_path: str) -> dict`: Returns structured analysis payload containing:
    - `is_valid`: bool
    - `detected_name`: Suggested display name and suffix
    - `header_bindings`: List of detected header mappings (field, table_idx, row_idx, col_idx, strategy)
    - `roster_table`: Table index, header row, name column, student number column, index column
    - `confidence_score`: Heuristic confidence percentage (0-100%)
    - `raw_preview`: Summary preview for the UI card

#### [NEW] `modules/generators/generic_doc_gen.py`
- Implements `ConfigurableDocumentGenerator(DocumentGenerator)`:
  - Consumes a declarative JSON recipe.
  - Implements `fill_header(body, info)` dynamically driving bindings.
  - Implements `_fill_student_row(cells, idx, name, stnum)` dynamically routing values into detected columns.
  - Reuses existing `docx_utils` (`set_cell_text`, `replace_after_colon`, `shrink_threshold`).

#### [MODIFY] `modules/common/config_manager.py`
- Add custom template directory management (`%APPDATA%/CVSU_Generators/custom_templates/`).
- Add methods:
  - `get_custom_templates() -> list[dict]`
  - `register_custom_template(name, suffix, docx_bytes_or_path, recipe) -> dict`
  - `delete_custom_template(template_id) -> bool`
  - `toggle_custom_template(template_id, enabled: bool) -> None`

#### [MODIFY] `modules/generators/ceit_gen.py`
- Update `GeneratorFactory`:
  - In `get_all()`, load built-in CEIT generators, and then dynamically query `config_manager.get_custom_templates()`.
  - For each enabled custom template, append:
    ```python
    (lambda: ConfigurableDocumentGenerator(custom_path, recipe), recipe["output_suffix"])
    ```
  - This immediately makes `orchestrator.py` pick up custom templates with zero orchestrator code modifications!

---

### 2. PyWebView Bridge & UI Integration

#### [MODIFY] `executable/main.py`
- Expose new `ScriptAPI` bridge methods:
  - `inspect_custom_template(file_path)`: Runs `TemplateInspector` and returns analysis JSON to the frontend.
  - `save_custom_template(payload)`: Saves template file and recipe into `%APPDATA%`, notifies listeners.
  - `get_custom_templates()`: Returns list of installed custom templates.
  - `delete_custom_template(template_id)`: Removes template and recipe.

#### [MODIFY] `executable/ui.html`
- **Settings Modal Addition**:
  - Add a 6th tab to `#modalParserSettingsBackdrop`: **📄 Custom Templates**.
  - Dropzone for `.docx` template files.
  - **Instant Analysis Card**:
    - Displays detected document title, detected metadata rows, and detected student table.
    - Editable fields: Form Name (e.g. *"Lab Clearance"*), Output Suffix (e.g. *"LAB_CLEARANCE"*).
    - Toggle switches for detected bindings with 1-click override dropdowns if the user wants to reassign a column.
    - Button: **Add to Generator Suite**.
  - List of active custom templates with toggle switch (Enable/Disable) and Delete button.
- **Main Stepper Step 2**:
  - Dynamically lists user-installed custom templates alongside the built-in forms.

---

## Verification Plan

### Automated Tests (under `tests/`)
1. **Inspector Self-Test on Existing Forms** (`tests/test_template_inspector.py`):
   - Run `TemplateInspector.inspect_docx()` on all 7 built-in templates:
     - `template_syllabus.docx`
     - `template_exam_midterm.docx`
     - `template_exam_finals.docx`
     - `template_tos_midterm.docx`
     - `template_tos_finals.docx`
     - `Midterm-Grade-Discussion_LATEST.docx`
     - `Final-Grade-Discussion_LATEST.docx`
   - Assert that the inspector correctly identifies:
     - The student roster table index.
     - The student name column index.
     - The student number column index.
     - At least 4 metadata fields (Instructor, Course/Section, Subject, SchedCode) without any hardcoded template-specific hints!
2. **Generic Generator Parity Test** (`tests/test_generic_doc_gen.py`):
   - Run `ConfigurableDocumentGenerator` using the auto-generated recipe against sample class rosters.
   - Assert that output `.docx` matches the output generated by the hardcoded Python subclasses!
3. **End-to-End Dynamic Orchestration Test** (`tests/test_custom_template_pipeline.py`):
   - Register a mock custom template in `%TEMP%`.
   - Run `GeneratorFactory.get_all()` and verify `len(generators)` increases by 1.
   - Run `orchestrator.py` and verify the custom document is generated in the output folder.
4. **Playwright UI Flow Test** (`tests/test_playwright_custom_templates.py`):
   - Open Settings &rarr; Custom Templates tab.
   - Test analysis card rendering and template management actions.
