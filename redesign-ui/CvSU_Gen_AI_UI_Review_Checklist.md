# CvSU Gen — Anti-Generic UI Review Checklist

Use this after every AI-assisted UI design, prototype, or implementation. It is a **product-specific HIG review**, not a generic style score. The checklist is intended to catch weak decisions before they reach production.

## Gate 0 — Authority check

- [ ] Apple HIG principles have been applied to purpose, agency, responsibility, familiarity, flexibility, simplicity, craft, and delight.
- [ ] Windows 10/11 conventions are respected for desktop behavior, typography, keyboard use, native dialogs, scaling, and high contrast.
- [ ] Product requirements, accessibility, data correctness, and repository governance have not been overridden by a visual rule.
- [ ] No macOS window chrome or Apple-only materials/components have been copied just to look “Apple-like.”

## Product fit and information architecture

- [ ] The first visible screen is the actual task workspace, not a marketing hero.
- [ ] The six contexts remain clear: Schedule, Rosters, Packages, Dates, Output, Generate.
- [ ] Each stage has one responsibility; unrelated stage forms are not displayed together.
- [ ] Users can revisit stages without losing valid work.
- [ ] Packages is optimized for comparing and configuring multiple sections.
- [ ] Roster repair happens in Rosters, not in a duplicate repair UI elsewhere.
- [ ] Every warning has one authoritative location and one direct correction route.
- [ ] There is one primary action per stage, not duplicated primary buttons.
- [ ] No invented KPI, chart, metric, activity feed, or decorative status panel is present.

## Batch and individual configuration

- [ ] The class matrix has the width needed to compare sections.
- [ ] Selection, select all, clear selection, and selected count are obvious.
- [ ] Mixed values are explicitly shown as mixed.
- [ ] Bulk action copy states its exact scope.
- [ ] Per-section exceptions are preserved by default.
- [ ] Overwriting exceptions is explicit and names the number of affected sections.
- [ ] Individual configuration is available on demand, not permanently stealing table width.
- [ ] Closing the inspector preserves selection and table context.

## Visual hierarchy and craft

- [ ] The most important task is the most visually obvious item on the screen.
- [ ] Grouping relies on clear alignment, spacing, and meaningful boundaries—not a card around everything.
- [ ] No unnecessary nested cards or floating shells.
- [ ] No glassmorphism, decorative gradients, gradient text, colored glows, blur panels, or background blobs.
- [ ] No default three-icon-card layout, bento grid, or centered SaaS hero inside the product.
- [ ] Color has a documented semantic role; CvSU green is verified against actual brand artwork before being called official.
- [ ] Light and dark themes are both intentionally designed; dark mode is not just inverted light mode.
- [ ] Geometry varies only when hierarchy or platform behavior requires it.
- [ ] The interface looks like a coherent tool for academic document production, not an interchangeable dashboard.

## Typography and copy

- [ ] Windows-native typography uses Segoe UI Variable / Segoe UI fallback unless a documented reason requires otherwise.
- [ ] Text hierarchy uses size and weight, not decorative type pairing.
- [ ] Body and control text remain readable; metadata is not used to squeeze content.
- [ ] UI text uses sentence case and left alignment by default.
- [ ] No repeated uppercase eyebrow labels or decorative micro-labels.
- [ ] No trendy display font or mono labels chosen merely to look designed.
- [ ] Button text names the outcome: `Replace roster`, `Apply to selected sections`, `Start generation`.
- [ ] Errors explain what happened, what is affected, and how to fix it.
- [ ] No promotional filler such as “seamless,” “command center,” “unlock productivity,” or “operational clarity.”

## Motion and interaction

- [ ] Motion only explains a user action or meaningful system progress.
- [ ] No repeated fade-up, spring, bounce, hover scaling, shimmer, or parallax.
- [ ] Focus, selected, disabled, loading, success, and error states are visible and consistent.
- [ ] Reduced-motion preferences are respected.
- [ ] No color-only status or selection communication.
- [ ] No unsupported success state; progress reflects real backend behavior.

## Accessibility and Windows behavior

- [ ] Every interactive control is keyboard reachable.
- [ ] Focus is clearly visible and follows a logical order.
- [ ] Dialogs have predictable close behavior and return focus to the invoking control.
- [ ] Controls expose accessible names, roles, and values.
- [ ] Normal text contrast is at least 4.5:1; large text is at least 3:1.
- [ ] Windows high-contrast mode, display scaling, and enlarged text have been checked.
- [ ] Native file dialogs and existing desktop behaviors remain intact.

## Responsive and state coverage

- [ ] Reviewed at 1120×780 and 880×640.
- [ ] No essential table column or action is clipped at 880 px.
- [ ] No horizontal page overflow or overlapping controls.
- [ ] Long course names and filenames are tested.
- [ ] A realistic 10–20-section dataset is used.
- [ ] Empty, populated, warning, blocker, selected, mixed, loading, success, and error states are covered.
- [ ] Light and dark themes are reviewed.

## Anti-AI tell audit

Flag only when a pattern is an unchosen default that does not serve the brief.

- [ ] No purple/indigo-blue gradient or gradient headline as a reflex.
- [ ] No “anti-AI” cream/terracotta or black/neon theme chosen by reflex.
- [ ] No identical rounded cards and soft shadows around every content group.
- [ ] No decorative 01/02/03 markers for non-sequential items.
- [ ] No middle-dot metadata chains, automatic CTA arrows, or all-caps micro-labels.
- [ ] No fake window chrome or macOS traffic-light buttons.
- [ ] No generic fake data, placeholder charts, invented metrics, or marketing filler.
- [ ] The grayscale silhouette of the screen reflects the real workflow, not a generic admin template.
- [ ] The interface's distinctive detail comes from its task model (exception-aware batch edits), not a decorative flourish.

## Final verdict

**PASS** — No critical HIG/accessibility/task failure; the screen is coherent, specific to CvSU Gen, and free of unchosen high-severity defaults.

**REVISE** — Any critical workflow is unclear, the design remains structurally generic, important data is clipped, a batch action can silently erase exceptions, or accessibility fails.

**ESCALATE** — A style rule conflicts with user requirements, accessibility, data integrity, platform behavior, or repository constraints. Preserve the higher-priority requirement and document the conflict.

### Evidence to attach to a review

- Rendered screenshots at 1120×780 and 880×640 in light and dark themes.
- One screenshot of mixed selection and preserved exceptions.
- One screenshot of the individual inspector open.
- One screenshot of roster mismatch repair.
- One screenshot of preflight with a blocker and its direct fix.
- Keyboard/focus and reduced-motion verification notes.
- Automated test results, with historical baseline failures separated from regressions.
