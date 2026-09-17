import os
import re
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
CSS_DIR = os.path.join(WORKSPACE_DIR, "executable_test", "css")
JS_DIR = os.path.join(WORKSPACE_DIR, "executable_test", "js")


def get_ui_html():
    assert os.path.exists(UI_HTML_PATH), "ui.html must exist"
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


def get_css_bundle():
    bundle = ""
    for f in sorted(os.listdir(CSS_DIR)):
        if f.endswith(".css"):
            with open(os.path.join(CSS_DIR, f), "r", encoding="utf-8") as file:
                bundle += f"\n/* === {f} === */\n" + file.read()
    return bundle


def get_js_bundle():
    bundle = ""
    for f in sorted(os.listdir(JS_DIR)):
        if f.endswith(".js"):
            with open(os.path.join(JS_DIR, f), "r", encoding="utf-8") as file:
                bundle += f"\n// === {f} ===\n" + file.read()
    return bundle


def test_accessibility_landmarks():
    """Verify primary ARIA landmarks: main, header, and navigation."""
    ui = get_ui_html()

    # Main landmark must exist
    assert '<main id="mainContent"' in ui, "ui.html must contain a <main> landmark"
    assert 'role="main"' in ui, "main container must specify role='main'"
    assert "</main>" in ui

    # Header and navigation landmarks
    assert "<header class=\"top-header\">" in ui
    assert '<nav aria-label="Quick Actions"' in ui
    assert '<nav aria-label="Workflow Steps"' in ui

    # Drawers must be defined as accessible regions
    assert '<aside id="helpDrawer" class="drawer-panel" role="region" aria-label=' in ui
    assert '<aside id="logsDrawer" class="drawer-panel" role="region" aria-label=' in ui


def test_dropzones_accessibility_and_keyboard():
    """Verify all dropzones have tabindex, button role, aria-label, and keyboard handlers."""
    ui = get_ui_html()

    dropzone_ids = ["scheduleDropzone", "rostersDropzone", "templateDropzone"]
    for dz_id in dropzone_ids:
        # Match dropzone block
        pattern = rf'<div[^>]*id="{dz_id}"[^>]*>'
        match = re.search(pattern, ui, re.DOTALL)
        assert match, f"Dropzone #{dz_id} not found in ui.html"
        tag = match.group(0)

        assert 'tabindex="0"' in tag, f"#{dz_id} must have tabindex='0'"
        assert 'role="button"' in tag, f"#{dz_id} must have role='button'"
        assert 'aria-label="' in tag, f"#{dz_id} must have an aria-label"
        assert "onkeydown=" in tag, f"#{dz_id} must have an onkeydown handler"
        assert "Enter" in tag and " " in tag, f"#{dz_id} onkeydown must support both Enter and Space"


def test_modals_dialog_roles_and_labeling():
    """Verify modal backdrops have role=dialog, aria-modal=true, and labeling attributes."""
    ui = get_ui_html()

    modals = [
        ("modalAppleConfirmBackdrop", "appleConfirmTitle", "appleConfirmMessage"),
        ("modalParserSettingsBackdrop", "settingsModalTitle", "settingsModalSubtitle"),
        ("modalRosterMappingBackdrop", "mapModalFilename", "mapModalSubtitle"),
    ]

    for m_id, title_id, desc_id in modals:
        pattern = rf'<div[^>]*id="{m_id}"[^>]*>'
        match = re.search(pattern, ui, re.DOTALL)
        assert match, f"Modal #{m_id} not found"
        tag = match.group(0)

        assert 'role="dialog"' in tag, f"#{m_id} must have role='dialog'"
        assert 'aria-modal="true"' in tag, f"#{m_id} must have aria-modal='true'"
        assert f'aria-labelledby="{title_id}"' in tag, f"#{m_id} must reference aria-labelledby='{title_id}'"
        assert f'aria-describedby="{desc_id}"' in tag, f"#{m_id} must reference aria-describedby='{desc_id}'"

    # All modal close buttons must have aria-label
    assert 'id="btnCloseSettingsModal"' in ui and 'aria-label="Close settings modal"' in ui
    assert 'id="btnCloseMappingModal"' in ui and 'aria-label="Close roster mapping modal"' in ui
    assert 'id="btnCloseLogs"' in ui and 'aria-label="Close logs drawer"' in ui


def test_tables_scope_and_semantics():
    """Verify data tables have scope=col on headers, caption/aria-label, and row scopes."""
    ui = get_ui_html()
    js = get_js_bundle()

    # ceitPrefixTable in help drawer
    assert 'id="ceitPrefixTable"' in ui
    assert '<caption class="sr-only">CEIT Academic Departments and Subject Prefixes Directory</caption>' in ui
    assert '<th scope="col"' in ui

    # Settings tables
    assert 'aria-label="Configured Subject Prefixes Table"' in ui
    assert 'aria-label="Configured Degree Aliases Table"' in ui

    # Raw spreadsheet preview grid in step2.js
    assert 'aria-label="Raw Spreadsheet Preview Grid"' in js
    assert '<th scope="col"' in js
    assert '<th scope="row"' in js
    # Non-color textual tags
    assert '(Name)' in js
    assert '(ID)' in js
    assert '[H]' in js


def test_progress_live_region_and_announcer():
    """Verify ARIA progressbar, live regions, and screen-reader announcements."""
    ui = get_ui_html()
    js = get_js_bundle()

    # Progress bar attributes
    assert 'id="progressContainer"' in ui
    assert 'role="progressbar"' in ui
    assert 'aria-valuemin="0"' in ui
    assert 'aria-valuemax="100"' in ui
    assert 'aria-valuenow=' in ui
    assert 'aria-valuetext=' in ui

    # Live regions
    assert 'id="toastContainer"' in ui
    assert 'aria-live="polite"' in ui
    assert 'aria-atomic="true"' in ui
    assert 'id="a11yLiveAnnouncer"' in ui
    assert 'class="sr-only"' in ui

    # Toast semantics
    assert 'toast.setAttribute("role", type === "error" ? "alert" : "status")' in js
    assert 'toast.setAttribute("aria-live", type === "error" ? "assertive" : "polite")' in js
    assert 'aria-label="Close notification"' in js
    assert "announceA11y" in js


def test_focus_visible_and_high_contrast_css():
    """Verify high-visibility focus indicators and forced-colors high-contrast CSS rules."""
    css = get_css_bundle()

    # Tokens
    assert "--a11y-focus-ring-color:" in css
    assert "--a11y-focus-ring-offset:" in css
    assert "--a11y-focus-ring-width:" in css
    assert "--a11y-focus-glow:" in css

    # Focus-visible styles
    assert ":focus-visible" in css
    assert ".segmented-btn:focus-visible" in css
    assert ".filter-pill:focus-visible" in css
    assert ".step-chip:focus-visible" in css
    assert ".drawer-tab:focus-visible" in css
    assert ".type-dropdown:focus-visible" in css
    assert ".text-input:focus-visible" in css
    assert ".date-input:focus-visible" in css

    # Windows High Contrast Mode / Forced Colors
    assert "@media (forced-colors: active)" in css
    assert "outline: 3px solid Highlight" in css
    assert "ButtonBorder" in css
    assert "CanvasText" in css
    assert "HighlightText" in css


def test_focus_trap_manager_and_focus_return():
    """Verify FocusTrapManager implementation and focus restoration across modals/drawers."""
    js = get_js_bundle()

    # FocusTrapManager declaration and key methods
    assert "const FocusTrapManager =" in js
    assert "trap(container" in js
    assert "release(" in js
    assert "previousTrigger" in js
    assert "stack" in js

    # Modal integrations
    assert re.search(r"FocusTrapManager\.trap\(\s*backdrop", js), "Apple Confirm must trap focus"
    assert re.search(r"FocusTrapManager\.trap\(\s*modal", js), "Settings & Mapping must trap focus"
    assert re.search(r"FocusTrapManager\.trap\(\s*drawer", js), "Help & Logs must trap focus"
    assert "FocusTrapManager.release()" in js


def test_stepper_aria_labels_dynamic():
    """Verify stepper buttons have accessible labels and dynamic updates."""
    ui = get_ui_html()
    js = get_js_bundle()

    for i in range(1, 7):
        assert f'id="chipStep{i}"' in ui
        assert f'aria-label="Step {i}:' in ui
        assert f'id="statusStep{i}" aria-hidden="true"' in ui

    # Dynamic setter updates aria-label
    assert 'chip.setAttribute("aria-label", `Step ${num}: ${name} - ${statusText}`)' in js
