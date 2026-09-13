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

- **Single Source of Truth**: The active application version is displayed in `executable_test/ui.html` via the `<span class="badge-version">Release vX.Y.Z</span>` badge in the navigation header.
- **When to Bump the Version**:
  - Whenever new features, UX workflows, generators, or significant fixes are implemented across a chat or milestone, the version number must be bumped (e.g. from `Release v1.0.0` -> `Release v1.0.1`).
  - Never leave the version number stale across releases or major feature updates.
- **Synchronization Checklist**:
  1. `executable_test/ui.html`: Update the header badge `<span class="badge-version">Release vX.Y.Z</span>`.
  2. `tests/test_ui_consistency.py`: Ensure test assertions verify the current version badge.
  3. `executable_test/README.md`: If version numbers or changelog items are listed, keep them synchronized.
  4. `executable_test/file_version_info.txt`: Synchronize `filevers`, `prodvers`, `FileVersion`, and `ProductVersion`.
  5. `cvsu-generator_documentation/05 - Releases & Changelog/`: Add or update release notes for the new version in the Obsidian documentation vault.

## Obsidian Documentation Vault Protocol

> [!IMPORTANT]
> ## Project and Documentation Relationship
>
> The project consists of two coordinated resources:
>
> 1. **Application Repository**
>    - Location: `C:\Users\danjo\OneDrive\CVSU GENERATORS`
>    - Git repository: `DrinkBoooz/cvsu-generators`
>    - Active development branch: `dev`
>    - Contains application source code, tests, templates, executable build configuration, and project configuration.
>
> 2. **Companion Obsidian Documentation Vault**
>    - Location: `C:\Users\danjo\Desktop\cvsu-generator_documentation`
>    - Contains the project's human-readable technical documentation, architecture knowledge, generator specifications, template documentation, user guides, and release documentation.
>
> The Obsidian vault is the project's **primary human-readable knowledge repository**. It documents the behavior and structure of the application but does not override the source code, tests, or actual templates.
>
> The vault is physically located outside the Git repository and must not be copied into or committed to the application repository unless explicitly requested.

### 1. Source-of-Truth Hierarchy

When discrepancies or questions arise, agents must strictly observe this priority hierarchy:

1. **Executable / Application Source Code**: Active Python and frontend runtime code.
2. **Automated Tests**: Validated test suites and test fixtures (`tests/`).
3. **Templates**: Word (`.docx`) and Excel (`.xlsx`) files actively consumed by generator engines.
4. **Obsidian Documentation Vault**: Primary human-readable knowledge repository and architectural guides.
5. **README / Supplementary Documentation**: Quickstart summaries and release notes.

> **Obsidian is the primary human-readable documentation and knowledge repository. It must reflect the behavior of the application, tests, and templates; it does not override implementation or test behavior.**

### 2. Never Fabricate Documentation

**Documentation must be derived from the current implementation, templates, tests, and verified project behavior. Agents must not infer or invent undocumented generator behavior, template mappings, coordinates, filenames, or workflow requirements.**

Before writing or updating documentation:
- Inspect the active source code.
- Inspect the physical template files using diagnostic scripts or parser tests.
- Verify exact cell names, coordinates, function signatures, and naming conventions from the actual files.

### 3. Documentation-First vs. Code-First Workflows

- **For Implementation Changes**:
  ```text
  Inspect implementation → Inspect tests/templates → Implement → Run tests → Update Obsidian → Verify documentation against implementation
  ```
- **For Documentation-Only Changes**:
  ```text
  Inspect implementation → Update Obsidian → No code changes unless discrepancy discovered
  ```

### 4. Documentation Synchronization Triggers

#### Changes Requiring Obsidian Updates:
- Application architecture and subsystem restructuring
- Generator engine logic, inputs, outputs, or new form registrations
- Template file structure, coordinates, placeholders, or auto-scaling rules
- User workflow steps, dialog flows, or public-facing UI features
- File naming patterns, folder organization, or roster column rules
- Application configuration management or settings schemas
- PyWebView bridge methods, IPC contracts, or threading/lifecycle mechanics
- Standalone packaging, PyInstaller specs, or code signing procedures
- Application version bumps and official release notes

#### Changes NOT Requiring Obsidian Updates:
- Typo corrections or code comment adjustments
- Pure styling tweaks or formatting-only CSS changes
- Internal code refactoring with identical externally observable behavior
- Test suite enhancements or refactoring that do not alter observable system contracts
- Minor dependency maintenance without behavioral impact

### 5. Vault Structure & Taxonomy

Documentation within `c:\Users\danjo\Desktop\cvsu-generator_documentation` must adhere to:

- **`00 - Index/`**: Maps of Content (MOC), root indexes, and high-level navigation (`CvSU Document Generator MOC.md`).
- **`01 - Architecture/`**: Core technical architecture, PyWebView API bridge, generator pipeline, orchestrator lifecycle, and UI architecture.
- **`02 - Generators/`**: Technical documentation for document generators (`ceit_gen.py`, `attendance_gen.py`, `grade_gen.py`).
- **`03 - Templates/`**: Template schema definitions, placeholder mapping tables, cell coordinates, and auto-scaling rules.
- **`04 - User Guides/`**: End-user manuals, step-by-step walkthroughs, file naming conventions, and troubleshooting.
- **`05 - Releases & Changelog/`**: Historical release notes (`vX.Y.Z.md`) synchronized with `ui.html` badges and `file_version_info.txt`.
- **`06 - Development/`**: Developer workflow, testing strategy, build & packaging recipes, and agent development rules.

### 6. Obsidian Markdown & Graph Conventions

- **YAML Frontmatter**: Standardized frontmatter for every note:
  ```yaml
  ---
  title: "<Note Title>"
  tags:
    - cvsu-generator
    - <category-tag>
  status: active # active | draft | deprecated | archived
  last_modified: YYYY-MM-DD # Note modification date, not app code date
  source_of_truth:
    - <relative/path/to/source/file>
  ---
  ```
- **Wikilinks**: Use `[[Target Note Name]]` or `[[Target Note Name|Display Text]]`. Keep links valid and ensure graph connections represent actual system dependencies.
- **MOC Maintenance**: When a new top-level documentation area or major component is created, update the relevant MOC / index note.
- **Git Separation**: The vault is physically located outside the Git repository. Agents must never copy the vault into the repository or commit it unintentionally.

## Executable Packaging, Copyright & Code Signing

Whenever the application is exported, compiled, or packaged as a standalone Windows executable (`.exe`):

- **Windows PE Version Information**: `executable_test/file_version_info.txt` must always be maintained with official copyright (`Copyright © 2026 Dan Joseph Ortega. All rights reserved.`), company/author name (`Dan Joseph Ortega`), product name (`CvSU Document Generator`), and version numbers synchronized with `ui.html`.
- **PyInstaller Integration**: Both `executable_test/build.bat` and `executable_test/CvSU Gen.spec` must embed `file_version_info.txt` via `--version-file` / `version='file_version_info.txt'` so Windows Explorer (Properties -> Details), hover tooltips, and Task Manager display the author and copyright.
- **Authenticode Code Signing**: Executable binaries compiled in `executable_test/dist/` should be digitally signed via `executable_test/sign_exe.ps1` (or automated post-build in `build.bat`) using `signtool.exe` and the author's Authenticode certificate (`Dan Joseph Ortega`). This ensures Windows SmartScreen and UAC prompts identify the verified author/publisher instead of "Unknown Publisher".
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
   - Both `executable_test/CvSU Gen.spec` and `executable_test/build.bat` bundle the entire `templates/` directory (`--add-data "..\templates;templates/"`), so the new file is automatically packaged into `.exe` builds.
7. **Step 7 — Synchronize Documentation**:
   After implementing and testing a new generator or template:
   1. Update `executable_test/README.md` when the change affects developer-facing repository documentation.
   2. Create or update the corresponding Obsidian documentation note in `cvsu-generator_documentation/02 - Generators/` or `03 - Templates/`.
   3. Update the relevant generator/template/architecture notes.
   4. Update affected wikilinks and MOCs (`00 - Index/CvSU Document Generator MOC.md`).
   5. Verify that documented behavior matches the implementation and actual template.
   6. Update `last_modified` in the note frontmatter.
   7. Do not document behavior that has not been verified against the physical template and code.
8. **Automate & Validate Tests**:
   - Update `tests/test_modules_generation.py`:
     - Update `assert len(all_gens) == <new_total>`
     - Add the new suffix to `expected_suffixes`.
   - Add a unit test (e.g. in `tests/test_<new_form>_generator.py`) asserting:
     - Template exists and loads via factory.
     - Generated `.docx` contains populated instructor, course, and student rows.
   - Run `pytest tests/ -k "not test_playwright"` to ensure 100% test pass rate.

