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

def test_stepper_semantic_separation(ui_content):
    """Verify that .active-step does not color incomplete chip numbers green."""
    # .step-chip.ready must use accent-emerald
    assert ".step-chip.ready" in ui_content
    assert ".step-chip.ready .chip-num" in ui_content
    
    # .step-chip.active-step must define dedicated chip-num styling
    assert ".step-chip.active-step .chip-num" in ui_content

    # .step-chip.ready.active-step must retain emerald
    ready_active_pattern = r'\.step-chip\.ready(?:\.active-step)?\s+\.chip-num[^{]*\{[^}]*background:\s*var\(--accent-emerald\)'
    assert re.search(ready_active_pattern, ui_content), ".step-chip.ready.active-step .chip-num must retain emerald"

def test_card_spotlight_definition(ui_content):
    """Verify card spotlight class exists for smooth navigation feedback."""
    assert ".glass-card.card-spotlight" in ui_content

def test_focal_scroll_spy_variables_and_functions(ui_content):
    """Verify 2-column focal scroll-spy engine declarations exist."""
    assert "const STEP_CARD_IDS = [" in ui_content
    assert "const STEP_CHIP_IDS = [" in ui_content
    assert "function setActiveStepChip" in ui_content
    assert "window._scrollSpyLockedUntil" in ui_content
