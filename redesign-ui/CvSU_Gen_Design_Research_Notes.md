# CvSU Gen — Anti-Generic UI Research Notes

**Research date:** 4 November 2026  
**Question:** How do we avoid an AI-generated interface look while retaining Apple HIG as CvSU Gen's primary design guideline?

## Executive synthesis

The most useful conclusion across the references is not “use a different color” or “make the UI more minimal.” It is: **replace unchosen defaults with decisions grounded in the actual product and user task.**

AI-generated interfaces often converge on familiar patterns because the model reuses common examples and starter-kit structures. The references identify first-order defaults (purple/blue gradients, generic fonts, centered hero + three feature cards, glassy nav, oversized cards) and second-order defaults that appear after people try to avoid the first set (cream/terracotta, near-black/neon, broadsheet hairlines, repeated card kits, uppercase mono labels, decorative numbering). A design can remove every obvious gradient and still look generic if its information architecture remains a stock dashboard.

For CvSU Gen, the highest-value anti-generic decision is therefore architectural: a focused six-stage workflow with a Packages-first batch matrix, contextual inspection on demand, and exception-safe bulk operations. The visual style should support that architecture, not decorate around it.

## 1. Apple HIG: primary design authority

Apple's current Design Principles page lists eight foundations: **Purpose, Agency, Responsibility, Familiarity, Flexibility, Simplicity, Craft, and Delight**. The current page notes a June 8, 2026 reintroduction of the principles. For CvSU Gen, these principles translate into:

- Purpose: show the instructor's current task, not decorative dashboard metrics.
- Agency: revisit stages, preserve work, make batch scope explicit, and recover from mistakes.
- Responsibility: state consequences and affected files/sections; show truthful generation progress.
- Familiarity: use recognizable file, table, form, dialog, and keyboard patterns.
- Flexibility: support first-use and repeat workflows, mouse and keyboard, mixed values and exceptions, themes and constrained windows.
- Simplicity: one clear primary action and one authoritative warning location; progressive disclosure rather than a flattened mega-form.
- Craft: design all meaningful states, not only the happy path; test real data and screenshots.
- Delight: use satisfying feedback and completion, not decorative spectacle.

Apple's Layout guidance reinforces grouping, sufficient space for important information, visual hierarchy, alignment, progressive disclosure, control spacing, and adaptation. Apple's Color guidance emphasizes consistent semantic meaning and not relying on color alone. These are directly useful to this desktop product.

**Important boundary:** HIG is the main design philosophy, but CvSU Gen is not an Apple-platform application. Use the HIG principles; do not copy macOS title bars, traffic-light controls, Liquid Glass, or Apple-specific chrome. Windows conventions must make the finished application feel at home on Windows.

## 2. `avoid-ai-design` — detect first-order and second-order defaults

Repository: https://github.com/funboy322/avoid-ai-design  
Relevant files: `SKILL.md`, `references/ai-tells-catalog.md`, `references/aesthetic-directions.md`.

Key ideas adopted:

- Two waves of visual defaults matter. Avoiding the classic purple gradient can merely lead to a new standard “tasteful” theme.
- A tell is evidence of an unchosen default, not proof that an AI authored it.
- Code scanning catches only some issues. Palette weight, visual hierarchy, spacing rhythm, and structure require rendered review.
- Derive direction from the product's actual artifacts, context, and audience.
- Establish one design contract across all stages; otherwise pages drift.
- Use a rendered silhouette test to catch generic composition that survives token changes.
- Make one deliberate design move and keep the rest restrained; do not over-design.

The catalog also usefully flags copy and component patterns: generic marketing language, repeated all-caps eyebrows, automatic arrows on every CTA, one-word headline highlighting, identical card grids, decorative metrics, and gratuitous motion.

## 3. `no-slop-ui` — pragmatic production checklist

Repository: https://github.com/LeoStehlik/no-slop-ui  
Relevant files: `SKILL.md`, `references/banned-patterns.md`, `examples/review-checklist.md`, `docs/conversion-proof.md`.

Key ideas adopted:

- Build the real product screen rather than a hero or decorative shell.
- Prefer content-first tables, forms, filters, menus, and controls when the task needs them.
- Avoid fake metrics, charts, vague copy, glass panels, gradients, glowing shadows, oversized card layouts, and decorative motion.
- Use stable dimensions, clear hierarchy, 4/8/12/16/24/32 spacing, predictable controls, and readable body text.
- Review with a checklist after implementation; do not accept a design merely because it appears polished.

### Where a repository rule must be overridden for CvSU Gen

`no-slop-ui` includes a blanket ban on the `Segoe UI` font stack. That is not appropriate for this particular Windows application. Microsoft documents Segoe UI Variable as the Windows system font and recommends it for Windows app UI; the supplied CvSU frontend design skill also specifies a native Windows font stack. Therefore use Segoe UI Variable / Segoe UI fallback rather than following that blanket ban. This is an example of why the repository itself says its visual rules must not override accessibility, product requirements, or the existing design system.

The same applies to a fixed sidebar: a sidebar can be useful, but it is not a universal requirement. Apple HIG notes that sidebars consume substantial space and suggests more compact navigation when space is limited. CvSU Gen's six-stage navigation and 880 px constraint favor a compact stage navigator over a permanent inspector. The Packages inspector is contextual and appears only when needed.

The `no-slop-ui` suggested palettes are not adopted as ready-made CvSU themes. The project already has a green institutional direction, and its actual logo assets should be sampled before anyone claims a hex value is official.

## 4. Supplied `frontend-design.SKILL.md`

The uploaded skill's strongest contributions are:

- ground the visual decisions in the actual subject and product;
- choose type, palette, layout, and visual structure deliberately rather than starting from familiar templates;
- review the plan against generic defaults before writing code;
- avoid automatic uppercase labels, decorative headline accents, and numbering that does not encode a real sequence;
- use motion sparingly and only where it serves the experience;
- write direct, user-centered copy with consistent action vocabulary;
- treat error and empty states as direction for the next action;
- critique rendered results and remove decorative elements that do not serve the brief.

The skill's explicit Windows system font recommendation and the user-supplied project handover's offline stack constraints are treated as product-specific requirements.

## 5. Tensions reconciled

| Source tension | CvSU Gen decision | Reason |
|---|---|---|
| No-slop UI bans Segoe UI; Windows guidance recommends Segoe UI Variable | Use Segoe UI Variable / Segoe UI fallback | Native Windows legibility and user-supplied project direction outweigh a generic blanket rule. |
| No-slop UI recommends fixed 240–260 px sidebar; project requires no permanent inspector and 880 px usability | Keep compact stage navigation; inspector is on-demand | Protect the central batch matrix and avoid consuming workspace width. |
| Some AI design advice says to avoid system fonts; Windows desktop guidance recommends the system font | Use one Windows-native family with intentional size/weight hierarchy | Distinctiveness should come from task architecture and craft, not novelty typography. |
| Anti-slop lists can read as absolute bans; Apple HIG values purpose and flexibility | Treat each as a warning, not a universal prohibition | Tables, cards, borders, motion, or sidebars are valid when the task and HIG justify them. |
| Apple HIG is primary, but the product runs on Windows | Apply HIG principles; use Windows platform conventions | The HIG itself calls for platform intention and familiarity, not literal cross-platform imitation. |
| A unique aesthetic may tempt decorative branding | Make the signature detail a meaningful interaction: exception-aware batch editing | CvSU Gen's real differentiator is the instructor workflow and correctness, not a decorative motif. |

## 6. Proposed CvSU Gen design direction

**Direction:** Quiet academic workbench with exception-aware batch editing.

**Distinctive idea:** Make batch intent visible. Before a bulk edit, show which sections will change and which contain custom exceptions that will remain untouched. The interface becomes recognizable through the way it protects academic configuration, not through a decorative visual flourish.

**Typography:** Segoe UI Variable / Segoe UI fallback; one family; regular and semibold weights; sentence case; 14 px body as the normal starting point; monospace only for paths and logs.

**Layout:** Compact six-stage navigation, focused stage canvas, full-width Packages matrix, contextual inspector on demand, one clear primary action, and direct issue repair.

**Color:** Neutral light/dark surfaces with a restrained verified CvSU green action/selection accent. Gold remains secondary and sparing only if confirmed from the actual identity assets. Working token values are provisional and are not official brand specifications.

**Surfaces:** Solid, clear, mostly flat; meaningful dividers and boundaries; temporary elevation for menus/dialogs/inspectors only.

**Motion:** User-triggered, short, non-dramatic, reduced-motion aware.

### Provisional contrast spot-check

The working token pairs in `cvsu-gen-ui-tokens.css` were calculated, not judged by eye. Examples: light body text `#58635B` on canvas `#F4F6F3` = **5.77:1**; white text on the primary green `#226247` = **7.23:1**; dark body text `#B6C1B8` on `#171E19` = **9.15:1**; dark button text `#142319` on action green `#83B897` = **7.22:1**. These are token-level checks only; every actual text/control combination still needs rendered verification.

## 7. Recommended review method

1. Inspect the real code and actual runtime; do not judge only from a generated screenshot.
2. Map task and data first; classify each element as task content, command, status, or optional detail.
3. Define the stage architecture and exception-safe interactions.
4. Record a token and layout plan in `CvSU_Gen_DESIGN.md`.
5. Check first-order and second-order defaults before implementation.
6. Render all relevant states in both themes at 1120×780 and 880×640.
7. Run keyboard, focus, contrast, text scaling, high-contrast, and reduced-motion checks.
8. Review a grayscale silhouette at small size for generic structure.
9. Use `CvSU_Gen_AI_UI_Review_Checklist.md` and report findings as code-certain, rendered, or judgment-based.
10. Stop for explicit approval before production changes.

## 8. Sources

### Primary design references

- Apple Human Interface Guidelines: https://developer.apple.com/design/human-interface-guidelines/
- Apple HIG — Design principles: https://developer.apple.com/design/human-interface-guidelines/design-principles/
- Apple HIG — Layout: https://developer.apple.com/design/human-interface-guidelines/layout/
- Apple HIG — Color: https://developer.apple.com/design/human-interface-guidelines/color/
- Apple HIG — Sidebars: https://developer.apple.com/design/human-interface-guidelines/sidebars/
- Apple HIG — Windows: https://developer.apple.com/design/human-interface-guidelines/windows/

### Windows platform references

- Windows app design: https://learn.microsoft.com/en-us/windows/apps/design/
- Windows typography: https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography
- Windows navigation basics: https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics
- Windows content layout and spacing: https://learn.microsoft.com/en-us/windows/apps/design/basics/content-basics
- Windows accessible text requirements: https://learn.microsoft.com/en-us/windows/apps/design/accessibility/accessible-text-requirements
- Designing inclusive Windows software: https://learn.microsoft.com/en-us/windows/apps/design/accessibility/designing-inclusive-software

### AI-generated UI critique references

- `avoid-ai-design` repository: https://github.com/funboy322/avoid-ai-design
- `avoid-ai-design` skill: https://github.com/funboy322/avoid-ai-design/blob/main/SKILL.md
- `avoid-ai-design` AI tells catalog: https://github.com/funboy322/avoid-ai-design/blob/main/references/ai-tells-catalog.md
- `no-slop-ui` repository: https://github.com/LeoStehlik/no-slop-ui
- `no-slop-ui` skill: https://github.com/LeoStehlik/no-slop-ui/blob/master/SKILL.md
- `no-slop-ui` banned patterns: https://github.com/LeoStehlik/no-slop-ui/blob/master/references/banned-patterns.md
- `no-slop-ui` review checklist: https://github.com/LeoStehlik/no-slop-ui/blob/master/examples/review-checklist.md

### User-supplied project sources

- `frontend-design.SKILL.md` — uploaded during this conversation. See its guidance on subject-grounded visual choices, two-pass planning/review, anti-default critique, restrained motion, and direct microcopy.
- `CvSU Gen — Design & UX Handover for the Next Agent` — uploaded earlier. Its settled requirements include the Hybrid Guided Batch Workbench, balanced first-use/repeat-use priority, Apple HIG as the design anchor, Windows desktop adaptation, 10–20-section batch scale, responsive target sizes, implementation boundaries, test expectations, and approval gate.
