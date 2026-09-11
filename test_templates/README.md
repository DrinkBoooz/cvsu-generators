# CvSU Document Generator - Test Templates

This directory contains diverse, realistic `.docx` test templates designed to verify the **Deterministic Heuristic Template Analyzer** and the **Configurable Generic Document Generator** introduced in **v2.0 Beta**.

You can test these files either:
1. **Directly in the App**: Drag and drop any of these files into the **Custom Templates** tab in the in-app Settings modal (`Ctrl+,` or ⚙️ icon).
2. **Automated Test Suite**: Run `pytest tests/test_templates/test_diverse_templates.py -v`.

---

## 📂 Included Template Formats

| File Name | Header Layout | Student Roster Columns | Primary Focus |
| :--- | :--- | :--- | :--- |
| `template_consultation_log.docx` | 2-column metadata table | `No.`, `Student Number`, `Name of Student`, `Signature` | Academic Consultation & Student Office Hours Log |
| `template_guidance_advising.docx` | 3-column colon table (`Label \| : \| Value`) | `Item`, `Student ID`, `Student Name`, `Concern`, `Action Taken` | Multi-column advising log with student number preceding name |
| `template_tag_placeholders.docx` | Tag-based placeholders (`{{INSTRUCTOR}}`, `{{COURSE_SECTION}}`, `{{SCHEDULE_CODE}}`, `{{SUBJECT}}`, `{{TIME_DAYS_ROOM}}`, `{{SEMESTER_AY}}`) | `LRN`, `Name`, `Remarks` | Tag-interpolated form with LRN student identification |
| `template_laboratory_monitoring.docx` | 4-column multi-label table | `#`, `Student's Name`, `Stud No`, `Workstation No.`, `Time In`, `Time Out` | Computer lab utilization log with 6-column roster |
| `template_faculty_eval.docx` | Paragraph colon bindings (`Professor:`, `Section:`, `Subject:`) | `Index`, `Pangalan`, `Numero`, `Lagda` | Filipino / Tagalog column token recognition |

---

## 🧪 Automated Verification

All automated tests for these templates reside in `tests/test_templates/test_diverse_templates.py` and are executed via:
```bash
pytest tests/test_templates/ -v
```
