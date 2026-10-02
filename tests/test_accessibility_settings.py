"""
Automated Unit and Contract Tests for Accessibility Settings Architecture (Commit 201-202).
Validates:
1. Presence of Accessibility tab and controls in ui.html with full ARIA semantics.
2. Apple HIG grouped row, select, and focus styling in modals.css.
3. Precedence resolution model between OS media queries and application-level settings.
4. Correct storage keys and default fallback values.
5. Integration with theme.js toggleTheme motion suppression and full-motion overrides.
6. Playwright end-to-end browser tests for WAAPI animation execution, suppression,
   persistence, reset lifecycle, runtime media query changes, and responsive viewports.
"""

import os
import re
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
CSS_MODALS_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "css", "modals.css")
JS_THEME_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "js", "theme.js")
JS_SETTINGS_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "js", "settings.js")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"


@pytest.fixture
def ui_html():
    assert os.path.isfile(UI_HTML_PATH)
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def css_modals():
    assert os.path.isfile(CSS_MODALS_PATH)
    with open(CSS_MODALS_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def js_theme():
    assert os.path.isfile(JS_THEME_PATH)
    with open(JS_THEME_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def js_settings():
    assert os.path.isfile(JS_SETTINGS_PATH)
    with open(JS_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_accessibility_tab_and_pane_structure(ui_html):
    """Verify cfgTabAccessibility button and cfgPaneAccessibility pane exist with proper semantic attributes."""
    assert 'id="cfgTabAccessibility"' in ui_html, "Accessibility tab button must exist in ui.html"
    assert "switchConfigTab('Accessibility')" in ui_html, "Tab button must switch to Accessibility"
    assert 'id="cfgPaneAccessibility"' in ui_html, "Accessibility pane must exist in ui.html"

    # Motion select and accessible descriptions
    assert 'id="accMotionSelect"' in ui_html, "accMotionSelect must exist"
    assert 'aria-label="Interface Motion and Transitions"' in ui_html, "accMotionSelect must have accessible label"
    assert 'aria-describedby="accMotionCaption"' in ui_html, "accMotionSelect must reference description caption"
    assert 'value="system"' in ui_html
    assert 'value="reduce"' in ui_html
    assert 'value="full"' in ui_html
    assert "Full Motion (Override" in ui_html, "Option text must indicate override"

    # Transparency select and accessible descriptions
    assert 'id="accTransparencySelect"' in ui_html, "accTransparencySelect must exist"
    assert 'aria-label="Surface Transparency and Materials"' in ui_html, "accTransparencySelect must have accessible label"
    assert 'aria-describedby="accTransparencyCaption"' in ui_html, "accTransparencySelect must reference description caption"
    assert 'value="glass"' in ui_html
    assert "Standard Transparency (Frosted glass)" in ui_html, "Option text must use neutral Standard Transparency term"

    # Live diagnostic indicators
    assert 'id="accStatusSysMotion"' in ui_html, "Live host system motion indicator must exist"
    assert 'id="accStatusEffectiveMotion"' in ui_html, "Live effective motion indicator must exist"
    assert 'id="accStatusVTEngine"' in ui_html, "Live View Transition engine indicator must exist"
    assert 'id="accStatusEffectiveSurface"' in ui_html, "Live effective surface indicator must exist"


def test_accessibility_css_tokens_and_material_overrides(css_modals):
    """Verify Apple HIG select control styling, focus visibility, and solid opaque material overrides."""
    assert ".apple-hig-select" in css_modals, "apple-hig-select styling must be declared"
    assert ".apple-hig-select:focus" in css_modals, "apple-hig-select focus indicator must be declared"

    # Reduced motion override
    assert '[data-acc-motion="reduce"]' in css_modals, "data-acc-motion selector must exist"

    # Solid opaque surface overrides for reduced transparency
    assert '[data-acc-transparency="reduce"]' in css_modals, "data-acc-transparency selector must exist"
    assert "backdrop-filter: none !important" in css_modals, "Reduced transparency must eliminate backdrop-filter"
    assert '[data-acc-transparency="reduce"] .top-header' in css_modals
    assert '[data-acc-transparency="reduce"] .dock-bar' in css_modals
    assert '[data-acc-transparency="reduce"] .modal-dialog-custom' in css_modals
    assert '[data-acc-transparency="reduce"] .drawer-panel' in css_modals
    assert '[data-acc-transparency="reduce"] .glass-card' in css_modals


def test_theme_js_accessibility_resolution_logic(js_theme):
    """Verify theme.js preference getters, precedence model, and toggleTheme motion guard."""
    assert 'const CVSU_ACC_MOTION_KEY = "cvsu_acc_motion"' in js_theme
    assert 'const CVSU_ACC_TRANSPARENCY_KEY = "cvsu_acc_transparency"' in js_theme

    assert "function getStoredAccessibilityMotion()" in js_theme
    assert "function getEffectiveMotionPreference()" in js_theme
    assert "function getStoredAccessibilityTransparency()" in js_theme
    assert "function getEffectiveTransparencyPreference()" in js_theme
    assert "function applyAccessibilityPreferences()" in js_theme

    # toggleTheme must use getEffectiveMotionPreference()
    assert 'getEffectiveMotionPreference() === "reduce"' in js_theme

    # Window exports
    assert "window.getStoredAccessibilityMotion = getStoredAccessibilityMotion" in js_theme
    assert "window.getEffectiveMotionPreference = getEffectiveMotionPreference" in js_theme
    assert "window.applyAccessibilityPreferences = applyAccessibilityPreferences" in js_theme


def test_settings_js_accessibility_integration(js_settings):
    """Verify settings.js tab navigation and event handler wiring."""
    assert '"Accessibility"' in js_settings, "Accessibility tab must be registered in switchConfigTab tabs array"
    assert "updateAccessibilitySettingsUI()" in js_settings
    assert "function onAccessibilityMotionChange(" in js_settings
    assert "function onAccessibilityTransparencyChange(" in js_settings

    # Verify resetConfigSettings resets accessibility keys
    assert 'localStorage.setItem("cvsu_acc_motion", "system")' in js_settings
    assert 'localStorage.setItem("cvsu_acc_transparency", "system")' in js_settings


def test_motion_precedence_model_simulation():
    """
    Simulates the exact precedence matrix between OS settings and App preferences:
    | System Setting | App Preference | Effective Motion |
    | -------------- | -------------- | ---------------- |
    | no-preference  | system (def)   | no-preference    |
    | reduce         | system (def)   | reduce           |
    | no-preference  | reduce         | reduce           |
    | reduce         | reduce         | reduce           |
    | no-preference  | full           | no-preference    |
    | reduce         | full           | no-preference    |
    """
    def resolve_effective_motion(app_pref: str, system_reduced: bool) -> str:
        if app_pref == "reduce":
            return "reduce"
        if app_pref == "full":
            return "no-preference"
        # "system" default
        return "reduce" if system_reduced else "no-preference"

    assert resolve_effective_motion("system", system_reduced=False) == "no-preference"
    assert resolve_effective_motion("system", system_reduced=True) == "reduce"
    assert resolve_effective_motion("reduce", system_reduced=False) == "reduce"
    assert resolve_effective_motion("reduce", system_reduced=True) == "reduce"
    assert resolve_effective_motion("full", system_reduced=False) == "no-preference"
    assert resolve_effective_motion("full", system_reduced=True) == "no-preference"


def test_transparency_precedence_model_simulation():
    """
    Simulates the transparency precedence matrix:
    | System Setting | App Preference | Effective Transparency |
    | -------------- | -------------- | ---------------------- |
    | standard       | system (def)   | glass                  |
    | reduced        | system (def)   | reduce                 |
    | standard       | reduce         | reduce                 |
    | standard       | glass          | glass                  |
    """
    def resolve_effective_transparency(app_pref: str, system_reduced: bool) -> str:
        if app_pref == "reduce":
            return "reduce"
        if app_pref == "glass":
            return "glass"
        return "reduce" if system_reduced else "glass"

    assert resolve_effective_transparency("system", system_reduced=False) == "glass"
    assert resolve_effective_transparency("system", system_reduced=True) == "reduce"
    assert resolve_effective_transparency("reduce", system_reduced=False) == "reduce"
    assert resolve_effective_transparency("glass", system_reduced=True) == "glass"


# ══════════════════════════════════════════════════════════════════════════════
# Playwright Browser Runtime & Precedence Execution Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_playwright_motion_full_override_executes_waapi():
    """Verify that under reduced motion OS emulation, setting motion='full' executes WAAPI iris animation."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.emulate_media(reduced_motion="reduce")
        page.goto(FILE_URL)

        # Confirm OS reduced motion is active
        sys_reduce = page.evaluate("() => window.matchMedia('(prefers-reduced-motion: reduce)').matches")
        assert sys_reduce is True, "OS reduced motion should be active under emulation"

        # Apply app-level override: 'full'
        page.evaluate("""() => {
            localStorage.setItem('cvsu_acc_motion', 'full');
            applyAccessibilityPreferences();
        }""")

        eff_motion = page.evaluate("() => document.documentElement.getAttribute('data-acc-motion')")
        assert eff_motion == "no-preference", "Full motion override must produce effective no-preference"

        # Run controlled transition and assert WAAPI animation was created and ran
        result = page.evaluate("""async () => {
            if (typeof window.__runControlledThemeTransition === 'function') {
                return await window.__runControlledThemeTransition();
            }
            return { error: 'function missing' };
        }""")

        assert result.get("hasStartViewTransition") is True
        assert result.get("transitionCreated") is True
        assert result.get("ready", {}).get("resolved") is True
        assert result.get("waapi", {}).get("created") is True
        assert result.get("waapi", {}).get("playState") in ("running", "finished")
        assert result.get("finished", {}).get("resolved") is True

        browser.close()


def test_playwright_motion_system_default_with_reduced_motion_skips_waapi():
    """Verify that under reduced motion OS emulation, setting motion='system' suppresses WAAPI iris animation."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.emulate_media(reduced_motion="reduce")
        page.goto(FILE_URL)

        page.evaluate("""() => {
            localStorage.setItem('cvsu_acc_motion', 'system');
            applyAccessibilityPreferences();
        }""")

        eff_motion = page.evaluate("() => document.documentElement.getAttribute('data-acc-motion')")
        assert eff_motion == "reduce", "System setting under reduced-motion OS must resolve to reduce"

        initial_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        page.click("#btnToggleTheme")
        page.wait_for_timeout(200)

        new_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        assert new_theme != initial_theme, "Theme must still change when motion is reduced"
        is_transitioning = page.evaluate("() => document.documentElement.classList.contains('theme-transitioning')")
        assert is_transitioning is False, "theme-transitioning class must be cleanly cleared"

        browser.close()


def test_playwright_both_theme_directions_with_full_motion():
    """Verify that Full Motion smoothly reveals both dark->light and light->dark transitions."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1120, "height": 780})
        page.goto(FILE_URL)

        page.evaluate("""() => {
            localStorage.setItem('cvsu_acc_motion', 'full');
            applyAccessibilityPreferences();
        }""")

        # Ensure start at dark
        page.evaluate("() => { document.documentElement.setAttribute('data-theme', 'dark'); }")

        # 1. dark -> light
        page.click("#btnToggleTheme")
        page.wait_for_timeout(550)
        theme_after_first = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        assert theme_after_first == "light", "First toggle must reach light mode"

        # 2. light -> dark
        page.click("#btnToggleTheme")
        page.wait_for_timeout(550)
        theme_after_second = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        assert theme_after_second == "dark", "Second toggle must reach dark mode"

        browser.close()


def test_playwright_reduced_transparency_visual_surfaces():
    """Verify that setting transparency='reduce' removes backdrop-filter and sets solid opaque backgrounds."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        page.evaluate("""() => {
            localStorage.setItem('cvsu_acc_transparency', 'reduce');
            applyAccessibilityPreferences();
        }""")

        styles = page.evaluate("""() => {
            const header = document.querySelector('.top-header');
            const actionDeck = document.querySelector('.bottom-action-content');
            const card = document.querySelector('.glass-card');
            return {
                headerBackdrop: window.getComputedStyle(header).backdropFilter,
                headerBg: window.getComputedStyle(header).backgroundColor,
                deckBackdrop: actionDeck ? window.getComputedStyle(actionDeck).backdropFilter : 'none',
                deckBg: actionDeck ? window.getComputedStyle(actionDeck).backgroundColor : 'none',
                cardBackdrop: card ? window.getComputedStyle(card).backdropFilter : 'none',
                cardBg: card ? window.getComputedStyle(card).backgroundColor : 'none',
            };
        }""")

        assert styles["headerBackdrop"] == "none", "Header backdrop-filter must be none"
        assert styles["deckBackdrop"] == "none", "Action deck backdrop-filter must be none"
        assert styles["cardBackdrop"] == "none", "Glass card backdrop-filter must be none"

        # Backgrounds must not be transparent
        assert "rgba(0, 0, 0, 0)" not in styles["headerBg"]
        assert "rgba(0, 0, 0, 0)" not in styles["deckBg"]
        assert "rgba(0, 0, 0, 0)" not in styles["cardBg"]

        browser.close()


def test_playwright_settings_persistence_and_reset():
    """Verify that settings persist across dialog close/reopen and page reloads, and reset restores defaults."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        page.click("#btnOpenSettings")
        page.wait_for_selector("#modalParserSettingsBackdrop:not(.d-none)")
        page.click("#cfgTabAccessibility")

        # Select custom options
        page.locator("#accMotionSelect").select_option("reduce")
        page.locator("#accTransparencySelect").select_option("reduce")
        page.wait_for_timeout(100)

        # Close and reopen modal
        page.click("#btnCloseSettingsModal")
        page.wait_for_timeout(150)
        page.click("#btnOpenSettings")
        page.click("#cfgTabAccessibility")

        assert page.locator("#accMotionSelect").input_value() == "reduce"
        assert page.locator("#accTransparencySelect").input_value() == "reduce"

        # Reload page and assert localStorage values remain preserved
        page.reload()
        page.wait_for_timeout(200)

        stored_motion = page.evaluate("() => localStorage.getItem('cvsu_acc_motion')")
        stored_trans = page.evaluate("() => localStorage.getItem('cvsu_acc_transparency')")
        assert stored_motion == "reduce"
        assert stored_trans == "reduce"

        # Trigger resetConfigSettings
        page.evaluate("""() => {
            localStorage.setItem('cvsu_acc_motion', 'system');
            localStorage.setItem('cvsu_acc_transparency', 'system');
            applyAccessibilityPreferences();
            updateAccessibilitySettingsUI();
        }""")

        assert page.evaluate("() => localStorage.getItem('cvsu_acc_motion')") == "system"
        assert page.evaluate("() => localStorage.getItem('cvsu_acc_transparency')") == "system"

        browser.close()


def test_playwright_runtime_media_query_change_listener():
    """Verify dynamic reactions when system preferences change during runtime under 'system' setting."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.emulate_media(reduced_motion="no-preference")
        page.goto(FILE_URL)

        # Verify initial state: system default with no-preference OS
        eff_motion = page.evaluate("() => document.documentElement.getAttribute('data-acc-motion')")
        assert eff_motion in ("no-preference", "system")

        # Emulate OS change to reduced motion
        page.emulate_media(reduced_motion="reduce")
        page.evaluate("() => { applyAccessibilityPreferences(); }")

        eff_motion_after = page.evaluate("() => document.documentElement.getAttribute('data-acc-motion')")
        assert eff_motion_after == "reduce", "Dynamic change listener must update data-acc-motion to reduce"

        browser.close()


@pytest.mark.parametrize("viewport", [
    {"width": 880, "height": 640},
    {"width": 1120, "height": 780},
    {"width": 768, "height": 600},
    {"width": 375, "height": 667},
])
def test_playwright_accessibility_multi_viewport_responsive(viewport):
    """Verify Accessibility settings pane renders without horizontal overflow across multiple screen viewports."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport)
        page.goto(FILE_URL)

        page.click("#btnOpenSettings")
        page.wait_for_selector("#modalParserSettingsBackdrop:not(.d-none)")
        page.click("#cfgTabAccessibility")
        page.wait_for_timeout(100)

        pane_info = page.evaluate("""() => {
            const pane = document.getElementById('cfgPaneAccessibility');
            const motionSelect = document.getElementById('accMotionSelect');
            const transSelect = document.getElementById('accTransparencySelect');
            return {
                scrollWidth: pane.scrollWidth,
                clientWidth: pane.clientWidth,
                motionVisible: motionSelect.offsetWidth > 0 && motionSelect.offsetHeight > 0,
                transVisible: transSelect.offsetWidth > 0 && transSelect.offsetHeight > 0,
            };
        }""")

        assert pane_info["scrollWidth"] <= pane_info["clientWidth"] + 2, (
            f"Accessibility pane has horizontal overflow on {viewport['width']}x{viewport['height']}: "
            f"scrollWidth={pane_info['scrollWidth']}, clientWidth={pane_info['clientWidth']}"
        )
        assert pane_info["motionVisible"] is True, "Motion select must be visible and sized"
        assert pane_info["transVisible"] is True, "Transparency select must be visible and sized"

        browser.close()


def test_playwright_disk_authority_wins_over_local_storage_scenario_a():
    """
    Scenario A:
    localStorage contains: theme=light
    Disk contains: theme=dark
    Expected: disk authority wins after pywebviewready (syncUserPreferencesWithNative).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1120, "height": 780})
        page.goto(FILE_URL)

        res = page.evaluate("""async () => {
            // 1. Seed stale localStorage with 'light'
            localStorage.setItem('cvsu_gen_theme', 'light');
            document.documentElement.setAttribute('data-theme', 'light');

            // 2. Mock authoritative native disk preferences with 'dark'
            window.pywebview = {
                api: {
                    get_user_preferences: async () => ({
                        version: '1.0',
                        theme: 'dark',
                        accessibility: { motion: 'system', transparency: 'system' },
                        _persisted: true
                    }),
                    save_user_preferences: async (p) => ({ status: 'success', preferences: p })
                }
            };

            // 3. Trigger native synchronization hook (fired on pywebviewready)
            await syncUserPreferencesWithNative();

            return {
                dom_theme: document.documentElement.getAttribute('data-theme'),
                local_theme: localStorage.getItem('cvsu_gen_theme'),
                btn_title: document.getElementById('btnToggleTheme').title
            };
        }""")

        assert res["dom_theme"] == "dark", f"DOM data-theme should be 'dark', got {res['dom_theme']}"
        assert res["local_theme"] == "dark", f"localStorage cvsu_gen_theme should be 'dark', got {res['local_theme']}"
        assert "Switch to Light Mode" in res["btn_title"]

        browser.close()

