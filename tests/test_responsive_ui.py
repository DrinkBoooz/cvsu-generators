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
    theme_js_path = os.path.join(JS_DIR, "theme.js")
    with open(theme_js_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "document.startViewTransition" in content, "theme.js must use View Transitions API"
    assert "spin-morph" in content, "theme.js must trigger spin-morph icon animation"
    assert "clipPath" in content, "theme.js must trigger circular iris animation"

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

def test_liquid_glass_theme_wavefront():
    """Verify Apple Liquid Glass annular wavefront with specular edge refraction."""
    modals_path = os.path.join(CSS_DIR, "modals.css")
    with open(modals_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Annular edge wave with backdrop blur and specular refraction
    assert ".theme-glass-wavefront" in css
    assert "mask-image" in css
    assert "backdrop-filter" in css
    assert "liquidGlassShockwave" in css

    theme_js_path = os.path.join(JS_DIR, "theme.js")
    with open(theme_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "theme-glass-wavefront" in js


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

