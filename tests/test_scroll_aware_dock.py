import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
ARTIFACT_DIR = os.environ.get("ARTIFACT_DIR", os.path.join(WORKSPACE_DIR, "scratch"))
os.makedirs(ARTIFACT_DIR, exist_ok=True)


def test_scroll_aware_dock_behavior():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        file_url = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"
        page.goto(file_url)
        page.wait_for_timeout(300)

        # 1. On Stage 1 (initial active stage): dock must be visible (no dock-hidden class)
        # Verify backward-compatible lookup via #bottomActionBar and migration identifier .sticky-action-dock
        dock = page.locator("#bottomActionBar")
        dock_alias = page.locator(".sticky-action-dock")
        assert dock.is_visible(), "Dock should be visible on Stage 1"
        assert dock_alias.is_visible(), "Dock must be selectable via .sticky-action-dock"
        assert "dock-hidden" not in (dock.get_attribute("class") or "")

        # Verify dock is compact and status-only (NO competing primary action button)
        assert page.locator("#bottomActionBar #btnDockProcess").count() == 0, (
            "Competing primary action button (#btnDockProcess) must be removed from the dock"
        )
        assert page.locator("#actionPillSchedule").is_visible(), "Schedule status indicator must be present"
        assert page.locator("#actionPillRosters").is_visible(), "Rosters status indicator must be present"
        assert page.locator("#actionPillOutput").is_visible(), "Output status indicator must be present"

        # Capture screenshot on Stage 1 with dock visible
        top_screenshot_path = os.path.join(ARTIFACT_DIR, "dock_visible_at_top.png")
        page.screenshot(path=top_screenshot_path)

        # 2. Switch to Stage 3 (Packages) and verify dock clearance
        page.click("#chipStep3")
        page.wait_for_timeout(200)
        assert dock.is_visible(), "Dock must remain visible on Stage 3 as a compact readiness bar"
        assert "dock-hidden" not in (dock.get_attribute("class") or "")

        # Verify Stage 3 has its own active-workspace primary action ("Continue to Dates ->")
        btn_stage3 = page.locator("#btnStage3Primary")
        assert btn_stage3.is_visible(), "Stage 3 primary action must remain inside the active workspace"
        assert "Continue to Dates" in btn_stage3.inner_text()

        # Verify that container padding ensures the stage footer is not obscured under the dock
        footer_box = page.locator("#cardStep3 .stage-footer-bar").bounding_box()
        dock_box = dock.bounding_box()
        assert footer_box is not None and dock_box is not None
        # When scrolled to bottom, footer must be above the dock top
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(100)
        footer_box_scrolled = page.locator("#cardStep3 .stage-footer-bar").bounding_box()
        assert footer_box_scrolled["y"] + footer_box_scrolled["height"] <= dock_box["y"] + 2, (
            "Stage 3 workspace content must not be obscured by the bottom dock"
        )

        # 3. Switch to Stage 6 (Generate) via chip click
        page.click("#chipStep6")
        page.wait_for_timeout(300)

        classes = dock.get_attribute("class") or ""
        assert "dock-hidden" in classes, "Dock must have dock-hidden class when Stage 6 is active"

        # Verify that Stage 6 is visible and Stages 1-5 are hidden (single-active-stage)
        step6 = page.locator("#cardStep6")
        assert step6.is_visible()
        assert not page.locator("#cardStep1").is_visible()
        assert not page.locator("#cardStep3").is_visible()

        # Verify Stage 6 empty-state explanation replaces "0 of 0 Selected"
        sec_stat = page.locator("#preflightStatSections").inner_text()
        assert "No Classes Available" in sec_stat, f"Expected 'No Classes Available', got: {sec_stat}"

        # Verify Stage 6 Generate button is genuinely disabled when prerequisites are missing
        proc_btn = page.locator("#processBtn")
        assert proc_btn.is_visible()
        assert proc_btn.is_disabled(), "Generate button must be genuinely disabled when prerequisites are missing"
        assert proc_btn.get_attribute("aria-disabled") == "true"
        assert proc_btn.get_attribute("aria-describedby") == "preflightBlockerBox"
        assert "Generation blocked" in (proc_btn.get_attribute("title") or "")

        # Verify clicking disabled Generate button never starts generation
        proc_btn.click(force=True)
        page.wait_for_timeout(200)
        assert not page.locator("#progressContainer").is_visible(), "Progress container must not appear"
        is_running = page.evaluate("() => window._isGenerationRunning")
        assert is_running is not True, "Generation running state must remain false"

        # Capture screenshot showing Stage 6 with only ONE genuinely disabled Initialize Workflow button
        step6_screenshot_path = os.path.join(ARTIFACT_DIR, "step6_single_button_verified.png")
        page.screenshot(path=step6_screenshot_path)

        # 4. Return to Stage 1
        page.click("#chipStep1")
        page.wait_for_timeout(300)

        # Dock should reappear
        classes_after = dock.get_attribute("class") or ""
        assert "dock-hidden" not in classes_after, "Dock must reappear when returning to Stage 1"

        browser.close()


if __name__ == "__main__":
    test_scroll_aware_dock_behavior()
    print("Stage-aware dock behavior verified successfully!")
