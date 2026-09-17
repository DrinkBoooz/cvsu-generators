# Implementation Plan: Comprehensive Accessibility & WCAG 2.1 AA Hardening

## Task Type
- [x] Frontend (→ Antigravity)
- [ ] Backend (→ Codex)
- [ ] Fullstack (→ Parallel)

---

## Executive Summary
This implementation plan outlines the full accessibility pass for the **CvSU Document Generator** desktop application to meet and exceed **WCAG 2.1 AA**, **Microsoft Windows Accessibility Guidelines**, and **Section 508** standards.

While basic `tabindex="0"` was previously added to file drop zones, a production-grade accessibility implementation requires:
1. **Keyboard-complete navigation**: 100% of interactive controls reachable and operable via keyboard alone.
2. **Logical Tab sequencing**: Natural, predictable progression across the 6-step ingestion-to-generation workflow.
3. **High-visibility focus rings**: Distinct, non-overlapping `:focus-visible` styling with zero suppressed outlines.
4. **Modal focus traps and focus return**: Trapping Tab within active dialogs/drawers and restoring focus to the exact triggering element upon dismissal.
5. **Escape key dismissal**: Stack-aware Escape dismissal across confirmation sheets, settings modals, mapping dialogs, and slide-over drawers.
6. **ARIA live announcements**: Screen reader announcements for toast notifications, dynamic status changes, and generation progress updates.
7. **Accessible table semantics**: Explicit `<th scope="col">` and `<th scope="row">` headers, table labels, and non-color data indicators.
8. **Windows High-Contrast / Forced-Colors mode**: Dedicated `@media (forced-colors: active)` rules providing high-contrast borders, focus rings, and selection indicators.
9. **High-DPI scaling robustness**: Resilient layouts at 125%, 150%, and 200% Windows scaling without text clipping or unreachable buttons.
10. **Automated CI accessibility regression suite**: Permanent automated pytest suite in `tests/test_ui_accessibility.py` ensuring zero accessibility regressions.

---

## User Review Required

> [!IMPORTANT]
> **Keyboard Interaction Standard**: In accordance with Microsoft HIG, all custom buttons and dropzones will respond to both <kbd>Enter</kbd> and <kbd>Space</kbd>, while modals will capture and cycle <kbd>Tab</kbd> / <kbd>Shift</kbd>+<kbd>Tab</kbd> until explicitly dismissed with <kbd>Esc</kbd> or close actions.

> [!NOTE]
> **Version Synchronization**: As required by project rules in `AGENTS.md`, this major UX/accessibility milestone will bump the application release version from `Release v1.0.0` to `Release v1.0.1`, synchronized across `executable_test/ui.html`, `executable_test/file_version_info.txt`, `executable_test/README.md`, and `tests/test_ui_consistency.py`.

---

## Proposed Changes

### Component 1: Design System & Styling (`executable_test/css/`)

Eliminate all outline suppression (`outline: none`) without focus indicators, add visible Apple HIG / Fluent focus rings, and implement complete Windows High Contrast Mode support.

#### [MODIFY] `executable_test/css/tokens.css`
- Add accessibility tokens for high-contrast focus rings:
  - `--a11y-focus-ring-color: var(--accent-emerald)`
  - `--a11y-focus-ring-offset: 2px`
  - `--a11y-focus-ring-width: 2px`
  - `--a11y-focus-glow: 0 0 0 4px var(--accent-emerald-glow)`

#### [MODIFY] `executable_test/css/base.css`
- Upgrade `:focus-visible` to support dual-layer high-visibility focus indicators across all interactive tags (`button`, `a`, `input`, `select`, `textarea`, `[tabindex="0"]`, `.dropzone`, `.step-chip`).
- Add standard `.sr-only` (visually hidden but screen-reader accessible) utility class for assistive technology announcements.
- Add comprehensive `@media (forced-colors: active)` block:
  - Enforce `outline: 3px solid Highlight !important; outline-offset: 3px !important;` on `:focus-visible`.
  - Enforce `border: 1px solid ButtonBorder` or `CanvasText` on cards, dialogs, drawers, badges, and buttons.
  - Enforce `border: 2px dashed CanvasText` on dropzones.
  - Enforce `background: Highlight !important; color: HighlightText !important;` on active tabs, active chips, and selected filter pills.

#### [MODIFY] `executable_test/css/components.css`
- Replace bare `outline: none;` on `.segmented-btn` and `.filter-pill` with explicit `:focus-visible` styling.
- Add visible focus indicators for `.btn-primary-action`, `.btn-browse`, `.btn-cancel-gen`, and `.dropzone`.
- Ensure flex wrapping and minimum touch target sizes (&ge; 32px height) for controls at 150% and 200% Windows display scaling.

#### [MODIFY] `executable_test/css/drawers.css`
- Remove `outline: none;` from `.step-chip` and `.drawer-tab`.
- Add explicit `:focus-visible` ring on `.step-chip:focus-visible` and `.drawer-tab:focus-visible`.
- Ensure drawer panels maintain `overflow-y: auto;` with proper padding so close buttons and tab bars remain accessible when zoomed.

#### [MODIFY] `executable_test/css/modals.css`
- Remove bare `outline: none;` from `.roster-class-link-select`, `.form-select-custom`, and `.form-control-custom`.
- Add distinct `:focus-visible` border and focus-ring states for all modal controls.
- Provide forced-colors high contrast borders for modal header, footer, and dialog container.

#### [MODIFY] `executable_test/css/tables.css`
- Replace bare `outline: none;` on `.type-dropdown`, `.text-input`, and `.date-input` with `:focus-visible` rules.
- Add accessible table styling for `.spreadsheet-preview-table` headers (`th[scope="col"]`, `th[scope="row"]`).

---

### Component 2: HTML Semantic Landmarks & ARIA Roles (`executable_test/ui.html`)

Upgrade document semantics and ARIA attributes for Windows Narrator and Accessibility Insights.

#### [MODIFY] `executable_test/ui.html`
- Bump version badge in header: `<span class="badge-version">Release v1.0.1</span>`.
- Add `<main id="mainContent" class="app-container" role="main">` landmark wrapping the dashboard grid.
- Add `<nav aria-label="Top Actions" class="header-actions">` for header controls.
- Add `<nav aria-label="Workflow Steps" class="stepper-bar" id="workflowStepper">` for the 6-step stepper.
- Update Stepper chips (`#chipStep1` ... `#chipStep6`):
  - Add dynamic `aria-label="Step 1: Schedule - Incomplete"` (updated via JS).
  - Add `aria-hidden="true"` to status emoji badges (`#statusStep1` ... `#statusStep6`).
- Update Dropzones:
  - Ensure `#templateDropzone` in Custom Forms settings has `tabindex="0"`, `role="button"`, `aria-label="Upload custom document template (.docx)"`, and keyboard `onkeydown` handler.
  - Ensure `#scheduleDropzone` and `#rostersDropzone` have explicit `aria-label`.
- Update Input fields:
  - Add `aria-label` to `#outputDisplay`, `#rosterSearchInput`, `#helpSearchInput`, `#cfgSearchPrefix`, etc.
  - Link labels and inputs via `for` / `id` attributes.
- Update Progress bar:
  - Add `role="progressbar"`, `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-valuenow="0"`, `aria-valuetext="0% - Not started"` to `#progressContainer` / `#progressFill`.
- Update Live announcements:
  - Add `<div id="a11yLiveAnnouncer" class="sr-only" aria-live="polite" aria-atomic="true"></div>` for screen-reader vocalization of workflow milestones.
  - Add `aria-live="polite"` and `aria-atomic="true"` to `#toastContainer`.
- Update Tables:
  - Add `<th scope="col">` to `#ceitPrefixTable` and settings data tables.
  - Add `aria-label` to all data tables.
- Update Modals:
  - Ensure `#modalRosterMappingBackdrop`, `#modalParserSettingsBackdrop`, and `#modalAppleConfirmBackdrop` have complete `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, and `aria-describedby`.
  - Add `aria-label="Close dialog"` to all modal close `&times;` buttons.

---

### Component 3: Focus Management & Keyboard Engine (`executable_test/js/`)

Implement focus trapping, focus restoration, and live region announcer utilities.

#### [MODIFY] `executable_test/js/modal.js`
- Implement universal `FocusTrapManager`:
  ```javascript
  const FocusTrapManager = {
    activeTrap: null,
    triggerElement: null,
    trap(container, initialFocusEl) { ... },
    release() { ... }
  };
  ```
- In `showAppleConfirm()`:
  - Capture triggering element before showing modal.
  - Trap Tab within confirm dialog.
  - Restore focus upon dismissal.

#### [MODIFY] `executable_test/js/settings.js`
- In `openSettingsModal()`:
  - Capture triggering element (`#btnOpenSettings`).
  - Activate focus trap inside `#modalParserSettingsBackdrop`.
  - Focus initial tab or first interactive element.
- In `closeSettingsModal()`:
  - Release focus trap.
  - Restore focus back to `#btnOpenSettings`.

#### [MODIFY] `executable_test/js/step2.js`
- In `openColumnMappingModal(fileKey)`:
  - Capture the specific "Map" button that was clicked.
  - Activate focus trap inside `#modalRosterMappingBackdrop`.
- In `closeColumnMappingModal()`:
  - Release focus trap.
  - Restore focus back to the triggering "Map" button.
- In `renderSpreadsheetGrid()`:
  - Render `th[scope="col"]` for columns.
  - Render `th[scope="row"]` for row numbers.
  - Render non-color textual tags: `(Name)`, `(ID)`, and `[H]`.
  - Add `aria-label="Raw Spreadsheet Preview Grid"`.

#### [MODIFY] `executable_test/js/drawers.js`
- In `openHelpDrawer()` / `openLogsDrawer()`:
  - Capture triggering button (`#btnOpenHelp` / `#btnOpenLogs`).
  - Activate focus trap on the active drawer panel.
  - Focus the drawer close button or search box.
- In `closeAllDrawers()`:
  - Release focus trap.
  - Restore focus back to `#btnOpenHelp` or `#btnOpenLogs`.

#### [MODIFY] `executable_test/js/bridge.js`
- Enhance global keydown handler:
  - Keep Tab cycling bounded inside active modal/drawer.
  - Ensure Escape key triggers appropriate dismissal and focus restoration.
- Provide global announcer function:
  ```javascript
  function announceA11y(message) {
    const el = document.getElementById("a11yLiveAnnouncer");
    if (el) { el.textContent = ""; setTimeout(() => { el.textContent = message; }, 50); }
  }
  ```

#### [MODIFY] `executable_test/js/stepper.js`
- When updating step readiness chips, dynamically update `aria-label`:
  `chip.setAttribute("aria-label", `Step ${stepNum}: ${name} - ${statusText}`);`
- Announce step transitions via `announceA11y`.

#### [MODIFY] `executable_test/js/toast.js`
- Add `role="status"` (or `role="alert"` for error toasts).
- Add `aria-label="Close notification"` to `.toast-close` buttons.

---

### Component 4: Versioning, PE Metadata & Packaging

Keep all release metadata synchronized per `AGENTS.md`.

#### [MODIFY] `executable_test/file_version_info.txt`
- Bump `filevers=(1, 0, 1, 0)` and `prodvers=(1, 0, 1, 0)`.
- Bump `FileVersion`, `ProductVersion` to `"1.0.1.0"`.

#### [MODIFY] `executable_test/README.md`
- Update version reference to `Release v1.0.1`.
- Add accessibility changelog item: "WCAG 2.1 AA & Microsoft Windows Accessibility compliance pass (complete keyboard navigation, focus trapping, high contrast forced-colors, ARIA landmarks & live regions)."

---

### Component 5: Automated Testing & Verification Suite (`tests/`)

#### [NEW] `tests/test_ui_accessibility.py`
Automated accessibility regression test suite covering:
1. **Interactive Element Labels**: Every button, input, select, textarea, and custom control has an accessible name (`aria-label`, visible text, or associated `<label>`).
2. **Dropzone Keyboard Accessibility**: All dropzones have `tabindex="0"`, `role="button"`, `aria-label`, and Enter/Space handlers.
3. **Modal & Drawer Semantics**: All modals and drawers have valid roles (`role="dialog"`), `aria-modal="true"`, and `aria-labelledby`.
4. **Table Semantics**: All data tables have `th[scope="col"]` and accessible titles/captions.
5. **Focus Trap & Focus Return**: Verifies `FocusTrapManager` registration and focus return hooks in JS modules.
6. **High Contrast CSS**: Verifies presence of `@media (forced-colors: active)` block and styles for `:focus-visible`, cards, buttons, dropzones.
7. **Zero Suppressed Outlines**: Asserts that no element sets `outline: none` without a corresponding `:focus-visible` rule.
8. **ARIA Live Regions**: Verifies presence of `aria-live="polite"` announcer and toast container.
9. **Landmarks**: Verifies `<main>`, `<header>`, and `<nav>` landmarks exist in `ui.html`.

#### [MODIFY] `tests/test_ui_consistency.py`
- Update version assertion from `Release v1.0.0` to `Release v1.0.1`.

#### [MODIFY] `tests/test_pe_version_info.py`
- Ensure version tests match `1.0.1.0`.

---

## Verification Plan

### Automated Tests
Execute full test suite via `uv run pytest`:
```powershell
uv run pytest tests/test_ui_accessibility.py -v
uv run pytest tests/test_ui_consistency.py -v
uv run pytest tests/test_pe_version_info.py -v
uv run pytest tests/ -k "not test_playwright"
```
**Success Criteria**: 100% tests pass (185+ passing tests) with 0 failures or regressions.

### Manual & Assistive Technology Verification
1. **Keyboard-Only Traversal (<kbd>Tab</kbd>, <kbd>Shift</kbd>+<kbd>Tab</kbd>, <kbd>Enter</kbd>, <kbd>Space</kbd>, <kbd>Esc</kbd>)**:
   - Tab through the full UI from Header -> Stepper -> Step 1 -> Step 2 -> Step 3 -> Step 4 -> Step 5 -> Step 6.
   - Verify visible 2px emerald focus ring on every focused control.
   - Activate dropzones with <kbd>Enter</kbd> and <kbd>Space</kbd>.
   - Open Settings (<kbd>Enter</kbd> on Settings) -> Verify focus trapped inside modal -> Press <kbd>Tab</kbd> continuously (stays inside modal) -> Press <kbd>Esc</kbd> -> Verify focus immediately returns to Settings button.
   - Open Help Drawer -> Verify focus trapped -> Press <kbd>Esc</kbd> -> Verify focus returns to Guides button.
   - Open Roster Mapping -> Verify focus trapped -> Press <kbd>Esc</kbd> -> Verify focus returns to triggering Map button.
2. **Windows High-Contrast / Forced-Colors Mode**:
   - Verify in Windows Settings -> Accessibility -> Contrast themes (Aquatic / Desert / Dusk / Night Sky).
   - Verify cards, buttons, focus rings (`Highlight`), and dropzones render clear, distinct high-contrast boundaries.
3. **Display Scaling (125%, 150%, 200%)**:
   - Zoom WebView2 / browser to 150% and 200%.
   - Verify modal dialogs scroll cleanly without clipping buttons or text.
4. **Windows Narrator / NVDA Announcement**:
   - Verify landmarks are announced: "banner", "main", "Workflow Steps navigation".
   - Verify toasts and progress updates are vocalized cleanly via `aria-live`.

---

### SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: accessibility-audit-codex
- ANTIGRAVITY_SESSION: accessibility-audit-antigravity
