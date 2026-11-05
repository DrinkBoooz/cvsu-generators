# CvSU Gen — UI Design/Implementation Agent Instructions

Read `CvSU_Gen_DESIGN.md` and `CvSU_Gen_AI_UI_Review_Checklist.md` before creating or changing any visible UI.

## Your design authority

Apple Human Interface Guidelines are the **main design guideline**. Use HIG to make decisions about purpose, agency, responsibility, familiarity, flexibility, simplicity, craft, delight, hierarchy, progressive disclosure, feedback, accessibility, and recovery. Adapt these principles to a Windows desktop application. Do not imitate macOS chrome, Liquid Glass, or Apple-only components.

Windows 10/11 conventions govern platform fit: use Segoe UI Variable / Segoe UI fallback, familiar desktop controls, keyboard behavior, high-contrast support, display scaling, and native file dialogs. Treat `avoid-ai-design` and `no-slop-ui` as anti-generic review aids; they do not outrank HIG, accessibility, the product requirements, or the established design contract.

## Understand the product before styling

CvSU Gen is an offline Windows utility for faculty members producing academic documents from an instructor schedule and student section rosters. Typical use is 10–20 sections, with up to 40 students per section. Accuracy, predictability, recovery, and repeated-use efficiency matter more than novelty.

The approved direction is **Hybrid Guided Batch Workbench**:

- Keep six revisitable contexts: Schedule, Rosters, Packages, Dates, Output, Generate.
- Packages is the full-width batch workspace.
- Show the individual class inspector only on demand; adapt it to an overlay/inline editor at narrow widths.
- Preserve per-class exceptions during batch changes unless the instructor explicitly opts to overwrite them.
- Keep roster repair in Rosters and show each warning once in an authoritative place.
- Preflight identifies the affected section/file and links directly to the fix.

## Before writing code

1. Read `AGENTS.md` and protected project instructions.
2. Inspect branch, uncommitted changes, canonical UI entrypoint, actual app behavior, existing CSS/JS modules, test locks, and bridge contract.
3. Re-verify that the work is frontend-only and preserve all existing features.
4. Map first-use, mismatch repair, batch, individual exception, repeat semester, preflight, and generation journeys.
5. Decide the information architecture before palette, geometry, or motion.
6. Propose a compact, product-specific token and layout plan. Challenge it against the first-order and second-order AI defaults described in `avoid-ai-design` and `frontend-design.SKILL.md`.
7. When a design decision is generic, change it because the task requires a better solution—not merely to be visually different.

## Do not generate by reflex

Avoid generic purple-blue gradients, cream/terracotta and black/neon “anti-AI” palettes, glassmorphism, nested cards, floating shells, oversized rounded cards, glows, default KPI grids, decorative charts, centered marketing heroes, three identical icon cards, bento grids without a content reason, all-caps eyebrows, decorative numbers, vague SaaS copy, CTA arrows, fake window chrome, and gratuitous motion.

Do not blindly apply bans that conflict with this product. Real tables, clear grouping, subtle borders, a verified CvSU green accent, a Windows system font, a temporary inspector, and purposeful animation are valid when supported by the task and HIG.

## Build and evaluate

- Use vanilla HTML/CSS/JS. No new framework, remote font, CDN, analytics, or backend behavior without explicit approval.
- Keep CSS modular, semantic, token-driven, and avoid specificity conflicts or endless overrides.
- Preserve `window.pywebview.api`, native dialogs, OLE drag-and-drop, workspaces, parsers, templates, settings, logs, guides, cancellation, telemetry, and generation behavior.
- Review at 1120×780 and 880×640 in both themes, with realistic labels and class counts.
- Test keyboard operation, visible focus, high contrast, display scaling, reduced motion, mixed batch values, preserved exceptions, roster repair, preflight, and true progress/completion.
- Render screenshots and run the silhouette test. A clean scanner result is not sufficient if the structure remains generic.
- Report which findings are code-certain, visible in rendered screenshots, or judgment-based.

## Approval and repository boundaries

The current task is design/prototype review unless the user explicitly approves production implementation. Stop for explicit approval before changing production UI source. Do not modify backend/generator/parser/orchestrator behavior. Read and obey branch governance; do not modify protected governance files, discard user changes, push, merge, or update the separate documentation repository without authorization. Do not bump the application version without authorization.

## Required final report

Provide: source/branch verification; UX audit; chosen information architecture; alternatives and trade-offs; screenshots/prototype; accessibility and viewport evidence; test results with baseline failures distinguished; unresolved risks. Do not claim production verification from a standalone mockup.
