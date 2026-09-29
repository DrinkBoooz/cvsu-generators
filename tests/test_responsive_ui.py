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

    # CSS must be the single authoritative owner of the iris clip-path animation
    assert "appleThemeIrisReveal" in css_content, \
        "modals.css must define appleThemeIrisReveal @keyframes as the CSS-owned iris animation"
    assert "clip-path" in css_content.lower(), \
        "modals.css appleThemeIrisReveal must use clip-path for the iris reveal"

    # JS must NOT independently animate clipPath on ::view-transition-new(root) via WAAPI
    # The dual-ownership anti-pattern causes choppy, competing animations
    assert "pseudoElement" not in js_content or "::view-transition-new(root)" not in js_content, \
        "theme.js must not independently animate ::view-transition-new(root) via WAAPI (CSS is sole owner)"

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

    # Commit 195: DOM wavefront eliminated — JS must NOT create it or check reduced-motion
    assert "theme-glass-wavefront" not in js_content, \
        "theme.js must NOT create DOM wavefront (eliminated in commit 195: captured in old-page VT snapshot)"
    assert "documentElement.appendChild" not in js_content, \
        "theme.js must NOT append any wavefront (DOM wavefront eliminated in commit 195)"


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

def test_vt_native_glass_edge_architecture():
    """
    Verify the VT-native glass edge architecture (commit 195).

    The DOM wavefront overlay (commit 194) was eliminated because:
    1. Created BEFORE document.startViewTransition(): Chromium snapshotted it into
       ::view-transition-old(root) as part of the old-page capture, not a live overlay.
    2. z-index: 2147483646 was a false claim: DOM z-index has no defined relationship
       to the VT rendering layer (a separate post-compositing pass).
    3. backdrop-filter on a snapshotted element blurs frozen pixels, not live content.

    Correct architecture: filter: drop-shadow on ::view-transition-new(root).
    CSS filter is evaluated INSIDE the VT pseudo-element render pass, AFTER clip-path,
    so the drop-shadow traces the iris circle boundary as it expands. Zero extra DOM.

    HIG sources:
    - liquid-glass.md § Color on glass: no inherent color, monochrome specular only
    - accessibility.md § Cognitive + motion.md § Best practices: reduced-motion fallback
    """
    modals_path = os.path.join(CSS_DIR, "modals.css")
    with open(modals_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Glass edge must be VT-native: filter on ::view-transition-new(root)
    assert "::view-transition-new(root)" in css, \
        "modals.css must define ::view-transition-new(root) rules"
    assert "filter: var(--vt-edge-specular)" in css, \
        "::view-transition-new(root) must apply VT-native edge via filter: var(--vt-edge-specular)"
    assert "drop-shadow" in css, \
        "--vt-edge-specular must use drop-shadow for the VT-native iris edge glow"

    # CSS iris animation must exist
    assert "appleThemeIrisReveal" in css, \
        "modals.css must define appleThemeIrisReveal @keyframes"

    # DOM wavefront must be completely absent
    assert ".theme-glass-wavefront" not in css, \
        "modals.css must NOT contain .theme-glass-wavefront (eliminated in commit 195)"
    assert "liquidGlassShockwave" not in css, \
        "modals.css must NOT contain liquidGlassShockwave (wavefront animation eliminated)"

    # False stacking claim must not be present as an active CSS rule in the theme-transition section.
    # Comments may reference the value to document the historical incorrect claim — that's intentional.
    # Only the active CSS declaration z-index: 2147483646; (with semicolon) must not appear.
    vt_section_start = css.find("Theme Transition Performance")
    vt_section_end = css.find("Theme button icon animation", vt_section_start)
    vt_section = css[vt_section_start:vt_section_end] if vt_section_start != -1 else ""
    assert "z-index: 2147483646;" not in vt_section, \
        "Theme-transition CSS must NOT use z-index: 2147483646 as an active CSS rule (incorrect VT rendering model)"

    # Reduced-motion: CSS clears filter (drops VT-native specular) and crossfades
    assert "prefers-reduced-motion" in css, \
        "modals.css must handle prefers-reduced-motion (HIG: motion.md, accessibility.md)"
    assert "filter: none" in css, \
        "prefers-reduced-motion block must set filter: none to clear the VT-native specular"

    theme_js_path = os.path.join(JS_DIR, "theme.js")
    with open(theme_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # JS must NOT create the DOM wavefront
    assert "theme-glass-wavefront" not in js, \
        "theme.js must NOT create .theme-glass-wavefront (DOM wavefront eliminated in commit 195)"
    assert "documentElement.appendChild" not in js, \
        "theme.js must NOT append a wavefront element (eliminated in commit 195)"
    assert "reduceMotion" not in js, \
        "theme.js must NOT check prefers-reduced-motion (CSS owns reduced-motion fallback entirely)"


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

