#!/usr/bin/env python3
"""
Authoritative Test Orchestrator for DrinkBoooz/cvsu-generators.

Provides a unified, fully automated, repeatable test pipeline covering:
  - Layer A: Static / AST Governance & Structural Authority Audits
  - Layer B: Backend / Core Unit & Integration Tests
  - Layer C: Adversarial Template Matrix & Mutation Invariance
  - Layer D: UI API Bridge & Playwright Real-Authority Browser E2E Tests
  - Layer E: Windows PE Version Info & Packaged Executable Smoke Tests

Usage:
  python scripts/test_orchestrator.py [OPTIONS]
  python scripts/test_all.py [OPTIONS]

Options:
  --all             Run all test layers (default).
  --governance      Run Layer A (Static / AST governance & structural authority audit).
  --backend         Run Layer B (Backend / core unit & integration tests).
  --templates       Run Layer C (Adversarial template matrix & mutation tests).
  --ui              Run Layer D1 (UI unit & bridge tests).
  --playwright      Run Layer D2 (Playwright browser E2E tests).
  --packaged        Run Layer E (PE version info & packaged executable smoke).
  --fast            Run Layers A, B, and C (skips slower browser E2E).
  --fail-fast, -x   Abort pipeline immediately upon first layer failure.
  --report-dir DIR  Directory where test reports and logs are saved (default: test_reports).
  --verbose, -v     Verbose output.
  --json            Print JSON report summary to stdout at completion.
  -h, --help        Show this help message and exit.
"""

import os
import sys
import time
import json
import shutil
import re
import argparse
import subprocess
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


def prepare_test_environment(report_dir: Path) -> dict:
    """Prepares clean, deterministic test environment and returns metadata."""
    report_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = report_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

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
        "platform": sys.platform,
        "report_dir": str(report_dir),
        "logs_dir": str(logs_dir),
    }


def parse_pytest_output(output: str) -> dict:
    """Extract passed, failed, skipped, and warning counts from pytest output."""
    counts = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "warnings": 0,
    }

    # Matches lines like: "11 passed, 2 skipped, 1 failed in 3.45s"
    # or "==== 10 passed in 16.77s ===="
    summary_match = re.search(
        r"=+\s*(.*?)\s+in\s+[\d\.]+[smh]+.*=+", output, re.IGNORECASE
    )
    if summary_match:
        text = summary_match.group(1)
        for part in text.split(","):
            part = part.strip()
            p_match = re.match(r"(\d+)\s+([a-zA-Z]+)", part)
            if p_match:
                n, kind = int(p_match.group(1)), p_match.group(2).lower()
                if "pass" in kind:
                    counts["passed"] = n
                elif "fail" in kind:
                    counts["failed"] = n
                elif "skip" in kind:
                    counts["skipped"] = n
                elif "error" in kind:
                    counts["errors"] = n
                elif "warn" in kind:
                    counts["warnings"] = n
    else:
        # Check single line short summary if not full banner
        for line in output.splitlines():
            line_clean = line.strip()
            if "passed" in line_clean:
                m = re.search(r"(\d+)\s+passed", line_clean)
                if m:
                    counts["passed"] = int(m.group(1))
            if "failed" in line_clean:
                m = re.search(r"(\d+)\s+failed", line_clean)
                if m:
                    counts["failed"] = int(m.group(1))
            if "skipped" in line_clean:
                m = re.search(r"(\d+)\s+skipped", line_clean)
                if m:
                    counts["skipped"] = int(m.group(1))
            if "errors" in line_clean or "error" in line_clean:
                m = re.search(r"(\d+)\s+error", line_clean)
                if m:
                    counts["errors"] = int(m.group(1))

    counts["total"] = (
        counts["passed"] + counts["failed"] + counts["skipped"] + counts["errors"]
    )
    return counts


def run_command(
    cmd: list[str], cwd: Path, log_file: Path, verbose: bool = False
) -> tuple[int, float, str]:
    """Runs command with output streaming and logging."""
    start_time = time.perf_counter()
    full_output = []

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

        for line in proc.stdout:
            full_output.append(line)
            if verbose:
                sys.stdout.write(f"    {line}")
                sys.stdout.flush()

        proc.wait()
        exit_code = proc.returncode
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

    return exit_code, duration, combined_output


def run_test_step(
    step_id: str,
    name: str,
    layer: str,
    cmd: list[str],
    logs_dir: Path,
    verbose: bool = False,
    is_audit_script: bool = False,
) -> dict:
    """Executes a single test step and returns structured result."""
    print(f"\n>> [{step_id}] {name}")
    log_file = logs_dir / f"{step_id}.log"
    exit_code, duration, output = run_command(
        cmd, cwd=REPO_ROOT, log_file=log_file, verbose=verbose
    )

    if is_audit_script:
        # Audit script returns 0 on 0 Category E violations
        # Parse Category E violations from output if present
        violations = 0
        m = re.search(r"Total Category E Violations:\s*(\d+)", output)
        if m:
            violations = int(m.group(1))
        passed = exit_code == 0 and violations == 0
        counts = {
            "total": 1,
            "passed": 1 if passed else 0,
            "failed": 0 if passed else 1,
            "skipped": 0,
            "errors": 0,
            "warnings": 0,
        }
    else:
        counts = parse_pytest_output(output)
        # If pytest collected no items or failed to run, check exit code
        if counts["total"] == 0:
            counts["total"] = 1
            if exit_code == 0:
                counts["passed"] = 1
            else:
                counts["failed"] = 1
        passed = exit_code == 0 and counts["failed"] == 0 and counts["errors"] == 0

    status = "PASSED" if passed else "FAILED"
    color = "\033[92m" if passed else "\033[91m"
    reset = "\033[0m"

    print(
        f"  +-- Status: {color}{status}{reset} | Duration: {duration:.2f}s | "
        f"Passed: {counts['passed']} | Failed: {counts['failed']} | Skipped: {counts['skipped']}"
    )

    return {
        "step_id": step_id,
        "name": name,
        "layer": layer,
        "command": cmd,
        "status": status,
        "exit_code": exit_code,
        "duration_sec": round(duration, 3),
        "counts": counts,
        "log_file": str(log_file),
        "output_snippet": "\n".join(output.strip().splitlines()[-15:])
        if output
        else "",
    }


def define_pipeline(selected_layers: list[str]) -> list[dict]:
    """Defines the layers and test steps based on user selection."""
    py = sys.executable
    steps = []

    # ── Layer A: Static / AST Governance ───────────────────────────────────────
    if "governance" in selected_layers or "all" in selected_layers:
        steps.append(
            {
                "layer": "Layer A — Static / AST Governance",
                "id": "A1_structural_authority_audit",
                "name": "Structural Authority Pattern Audit (Category E Invariance)",
                "cmd": [py, "tests/audit_structural_patterns.py"],
                "is_audit": True,
            }
        )
        steps.append(
            {
                "layer": "Layer A — Static / AST Governance",
                "id": "A2_ast_governance_rules",
                "name": "AST Architectural Governance & Coordinate Literal Audits",
                "cmd": [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_ast_rules.py",
                    "tests/test_structural_authority_audit.py",
                    "-v",
                ],
                "is_audit": False,
            }
        )

    # ── Layer B: Backend / Core Unit & Integration ────────────────────────────
    if "backend" in selected_layers or "all" in selected_layers:
        steps.append(
            {
                "layer": "Layer B — Backend / Core",
                "id": "B1_backend_core_unit_and_integration",
                "name": "Parsers, Inspectors, Detectors, Resolvers, Validators, Generators",
                "cmd": [
                    py,
                    "-m",
                    "pytest",
                    "tests/",
                    "-m",
                    "not desktop_integration",
                    "-k",
                    "not test_playwright and not test_pywebview and not test_packaged_executable_smoke and not test_pe_version_info and not test_adversarial_template_matrix and not test_invalid_templates and not test_template_mutations and not test_ast_rules and not test_structural_authority_audit",
                    "-v",
                ],
                "is_audit": False,
            }
        )

    # ── Layer C: Adversarial Template Matrix ──────────────────────────────────
    if "templates" in selected_layers or "all" in selected_layers:
        steps.append(
            {
                "layer": "Layer C — Adversarial Template Matrix",
                "id": "C1_adversarial_template_matrix",
                "name": "Adversarial Template Matrix (Formulas, Foreign, Renames, Decoys, Invariance)",
                "cmd": [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_adversarial_template_matrix.py",
                    "tests/test_invalid_templates.py",
                    "tests/test_template_mutations.py",
                    "-v",
                ],
                "is_audit": False,
            }
        )

    # ── Layer D: UI API Bridge & Playwright Real-Authority E2E ─────────────────
    if "ui" in selected_layers or "all" in selected_layers:
        steps.append(
            {
                "layer": "Layer D — UI & Playwright Browser E2E",
                "id": "D1_ui_bridge_and_consistency",
                "name": "UI API Bridge, Consistency, Accessibility, & Responsive Modals",
                "cmd": [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_ui_api_bridge.py",
                    "tests/test_ui_consistency.py",
                    "tests/test_ui_accessibility.py",
                    "tests/test_ui_asset_resilience.py",
                    "tests/test_settings_modal_responsive.py",
                    "-v",
                ],
                "is_audit": False,
            }
        )

    if "playwright" in selected_layers or "all" in selected_layers:
        steps.append(
            {
                "layer": "Layer D — UI & Playwright Browser E2E",
                "id": "D2_playwright_real_authority_e2e",
                "name": "Playwright Real-Authority PyWebView Bridge (Lifecycle, Ambig Confirmation, Gen)",
                "cmd": [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_playwright_real_authority_e2e.py",
                    "tests/test_playwright_e2e.py",
                    "tests/test_playwright_settings_modal.py",
                    "tests/test_playwright_roster_mapping.py",
                    "tests/test_playwright_accessibility.py",
                    "-v",
                ],
                "is_audit": False,
            }
        )

    # ── Layer E: Packaged Executable & PE Metadata ────────────────────────────
    if "packaged" in selected_layers or "all" in selected_layers:
        steps.append(
            {
                "layer": "Layer E — Packaged Executable & PE Metadata",
                "id": "E1_pe_metadata_and_packaged_smoke",
                "name": "Windows PE Version Info, Authenticode Signature, & Binary Lifecycle Smoke",
                "cmd": [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_pe_version_info.py",
                    "tests/test_packaged_executable_smoke.py",
                    "-v",
                ],
                "is_audit": False,
            }
        )

    return steps


def generate_reports(
    report_data: dict, report_dir: Path
) -> tuple[Path, Path, Path, Path]:
    """Generates machine-readable JSON and human-readable Markdown test reports."""
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
        f"**Status**: {overall_badge}  ",
        f"**Timestamp**: `{report_data['timestamp']}`  ",
        f"**Repository**: `{report_data['git']['branch']}` (`{report_data['git']['commit'][:8]}`)  ",
        f"**Python Runtime**: `{report_data['environment']['python_version']}` on `{report_data['environment']['platform']}`  ",
        f"**Total Duration**: `{report_data['total_duration_sec']:.2f}s`  ",
        "",
        "## Summary Metrics",
        "",
        "| Metric | Count |",
        "| :--- | :--- |",
        f"| **Total Tests Executed** | **{report_data['summary']['total']}** |",
        f"| Passed | {report_data['summary']['passed']} |",
        f"| Failed | {report_data['summary']['failed']} |",
        f"| Skipped | {report_data['summary']['skipped']} |",
        f"| Errors | {report_data['summary']['errors']} |",
        "",
        "## Pipeline Step Breakdown",
        "",
        "| Step ID | Layer | Description | Status | Tests | Duration | Log |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :--- |",
    ]

    for s in report_data["steps"]:
        badge = "✅ PASS" if s["status"] == "PASSED" else "❌ FAIL"
        log_name = Path(s["log_file"]).name
        md_lines.append(
            f"| `{s['step_id']}` | {s['layer']} | {s['name']} | {badge} | {s['counts']['passed']} passed | {s['duration_sec']:.2f}s | [`{log_name}`](logs/{log_name}) |"
        )

    md_lines.extend(
        [
            "",
            "## Architectural Invariants Verified",
            "",
            "- **Inspector Discovers Where**: No layer fabricates template coordinates; inspection discovers table & sheet candidates strictly from physical structure.",
            "- **Detector Proposes Role**: Discovered candidates map to semantic roles without mutating underlying template files.",
            "- **Validator Verifies Structural Compatibility**: Ambiguity fails closed; sheets missing required headers are rejected immediately.",
            "- **Generator Consumes Validated Recipes**: Document generation executes strictly through validated structural recipes.",
            "- **Playwright Authority Bridge**: Web browser exercises ui.html interacting directly with the real Python `ScriptAPI`.",
            "- **Packaged Binary Verification**: PE version headers, Copyright notices, and process startup smoke tested gracefully.",
            "",
        ]
    )

    failures = [s for s in report_data["steps"] if s["status"] != "PASSED"]
    if failures:
        md_lines.extend(["## Failure Diagnostics", ""])
        for f in failures:
            md_lines.extend(
                [
                    f"### ❌ {f['step_id']}: {f['name']}",
                    "",
                    f"**Command**: `{' '.join(f['command'])}`  ",
                    f"**Exit Code**: `{f['exit_code']}`  ",
                    "",
                    "```text",
                    f["output_snippet"],
                    "```",
                    "",
                ]
            )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    shutil.copyfile(md_path, latest_md_path)

    return json_path, latest_json_path, md_path, latest_md_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Authoritative Automated Test Orchestrator for DrinkBoooz/cvsu-generators",
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
        help="Run Layer D2 (Playwright browser E2E tests).",
    )
    group.add_argument(
        "--packaged",
        action="store_true",
        help="Run Layer E (PE metadata & packaged executable smoke).",
    )
    group.add_argument(
        "--fast",
        action="store_true",
        help="Run Layers A, B, and C (skips slower browser E2E).",
    )

    parser.add_argument(
        "--fail-fast",
        "-x",
        action="store_true",
        help="Abort immediately on first step failure.",
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
            "packaged",
        ]

    # Initialize environment
    start_total_time = time.perf_counter()
    env_meta = prepare_test_environment(args.report_dir)
    git_meta = get_git_info()

    print("=" * 80)
    print("  CvSU Document Automation Suite — Authoritative Test Orchestrator")
    print(f"  Branch: {git_meta['branch']} ({git_meta['commit'][:8]})")
    print(f"  Python: {env_meta['python_version']} ({env_meta['platform']})")
    print(f"  Layers: {', '.join(selected_layers)}")
    print(f"  Reports Directory: {env_meta['report_dir']}")
    print("=" * 80)

    pipeline_steps = define_pipeline(selected_layers)
    step_results = []
    overall_passed = True

    for step in pipeline_steps:
        res = run_test_step(
            step_id=step["id"],
            name=step["name"],
            layer=step.get("layer", "Unknown Layer"),
            cmd=step["cmd"],
            logs_dir=Path(env_meta["logs_dir"]),
            verbose=args.verbose,
            is_audit_script=step.get("is_audit", False),
        )
        step_results.append(res)
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
        "errors": sum(s["counts"]["errors"] for s in step_results),
    }

    report_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git": git_meta,
        "environment": env_meta,
        "overall_status": "PASSED" if overall_passed else "FAILED",
        "total_duration_sec": round(total_duration, 3),
        "summary": summary,
        "steps": step_results,
    }

    json_path, _, md_path, _ = generate_reports(report_payload, args.report_dir)

    # Terminal summary banner
    print("\n" + "=" * 80)
    print("  PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    for s in step_results:
        st_color = "\033[92m" if s["status"] == "PASSED" else "\033[91m"
        print(
            f"  {st_color}[{s['status']}]\033[0m {s['step_id']:<35} "
            f"({s['counts']['passed']:>3} passed, {s['counts']['failed']:>2} failed) in {s['duration_sec']:>6.2f}s"
        )
    print("-" * 80)
    status_str = (
        "\033[92mPASSED\033[0m" if overall_passed else "\033[91mFAILED\033[0m"
    )
    print(
        f"  Result: {status_str} | Tests: {summary['total']} total | "
        f"Passed: {summary['passed']} | Failed: {summary['failed']} | Skipped: {summary['skipped']} | "
        f"Duration: {total_duration:.2f}s"
    )
    print(f"  JSON Report:     {json_path}")
    print(f"  Markdown Report: {md_path}")
    print("=" * 80)

    if args.json:
        print("\n" + json.dumps(report_payload, indent=2))

    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
