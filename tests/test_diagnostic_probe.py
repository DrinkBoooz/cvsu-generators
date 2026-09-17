"""
Unit test for tests/diagnostics/diagnose_runtime_assets.py.
Validates Phase 1 diagnostic probe data structures, non-mutating request contracts,
and environment gating.
"""

import os
import sys
import copy
from typing import Dict

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.diagnostics.diagnose_runtime_assets import (
    DIAGNOSTIC_ENV_VAR,
    is_diagnostic_mode_enabled,
    RawEventRecord,
    AssetObservation,
    LaunchTelemetrySummary,
    Phase1DiagnosticProbe,
)

class MockRequest:
    def __init__(self, url: str, method: str, headers: Dict[str, str]):
        self.url = url
        self.method = method
        self.headers = copy.copy(headers)

class MockResponse:
    def __init__(self, url: str, status_code: int, headers: Dict[str, str]):
        self.url = url
        self.status_code = status_code
        self.headers = copy.copy(headers)

def test_diagnostic_mode_environment_gating(monkeypatch):
    monkeypatch.delenv(DIAGNOSTIC_ENV_VAR, raising=False)
    assert not is_diagnostic_mode_enabled()

    monkeypatch.setenv(DIAGNOSTIC_ENV_VAR, "0")
    assert not is_diagnostic_mode_enabled()

    monkeypatch.setenv(DIAGNOSTIC_ENV_VAR, "1")
    assert is_diagnostic_mode_enabled()

def test_raw_event_record_and_asset_observation_structures():
    rec = RawEventRecord(
        event_id="evt_1",
        trace_id="launch_1_drawers.css",
        timestamp=100.0,
        url="http://127.0.0.1:5000/css/drawers.css",
        stage="request_sent",
        method="GET",
        status_code=None,
        thread_id=1234
    )
    assert rec.event_id == "evt_1"
    assert rec.stage == "request_sent"
    assert rec.method == "GET"

    obs = AssetObservation(
        url="http://127.0.0.1:5000/css/drawers.css",
        asset_basename="drawers.css",
        request_sent=True,
        request_timestamp=100.0,
        response_received=True,
        response_timestamp=100.025,
        status_code=200,
        duration_ms=25.0
    )
    assert obs.duration_ms == 25.0
    assert obs.status_code == 200

def test_probe_request_sent_is_strictly_read_only():
    probe = Phase1DiagnosticProbe(launch_index=42)
    original_headers = {"User-Agent": "CvSUTest/1.0", "Accept": "text/css"}
    req = MockRequest(
        url="http://127.0.0.1:5000/css/drawers.css",
        method="GET",
        headers=original_headers
    )

    # Invoke on_request_sent callback
    probe.on_request_sent(req)

    # Verify Request object and headers were NEVER mutated
    assert req.headers == original_headers
    assert req.method == "GET"
    assert req.url == "http://127.0.0.1:5000/css/drawers.css"

    # Verify shallow record buffered in deque
    assert len(probe.raw_events) == 1
    buffered = probe.raw_events[0]
    assert buffered.stage == "request_sent"
    assert buffered.trace_id == "launch_42_drawers.css"
    assert buffered.url == req.url

def test_probe_response_received_buffering():
    probe = Phase1DiagnosticProbe(launch_index=42)
    resp = MockResponse(
        url="http://127.0.0.1:5000/css/drawers.css",
        status_code=200,
        headers={"Content-Type": "text/css"}
    )

    probe.on_response_received(resp)

    assert len(probe.raw_events) == 1
    buffered = probe.raw_events[0]
    assert buffered.stage == "response_received"
    assert buffered.status_code == 200
    assert buffered.trace_id == "launch_42_drawers.css"


# ==============================================================================
# Tests for executable_test/main.py _setup_diagnostics Hook
# ==============================================================================

class MockPyWebViewEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __call__(self, *args, **kwargs):
        for h in self.handlers:
            h(*args, **kwargs)


class MockPyWebViewWindow:
    def __init__(self):
        self.events = type("Events", (), {
            "request_sent": MockPyWebViewEvent(),
            "response_received": MockPyWebViewEvent(),
            "closing": MockPyWebViewEvent(),
            "closed": MockPyWebViewEvent()
        })()


def test_main_setup_diagnostics_zero_io_and_single_response_contract(monkeypatch):
    """
    Verifies that executable_test/main.py _setup_diagnostics:
    1. Callback on_request performs ZERO file I/O.
    2. Callback on_response accepts exactly ONE Response argument and performs ZERO file I/O.
    3. Correct status_code is recorded.
    4. Records are buffered in-memory and flushed asynchronously by background flusher.
    """
    import inspect
    from unittest.mock import patch
    import builtins
    from executable_test.main import _setup_diagnostics

    win = MockPyWebViewWindow()
    diag_state = _setup_diagnostics(win, "file:///app/ui.html")
    assert diag_state is not None, "_setup_diagnostics must initialize state"

    on_request = diag_state["on_request"]
    on_response = diag_state["on_response"]
    buffer = diag_state["buffer"]
    stop_event = diag_state["stop_event"]
    flusher = diag_state["flusher"]

    try:
        # Verify on_response signature accepts exactly 1 argument (response)
        sig = inspect.signature(on_response)
        assert len(sig.parameters) == 1, f"on_response must accept 1 parameter, got {sig.parameters}"

        req = MockRequest("file:///app/css/base.css", "GET", {})
        resp = MockResponse("file:///app/css/base.css", 200, {})

        # Track any synchronous file opens during callback execution
        real_open = builtins.open
        open_called_in_callback = []

        def tracked_open(*args, **kwargs):
            open_called_in_callback.append(args)
            return real_open(*args, **kwargs)

        with patch("builtins.open", side_effect=tracked_open):
            on_request(req)
            on_response(resp)

        # Zero file I/O inside callbacks!
        assert len(open_called_in_callback) == 0, f"Synchronous file I/O detected in callbacks: {open_called_in_callback}"

        # Verify buffered records
        records = list(buffer)
        req_records = [r for r in records if r.get("event") == "request_sent"]
        resp_records = [r for r in records if r.get("event") == "response_received"]

        assert len(req_records) == 1
        assert req_records[0]["url"] == "file:///app/css/base.css"
        assert req_records[0]["method"] == "GET"
        assert "timestamp" in req_records[0]

        assert len(resp_records) == 1
        assert resp_records[0]["url"] == "file:///app/css/base.css"
        assert resp_records[0]["status_code"] == 200
        assert "timestamp" in resp_records[0]

    finally:
        # Cleanly stop flusher thread
        win.events.closed()


def test_main_production_mode_dormant(monkeypatch):
    """
    Verifies that when CVSU_DIAGNOSTIC_MODE is unset or '0',
    no diagnostic listeners are installed and _diag_state is absent.
    """
    from executable_test.main import create_app

    for mode in (None, "0", ""):
        if mode is None:
            monkeypatch.delenv("CVSU_DIAGNOSTIC_MODE", raising=False)
        else:
            monkeypatch.setenv("CVSU_DIAGNOSTIC_MODE", mode)

        win, api = create_app()
        assert not hasattr(win, "_diag_state") or win._diag_state is None

