import os
import inspect
import pytest
from executable.main import ScriptAPI

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_EXEC_DIR = os.path.join(WORKSPACE_ROOT, "executable_test")

def test_script_api_signatures_match_pywebview_calls():
    """Ensure Python ScriptAPI methods match TypeScript pywebviewService calls without argument mismatch."""
    api = ScriptAPI()

    # browse_schedule takes 0 arguments (besides self)
    sig_sched = inspect.signature(api.browse_schedule)
    assert len(sig_sched.parameters) == 0, "browse_schedule must take 0 parameters to avoid TypeError"

    # browse_output takes 0 arguments (besides self)
    sig_out = inspect.signature(api.browse_output)
    assert len(sig_out.parameters) == 0, "browse_output must take 0 parameters"

    # handle_dropped_schedule takes filename, base64_data=None, original_path=None
    sig_drop_sched = inspect.signature(api.handle_dropped_schedule)
    params = list(sig_drop_sched.parameters.keys())
    assert params == ["filename", "base64_data", "original_path"]

    # detect_classes takes roster_configs=None
    sig_detect = inspect.signature(api.detect_classes)
    assert "roster_configs" in sig_detect.parameters

    # run_generation takes (type_overrides, date_overrides, class_filter, engine_filter, roster_configs)
    sig_gen = inspect.signature(api.run_generation)
    expected_gen_params = ["type_overrides", "date_overrides", "class_filter", "engine_filter", "roster_configs"]
    for p in expected_gen_params:
        assert p in sig_gen.parameters

def test_dropzone_dom_element_ids_parity():
    """Verify React components define the exact IDs expected by main.py's native OLE bridge."""
    step1_file = os.path.join(TEST_EXEC_DIR, "src", "components", "steps", "Step1Schedule.tsx")
    step2_file = os.path.join(TEST_EXEC_DIR, "src", "components", "steps", "Step2Rosters.tsx")

    with open(step1_file, "r", encoding="utf-8") as f:
        step1_code = f.read()
    assert 'id="scheduleDropzone"' in step1_code, "Step 1 must have id='scheduleDropzone'"

    with open(step2_file, "r", encoding="utf-8") as f:
        step2_code = f.read()
    assert 'id="rostersDropzone"' in step2_code, "Step 2 must have id='rostersDropzone' matching python dom query"

def test_app_tsx_registers_global_window_callbacks():
    """Verify App.tsx registers onScheduleLoaded, onRostersLoaded, and telemetry callbacks."""
    app_tsx = os.path.join(TEST_EXEC_DIR, "src", "App.tsx")
    with open(app_tsx, "r", encoding="utf-8") as f:
        app_code = f.read()

    assert "window.onScheduleLoaded" in app_code, "Must register window.onScheduleLoaded"
    assert "window.onRostersLoaded" in app_code, "Must register window.onRostersLoaded"
    assert "window.onGenerationProgress" in app_code, "Must register window.onGenerationProgress"
    assert "window.onGenerationComplete" in app_code, "Must register window.onGenerationComplete"
    assert "window.onGenerationError" in app_code, "Must register window.onGenerationError"

def test_apple_hig_design_system_tokens_coverage():
    """Verify tokens.css defines all required Apple HIG scales and semantic roles."""
    tokens_file = os.path.join(TEST_EXEC_DIR, "src", "design-system", "tokens.css")
    assert os.path.exists(tokens_file), "design-system/tokens.css must exist"

    with open(tokens_file, "r", encoding="utf-8") as f:
        tokens_css = f.read()

    # Typography
    assert "--hig-font-display" in tokens_css
    assert "--hig-font-title-1" in tokens_css
    assert "--hig-font-body" in tokens_css
    assert "--hig-font-caption" in tokens_css
    assert "--hig-font-footnote" in tokens_css

    # Semantic Colors
    assert "--hig-bg-canvas" in tokens_css
    assert "--hig-bg-surface" in tokens_css
    assert "--hig-color-primary" in tokens_css
    assert "--hig-color-success" in tokens_css
    assert "--hig-color-warning" in tokens_css
    assert "--hig-color-destructive" in tokens_css

    # Spatial scale
    assert "--hig-space-sm" in tokens_css
    assert "--hig-space-md" in tokens_css
    assert "--hig-space-lg" in tokens_css

    # Interaction & Motion
    assert "--hig-ease-spring" in tokens_css
    assert "--hig-press-scale" in tokens_css
    assert "--hig-focus-ring" in tokens_css
