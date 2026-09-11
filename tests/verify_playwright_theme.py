import os
from playwright.sync_api import sync_playwright

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_HTML_PATH = os.path.join(WORKSPACE_DIR, "executable", "ui.html")
FILE_URL = f"file:///{UI_HTML_PATH.replace(os.sep, '/')}"

def verify_theme_rendering():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FILE_URL)
        
        # Verify initial dark theme
        theme = page.evaluate("() => document.documentElement.getAttribute('data-bs-theme')")
        print(f"Initial theme: {theme}")
        assert theme == "dark", f"Expected dark, got {theme}"
        
        # Verify date input styles
        date_input = page.locator("#startDate")
        assert date_input.is_visible(), "Start date input must be visible"
        
        # Toggle theme to light mode
        page.click("#btnToggleTheme")
        page.wait_for_function("() => document.documentElement.getAttribute('data-bs-theme') === 'light'")
        new_theme = page.evaluate("() => document.documentElement.getAttribute('data-bs-theme')")
        print(f"Theme after toggle: {new_theme}")
        assert new_theme == "light", f"Expected light, got {new_theme}"
        
        # Verify theme button label in light mode
        btn_label = page.locator("#themeLabel").inner_text()
        print(f"Theme button label in light mode: {btn_label}")
        assert btn_label == "Dark", f"Expected Dark, got {btn_label}"
        
        # Toggle back to dark mode
        page.click("#btnToggleTheme")
        page.wait_for_function("() => document.documentElement.getAttribute('data-bs-theme') === 'dark'")
        final_theme = page.evaluate("() => document.documentElement.getAttribute('data-bs-theme')")
        print(f"Theme after second toggle: {final_theme}")
        assert final_theme == "dark", f"Expected dark, got {final_theme}"
        
        browser.close()
        print("Playwright theme rendering verification: SUCCESS!")

if __name__ == "__main__":
    verify_theme_rendering()
