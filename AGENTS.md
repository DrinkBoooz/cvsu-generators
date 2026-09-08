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

