"""
Theme transition performance test (commit 197).

Verifies that the theme toggle does NOT produce runaway DOM transition cascade events.

Architecture context:
- Pre-fix: 700+ transitionstart events from CSS 'transition: all'
- Commit 190+: .theme-transitioning guard suppresses all CSS transitions
- Commit 196: WAAPI-owned iris, double-rAF cleanup
- Commit 197: spin-morph converted to @keyframes (no transitionstart events)

Measurement contract:
  The counting window is bounded by the ACTUAL VT lifecycle:
  - Start: button click (when theme-transitioning class is added)
  - End:   transition.finished + double-rAF (when theme-transitioning class is removed)

  This avoids the earlier race: the old test waited 250ms after data-theme changed.
  data-theme changes synchronously in the VT callback at t=0, so the 250ms window
  captured events that occurred AFTER the double-rAF cleanup fired (~33ms).

  With lifecycle-bounded instrumentation, the count MUST be 0.
"""
import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

# JS snippet that intercepts startViewTransition and counts transitionstart events
# only within the exact VT lifecycle window (click → transition.finished + rAF).
# Uses a CustomEvent 'vt-cleanup-done' dispatched after the double-rAF fires.
_COUNT_TRANSITIONS_JS = """
() => new Promise((resolve) => {
    const transitions = [];
    const onTransitionStart = (e) => {
        transitions.push({ tag: e.target.tagName, prop: e.propertyName });
    };

    // Listen for the cleanup sentinel that theme.js dispatches after double-rAF.
    // If theme.js does not dispatch it, we fall back to transition.finished + rAF.
    let cleanupListenerActive = true;
    const onCleanupDone = () => {
        if (!cleanupListenerActive) return;
        cleanupListenerActive = false;
        window.removeEventListener('transitionstart', onTransitionStart, true);
        window.removeEventListener('vt-cleanup-done', onCleanupDone, true);
        resolve({
            count: transitions.length,
            events: transitions,
            method: 'sentinel'
        });
    };
    window.addEventListener('vt-cleanup-done', onCleanupDone, { capture: true, once: true });

    // Fallback: intercept the VT directly and count until finished+rAF.
    const origSVT = document.startViewTransition.bind(document);
    document.startViewTransition = (callback) => {
        const t = origSVT(callback);
        t.finished.then(() => {
            // Mirror the double-rAF in theme.js
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    if (!cleanupListenerActive) return; // sentinel already fired
                    cleanupListenerActive = false;
                    window.removeEventListener('transitionstart', onTransitionStart, true);
                    resolve({
                        count: transitions.length,
                        events: transitions,
                        method: 'finished+rAF'
                    });
                });
            });
        }).catch(() => {
            cleanupListenerActive = false;
            window.removeEventListener('transitionstart', onTransitionStart, true);
            resolve({ count: transitions.length, events: transitions, method: 'error' });
        });
        return t;
    };

    // Start counting from right before the click (when theme-transitioning is added)
    window.addEventListener('transitionstart', onTransitionStart, true);
    const start = performance.now();
    document.getElementById('btnToggleTheme').click();
    // Store start time for duration reporting
    window.__vt_perf_start = start;
})
"""


def test_theme_transition_zero_runaway_events():
    """Verify that toggling themes produces ZERO runaway DOM transition cascade events.

    The measurement window is bounded by the actual VT lifecycle:
      [button click] → [transition.finished + double-rAF]

    This is the exact window during which .theme-transitioning is active.
    Any transitionstart event in this window is a cascade from an unguarded element.

    Expected: 0 events.
    Pre-fix baseline: 700+ events.

    With commit 197 (spin-morph converted to @keyframes), the icon animation
    does not fire transitionstart at all. The WAAPI iris does not fire
    transitionstart. Result: 0 events, deterministically.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        # Confirm initial state
        initial_theme = page.evaluate(
            "() => document.documentElement.getAttribute('data-theme') || 'dark'"
        )
        assert initial_theme == "dark", f"Expected dark, got {initial_theme}"

        # --- dark → light ---
        res_to_light = page.evaluate(_COUNT_TRANSITIONS_JS)
        dur_to_light = page.evaluate(
            "() => performance.now() - (window.__vt_perf_start || performance.now())"
        )

        theme_after_light = page.evaluate(
            "() => document.documentElement.getAttribute('data-theme')"
        )
        print(
            f"\nDark -> Light: count={res_to_light['count']}, "
            f"method={res_to_light['method']}, "
            f"events={res_to_light['events']}"
        )

        assert theme_after_light == "light", \
            f"Theme did not change to light: {theme_after_light}"
        assert res_to_light["count"] == 0, (
            f"Expected 0 transitionstart events in the VT lifecycle window, "
            f"got {res_to_light['count']}.\n"
            f"Events: {res_to_light['events']}\n"
            f"Method: {res_to_light['method']}\n"
            "This indicates an unguarded CSS transition firing during theme-transitioning."
        )

        # Verify button label updated
        btn_label = page.locator("#themeLabel").inner_text()
        assert btn_label == "Dark", \
            f"Expected 'Dark' button label in light mode, got {btn_label!r}"

        # --- light → dark ---
        res_to_dark = page.evaluate(_COUNT_TRANSITIONS_JS)

        theme_after_dark = page.evaluate(
            "() => document.documentElement.getAttribute('data-theme')"
        )
        print(
            f"Light -> Dark: count={res_to_dark['count']}, "
            f"method={res_to_dark['method']}, "
            f"events={res_to_dark['events']}"
        )

        assert theme_after_dark == "dark", \
            f"Theme did not change to dark: {theme_after_dark}"
        assert res_to_dark["count"] == 0, (
            f"Expected 0 transitionstart events in the VT lifecycle window, "
            f"got {res_to_dark['count']}.\n"
            f"Events: {res_to_dark['events']}\n"
            f"Method: {res_to_dark['method']}\n"
            "This indicates an unguarded CSS transition firing during theme-transitioning."
        )

        # Verify final button label
        final_label = page.locator("#themeLabel").inner_text()
        assert final_label == "Light", \
            f"Expected 'Light' button label in dark mode, got {final_label!r}"

        browser.close()


def test_theme_transition_zero_runaway_events_repeated():
    """Verify non-flakiness across multiple consecutive toggles (commit 197 Req 16).

    Performs 5 consecutive theme toggles back-and-forth and asserts count == 0
    on every single toggle, confirming determinism and zero flakiness.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        for iteration in range(1, 6):
            expected_next = "light" if iteration % 2 == 1 else "dark"
            res = page.evaluate(_COUNT_TRANSITIONS_JS)
            theme_after = page.evaluate(
                "() => document.documentElement.getAttribute('data-theme')"
            )
            print(f"  Iteration {iteration} -> {expected_next}: count={res['count']}")
            assert theme_after == expected_next, (
                f"Iteration {iteration}: expected theme {expected_next}, got {theme_after}"
            )
            assert res["count"] == 0, (
                f"Iteration {iteration}: expected 0 transitionstart events, "
                f"got {res['count']} (flakiness detected!)."
            )

        browser.close()


if __name__ == "__main__":
    test_theme_transition_zero_runaway_events()
    test_theme_transition_zero_runaway_events_repeated()
    print("All performance tests passed successfully!")
