# CvSU Gen — Design & UX Handover for the Next Agent

**Handover date:** 4 November 2026  
**Project:** CvSU Gen (Cavite State University Document Generator)  
**Purpose:** Continue the UI/UX redesign without requiring the next agent to see the earlier conversation or re-upload the screenshots.

---

## 1. Executive summary

The user is dissatisfied with multiple AI-generated redesign attempts. The problem is **not primarily the color palette**. Previous attempts changed colors, borders and component arrangement while retaining the same dashboard/form architecture. The result still looks generic, cramped, overly segmented and difficult to scan.

The next agent must change the **interaction model and information architecture before visual styling**.

The user has explicitly chosen:

- **Workflow:** Hybrid.
- **Priority:** Balanced — approachable for first-time instructors while efficient for experienced instructors and repeat semester workflows.
- **Preferred product direction:** A **Hybrid Guided Batch Workbench** for academic document production.
- **Design anchor:** Apple Human Interface Guidelines and HCI/UX methods, adapted to a Windows desktop application. Do not imitate macOS chrome or copy a visual trend literally.

The key product idea:

> Instructors must be able to manage many class sections together, while still being able to inspect and configure one class at a time. Batch operations should be efficient; individual exceptions should remain easy to find and edit.

**Do not produce another dashboard reskin.** The next result must demonstrate a materially different information architecture and interaction design.

## 2. Product and user context

CvSU Gen is an offline Windows desktop utility for faculty members, particularly within the Cavite State University College of Engineering and Information Technology (CEIT).

Instructors use it to:

1. Load an instructor schedule (`.xls` / `.xlsx`).
2. Load student rosters (`.xls` / `.xlsx` / `.csv`).
3. Match roster files to scheduled classes/sections and correct mismatches.
4. Review detected classes and configure subject type and document packages.
5. Set optional semester date boundaries.
6. Choose an output directory.
7. Review prerequisites and generate academic documents.

Outputs include:

- Attendance sheets (`.docx`).
- CEIT departmental forms (`.docx`).
- Official grade sheets (`.xlsx`).

Typical scale: approximately **10–20 sections**, with up to **40 students per section**. Users may process many sections in one operation, but configurations can differ by section.

The instructor's priorities are accuracy, clarity, predictability, speed, error prevention, recovery and low-friction repeated use. This is a specialized faculty productivity tool, not a consumer application, analytics dashboard, website or marketing page.

## 3. The user's settled workflow preference

### Hybrid Guided Batch Workbench

Keep the six familiar stages as navigational contexts:

1. Schedule
2. Rosters
3. Packages
4. Dates
5. Output
6. Generate

These are **not six full forms that must all be displayed simultaneously**. A stage is a focused workspace. Users can revisit completed stages without losing valid work; do not trap them in a rigid wizard.

### The three interaction layers

**A. Guided workflow / orientation**
- Communicate where the user is, what is complete, what needs attention and what comes next.
- Show concise prerequisite summaries where useful.
- Support returning to earlier stages.
- Do not repeat all stage content in every screen.

**B. Batch workspace / primary work surface**
- Packages is expected to be the central batch-management workspace.
- Present all detected sections in a readable, scannable table or equivalent purpose-built batch view.
- Support individual and multi-selection, select all/deselect all, bulk package changes and clear readiness/exception states.
- Bulk operations must preserve per-class exceptions unless the user explicitly chooses to overwrite them.
- Show mixed values honestly when selected classes differ.

**C. Contextual editing / individual configuration**
- Selecting one class reveals the relevant class details and configuration.
- Use an on-demand inspector, contextual pane, drawer or adaptive detail view.
- Do not keep a permanent inspector open by default if it steals space from the working table.
- At narrow window sizes, use an overlay/drawer or inline editing; preserve access to all essential data.
- Users must return to batch view without losing other classes' state.

### Expected stage responsibilities

| Stage | Primary responsibility | Keep out of this stage |
|---|---|---|
| Schedule | Import/replace schedule, parse it, show instructor/semester/classes detected and parsing errors | Full roster pairing UI and package matrix |
| Rosters | Add/remove/replace roster files; show matching, student counts, parse/column status; correct incorrect or ambiguous pairings | Duplicate full roster tables elsewhere |
| Packages | Batch class selection, lecture/lab or supported subject classification, package selection, per-class exceptions and contextual inspection | Full date/output forms and duplicate roster repair controls |
| Dates | Optional start/end dates, presets/defaults, validation and reset | Full class configuration |
| Output | Destination folder, browse/open, path validation and useful summary | Repeated package settings |
| Generate | Preflight review, blockers/warnings with direct fixes, generation/progress/cancel, completion and output verification | A second competing primary generation button |

Preflight should summarize affected classes, missing requirements, warnings, selected packages and expected outputs. Each issue should identify the affected file/class and give a direct correction route.

## 4. Why previous redesigns failed

The following failure patterns have appeared repeatedly. They are not acceptable final design choices.

- Repainting the old dashboard without changing its architecture.
- Showing schedule, roster intake, class packages, semester dates, output path and generation readiness all at once.
- Repeated cards and nested bordered containers around nearly every group.
- Equal visual weight for every region, so there is no obvious focal task.
- Navigation duplicated by a top stepper, numbered `STEP` labels on every card and a bottom action bar.
- Permanent inspector/sidebar consuming a large portion of the window and reducing table width.
- Tables clipped horizontally, especially the Grade package column, or made so dense that scanning is tiring.
- Tiny text, excessive uppercase micro-labels, cramped rows and compressed explanatory text.
- Repeating the same warning in a row, a banner and a global summary.
- Duplicate primary actions (e.g. `Initialize Workflow` shown both inside the workflow and again in a footer).
- Arbitrary two-column layout that places unrelated stages side by side.
- Treating “minimal” as “remove decoration but compress everything”.
- Treating “modern”, “Apple-inspired” or “professional” as visual-style keywords instead of applying interaction design methods.

A redesign is successful only if it changes how work is organized, how users recover from mistakes, and how batch and individual configuration coexist.

## 5. Visual evidence — included in this handover

The `assets/` directory contains the two screenshots the user supplied during the conversation. They are included so the next agent can inspect them without asking the user to upload images again.

### Screenshot A: `assets/antigravity-output-light-latest.png`

- Light-themed output, 792 × 546 pixels.
- Header includes CvSU Gen, version text, workspace, System/Light/Dark, Settings, Logs and Guides.
- Six horizontal workflow stages appear at the top.
- Main content is split into two columns.
- Left column stacks Instructor Schedule, Student Rosters and Detected Classes & Packages.
- Right column stacks Semester Date Boundaries, Target Output Destination and Workflow Readiness & Launch.
- Each major panel has its own border, heading, step badge and often a status badge.
- A bottom status strip repeats readiness and contains another `Initialize Workflow` button, while a generation button is already present inside the Step 6 panel.
- The class table continues below the visible area and is clipped by the viewport.
- Typography is small and compressed; content is packed into narrow panels. The six stages are presented as both top navigation and numbered panel labels.

**Assessment:** Cleaner than some previous dark outputs, but still a multi-step admin dashboard made of repeated cards. The full workflow is displayed simultaneously, creating competing priorities and unnecessary visual segmentation. The duplicated primary action is a clear defect.

### Screenshot B: `assets/antigravity-output-dark-previous.png`

- Dark-themed output, 1153 × 803 pixels.
- Header and six-stage strip at the top.
- Main canvas contains schedule summary, a three-row roster table, a pairing warning, class/package table and collapsed dates/output section.
- A fixed class inspector occupies the right side. It displays pairing, class details and individual package settings.
- The selected ITEC 85 / BSIT 3-B row has a green-tinted selection background.
- The class table's Grade column is partly clipped by the inspector/window width and horizontal scrolling is visible.
- The same roster mismatch is represented in the roster row, a warning banner and a bottom attention summary.
- A bottom action area and status strip compete with the main workspace.

**Assessment:** The inspector provides useful context, but permanently reserving this width harms the main table. The repeated warning and dense, heavily outlined composition make the screen tiring to scan.

These screenshots are **design-review outputs from Antigravity**, not proof of the current packaged application's exact appearance. Inspect the actual running application and source tree before making implementation claims.

## 6. Design methodology required

Do not start by choosing a palette or generating a dashboard.

Use this order:

1. **Task analysis:** map what instructors do for first-time setup and repeated semester processing.
2. **User journey:** identify transitions, decisions, interruptions, errors and recovery paths.
3. **Information architecture:** decide what belongs in each stage and what is merely summary/context.
4. **Cognitive walkthrough:** test whether a first-time instructor can identify the next action, understand a warning and recover.
5. **Batch interaction design:** define selection, bulk editing, mixed values, exceptions and confirmation behavior.
6. **Individual editing design:** define contextual inspection and editing without losing batch context.
7. **Visual hierarchy:** only then define typography, grouping, surfaces, density, spacing and color.
8. **Prototype and usability evaluation:** test realistic scenarios before touching production files.

Apply, where appropriate:

- Apple HIG principles: purpose, agency, responsibility, familiarity, flexibility, simplicity, craft and meaningful delight.
- Recognition rather than recall.
- Progressive disclosure.
- Direct manipulation.
- Immediate and truthful system feedback.
- Error prevention and recovery.
- User control and reversibility.
- Consistency and familiar desktop interaction patterns.
- Accessible keyboard interaction and focus order.
- Information hierarchy, proximity, alignment and readable density.

Apple HIG is an **interaction-design anchor**, not a request to imitate macOS chrome. Keep Windows conventions appropriate to PyWebView/WebView2. Check the current HIG and Windows guidance available at implementation time; do not rely on old screenshot trends or generic Dribbble dashboards.

Research reference supplied by the user:
- https://dev.to/a_shokn/how-to-break-the-ai-generated-ui-curse-your-guide-to-authentic-professional-design-2en

Useful primary/established references to inspect:
- Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
- Apple design principles: https://developer.apple.com/design/human-interface-guidelines/design-principles
- Apple designing for macOS: https://developer.apple.com/design/human-interface-guidelines/designing-for-macos
- Microsoft Windows app design: https://learn.microsoft.com/en-us/windows/apps/design/
- Nielsen Norman Group usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/

Do not claim a design follows a guideline merely because it uses a similar visual style. Explain the behavior or usability benefit.

## 7. Three design compositions to investigate

Create materially different compositions of the **same hybrid model**, not three color variations and not three unrelated products. For example:

1. **Focused stage canvas:** persistent compact stage navigation, one main task canvas, contextual details on demand.
2. **Batch-first workbench:** Packages opens to the full-width class matrix with a contextual inspector only on selection; other stages remain focused task screens.
3. **Master/detail adaptive workspace:** section list or batch matrix with a detail editor that appears only when needed and becomes an overlay at narrow widths.

Compare these on:
- First-use clarity.
- Efficiency for 10–20 sections.
- Ease of configuring exceptions.
- Number of unnecessary navigation/actions.
- Ability to see all important table columns at 880px.
- Error visibility and recovery.
- Accessibility and keyboard operation.
- Continuity when moving between stages.

Recommend one composition and justify it. Do not ask the user again whether they prefer a wizard, batch workflow or hybrid; that choice is settled.

## 8. Product constraints and engineering context

### Repository locations

Application repository:
- GitHub: https://github.com/DrinkBoooz/cvsu-generators
- Expected local folder: `C:\Users\danjo\OneDrive\CVSU GENERATORS`

Documentation repository (separate sibling repository):
- GitHub: https://github.com/DrinkBoooz/cvsu-generator_documentation
- Expected local folder: `C:\Users\danjo\OneDrive\cvsu-generator_documentation`

Do not merge or copy the documentation vault into the application repository. Do not edit the documentation repository unless separately requested.

### Runtime

- Windows 10/11.
- PyWebView with Microsoft Edge WebView2.
- Python backend.
- Vanilla HTML/CSS/JavaScript frontend.
- Native Windows file dialogs and OLE drag-and-drop bridge.
- Fully offline.

Do not introduce React, Vue, Next.js, Tailwind, Vite, external fonts, CDNs, remote assets, analytics or new frontend frameworks without explicit approval.

### UI source of truth (reported by prior repository investigation)

- Canonical UI entrypoint: `executable_test/ui.html`.
- Modular CSS: `executable_test/css/` (`tokens.css`, `base.css`, `layout.css`, `components.css`, `tables.css`, `modals.css`, `drawers.css`).
- Modular JS: `executable_test/js/` (`state.js`, `bridge.js`, `app.js`, `theme.js`, `stepper.js`, `step1.js`, `step2.js`, `step3.js`, `settings.js`, `templates.js`, `template_sets.js`, `workspaces.js`, `modal.js`, `drawers.js`, `toast.js`).
- PyWebView/build investigation previously identified `executable_test/` as the development/packaging source.
- Displayed application version was `Release v1.1.0` in `executable_test/ui.html`.

**These findings must be re-verified in the current checkout** before changing files. Do not assume the README is current; inspect `main.py`, resource resolution, PyInstaller specs and build scripts.

### Branch/governance

Prior Antigravity inspection reported that `AGENTS.md` requires active work, feature implementation and task commits to stay on `dev` / `origin/dev`; automatic merging to `main` is prohibited. Therefore:

- Read `AGENTS.md` first and obey it.
- Use `dev` if that rule remains in force.
- Do not create `ui/redesign` if it conflicts with governance.
- Inspect current branch and uncommitted changes before acting.
- Never discard or overwrite user changes.
- Do not push or merge.
- Never modify `AGENTS.md` or protected `.agents/` governance files.

### Frontend-only boundary

Do not modify `modules/`, generators, parsers, orchestrator, document-generation logic or Python backend behavior. Preserve the `window.pywebview.api` bridge contract. If a proposed UX improvement genuinely requires a backend change, stop and explain why before proceeding.

Known API methods to inspect/preserve include:
- `browse_schedule()`
- `browse_rosters()`
- `browse_output_dir()`
- `start_generation(options)`
- `cancel_generation()`
- `get_parser_config()`
- `save_parser_config()`
- `reset_parser_config()`
- `inspect_custom_template()`
- `save_custom_template()`
- `delete_custom_template()`

Also inspect workspace, save, log, guide and other bridge methods in the actual source.

### Existing features that must remain

- Workspace selector, save and workspace management.
- Schedule browsing/replacement and parsing.
- Multiple roster browsing, replacement and removal.
- Native OLE drag-and-drop.
- Auto-Strip Extra Columns.
- Class detection, selection and filters.
- Lecture/laboratory subject classification and manual overrides.
- Three output packages: CEIT, Attendance, Grades.
- Optional semester date boundaries, presets and Reset Dates.
- Output-directory browsing/opening.
- Generation readiness, progress telemetry and cancellation.
- Completion/output feedback.
- Parser settings, custom templates and live template inspection.
- Logs and Guides.
- Theme preferences and accessibility preferences.

Settings categories previously identified: Subject Prefixes, Lab Subjects, Degree Aliases, Column Keywords, Schedule Defaults and Custom Templates. However, existing tests also reference `cfgTabAccessibility` / `cfgPaneAccessibility`; investigate whether Accessibility is a separate tab/panel and preserve reduced-motion and transparency settings. Do not assume there are exactly six total panels without inspecting the markup.

## 9. Existing test locks and reported baseline

A prior Antigravity plan reported the following selectors/behavioral dependencies. Re-read the tests in the current checkout; this list is a starting point, not a substitute for the full inventory.

- `test_ui_consistency.py`: `workflowStepper`, `chipStep1`–`chipStep6`, `statusStep1`–`statusStep6`, `connector1to2`–`connector5to6`, `toastContainer`, `btnCancelGeneration`, version text, expected button labels and JS DOM ID coverage.
- `test_theme_consistency.py`: `color-scheme`, `data-theme="dark"`, calendar indicator behavior, `btnToggleTheme`, `themeIcon`, `themeLabel`, `updateThemeButtonState`, `SUN_ICON_SVG`, `MOON_ICON_SVG`.
- `test_stepper_2col_scroll.py`: `.step-chip.ready`, `.step-chip.ready .chip-num`, `.step-chip.active-step .chip-num`, `.glass-card.card-spotlight`, `STEP_CARD_IDS`, `STEP_CHIP_IDS`, `setActiveStepChip`, `_scrollSpyLockedUntil`.
- `test_scroll_aware_dock.py`: `#bottomActionBar`, `.dock-hidden`, `#cardStep6`.
- `test_accessibility_settings.py`: `modalParserSettingsBackdrop`, `cfgTabAccessibility`, `cfgPaneAccessibility`, `accSelectMotion`, `accSelectTransparency`, `cvsu_acc_motion`, `cvsu_acc_transparency`.
- `test_playwright_settings_modal.py`: settings modal/tab selectors including prefixes, lab, degrees, keywords, schedule and custom templates.
- `test_pywebview_dnd_binding.py`: `window.onScheduleLoaded`, `window.onRostersLoaded`.

Do not preserve a glassmorphism *appearance* just because an old test references `.glass-card`. If needed, retain a harmless compatibility class or update the selector while preserving the behavior/assertion.

### Prior-reported baseline (must be rerun)

A prior plan reported:
- 79 passing tests across a grouped D1 UI bridge/consistency/accessibility/theme/settings set.
- `test_stepper_2col_scroll.py`: 3 passed.
- `test_scroll_aware_dock.py`: 1 passed.
- `test_dnd_flow.py`: 2 passed.
- `test_theme_transition_perf.py`: 2 passed.
- `test_responsive_ui.py`: 9 passed.
- Several Playwright E2E/settings/accessibility tests passed.

Reported pre-existing issues:
1. `test_playwright_roster_mapping.py::test_playwright_roster_mapping_modal_and_ceit_help` failed because `.btn-map-columns` matched two elements (strict-mode ambiguity).
2. `scripts/test_orchestrator.py --fast` reported four Layer A2 failures because `tests/test_antivirus_hardening.py` was not classified by `test_dependency_manifests.py`.
3. Some native PyWebView GUI tests require an interactive desktop/message pump and must use the repository's supported orchestrator or isolated runner.

These are **reported historical baseline results**, not verified current results. Run tests before implementation and distinguish old failures from regressions. Never weaken/delete assertions to make a redesign pass.

Required additional tests for the redesign:
- System/Light/Dark theme selection, persistence, runtime OS preference changes where supported.
- Accessible disabled-generation reason that updates as requirements are met.
- Stepper keyboard navigation, activation, visible focus and current-step announcement.
- Batch selection and bulk changes preserving individual exceptions, if that behavior is implemented in the frontend state.

## 10. Visual design guardrails

The exact final aesthetic should emerge from the selected workflow architecture. Avoid prescribing a theme as a substitute for design.

Guidance:
- Use a native Windows system font stack (e.g. Segoe UI Variable / Segoe UI); reserve monospace for paths and logs.
- Comfortable, readable typography. Avoid tiny metadata and excessive uppercase labels.
- Establish a hierarchy through type, spacing, alignment and grouping—not repeated cards.
- Use tables when they support real comparison and batch work; make column widths/responsiveness deliberate.
- Do not shrink content merely to fit every stage into one viewport.
- Avoid permanent sidebars/inspectors unless user-opened and demonstrably useful.
- Avoid duplicate warnings and duplicate primary actions.
- Keep a restrained CvSU-inspired green accent; sample actual repository logo/seal assets if available. Any unsourced color values are approximations, not official brand specifications. Gold is secondary and sparing.
- Light and dark themes must each be designed intentionally.
- Avoid glass, decorative gradients, colored glows, neon, excessive pills, decorative dots, unnecessary shadows, emoji and generic dashboard ornament.
- Preserve semantic status colors and never rely on color alone.
- Measure contrast; distinguish subtle decorative dividers from functional control boundaries.
- Do not treat the previous 8px radius suggestion as the main design objective. Geometry is secondary to usability and hierarchy.

## 11. Required next-agent process

### Phase 1 — Re-investigate and document

1. Read `AGENTS.md` and protected project instructions.
2. Check branch/status/uncommitted changes; follow `dev` governance.
3. Verify the live and packaged UI entrypoints.
4. Inspect all HTML/CSS/JS and bridge behavior.
5. Read all relevant UI tests, including roster mapping, accessibility, native drag-and-drop, responsive behavior and theme performance.
6. Rerun baseline tests and capture current screenshots from the actual app.
7. Map the task flow and user-visible application states.
8. Produce a clear audit explaining why the prior designs failed.

### Phase 2 — Architecture and design exploration

1. Produce a task model and journey map for first-time and repeat users.
2. Define the Hybrid Guided Batch Workbench information architecture.
3. Create three materially different compositions of this same model (not mere color variations).
4. Evaluate them against the scenarios in Section 12.
5. Recommend one composition with explicit trade-offs.
6. Produce low-fidelity wireframes before high-fidelity styling.
7. Produce high-fidelity light and dark mockups plus working, offline prototypes.
8. Include the Packages batch workspace, selected-class inspector, roster mismatch repair, preflight and generation.
9. Test 1120×780 and 880×640; do not clip essential information.
10. Present results and STOP for explicit user approval.

### Phase 3 — Controlled implementation (approval required)

Only after the user explicitly approves the chosen design:
- Implement against the verified canonical frontend.
- Preserve bridge contracts, existing state semantics, native file flows, workspaces and all existing features.
- Keep CSS modular and remove obsolete conflicts rather than appending endless overrides.
- Preserve DOM IDs/classes where practical; update tests only when a deliberate structural change requires it, without weakening behavior assertions.
- Run the full applicable test suite and visual regression checks.
- Update the separate documentation repository only if the user separately authorizes it.
- Do not bump application version, push or merge without authorization.

## 12. Required usability scenarios

Evaluate every concept and prototype with these scenarios:

A. **First-use intake:** A new instructor imports a schedule, understands the parsing result, adds rosters and knows what to do next.

B. **Roster mismatch:** Four roster files are imported; one filename or section identity conflicts with the schedule. The user can identify the exact mismatch, correct it in Rosters and return without losing work.

C. **Batch configuration:** The instructor configures 10–20 sections. They can select many classes and apply package choices efficiently.

D. **Individual exception:** One section needs a different package configuration. The user can edit it individually without unintentionally overwriting other sections.

E. **Repeat workflow:** The instructor opens an existing workspace, changes one roster/class and reruns generation without repeating unrelated work.

F. **Preflight issue:** A required roster or output prerequisite is missing. The user sees one authoritative issue, understands which section/file is affected and can navigate directly to the fix.

G. **Generation:** The user sees truthful progress, can cancel where supported, and can verify the resulting output files.

## 13. Acceptance criteria

A successful design must demonstrate all of the following:

- It is structurally and visually distinct from both attached failed screenshots.
- It supports batch management and individual configuration together.
- Bulk changes do not silently overwrite individual exceptions.
- No permanent inspector consumes workspace width by default.
- The Packages stage gives the class matrix enough room to be readable.
- Essential information and actions remain usable at 880px width.
- Roster repair happens in the Rosters context; summaries elsewhere are concise and non-duplicative.
- Warnings appear once authoritatively with direct corrective actions.
- There is one clear primary action per context, not duplicated buttons.
- First-time users understand the next step; experienced users can work efficiently.
- Light and dark themes are both accessible and intentional.
- The design follows HCI principles through actual behaviors, not merely a visual resemblance to Apple apps.
- Existing application functionality and backend contracts remain intact.
- Production implementation does not begin before explicit approval.

## 14. What the next agent should report

Provide:

1. Verified source-of-truth and branch status.
2. UX audit of the actual application and previous failed designs.
3. Task model and user journey.
4. Hybrid information architecture.
5. Three composition options and comparison.
6. Recommended design and rationale.
7. Wireframes and high-fidelity mockups.
8. Interactive prototypes.
9. Accessibility/contrast results and viewport evidence.
10. Risks, unknowns and questions that genuinely require user input.

Do not ask the user to repeat the settled decisions: **Hybrid workflow, balanced priority, Apple-HIG-informed HCI, Windows desktop conventions, and rejection of the previous dashboard-like outputs.**

---

## Final instruction

Do not try to make the old dashboard look more fashionable. Redesign the way the instructor's work is organized and supported.

**The goal is a human-centred academic document-production workbench: clear for a first-time instructor, efficient for a faculty member handling many sections, and calm enough to use repeatedly throughout every semester.**
