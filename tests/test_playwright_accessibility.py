import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
AXE_JS_PATH = os.path.join(WORKSPACE_DIR, "tests", "vendor", "axe.min.js")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"


def test_playwright_focus_trap_settings_modal_cycling_and_escape():
    """Verify that FocusTrapManager traps Tab/Shift+Tab inside Settings modal,

    closes on Escape, and returns focus to the triggering button.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(200)

        # 1. Trigger Settings modal via button
        btn_settings = page.locator("#btnOpenSettings")
        assert btn_settings.is_visible()
        btn_settings.focus()
        btn_settings.click()
        page.wait_for_timeout(200)

        modal = page.locator("#modalParserSettingsBackdrop")
        assert modal.is_visible(), "Settings modal must be visible after click"

        # 2. Verify initial focus is inside modal
        active_in_modal = page.evaluate("""() => {
            const modal = document.getElementById("modalParserSettingsBackdrop");
            return modal.contains(document.activeElement);
        }""")
        assert active_in_modal, "Active focus must be transferred inside the opened modal"

        # 3. Test Tab cycling boundary (Last -> First)
        # Focus the last focusable element in the modal
        page.evaluate("""() => {
            const modal = document.getElementById("modalParserSettingsBackdrop");
            const focusables = Array.from(modal.querySelectorAll(
                'button:not([disabled]):not([aria-hidden="true"]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )).filter(el => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement);
            if (focusables.length > 0) {
                focusables[focusables.length - 1].focus();
            }
        }""")

        # Press Tab while on last element
        page.keyboard.press("Tab")
        page.wait_for_timeout(50)

        is_first_focused = page.evaluate("""() => {
            const modal = document.getElementById("modalParserSettingsBackdrop");
            const focusables = Array.from(modal.querySelectorAll(
                'button:not([disabled]):not([aria-hidden="true"]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )).filter(el => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement);
            return document.activeElement === focusables[0];
        }""")
        assert is_first_focused, "Tab on last element must cycle back to first focusable element"

        # 4. Test Shift+Tab boundary (First -> Last)
        page.keyboard.press("Shift+Tab")
        page.wait_for_timeout(50)

        is_last_focused = page.evaluate("""() => {
            const modal = document.getElementById("modalParserSettingsBackdrop");
            const focusables = Array.from(modal.querySelectorAll(
                'button:not([disabled]):not([aria-hidden="true"]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )).filter(el => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement);
            return document.activeElement === focusables[focusables.length - 1];
        }""")
        assert is_last_focused, "Shift+Tab on first element must cycle to last focusable element"

        # 5. Test Escape dismissal and focus restoration
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        assert modal.is_hidden(), "Settings modal must close on Escape key"

        restored_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
        assert restored_id == "btnOpenSettings", f"Focus must return to #btnOpenSettings trigger, got '{restored_id}'"

        browser.close()


def test_playwright_focus_trap_stack_nested_confirm():
    """Verify that FocusTrapManager handles stacked/nested overlays:

    Settings Modal -> Apple HIG Confirm Modal -> Dismiss Confirm -> Focus returns to Settings -> Dismiss Settings -> Focus returns to Header button.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(200)

        # Open Settings modal
        page.click("#btnOpenSettings")
        page.wait_for_timeout(200)
        assert page.locator("#modalParserSettingsBackdrop").is_visible()

        # Trigger Apple Confirm modal on top of Settings modal
        page.evaluate("""() => {
            showAppleConfirm({
                title: "Reset Configuration",
                message: "Are you sure you want to test nested confirmation?",
                confirmText: "Reset",
                isDestructive: true
            });
        }""")
        page.wait_for_timeout(200)

        confirm_backdrop = page.locator("#modalAppleConfirmBackdrop")
        assert confirm_backdrop.is_visible(), "Confirm modal must be visible on top of settings"

        # Focus must be inside confirm modal
        in_confirm = page.evaluate("""() => {
            const modal = document.getElementById("modalAppleConfirmBackdrop");
            return modal.contains(document.activeElement);
        }""")
        assert in_confirm, "Focus must be transferred to the nested confirmation modal"

        # Dismiss confirmation modal via Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        assert confirm_backdrop.is_hidden(), "Confirmation modal must close on Escape"

        # Settings modal must still be visible and active
        settings_modal = page.locator("#modalParserSettingsBackdrop")
        assert settings_modal.is_visible(), "Settings modal must still be visible underneath"

        # Dismiss settings modal via Escape
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        assert settings_modal.is_hidden(), "Settings modal must close on second Escape"

        # Final focus must be returned to original header settings trigger
        restored_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
        assert restored_id == "btnOpenSettings", f"Focus must restore to #btnOpenSettings, got '{restored_id}'"

        browser.close()


def test_playwright_drawers_focus_trap_and_escape():
    """Verify Help Drawer and Logs Drawer trap focus and restore to trigger upon Escape."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(200)

        # 1. Help Drawer
        btn_help = page.locator("#btnOpenHelp")
        assert btn_help.is_visible()
        btn_help.click()
        page.wait_for_timeout(200)

        help_drawer = page.locator("#helpDrawer")
        assert help_drawer.is_visible()

        # Escape closes help drawer and restores focus
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert "active" not in (help_drawer.get_attribute("class") or "")
        assert help_drawer.is_hidden()

        restored_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
        assert restored_id == "btnOpenHelp", f"Focus must restore to #btnOpenHelp, got '{restored_id}'"

        # 2. Logs Drawer
        btn_logs = page.locator("#btnOpenLogs")
        assert btn_logs.is_visible()
        btn_logs.click()
        page.wait_for_timeout(200)

        logs_drawer = page.locator("#logsDrawer")
        assert logs_drawer.is_visible()

        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
        assert "active" not in (logs_drawer.get_attribute("class") or "")
        assert logs_drawer.is_hidden()

        restored_id = page.evaluate("() => document.activeElement ? document.activeElement.id : null")
        assert restored_id == "btnOpenLogs", f"Focus must restore to #btnOpenLogs, got '{restored_id}'"

        browser.close()


def test_playwright_keyboard_dropzones_activation():
    """Verify that drop zones are focusable and activate on Enter and Space."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(200)

        # Mock loadSchedule and loadRosters to track keyboard triggers
        page.evaluate("""() => {
            window.__dropZoneCalls = { schedule: 0, rosters: 0 };
            window.loadSchedule = () => { window.__dropZoneCalls.schedule += 1; };
            window.loadRosters = () => { window.__dropZoneCalls.rosters += 1; };
        }""")

        # Focus Schedule drop zone and press Enter
        drop_sched = page.locator("#scheduleDropzone")
        assert drop_sched.is_visible()
        drop_sched.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(50)

        # Press Space
        page.keyboard.press("Space")
        page.wait_for_timeout(50)

        calls = page.evaluate("() => window.__dropZoneCalls")
        assert calls["schedule"] == 2, f"Schedule drop zone must trigger on Enter and Space, got {calls['schedule']}"

        # Focus Rosters drop zone and press Enter
        drop_rosters = page.locator("#rostersDropzone")
        assert drop_rosters.is_visible()
        drop_rosters.focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(50)

        # Press Space
        page.keyboard.press("Space")
        page.wait_for_timeout(50)

        calls = page.evaluate("() => window.__dropZoneCalls")
        assert calls["rosters"] == 2, f"Rosters drop zone must trigger on Enter and Space, got {calls['rosters']}"

        browser.close()


def test_playwright_axe_core_initial_scan():
    """Run axe-core accessibility engine on the live rendered UI to catch semantic,

    contrast, ARIA, and landmark violations.
    """
    if not os.path.exists(AXE_JS_PATH):
        pytest.skip(f"axe.min.js not found at {AXE_JS_PATH}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)
        page.wait_for_timeout(300)

        # Inject local axe-core library
        page.add_script_tag(path=AXE_JS_PATH)

        # Run axe scan
        scan_results = page.evaluate("""() => {
            return new Promise((resolve) => {
                axe.run(document, {
                    runOnly: {
                        type: 'tag',
                        values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']
                    }
                }, (err, results) => {
                    if (err) resolve({ error: String(err) });
                    resolve(results);
                });
            });
        }""")

        assert "error" not in scan_results, f"axe scan failed: {scan_results.get('error')}"

        violations = scan_results.get("violations", [])
        # Filter for critical or serious violations
        critical_or_serious = [
            v for v in violations
            if v.get("impact") in ("critical", "serious")
        ]

        if critical_or_serious:
            summary = "\n".join(
                f"- [{v['impact']}] {v['id']}: {v['help']} (targets: {[n.get('target') for n in v.get('nodes', [])[:2]]})"
                for v in critical_or_serious
            )
            pytest.fail(f"axe-core found {len(critical_or_serious)} critical/serious accessibility violations:\n{summary}")

        browser.close()
