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
