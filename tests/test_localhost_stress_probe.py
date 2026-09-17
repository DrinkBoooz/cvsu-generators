"""
Unit test for Phase 2 localhost server stress harness.
Validates asset manifest count, is_local_url evaluation, and event data structures.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.diagnostics.stress_localhost_server import (
    ASSET_MANIFEST,
    CorrelatedEventRecord,
    TierStressResult,
    is_diagnostic_mode_enabled,
    DIAGNOSTIC_ENV_VAR,
)
from executable_test.api import get_resource_path
import webview.http as webview_http
from wsgiref.simple_server import WSGIServer

def test_asset_manifest_conformance():
    # Exactly 20 assets (7 CSS + 13 JS)
    assert len(ASSET_MANIFEST) == 20
    css_files = [a for a in ASSET_MANIFEST if a.startswith("css/")]
    js_files = [a for a in ASSET_MANIFEST if a.startswith("js/")]
    assert len(css_files) == 7
    assert len(js_files) == 13
    assert "css/drawers.css" in ASSET_MANIFEST
    assert "css/modals.css" in ASSET_MANIFEST
    assert "js/app.js" in ASSET_MANIFEST

def test_is_local_url_evaluates_true_for_ui_html():
    html_template = get_resource_path("ui.html")
    assert os.path.exists(html_template)
    assert webview_http.is_local_url(html_template) is True

def test_server_architecture_defaults():
    # WSGIServer default queue size
    assert WSGIServer.request_queue_size == 5

def test_event_structures():
    rec = CorrelatedEventRecord(
        event_id="evt_1",
        trace_id="trace_1",
        timestamp=10.0,
        stage="server_handler_entered",
        asset_path="css/drawers.css",
        thread_id=123,
    )
    assert rec.stage == "server_handler_entered"
    assert rec.trace_id == "trace_1"
