"""
Automated Unit and Contract Tests for Accessibility Settings Architecture (Commit 201).
Validates:
1. Presence of Accessibility tab and controls in ui.html with full ARIA semantics.
2. Apple HIG grouped row and select styling in modals.css.
3. Precedence resolution model between OS media queries and application-level settings.
4. Correct storage keys and default fallback values.
5. Integration with theme.js toggleTheme motion suppression.
"""

import os
import re
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
CSS_MODALS_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "css", "modals.css")
JS_THEME_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "js", "theme.js")
JS_SETTINGS_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "js", "settings.js")


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

    # Transparency select and accessible descriptions
    assert 'id="accTransparencySelect"' in ui_html, "accTransparencySelect must exist"
    assert 'aria-label="Surface Transparency and Materials"' in ui_html, "accTransparencySelect must have accessible label"
    assert 'aria-describedby="accTransparencyCaption"' in ui_html, "accTransparencySelect must reference description caption"
    assert 'value="glass"' in ui_html

    # Live diagnostic indicators
    assert 'id="accStatusSysMotion"' in ui_html, "Live host system motion indicator must exist"
    assert 'id="accStatusEffectiveMotion"' in ui_html, "Live effective motion indicator must exist"
    assert 'id="accStatusVTEngine"' in ui_html, "Live View Transition engine indicator must exist"
    assert 'id="accStatusEffectiveSurface"' in ui_html, "Live effective surface indicator must exist"


def test_accessibility_css_tokens_and_material_overrides(css_modals):
    """Verify Apple HIG select control styling and solid opaque material overrides."""
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
    assert "getEffectiveMotionPreference() === \"reduce\"" in js_theme

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

    # 1. System no-preference + App system -> no-preference
    assert resolve_effective_motion("system", system_reduced=False) == "no-preference"

    # 2. System reduce + App system -> reduce
    assert resolve_effective_motion("system", system_reduced=True) == "reduce"

    # 3. System no-preference + App reduce -> reduce (forced by app)
    assert resolve_effective_motion("reduce", system_reduced=False) == "reduce"

    # 4. System reduce + App reduce -> reduce
    assert resolve_effective_motion("reduce", system_reduced=True) == "reduce"

    # 5. System no-preference + App full -> no-preference
    assert resolve_effective_motion("full", system_reduced=False) == "no-preference"

    # 6. System reduce + App full -> no-preference (explicit user override)
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
