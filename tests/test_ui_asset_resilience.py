"""
UI Asset Resilience and Packaging Test Suite.
Validates the three-layer asset pipeline:
  Layer 1: Source asset integrity on disk
  Layer 2: PyInstaller packaging definitions (spec and build.bat)
  Layer 3: Browser/WebView runtime resilience against missing stylesheets
           and delayed script execution under file:/// transport.
"""

import os
import re
from pathlib import Path
import pytest

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
EXECUTABLE_DIR = WORKSPACE_DIR / "executable_test"
UI_HTML_PATH = EXECUTABLE_DIR / "ui.html"
CSS_DIR = EXECUTABLE_DIR / "css"
JS_DIR = EXECUTABLE_DIR / "js"
SPEC_PATH = EXECUTABLE_DIR / "CvSU Gen.spec"
BUILD_BAT_PATH = EXECUTABLE_DIR / "build.bat"


# ==============================================================================
# Layer 1: Source Asset Integrity
# ==============================================================================

def test_layer1_source_asset_integrity():
    """Verify all CSS and JS assets referenced in ui.html exist on disk with non-zero size."""
    assert UI_HTML_PATH.exists(), f"ui.html missing at {UI_HTML_PATH}"
    html_content = UI_HTML_PATH.read_text(encoding="utf-8")

    # Extract all CSS stylesheet hrefs
    css_hrefs = re.findall(r'<link\s+[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', html_content)
    assert len(css_hrefs) >= 7, f"Expected at least 7 stylesheets, found {len(css_hrefs)}: {css_hrefs}"

    for href in css_hrefs:
        # Strip query strings if any
        clean_href = href.split("?")[0]
        css_file = EXECUTABLE_DIR / clean_href
        assert css_file.exists(), f"Stylesheet referenced in ui.html not found: {css_file}"
        assert css_file.stat().st_size > 0, f"Stylesheet is empty: {css_file}"

    # Extract all JS script srcs
    js_srcs = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', html_content)
    assert len(js_srcs) >= 10, f"Expected at least 10 scripts, found {len(js_srcs)}: {js_srcs}"

    for src in js_srcs:
        clean_src = src.split("?")[0]
        js_file = EXECUTABLE_DIR / clean_src
        assert js_file.exists(), f"Script referenced in ui.html not found: {js_file}"
        assert js_file.stat().st_size > 0, f"Script is empty: {js_file}"


def test_layer1_css_architectural_boundaries():
    """Verify .d-none failsafe locations, stepper/dock relocation to components.css, and drawer isolation."""
    html_content = UI_HTML_PATH.read_text(encoding="utf-8")

    # Phase 5: Critical visibility inline failsafe in ui.html <head>
    assert re.search(r'<style[^>]*>\s*\.d-none\s*\{\s*display:\s*none\s*!important;\s*\}\s*</style>', html_content), \
        "Minimal .d-none inline failsafe must be present in ui.html <head>"

    # Phase 4: .d-none and utilities in base.css
    base_css = (CSS_DIR / "base.css").read_text(encoding="utf-8")
    assert ".d-none" in base_css, ".d-none must be defined in base.css"
    assert "display: none !important;" in base_css

    # Phase 4: defensive .d-none fallback retained in drawers.css
    drawers_css = (CSS_DIR / "drawers.css").read_text(encoding="utf-8")
    assert ".d-none" in drawers_css, "Defensive .d-none fallback must be retained in drawers.css"

    # Stepper and Dock must be in components.css
    components_css = (CSS_DIR / "components.css").read_text(encoding="utf-8")
    assert ".stepper-bar" in components_css, ".stepper-bar must be defined in components.css"
    assert ".bottom-action-bar" in components_css, ".bottom-action-bar must be defined in components.css"

    # Stepper and Dock must NOT be in drawers.css
    assert ".stepper-bar" not in drawers_css, ".stepper-bar must NOT be in drawers.css"
    assert ".bottom-action-bar" not in drawers_css, ".bottom-action-bar must NOT be in drawers.css"


def test_layer1_js_lifecycle_bootstrap_sentinels():
    """Verify app.js defines readyState-aware bootstrapApp with observability sentinels."""
    app_js = (JS_DIR / "app.js").read_text(encoding="utf-8")
    assert "function bootstrapApp()" in app_js, "app.js must define bootstrapApp()"
    assert "window.__app_initialized__ = true;" in app_js, "app.js must set window.__app_initialized__"
    assert "window.__app_bootstrap_runs" in app_js, "app.js must increment window.__app_bootstrap_runs"
    assert "document.readyState" in app_js, "app.js must check document.readyState"
    assert "pywebviewready" in app_js, "app.js must preserve pywebviewready listener"


# ==============================================================================
# Layer 2: PyInstaller Packaging Integrity
# ==============================================================================

def test_layer2_pyinstaller_packaging_integrity():
    """Verify PyInstaller spec and build.bat bundle css/ and js/ into the distribution package."""
    assert SPEC_PATH.exists(), f"Spec file missing: {SPEC_PATH}"
    spec_content = SPEC_PATH.read_text(encoding="utf-8")

    # Verify datas tuple in spec
    assert "('css', 'css')" in spec_content, "CvSU Gen.spec must bundle ('css', 'css')"
    assert "('js', 'js')" in spec_content, "CvSU Gen.spec must bundle ('js', 'js')"
    assert "('ui.html', '.')" in spec_content, "CvSU Gen.spec must bundle ('ui.html', '.')"

    assert BUILD_BAT_PATH.exists(), f"build.bat missing: {BUILD_BAT_PATH}"
    build_content = BUILD_BAT_PATH.read_text(encoding="utf-8")
    assert '--add-data "css;css/"' in build_content or '--add-data "css;css"' in build_content, \
        "build.bat must package css directory"
    assert '--add-data "js;js/"' in build_content or '--add-data "js;js"' in build_content, \
        "build.bat must package js directory"


# ==============================================================================
# Layer 3: Browser/WebView Runtime Resilience (Playwright)
# ==============================================================================

def test_layer3_drawers_css_suppression_resilience():
    """
    Simulate complete failure/suppression of drawers.css.
    Assert that .d-none hidden elements (banners, results, modals) remain hidden
    and stepper/dock retain functional layout from components.css.
    """
    from playwright.sync_api import sync_playwright

    file_uri = UI_HTML_PATH.as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Intercept and abort drawers.css
        drawers_aborted = []
        def handle_route(route):
            if "drawers.css" in route.request.url:
                drawers_aborted.append(route.request.url)
                route.abort("failed")
            else:
                route.continue_()

        page.route("**/*", handle_route)
        page.goto(file_uri)
        page.wait_for_load_state("domcontentloaded")

        assert len(drawers_aborted) > 0, "drawers.css must have been intercepted and aborted"

        # 1. Critical visibility check: .d-none elements must remain hidden (display: none)
        instructor_display = page.evaluate("() => window.getComputedStyle(document.getElementById('instructorBanner')).display")
        classes_display = page.evaluate("() => window.getComputedStyle(document.getElementById('classesSection')).display")
        results_display = page.evaluate("() => window.getComputedStyle(document.getElementById('resultsCard')).display")
        modal_display = page.evaluate("() => window.getComputedStyle(document.getElementById('modalParserSettingsBackdrop')).display")

        assert instructor_display == "none", f"instructorBanner bled through with display: {instructor_display}"
        assert classes_display == "none", f"classesSection bled through with display: {classes_display}"
        assert results_display == "none", f"resultsCard bled through with display: {results_display}"
        assert modal_display == "none", f"modalParserSettingsBackdrop bled through with display: {modal_display}"

        # 2. Stepper and Dock layout preservation via components.css
        stepper_track_display = page.evaluate("() => window.getComputedStyle(document.querySelector('.stepper-track')).display")
        dock_pos = page.evaluate("() => window.getComputedStyle(document.querySelector('.bottom-action-bar')).position")

        assert stepper_track_display == "flex", f"stepper-track display broke: {stepper_track_display}"
        assert dock_pos == "fixed", f"bottom-action-bar position broke: {dock_pos}"

        browser.close()


def test_layer3_delayed_app_js_bootstrap_resilience():
    """
    Simulate delayed loading of app.js after document.readyState is 'complete'.
    Verify bootstrapApp() executes cleanly via the readyState !== 'loading' branch,
    registering __app_initialized__ and __app_bootstrap_runs sentinels.
    """
    from playwright.sync_api import sync_playwright

    file_uri = UI_HTML_PATH.as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Intercept and block initial app.js
        app_js_aborted = []
        def handle_route(route):
            if "app.js" in route.request.url:
                app_js_aborted.append(route.request.url)
                route.abort("failed")
            else:
                route.continue_()

        page.route("**/*", handle_route)
        page.goto(file_uri)
        page.wait_for_load_state("load")

        assert len(app_js_aborted) > 0, "app.js must have been intercepted and blocked"

        # Verify app is NOT initialized yet
        initial_state = page.evaluate("() => window.__app_initialized__")
        assert initial_state is None or initial_state is False, "App must not be initialized before app.js runs"

        # Unroute and dynamically inject app.js code after page is fully complete
        page.unroute("**/*")
        app_js_code = (JS_DIR / "app.js").read_text(encoding="utf-8")
        ready_state = page.evaluate("() => document.readyState")
        assert ready_state == "complete", f"Expected readyState 'complete', got '{ready_state}'"

        page.evaluate(app_js_code)

        # Verify sentinels
        initialized = page.evaluate("() => window.__app_initialized__")
        runs = page.evaluate("() => window.__app_bootstrap_runs")

        assert initialized is True, "window.__app_initialized__ must be True after late bootstrap"
        assert runs == 1, f"window.__app_bootstrap_runs expected 1, got {runs}"

        browser.close()


def test_layer3_clean_launch_drawer_behavior():
    """
    Verify clean launch behavior:
    - All stylesheets and scripts load normally.
    - Help drawer starts off-canvas / hidden.
    - Hidden banners remain hidden.
    - Sentinel confirms clean initialization.
    """
    from playwright.sync_api import sync_playwright

    file_uri = UI_HTML_PATH.as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(file_uri)
        page.wait_for_load_state("domcontentloaded")

        # Verify sentinels
        initialized = page.evaluate("() => window.__app_initialized__")
        runs = page.evaluate("() => window.__app_bootstrap_runs")
        assert initialized is True
        assert runs == 1

        # Verify help drawer starts hidden
        drawer = page.locator("#helpDrawer")
        assert drawer.count() == 1
        drawer_visibility = page.evaluate("() => window.getComputedStyle(document.getElementById('helpDrawer')).visibility")
        assert drawer_visibility == "hidden", f"Help drawer should have visibility: hidden initially, got {drawer_visibility}"

        # Verify hidden banners remain hidden
        banner_display = page.evaluate("() => window.getComputedStyle(document.getElementById('instructorBanner')).display")
        assert banner_display == "none"

        browser.close()


# ==============================================================================
# Desktop Integration Container Test
# ==============================================================================

@pytest.mark.desktop_integration
def test_desktop_container_live_launch():
    """
    Live PyWebView container verification under file:/// transport.
    Verifies container launches with Path(html_template).resolve().as_uri(),
    window.__app_initialized__ is True, and pywebview API binding works.
    """
    import webview
    from executable_test.main import ScriptAPI

    api = ScriptAPI()
    results = {}

    file_uri = UI_HTML_PATH.as_uri()

    def runner(window, api_inst):
        try:
            results["protocol"] = window.evaluate_js("window.location.protocol")
            results["app_initialized"] = window.evaluate_js("window.__app_initialized__")
            results["app_runs"] = window.evaluate_js("window.__app_bootstrap_runs")
            results["has_pywebview_api"] = window.evaluate_js("typeof window.pywebview === 'object' && typeof window.pywebview.api === 'object'")
            # Test bridge call
            res = window.evaluate_js("window.pywebview.api.get_parser_config()")
            results["bridge_call_success"] = isinstance(res, dict)
        finally:
            window.destroy()

    w = webview.create_window("Resilience Desktop Test", url=file_uri, js_api=api)
    api._window = w
    webview.start(runner, (w, api))

    assert results.get("protocol") == "file:", f"Expected protocol 'file:', got {results.get('protocol')}"
    assert results.get("app_initialized") is True, "window.__app_initialized__ was not True in desktop host"
    assert results.get("app_runs") == 1, f"window.__app_bootstrap_runs was {results.get('app_runs')}"
    assert results.get("has_pywebview_api") is True, "window.pywebview.api missing in desktop host"
    assert results.get("bridge_call_success") is True, "Bridge call get_parser_config() failed in desktop host"
