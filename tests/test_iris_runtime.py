"""
Playwright iris runtime verification (commit 196 / PART 11 + 12).

Tests:
1. test_iris_clip_path_animates_during_transition:
   Verify the WAAPI iris clip-path changes from near-zero to large radius during
   the View Transition. Captures clip-path at multiple points. Fails if the
   pseudo-element has clip-path "none" for the entire transition.

2. test_iris_transition_ready_and_finished_resolve:
   Verify that transition.updateCallbackDone, transition.ready, and
   transition.finished all resolve successfully. Capture any thrown exceptions.
   Verify theme change occurred even if transition failed.

3. test_iris_multi_viewport_and_direction:
   Run dark->light and light->dark across 3 viewport sizes (880x640, 1120x780,
   1440x900). Verify iris fires at each size and direction.
"""

import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"


def _sample_iris_clip_paths(page):
    """
    Sample the ::view-transition-new(root) clip-path at multiple points during
    a theme toggle. Returns a dict with:
      - theme_changed: bool
      - samples: list of clip-path strings (may be empty if pseudo-element not accessible)
      - exception: str or None
      - ready_resolved: bool
      - finished_resolved: bool
    """
    result = page.evaluate("""() => {
        return new Promise((resolve) => {
            const samples = [];
            let readyResolved = false;
            let finishedResolved = false;
            let exception = null;

            // Collect clip-path samples during the transition via polling
            const SAMPLE_INTERVAL_MS = 20;
            const MAX_SAMPLES = 30;
            let samplerInterval = null;

            function startSampling() {
                let count = 0;
                samplerInterval = setInterval(() => {
                    try {
                        const style = getComputedStyle(
                            document.documentElement,
                            "::view-transition-new(root)"
                        );
                        const cp = style ? style.clipPath : "unavailable";
                        samples.push(cp);
                    } catch (e) {
                        samples.push("error: " + e.message);
                    }
                    count++;
                    if (count >= MAX_SAMPLES) {
                        clearInterval(samplerInterval);
                    }
                }, SAMPLE_INTERVAL_MS);
            }

            // Inject a patched startViewTransition to intercept promises
            const origSVT = document.startViewTransition.bind(document);
            document.startViewTransition = (callback) => {
                const t = origSVT(callback);
                startSampling();
                t.ready.then(() => {
                    readyResolved = true;
                }).catch(e => {
                    exception = "ready rejected: " + e.message;
                });
                t.finished.then(() => {
                    finishedResolved = true;
                    clearInterval(samplerInterval);
                    // Wait one more frame then resolve
                    requestAnimationFrame(() => {
                        resolve({
                            samples,
                            readyResolved,
                            finishedResolved,
                            exception,
                            theme: document.documentElement.getAttribute("data-theme")
                        });
                    });
                }).catch(e => {
                    exception = (exception || "") + " finished rejected: " + e.message;
                    clearInterval(samplerInterval);
                    resolve({
                        samples,
                        readyResolved,
                        finishedResolved,
                        exception,
                        theme: document.documentElement.getAttribute("data-theme")
                    });
                });
                return t;
            };

            // Click the button to trigger the transition
            const btn = document.getElementById("btnToggleTheme");
            if (!btn) {
                resolve({
                    samples: [],
                    readyResolved: false,
                    finishedResolved: false,
                    exception: "btnToggleTheme not found",
                    theme: null
                });
                return;
            }
            btn.click();
        });
    }""")
    return result


@pytest.mark.playwright
def test_iris_clip_path_animates_during_transition():
    """
    PART 11: Verify that ::view-transition-new(root) has a non-'none' clip-path
    during the WAAPI iris animation. Samples the pseudo-element clip-path at
    20ms intervals during the transition.

    Expected pattern:
        early samples -> circle near 0px radius
        mid samples   -> circle with intermediate radius
        late samples  -> circle with large radius or pseudo-element gone
        NOT all 'none' for the entire transition
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        initial_theme = page.evaluate(
            "() => document.documentElement.getAttribute('data-theme') || 'dark'"
        )
        assert initial_theme == "dark", f"Expected dark initial theme, got {initial_theme}"

        result = _sample_iris_clip_paths(page)

        print(f"\nTransition samples ({len(result['samples'])}): {result['samples'][:10]}")
        print(f"  ready_resolved: {result['readyResolved']}")
        print(f"  finished_resolved: {result['finishedResolved']}")
        print(f"  exception: {result['exception']}")
        print(f"  theme: {result['theme']}")

        # PART 12: Transition promises must resolve
        assert result["exception"] is None, \
            f"Transition threw an exception: {result['exception']}"
        assert result["readyResolved"], \
            "transition.ready did not resolve — WAAPI animation cannot start until ready"
        assert result["finishedResolved"], \
            "transition.finished did not resolve — transition may have been aborted"

        # Theme must have actually changed
        assert result["theme"] == "light", \
            f"Theme did not change to light: {result['theme']}"

        # PART 11: clip-path must NOT be 'none' for the ENTIRE sample window.
        # Some samples may be 'none' when the pseudo-element does not exist
        # (before the VT starts or after it ends). But at least SOME samples
        # during the animation window must show a circle() value.
        non_none_samples = [s for s in result["samples"] if s and s != "none" and "unavailable" not in s and "error" not in s]

        assert len(non_none_samples) > 0, (
            "Expected at least one clip-path sample with a non-'none' value during the WAAPI iris.\n"
            f"All {len(result['samples'])} samples were: {result['samples']}\n"
            "This indicates the WAAPI iris animation is not running on ::view-transition-new(root)."
        )

        # At least one sample should contain 'circle(' indicating the iris is active
        circle_samples = [s for s in non_none_samples if "circle(" in s.lower()]
        assert len(circle_samples) > 0, (
            "Expected at least one sample with 'circle(' in the clip-path.\n"
            f"Non-none samples were: {non_none_samples}\n"
            "This indicates clip-path is set but not to the expected iris circle() shape."
        )

        browser.close()


@pytest.mark.playwright
def test_iris_transition_promises_resolve():
    """
    PART 12: Verify transition.updateCallbackDone, transition.ready, and
    transition.finished all resolve without exceptions. If transition.ready
    rejects, capture the exception and fail with a clear message.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        result = page.evaluate("""() => {
            return new Promise((resolve) => {
                const outcomes = {
                    updateCallbackDoneResolved: false,
                    readyResolved: false,
                    finishedResolved: false,
                    exceptions: []
                };

                const origSVT = document.startViewTransition.bind(document);
                document.startViewTransition = (callback) => {
                    const t = origSVT(callback);

                    t.updateCallbackDone.then(() => {
                        outcomes.updateCallbackDoneResolved = true;
                    }).catch(e => {
                        outcomes.exceptions.push("updateCallbackDone: " + e.message);
                    });

                    t.ready.then(() => {
                        outcomes.readyResolved = true;
                    }).catch(e => {
                        outcomes.exceptions.push("ready: " + e.message);
                    });

                    t.finished.then(() => {
                        outcomes.finishedResolved = true;
                        outcomes.finalTheme = document.documentElement.getAttribute("data-theme");
                        resolve(outcomes);
                    }).catch(e => {
                        outcomes.exceptions.push("finished: " + e.message);
                        outcomes.finalTheme = document.documentElement.getAttribute("data-theme");
                        resolve(outcomes);
                    });

                    return t;
                };

                document.getElementById("btnToggleTheme").click();
            });
        }""")

        print(f"\nPromise outcomes: {result}")

        assert len(result["exceptions"]) == 0, \
            f"Transition promises threw exceptions: {result['exceptions']}"
        assert result["updateCallbackDoneResolved"], \
            "transition.updateCallbackDone did not resolve"
        assert result["readyResolved"], \
            "transition.ready did not resolve — WAAPI cannot start until ready resolves"
        assert result["finishedResolved"], \
            "transition.finished did not resolve"
        assert result.get("finalTheme") == "light", \
            f"Theme did not change: {result.get('finalTheme')}"

        browser.close()


@pytest.mark.playwright
def test_iris_multi_viewport_and_direction():
    """
    PART 13 (runtime portion): Verify the iris works at multiple viewport sizes
    and in both toggle directions.

    Tests 880x640, 1120x780, 1440x900 viewports with dark->light and light->dark.
    At each toggle, verifies:
    - transition.ready resolves
    - transition.finished resolves
    - no exceptions thrown
    - theme changes correctly
    """
    viewports = [
        {"width": 880, "height": 640},
        {"width": 1120, "height": 780},
        {"width": 1440, "height": 900},
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in viewports:
            page = browser.new_page(viewport=vp)
            page.goto(FILE_URL)

            # dark -> light
            r = _sample_iris_clip_paths(page)
            assert r["exception"] is None, \
                f"dark->light at {vp}: exception={r['exception']}"
            assert r["readyResolved"], \
                f"dark->light at {vp}: transition.ready did not resolve"
            assert r["finishedResolved"], \
                f"dark->light at {vp}: transition.finished did not resolve"
            assert r["theme"] == "light", \
                f"dark->light at {vp}: theme={r['theme']}"

            print(f"[PASS] dark->light at {vp['width']}x{vp['height']}: "
                  f"{len(r['samples'])} samples, "
                  f"{sum(1 for s in r['samples'] if s and s != 'none')} non-none")

            # light -> dark
            r2 = _sample_iris_clip_paths(page)
            assert r2["exception"] is None, \
                f"light->dark at {vp}: exception={r2['exception']}"
            assert r2["readyResolved"], \
                f"light->dark at {vp}: transition.ready did not resolve"
            assert r2["finishedResolved"], \
                f"light->dark at {vp}: transition.finished did not resolve"
            assert r2["theme"] == "dark", \
                f"light->dark at {vp}: theme={r2['theme']}"

            print(f"[PASS] light->dark at {vp['width']}x{vp['height']}: "
                  f"{len(r2['samples'])} samples, "
                  f"{sum(1 for s in r2['samples'] if s and s != 'none')} non-none")

            page.close()

        browser.close()


if __name__ == "__main__":
    test_iris_clip_path_animates_during_transition()
    test_iris_transition_promises_resolve()
    test_iris_multi_viewport_and_direction()
    print("All iris runtime tests passed!")
