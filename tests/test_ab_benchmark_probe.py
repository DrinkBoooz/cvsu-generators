"""
CvSU Document Automation Suite — Phase 3 A/B Benchmark Probe Unit Tests.

Validates:
1. Completeness and physical existence of the 20-asset manifest (7 CSS + 13 JS).
2. Coverage and validity of all JS sentinels.
3. Transport URL contracts:
   - Variant A (html_template) triggers pywebview local BottleServer (is_local_url == True).
   - Variant B (as_uri) bypasses BottleServer (is_local_url == False, file:/// scheme).
4. Telemetry data structures, status classification, and diagnostic mode gating.
"""

import os
import sys
from pathlib import Path
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEC_TEST_DIR = os.path.join(REPO_ROOT, "executable_test")
for p in (EXEC_TEST_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from tests.diagnostics.ab_benchmark_transport import (
    CSS_ASSETS,
    JS_ASSETS,
    ALL_20_ASSETS,
    JS_SENTINELS,
    AssetResult,
    LaunchTelemetry,
    is_diagnostic_mode_enabled,
    DIAGNOSTIC_ENV_VAR,
)
from executable_test.api import get_resource_path
from webview.util import is_local_url


def test_asset_manifest_physical_existence():
    """Verifies that all 20 assets declared in the manifest physically exist on disk."""
    assert len(CSS_ASSETS) == 7, f"Expected 7 CSS assets, got {len(CSS_ASSETS)}"
    assert len(JS_ASSETS) == 13, f"Expected 13 JS assets, got {len(JS_ASSETS)}"
    assert len(ALL_20_ASSETS) == 20, f"Expected 20 total assets, got {len(ALL_20_ASSETS)}"

    for asset in ALL_20_ASSETS:
        full_path = os.path.join(EXEC_TEST_DIR, asset)
        assert os.path.isfile(full_path), f"Asset declared in manifest missing on disk: {full_path}"


def test_js_sentinels_coverage():
    """Verifies that every JS module in JS_ASSETS has an associated validation sentinel."""
    for js_file in JS_ASSETS:
        assert js_file in JS_SENTINELS, f"Missing sentinel expression for {js_file}"
        expr = JS_SENTINELS[js_file]
        assert "typeof" in expr or "Boolean" in expr, f"Invalid sentinel expression for {js_file}: {expr}"


def test_variant_transport_url_contracts():
    """Verifies the pywebview URL classification for Variant A vs Variant B."""
    html_template = get_resource_path("ui.html")
    assert os.path.isabs(html_template)
    assert os.path.isfile(html_template)

    # Variant A: raw path string -> is_local_url is True (starts BottleServer)
    assert is_local_url(html_template) is True, "Variant A must be recognized as local URL by pywebview"

    # Variant B: explicit file URI -> is_local_url is False (bypasses BottleServer, direct file://)
    file_uri = Path(html_template).resolve().as_uri()
    assert file_uri.startswith("file:///"), f"Variant B URI format unexpected: {file_uri}"
    assert is_local_url(file_uri) is False, "Variant B file URI must bypass pywebview local server detection"


def test_telemetry_data_structures():
    """Verifies that LaunchTelemetry and AssetResult instantiate and serialize cleanly."""
    ar = AssetResult(
        asset_name="css/drawers.css",
        category="css",
        requested=True,
        responded=True,
        status_code=200,
        has_sheet=True,
        rules_count=15,
        effective_success=True,
    )
    assert ar.effective_success is True

    lt = LaunchTelemetry(
        launch_id="test_01",
        pair_index=1,
        variant="B",
        stratum="cold",
        mode="desktop",
        order_in_pair=1,
        timestamp_iso="2026-09-17T12:00:00Z",
        configured_url="file:///C:/test/ui.html",
        effective_url="file:///C:/test/ui.html",
        protocol="file",
        d_none_effective=True,
        bridge_roundtrip_ok=True,
        ole_dnd_dropzones_found=True,
    )
    assert lt.protocol == "file"
    assert lt.localhost_port is None
    assert lt.d_none_effective is True


def test_diagnostic_mode_gate(monkeypatch):
    """Verifies that the diagnostic environment variable gate functions correctly."""
    monkeypatch.delenv(DIAGNOSTIC_ENV_VAR, raising=False)
    assert not is_diagnostic_mode_enabled()

    monkeypatch.setenv(DIAGNOSTIC_ENV_VAR, "1")
    assert is_diagnostic_mode_enabled()
