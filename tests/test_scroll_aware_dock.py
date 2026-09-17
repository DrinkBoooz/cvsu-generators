import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
ARTIFACT_DIR = r"C:\Users\danjo\.gemini\antigravity-ide\brain\7cdd1ee2-d27f-4cac-ab45-d659c8cd0ed5"

def test_scroll_aware_dock_behavior():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a standard 1280x800 laptop viewport where Step 6 is below the fold initially
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        
        file_url = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"
        page.goto(file_url)
        page.wait_for_timeout(500)
        
        # 1. At the top of the page: dock must be visible (no dock-hidden class)
        dock = page.locator("#bottomActionBar")
        assert dock.is_visible(), "Dock should be visible when at top of page"
        assert "dock-hidden" not in (dock.get_attribute("class") or "")
        
        # Capture screenshot at top with dock visible
        top_screenshot_path = os.path.join(ARTIFACT_DIR, "dock_visible_at_top.png")
        page.screenshot(path=top_screenshot_path)
        
        # 2. Scroll to Step 6
        page.evaluate("document.getElementById('cardStep6').scrollIntoView({ behavior: 'instant', block: 'center' })")
        page.wait_for_timeout(500)
        
        classes = dock.get_attribute("class") or ""
        assert "dock-hidden" in classes, "Dock must have dock-hidden class when Step 6 is in view"
        
        # Verify that Step 6 is visible
        step6 = page.locator("#cardStep6")
        assert step6.is_visible()
        
        # Capture screenshot showing Step 6 with only ONE Initialize Workflow button
        step6_screenshot_path = os.path.join(ARTIFACT_DIR, "step6_single_button_verified.png")
        page.screenshot(path=step6_screenshot_path)
        
        # 3. Scroll back to top
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        
        # Dock should reappear
        classes_after = dock.get_attribute("class") or ""
        assert "dock-hidden" not in classes_after, "Dock must reappear when scrolled back to top"
        
        browser.close()

if __name__ == "__main__":
    test_scroll_aware_dock_behavior()
    print("Scroll-aware dock behavior verified successfully!")
