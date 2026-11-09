import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")


def test_contextual_workflow_dock_zones_and_behavior():
    """Verify Phase 12 Contextual Workflow Dock zones, dynamic telemetry, and Stage 6 hero isolation."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        file_url = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"
        page.goto(file_url)
        page.wait_for_timeout(300)

        dock = page.locator("#bottomActionBar")
        assert dock.is_visible(), "Contextual Workflow Dock must be visible on Stage 1"

        # 1. Verify Information Architecture
        # Zone 1: Where am I? (Stage context title, without redundant step counter)
        title = page.locator("#dockStageTitle")
        assert title.is_visible(), "Dock stage title must be visible"
        assert "Schedule" in title.inner_text()

        # Zone 2: What is current state? (Guidance + Readiness pills)
        status_msg = page.locator("#dockStatusMessage")
        assert status_msg.is_visible(), "Dock dynamic status guidance must be visible"
        assert "schedule" in status_msg.inner_text().lower()

        # Preserved compatibility pills
        pill_sched = page.locator("#actionPillSchedule")
        pill_rost = page.locator("#actionPillRosters")
        pill_out = page.locator("#actionPillOutput")
        pill_classes = page.locator("#actionPillClasses")
        assert pill_sched.is_visible()
        assert pill_rost.is_visible()
        assert pill_out.is_visible()
        assert pill_classes.is_visible()

        # Repetitive action button was eliminated per user request (photo 1)
        assert page.locator("#bottomActionBar #btnDockAction").count() == 0, (
            "Repetitive action button must not exist in dock ribbon"
        )

        # 2. Dynamic Progression Across Stages
        # Navigate to Stage 2: Rosters
        page.click("#chipStep2")
        page.wait_for_timeout(200)
        assert "Rosters" in title.inner_text()

        # Navigate to Stage 3: Packages
        page.click("#chipStep3")
        page.wait_for_timeout(200)
        assert "Packages" in title.inner_text()

        # Navigate to Stage 4: Dates
        page.click("#chipStep4")
        page.wait_for_timeout(200)
        assert "Dates" in title.inner_text()

        # Navigate to Stage 5: Output
        page.click("#chipStep5")
        page.wait_for_timeout(200)
        assert "Output" in title.inner_text()

        # Navigate to Stage 6: Generate / Preflight
        page.click("#chipStep6")
        page.wait_for_timeout(200)
        # Dock must be hidden on Stage 6
        assert "dock-hidden" in (dock.get_attribute("class") or ""), (
            "Dock must receive dock-hidden class on Stage 6 to preserve single hero CTA"
        )
        assert not dock.is_visible()

        # Verify #processBtn in Stage 6 is the sole hero CTA
        proc_btn = page.locator("#processBtn")
        assert proc_btn.is_visible()
        assert proc_btn.is_disabled()

        browser.close()


def test_dock_readiness_telemetry_live_update():
    """Verify that dock readiness pills update live when state changes."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        file_url = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"
        page.goto(file_url)
        page.wait_for_timeout(300)

        # Initially, schedule pill is not ready (missing or incomplete)
        sched_pill = page.locator("#actionPillSchedule")
        assert "ready" not in (sched_pill.get_attribute("class") or "").lower()

        # Simulate loading valid schedule
        page.evaluate("""
            () => {
                state.schedulePath = "C:/mock/FACULTY_SCHEDULE.xlsx";
                state.scheduleMeta = { instructor: "Prof. Cruz", semester: "1st Semester" };
                updateStepperStatus();
            }
        """)
        page.wait_for_timeout(200)
        assert "ready" in (sched_pill.get_attribute("class") or "").lower()
        browser.close()
