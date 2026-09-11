import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

def test_playwright_parser_settings_modal_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        # 1. Verify modal is initially hidden
        modal = page.locator("#modalParserSettingsBackdrop")
        assert modal.is_hidden(), "Settings modal must be hidden initially"

        # 2. Click Settings button in top header
        btn_settings = page.locator("#btnOpenSettings")
        assert btn_settings.is_visible(), "Settings button must be visible in header"
        btn_settings.click()
        page.wait_for_timeout(200)

        assert modal.is_visible(), "Settings modal should open when clicking settings button"

        # 3. Check Prefixes Tab
        prefix_pane = page.locator("#cfgPanePrefixes")
        assert prefix_pane.is_visible(), "Prefixes pane should be visible by default"
        tbody = page.locator("#cfgPrefixTableBody")
        assert "COSC" in tbody.inner_text(), "COSC must be listed in prefixes table"
        assert "DCIT" in tbody.inner_text(), "DCIT must be listed in prefixes table"

        # Test prefix search filter
        search_input = page.locator("#cfgSearchPrefix")
        search_input.fill("COSC")
        page.wait_for_timeout(100)
        assert "COSC" in tbody.inner_text()
        assert "AGEN" not in tbody.inner_text()
        search_input.fill("")
        page.wait_for_timeout(100)

        # Add a custom prefix
        page.fill("#cfgNewPrefix", "CRIM")
        page.fill("#cfgNewDeptCode", "CCJ")
        page.fill("#cfgNewDeptName", "College of Criminal Justice")
        page.click("text=+ Add Prefix")
        page.wait_for_timeout(100)
        assert "CRIM" in tbody.inner_text(), "Newly added prefix CRIM must appear in table"

        # 4. Check Lab Courses Tab
        page.click("#cfgTabLab")
        lab_pane = page.locator("#cfgPaneLab")
        assert lab_pane.is_visible(), "Lab courses pane must be visible"
        lab_cloud = page.locator("#cfgLabTagCloud")
        assert "DCIT 21" in lab_cloud.inner_text()
        assert "COSC 70" in lab_cloud.inner_text()

        # Add a custom lab code
        page.fill("#cfgNewLabCode", "CHEM 101")
        page.click("text=+ Add Lab Code")
        page.wait_for_timeout(100)
        assert "CHEM 101" in lab_cloud.inner_text()

        # 5. Check Degree Aliases Tab
        page.click("#cfgTabDegrees")
        degrees_pane = page.locator("#cfgPaneDegrees")
        assert degrees_pane.is_visible(), "Degree aliases pane must be visible"
        degrees_table = page.locator("#cfgDegreesTableBody")
        assert "BSCS" in degrees_table.inner_text()

        # Add custom degree alias
        page.fill("#cfgNewAliasShort", "CRIM")
        page.fill("#cfgNewAliasFull", "BSCRIM")
        page.click("text=+ Add Degree Alias")
        page.wait_for_timeout(100)
        assert "BSCRIM" in degrees_table.inner_text()

        # 6. Check Roster Keywords Tab
        page.click("#cfgTabKeywords")
        keywords_pane = page.locator("#cfgPaneKeywords")
        assert keywords_pane.is_visible(), "Keywords pane must be visible"
        name_cloud = page.locator("#cfgNameTokensCloud")
        assert "pangalan" in name_cloud.inner_text()
        id_cloud = page.locator("#cfgIdTokensCloud")
        assert "lrn" in id_cloud.inner_text()

        # 7. Check Faculty Defaults Tab
        page.click("#cfgTabSchedule")
        schedule_pane = page.locator("#cfgPaneSchedule")
        assert schedule_pane.is_visible(), "Schedule pane must be visible"
        instr_input = page.locator("#cfgDefaultInstructor")
        assert "ORTEGA" in instr_input.input_value()

        # 8. Close Modal
        page.click("#btnCloseSettingsModal")
        page.wait_for_timeout(200)
        assert modal.is_hidden(), "Modal must be hidden after clicking close"

        browser.close()
