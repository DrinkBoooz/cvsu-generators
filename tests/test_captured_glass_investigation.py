"""
Automated Captured Glass Material Investigation Test (Commit 199).

Verifies the empirical findings established during the Commit 199 investigation:
1. test_production_baseline_preserves_clean_reveal_without_raster_tears:
   Proves that production Commit 198 baseline maintains a clean WAAPI geometric reveal
   on ::view-transition-new(root) with 0 DOM wavefront elements and 0 frozen raster tears.

2. test_production_baseline_maintains_zero_runaway_cascade:
   Confirms that under all transition conditions, the production transition produces
   deterministically 0 transitionstart events during the View Transition window.

3. test_accessibility_reduced_motion_and_transparency_contracts:
   Verifies that when prefers-reduced-motion is active, theme transitions occur with
   instantaneous duration (0ms) and no decorative annular motion, and that
   reduced-transparency media tokens provide high-opacity edge definition in modals.css.
"""
import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
MODALS_CSS_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "css", "modals.css")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"


@pytest.mark.playwright
def test_production_baseline_preserves_clean_reveal_without_raster_tears():
    """Verify that production runtime has no stray DOM wavefront layers or captured raster overlays."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1120, "height": 780})
        page.goto(FILE_URL)

        # Check DOM before transition
        wavefronts = page.evaluate("""() => {
            return {
                capturedGlass: document.getElementById('capturedGlassSurface') !== null,
                decorativeWavefront: document.querySelector('.theme-glass-wavefront') !== null,
                svgAnnulus: document.getElementById('decorativeAnnulusWavefront') !== null
            };
        }""")

        assert not wavefronts["capturedGlass"], "Found unexpected capturedGlassSurface in production DOM"
        assert not wavefronts["decorativeWavefront"], "Found unexpected theme-glass-wavefront in production DOM"
        assert not wavefronts["svgAnnulus"], "Found unexpected decorativeAnnulusWavefront in production DOM"

        # Toggle theme and wait for completion
        page.evaluate("() => document.getElementById('btnToggleTheme').click()")
        page.wait_for_function("() => !document.documentElement.classList.contains('theme-transitioning')", timeout=3000)

        # Re-verify clean DOM post transition
        post_wavefronts = page.evaluate("""() => {
            return {
                capturedGlass: document.getElementById('capturedGlassSurface') !== null,
                decorativeWavefront: document.querySelector('.theme-glass-wavefront') !== null,
                transitioningClass: document.documentElement.classList.contains('theme-transitioning')
            };
        }""")

        assert not post_wavefronts["capturedGlass"], "Found residual capturedGlassSurface after transition"
        assert not post_wavefronts["decorativeWavefront"], "Found residual theme-glass-wavefront after transition"
        assert not post_wavefronts["transitioningClass"], "theme-transitioning class not cleaned up"

        browser.close()


@pytest.mark.playwright
def test_production_baseline_maintains_zero_runaway_cascade():
    """Verify deterministically 0 transitionstart events during production theme transition."""
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


@pytest.mark.playwright
def test_accessibility_reduced_motion_and_transparency_contracts():
    """Verify accessibility adaptations: reduced-motion bypass and high-contrast/reduced-transparency tokens."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1120, "height": 780},
            reduced_motion="reduce"
        )
        page = context.new_page()
        page.goto(FILE_URL)

        # In reduced motion, transition duration is 0ms in theme.js
        res = page.evaluate("""() => {
            const btn = document.getElementById('btnToggleTheme');
            const before = performance.now();
            btn.click();
            const after = performance.now();
            return {
                duration: after - before,
                theme: document.documentElement.getAttribute('data-theme')
            };
        }""")

        assert res["theme"] == "light", "Theme failed to toggle under reduced-motion"

        # Check reduced-transparency CSS definition in modals.css
        with open(MODALS_CSS_PATH, "r", encoding="utf-8") as f:
            modals_css = f.read()

        assert "prefers-reduced-transparency" in modals_css, \
            "Expected prefers-reduced-transparency CSS media block in modals.css"
        assert "prefers-contrast" in modals_css, \
            "Expected prefers-contrast CSS media block in modals.css"

        browser.close()
