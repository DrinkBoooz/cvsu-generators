"""
Automated Dependency Architecture & Manifest Consistency Test Suite.
Validates exact pinning, four-tier manifest partitioning, explicit import-to-distribution
mappings, absence of undeclared/deprecated packages, and forwarding manifest integrity.
"""

import os
import ast
import re
import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_REQ = os.path.join(WORKSPACE_ROOT, "requirements-runtime.txt")
TEST_REQ = os.path.join(WORKSPACE_ROOT, "requirements-test.txt")
BUILD_REQ = os.path.join(WORKSPACE_ROOT, "requirements-build.txt")
AGGREGATE_REQ = os.path.join(WORKSPACE_ROOT, "requirements.txt")
EXEC_BUILD_REQ = os.path.join(WORKSPACE_ROOT, "executable_test", "requirements-build.txt")

# Explicit mapping from Python import roots to PyPI distribution names
IMPORT_TO_DIST = {
    "webview": "pywebview",
    "clr": "pythonnet",
    "System": "pythonnet",
    "lxml": "lxml",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
    "docx": "python-docx",
    "playwright": "playwright",
    "PyInstaller": "pyinstaller",
}

INTERNAL_MODULE_NAMES = {
    "modules", "executable_test", "tests", "dev", "api", "native", "parsers",
    "models", "services", "generators", "common", "utils", "roster_parser",
    "schedule_parser", "ceit_gen", "attendance_gen", "grade_gen", "recipe",
    "schedule", "student", "class_info", "template_inspector",
    "template_recipe_service", "validator", "config_manager", "orchestrator",
    "docx_utils", "system", "config", "templates", "schedule_roster",
    "document_generator", "ceit_directory", "excel_utils", "logger",
    "recipe_validator", "base", "generation", "dnd"
}


def parse_manifest_direct_pins(filepath: str) -> dict[str, str]:
    """Extracts direct package==version declarations from a requirements file, ignoring -r includes."""
    pins = {}
    assert os.path.exists(filepath), f"Manifest file does not exist: {filepath}"
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-r"):
                continue
            match = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-]+)$", stripped)
            assert match, f"Line in {os.path.basename(filepath)} must be an exact '==' pin: '{stripped}'"
            pkg, ver = match.group(1).lower(), match.group(2)
            pins[pkg] = ver
    return pins


def extract_third_party_imports(directories: list[str]) -> set[str]:
    """Parses AST of all python files in given directories and extracts non-stdlib, non-internal root imports."""
    stdlib = set(getattr(os, "stdlib_module_names", []))
    if not stdlib:
        import sys
        stdlib = set(sys.stdlib_module_names)

    found_imports = set()
    for directory in directories:
        dir_path = os.path.join(WORKSPACE_ROOT, directory)
        for root, _, files in os.walk(dir_path):
            if any(x in root for x in [".venv", "venv", "__pycache__", "node_modules"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    full_path = os.path.join(root, f)
                    with open(full_path, "r", encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=full_path)
                    for node in ast.walk(tree):
                        mod_name = None
                        if isinstance(node, ast.Import):
                            for n in node.names:
                                mod_name = n.name.split(".")[0]
                                if mod_name not in stdlib and mod_name not in INTERNAL_MODULE_NAMES:
                                    found_imports.add(mod_name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                mod_name = node.module.split(".")[0]
                                if mod_name not in stdlib and mod_name not in INTERNAL_MODULE_NAMES:
                                    found_imports.add(mod_name)
    return found_imports


def test_manifest_files_exist():
    """Verify that all normalized requirement manifests exist in the expected locations."""
    assert os.path.isfile(RUNTIME_REQ), "requirements-runtime.txt must exist"
    assert os.path.isfile(TEST_REQ), "requirements-test.txt must exist"
    assert os.path.isfile(BUILD_REQ), "requirements-build.txt must exist"
    assert os.path.isfile(AGGREGATE_REQ), "requirements.txt must exist"
    assert os.path.isfile(EXEC_BUILD_REQ), "executable_test/requirements-build.txt must exist"


def test_manifest_forwarding_syntax():
    """Verify executable_test/requirements-build.txt forwards to ../requirements-build.txt."""
    with open(EXEC_BUILD_REQ, "r", encoding="utf-8") as f:
        content = f.read().strip()
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert lines == ["-r ../requirements-build.txt"], (
        f"executable_test/requirements-build.txt must forward to ../requirements-build.txt, got: {lines}"
    )


def test_production_runtime_manifest_coverage():
    """Verify all production third-party imports are covered by requirements-runtime.txt via explicit mapping."""
    prod_imports = extract_third_party_imports(["modules", "executable_test"])
    runtime_pins = parse_manifest_direct_pins(RUNTIME_REQ)

    # Every production import must map to a declared distribution
    for imp in prod_imports:
        assert imp in IMPORT_TO_DIST, f"Untracked third-party production import: '{imp}'"
        dist = IMPORT_TO_DIST[imp].lower()
        assert dist in runtime_pins, (
            f"Production import '{imp}' maps to distribution '{dist}' which is missing from requirements-runtime.txt"
        )

    # Verify pythonnet is directly declared
    assert "pythonnet" in runtime_pins, "pythonnet must be explicitly declared in requirements-runtime.txt"
    assert runtime_pins["pythonnet"] == "3.1.0"
    assert runtime_pins["pywebview"] == "6.2.1"
    assert runtime_pins["lxml"] == "6.1.1"
    assert runtime_pins["openpyxl"] == "3.1.5"
    assert runtime_pins["xlrd"] == "2.0.2"


def test_test_manifest_contents():
    """Verify test manifest declarations: includes runtime, pytest, python-docx, and playwright."""
    with open(TEST_REQ, "r", encoding="utf-8") as f:
        content = f.read()
    assert "-r requirements-runtime.txt" in content

    test_pins = parse_manifest_direct_pins(TEST_REQ)
    assert test_pins.get("pytest") == "9.1.1"
    assert test_pins.get("python-docx") == "1.2.0"
    assert test_pins.get("playwright") == "1.63.0"

    # python-docx must NOT be in runtime or build manifests
    runtime_pins = parse_manifest_direct_pins(RUNTIME_REQ)
    build_pins = parse_manifest_direct_pins(BUILD_REQ)
    assert "python-docx" not in runtime_pins, "python-docx must not be in requirements-runtime.txt"
    assert "python-docx" not in build_pins, "python-docx must not be in requirements-build.txt"


def test_build_manifest_contents():
    """Verify build manifest declarations: includes runtime and pyinstaller."""
    with open(BUILD_REQ, "r", encoding="utf-8") as f:
        content = f.read()
    assert "-r requirements-runtime.txt" in content

    build_pins = parse_manifest_direct_pins(BUILD_REQ)
    assert build_pins.get("pyinstaller") == "6.22.2"


def test_aggregate_manifest_contents():
    """Verify root requirements.txt is an aggregate including test and build requirements."""
    with open(AGGREGATE_REQ, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    assert "-r requirements-test.txt" in lines
    assert "-r requirements-build.txt" in lines


def test_excluded_packages_not_in_manifests():
    """Verify pypiwin32, pywin32, pytest-mock, and pytest-playwright are absent from all manifests."""
    forbidden = ["pypiwin32", "pywin32", "pytest-mock", "pytest-playwright"]
    for req_path in [RUNTIME_REQ, TEST_REQ, BUILD_REQ, AGGREGATE_REQ, EXEC_BUILD_REQ]:
        with open(req_path, "r", encoding="utf-8") as f:
            text = f.read().lower()
        for pkg in forbidden:
            assert pkg not in text, f"Forbidden package '{pkg}' must not be declared in {os.path.basename(req_path)}"
