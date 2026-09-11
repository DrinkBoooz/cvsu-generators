#!/usr/bin/env python3
"""
executable_test/main.py

PyWebView desktop launcher for the React + TypeScript frontend in executable_test/.
Can load either the production compiled build (dist/index.html) or the Vite development
server (http://localhost:5173 when passing --dev).
"""

import os
import sys
import webview

# Add project root to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from executable.main import ScriptAPI, setup_window_drag_and_drop

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def main():
    api = ScriptAPI()

    dev_mode = '--dev' in sys.argv
    dist_html = get_resource_path(os.path.join('dist', 'index.html'))

    if dev_mode:
        target_url = 'http://localhost:5173'
        print(f"Launching executable_test in DEV mode ({target_url})...")
    else:
        if not os.path.exists(dist_html):
            print(f"Error: {dist_html} not found. Please run 'npm run build' inside executable_test first.")
            sys.exit(1)
        target_url = dist_html
        print(f"Launching executable_test in PRODUCTION mode ({target_url})...")

    window = webview.create_window(
        title='CvSU Gen (React + TypeScript Beta)',
        url=target_url,
        js_api=api,
        width=1120,
        height=780,
        min_size=(880, 640),
        text_select=True,
    )
    api._window = window

    webview.start(setup_window_drag_and_drop, (window, api))

if __name__ == '__main__':
    main()
