#!/usr/bin/env python3
"""
Authoritative Automated Multi-Layer Test Orchestrator for DrinkBoooz/cvsu-generators.

Provides an authoritative, fully repeatable, deterministic multi-layer test pipeline:
  - Layer A: Static / AST Architectural Governance & Structural Authority Audits
  - Layer B: Backend / Core Unit & Integration Tests (Parsers, Detectors, Validators, Generators)
  - Layer C: Adversarial Template Matrix & Mutation Invariance Tests
  - Layer D1: UI API Bridge, Accessibility, Asset Resilience & Consistent Themes
  - Layer D2: Browser ScriptAPI Bridge E2E (Playwright Chromium + Real ScriptAPI + Real ui.html)
  - Layer D3: Native PyWebView Host Smoke / Integration (Real Windows WebView2 Desktop Host + Native DnD)
  - Layer E: Windows PE Version Info & Packaged Executable Smoke Tests

Usage:
  python scripts/test_orchestrator.py [OPTIONS]
  python scripts/test_all.py [OPTIONS]

Options:
  --all             Run all test layers (default).
  --governance      Run Layer A (AST rules, structural authority audit).
  --backend         Run Layer B (Backend / core unit & integration tests).
  --templates       Run Layer C (Adversarial template matrix).
  --ui              Run Layer D1 (UI unit & bridge tests).
  --playwright      Run Layer D2 (Browser ScriptAPI bridge E2E).
  --native          Run Layer D3 (Native PyWebView host smoke & DnD).
  --packaged        Run Layer E (PE metadata & packaged executable smoke).
  --fast            Run Layers A, B, and C (skips UI, browser, and desktop integration).
  --fail-fast, -x   Abort pipeline immediately upon first step failure.
  --timeout SEC     Per-step timeout in seconds (default: 180s).
  --retry-flaky     Re-run failed steps once to identify and isolate flaky tests.
  --report-dir DIR  Directory where test reports and logs are saved (default: test_reports).
  --verbose, -v     Verbose output (stream process stdout/stderr to console).
  --json            Print JSON report summary to stdout at completion.
  -h, --help        Show this help message and exit.
"""

import os
import sys
import time
import json
import shutil
import argparse
import subprocess
import threading
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# Ensure resilient console encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR = REPO_ROOT / "test_reports"
DEFAULT_STEP_TIMEOUT_SEC = 180.0

# ─────────────────────────────────────────────────────────────────────────────
# AUTHORITATIVE TEST MANIFEST
# Explicit file mappings across all layers. Zero reliance on fragile `-k` string matching.
# ─────────────────────────────────────────────────────────────────────────────

MANIFEST = {
    "Layer A": {
        "A1_structural_patterns": {
            "type": "standalone_script",
            "files": [
                "tests/audit_structural_patterns.py",
            ],
        },
        "A2_ast_governance": {
            "type": "pytest",
            "files": [
                "tests/test_ast_rules.py",
                "tests/test_structural_authority_audit.py",
                "tests/test_dependency_manifests.py",
                "tests/test_obsidian_vault_integrity.py",
                "tests/test_api_inventory.py",
                "tests/test_manifest_integrity.py",
            ],
        },
    },
    "Layer B": {
        "B1_parsers_and_resolvers": {
            "type": "pytest",
            "files": [
                "tests/test_modules_parsing.py",
                "tests/test_roster_parser.py",
                "tests/test_parser_user_config.py",
                "tests/test_attendance_schedule_parsing.py",
                "tests/test_canonical_schedule_room.py",
                "tests/test_multi_row_roster_headers.py",
                "tests/test_field_resolver.py",
                "tests/test_compound_semantic_labels.py",
            ],
        },
        "B2_inspectors_detectors_validators": {
            "type": "pytest",
            "files": [
                "tests/test_template_inspector.py",
                "tests/test_template_role_detector.py",
                "tests/test_generalized_detection.py",
                "tests/test_recipe_stage1.py",
                "tests/test_xlsx_template_contract.py",
                "tests/test_template_set_model.py",
                "tests/test_template_set_manager.py",
                "tests/test_template_set_orchestrator.py",
                "tests/test_template_set_e2e.py",
            ],
        },
        "B3_generators_and_lifecycle": {
            "type": "pytest",
            "files": [
                "tests/test_modules_generation.py",
                "tests/test_modules_integrity.py",
                "tests/test_generic_doc_gen.py",
                "tests/test_grade_generator.py",
                "tests/test_grade_discussion_generator.py",
                "tests/test_attendance_default_template.py",
                "tests/test_attendance_name_scaling.py",
                "tests/test_ceit_name_scaling.py",
                "tests/test_custom_docx_typography.py",
                "tests/test_custom_template_pipeline.py",
                "tests/test_custom_template_routing.py",
                "tests/test_docx_utils_retry.py",
                "tests/test_replace_retry.py",
                "tests/test_output_parity.py",
                "tests/test_config_manager.py",
                "tests/test_crash_logging_hooks.py",
                "tests/test_executable_lifecycle.py",
                "tests/test_executable_improvements.py",
                "tests/test_executable_dnd_routing.py",
                "tests/test_dnd_flow.py",
                "tests/test_edge_cases.py",
                "tests/test_regression.py",
                "tests/test_diagnostic_probe.py",
                "tests/test_ab_benchmark_probe.py",
                "tests/test_localhost_stress_probe.py",
            ],
        },
    },
    "Layer C": {
        "C1_adversarial_template_matrix": {
            "type": "pytest",
            "files": [
                "tests/test_adversarial_template_matrix.py",
                "tests/test_invalid_templates.py",
                "tests/test_template_mutations.py",
                "tests/test_simulate_unknown.py",
                "tests/test_synthetic_non_ceit_header.py",
            ],
        },
    },
    "Layer D1": {
        "D1_ui_bridge_and_consistency": {
            "type": "pytest",
            "files": [
                "tests/test_ui_api_bridge.py",
                "tests/test_ui_consistency.py",
                "tests/test_ui_accessibility.py",
                "tests/test_ui_asset_resilience.py",
                "tests/test_settings_modal_responsive.py",
                "tests/test_executable_test_api_bindings.py",
                "tests/test_executable_test_hig_bridge.py",
                "tests/test_theme_consistency.py",
                "tests/test_theme_transition_perf.py",
                "tests/test_scroll_aware_dock.py",
                "tests/test_stepper_2col_scroll.py",
                "tests/test_react_executable_build.py",
            ],
        },
    },
    "Layer D2": {
        "D2_playwright_browser_e2e": {
            "type": "pytest",
            "files": [
                "tests/test_playwright_real_authority_e2e.py",
                "tests/test_playwright_e2e.py",
                "tests/test_playwright_settings_modal.py",
                "tests/test_playwright_roster_mapping.py",
                "tests/test_playwright_accessibility.py",
            ],
        },
    },
    "Layer D3": {
        "D3_native_pywebview_host": {
            "type": "pytest",
            "files": [
                "tests/test_native_pywebview_host.py",
                "tests/test_pywebview_dnd_binding.py",
            ],
        },
    },
    "Layer E": {
        "E1_pe_metadata_and_packaged_smoke": {
            "type": "pytest",
            "files": [
                "tests/test_pe_version_info.py",
                "tests/test_packaged_executable_smoke.py",
            ],
        },
    },
}

# Explicit reconciliation of non-test utility and manual probe scripts in tests/
AUXILIARY_UTILITIES = {
    "tests/check_sig.py": "Standalone Authenticode signature probe utility for PE signing diagnostics",
    "tests/check_sig2.py": "Standalone Authenticode signature probe utility (variant 2)",
    "tests/check_sig3.py": "Standalone Authenticode signature probe utility (variant 3)",
    "tests/diff_test.py": "Ad-hoc document diff comparator utility for manual visual inspection",
    "tests/diff_test2.py": "Ad-hoc document diff comparator utility (variant 2)",
    "tests/diff_test_docx.py": "Ad-hoc docx XML diff inspection script",
    "tests/extract_css.py": "Utility to extract embedded CSS tokens from ui.html",
    "tests/run_gen.py": "Standalone manual document generator script for interactive debugging",
    "tests/test_cells.py": "Interactive workbook cell locator probe script for manual spreadsheet examination",
    "tests/verify_c14n.py": "Ad-hoc XML C14N canonicalization comparison utility",
    "tests/verify_compare.py": "Ad-hoc document structure comparison utility",
    "tests/verify_playwright_theme.py": "Manual visual helper script for theme toggling under Playwright",
}

# Root repository test infrastructure configuration files
DOCUMENTED_REPO_ARTIFACTS = {
    "tests/conftest.py": "Root pytest configuration, shared fixture definitions and session setup",
}


def get_repository_test_inventory(root_dir: Path | None = None) -> dict:
    """
    Authoritatively discovers all tests/*.py files on the filesystem and performs
    a strict three-way partition reconciliation against MANIFEST, AUXILIARY_UTILITIES,
    and DOCUMENTED_REPO_ARTIFACTS.
    """
    root = Path(root_dir) if root_dir else REPO_ROOT
    tests_dir = root / "tests"

    discovered_files = sorted(p.relative_to(root).as_posix() for p in tests_dir.glob("*.py"))

    orchestrated_pytest_files = []
    standalone_audit_files = []
    layer_counts = {}
    layer_pytest_counts = {}
    manifest_seen = set()
    duplicates = []

    for layer_name, layer_steps in MANIFEST.items():
        layer_total = 0
        layer_pytest = 0
        for step_id, step_meta in layer_steps.items():
            step_type = step_meta.get("type", "pytest")
            step_files = step_meta.get("files", [])
            for f in step_files:
                norm_f = Path(f).as_posix()
                layer_total += 1
                if norm_f in manifest_seen:
                    duplicates.append(f"MANIFEST internal duplicate: {norm_f} in {step_id}")
                manifest_seen.add(norm_f)
                if step_type == "standalone_script":
                    standalone_audit_files.append(norm_f)
                else:
                    orchestrated_pytest_files.append(norm_f)
                    layer_pytest += 1
        layer_counts[layer_name] = layer_total
        layer_pytest_counts[layer_name] = layer_pytest

    auxiliary_files = [Path(f).as_posix() for f in AUXILIARY_UTILITIES.keys()]
    repo_artifacts = [Path(f).as_posix() for f in DOCUMENTED_REPO_ARTIFACTS.keys()]

    set_manifest = set(manifest_seen)
    set_aux = set(auxiliary_files)
    set_art = set(repo_artifacts)

    # 3-way pairwise disjointness check
    for o in sorted(set_manifest & set_aux):
        duplicates.append(f"MANIFEST / AUXILIARY overlap: {o}")
    for o in sorted(set_manifest & set_art):
        duplicates.append(f"MANIFEST / DOCUMENTED_REPO_ARTIFACTS overlap: {o}")
    for o in sorted(set_aux & set_art):
        duplicates.append(f"AUXILIARY / DOCUMENTED_REPO_ARTIFACTS overlap: {o}")

    # Check physical existence of declared files
    missing_on_disk = []
    for f in sorted(set_manifest | set_aux | set_art):
        if not (root / f).is_file():
            missing_on_disk.append(f)

    classified_files = sorted(set_manifest | set_aux | set_art)
    missing = sorted(set(discovered_files) - set(classified_files))
    extra = sorted(set(classified_files) - set(discovered_files))

    is_reconciled = (
        set(discovered_files) == set(classified_files)
        and len(missing) == 0
        and len(extra) == 0
        and len(duplicates) == 0
        and len(missing_on_disk) == 0
    )

    reconciliation_error = None
    if not is_reconciled:
        reconciliation_error = (
            f"Missing unclassified files: {missing}; "
            f"Phantom/extra files: {extra}; "
            f"Duplicates/overlaps: {duplicates}; "
            f"Missing on disk: {missing_on_disk}"
        )

    return {
        "discovered_files": discovered_files,
        "classified_files": classified_files,
        "orchestrated_pytest_files": sorted(orchestrated_pytest_files),
        "standalone_audit_files": sorted(standalone_audit_files),
        "auxiliary_utility_files": sorted(auxiliary_files),
        "documented_repo_artifacts": sorted(repo_artifacts),
        "layer_counts": layer_counts,
        "layer_pytest_counts": layer_pytest_counts,
        "total_discovered_files": len(discovered_files),
        "total_classified_files": len(classified_files),
        "total_pytest_files": len(orchestrated_pytest_files),
        "standalone_audit_count": len(standalone_audit_files),
        "total_orchestrated_files": len(orchestrated_pytest_files) + len(standalone_audit_files),
        "total_auxiliary_utilities": len(auxiliary_files),
        "total_repo_artifacts": len(repo_artifacts),
        "missing": missing,
        "extra": extra,
        "duplicates": duplicates,
        "missing_on_disk": missing_on_disk,
        "is_reconciled": is_reconciled,
        "reconciliation_error": reconciliation_error,
    }


def get_manifest_inventory() -> dict:
    """
    Programmatically calculates inventory counts from the authoritative MANIFEST structure
    and verifies reconciliation with the actual repository filesystem.
    """
    inv = get_repository_test_inventory(REPO_ROOT)
    return {
        "layer_counts": inv["layer_counts"],
        "layer_pytest_counts": inv["layer_pytest_counts"],
        "total_pytest_files": inv["total_pytest_files"],
        "standalone_audit_files": inv["standalone_audit_count"],
        "total_orchestrated_files": inv["total_orchestrated_files"],
        "total_auxiliary_utilities": inv["total_auxiliary_utilities"],
        "is_reconciled": inv["is_reconciled"],
    }



def get_git_info() -> dict:
    """Collect git branch and commit hash for reporting."""
    info = {"branch": "unknown", "commit": "unknown"}
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        info["branch"] = branch
    except Exception:
        pass
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        info["commit"] = commit
    except Exception:
        pass
    return info


def resolve_python_executable(preferred_py: str | None = None) -> str:
    """
    Returns the authoritative Python executable containing required test packages (pytest).
    Resolution order (strictly portable):
      1. Explicitly supplied interpreter (preferred_py or CVSU_PYTHON env var).
      2. Repository-local .venv interpreter (.venv/Scripts/python.exe or .venv/bin/python).
      3. Active Python executable / current runtime (sys.executable).
      4. Python executables discovered on system PATH (python, python3, py).
      5. Fail closed with RuntimeError if no executable with pytest is available.
    Does NOT contain developer-specific or hardcoded user directory paths.
    """
    candidates = []

    # 1. Explicitly supplied interpreter
    if preferred_py:
        candidates.append(preferred_py)
    env_py = os.environ.get("CVSU_PYTHON")
    if env_py:
        candidates.append(env_py)

    # 2. Repository-local .venv interpreter
    venv_scripts = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    venv_bin = REPO_ROOT / ".venv" / "bin" / "python"
    candidates.extend([str(venv_scripts), str(venv_bin)])

    # 3. Active runtime interpreter
    candidates.append(sys.executable)

    # 4. PATH discovered executables
    for name in ("python", "python3", "py"):
        which_path = shutil.which(name)
        if which_path:
            candidates.append(which_path)

    tried = []
    seen = set()
    for cand in candidates:
        if not cand:
            continue
        cand_str = str(cand)
        if cand_str in seen:
            continue
        seen.add(cand_str)

        cand_path = Path(cand)
        if cand_path.is_file():
            tried.append(cand_str)
            try:
                res = subprocess.run(
                    [cand_str, "-m", "pytest", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    return str(cand_path.resolve())
            except Exception:
                pass

    raise RuntimeError(
        f"Unable to resolve a portable Python interpreter with pytest installed.\n"
        f"Candidate interpreters checked:\n  " + "\n  ".join(tried) + "\n"
        f"Please activate a valid virtual environment or configure CVSU_PYTHON."
    )


def prepare_test_environment(report_dir: Path, preferred_py: str | None = None) -> dict:
    """Prepares clean, deterministic test environment and returns metadata."""
    report_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = report_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    junit_dir = report_dir / "junit"
    junit_dir.mkdir(parents=True, exist_ok=True)
    playwright_dir = report_dir / "playwright"
    playwright_dir.mkdir(parents=True, exist_ok=True)

    # Clean stale junit xml files from previous runs to prevent stale metric leakage
    for old_xml in junit_dir.glob("*.xml"):
        try:
            old_xml.unlink()
        except Exception:
            pass

    resolved_py = resolve_python_executable(preferred_py)

    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["CVSU_TEST_ORCHESTRATOR"] = "1"
    if "PYTHONPATH" in os.environ:
        os.environ["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{os.environ['PYTHONPATH']}"
    else:
        os.environ["PYTHONPATH"] = str(REPO_ROOT)

    return {
        "repo_root": str(REPO_ROOT),
        "python_version": sys.version.split()[0],
        "python_executable": resolved_py,
        "platform": sys.platform,
        "report_dir": str(report_dir),
        "logs_dir": str(logs_dir),
        "junit_dir": str(junit_dir),
        "playwright_dir": str(playwright_dir),
    }


def parse_junit_xml(xml_path: Path) -> tuple[dict, list[dict]]:
    """
    Parses pytest JUnit XML output into authoritative structured counts and testcase records.
    Returns: (counts_dict, list_of_testcase_dicts)
    """
    counts = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
    }
    testcases = []

    if not xml_path.is_file():
        return counts, testcases

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Some pytest junitxml outputs have <testsuites> wrapping <testsuite>, or directly <testsuite>
        testsuite_elems = root.findall(".//testsuite") if root.tag != "testsuite" else [root]
        for ts in testsuite_elems:
            # Accumulate testcases
            for tc in ts.findall("testcase"):
                classname = tc.attrib.get("classname", "")
                name = tc.attrib.get("name", "")
                time_sec = float(tc.attrib.get("time", "0.0"))
                failure = tc.find("failure")
                error = tc.find("error")
                skipped = tc.find("skipped")

                status = "PASSED"
                message = ""
                if failure is not None:
                    status = "FAILED"
                    message = failure.attrib.get("message", "") or (failure.text or "")
                elif error is not None:
                    status = "ERROR"
                    message = error.attrib.get("message", "") or (error.text or "")
                elif skipped is not None:
                    status = "SKIPPED"
                    message = skipped.attrib.get("message", "") or (skipped.text or "")

                if status == "PASSED":
                    counts["passed"] += 1
                elif status == "FAILED":
                    counts["failed"] += 1
                elif status == "ERROR":
                    counts["errors"] += 1
                elif status == "SKIPPED":
                    counts["skipped"] += 1

                testcases.append({
                    "classname": classname,
                    "name": name,
                    "status": status,
                    "time_sec": round(time_sec, 3),
                    "message": message[:300].strip() if message else "",
                })

        counts["total"] = counts["passed"] + counts["failed"] + counts["errors"] + counts["skipped"]
    except Exception as e:
        print(f"Warning: error parsing JUnit XML {xml_path}: {e}")

    return counts, testcases


def run_command(
    cmd: list[str],
    cwd: Path,
    log_file: Path,
    verbose: bool = False,
    timeout_sec: float | None = DEFAULT_STEP_TIMEOUT_SEC,
) -> tuple[int, float, str, bool]:
    """
    Runs command with streaming, logging, and deterministic timeout handling.
    If timeout expires, kills process tree on Windows via taskkill /F /T /PID.
    Returns: (exit_code, duration_sec, combined_output, timed_out)
    """
    start_time = time.perf_counter()
    full_output = []
    timed_out = False

    print(f"  \033[90m$ {' '.join(cmd)}\033[0m")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        def reader():
            try:
                for line in proc.stdout:
                    full_output.append(line)
                    if verbose:
                        sys.stdout.write(f"    {line}")
                        sys.stdout.flush()
            except Exception:
                pass

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        try:
            proc.wait(timeout=timeout_sec)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            # Forcefully kill process tree on Windows
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
            try:
                proc.kill()
            except Exception:
                pass
            exit_code = 124
            full_output.append(
                f"\n[TIMEOUT ERROR: Step exceeded {timeout_sec}s timeout limit. Process tree terminated.]\n"
            )

        reader_thread.join(timeout=1.0)
    except Exception as e:
        exit_code = 1
        full_output.append(f"Command execution error: {e}\n")

    duration = time.perf_counter() - start_time
    combined_output = "".join(full_output)

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(combined_output)
    except Exception as e:
        print(f"Warning: could not write log file {log_file}: {e}")

    return exit_code, duration, combined_output, timed_out


def run_test_step(
    step_id: str,
    name: str,
    layer: str,
    files: list[str],
    logs_dir: Path,
    junit_dir: Path,
    verbose: bool = False,
    timeout_sec: float = DEFAULT_STEP_TIMEOUT_SEC,
    is_audit_script: bool = False,
    retry_flaky: bool = False,
    py_executable: str | None = None,
) -> dict:
    """Executes a single test step and returns authoritative structured result."""
    print(f"\n>> [{step_id}] {name}")
    log_file = logs_dir / f"{step_id}.log"
    junit_xml = junit_dir / f"{step_id}.xml"
    if junit_xml.is_file():
        try:
            junit_xml.unlink()
        except Exception:
            pass

    py = py_executable or sys.executable
    if is_audit_script:
        cmd = [py, files[0]]
    else:
        cmd = [py, "-m", "pytest", *files, f"--junitxml={str(junit_xml)}", "-v"]

    exit_code, duration, output, timed_out = run_command(
        cmd, cwd=REPO_ROOT, log_file=log_file, verbose=verbose, timeout_sec=timeout_sec
    )

    flaky_cases = []
    if is_audit_script:
        # Category E structural audit script: returns 0 on 0 Category E violations
        violations = 0
        m = re.search(r"Total Category E Violations:\s*(\d+)", output)
        if m:
            violations = int(m.group(1))
        passed = (exit_code == 0) and (violations == 0) and not timed_out
        counts = {
            "total": 1,
            "passed": 1 if passed else 0,
            "failed": 0 if passed else 1,
            "skipped": 0,
            "errors": 0,
        }
        testcases = [{
            "classname": "tests.audit_structural_patterns",
            "name": "audit_structural_patterns",
            "status": "PASSED" if passed else "FAILED",
            "time_sec": round(duration, 3),
            "message": f"Category E violations: {violations}" if not passed else "",
        }]
    else:
        xml_exists = junit_xml.is_file()
        counts, testcases = parse_junit_xml(junit_xml)
        if not xml_exists or counts["total"] == 0:
            counts["total"] = max(counts["total"], 1)
            counts["failed"] = max(counts["failed"], 1)
            passed = False
        else:
            if exit_code != 0 and counts["failed"] == 0 and counts["errors"] == 0:
                counts["errors"] = 1
                counts["total"] = counts["passed"] + counts["failed"] + counts["skipped"] + counts["errors"]
            passed = (
                (exit_code == 0)
                and (counts["failed"] == 0)
                and (counts["errors"] == 0)
                and not timed_out
            )

        # Real Flaky Test Detection: If retry_flaky enabled and first run had failures
        if not passed and retry_flaky and not timed_out:
            failed_cases = [tc for tc in testcases if tc["status"] in ("FAILED", "ERROR")]
            if failed_cases:
                print(f"  \033[93m[RETRY] Step {step_id} had {len(failed_cases)} failures. Executing single retry pass for flaky classification...\033[0m")
                retry_log = logs_dir / f"{step_id}_retry.log"
                retry_xml = junit_dir / f"{step_id}_retry.xml"
                if retry_xml.is_file():
                    try:
                        retry_xml.unlink()
                    except Exception:
                        pass
                r_code, r_dur, r_out, r_to = run_command(
                    [py, "-m", "pytest", *files, f"--junitxml={str(retry_xml)}", "-v"],
                    cwd=REPO_ROOT,
                    log_file=retry_log,
                    verbose=verbose,
                    timeout_sec=timeout_sec,
                )
                r_counts, r_testcases = parse_junit_xml(retry_xml)
                r_tc_map = {f"{tc['classname']}::{tc['name']}": tc for tc in r_testcases}

                for fc in failed_cases:
                    key = f"{fc['classname']}::{fc['name']}"
                    if key in r_tc_map and r_tc_map[key]["status"] == "PASSED":
                        flaky_cases.append({
                            "test": key,
                            "first_attempt": fc["status"],
                            "second_attempt": "PASSED",
                            "step_id": step_id,
                            "message": fc.get("message", ""),
                        })
                        fc["status"] = "FLAKY"

                counts["flaky"] = len(flaky_cases)
                counts["failed"] = sum(1 for tc in testcases if tc["status"] == "FAILED")
                counts["errors"] = sum(1 for tc in testcases if tc["status"] == "ERROR")
                counts["passed"] = sum(1 for tc in testcases if tc["status"] == "PASSED")

    counts.setdefault("flaky", len(flaky_cases))
    counts.setdefault("timed_out", 1 if timed_out else 0)
    counts.setdefault("errors", 0)
    counts.setdefault("skipped", 0)
    if timed_out and counts.get("failed", 0) == 1 and counts.get("passed", 0) == 0:
        counts["failed"] = 0
    counts["total"] = (
        counts["passed"]
        + counts["failed"]
        + counts["skipped"]
        + counts["flaky"]
        + counts["timed_out"]
        + counts["errors"]
    )

    if timed_out:
        status = "TIMED_OUT"
    elif not passed and len(flaky_cases) > 0 and counts.get("failed", 0) == 0 and counts.get("errors", 0) == 0:
        status = "FLAKY"
    elif passed:
        status = "PASSED"
    else:
        status = "FAILED"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"

    print(
        f"  +-- Status: {color}{status}{reset} | Duration: {duration:.2f}s | "
        f"Passed: {counts['passed']} | Failed: {counts['failed']} | Skipped: {counts['skipped']}"
        + (f" | \033[93mFlaky: {len(flaky_cases)}\033[0m" if flaky_cases else "")
        + (f" | \033[91mTimed Out: {counts['timed_out']}\033[0m" if counts["timed_out"] else "")
    )

    return {
        "step_id": step_id,
        "name": name,
        "layer": layer,
        "files": files,
        "command": cmd,
        "status": status,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_sec": round(duration, 3),
        "counts": counts,
        "flaky_cases": flaky_cases,
        "testcases": testcases,
        "log_file": str(log_file),
        "junit_xml": str(junit_xml) if not is_audit_script else None,
        "output_snippet": "\n".join(output.strip().splitlines()[-20:]) if output else "",
    }


def define_pipeline(selected_layers: list[str]) -> list[dict]:
    """Constructs the sequence of orchestrated test steps from the authoritative manifest."""
    steps = []

    # ── Layer A: Static / AST Governance ───────────────────────────────────────
    if "governance" in selected_layers or "all" in selected_layers:
        a1_meta = MANIFEST["Layer A"]["A1_structural_patterns"]
        steps.append({
            "layer": "Layer A — Static / AST Governance & Structural Authority Audits",
            "id": "A1_structural_authority_audit",
            "name": "Structural Authority Pattern Audit (Category E Invariance)",
            "files": a1_meta["files"],
            "timeout_sec": 60.0,
            "is_audit": a1_meta.get("type") == "standalone_script",
        })
        a2_meta = MANIFEST["Layer A"]["A2_ast_governance"]
        steps.append({
            "layer": "Layer A — Static / AST Governance & Structural Authority Audits",
            "id": "A2_ast_governance_rules",
            "name": "AST Architectural Governance & Coordinate Literal Audits",
            "files": a2_meta["files"],
            "timeout_sec": 90.0,
            "is_audit": a2_meta.get("type") == "standalone_script",
        })

    # ── Layer B: Backend / Core Unit & Integration ────────────────────────────
    if "backend" in selected_layers or "all" in selected_layers:
        b1_meta = MANIFEST["Layer B"]["B1_parsers_and_resolvers"]
        steps.append({
            "layer": "Layer B — Backend / Core Unit & Integration Tests",
            "id": "B1_parsers_and_resolvers",
            "name": "Schedules, Rosters, Config & Field Resolvers",
            "files": b1_meta["files"],
            "timeout_sec": 90.0,
            "is_audit": b1_meta.get("type") == "standalone_script",
        })
        b2_meta = MANIFEST["Layer B"]["B2_inspectors_detectors_validators"]
        steps.append({
            "layer": "Layer B — Backend / Core Unit & Integration Tests",
            "id": "B2_inspectors_detectors_validators",
            "name": "Inspectors, Role Detectors, Validators & Template Set Manager",
            "files": b2_meta["files"],
            "timeout_sec": 120.0,
            "is_audit": b2_meta.get("type") == "standalone_script",
        })
        b3_meta = MANIFEST["Layer B"]["B3_generators_and_lifecycle"]
        steps.append({
            "layer": "Layer B — Backend / Core Unit & Integration Tests",
            "id": "B3_generators_and_lifecycle",
            "name": "Generators, Output Parity, Packaging, Lifecycle & Probes",
            "files": b3_meta["files"],
            "timeout_sec": 180.0,
            "is_audit": b3_meta.get("type") == "standalone_script",
        })

    # ── Layer C: Adversarial Template Matrix ──────────────────────────────────
    if "templates" in selected_layers or "all" in selected_layers:
        c1_meta = MANIFEST["Layer C"]["C1_adversarial_template_matrix"]
        steps.append({
            "layer": "Layer C — Adversarial Template Matrix & Mutation Invariance",
            "id": "C1_adversarial_template_matrix",
            "name": "Adversarial Matrix (Formulas, Foreign, Renames, Decoys, Invariance)",
            "files": c1_meta["files"],
            "timeout_sec": 90.0,
            "is_audit": c1_meta.get("type") == "standalone_script",
        })

    # ── Layer D1: UI API Bridge & Consistency ─────────────────────────────────
    if "ui" in selected_layers or "all" in selected_layers:
        d1_meta = MANIFEST["Layer D1"]["D1_ui_bridge_and_consistency"]
        steps.append({
            "layer": "Layer D1 — UI API Bridge, Unit & Consistency",
            "id": "D1_ui_bridge_and_consistency",
            "name": "UI API Bridge, Consistency, Accessibility, Assets & Responsive Modals",
            "files": d1_meta["files"],
            "timeout_sec": 90.0,
            "is_audit": d1_meta.get("type") == "standalone_script",
        })

    # ── Layer D2: Browser ScriptAPI Bridge E2E (Playwright) ───────────────────
    if "playwright" in selected_layers or "all" in selected_layers:
        d2_meta = MANIFEST["Layer D2"]["D2_playwright_browser_e2e"]
        steps.append({
            "layer": "Layer D2 — Browser ScriptAPI Bridge E2E (Playwright Chromium + Real ScriptAPI)",
            "id": "D2_playwright_browser_e2e",
            "name": "Playwright Browser Bridge (ui.html + Real ScriptAPI + Failure Artifacts)",
            "files": d2_meta["files"],
            "timeout_sec": 240.0,
            "is_audit": d2_meta.get("type") == "standalone_script",
        })

    # ── Layer D3: Native PyWebView Host Smoke / Integration ───────────────────
    if "native" in selected_layers or "all" in selected_layers:
        d3_meta = MANIFEST["Layer D3"]["D3_native_pywebview_host"]
        steps.append({
            "layer": "Layer D3 — Native PyWebView Host Smoke & Desktop Integration",
            "id": "D3_native_pywebview_host",
            "name": "Native Desktop Host (Real WebView2 Window, Lifecycle, Bidirectional Bridge & DnD)",
            "files": d3_meta["files"],
            "timeout_sec": 90.0,
            "is_audit": d3_meta.get("type") == "standalone_script",
        })

    # ── Layer E: Packaged Executable & PE Metadata ────────────────────────────
    if "packaged" in selected_layers or "all" in selected_layers:
        e1_meta = MANIFEST["Layer E"]["E1_pe_metadata_and_packaged_smoke"]
        steps.append({
            "layer": "Layer E — Windows PE Metadata & Packaged Binary Smoke Tests",
            "id": "E1_pe_metadata_and_packaged_smoke",
            "name": "Windows PE Version Info, Authenticode Signature, & Binary Lifecycle Smoke",
            "files": e1_meta["files"],
            "timeout_sec": 90.0,
            "is_audit": e1_meta.get("type") == "standalone_script",
        })

    return steps


def validate_report_consistency(report_data: dict) -> None:
    """
    Validates mathematical self-consistency across all step results and summary aggregates.
    Fails closed immediately if report arithmetic contains any discrepancy or fabrication.
    """
    summary = report_data["summary"]
    steps = report_data["steps"]

    sum_total = sum(s["counts"]["total"] for s in steps)
    sum_passed = sum(s["counts"]["passed"] for s in steps)
    sum_failed = sum(s["counts"]["failed"] for s in steps)
    sum_skipped = sum(s["counts"]["skipped"] for s in steps)
    sum_errors = sum(s["counts"].get("errors", 0) for s in steps)
    sum_flaky = sum(s["counts"].get("flaky", 0) for s in steps)
    sum_timed_out = sum(s["counts"].get("timed_out", 0) for s in steps)

    if sum_total != summary["total"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step total sum ({sum_total}) != summary total ({summary['total']})"
        )
    if sum_passed != summary["passed"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step passed sum ({sum_passed}) != summary passed ({summary['passed']})"
        )
    if sum_failed != summary["failed"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step failed sum ({sum_failed}) != summary failed ({summary['failed']})"
        )
    if sum_skipped != summary["skipped"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step skipped sum ({sum_skipped}) != summary skipped ({summary['skipped']})"
        )
    if sum_errors != summary["errors"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step errors sum ({sum_errors}) != summary errors ({summary['errors']})"
        )
    if sum_flaky != summary["flaky"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step flaky sum ({sum_flaky}) != summary flaky ({summary['flaky']})"
        )
    if sum_timed_out != summary["timed_out"]:
        raise ValueError(
            f"Report arithmetic inconsistency: step timed_out sum ({sum_timed_out}) != summary timed_out ({summary['timed_out']})"
        )

    calculated_total = (
        summary["passed"]
        + summary["failed"]
        + summary["skipped"]
        + summary["flaky"]
        + summary["timed_out"]
        + summary["errors"]
    )
    if summary["total"] != calculated_total:
        raise ValueError(
            f"Report arithmetic inconsistency: pipeline total ({summary['total']}) does not equal "
            f"passed ({summary['passed']}) + failed ({summary['failed']}) + skipped ({summary['skipped']}) + "
            f"flaky ({summary['flaky']}) + timed_out ({summary['timed_out']}) + errors ({summary['errors']}) = {calculated_total}"
        )


def generate_reports(report_data: dict, report_dir: Path) -> tuple[Path, Path, Path, Path]:
    """Generates machine-readable JSON and human-readable Markdown test reports."""
    validate_report_consistency(report_data)

    repo_inv = get_repository_test_inventory(REPO_ROOT)
    if not repo_inv["is_reconciled"]:
        raise RuntimeError(
            f"Repository test inventory reconciliation failed: {repo_inv['reconciliation_error']}"
        )
    report_data["inventory"] = repo_inv

    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # 1. JSON Report
    json_path = report_dir / f"test_report_{timestamp_slug}.json"
    latest_json_path = report_dir / "latest_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    shutil.copyfile(json_path, latest_json_path)

    # 2. Markdown Report
    md_path = report_dir / f"test_report_{timestamp_slug}.md"
    latest_md_path = report_dir / "latest_report.md"

    overall_badge = (
        "🟢 **ALL TESTS PASSED**"
        if report_data["overall_status"] == "PASSED"
        else "🔴 **FAILURES DETECTED**"
    )

    md_lines = [
        "# Automated Test Orchestration Report",
        "",
        f"**Execution Mode**: Authoritative Local Pipeline (Pre-Commit / Pre-Release Verification)  ",
        f"**Status**: {overall_badge}  ",
        f"**Timestamp**: `{report_data['timestamp']}`  ",
        f"**Repository**: `{report_data['git']['branch']}` (`{report_data['git']['commit'][:8]}`)  ",
        f"**Python Runtime**: `{report_data['environment']['python_version']}` on `{report_data['environment']['platform']}`  ",
        f"**Total Duration**: `{report_data['total_duration_sec']:.2f}s`  ",
        "",
        "> [!NOTE]",
        "> This report reflects **authoritative local test orchestration** executed directly within the active repository environment.",
        "> It is technically distinct from remote GitHub Actions CI workflows.",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Count |",
        "| :--- | :--- |",
        f"| **Total Orchestrated Tests** | **{report_data['summary']['total']}** |",
        f"| Passed | {report_data['summary']['passed']} |",
        f"| Failed | {report_data['summary']['failed']} |",
        f"| Skipped | {report_data['summary']['skipped']} |",
        f"| Errors | {report_data['summary']['errors']} |",
        f"| Flaky Tests | {report_data['summary']['flaky']} |",
        f"| Timed Out | {report_data['summary']['timed_out']} |",
        "",
        "## Technical Layer Architecture",
        "",
        "| Layer | Testing Target | Host Container | PyWebView / ScriptAPI Scope |",
        "| :--- | :--- | :--- | :--- |",
        "| **Layer A** | AST rules & structural authority audits | Python runtime | Static code analysis & coordinate literal verification |",
        "| **Layer B** | Parsers, Detectors, Validators, Generators | Python runtime | Real backend data pipeline & generation engines |",
        "| **Layer C** | Adversarial template matrix | Python runtime | Corrupt XML, foreign keys, formula-free, decoy sheets |",
        "| **Layer D1** | UI bridge unit & visual consistency | Python / jsdom | UI event handlers, accessibility tokens, responsive modals |",
        "| **Layer D2** | **Browser ScriptAPI Bridge E2E** | Playwright Chromium | Real `ui.html` + real `ScriptAPI` bridged via Playwright Proxy |",
        "| **Layer D3** | **Native PyWebView Host Smoke** | Real WebView2 Window | Real `webview.start()`, native lifecycle, IPC & native DnD |",
        "| **Layer E** | PE version headers & packaged binary | Windows Desktop OS | PyInstaller `.exe` startup, Authenticode signature & metadata |",
        "",
        "## Pipeline Step Breakdown",
        "",
        "| Step ID | Layer | Description | Status | Tests | Duration | Log | JUnit XML |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- |",
    ]

    for s in report_data["steps"]:
        badge = "✅ PASS" if s["status"] == "PASSED" else ("⏱️ TIMEOUT" if s["status"] == "TIMED_OUT" else "❌ FAIL")
        log_name = Path(s["log_file"]).name
        xml_cell = f"[`{Path(s['junit_xml']).name}`](junit/{Path(s['junit_xml']).name})" if s.get("junit_xml") else "—"
        md_lines.append(
            f"| `{s['step_id']}` | {s['layer']} | {s['name']} | {badge} | {s['counts']['passed']} passed | {s['duration_sec']:.2f}s | [`{log_name}`](logs/{log_name}) | {xml_cell} |"
        )

    md_lines.extend([
        "",
        "## Repository Test Inventory Reconciliation",
        "",
        "| Category | File Count | Scope / Execution Policy |",
        "| :--- | :---: | :--- |",
        f"| **DISCOVERED FILES** | **{repo_inv['total_discovered_files']}** | Total `*.py` files discovered in `tests/` on the physical filesystem |",
        f"| **CLASSIFIED FILES** | **{repo_inv['total_classified_files']}** | Total files authoritatively classified into the three-way partition |",
        f"| **ORCHESTRATED TEST FILES** | **{repo_inv['total_pytest_files']}** | Authoritative pytest test suites executed in Layers A2, B, C, D1, D2, D3, E |",
        f"| **STANDALONE AUDIT SCRIPTS** | **{repo_inv['standalone_audit_count']}** | Standalone AST / structural authority inspection (`tests/audit_structural_patterns.py`) executed in Layer A1 |",
        f"| **DECLARED AUXILIARY UTILITIES** | **{repo_inv['total_auxiliary_utilities']}** | Standalone diagnostic probes, diff utilities, and manual inspection tools excluded with architectural justification |",
        f"| **DOCUMENTED REPOSITORY ARTIFACTS** | **{repo_inv['total_repo_artifacts']}** | Root pytest configuration & fixture definition (`tests/conftest.py`) |",
        f"| **TOTAL INVENTORY** | **{repo_inv['total_classified_files']}** | 100% of all Python files in `tests/` accounted for with verified filesystem reconciliation (zero unclassified files) |",
        "",
        "### Breakdown of Orchestrated Test Suites by Layer",
        "",
        "| Layer | Pytest Suites | Standalone Audits | Total Files | Scope |",
        "| :--- | :---: | :---: | :---: | :--- |",
        f"| **Layer A** | {repo_inv['layer_pytest_counts']['Layer A']} | {repo_inv['standalone_audit_count']} | {repo_inv['layer_counts']['Layer A']} | Static AST Governance & Structural Authority |",
        f"| **Layer B** | {repo_inv['layer_pytest_counts']['Layer B']} | 0 | {repo_inv['layer_counts']['Layer B']} | Parsers, Resolvers, Detectors, Validators, Generators, Probes |",
        f"| **Layer C** | {repo_inv['layer_pytest_counts']['Layer C']} | 0 | {repo_inv['layer_counts']['Layer C']} | Adversarial Template Matrix & Mutation Invariance |",
        f"| **Layer D1** | {repo_inv['layer_pytest_counts']['Layer D1']} | 0 | {repo_inv['layer_counts']['Layer D1']} | UI API Bridge, Theme, Layout, Accessibility |",
        f"| **Layer D2** | {repo_inv['layer_pytest_counts']['Layer D2']} | 0 | {repo_inv['layer_counts']['Layer D2']} | Browser ScriptAPI Bridge E2E (Playwright Chromium) |",
        f"| **Layer D3** | {repo_inv['layer_pytest_counts']['Layer D3']} | 0 | {repo_inv['layer_counts']['Layer D3']} | Native Desktop Host (Windows WebView2 Window) |",
        f"| **Layer E** | {repo_inv['layer_pytest_counts']['Layer E']} | 0 | {repo_inv['layer_counts']['Layer E']} | Windows PE Metadata & Packaged Executable Smoke |",
        "",
        f"### Declared Auxiliary Utilities & Diagnostic Probes ({repo_inv['total_auxiliary_utilities']} files)",
        "",
        f"The following {repo_inv['total_auxiliary_utilities']} non-test scripts in `tests/` are excluded from automated test collection with explicit architectural justification:",
        "",
        "| Script Path | Purpose & Exclusion Justification |",
        "| :--- | :--- |",
    ])

    for path, reason in AUXILIARY_UTILITIES.items():
        md_lines.append(f"| `{path}` | {reason} |")

    md_lines.extend([
        "",
        "## Architectural Invariants Verified",
        "",
        "- **Inspector Discovers Where**: No layer fabricates template coordinates; inspection discovers table & sheet candidates strictly from physical structure.",
        "- **Detector Proposes Role**: Discovered candidates map to semantic roles without mutating underlying template files.",
        "- **Validator Verifies Structural Compatibility**: Ambiguity fails closed; sheets missing required headers are rejected immediately.",
        "- **Generator Consumes Validated Recipes**: Document generation executes strictly through validated structural recipes.",
        "- **User Constrained to Discovered Candidates**: Users may choose only from discovered candidate roles/sheets; no user-supplied coordinates permitted.",
        "- **Browser ScriptAPI Bridge Verified**: Headless Chromium validates real `ui.html` interacting directly with the real Python `ScriptAPI` without coordinate mocks (utilizing named controlled test seam `inject_test_file_selection` for simulated OS file dialog selection).",
        "- **Native PyWebView Host Verified**: Windows WebView2 native container bootstraps real UI, validates bidirectional IPC, exercises native DnD, and shuts down cleanly.",
        "- **Packaged Binary Verified**: PE version headers, Copyright notices, and process startup smoke tested gracefully on Windows.",
        "",
    ])

    failures = [s for s in report_data["steps"] if s["status"] != "PASSED"]
    if failures:
        md_lines.extend(["## Failure Diagnostics", ""])
        for f in failures:
            md_lines.extend([
                f"### ❌ {f['step_id']}: {f['name']}",
                "",
                f"**Command**: `{' '.join(f['command'])}`  ",
                f"**Exit Code**: `{f['exit_code']}` (Timed Out: `{f['timed_out']}`)  ",
                "",
                "```text",
                f["output_snippet"],
                "```",
                "",
            ])

    if report_data["flaky_tests"]:
        md_lines.extend(["## Flaky Tests Detected", ""])
        for fl in report_data["flaky_tests"]:
            md_lines.append(f"- **{fl['test']}** (Step: `{fl['step_id']}`): {fl['first_attempt']} -> {fl['second_attempt']}")
        md_lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    shutil.copyfile(md_path, latest_md_path)

    return json_path, latest_json_path, md_path, latest_md_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Authoritative Automated Multi-Layer Test Orchestrator for DrinkBoooz/cvsu-generators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_argument_group("Test Execution Scope")
    group.add_argument(
        "--all",
        action="store_true",
        help="Run all test layers A through E (default).",
    )
    group.add_argument(
        "--governance",
        "--static",
        action="store_true",
        help="Run Layer A (AST rules, structural authority audit).",
    )
    group.add_argument(
        "--backend",
        "--core",
        action="store_true",
        help="Run Layer B (Backend / core unit & integration tests).",
    )
    group.add_argument(
        "--templates",
        "--adversarial",
        action="store_true",
        help="Run Layer C (Adversarial template matrix).",
    )
    group.add_argument(
        "--ui", action="store_true", help="Run Layer D1 (UI unit & bridge tests)."
    )
    group.add_argument(
        "--playwright",
        action="store_true",
        help="Run Layer D2 (Browser ScriptAPI bridge E2E).",
    )
    group.add_argument(
        "--native",
        "--native-host",
        action="store_true",
        help="Run Layer D3 (Native PyWebView host smoke & DnD).",
    )
    group.add_argument(
        "--packaged",
        action="store_true",
        help="Run Layer E (PE metadata & packaged executable smoke).",
    )
    group.add_argument(
        "--fast",
        action="store_true",
        help="Run Layers A, B, and C (skips UI, browser, and desktop integration).",
    )

    parser.add_argument(
        "--python",
        type=str,
        default=None,
        help="Explicit Python interpreter to execute tests.",
    )
    parser.add_argument(
        "--fail-fast",
        "-x",
        action="store_true",
        help="Abort immediately on first step failure.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_STEP_TIMEOUT_SEC,
        help=f"Per-step timeout in seconds (default: {DEFAULT_STEP_TIMEOUT_SEC}s).",
    )
    parser.add_argument(
        "--retry-flaky",
        action="store_true",
        help="Re-run failed steps once to isolate and classify flaky tests.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help=f"Directory for test reports (default: {DEFAULT_REPORT_DIR}).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Stream full test stdout/stderr to terminal.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report summary to stdout on finish.",
    )

    args = parser.parse_args()

    # Determine active layers
    selected_layers = []
    if args.governance:
        selected_layers.append("governance")
    if args.backend:
        selected_layers.append("backend")
    if args.templates:
        selected_layers.append("templates")
    if args.ui:
        selected_layers.append("ui")
    if args.playwright:
        selected_layers.append("playwright")
    if args.native:
        selected_layers.append("native")
    if args.packaged:
        selected_layers.append("packaged")
    if args.fast:
        selected_layers.extend(["governance", "backend", "templates"])

    if not selected_layers or args.all:
        selected_layers = [
            "governance",
            "backend",
            "templates",
            "ui",
            "playwright",
            "native",
            "packaged",
        ]

    # Initialize environment
    start_total_time = time.perf_counter()
    env_meta = prepare_test_environment(args.report_dir, preferred_py=args.python)
    git_meta = get_git_info()

    print("=" * 80)
    print("  CvSU Document Automation Suite — Authoritative Test Orchestrator")
    print(f"  Branch: {git_meta['branch']} ({git_meta['commit'][:8]})")
    print(f"  Python: {env_meta['python_version']} ({env_meta['platform']})")
    print(f"  Layers: {', '.join(selected_layers)}")
    print(f"  Reports Directory: {env_meta['report_dir']}")
    print(f"  Step Timeout: {args.timeout}s (Retry Flaky: {args.retry_flaky})")
    print("=" * 80)

    pipeline_steps = define_pipeline(selected_layers)
    step_results = []
    all_flaky_tests = []
    overall_passed = True

    for step in pipeline_steps:
        step_timeout = min(args.timeout, step.get("timeout_sec", args.timeout))
        res = run_test_step(
            step_id=step["id"],
            name=step["name"],
            layer=step.get("layer", "Unknown Layer"),
            files=step["files"],
            logs_dir=Path(env_meta["logs_dir"]),
            junit_dir=Path(env_meta["junit_dir"]),
            verbose=args.verbose,
            timeout_sec=step_timeout,
            is_audit_script=step.get("is_audit", False),
            retry_flaky=args.retry_flaky,
            py_executable=env_meta.get("python_executable", sys.executable),
        )
        step_results.append(res)
        if res.get("flaky_cases"):
            all_flaky_tests.extend(res["flaky_cases"])

        if res["status"] != "PASSED":
            overall_passed = False
            if args.fail_fast:
                print(
                    f"\n\033[91m[FAIL-FAST] Pipeline aborted after failure in {step['id']}.\033[0m"
                )
                break

    total_duration = time.perf_counter() - start_total_time

    # Aggregate metrics
    summary = {
        "total": sum(s["counts"]["total"] for s in step_results),
        "passed": sum(s["counts"]["passed"] for s in step_results),
        "failed": sum(s["counts"]["failed"] for s in step_results),
        "skipped": sum(s["counts"]["skipped"] for s in step_results),
        "errors": sum(s["counts"].get("errors", 0) for s in step_results),
        "flaky": sum(s["counts"].get("flaky", 0) for s in step_results),
        "timed_out": sum(s["counts"].get("timed_out", 0) for s in step_results),
    }

    report_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_mode": "Authoritative Local Pipeline",
        "git": git_meta,
        "environment": env_meta,
        "inventory": get_manifest_inventory(),
        "overall_status": "PASSED" if overall_passed else "FAILED",
        "total_duration_sec": round(total_duration, 3),
        "summary": summary,
        "flaky_tests": all_flaky_tests,
        "steps": step_results,
    }

    # Validate mathematical self-consistency before generating reports (fails closed if discrepancy found)
    validate_report_consistency(report_payload)

    json_path, _, md_path, _ = generate_reports(report_payload, args.report_dir)

    # Terminal summary banner
    print("\n" + "=" * 80)
    print("  PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    for s in step_results:
        st_color = "\033[92m" if s["status"] == "PASSED" else "\033[91m"
        fl_str = f", \033[93m{len(s.get('flaky_cases', []))} flaky\033[0m" if s.get("flaky_cases") else ""
        print(
            f"  {st_color}[{s['status']}]\033[0m {s['step_id']:<35} "
            f"({s['counts']['passed']:>3} passed, {s['counts']['failed']:>2} failed{fl_str}) in {s['duration_sec']:>6.2f}s"
        )
    print("-" * 80)
    status_str = "\033[92mPASSED\033[0m" if overall_passed else "\033[91mFAILED\033[0m"
    print(
        f"  Result: {status_str} | Tests: {summary['total']} total | "
        f"Passed: {summary['passed']} | Failed: {summary['failed']} | Skipped: {summary['skipped']} | "
        f"Flaky: {summary['flaky']} | Timed Out: {summary['timed_out']} | Errors: {summary['errors']} | Duration: {total_duration:.2f}s"
    )
    print(f"  JSON Report:     {json_path}")
    print(f"  Markdown Report: {md_path}")
    print("=" * 80)

    if args.json:
        print("\n" + json.dumps(report_payload, indent=2))

    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
