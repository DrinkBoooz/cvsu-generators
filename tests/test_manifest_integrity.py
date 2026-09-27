"""
Permanent Manifest Integrity & Test Inventory Governance Suite.

Enforces the architectural invariant that scripts/test_orchestrator.py MANIFEST
is the authoritative, self-checking source of truth for all tests in the repository:
  1. Every tests/test_*.py file must appear in exactly ONE manifest layer
     (unless explicitly declared in AUXILIARY_UTILITIES with architectural justification).
  2. No manifest file path may appear twice across any layer.
  3. No nonexistent file paths may be listed in MANIFEST or AUXILIARY_UTILITIES.
  4. Adding a new tests/test_*.py without registering it in MANIFEST immediately FAILS closed.
"""

import os
import sys
import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.test_orchestrator import (
    MANIFEST,
    AUXILIARY_UTILITIES,
    DOCUMENTED_REPO_ARTIFACTS,
    get_manifest_inventory,
    resolve_python_executable,
    validate_report_consistency,
)


def test_manifest_files_exist_on_disk():
    """Verify that every file listed anywhere in MANIFEST physically exists."""
    for layer_name, steps in MANIFEST.items():
        for step_id, file_list in steps.items():
            for file_path in file_list:
                full_path = REPO_ROOT / file_path
                assert full_path.is_file(), (
                    f"Manifest entry in [{layer_name}][{step_id}] does not exist on disk: {file_path}"
                )


def test_auxiliary_utilities_exist_on_disk():
    """Verify that every file listed in AUXILIARY_UTILITIES physically exists."""
    for file_path, reason in AUXILIARY_UTILITIES.items():
        full_path = REPO_ROOT / file_path
        assert full_path.is_file(), (
            f"Auxiliary utility listed in AUXILIARY_UTILITIES does not exist on disk: {file_path}"
        )
        assert reason and len(reason.strip()) > 10, (
            f"Auxiliary utility {file_path} must have a substantive architectural justification"
        )


def test_no_duplicate_files_across_manifest_layers():
    """Verify that no file is assigned to multiple layers or multiple steps in MANIFEST."""
    seen_files = {}
    for layer_name, steps in MANIFEST.items():
        for step_id, file_list in steps.items():
            for file_path in file_list:
                normalized = str(Path(file_path).as_posix())
                if normalized in seen_files:
                    prev_layer, prev_step = seen_files[normalized]
                    pytest.fail(
                        f"Duplicate test file detected in MANIFEST: '{normalized}' is assigned to both "
                        f"[{prev_layer}][{prev_step}] and [{layer_name}][{step_id}]."
                    )
                seen_files[normalized] = (layer_name, step_id)


def test_no_overlap_between_manifest_and_auxiliary_utilities():
    """Verify that no file is both in MANIFEST and in AUXILIARY_UTILITIES."""
    manifest_files = set()
    for steps in MANIFEST.values():
        for file_list in steps.values():
            for f in file_list:
                manifest_files.add(str(Path(f).as_posix()))

    aux_files = {str(Path(f).as_posix()) for f in AUXILIARY_UTILITIES}
    overlap = manifest_files.intersection(aux_files)
    assert not overlap, (
        f"Files cannot be both in MANIFEST and in AUXILIARY_UTILITIES: {overlap}"
    )


def test_every_repository_test_file_is_authoritatively_classified():
    """
    Self-Checking Governance Invariant:
    Every single test_*.py in tests/ must be declared in exactly one MANIFEST step
    or explicitly declared in AUXILIARY_UTILITIES.
    """
    manifest_files = set()
    for steps in MANIFEST.values():
        for file_list in steps.values():
            for f in file_list:
                manifest_files.add(str(Path(f).as_posix()))

    aux_files = {str(Path(f).as_posix()) for f in AUXILIARY_UTILITIES}

    tests_dir = REPO_ROOT / "tests"
    all_disk_tests = sorted(tests_dir.glob("test_*.py"))

    unclassified_tests = []
    for test_file in all_disk_tests:
        rel_posix = str(test_file.relative_to(REPO_ROOT).as_posix())
        if rel_posix not in manifest_files and rel_posix not in aux_files:
            unclassified_tests.append(rel_posix)

    assert not unclassified_tests, (
        f"Unclassified test files found in tests/:\n"
        + "\n".join(f"  - {f}" for f in unclassified_tests)
        + "\nEvery tests/test_*.py file must be explicitly added to MANIFEST or AUXILIARY_UTILITIES."
    )


def test_manifest_structure_validity():
    """Verify that MANIFEST contains expected layers and steps with valid file entries."""
    expected_layers = {"Layer A", "Layer B", "Layer C", "Layer D1", "Layer D2", "Layer D3", "Layer E"}
    assert set(MANIFEST.keys()) == expected_layers, (
        f"MANIFEST must contain exactly {expected_layers}, got {set(MANIFEST.keys())}"
    )

    for layer_name, steps in MANIFEST.items():
        assert len(steps) > 0, f"Layer {layer_name} must contain at least one step"
        for step_id, file_list in steps.items():
            assert isinstance(file_list, list), f"Step {step_id} must have a list of file paths"
            assert len(file_list) > 0, f"Step {step_id} file list cannot be empty"
            for f in file_list:
                assert f.endswith(".py"), f"Manifest file must be a python file: {f}"


def test_orchestrator_timeout_and_process_tree_termination(tmp_path):
    """
    Self-test for the orchestrator runner:
    Spawns a child process that sleeps for 10 seconds with a 1.0 second timeout.
    Verifies that:
      1. timed_out is True.
      2. exit_code is 124.
      3. Process tree was terminated.
      4. Duration is approx 1.0s (not 10s).
      5. Output contains timeout error message.
    """
    from scripts.test_orchestrator import run_command

    log_file = tmp_path / "timeout_test.log"
    cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
    exit_code, duration, output, timed_out = run_command(
        cmd, cwd=tmp_path, log_file=log_file, verbose=False, timeout_sec=1.0
    )
    assert timed_out is True, "run_command must return timed_out=True when duration exceeds timeout_sec"
    assert exit_code == 124, f"Expected exit_code 124 on timeout, got {exit_code}"
    assert duration < 5.0, f"Process was not killed promptly: duration {duration:.2f}s"
    assert "TIMEOUT ERROR" in output, "Output must contain TIMEOUT ERROR notice"
    assert log_file.is_file(), "Log file must be written even upon timeout"


def test_junit_authoritative_parsing_and_no_false_green(tmp_path):
    """
    Self-test for JUnit parsing:
    Proves that parse_junit_xml accurately extracts passed, failed, skipped, error counts,
    and never manufactures a PASS from missing XML or non-zero exit codes.
    """
    from scripts.test_orchestrator import parse_junit_xml

    # Case 1: Non-existent XML returns 0 counts
    missing_xml = tmp_path / "missing.xml"
    counts, testcases = parse_junit_xml(missing_xml)
    assert counts["total"] == 0
    assert counts["passed"] == 0
    assert counts["failed"] == 0
    assert testcases == []

    # Case 2: Structured XML with pass, fail, skip, error
    sample_xml = tmp_path / "sample.xml"
    sample_xml.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="sample" tests="4" errors="1" failures="1" skipped="1">
    <testcase classname="tests.a" name="test_p" time="0.01" />
    <testcase classname="tests.a" name="test_f" time="0.02">
      <failure message="assertion error">Traceback</failure>
    </testcase>
    <testcase classname="tests.a" name="test_s" time="0.00">
      <skipped message="skipped reason" />
    </testcase>
    <testcase classname="tests.a" name="test_e" time="0.00">
      <error message="runtime error">Crash</error>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    c2, tc2 = parse_junit_xml(sample_xml)
    assert c2["total"] == 4
    assert c2["passed"] == 1
    assert c2["failed"] == 1
    assert c2["skipped"] == 1
    assert c2["errors"] == 1
    assert len(tc2) == 4
    assert tc2[0]["status"] == "PASSED"
    assert tc2[1]["status"] == "FAILED"
    assert tc2[2]["status"] == "SKIPPED"
    assert tc2[3]["status"] == "ERROR"


def test_every_non_test_python_file_is_authoritatively_classified():
    """
    Self-Checking Governance Invariant:
    Every non-test_*.py Python file in tests/ must be:
      1. Declared in MANIFEST (e.g. tests/audit_structural_patterns.py), OR
      2. Explicitly listed in AUXILIARY_UTILITIES, OR
      3. Explicitly declared in DOCUMENTED_REPO_ARTIFACTS (e.g. tests/conftest.py).
    Guarantees ZERO unclassified Python scripts can exist in the tests/ directory.
    """
    manifest_files = set()
    for steps in MANIFEST.values():
        for file_list in steps.values():
            for f in file_list:
                manifest_files.add(str(Path(f).as_posix()))

    aux_files = {str(Path(f).as_posix()) for f in AUXILIARY_UTILITIES}
    repo_artifacts = {str(Path(f).as_posix()) for f in DOCUMENTED_REPO_ARTIFACTS}

    tests_dir = REPO_ROOT / "tests"
    all_non_test_scripts = sorted([
        p for p in tests_dir.glob("*.py")
        if not p.name.startswith("test_")
    ])

    unclassified = []
    for script in all_non_test_scripts:
        rel_posix = str(script.relative_to(REPO_ROOT).as_posix())
        if (
            rel_posix not in manifest_files
            and rel_posix not in aux_files
            and rel_posix not in repo_artifacts
        ):
            unclassified.append(rel_posix)

    assert not unclassified, (
        f"Unclassified non-test Python files found in tests/:\n"
        + "\n".join(f"  - {f}" for f in unclassified)
        + "\nEvery tests/*.py file must be in MANIFEST, AUXILIARY_UTILITIES, or DOCUMENTED_REPO_ARTIFACTS."
    )


def test_manifest_inventory_calculation_invariants():
    """
    Verifies that get_manifest_inventory() computes all counts programmatically
    matching the exact underlying MANIFEST data structure:
      1. reported_layer_file_count == len(manifest_layer_files)
      2. reported_total_pytest_files == sum(all manifest pytest file counts)
      3. standalone_audit_files == len(MANIFEST['Layer A']['A1_structural_patterns'])
      4. total_auxiliary_utilities == len(AUXILIARY_UTILITIES)
      5. total_orchestrated_files == total_pytest_files + standalone_audit_files
    """
    inv = get_manifest_inventory()

    for layer_name, steps in MANIFEST.items():
        expected_files = sum(len(fl) for fl in steps.values())
        assert inv["layer_counts"][layer_name] == expected_files, (
            f"Layer {layer_name} file count mismatch in get_manifest_inventory()"
        )

    expected_total_pytest = sum(
        len(files)
        for layer in MANIFEST.values()
        for step_id, files in layer.items()
        if step_id != "A1_structural_patterns"
    )
    assert inv["total_pytest_files"] == expected_total_pytest
    assert inv["standalone_audit_files"] == len(MANIFEST["Layer A"]["A1_structural_patterns"])
    assert inv["total_auxiliary_utilities"] == len(AUXILIARY_UTILITIES)
    assert inv["total_orchestrated_files"] == expected_total_pytest + inv["standalone_audit_files"]


def test_report_consistency_validation_fails_on_mismatched_counts():
    """
    Regression test: proves that validate_report_consistency rejects fabricated or
    mismatched summary counts with ValueError, preventing false green reports.
    """
    valid_report = {
        "summary": {
            "total": 10,
            "passed": 8,
            "failed": 1,
            "skipped": 1,
            "errors": 0,
            "flaky": 0,
            "timed_out": 0,
        },
        "steps": [
            {
                "step_id": "step_1",
                "status": "PASSED",
                "counts": {
                    "total": 5, "passed": 5, "failed": 0, "skipped": 0,
                    "errors": 0, "flaky": 0, "timed_out": 0,
                },
            },
            {
                "step_id": "step_2",
                "status": "FAILED",
                "counts": {
                    "total": 5, "passed": 3, "failed": 1, "skipped": 1,
                    "errors": 0, "flaky": 0, "timed_out": 0,
                },
            },
        ],
    }

    # Valid payload passes
    validate_report_consistency(valid_report)

    # Tampering 1: summary total inflated
    bad_total = json.loads(json.dumps(valid_report))
    bad_total["summary"]["total"] = 11
    with pytest.raises(ValueError, match="step total sum.*!= summary total"):
        validate_report_consistency(bad_total)

    # Tampering 2: summary passed inflated (leaving summary total matching step sum)
    bad_passed = json.loads(json.dumps(valid_report))
    bad_passed["summary"]["passed"] = 9
    bad_passed["summary"]["failed"] = 0
    with pytest.raises(ValueError, match="step passed sum.*!= summary passed"):
        validate_report_consistency(bad_passed)

    # Tampering 3: internal arithmetic discrepancy in summary (step sums match summary fields, but fields don't sum to total)
    bad_arith = json.loads(json.dumps(valid_report))
    bad_arith["summary"]["total"] = 20
    bad_arith["steps"][0]["counts"]["total"] = 15
    # Here sum_total is 5 + 15 = 20 matching summary["total"], but passed(8) + failed(1) + skipped(1) = 10 != 20
    with pytest.raises(ValueError, match="pipeline total.*does not equal"):
        validate_report_consistency(bad_arith)


def test_resolve_python_executable_portability_and_fallback():
    """
    Verifies that resolve_python_executable():
      1. Returns an existing, functional Python interpreter.
      2. Contains NO developer-specific paths or hardcoded usernames in its implementation.
      3. Correctly falls back to a portable candidate when preferred_py does not exist.
    """
    import inspect
    from scripts import test_orchestrator

    py = resolve_python_executable()
    assert Path(py).is_file(), f"Resolved Python does not exist: {py}"

    src = inspect.getsource(test_orchestrator.resolve_python_executable)
    assert "danjo" not in src.lower(), (
        "resolve_python_executable must not contain developer-specific username 'danjo'"
    )
    assert "appdata" not in src.lower(), (
        "resolve_python_executable must not contain developer-specific AppData paths"
    )

    fallback_py = resolve_python_executable(preferred_py="nonexistent_python_binary_xyz.exe")
    assert Path(fallback_py).is_file(), (
        f"Resolver failed to fall back to a valid interpreter when preferred was missing: {fallback_py}"
    )
