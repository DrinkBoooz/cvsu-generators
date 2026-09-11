import os
import re
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable", "ui.html")

@pytest.fixture
def ui_content():
    assert os.path.exists(UI_HTML_PATH), f"File {UI_HTML_PATH} does not exist"
    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()

def test_stepper_semantic_separation(ui_content):
    """Verify that .active-step does not color incomplete chip numbers green."""
    # .step-chip.ready must use accent-emerald
    assert ".step-chip.ready" in ui_content
    assert ".step-chip.ready .chip-num" in ui_content
    
    # .step-chip.active-step must use neutral surface-hover/text-primary for chip-num
    active_num_pattern = r'\.step-chip\.active-step\s+\.chip-num\s*\{[^}]*background:\s*var\(--surface-hover\)'
    assert re.search(active_num_pattern, ui_content), ".step-chip.active-step .chip-num must use neutral background"

    # .step-chip.ready.active-step must retain emerald
    ready_active_pattern = r'\.step-chip\.ready\.active-step\s+\.chip-num\s*\{[^}]*background:\s*var\(--accent-emerald\)'
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
