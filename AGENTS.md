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
When merging branches (e.g., merging `dev` into `main`):
- **Always use `--no-ff` (No Fast-Forward)**: Never perform fast-forward merges into `main`. Always force a dedicated merge commit using `git merge --no-ff <branch>` to ensure the Git commit history preserves a distinct visual branch tree with fork-and-merge nodes.
- **Merge Commit Message Formatting**: Merge commits must also follow the commit numbering rule:
  `<commit_number>: merge <source_branch> into <target_branch>`
  Example: `44: merge dev into main`
- **Standard Merge Workflow**:
  1. Ensure all work is committed and pushed on `dev`.
  2. `git checkout main`
  3. `git merge --no-ff dev -m "<commit_number>: merge dev into main"`
  4. `git push origin main`
  5. `git checkout dev`
