import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

TABS = ["Prefixes", "Lab", "Degrees", "Keywords", "Schedule", "CustomTemplates"]


def test_settings_modal_height_uniformity_desktop():
    """Assert settings modal maintains uniform dimensions and stable position across all tabs on desktop."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        page.click("#btnOpenSettings")
        page.wait_for_selector("#modalParserSettingsBackdrop:not(.d-none)")

        measurements = []
        for t in TABS:
            page.click(f"#cfgTab{t}")
            page.wait_for_timeout(50)

            rect = page.evaluate("""() => {
                const modal = document.querySelector('#modalParserSettingsBackdrop .modal-dialog-custom');
                const r = modal.getBoundingClientRect();
                return { width: r.width, height: r.height, top: r.top, left: r.left };
            }""")
            measurements.append((t, rect))

        first_t, first_rect = measurements[0]
        for t, r in measurements:
            assert abs(r["height"] - first_rect["height"]) < 2.0, (
                f"Height mismatch for tab '{t}': expected ~{first_rect['height']}px, got {r['height']}px"
            )
            assert abs(r["width"] - first_rect["width"]) < 2.0, (
                f"Width mismatch for tab '{t}': expected ~{first_rect['width']}px, got {r['width']}px"
            )
            assert abs(r["top"] - first_rect["top"]) < 2.0, (
                f"Vertical position shifted for tab '{t}': expected ~{first_rect['top']}px, got {r['top']}px"
            )

        browser.close()


def test_settings_modal_responsive_tablet():
    """Assert segmented tabs adapt to a 3-column grid without horizontal overflow on tablet."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 768, "height": 600})
        page.goto(FILE_URL)

        page.click("#btnOpenSettings")
        page.wait_for_selector("#modalParserSettingsBackdrop:not(.d-none)")

        nav_info = page.evaluate("""() => {
            const tabs = document.querySelector('.settings-nav-tabs');
            const style = window.getComputedStyle(tabs);
            const m = document.querySelector('#modalParserSettingsBackdrop .modal-dialog-custom').getBoundingClientRect();
            return {
                display: style.display,
                gridTemplateColumns: style.gridTemplateColumns,
                scrollWidth: tabs.scrollWidth,
                clientWidth: tabs.clientWidth,
                modalWidth: m.width,
                modalHeight: m.height
            };
        }""")

        assert nav_info["display"] == "grid", "Tabs must use grid layout on tablet breakpoint"
        # In a 3-column grid, gridTemplateColumns has 3 space-separated track values
        cols = nav_info["gridTemplateColumns"].strip().split()
        assert len(cols) == 3, f"Expected 3 columns on tablet, got {len(cols)} ({nav_info['gridTemplateColumns']})"
        assert nav_info["scrollWidth"] <= nav_info["clientWidth"] + 1, (
            f"Tabs must not overflow horizontally on tablet: scrollWidth={nav_info['scrollWidth']}, clientWidth={nav_info['clientWidth']}"
        )
        assert nav_info["modalWidth"] <= 768, "Modal must fit within tablet viewport width"

        browser.close()


def test_settings_modal_responsive_mobile():
    """Assert settings modal adapts to 2-column tab grid and stacked footer on mobile."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 375, "height": 667})
        page.goto(FILE_URL)

        page.click("#btnOpenSettings")
        page.wait_for_selector("#modalParserSettingsBackdrop:not(.d-none)")

        info = page.evaluate("""() => {
            const tabs = document.querySelector('.settings-nav-tabs');
            const style = window.getComputedStyle(tabs);
            const buttons = Array.from(tabs.querySelectorAll('.settings-nav-tab')).map(b => {
                const r = b.getBoundingClientRect();
                return { text: b.innerText.trim(), width: r.width, height: r.height };
            });
            const footer = document.querySelector('#modalParserSettingsBackdrop .modal-footer-custom');
            const modal = document.querySelector('#modalParserSettingsBackdrop .modal-dialog-custom');
            const mRect = modal.getBoundingClientRect();
            const fRect = footer.getBoundingClientRect();

            return {
                display: style.display,
                gridTemplateColumns: style.gridTemplateColumns,
                tabsScrollWidth: tabs.scrollWidth,
                tabsClientWidth: tabs.clientWidth,
                buttons: buttons,
                footerWidth: fRect.width,
                footerHeight: fRect.height,
                footerScrollWidth: footer.scrollWidth,
                footerClientWidth: footer.clientWidth,
                modalWidth: mRect.width,
                modalHeight: mRect.height
            };
        }""")

        assert info["display"] == "grid", "Tabs must use grid layout on mobile breakpoint"
        cols = info["gridTemplateColumns"].strip().split()
        assert len(cols) == 2, f"Expected 2 columns on mobile, got {len(cols)}"
        assert info["tabsScrollWidth"] <= info["tabsClientWidth"] + 1, "Tabs must not overflow horizontally on mobile"
        assert len(info["buttons"]) == 6, "All 6 tabs must be present"
        for btn in info["buttons"]:
            assert btn["height"] >= 20, f"Tab '{btn['text']}' height too small: {btn['height']}px"
            assert btn["width"] >= 70, f"Tab '{btn['text']}' width too small: {btn['width']}px"

        # Footer must wrap cleanly into two rows (height > 60px) without horizontal scroll
        assert info["footerHeight"] >= 60, f"Footer must stack rows on mobile, got height {info['footerHeight']}px"
        assert info["footerScrollWidth"] <= info["footerClientWidth"] + 1, "Footer must not overflow horizontally on mobile"
        assert info["modalWidth"] <= 375, "Modal width must not exceed viewport width"

        browser.close()


def test_settings_modal_responsive_short_viewport():
    """Assert settings modal height adapts to short displays (e.g. 550px height) without exceeding bounds."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1024, "height": 550})
        page.goto(FILE_URL)

        page.click("#btnOpenSettings")
        page.wait_for_selector("#modalParserSettingsBackdrop:not(.d-none)")

        m_info = page.evaluate("""() => {
            const modal = document.querySelector('#modalParserSettingsBackdrop .modal-dialog-custom');
            const body = modal.querySelector('.modal-body-custom');
            const r = modal.getBoundingClientRect();
            return {
                modalHeight: r.height,
                modalTop: r.top,
                bodyOverflowY: window.getComputedStyle(body).overflowY
            };
        }""")

        assert m_info["modalHeight"] <= 550 * 0.96, (
            f"Modal height ({m_info['modalHeight']}px) must not exceed 96% of 550px viewport"
        )
        assert m_info["modalTop"] >= 0, "Modal top must not clip off the top of the viewport"
        assert m_info["bodyOverflowY"] in ["auto", "scroll"], "Modal body must remain scrollable on short viewports"

        browser.close()
