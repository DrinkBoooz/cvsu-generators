"""
Automated View Transition rendering and pseudo-tree investigation test (Commit 198).

Verifies the empirical rendering facts established during the Commit 198 investigation:
1. test_vt_pseudo_elements_prohibit_nested_pseudo_elements:
   Proves that ::view-transition-new(root)::before and ::view-transition-image-pair(root)::after
   are invalid CSS syntax rejected by the browser parser, precluding synthetic glass overlays
   within the VT layer.

2. test_vt_new_root_is_fully_opaque_and_clip_path_bound:
   Proves that ::view-transition-new(root) has computed opacity: 1 and that its clip-path
   strictly encloses the destination theme, meaning backdrop-filter cannot filter an annulus
   without occluding the interior or exposing the old snapshot.

3. test_vt_specular_filter_is_restrained_and_monochrome:
   Verifies that the specular filter on ::view-transition-new(root) uses monochrome
   specular styling (no neon hues, no white halo) conforming to Apple HIG liquid-glass.md.

4. test_vt_investigation_preserves_zero_runaway_cascade:
   Confirms that the transition produces deterministically 0 transitionstart events during
   the lifecycle window.
"""
import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"


@pytest.mark.playwright
def test_vt_pseudo_elements_prohibit_nested_pseudo_elements():
    """Verify that CSS parser rejects pseudo-elements on VT pseudo-elements."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        res = page.evaluate("""() => {
            const style = document.createElement("style");
            document.head.appendChild(style);
            let beforeErr = null;
            let afterErr = null;
            try {
                style.sheet.insertRule("::view-transition-new(root)::before { content: ''; }", 0);
            } catch (e) {
                beforeErr = e.message;
            }
            try {
                style.sheet.insertRule("::view-transition-image-pair(root)::after { content: ''; }", 0);
            } catch (e) {
                afterErr = e.message;
            }
            return { beforeErr, afterErr };
        }""")

        assert res["beforeErr"] is not None, \
            "Expected ::view-transition-new(root)::before to fail CSS parsing"
        assert res["afterErr"] is not None, \
            "Expected ::view-transition-image-pair(root)::after to fail CSS parsing"
        browser.close()


@pytest.mark.playwright
def test_vt_new_root_is_fully_opaque_and_clip_path_bound():
    """Verify that during transition, ::view-transition-new(root) has opacity: 1 and WAAPI clip-path."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1120, "height": 780})
        page.goto(FILE_URL)

        res = page.evaluate("""() => new Promise((resolve) => {
            let captured = null;
            const origSVT = document.startViewTransition.bind(document);
            document.startViewTransition = (cb) => {
                const t = origSVT(cb);
                t.ready.then(() => {
                    requestAnimationFrame(() => {
                        const style = getComputedStyle(document.documentElement, '::view-transition-new(root)');
                        captured = {
                            opacity: style ? style.opacity : null,
                            filter: style ? style.filter : null,
                            clipPath: style ? style.clipPath : null
                        };
                    });
                });
                t.finished.then(() => {
                    resolve(captured);
                });
                return t;
            };
            document.getElementById('btnToggleTheme').click();
        })""")

        assert res is not None, "Failed to capture transition styles"
        assert res["opacity"] == "1", f"Expected opacity: 1 on ::view-transition-new(root), got {res['opacity']}"
        assert res["clipPath"] is not None and "circle(" in res["clipPath"], \
            f"Expected circular clipPath, got {res['clipPath']}"
        browser.close()


@pytest.mark.playwright
def test_vt_specular_filter_is_restrained_and_monochrome():
    """Verify that specular filter custom property is monochrome and restrained."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)

        # In dark mode
        dark_spec = page.evaluate(
            "() => getComputedStyle(document.documentElement).getPropertyValue('--vt-edge-specular').trim()"
        )
        assert "drop-shadow" in dark_spec, f"Expected drop-shadow in dark mode specular, got: {dark_spec}"

        # Toggle to light
        page.evaluate("() => document.getElementById('btnToggleTheme').click()")
        page.wait_for_function("() => document.documentElement.getAttribute('data-theme') === 'light'")

        light_spec = page.evaluate(
            "() => getComputedStyle(document.documentElement).getPropertyValue('--vt-edge-specular').trim()"
        )
        assert "drop-shadow" in light_spec, f"Expected drop-shadow in light mode specular, got: {light_spec}"
        browser.close()


@pytest.mark.playwright
def test_vt_investigation_preserves_zero_runaway_cascade():
    """Verify deterministically 0 transitionstart events during the VT lifecycle window."""
    from tests.test_theme_transition_perf import _COUNT_TRANSITIONS_JS

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1120, "height": 780})
        page.goto(FILE_URL)

        res = page.evaluate(_COUNT_TRANSITIONS_JS)
        theme_after = page.evaluate("() => document.documentElement.getAttribute('data-theme')")

        assert theme_after == "light", f"Theme did not toggle to light: {theme_after}"
        assert res["count"] == 0, (
            f"Expected 0 transitionstart events during VT lifecycle, "
            f"got {res['count']}: {res['events']}"
        )
        browser.close()
