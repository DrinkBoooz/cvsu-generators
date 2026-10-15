"""
Authoritative Pytest Configuration and Test Failure Diagnostics Hook.
"""

from pathlib import Path
import pytest


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Stores test outcome on the test item for post-failure inspection in fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture(autouse=True)
def capture_playwright_failure_artifacts(request):
    """
    Automatic failure capture for any test utilizing Playwright page or browser.
    Saves screenshot and logs to test_reports/playwright/<test_name>/ if test fails.
    """
    yield
    rep_call = getattr(request.node, "rep_call", None)
    if rep_call and rep_call.failed:
        page = None
        if "page" in request.node.funcargs:
            page = request.node.funcargs["page"]
        elif "app_page" in request.node.funcargs:
            page = request.node.funcargs["app_page"]

        if page is not None:
            try:
                repo_root = Path(__file__).resolve().parent.parent
                sanitized_name = request.node.name.replace("[", "_").replace("]", "_").replace(" ", "_")
                artifact_dir = repo_root / "test_reports" / "playwright" / sanitized_name
                artifact_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(artifact_dir / "screenshot.png"), full_page=True)
            except Exception:
                pass
