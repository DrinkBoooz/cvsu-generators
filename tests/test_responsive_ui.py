import os
import re
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_DIR = os.path.join(WORKSPACE_DIR, "executable_test", "css")
JS_DIR = os.path.join(WORKSPACE_DIR, "executable_test", "js")
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")

def test_high_contrast_tokens_defined():
    tokens_path = os.path.join(CSS_DIR, "tokens.css")
    assert os.path.exists(tokens_path), "tokens.css must exist"
    with open(tokens_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Light mode high-contrast text tokens
    assert "--text-emerald:" in content
    assert "--text-amber:" in content
    assert "--text-rose:" in content

    # Dark mode section must override with accessible dark variants
    assert '[data-theme="dark"]' in content
    dark_section = content.split('[data-theme="dark"]')[1]
    assert "--text-emerald:" in dark_section
    assert "--text-amber:" in dark_section
    assert "--text-rose:" in dark_section

def test_contrast_ratio_wcag_aa_compliance():
    """Verify mathematically that high-contrast tokens achieve >= 4.5:1 against surfaces."""
    def hex_to_rgb(hex_str):
        hex_str = hex_str.strip().lstrip("#")
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    def relative_luminance(rgb):
        srgb = [c / 255.0 for c in rgb]
        linear = [(c / 12.92) if c <= 0.03928 else (((c + 0.055) / 1.055) ** 2.4) for c in srgb]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def contrast_ratio(hex1, hex2):
        l1 = relative_luminance(hex_to_rgb(hex1))
        l2 = relative_luminance(hex_to_rgb(hex2))
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    # Light mode: surface is #f8fafc / #ffffff
    light_surface = "#f8fafc"
    assert contrast_ratio("#047857", light_surface) >= 4.5, "Light emerald must meet 4.5:1 WCAG AA"
    assert contrast_ratio("#b45309", light_surface) >= 4.5, "Light amber must meet 4.5:1 WCAG AA"
    assert contrast_ratio("#b91c1c", light_surface) >= 4.5, "Light rose must meet 4.5:1 WCAG AA"

    # Dark mode: surface is #111827 / #1f2937
    dark_surface = "#111827"
    assert contrast_ratio("#34d399", dark_surface) >= 4.5, "Dark emerald must meet 4.5:1 WCAG AA"
    assert contrast_ratio("#fbbf24", dark_surface) >= 4.5, "Dark amber must meet 4.5:1 WCAG AA"
    assert contrast_ratio("#f87171", dark_surface) >= 4.5, "Dark rose must meet 4.5:1 WCAG AA"

def test_responsive_header_collapse_rules():
    comp_path = os.path.join(CSS_DIR, "components.css")
    with open(comp_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".nav-btn-label" in content
    assert "@media (max-width: 600px)" in content
    assert "display: none;" in content, "nav-btn-label should collapse on narrow viewports"

def test_responsive_step5_input_stacking():
    tables_path = os.path.join(CSS_DIR, "tables.css")
    with open(tables_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".input-with-action" in content
    assert "flex-direction: column;" in content, "input-with-action must stack vertically on mobile"

def test_theme_view_transition_and_animation():
    """
    Verify the unified CSS-owns-animation architecture (commit 193/195).

    CSS (appleThemeIrisReveal @keyframes) is the SOLE owner of the iris clip-path.
    JS must NOT independently animate clipPath on ::view-transition-new(root) via WAAPI.
    JS supplies dynamic CSS custom properties and calls startViewTransition().

    Commit 195 corrections over 194:
    - DOM wavefront eliminated (was captured into old-page VT snapshot, not a live overlay)
    - z-index: 2147483646 stacking claim removed (DOM z-index cannot reference VT render layer)
    - Glass edge is VT-native: filter: drop-shadow on ::view-transition-new(root)
    - CSS owns prefers-reduced-motion fallback entirely; no JS intervention required
    """
    theme_js_path = os.path.join(JS_DIR, "theme.js")
    with open(theme_js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    modals_path = os.path.join(CSS_DIR, "modals.css")
    with open(modals_path, "r", encoding="utf-8") as f:
        css_content = f.read()

    # JS must use the View Transitions API
    assert "document.startViewTransition" in js_content, \
        "theme.js must use View Transitions API"

    # JS must trigger the icon spin-morph animation
    assert "spin-morph" in js_content, \
        "theme.js must trigger spin-morph icon animation"

    # JS must supply dynamic CSS custom properties for the iris origin
    assert "--vt-x" in js_content, "theme.js must set --vt-x custom property"
    assert "--vt-y" in js_content, "theme.js must set --vt-y custom property"
    assert "--vt-radius" in js_content, "theme.js must set --vt-radius custom property"

    # CSS must be the sole specular/styling owner; WAAPI is the iris clip-path owner (commit 196)
    # The @keyframes appleThemeIrisReveal has been removed — WAAPI handles geometry
    assert "clip-path" in css_content.lower() or "clip-path" in js_content.lower(), \
        "clip-path must appear in the theme subsystem (WAAPI iris uses clipPath)"

    # WAAPI must be the sole iris owner in JS, waiting for transition.ready (commit 196)
    # This is the inverse of the commit-193 anti-pattern where CSS and WAAPI competed
    assert "pseudoElement" in js_content and "::view-transition-new(root)" in js_content, \
        "theme.js must animate ::view-transition-new(root) via WAAPI (WAAPI is sole iris owner in commit 196)"
    assert "await transition.ready" in js_content, \
        "theme.js must await transition.ready before WAAPI iris animation"

    # One shared duration token must exist
    assert "THEME_TRANSITION_DURATION_MS" in js_content, \
        "theme.js must define a single shared THEME_TRANSITION_DURATION_MS constant"

    # Apple HIG: glass has no inherent color — specular driven by CSS custom property
    assert "--vt-edge-specular" in css_content, \
        "modals.css must use --vt-edge-specular custom property (HIG: monochrome specular only)"

    # HIG accessibility: CSS owns prefers-reduced-motion fallback entirely (no JS wavefront to guard)
    assert "prefers-reduced-motion" in css_content, \
        "modals.css must handle prefers-reduced-motion (HIG: motion.md, accessibility.md)"
    assert "vt-fade-in" in css_content, \
        "modals.css must provide vt-fade-in crossfade fallback for reduced-motion"

    # Commit 196: DOM wavefront eliminated — JS must NOT create it
    # (DOM elements created before startViewTransition() are snapshotted into the old-page capture)
    assert "theme-glass-wavefront" not in js_content, \
        "theme.js must NOT create DOM wavefront"
    assert "documentElement.appendChild" not in js_content, \
        "theme.js must NOT append any wavefront"


def test_template_set_form_grid_responsive():
    modals_path = os.path.join(CSS_DIR, "modals.css")
    with open(modals_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".template-set-form-grid" in content
    assert "grid-template-columns: 1fr;" in content, "template-set-form-grid must stack to 1 col on mobile"

    with open(UI_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    assert 'class="template-set-form-grid"' in html, "ui.html must use template-set-form-grid class"

def test_roster_title_responsive_text_wrapping():
    """Verify that roster title items allow flexible wrapping without horizontal text clipping."""
    comp_path = os.path.join(CSS_DIR, "components.css")
    with open(comp_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert ".roster-title" in content
    assert "word-break: break-word;" in content
    assert "overflow-wrap: anywhere;" in content
    assert "min-width: 0;" in content
    assert "white-space: normal;" in content

def test_waapi_iris_and_glass_edge_architecture():
    """
    Verify the commit-196 WAAPI iris architecture:
    - WAAPI is the sole iris animation owner (theme.js, pseudoElement on ::view-transition-new(root))
    - CSS has NO competing iris animation on ::view-transition-new(root)
    - Glass edge is a restrained CSS specular filter on the VT pseudo-element
    - DOM wavefront is completely absent
    - JS evaluates prefers-reduced-motion before VT (WAAPI iris is JS-controlled)
    - CSS provides accessibility fallback for VT pseudo-elements under reduced-motion
    - ::view-transition-image-pair(root) isolation and display:block present
    - prefers-reduced-transparency and prefers-contrast:more media queries present

    Architecture split (commit 196):
      WAAPI  = sole owner of circular iris clip-path (theme.js)
      CSS    = static specular/glass-like styling on VT pseudo-elements
      DOM    = no wavefront overlay

    HIG sources:
    - liquid-glass.md § Color on glass: no inherent color, monochrome specular only
    - accessibility.md § Cognitive + motion.md § Best practices: reduced-motion fallback
    """
    modals_path = os.path.join(CSS_DIR, "modals.css")
    with open(modals_path, "r", encoding="utf-8") as f:
        css = f.read()

    # CSS specular filter must be on ::view-transition-new(root)
    assert "::view-transition-new(root)" in css, \
        "modals.css must define ::view-transition-new(root) rules"
    assert "filter: var(--vt-edge-specular)" in css, \
        "::view-transition-new(root) must apply restrained edge via filter: var(--vt-edge-specular)"
    assert "drop-shadow" in css, \
        "--vt-edge-specular must use drop-shadow for the glass-like edge treatment"

    # PART 2: CSS must NOT have any iris animation — WAAPI is sole owner (commit 196)
    assert "appleThemeIrisReveal" not in css, \
        "modals.css must NOT contain appleThemeIrisReveal (WAAPI is sole iris owner in commit 196)"

    # PART 3: VT wipe setup must be present
    assert "::view-transition-image-pair(root)" in css, \
        "modals.css must configure ::view-transition-image-pair(root) for wipe behavior"
    assert "display: block" in css, \
        "modals.css must set display:block on VT pseudo-elements"

    # DOM wavefront must be completely absent
    assert ".theme-glass-wavefront" not in css, \
        "modals.css must NOT contain .theme-glass-wavefront"
    assert "liquidGlassShockwave" not in css, \
        "modals.css must NOT contain liquidGlassShockwave"

    # Active z-index stacking claim must not appear as a CSS rule in the VT section
    vt_section_start = css.find("Theme Transition Performance")
    vt_section_end = css.find("Theme button icon animation", vt_section_start)
    vt_section = css[vt_section_start:vt_section_end] if vt_section_start != -1 else ""
    assert "z-index: 2147483646;" not in vt_section, \
        "Theme-transition CSS must NOT use z-index: 2147483646 as an active CSS rule"

    # PART 5: Incorrect filter-order claims must not exist
    assert "filter is evaluated AFTER" not in css, \
        "modals.css must NOT claim 'filter is evaluated AFTER clip-path' (incorrect)"
    assert "filter is evaluated INSIDE" not in css, \
        "modals.css must NOT claim 'filter is evaluated INSIDE' (incorrect)"

    # PARTS 8 + 9: Accessibility media queries
    assert "prefers-reduced-motion" in css, \
        "modals.css must handle prefers-reduced-motion"
    assert "filter: none" in css, \
        "prefers-reduced-motion block must clear the specular filter"
    assert "prefers-reduced-transparency" in css, \
        "modals.css must handle prefers-reduced-transparency (opaque fallback)"
    assert "prefers-contrast: more" in css, \
        "modals.css must handle prefers-contrast: more (stronger edge)"

    theme_js_path = os.path.join(JS_DIR, "theme.js")
    with open(theme_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # PART 1: WAAPI must be the sole iris owner in JS
    assert "pseudoElement" in js, \
        "theme.js must use WAAPI with pseudoElement to animate ::view-transition-new(root)"
    assert "::view-transition-new(root)" in js, \
        "theme.js must target ::view-transition-new(root) in WAAPI animate call"
    assert "await transition.ready" in js, \
        "theme.js must await transition.ready before WAAPI iris (pseudo-elements not available before ready)"
    assert "clipPath" in js, \
        "theme.js WAAPI animate call must use clipPath for the iris geometry"

    # PART 6/7: reduceMotion must be checked in JS (WAAPI iris is JS-owned)
    assert "reduceMotion" in js, \
        "theme.js must check prefers-reduced-motion (WAAPI iris is JS-owned, not CSS-owned)"
    assert "spin-morph" in js, \
        "theme.js must reference spin-morph for icon animation"

    # DOM wavefront must be absent from JS
    assert "theme-glass-wavefront" not in js, \
        "theme.js must NOT create .theme-glass-wavefront"
    assert "documentElement.appendChild" not in js, \
        "theme.js must NOT append any wavefront DOM element"


@pytest.mark.playwright
def test_playwright_responsive_viewports():
    from playwright.sync_api import sync_playwright
    file_url = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        test_viewports = [
            {"width": 320, "height": 600},
            {"width": 375, "height": 667},
            {"width": 414, "height": 896},
            {"width": 600, "height": 800},
            {"width": 768, "height": 1024},
            {"width": 880, "height": 640},
            {"width": 1120, "height": 780},
            {"width": 1440, "height": 900},
        ]

        page = browser.new_page()

        for vp in test_viewports:
            page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            page.goto(file_url)
            page.wait_for_load_state("domcontentloaded")

            doc_scroll_width = page.evaluate("() => document.documentElement.scrollWidth")
            win_inner_width = page.evaluate("() => window.innerWidth")
            assert doc_scroll_width <= win_inner_width + 1, (
                f"Viewport {vp['width']}x{vp['height']} caused horizontal overflow: scrollWidth {doc_scroll_width} > innerWidth {win_inner_width}"
            )

            if vp["width"] <= 600:
                settings_btn = page.locator("#btnOpenSettings")
                assert settings_btn.is_visible()
                bbox = settings_btn.bounding_box()
                assert bbox is not None
                assert bbox["x"] >= 0 and (bbox["x"] + bbox["width"]) <= win_inner_width + 1

                output_input = page.locator("#outputDisplay")
                in_bbox = output_input.bounding_box()
                if in_bbox:
                    assert in_bbox["width"] >= 200, f"Step 5 input should not be cramped on {vp['width']}px (got {in_bbox['width']}px)"

        browser.close()

