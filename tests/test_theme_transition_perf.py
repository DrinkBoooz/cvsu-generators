import os
import pytest
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

def test_theme_transition_zero_runaway_events():
    """Verify that toggling themes triggers zero DOM transition cascades (no runaway 700+ transitions)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(FILE_URL)

        # Confirm initial state
        initial_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme') || document.documentElement.getAttribute('data-bs-theme')")
        assert initial_theme == "dark", f"Expected dark, got {initial_theme}"

        # Track transitionstart events during dark -> light toggle
        res_to_light = page.evaluate('''() => {
            return new Promise((resolve) => {
                const transitions = [];
                const onTransitionStart = (e) => {
                    transitions.push({
                        tag: e.target.tagName,
                        propertyName: e.propertyName
                    });
                };
                window.addEventListener('transitionstart', onTransitionStart, true);
                const start = performance.now();

                const btn = document.getElementById('btnToggleTheme');
                btn.click();

                // Wait for theme to change and View Transition to complete
                const checkInterval = setInterval(() => {
                    const cur = document.documentElement.getAttribute('data-theme') || document.documentElement.getAttribute('data-bs-theme');
                    if (cur === 'light') {
                        clearInterval(checkInterval);
                        setTimeout(() => {
                            window.removeEventListener('transitionstart', onTransitionStart, true);
                            resolve({
                                count: transitions.length,
                                duration: performance.now() - start
                            });
                        }, 250);
                    }
                }, 10);
            });
        }''')

        print(f"Dark -> Light: transitions={res_to_light['count']}, duration={res_to_light['duration']:.1f}ms")
        assert res_to_light["count"] == 0, f"Expected 0 runaway transitions, got {res_to_light['count']}"
        assert res_to_light["duration"] < 600, f"Theme toggle took too long: {res_to_light['duration']:.1f}ms"

        # Verify button label
        btn_label = page.locator("#themeLabel").inner_text()
        assert btn_label == "Dark", f"Expected Dark button label in light mode, got {btn_label}"

        # Track transitionstart events during light -> dark toggle
        res_to_dark = page.evaluate('''() => {
            return new Promise((resolve) => {
                const transitions = [];
                const onTransitionStart = (e) => {
                    transitions.push({
                        tag: e.target.tagName,
                        propertyName: e.propertyName
                    });
                };
                window.addEventListener('transitionstart', onTransitionStart, true);
                const start = performance.now();

                const btn = document.getElementById('btnToggleTheme');
                btn.click();

                const checkInterval = setInterval(() => {
                    const theme = document.documentElement.getAttribute('data-theme') || document.documentElement.getAttribute('data-bs-theme');
                    if (theme === 'dark') {
                        clearInterval(checkInterval);
                        setTimeout(() => {
                            window.removeEventListener('transitionstart', onTransitionStart, true);
                            resolve({
                                count: transitions.length,
                                duration: performance.now() - start
                            });
                        }, 250);
                    }
                }, 10);
            });
        }''')

        print(f"Light -> Dark: transitions={res_to_dark['count']}, duration={res_to_dark['duration']:.1f}ms")
        assert res_to_dark["count"] == 0, f"Expected 0 runaway transitions, got {res_to_dark['count']}"
        assert res_to_dark["duration"] < 600, f"Theme toggle took too long: {res_to_dark['duration']:.1f}ms"

        # Verify final button label
        final_label = page.locator("#themeLabel").inner_text()
        assert final_label == "Light", f"Expected Light button label in dark mode, got {final_label}"

        browser.close()

if __name__ == "__main__":
    test_theme_transition_zero_runaway_events()
    print("Performance test passed successfully!")
