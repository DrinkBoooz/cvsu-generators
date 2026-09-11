"""
CvSU Document Automation Suite — Desktop Executable Entrypoint.
Initializes the pywebview desktop container with the modular ScriptAPI and native OLE Drag-and-Drop.
"""

import os
import sys

# Ensure repository root and package directory are on sys.path
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(CURR_DIR)

for p in (CURR_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import webview

try:
    from .api import ScriptAPI, get_resource_path
    from .native import setup_window_drag_and_drop
except (ImportError, ValueError):
    from api import ScriptAPI, get_resource_path
    from native import setup_window_drag_and_drop

def create_app():
    """Initializes ScriptAPI and creates the pywebview main application window."""
    api = ScriptAPI()
    html_template = get_resource_path('ui.html')

    window = webview.create_window(
        title='CvSU Gen (Beta)',
        url=html_template,
        js_api=api,
        width=1120,
        height=780,
        min_size=(880, 640),
        text_select=True
    )
    api._window = window

    def on_window_closing():
        api.cancel_generation()

    window.events.closing += on_window_closing
    return window, api

if __name__ == '__main__':
    app_window, app_api = create_app()
    webview.start(setup_window_drag_and_drop, (app_window, app_api))
