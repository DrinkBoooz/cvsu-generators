import os
import re
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")

@pytest.fixture
def ui_content():
    assert os.path.exists(UI_HTML_PATH), f"File {UI_HTML_PATH} does not exist"
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    exec_dir = os.path.dirname(UI_HTML_PATH)
    css_dir = os.path.join(exec_dir, "css")
    if os.path.isdir(css_dir):
        for f in os.listdir(css_dir):
            if f.endswith(".css"):
                with open(os.path.join(css_dir, f), "r", encoding="utf-8") as cf:
                    content += "\n" + cf.read()
    js_dir = os.path.join(exec_dir, "js")
    if os.path.isdir(js_dir):
        for f in os.listdir(js_dir):
            if f.endswith(".js"):
                with open(os.path.join(js_dir, f), "r", encoding="utf-8") as jf:
                    content += "\n" + jf.read()
    return content

def test_color_scheme_declarations(ui_content):
    # Verify color-scheme is declared for both light and dark themes
    assert "color-scheme: light;" in ui_content, "color-scheme: light; must be declared in :root"
    assert "color-scheme: dark;" in ui_content, "color-scheme: dark; must be declared in [data-bs-theme=\"dark\"]"

def test_date_picker_indicator_theme_rules(ui_content):
    # Verify webkit-calendar-picker-indicator rules exist
    assert "::-webkit-calendar-picker-indicator" in ui_content, "Calendar picker indicator must be styled"
    
    # Verify dark mode date input has explicit color-scheme: dark and indicator avoids black-inverting filter
    assert (
        '[data-theme="dark"] .date-input' in ui_content
        or '[data-bs-theme="dark"] .date-input' in ui_content
    ), "Dark mode must explicitly configure .date-input"
    dark_indicator_pattern = r'\[data-(?:bs-)?theme=["\']dark["\']\]\s*\.date-input::-webkit-calendar-picker-indicator\s*\{[^}]*filter:\s*none'
    assert re.search(dark_indicator_pattern, ui_content), "Dark mode calendar indicator must use filter: none to prevent turning black"

    # Verify focus state for .date-input
    assert ".date-input:focus" in ui_content, ".date-input:focus must be explicitly defined"

def test_custom_scrollbars_and_placeholders(ui_content):
    # Verify custom scrollbars are defined
    assert "::-webkit-scrollbar" in ui_content, "Custom scrollbar width/style must be defined"
    assert "::-webkit-scrollbar-thumb" in ui_content, "Custom scrollbar thumb must be defined"
    assert "scrollbar-color:" in ui_content, "Standard CSS scrollbar-color must be defined"

    # Verify placeholder styling exists
    assert "::placeholder" in ui_content, "Placeholder styling must be defined"

    # Verify selection styling
    assert "::selection" in ui_content, "Emerald selection styling must be defined"

def test_select_option_theming(ui_content):
    # Verify native select option styling
    assert ".type-dropdown option" in ui_content, ".type-dropdown option must be styled for dark mode consistency"

def test_theme_toggle_elements_and_logic(ui_content):
    # Verify toggle theme button has proper IDs and dynamic elements
    assert 'id="btnToggleTheme"' in ui_content, "btnToggleTheme ID must exist in HTML"
    assert 'id="themeIcon"' in ui_content, "themeIcon ID must exist in HTML"
    assert 'id="themeLabel"' in ui_content, "themeLabel ID must exist in HTML"

    # Verify updateThemeButtonState function exists in JS
    assert "function updateThemeButtonState" in ui_content, "updateThemeButtonState function must exist in JS"
    assert "SUN_ICON_SVG" in ui_content, "SUN_ICON_SVG must exist in JS"
    assert "MOON_ICON_SVG" in ui_content, "MOON_ICON_SVG must exist in JS"
