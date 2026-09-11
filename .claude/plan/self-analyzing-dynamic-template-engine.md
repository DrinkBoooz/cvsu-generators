# Technical Feasibility & Architecture Plan: Self-Analyzing Dynamic Template Engine

## Executive Summary

**Yes, it is entirely possible for the CvSU Document Generator to analyze new document formats and apply the needed population logic automatically from within the program itself, without requiring manual Python subclassing or AI intervention.**

Currently, the application uses **Hardcoded Coordinate Generators** (e.g., `ConsultationGenerator`, `DTRGenerator`, `AttendanceGenerator`), where table indices (`tables[1]`), row offsets (`row[3]`), and string replacement techniques (`replace_after_colon`) are statically written in Python source code.

By introducing a **Declarative Template Engine with Heuristic Auto-Detection**, the software can inspect any newly uploaded `.docx` or `.xlsx` template, identify the metadata fields and roster tables, generate an internal mapping "recipe," and execute generation dynamically.

---

## 1. Why Code Changes Are Currently Required

In the current v1.9 architecture:
```
New Template (.docx)
  └──> Developer/AI must inspect XML table structure
        └──> Write New Python Subclass in `ceit_gen.py`
              └──> Hardcode table/row/cell indices
                    └──> Register in `GeneratorFactory`
                          └──> Recompile .exe
```

Every form has slight variations:
- Some forms have instructor names inside paragraph runs: `"Instructor: Dan Joseph Ortega"`.
- Some forms place metadata in a 2-column header table (`Row 0, Cell 1`).
- Student tables differ: some start at Row 1, others have 3 header rows (Row 3), and column order varies (`[No, Name, Student Number]` vs. `[No, Student Number, Name]`).

---

## 2. The Three Solutions for Self-Analyzing Templates

### Solution A: Smart Placeholder Tags (The Jinja-docx Approach)
*Best for: When the user has permission to edit the template file in Microsoft Word.*

- **How it works**: Instead of the program guessing where data goes, the template author simply writes standard tags into the Word document:
  - Header: `{{INSTRUCTOR}}`, `{{SUBJECT}}`, `{{COURSE_SEC}}`, `{{SCHED_CODE}}`, `{{SEMESTER}}`
  - Student Rows: A table row containing `{{#STUDENTS}}`, `{{NAME}}`, `{{STUDENT_NO}}`, `{{/#STUDENTS}}`
- **Program Behavior**:
  1. The user drops `my_custom_form.docx` into `templates/custom/` or uploads it via the app.
  2. The program analyzes the document for `{{...}}` tokens.
  3. If recognized tokens exist, the document is registered immediately.
- **Pros**: 100% precision; impossible for the program to place data in the wrong cell; zero UI configuration needed.
- **Cons**: Requires adding placeholders into official Word templates once before using.

---

### Solution B: Heuristic Structural Auto-Detection (The "Smart Sniffer")
*Best for: When the user drops in raw official CvSU forms without editing them.*

- **How it works**: The program inspects any standard `.docx` file using heuristic pattern recognition:
  1. **Metadata Field Sniffing**:
     - Scans all paragraphs and table cells for label regexes:
       - Instructor: `/(faculty|instructor|teacher)\s*[:.]?/i`
       - Course/Section: `/(course\s*(&|and)?\s*sec(tion)?|section|yr\s*(&|and)?\s*sec)\s*[:.]?/i`
       - Subject Name: `/(subject(\s*title)?|course\s*title|descriptive\s*title)\s*[:.]?/i`
       - Schedule Code: `/(sched(ule)?\s*code|class\s*code)\s*[:.]?/i`
     - Determines target:
       - If the label is followed by a colon or underscore in the same cell (`"Instructor: ________"`), marks for in-place text replacement.
       - If the label is alone in a cell (e.g., Row 0, Cell 0 = "Instructor:"), targets the adjacent cell (Row 0, Cell 1).
  2. **Roster Table Identification**:
     - Examines all tables in the document.
     - Identifies the table that has a row with column headers matching:
       - Name: `/(student\s*)?name|pangalan|pupil/i`
       - ID: `/(student\s*)?(no|number|id)|lrn/i`
       - Row Index: `/(no|#|item)/i`
     - Detects the `first_student_row_index` and column mappings automatically.
  3. **Capacity & Overflow Rules**:
     - Counts blank rows already present in the template.
     - If roster length > blank rows, enables dynamic row cloning.

---

### Solution C: Interactive Visual Template Mapper (The "Template Studio" Modal)
*Best for: Combining Auto-Detection with 1-click User Confirmation.*

- **UI Workflow**:
  1. User clicks **"Import New Template"** in the UI.
  2. The program runs Solution B's Auto-Detection.
  3. A modal opens with a live visual preview of the template:
     - Header Block: "Detected: Instructor &rarr; Table 0, Cell (0, 1) [✓ Correct / Change]"
     - Student Block: "Detected: Table 1, Row 2 onwards &rarr; Col 1 = Name, Col 2 = ID [✓ Correct / Change]"
  4. The user verifies with one click, gives the form a friendly name (e.g. *"Laboratory Safety Agreement"*), and clicks **Save Form**.
  5. The program writes a declarative JSON Recipe into `%APPDATA%/CVSU_Generators/custom_templates/`.

---

## 3. Declarative Template Recipe Schema

Instead of compiling Python code, the program uses a JSON recipe:

```json
{
  "template_id": "lab_safety_agreement",
  "display_name": "Laboratory Safety Agreement",
  "filename": "template_lab_safety.docx",
  "category": "ceit_forms",
  "output_suffix": "LAB_SAFETY",
  "header_bindings": [
    {
      "field": "instructor",
      "location_type": "table_cell",
      "table_index": 0,
      "row_index": 1,
      "col_index": 1,
      "strategy": "replace_after_colon"
    },
    {
      "field": "course_section",
      "location_type": "table_cell",
      "table_index": 0,
      "row_index": 1,
      "col_index": 3,
      "strategy": "full_replace"
    }
  ],
  "roster_table_binding": {
    "table_index": 1,
    "header_row_index": 0,
    "first_data_row_index": 1,
    "columns": {
      "index": 0,
      "name": 1,
      "student_number": 2
    },
    "font_shrink_threshold": 32,
    "font_shrink_size": "18"
  }
}
```

---

## 4. Generic Engine Architecture (`modules/generators/generic_doc_gen.py`)

A single Python class handles all dynamic templates forever:

```python
class ConfigurableDocumentGenerator(DocumentGenerator):
    def __init__(self, template_path: str, recipe: dict):
        super().__init__(template_path)
        self.recipe = recipe

    def fill_header(self, body, info: ClassInfo) -> None:
        for binding in self.recipe.get("header_bindings", []):
            field_val = getattr(info, binding["field"], "")
            if binding["location_type"] == "table_cell":
                cell = body.tables[binding["table_index"]].rows[binding["row_index"]].cells[binding["col_index"]]
                if binding["strategy"] == "replace_after_colon":
                    replace_after_colon(cell, field_val)
                else:
                    set_cell_text(cell, field_val)

    def _fill_student_row(self, cells: list, idx: int, name: str, stnum: str) -> None:
        cols = self.recipe["roster_table_binding"]["columns"]
        if "index" in cols:
            set_cell_text(cells[cols["index"]], str(idx))
        if "name" in cols:
            set_cell_text(cells[cols["name"]], name, shrink_threshold=32, shrink_sz="18")
        if "student_number" in cols:
            set_cell_text(cells[cols["student_number"]], stnum)
```

---

## 5. Feasibility Breakdown by File Format

| Format | Feasibility | Complexity | Notes |
| :--- | :---: | :---: | :--- |
| **Word (.docx) Academic Forms** | **98% (Extremely High)** | Low/Moderate | Table structures, paragraphs, and runs in `python-docx` are highly predictable. Auto-detection of labels and rosters can be built in ~300 lines of Python. |
| **Word (.docx) Attendance Sheets** | **90% (High)** | Moderate | Requires detecting calendar/date columns and duplicating rows or columns per day of week. |
| **Excel (.xlsx) Grading Sheets** | **60% (Moderate)** | High | Grade sheets contain formulas (`SUM`, `AVERAGE`, `VLOOKUP`), merged calculation cells, and locked ranges. Dynamic formula rewrites require cell coordinate dependency graphs. Best handled with tagged cell ranges. |

---

## 6. Implementation Roadmap (If You Choose to Build This)

1. **Phase 1: Backend Inspection Engine**
   - Create `modules/parsers/template_inspector.py`.
   - Implement `inspect_docx_template(filepath) -> dict` returning detected metadata fields, table candidate scores, and suggested recipe.
2. **Phase 2: Generic Document Generator**
   - Create `ConfigurableDocumentGenerator` driven by the JSON recipe.
   - Update `GeneratorFactory.get_all()` to dynamically scan `%APPDATA%/CVSU_Generators/custom_templates/` and load custom generators alongside factory defaults.
3. **Phase 3: Frontend "Template Studio" UI**
   - Add "Custom Templates" tab in the Settings modal (⚙️).
   - Allow drag-and-drop of any new `.docx` file.
   - Show live auto-detection summary with visual confirmation cards.
4. **Phase 4: Dynamic Orchestration & Stepper**
   - Step 2 in the main Stepper dynamically lists both official CEIT forms and user-added custom forms.
   - Orchestrator computes total generation steps dynamically.
