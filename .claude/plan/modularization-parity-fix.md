# Implementation Plan: Modular Backend Logic Parity & Regression Remediation

## Task Type
- [x] Backend (→ Logic & Parser Remediation)
- [x] Verification (→ Automated Regression & Parity Suite)

## Technical Solution & Analysis

Our deep byte-level, XML structure, and workbook comparison between current output (`C:\Users\danjo\Downloads\test-1`) and desired reference output (`C:\Users\danjo\OneDrive\SCHOOL FILES 2026`) identified 7 specific issues to resolve:

1. **Dynamic Student Name Font Scaling Ladder**:
   - The user specified the exact dynamic ladder for student names:
     - **<= 25 characters**: **9 pt** (`sz="18"`)
     - **26–30 characters**: **8 pt** (`sz="16"`)
     - **31–35 characters**: **7 pt** (`sz="14"`)
     - **> 35 characters**: **6 pt** (`sz="12"`)
   - **Remedy**: Create a unified `get_student_name_font_sz(name: str) -> str` in `modules/common/docx_utils.py` and invoke it across all CEIT generators (`ceit_gen.py`) and Attendance sheet generation (`attendance_gen.py`).

2. **Student Name Dropped (IT1-1 `NAME, ZULEIKAH MARIJ C.`)**:
   - In `modules/parsers/roster_parser.py`, `_is_name_header(a)` was being evaluated on every row after the header. Because `RE_NAME_TOKEN` matches `\bname\b` case-insensitively, any real student whose surname is "NAME" was mistakenly flagged as a header row and dropped.
   - **Remedy**: Only call header detection on rows up to `header_row`. For data rows, simply verify non-empty text that is not literally identical to the header cell.

3. **Corrupted Enye Character Encoding (`Ã` -> `Ñ`)**:
   - In `modules/parsers/roster_parser.py`, `_fix_encoding()` handles `Ã±` and `Ã‘`, but university portal exports often encode `Ñ` in all-caps names as an isolated `Ã` followed by uppercase letters (e.g., `SAÃEZ`, `CORTIÃAS`, `DELA PEÃA`).
   - **Remedy**: Enhance `_fix_encoding()` with `re.sub(r'Ã(?=[A-Z])', 'Ñ', s)` and explicit portal artifact replacements.

4. **Grade Discussion Table 0 Row 4 Mismatch & Template Discrepancy**:
   - `templates/*-Grade-Discussion_LATEST.docx` has 7 rows in Table 0 with Row 4 being an empty row `['', ':', '']`. In `ceit_gen.py`, row index fallback filled `time_days_room` into Row 4 without a label (` : Fri: 07:00AM...`). The reference desired output has 6 clean rows without this row.
   - **Remedy**: Remove the blank row from `templates/*-Grade-Discussion_LATEST.docx` and ensure `ceit_gen.py` only populates `time_days_room` if an explicit label (`TIME`, `DAY`, `ROOM`) exists.
   - *Note on file size*: The 680KB file size difference was due to duplicate header logos inside older template revisions (deduplicated in commit 53471df), not missing charts.

5. **Subject Code Normalization (`COSC 111A` vs `COSC 111`)**:
   - Roster files for CS4-1 and CS4-2 include an extra `"A"` suffix (`COSC 111A`). In `orchestrator.py`, when a matching timetable block exists with base subject code `COSC 111`, use the master schedule title to eliminate spurious suffixes across attendance and CEIT forms.

6. **Subject Type Determination for Hybrid Subjects (DCIT 21 / CS1-4)**:
   - For DCIT 21 in CS1-4, only the lecture meeting is on the instructor's schedule sheet. Auto-detection flagged it as `lecture_only` (5 sheets in Excel) instead of `lecture_lab` (7 sheets in Excel).
   - **Remedy**: Maintain curriculum awareness in `validator.py` for known lecture+lab subjects (like `DCIT 21`) so it defaults to `lecture_lab`.

---

## Implementation Steps

1. **Unified Font Size Ladder & Low-Level Helpers** (`modules/common/docx_utils.py`):
   - Add `get_student_name_font_sz()` and `is_student_name` support in `set_cell_text()`.
2. **Roster Parser Normalization** (`modules/parsers/roster_parser.py`):
   - Fix `load_students()` to avoid dropping students with surname `NAME`.
   - Update `_fix_encoding()` to correct isolated `Ã` before uppercase letters.
3. **Document Generators** (`modules/generators/ceit_gen.py`, `modules/generators/attendance_gen.py`):
   - Pass `is_student_name=True` in all student row generation methods.
   - Align `_auto_scale_attendance_name` with the 9/8/7/6 pt ladder.
   - Update `ceit_gen.py` to only write `time_days_room` when labeled.
4. **Grade Discussion Templates** (`templates/`):
   - Remove orphaned empty row from `Final-Grade-Discussion_LATEST.docx`, `Finals-Grade-Discussion_LATEST.docx`, and `Midterm-Grade-Discussion_LATEST.docx`.
5. **Subject Reconciliation & Lab Detection** (`modules/services/validator.py`, `modules/services/orchestrator.py`):
   - Reconcile subject codes against timetable blocks to strip spurious `A` suffixes.
   - Default known lab subjects (`DCIT 21`, etc.) to `lecture_lab`.
6. **Verification & Regression Suite** (`tests/test_output_parity.py`):
   - Write automated parity tests verifying font sizes, student count, enye encodings, table structure, and sheet counts.
   - Run complete test suite (`pytest`) and verify clean end-to-end execution.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `modules/common/docx_utils.py` | Modify | Add `get_student_name_font_sz()` & font ladder in `set_cell_text` |
| `modules/generators/ceit_gen.py` | Modify | Apply student name font ladder & guard `time_days_room` |
| `modules/generators/attendance_gen.py` | Modify | Align attendance student name scaling with 9/8/7/6 pt ladder |
| `modules/parsers/roster_parser.py` | Modify | Fix student row dropping & fix `Ã` -> `Ñ` encoding |
| `templates/Final-Grade-Discussion_LATEST.docx` | Modify | Remove orphan blank row 4 from Table 0 |
| `templates/Finals-Grade-Discussion_LATEST.docx` | Modify | Remove orphan blank row 4 from Table 0 |
| `templates/Midterm-Grade-Discussion_LATEST.docx` | Modify | Remove orphan blank row 4 from Table 0 |
| `modules/services/validator.py` | Modify | Add hybrid subject lab awareness for courses like DCIT 21 |
| `modules/services/orchestrator.py` | Modify | Reconcile canonical subject title against master schedule |
| `tests/test_output_parity.py` | New | End-to-end regression, parity, and font size assertion test |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Small font sizes (6pt) becoming unreadable | 6pt is strictly reserved for names > 35 chars to prevent row height expansion; 9pt/8pt used for standard names |
| Modifying templates could affect layout margins | Only delete the empty XML row element `<w:tr>` containing `['', ':', '']` from Table 0; leave all other XML properties untouched |

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: modules-backend-parity-01
- ANTIGRAVITY_SESSION: modules-verification-parity-01
