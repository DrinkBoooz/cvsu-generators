# CvSU Gen — Design Constitution

**Status:** Proposed design contract for review; not yet approved for production implementation  
**Prepared:** 4 November 2026  
**Product:** CvSU Gen — offline Windows desktop academic document-production utility  
**Primary design authority:** Apple Human Interface Guidelines (HIG)  
**Platform adaptation:** Windows 10/11 + PyWebView + Microsoft Edge WebView2

> Design CvSU Gen as a dependable academic workbench. It should feel like a carefully considered Windows application whose interaction quality is guided by Apple HIG—not like a web dashboard wearing a desktop window, and not like a macOS imitation.

## 1. Authority and precedence

Apply guidance in this order. A lower item cannot override a higher one.

1. **User and product requirements.** Correct academic output, preservation of user work, offline operation, current repository governance, the approved Hybrid Guided Batch Workbench, and the existing backend bridge are non-negotiable.
2. **Accessibility, safety, data integrity, and factual feedback.** Aesthetic rules never justify low contrast, hidden focus, ambiguous status, lost work, or false progress.
3. **Apple HIG — primary design philosophy.** Use its principles to judge purpose, agency, responsibility, familiarity, flexibility, simplicity, craft, and delight. Use HIG guidance on hierarchy, progressive disclosure, feedback, color meaning, and recovery.
4. **Windows conventions — platform fit.** Use familiar Windows window behavior, keyboard behavior, system fonts, native file dialogs, high-contrast behavior, and desktop input conventions. This is an adaptation layer, not a competing design philosophy.
5. **Anti-generic design references.** Use `avoid-ai-design`, `no-slop-ui`, and the supplied `frontend-design` skill as audit and craft references. Their rules are heuristics, not universal laws. Apply them only when they improve this product and do not conflict with items 1–4.

### Core rule

**Apple HIG decides whether the experience is humane and understandable. Windows conventions decide whether it belongs on Windows. The anti-slop references help identify unchosen defaults. The CvSU Gen task model decides the actual layout.**

Do not copy macOS window chrome, traffic-light controls, Liquid Glass, or Apple-only components. Do not copy a generic Windows Fluent sample wholesale either. Translate HIG principles into the product's faculty workflows.

## 2. Product identity and audience

CvSU Gen serves faculty members producing academic documents from instructor schedules and student section rosters. Typical use includes about 10–20 class sections and up to around 40 students per section.

The work is consequential: an incorrect section pairing or package configuration can create incorrect attendance sheets, CEIT forms, or grade sheets. The interface must favor:

- accuracy over visual novelty;
- clear state over decorative status;
- recoverable actions over rigid step enforcement;
- batch efficiency without hiding individual exceptions;
- useful density without tiny text or clipping;
- calm, predictable use across repeated semesters.

This is an **offline Windows productivity utility**, not a consumer SaaS product, analytics dashboard, marketing site, or portfolio piece.

## 3. Apple HIG principles translated into CvSU Gen

Use the current HIG principles as decision criteria. The labels below are not decorative section tags; each has a product behavior attached to it.

### Purpose — make the task the visual center

- Every stage must answer: what is the instructor here to do?
- Put the working content first. The Packages stage is the central batch workspace, not a KPI dashboard.
- Show counts only when they help a decision, such as `14 sections selected` or `2 sections need attention`.
- Do not invent metrics, charts, activity feeds, or “productivity” summaries.

### Agency — preserve choice and control

- Keep the six stages directly revisitable; do not trap users in a rigid wizard.
- Let users move backward and forward without discarding valid work.
- Make bulk scope explicit before applying a change.
- Preserve per-section exceptions unless the instructor explicitly chooses to replace them.
- Provide undo or a clear restore path for reversible configuration changes where feasible.

### Responsibility — communicate consequences honestly

- Tell users what a command will change before a high-impact or destructive operation.
- Clearly distinguish a warning from a blocker and a completed action from an in-progress action.
- Never report generation success before the backend confirms completion.
- Identify the affected section/file and provide a direct route to fix it.
- Do not silently infer that a roster is correct from its filename alone.

### Familiarity — use recognizable desktop patterns

- Use clear page titles, labelled controls, ordinary tables, menus, dialogs, and file pickers.
- Keep action names stable throughout a flow. `Replace roster` should not become `Upload` in the confirmation message.
- Use familiar Windows keyboard focus, selection, and native file-dialog behavior.
- Use a consistent appearance for the same action and status throughout the application.

### Flexibility — support different ways of working

- Support first-time guided intake and fast repeat-semester workflows.
- Support keyboard and pointer operation.
- Allow batch configuration and individual exceptions to coexist.
- Adapt between 1120×780 and 880×640 without hiding essential information or forcing a permanent inspector.
- Respect theme, contrast, text scaling, and reduced-motion preferences.

### Simplicity — remove competing priorities, not useful capability

- One obvious primary action per stage.
- One authoritative location for each warning.
- Show details when they are relevant; do not repeat every stage's content on every screen.
- Group related controls by task, alignment, and spacing before adding a border or card.
- Simplicity is not a requirement to make everything small or empty.

### Craft — make every state deliberate

- Design success, error, empty, loading, disabled, selected, mixed, and partial states—not only the happy path.
- Check real-length filenames, long course names, 20-section datasets, and 40-student counts.
- Use a coherent type scale, spacing rhythm, and palette across every stage and theme.
- Review rendered screenshots rather than judging CSS alone.

### Delight — make reliability feel satisfying

- Use clear, calm completion feedback and useful output verification.
- Let the application feel responsive through immediate feedback to a user's action.
- Avoid decorative motion, gamification, confetti, or celebratory effects that distract from academic work.

## 4. Information architecture and interaction contract

Keep the six established contexts:

1. **Schedule** — import/replace the instructor schedule; show parse result, instructor, semester, detected classes, and actionable parse errors.
2. **Rosters** — add/replace/remove roster files; show pairing, student count, column validation, and fix ambiguous or incorrect matches here.
3. **Packages** — primary batch workbench; class matrix, multi-selection, filters, bulk changes, mixed values, and per-class exceptions.
4. **Dates** — optional semester start/end dates, presets, validation, and reset.
5. **Output** — destination folder, browse/open, path validation, and concise summary.
6. **Generate** — preflight, blockers/warnings with direct fixes, progress, cancellation, completion, and output verification.

These are **six navigable work contexts**, not six forms stacked on one dashboard. Completed stages remain revisitable. A completed stage must not be duplicated as a full panel elsewhere.

### Packages: batch-first workbench

- The class matrix owns the available width by default.
- Include the actual decision columns: section, subject type, CEIT package, Attendance package, Grades package, and readiness/exception state as supported by the real data model.
- Use row selection and multi-selection with clear selected counts; provide select all and clear selection.
- When selected classes differ, show `Mixed` or an equivalent explicit mixed state. Never silently choose one class's value as the batch value.
- A batch edit must state the scope, e.g. `Apply Attendance settings to 8 selected sections`.
- By default, preserve section-level overrides. If the user chooses to overwrite them, identify how many exceptions will be replaced and require an explicit confirmation.
- Selecting one section opens a contextual inspector only when requested. Closing it returns to the same table position and selection state.
- At narrow widths, the inspector becomes an overlay/drawer or inline editor. It must not permanently consume table width.
- The distinctive CvSU Gen interaction should be the **exception-aware batch action**: make it immediately clear which sections will change and which customized sections will remain untouched.

### Rosters: one authoritative repair path

- Show each detected class once, its matched roster once, student count, and validation result.
- An incorrect or ambiguous pairing links directly to the repair interaction in Rosters.
- Do not echo the same roster warning in the row, a global banner, and a bottom summary.
- Preserve the original file identity and make the selected pairing explicit before saving a correction.

### Generate: preflight as a repair surface

- Preflight must identify the exact blocker/warning, affected file or section, consequence, and direct correction route.
- Avoid a second competing Generate button. Keep one primary launch action in the Generate context.
- Progress must reflect backend telemetry. Cancellation must be offered only when supported.
- Completion must verify generated outputs rather than showing an unsupported success state.

## 5. Visual design language

### 5.1 Typography

- **Primary family:** `Segoe UI Variable`, with `Segoe UI` and the platform sans-serif fallback as fallbacks.
- This is an intentional platform choice, not an unstyled AI default: Microsoft identifies Segoe UI Variable as the Windows system font and documents its small-size legibility and type ramp.
- Use one family for the application interface. Establish distinction through size, weight, and spacing instead of adding a fashionable display face.
- Use regular for body text and semibold for headings and important controls.
- Prefer sentence case. Do not use tracked uppercase labels as decoration.
- Align interface text left by default. Center only where the content's meaning benefits from it, such as a compact empty state.
- Starting scale (CSS px; tune after real-device rendering): 12/16 for secondary metadata only; 14/20 body; 14/20 semibold controls; 16/24 emphasized body; 18/26 section headings; 22/30 stage title; 28/36 app/workspace title where needed.
- Do not use tiny text to squeeze content into a fixed viewport. Reflow, disclose, or allow vertical scrolling instead.
- Reserve monospace for file paths, logs, code-like identifiers, and genuinely tabular technical values—not decorative micro-labels.

### 5.2 Color and semantic roles

Color is a communication system. Each token must have one role. Do not make the same hue mean an interactive control in one place and an inert label in another.

- Use a restrained CvSU-inspired green as the primary action/selection accent, subject to verification against the actual logo and existing repository assets.
- Gold may appear sparingly for a secondary institutional accent if confirmed by the source artwork.
- Use neutral surfaces and strong readable text; avoid grey-on-grey microcopy.
- Status colors must be paired with text or a meaningful symbol. Never encode readiness, failure, or selection with color alone.
- Define light and dark tokens by semantic role, not by copying a single hue and inverting it.
- The sample hex values in `cvsu-gen-ui-tokens.css` are **provisional working values**, not official Cavite State University brand specifications. Sample the current logo/seal and verify with the project owner before production use.
- No palette is inherently anti-AI. Do not use purple gradients, cream/terracotta, or black/neon as reflexive directions; equally, do not use green just because CvSU is involved. Ground the actual accent in the verified brand asset and assign it a functional role.

### 5.3 Surface, borders, and geometry

- Prefer a clear canvas with solid content surfaces.
- Use spacing, alignment, and grouping first; add a border only when it clarifies a real boundary or control.
- Avoid nested cards. A card is justified only when content is independently actionable, repeated as a collection item, or needs a distinct temporary surface.
- No glassmorphism, blur panels, gradient borders, colored glows, decorative blobs, or floating-card drama.
- Use subtle separators for data rows and clear boundaries for inputs and command areas.
- Use a restrained, role-specific radius: controls may be slightly rounded; tables and large work surfaces need not be wrapped in rounded cards. Do not apply one radius to every object.
- Shadows communicate actual elevation (e.g. menu, dialog, temporary inspector), not decoration.

### 5.4 Layout and spacing

- Use a consistent spacing scale based on 4/8/12/16/24/32 px.
- Maintain a stable header and compact stage navigation; do not duplicate the six-stage navigation with numbered labels on every panel.
- Use a focused stage title and one short explanatory sentence where it helps orientation.
- Put the working task first; keep settings and secondary actions close to the content they modify.
- Use tables for comparing multiple sections. The matrix should remain readable at 880 px; essential package state must not disappear behind clipped columns.
- Prefer left alignment and consistent column anchors. Use column widths according to content and scanning needs, not equal widths by default.
- Avoid arbitrary two-column compositions that place unrelated stages side by side.
- Use progressive disclosure for details, but visibly indicate that more information or actions are available.

### 5.5 Icons and imagery

- Use icons only where they speed recognition or distinguish a state/action.
- Prefer a consistent line weight and size. Avoid icon-in-a-rounded-square as default decoration.
- Do not use emoji as status markers or UI ornament.
- Do not use abstract AI-generated blobs or stock imagery to fill empty space. This product is a working utility; its real data and document artifacts are the meaningful visual content.

## 6. Motion and feedback

- Motion must explain a user-triggered change: opening an inspector, expanding details, acknowledging a saved change, or showing generation progress.
- Keep transitions restrained and brief; opacity or small positional movement only when it improves orientation.
- No repeated fade-up entrance on every panel, parallax, spring/bounce, hover scaling, shimmer, or count-up metrics.
- Respect `prefers-reduced-motion` and the application's saved reduced-motion setting.
- Do not animate static dashboard regions merely to make the interface feel alive.
- Every action needs immediate, truthful feedback. Keep loading indicators from changing the dimensions or position of surrounding controls.

## 7. Writing and microcopy

- Write from the instructor's point of view using familiar academic and file-management terms.
- Use simple, direct, active labels: `Replace schedule`, `Add roster`, `Remove roster`, `Apply to selected sections`, `Save dates`, `Choose output folder`, `Start generation`.
- Buttons describe their result; avoid `Submit`, `Proceed`, `Initialize`, or abstract calls to action when a direct verb is possible.
- Keep labels consistent: the name of an action stays the same in the button, confirmation, status message, and log entry.
- An error states what failed, what is affected, and how to fix it. Avoid vague `Something went wrong` messages.
- Empty states give the next useful action. They are not blank decoration.
- Remove phrases such as `command center`, `operational clarity`, `seamless workflow`, `unlock productivity`, `next-generation`, or other promotional filler unless they are actual product terminology.
- Avoid unnecessary eyebrow labels, middle-dot metadata chains, automatic arrows appended to every link/button, and decorative numeric labels.

## 8. Accessibility and Windows behavior

- Ensure every action is keyboard reachable and has a visible focus indicator.
- Give controls accessible names, roles, values, and useful announcements for stage changes, selection counts, errors, and generation progress.
- Support `Tab`, `Shift+Tab`, arrow-key navigation where appropriate, `Enter`/`Space` activation, and `Escape` to close transient UI without losing work.
- Keep focus within dialogs while open, return focus to the invoking control when closed, and provide a predictable close path.
- Support Windows high-contrast settings and avoid hard-coded styling that prevents user-selected contrast modes where possible.
- Target at least 4.5:1 contrast for normal text and 3:1 for large text; verify actual rendered foreground/background pairs in both themes.
- Do not rely on color alone for selected, warning, error, valid, or mixed states.
- Respect OS display scaling, text size, and window resizing. Check clipping and overlap at higher scaling as well as the target viewport sizes.
- Honour reduced motion.
- Keep native Windows file dialogs and the existing PyWebView/WebView2 behavior.

## 9. Anti-generic UI guardrails

These are warning signs, not proof that a model generated the interface. A pattern is a problem when it is an unchosen default that does not serve the brief.

### Do not reach for these by reflex

- purple/indigo-to-blue gradients, gradient text, glowing accents;
- warm cream + terracotta as a generic “tasteful” escape;
- near-black + acid green or vermilion as a generic technical look;
- glass panels, frosted surfaces, blurred cards, glowing shadows;
- oversized rounded cards, floating shells, and card-inside-card layouts;
- a centered marketing hero or a three-icon-card feature grid inside an internal application;
- fake KPI/stat tiles or charts that do not support an instructor decision;
- decorative 01/02/03 labels for non-sequential content;
- all-caps eyebrow labels above every heading;
- monospace micro-labels, middle-dot metadata chains, automatic arrow glyphs on every action;
- “designed” one-word headline emphasis (italic/gradient/highlight) without semantic purpose;
- arbitrary bento grids, asymmetry, or dense broadsheet styling chosen only to look distinctive;
- a permanent inspector that steals space from the Packages matrix;
- duplicated warnings, duplicated primary actions, or six workflow forms displayed together;
- fake device/window mockups, macOS traffic-light controls, or fake desktop chrome;
- unnecessary hover transforms, entrance choreography, bounce, shimmer, or parallax;
- lorem ipsum, fake student data presented as actual data, or fabricated system metrics.

### Do not ban these without context

- **Tables:** they are appropriate for the actual batch comparison task.
- **Green accent:** appropriate when verified from the CvSU identity and used consistently for action/selection.
- **Cards or borders:** appropriate when they express a real grouping, temporary surface, or repeated item.
- **A sidebar:** potentially useful for stable top-level navigation, but not automatically appropriate at 880 px and not a reason to keep an inspector permanently open.
- **Monospace:** appropriate for file paths, logs, and code-like values.
- **Animation:** appropriate when it clarifies a user's action or system progress.
- **System font:** appropriate here because this is Windows software and platform legibility matters more than fashionable typeface novelty.

## 10. Responsive and state requirements

Prototype and inspect at:

- 1120×780 — primary desktop review size;
- 880×640 — constrained desktop review size;
- Windows display scaling above 100% — verify no clipped controls or hidden columns.

For each stage, review:

- initial/empty state;
- valid populated state;
- validation warning and blocking error;
- busy/progress state where relevant;
- selected/multi-selected state;
- keyboard focus state;
- light and dark appearance;
- reduced motion;
- long labels and realistic filenames.

For Packages additionally review: all selected, none selected, mixed values, bulk apply, exceptions preserved, deliberate overwrite, inspector open/closed, and selection retained after closing inspector.

## 11. Design workflow and review gates

1. **Investigate.** Read `AGENTS.md`, confirm branch and worktree, verify the UI source of truth, inspect existing components/tokens and tests. Do not assume the handover reflects the latest checkout.
2. **Map tasks.** Model first-time intake, roster repair, 10–20-section batch configuration, individual exception, repeat-semester flow, preflight correction, and generation.
3. **Decide information architecture.** Assign each piece of content/action to one stage. Remove duplicates before styling.
4. **Plan the direction.** State the product-specific visual rationale, semantic color roles, type ramp, layout, and one meaningful signature interaction. Do not begin from a fashionable style menu.
5. **Challenge defaults.** Ask whether each visual choice would appear unchanged in a generic SaaS dashboard. Check both first-order and second-order AI tells.
6. **Prototype real states.** Use realistic class counts, filenames, and package states. Show the user interaction and exception paths.
7. **Render and critique.** Inspect screenshots, not only code. Perform the silhouette test: reduce the screen to coarse black/white blocks; if its structure could describe any generic admin dashboard, revise the information architecture.
8. **Test.** Keyboard, focus, high contrast, text size, 880/1120 widths, themes, reduced motion, and existing automated tests.
9. **Reconcile.** Preserve working bridge contracts, state semantics, native file dialogs, workspaces, and features. Distinguish known pre-existing test failures from regressions.
10. **Approval gate.** Present concepts/prototypes and stop for explicit approval before production changes.

### Review verdict

- **PASS:** Every visible element has a task or meaning; all critical HIG behaviors are present; no blocking accessibility or responsiveness defect; no unchosen high-severity AI default; no duplicated warnings/actions.
- **REVISE:** The screen is still structurally generic, a major task is hidden, the main action is unclear, the table clips essential information, exceptions can be overwritten silently, or any accessibility requirement fails.
- **ESCALATE:** A requested rule conflicts with data correctness, accessibility, security, repository governance, backend behavior, or a settled product requirement. Preserve the higher-priority constraint and document the tradeoff.

## 12. Boundaries for implementation agents

- Stack: vanilla HTML/CSS/JavaScript, Python backend, PyWebView, Microsoft Edge WebView2. Do not introduce React, Vue, Next.js, Tailwind, Vite, external fonts, CDNs, remote assets, analytics, or new frontend frameworks without explicit approval.
- Keep the work frontend-only unless a real UX requirement cannot be achieved without backend changes; stop and explain before crossing that boundary.
- Preserve the `window.pywebview.api` bridge and existing workspace, file import, parser, template, settings, logs, guides, progress, cancellation, and output behaviors.
- Read `AGENTS.md`; obey branch governance; do not modify protected governance files; do not discard user changes; do not push or merge.
- Do not modify the separate documentation repository unless explicitly asked.
- Do not bump the application version without authorization.

## 13. Source notes

This contract synthesizes:

- Apple HIG: Design principles, Layout, Color, Windows, and current platform guidance (primary philosophy).
- Microsoft Windows app guidance: Windows typography, navigation, content layout, and accessibility (platform adaptation).
- `funboy322/avoid-ai-design`: two generations of AI visual defaults; scan + render + intent-based critique; maintain one design contract across pages.
- `LeoStehlik/no-slop-ui`: practical bans/checklist for gradients, glass, decorative metrics, vague copy, fake dashboards, and common component patterns.
- Supplied `frontend-design.SKILL.md`: subject-grounded direction, intentional type/layout decisions, restrained motion, functional language, and self-critique.
- CvSU Gen handover: settled Hybrid Guided Batch Workbench, stage responsibilities, Windows/PyWebView constraints, failure modes, tests, and approval gate.

See `CvSU_Gen_Design_Research_Notes.md` for the source links, conflicts, and interpretation notes.
