# Test Programs and Testing Location Rule

Always place all test programs, test suites, test fixtures, and testing utilities inside the `tests/` directory:
- Automated unit and integration tests (e.g., `test_*.py`) must reside under `tests/`.
- Manual verification scripts, diff scripts, and test helpers must also be kept under `tests/`.
- Never create standalone test scripts or test files in the project root directory or other non-test folders.
