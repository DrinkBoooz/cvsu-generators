# Project Rules

## Tests Location

All test programs, test suites, test fixtures, and testing utilities must always be placed under the `tests/` directory:

- Automated tests (`test_*.py`) belong in `tests/`.
- Regression, edge cases, diff, and verification scripts belong in `tests/`.
- Do not place test scripts in the root directory.

## Git Commit Formatting

All git commit messages must strictly follow the format:
`<commit_number>: <description based on chat changes>`

- **Format**: `<commit_number>: <description based on chat changes>`
- **`<commit_number>`**: The sequential commit number for the repository (e.g. `git rev-list --count HEAD + 1`).
- **`<description based on chat changes>`**: Clear, descriptive summary of the modifications implemented during the chat/task.
- **Example**: `43: dynamically calculate progress bar total steps and update completion telemetry`

## Git Branching & Merging Rules

- **Development on `dev`**: All active work, feature implementations, tests, and task commits belong strictly on the `dev` branch.
- **Do NOT Auto-Merge to `main`**: Merging into `main` must **NEVER** happen automatically at the end of a task or chat. Merging to `main` requires an explicit user prompt or request.
- **Merging into `main` (Only When Prompted by User)**:
  When the user explicitly instructs to merge `dev` into `main`:
  - **Always use `--no-ff` (No Fast-Forward)**: Never perform fast-forward merges into `main`. Always force a dedicated merge commit using `git merge --no-ff <branch>` to ensure the Git commit history preserves a distinct visual branch tree with fork-and-merge nodes.
  - **Merge Commit Message Formatting**: Merge commits must also follow the commit numbering rule and clearly summarize the changes being merged into the target branch:
    `<commit_number>: merge <source_branch> into <target_branch> - <description of merged changes>`
    Example: `49: merge dev into main - implement toast notifications, cancellation engine, and stepper workflow`
  - **Standard Merge Workflow**:
    1. Ensure all work is committed and pushed on `dev`.
    2. `git checkout main`
    3. `git merge --no-ff dev -m "<commit_number>: merge dev into main - <description of merged changes>"`
    4. `git push origin main`
    5. `git checkout dev`

## Version Numbering & Synchronization

- **Single Source of Truth**: The active application version is displayed in `executable/ui.html` via the `<span class="badge-version">vX.Y Beta</span>` badge in the navigation header.
- **When to Bump the Version**:
  - Whenever new features, UX workflows, generators, or significant fixes are implemented across a chat or milestone, the version number must be bumped (e.g. from `v1.1 Beta` -> `v1.2 Beta`).
  - Never leave the version number stale across releases or major feature updates.
- **Synchronization Checklist**:
  1. `executable/ui.html`: Update the header badge `<span class="badge-version">vX.Y Beta</span>`.
  2. `tests/test_ui_consistency.py`: Ensure test assertions verify the current version badge.
  3. `executable/README.md`: If version numbers or changelog items are listed, keep them synchronized.
  4. `executable/file_version_info.txt`: Synchronize `filevers`, `prodvers`, `FileVersion`, and `ProductVersion`.

## Executable Packaging, Copyright & Code Signing

Whenever the application is exported, compiled, or packaged as a standalone Windows executable (`.exe`):

- **Windows PE Version Information**: `executable/file_version_info.txt` must always be maintained with official copyright (`Copyright © 2026 Dan Joseph Ortega. All rights reserved.`), company/author name (`Dan Joseph Ortega`), product name (`CvSU Document Generator`), and version numbers synchronized with `ui.html`.
- **PyInstaller Integration**: Both `executable/build.bat` and `executable/CvSU Gen (Beta).spec` must embed `file_version_info.txt` via `--version-file` / `version='file_version_info.txt'` so Windows Explorer (Properties -> Details), hover tooltips, and Task Manager display the author and copyright.
- **Authenticode Code Signing**: Executable binaries compiled in `executable/dist/` should be digitally signed via `executable/sign_exe.ps1` (or automated post-build in `build.bat`) using `signtool.exe` and the author's Authenticode certificate (`Dan Joseph Ortega`). This ensures Windows SmartScreen and UAC prompts identify the verified author/publisher instead of "Unknown Publisher".
- **Automated Tests**: Any changes to versioning or executable metadata must be validated by tests under `tests/` (including `tests/test_pe_version_info.py`).

## Adding New Templates & Generators Protocol

Whenever a new document template is introduced to the application, the agent must follow this protocol to integrate, scaffold, and test it end-to-end.

### 1. The 3 Template Families in the Architecture

| Family                            | Template Directory | Generator Engine                                       | Output Folder                       | Output Naming Pattern                                    |
| :-------------------------------- | :----------------- | :----------------------------------------------------- | :---------------------------------- | :------------------------------------------------------- |
| **Academic / CEIT Forms (.docx)** | `templates/`       | `modules/generators/ceit_gen.py` (`DocumentGenerator`) | `<Output>/<Course_Sec>/CEIT_Forms/` | `<Course_Sec>_<SchedCode>_<SUFFIX>.docx`                 |
| **Attendance Sheets (.docx)**     | `attendance/`      | `modules/generators/attendance_gen.py`                 | `<Output>/<Course_Sec>/Attendance/` | `<Course_Sec>_<SchedCode>_ATTENDANCE_<Day>_<Month>.docx` |
| **Grading Spreadsheets (.xlsx)**  | `templates/`       | `modules/generators/grade_gen.py`                      | `<Output>/<Course_Sec>/`            | `<Course_Sec>_<SchedCode>_GRADING_SHEET.xlsx`            |

### 2. Step-by-Step Checklist for Academic / CEIT Forms (.docx)

When instructed to add or create a new form generator from a `.docx` template:

1. **Place Template**: Place the template file in `templates/` (e.g. `templates/template_consultation.docx`).
2. **Inspect Template Structure**: Run a quick diagnostic script using `python-docx` to inspect table indices, row structures, and column layouts:
   ```python
   import docx
   doc = docx.Document("templates/<your_template>.docx")
   for idx, tbl in enumerate(doc.tables):
       print(f"Table {idx} ({len(tbl.rows)} rows, {len(tbl.columns)} cols):")
       for r_idx, r in enumerate(tbl.rows[:3]):
           print(f"  Row {r_idx}: {[c.text.strip() for c in r.cells]}")
   ```
3. **Implement Generator Subclass in `modules/generators/ceit_gen.py`**:
   - Subclass `DocumentGenerator(ABC)`.
   - Implement `fill_header(self, body, info: ClassInfo) -> None`:
     - Access header tables or paragraphs.
     - Replace metadata placeholders (`info.instructor`, `info.course_section`, `info.schedule_code`, `info.subject`, `info.time_days_room`, `info.semester_ay`).
     - Use helper functions from `modules.common.docx_utils`: `set_cell_text`, `replace_after_colon`, `replace_value_run`, and `shrink_threshold` font scaling.
   - Implement `_fill_student_row(self, cells: list, idx: int, name: str, stnum: str) -> None`:
     - Assign row cells (e.g. `cells[0]` for row number or name, `cells[1]` for student number, etc.).
     - Apply `set_cell_text(cells[col], name, shrink_threshold=32, shrink_sz="18")` to protect against long student names wrapping awkwardly.
4. **Register in `GeneratorFactory` (`modules/generators/ceit_gen.py`)**:
   - Add template key to `GeneratorFactory.TEMPLATE_FILES`:
     ```python
     "new_key": "template_new_file.docx",
     ```
   - Add instantiation tuple to `GeneratorFactory.get_all()`:
     ```python
     (lambda: NewFormGenerator(self._path("new_key")), "NEW_FORM_SUFFIX"),
     ```
5. **Export in `modules/generators/__init__.py`**:
   - Import the new generator class and add it to `__all__`.
6. **Orchestrator Telemetry & Packaging**:
   - `modules/services/orchestrator.py` automatically scales: `num_ceit_generators = len(factory.get_all())` calculates total progress steps dynamically.
   - Both `executable/CvSU Gen (Beta).spec` and `executable/build.bat` bundle the entire `templates/` directory (`--add-data "..\templates;templates/"`), so the new file is automatically packaged into `.exe` builds.
7. **Synchronize Documentation & README**:
   - `executable/README.md`: If the total count of CEIT forms (e.g. "7 complete forms") or list of forms is described, update the count and bullet item.
   - `tests/test_ui_consistency.py`: Keep README assertions synchronized.
8. **Automate & Validate Tests**:
   - Update `tests/test_modules_generation.py`:
     - Update `assert len(all_gens) == <new_total>`
     - Add the new suffix to `expected_suffixes`.
   - Add a unit test (e.g. in `tests/test_<new_form>_generator.py`) asserting:
     - Template exists and loads via factory.
     - Generated `.docx` contains populated instructor, course, and student rows.
   - Run `pytest tests/ -k "not test_playwright"` to ensure 100% test pass rate.
