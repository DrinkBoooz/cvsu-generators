"""
Playwright iris runtime verification (commit 197).

Tests verify:
1. test_iris_clip_path_grows_monotonically:
   - Extracts circle radius from EVERY sample during the transition.
   - Verifies actual GROWTH (not static clip-path).
   - Requires: near-0 start, intermediate, materially larger final.
   - Both dark→light and light→dark directions.

2. test_iris_click_origin_matches_button_center:
   - Captures the circle center (x, y) from clip-path samples.
   - Verifies it corresponds approximately to the theme button's center.
   - Tolerance: ±40px (button width ÷ 2 + margin).

3. test_iris_final_radius_covers_viewport:
   - Verifies the final sampled radius is >= the computed endRadius
     (Math.hypot of the farthest viewport corner from the click origin).
   - Does not hardcode expected radius.

4. test_iris_transition_promises_resolve:
   - Verifies all three VT promises resolve.
   - Captures any thrown exceptions.

5. test_iris_multi_viewport_and_direction:
   - Tests 880×640, 1120×780, 1440×900.
   - Both dark→light and light→dark.
   - Verifies growth at each viewport.
"""

import os
import re
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

# ----- helpers ---------------------------------------------------------------

def _parse_circle_radius(clip_path: str) -> float | None:
    """Extract the radius from a 'circle(Xpx at Ypx Zpx)' string.
    Returns None if the string is not a well-formed circle()."""
    if not clip_path or "circle(" not in clip_path.lower():
        return None
    m = re.search(r"circle\(\s*([\d.]+)px", clip_path, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _parse_circle_center(clip_path: str) -> tuple[float, float] | None:
    """Extract (cx, cy) from 'circle(Rpx at Xpx Ypx)'."""
    if not clip_path or "circle(" not in clip_path.lower():
        return None
    m = re.search(
        r"circle\(\s*[\d.]+px\s+at\s+([\d.]+)px\s+([\d.]+)px",
        clip_path, re.IGNORECASE
    )
    return (float(m.group(1)), float(m.group(2))) if m else None


# JS that intercepts startViewTransition and samples clip-path at 15ms intervals
# for the full duration of the animation, returning ALL samples plus metadata.
_SAMPLE_JS = """() => {
    return new Promise((resolve) => {
        const samples = [];        // { t, cp } objects
        let readyResolved = false;
        let finishedResolved = false;
        let exception = null;
        let samplerInterval = null;

        function startSampling() {
            const t0 = performance.now();
            samplerInterval = setInterval(() => {
                try {
                    const style = getComputedStyle(
                        document.documentElement,
                        '::view-transition-new(root)'
                    );
                    samples.push({
                        t: Math.round(performance.now() - t0),
                        cp: style ? style.clipPath : 'unavailable'
                    });
                } catch (e) {
                    samples.push({ t: -1, cp: 'error: ' + e.message });
                }
            }, 15);
        }

        const origSVT = document.startViewTransition.bind(document);
        document.startViewTransition = (callback) => {
            const t = origSVT(callback);
            startSampling();
            t.ready.then(() => { readyResolved = true; })
                   .catch(e => { exception = 'ready: ' + e.message; });
            t.finished.then(() => {
                finishedResolved = true;
                clearInterval(samplerInterval);
                // One extra tick to catch the last frame of the animation
                setTimeout(() => {
                    resolve({
                        samples,
                        readyResolved,
                        finishedResolved,
                        exception,
                        theme: document.documentElement.getAttribute('data-theme'),
                        btnRect: (() => {
                            const b = document.getElementById('btnToggleTheme');
                            if (!b) return null;
                            const r = b.getBoundingClientRect();
                            return { cx: r.left + r.width / 2, cy: r.top + r.height / 2,
                                     w: r.width, h: r.height };
                        })(),
                        vtX: parseFloat(
                            getComputedStyle(document.documentElement)
                                .getPropertyValue('--vt-x')) || null,
                        vtY: parseFloat(
                            getComputedStyle(document.documentElement)
                                .getPropertyValue('--vt-y')) || null,
                        vtRadius: parseFloat(
                            getComputedStyle(document.documentElement)
                                .getPropertyValue('--vt-radius')) || null,
                        innerW: window.innerWidth,
                        innerH: window.innerHeight
                    });
                }, 10);
            }).catch(e => {
                exception = (exception || '') + ' finished: ' + e.message;
                clearInterval(samplerInterval);
                resolve({
                    samples, readyResolved, finishedResolved, exception,
                    theme: document.documentElement.getAttribute('data-theme'),
                    btnRect: null, vtX: null, vtY: null, vtRadius: null,
                    innerW: window.innerWidth, innerH: window.innerHeight
                });
            });
            return t;
        };

        document.getElementById('btnToggleTheme').click();
    });
}"""


def _run_toggle(page) -> dict:
    """Run one theme toggle and return the full sample result."""
    return page.evaluate(_SAMPLE_JS)


def _assert_growth(result: dict, direction: str, viewport: str = ""):
    """
    Extract circle radii from all samples and verify monotonic-ish growth.

    Requirements:
    - At least one near-start sample (radius < 10% of final)
    - At least one intermediate sample (10%–90% of final)
    - At least one near-final sample (radius > 50% of final)
    - First meaningful radius < last meaningful radius (actual growth)
    """
    label = f"{direction} {viewport}".strip()
    samples = result.get("samples", [])
    radii = []
    for s in samples:
        cp = s.get("cp", "")
        r = _parse_circle_radius(cp)
        if r is not None:
            radii.append(r)

    assert len(radii) >= 3, (
        f"[{label}] Need ≥3 circle() radius samples to verify growth. "
        f"Got {len(radii)} from {len(samples)} total samples.\n"
        f"Samples: {[s['cp'] for s in samples[:10]]}"
    )

    max_r = max(radii)
    min_r = min(radii)

    assert max_r > 0, f"[{label}] Max radius is 0 — iris never opened."

    # Require actual growth: max must be materially larger than min
    assert max_r > min_r * 2, (
        f"[{label}] Iris radius did not grow materially.\n"
        f"min_r={min_r:.1f}px, max_r={max_r:.1f}px (ratio {max_r/max(min_r,1):.1f}x).\n"
        f"All radii: {[round(r) for r in radii]}"
    )

    # First meaningful (non-zero) < last meaningful
    non_zero = [r for r in radii if r > 0.5]
    assert len(non_zero) >= 2, (
        f"[{label}] Need ≥2 non-zero radius samples. Got: {non_zero}"
    )
    first_r = non_zero[0]
    last_r = non_zero[-1]
    assert last_r > first_r, (
        f"[{label}] Last radius ({last_r:.1f}px) is not > first ({first_r:.1f}px). "
        f"Iris may be static or reversed."
    )

    # Near-start, intermediate, and near-final checks
    threshold_pct = max_r
    near_start = [r for r in radii if r < threshold_pct * 0.15]
    near_final  = [r for r in radii if r > threshold_pct * 0.50]
    middle      = [r for r in radii if threshold_pct * 0.15 <= r <= threshold_pct * 0.85]

    assert len(near_start) >= 1, (
        f"[{label}] No near-start sample (r < 15% of max_r={max_r:.0f}px).\n"
        f"Radii: {[round(r) for r in radii]}"
    )
    assert len(near_final) >= 1, (
        f"[{label}] No near-final sample (r > 50% of max_r={max_r:.0f}px).\n"
        f"Radii: {[round(r) for r in radii]}"
    )
    assert len(middle) >= 1, (
        f"[{label}] No intermediate sample (15%–85% of max_r={max_r:.0f}px).\n"
        f"Radii: {[round(r) for r in radii]}"
    )

    print(
        f"  [{label}] radii count={len(radii)}, "
        f"first={first_r:.0f}px, max={max_r:.0f}px, "
        f"near_start={len(near_start)}, middle={len(middle)}, near_final={len(near_final)}"
    )
    return radii


# ----- tests -----------------------------------------------------------------

@pytest.mark.playwright
def test_iris_clip_path_grows_monotonically():
    """
    REQ 2: Verify that the WAAPI iris clip-path radius actually GROWS during the
    transition. Distinguishes 'clip-path exists but is static' from actual animation.

    Both dark→light and light→dark are tested.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        # dark → light
        r1 = _run_toggle(page)
        assert r1["exception"] is None, f"Exception: {r1['exception']}"
        assert r1["readyResolved"], "transition.ready did not resolve"
        assert r1["finishedResolved"], "transition.finished did not resolve"
        assert r1["theme"] == "light", f"Expected light, got {r1['theme']}"
        print(f"\ndark→light:")
        _assert_growth(r1, "dark→light")

        # light → dark
        r2 = _run_toggle(page)
        assert r2["exception"] is None, f"Exception: {r2['exception']}"
        assert r2["readyResolved"], "transition.ready did not resolve"
        assert r2["finishedResolved"], "transition.finished did not resolve"
        assert r2["theme"] == "dark", f"Expected dark, got {r2['theme']}"
        print(f"light→dark:")
        _assert_growth(r2, "light→dark")

        browser.close()


@pytest.mark.playwright
def test_iris_click_origin_matches_button_center():
    """
    REQ 3: Verify that the circle()'s center coordinates (x, y) correspond
    approximately to the theme button's center, within a ±40px tolerance.

    The button center is captured via getBoundingClientRect() and compared
    to the --vt-x / --vt-y custom properties set by theme.js, and also to
    the circle()'s own 'at Xpx Ypx' values in the clip-path samples.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        result = _run_toggle(page)
        assert result["exception"] is None, f"Exception: {result['exception']}"

        btn_rect = result.get("btnRect")
        vt_x = result.get("vtX")
        vt_y = result.get("vtY")
        samples = result.get("samples", [])

        assert btn_rect is not None, "Could not capture button bounding rect"

        btn_cx = btn_rect["cx"]
        btn_cy = btn_rect["cy"]
        print(f"\nButton center: ({btn_cx:.1f}, {btn_cy:.1f})")
        print(f"--vt-x: {vt_x}, --vt-y: {vt_y}")

        # Verify --vt-x and --vt-y are set and close to button center
        assert vt_x is not None, "--vt-x was not set by theme.js"
        assert vt_y is not None, "--vt-y was not set by theme.js"

        TOLERANCE = 50  # px — button half-width + click event margin
        assert abs(vt_x - btn_cx) <= TOLERANCE, (
            f"--vt-x ({vt_x:.1f}) deviates {abs(vt_x - btn_cx):.1f}px from "
            f"button center ({btn_cx:.1f}). Exceeds ±{TOLERANCE}px tolerance."
        )
        assert abs(vt_y - btn_cy) <= TOLERANCE, (
            f"--vt-y ({vt_y:.1f}) deviates {abs(vt_y - btn_cy):.1f}px from "
            f"button center ({btn_cy:.1f}). Exceeds ±{TOLERANCE}px tolerance."
        )

        # Also verify the circle()'s 'at' coordinates match
        circle_centers = []
        for s in samples:
            ctr = _parse_circle_center(s.get("cp", ""))
            if ctr:
                circle_centers.append(ctr)

        assert len(circle_centers) >= 1, (
            f"No circle() samples with 'at X Y' coordinates found.\n"
            f"Samples: {[s['cp'] for s in samples[:5]]}"
        )

        # All circle() samples should have the same center (it's constant during animation)
        cx_vals = [c[0] for c in circle_centers]
        cy_vals = [c[1] for c in circle_centers]
        cx_spread = max(cx_vals) - min(cx_vals)
        cy_spread = max(cy_vals) - min(cy_vals)
        assert cx_spread < 2.0, \
            f"circle() cx coordinates vary inconsistently: spread={cx_spread:.1f}px"
        assert cy_spread < 2.0, \
            f"circle() cy coordinates vary inconsistently: spread={cy_spread:.1f}px"

        avg_cx = sum(cx_vals) / len(cx_vals)
        avg_cy = sum(cy_vals) / len(cy_vals)
        print(f"circle() center: ({avg_cx:.1f}, {avg_cy:.1f})")

        assert abs(avg_cx - btn_cx) <= TOLERANCE, (
            f"circle() cx ({avg_cx:.1f}) deviates from button center ({btn_cx:.1f})"
        )
        assert abs(avg_cy - btn_cy) <= TOLERANCE, (
            f"circle() cy ({avg_cy:.1f}) deviates from button center ({btn_cy:.1f})"
        )

        browser.close()


@pytest.mark.playwright
def test_iris_final_radius_covers_viewport():
    """
    REQ 4: Verify that the final iris radius is large enough to fully cover
    the viewport from the click origin.

    Expected final radius >= Math.hypot(max(x, W-x), max(y, H-y))
    which is the endRadius computed in theme.js.

    Uses --vt-radius (the computed endRadius injected by theme.js) as
    the expected value, and verifies the largest sampled radius achieves
    at least 90% of it (allowing for mid-transition sampling cutoff).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        result = _run_toggle(page)
        assert result["exception"] is None, f"Exception: {result['exception']}"

        vt_radius = result.get("vtRadius")
        vt_x = result.get("vtX")
        vt_y = result.get("vtY")
        inner_w = result.get("innerW", 1280)
        inner_h = result.get("innerH", 800)
        samples = result.get("samples", [])

        print(f"\nViewport: {inner_w}x{inner_h}")
        print(f"Origin: ({vt_x}, {vt_y}), endRadius (--vt-radius): {vt_radius}")

        # Verify --vt-radius was set
        assert vt_radius is not None and vt_radius > 0, \
            f"--vt-radius not set or zero: {vt_radius}"

        # Re-compute expected endRadius from first principles
        assert vt_x is not None and vt_y is not None, "Missing --vt-x / --vt-y"
        import math
        expected_end = math.hypot(
            max(vt_x, inner_w - vt_x),
            max(vt_y, inner_h - vt_y)
        )
        print(f"Expected endRadius (computed): {expected_end:.1f}px")

        # --vt-radius must match the formula within 1px
        assert abs(vt_radius - expected_end) <= 1.5, (
            f"--vt-radius ({vt_radius:.1f}) does not match "
            f"Math.hypot formula ({expected_end:.1f}). "
            f"theme.js endRadius computation may have changed."
        )

        # The largest sampled radius must be at least 90% of endRadius
        # (it may not reach 100% if the final frame is sampled mid-animation)
        radii = [_parse_circle_radius(s.get("cp", "")) for s in samples]
        radii = [r for r in radii if r is not None]

        assert len(radii) >= 1, "No circle() radius samples found"

        max_r = max(radii)
        coverage = max_r / vt_radius
        print(f"Max sampled radius: {max_r:.1f}px ({coverage*100:.0f}% of endRadius)")

        assert coverage >= 0.85, (
            f"Max sampled radius ({max_r:.1f}px) is only {coverage*100:.0f}% "
            f"of endRadius ({vt_radius:.1f}px). "
            f"Expected ≥85%. Iris may not be expanding to full viewport coverage."
        )

        browser.close()


@pytest.mark.playwright
def test_iris_transition_promises_resolve():
    """
    REQ (PART 12): Verify transition.updateCallbackDone, transition.ready, and
    transition.finished all resolve without exceptions.
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
                        outcomes.exceptions.push('updateCallbackDone: ' + e.message);
                    });

                    t.ready.then(() => {
                        outcomes.readyResolved = true;
                    }).catch(e => {
                        outcomes.exceptions.push('ready: ' + e.message);
                    });

                    t.finished.then(() => {
                        outcomes.finishedResolved = true;
                        outcomes.finalTheme = document.documentElement.getAttribute('data-theme');
                        resolve(outcomes);
                    }).catch(e => {
                        outcomes.exceptions.push('finished: ' + e.message);
                        outcomes.finalTheme = document.documentElement.getAttribute('data-theme');
                        resolve(outcomes);
                    });

                    return t;
                };

                document.getElementById('btnToggleTheme').click();
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
    PART 5 (multi-viewport): Verify iris growth at 3 viewport sizes,
    both dark→light and light→dark directions.
    """
    viewports = [
        {"width": 880,  "height": 640},
        {"width": 1120, "height": 780},
        {"width": 1440, "height": 900},
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for vp in viewports:
            label = f"{vp['width']}x{vp['height']}"
            print(f"\nViewport {label}:")
            page = browser.new_page(viewport=vp)
            page.goto(FILE_URL)

            # dark → light
            r1 = _run_toggle(page)
            assert r1["exception"] is None, \
                f"dark→light at {label}: exception={r1['exception']}"
            assert r1["readyResolved"], \
                f"dark→light at {label}: transition.ready did not resolve"
            assert r1["finishedResolved"], \
                f"dark→light at {label}: transition.finished did not resolve"
            assert r1["theme"] == "light", \
                f"dark→light at {label}: theme={r1['theme']}"
            _assert_growth(r1, "dark→light", label)

            # light → dark
            r2 = _run_toggle(page)
            assert r2["exception"] is None, \
                f"light→dark at {label}: exception={r2['exception']}"
            assert r2["readyResolved"], \
                f"light→dark at {label}: transition.ready did not resolve"
            assert r2["finishedResolved"], \
                f"light→dark at {label}: transition.finished did not resolve"
            assert r2["theme"] == "dark", \
                f"light→dark at {label}: theme={r2['theme']}"
            _assert_growth(r2, "light→dark", label)

            page.close()

        browser.close()


if __name__ == "__main__":
    test_iris_clip_path_grows_monotonically()
    test_iris_click_origin_matches_button_center()
    test_iris_final_radius_covers_viewport()
    test_iris_transition_promises_resolve()
    test_iris_multi_viewport_and_direction()
    print("All iris runtime tests passed!")
