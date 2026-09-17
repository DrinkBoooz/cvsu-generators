"""
CvSU Document Automation Suite — Phase 1 Non-Invasive Runtime Asset Diagnostic Probe.

Governing Specification: Investigation & Implementation Plan (Finalized), Phase 1.

Key Diagnostic Functions:
1. Native PyWebView 6.2.1 Python-side Window telemetry:
   - app_window.events.request_sent: strictly read-only, non-mutating, latency-sensitive.
   - app_window.events.response_received: strictly read-only, non-mutating, latency-sensitive.
2. In-memory buffering via deque to ensure zero perturbation to the event loop.
3. Accurate lifecycle recording of Python-side get_current_url() and JavaScript window.location.href.
4. Identification of transport protocol (http://127.0.0.1:<port> vs file://) and dynamic localhost port.
5. Verification of stylesheet CSSOM state and script sentinels without altering source files.
6. Secondary Resource Timing inspection via Chromium performance.getEntriesByType('resource').
7. Exploratory rapid-launch screening (default 25 launches) recording failure frequency of later-listed assets (drawers.css, app.js).
8. Gated strictly by CVSU_DIAGNOSTIC_MODE=1.
"""

import os
import sys
import json
import time
import uuid
import tempfile
import threading
import itertools
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple

# Reconfigure stdout for UTF-8 when supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repository root and executable_test are on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXEC_TEST_DIR = os.path.join(REPO_ROOT, "executable_test")
for p in (EXEC_TEST_DIR, REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import webview
from executable_test.main import create_app

DIAGNOSTIC_ENV_VAR = "CVSU_DIAGNOSTIC_MODE"

def is_diagnostic_mode_enabled() -> bool:
    """Returns True if CVSU_DIAGNOSTIC_MODE is enabled in the environment."""
    return os.environ.get(DIAGNOSTIC_ENV_VAR, "").strip() == "1"

@dataclass
class RawEventRecord:
    event_id: str
    trace_id: str
    timestamp: float
    url: str
    stage: str
    method: Optional[str] = None
    status_code: Optional[int] = None
    thread_id: int = 0

@dataclass
class AssetObservation:
    url: str
    asset_basename: str
    request_sent: bool = False
    request_timestamp: Optional[float] = None
    response_received: bool = False
    response_timestamp: Optional[float] = None
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    transfer_size: Optional[int] = None

@dataclass
class LaunchTelemetrySummary:
    launch_index: int
    timestamp_iso: str
    python_url: str = ""
    browser_url: str = ""
    protocol: str = ""
    localhost_port: Optional[int] = None
    total_requests_sent: int = 0
    total_responses_received: int = 0
    drawers_css_observed: Optional[AssetObservation] = None
    modals_css_observed: Optional[AssetObservation] = None
    app_js_observed: Optional[AssetObservation] = None
    total_unique_assets_requested: int = 0
    total_unique_assets_responded: int = 0
    status_code_counts: Dict[str, int] = field(default_factory=dict)
    stylesheets_evaluation: List[Dict[str, Any]] = field(default_factory=list)
    scripts_evaluation: Dict[str, Any] = field(default_factory=dict)
    hydration_status: Dict[str, Any] = field(default_factory=dict)
    critical_visibility: Dict[str, Any] = field(default_factory=dict)
    resource_timing_entries: List[Dict[str, Any]] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    launch_duration_seconds: float = 0.0

class Phase1DiagnosticProbe:
    """
    Non-invasive diagnostic probe instrumenting PyWebView 6.2.1 native event callbacks.
    Guaranteed zero-perturbation, read-only Request/Response handling.
    """
    def __init__(self, launch_index: int = 1, timeout_seconds: float = 6.0):
        self.launch_index = launch_index
        self.timeout_seconds = timeout_seconds
        self.raw_events: deque = deque()
        self._event_counter = itertools.count(1)
        self.summary = LaunchTelemetrySummary(
            launch_index=launch_index,
            timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        self._window = None
        self._api = None
        self._loaded_event = threading.Event()
        self._start_time = 0.0

    def on_request_sent(self, request):
        """
        PyWebView Window request_sent event callback.
        Strictly read-only, non-mutating, zero-I/O in callback.
        """
        t = time.perf_counter()
        eid = f"evt_{next(self._event_counter)}"
        url = str(request.url)
        method = str(getattr(request, "method", "GET"))
        tid = threading.get_ident()
        asset_basename = url.split("?")[0].split("/")[-1]
        trace_id = f"launch_{self.launch_index}_{asset_basename}"
        # Append shallow record to in-memory deque immediately
        self.raw_events.append(RawEventRecord(
            event_id=eid,
            trace_id=trace_id,
            timestamp=t,
            url=url,
            stage="request_sent",
            method=method,
            status_code=None,
            thread_id=tid
        ))

    def on_response_received(self, response):
        """
        PyWebView Window response_received event callback.
        Strictly read-only, non-mutating, zero-I/O in callback.
        """
        t = time.perf_counter()
        eid = f"evt_{next(self._event_counter)}"
        url = str(response.url)
        status = int(getattr(response, "status_code", 0))
        tid = threading.get_ident()
        asset_basename = url.split("?")[0].split("/")[-1]
        trace_id = f"launch_{self.launch_index}_{asset_basename}"
        # Append shallow record to in-memory deque immediately
        self.raw_events.append(RawEventRecord(
            event_id=eid,
            trace_id=trace_id,
            timestamp=t,
            url=url,
            stage="response_received",
            method=None,
            status_code=status,
            thread_id=tid
        ))

    def on_loaded(self):
        """Signals that the page load has completed in WebView2."""
        self._loaded_event.set()

    def run(self) -> LaunchTelemetrySummary:
        """Executes a single instrumented webview launch."""
        self._start_time = time.perf_counter()
        self._window, self._api = create_app()

        # Wire low-overhead native Python-side telemetry
        self._window.events.request_sent += self.on_request_sent
        self._window.events.response_received += self.on_response_received
        self._window.events.loaded += self.on_loaded

        # Worker thread to observe lifecycle and cleanly destroy window
        def diagnostic_worker():
            # Wait for loaded event or timeout
            self._loaded_event.wait(timeout=self.timeout_seconds)
            time.sleep(0.5)  # brief grace period for resource settlement

            try:
                # 1. Record Python-side get_current_url()
                try:
                    self.summary.python_url = str(self._window.get_current_url())
                except Exception as e:
                    self.summary.python_url = f"<error: {e}>"

                # 2. Record JavaScript-side window.location.href
                try:
                    self.summary.browser_url = str(self._window.evaluate_js("window.location.href") or "")
                except Exception as e:
                    self.summary.browser_url = f"<error: {e}>"

                # 3. Detect Protocol & Localhost Port
                eff_url = self.summary.browser_url or self.summary.python_url
                if eff_url.startswith("file://") or eff_url.startswith("file:///"):
                    self.summary.protocol = "file"
                    self.summary.localhost_port = None
                elif "127.0.0.1:" in eff_url or "localhost:" in eff_url:
                    self.summary.protocol = "http"
                    try:
                        port_str = eff_url.split("://")[1].split("/")[0].split(":")[-1]
                        self.summary.localhost_port = int(port_str)
                    except Exception:
                        self.summary.localhost_port = None
                else:
                    self.summary.protocol = "unknown"

                # 4. Evaluate Stylesheet DOM State
                try:
                    css_js = """
                    Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(function(l) {
                        var rulesCount = -1;
                        try {
                            rulesCount = l.sheet ? l.sheet.cssRules.length : 0;
                        } catch(e) {
                            rulesCount = -999; // SecurityError or inaccessible
                        }
                        return {
                            href: l.getAttribute('href'),
                            fullHref: l.href,
                            hasSheet: !!l.sheet,
                            rulesCount: rulesCount
                        };
                    })
                    """
                    self.summary.stylesheets_evaluation = self._window.evaluate_js(css_js) or []
                except Exception as e:
                    self.summary.stylesheets_evaluation = [{"error": str(e)}]

                # 5. Evaluate Script Sentinels & Functions
                try:
                    scripts_js = """
                    ({
                        stepper_update_fn: typeof updateStepperStatus === 'function',
                        dock_init_fn: typeof initScrollAwareDock === 'function',
                        drawers_open_help_fn: typeof openHelpDrawer === 'function',
                        drawers_open_logs_fn: typeof openLogsDrawer === 'function',
                        drawers_close_all_fn: typeof closeAllDrawers === 'function',
                        bridge_on_sched_fn: typeof window.onScheduleLoaded === 'function',
                        bridge_on_roster_fn: typeof window.onRostersLoaded === 'function',
                        theme_init_fn: typeof initTheme === 'function',
                        step1_init_fn: typeof initStep1 === 'function',
                        step2_init_fn: typeof initStep2 === 'function',
                        step3_init_fn: typeof initStep3 === 'function'
                    })
                    """
                    self.summary.scripts_evaluation = self._window.evaluate_js(scripts_js) or {}
                except Exception as e:
                    self.summary.scripts_evaluation = {"error": str(e)}

                # 6. Evaluate Hydration State & Status Chips
                try:
                    hydration_js = """
                    (function() {
                        var s1 = document.getElementById('statusStep1');
                        var s4 = document.getElementById('statusStep4');
                        var s1Text = s1 ? s1.textContent.trim() : null;
                        var s4Text = s4 ? s4.textContent.trim() : null;
                        return {
                            statusStep1_text: s1Text,
                            statusStep4_text: s4Text,
                            is_raw_white_circle: (s1Text === '⚪' || s1Text === '\\u26aa'),
                            is_hydrated: (s1Text === '•' || s1Text === '✓' || s1Text === '📅' || s1Text === '\\u2022' || s1Text === '\\u2713')
                        };
                    })()
                    """
                    self.summary.hydration_status = self._window.evaluate_js(hydration_js) or {}
                except Exception as e:
                    self.summary.hydration_status = {"error": str(e)}

                # 7. Evaluate Critical Element Visibility (Prevent Element Bleed)
                try:
                    visibility_js = """
                    (function() {
                        function getDisp(id) {
                            var el = document.getElementById(id);
                            if (!el) return 'missing';
                            return window.getComputedStyle(el).display;
                        }
                        return {
                            instructorBanner: getDisp('instructorBanner'),
                            classesSection: getDisp('classesSection'),
                            resultsCard: getDisp('resultsCard'),
                            modalParserSettingsBackdrop: getDisp('modalParserSettingsBackdrop')
                        };
                    })()
                    """
                    self.summary.critical_visibility = self._window.evaluate_js(visibility_js) or {}
                except Exception as e:
                    self.summary.critical_visibility = {"error": str(e)}

                # 8. Supplemental Chromium Resource Timing
                try:
                    timing_js = """
                    (window.performance && window.performance.getEntriesByType)
                        ? window.performance.getEntriesByType('resource').map(function(r) {
                            return {
                                name: r.name,
                                initiatorType: r.initiatorType,
                                duration: r.duration,
                                transferSize: r.transferSize
                            };
                        })
                        : []
                    """
                    self.summary.resource_timing_entries = self._window.evaluate_js(timing_js) or []
                except Exception as e:
                    self.summary.resource_timing_entries = [{"error": str(e)}]

            finally:
                self.summary.launch_duration_seconds = time.perf_counter() - self._start_time
                self._window.destroy()

        # Start diagnostic observation thread
        worker_thread = threading.Thread(target=diagnostic_worker, daemon=True)
        worker_thread.start()

        # Start PyWebView message loop (blocks until window.destroy())
        webview.start()
        worker_thread.join(timeout=2.0)

        # Process Buffered Telemetry Asynchronously After Loop Exits
        self._process_buffered_telemetry()
        return self.summary

    def _process_buffered_telemetry(self):
        """Flushes and aggregates raw events without impacting webview thread."""
        req_map: Dict[str, float] = {}
        resp_map: Dict[str, Tuple[float, int]] = {}
        unique_req_urls = set()
        unique_resp_urls = set()

        while self.raw_events:
            rec: RawEventRecord = self.raw_events.popleft()
            clean_url = rec.url.split("?")[0]
            if rec.stage == "request_sent":
                self.summary.total_requests_sent += 1
                unique_req_urls.add(clean_url)
                req_map[clean_url] = rec.timestamp
            elif rec.stage == "response_received":
                self.summary.total_responses_received += 1
                unique_resp_urls.add(clean_url)
                status = rec.status_code or 0
                resp_map[clean_url] = (rec.timestamp, status)
                status_key = str(status)
                self.summary.status_code_counts[status_key] = (
                    self.summary.status_code_counts.get(status_key, 0) + 1
                )

        self.summary.total_unique_assets_requested = len(unique_req_urls)
        self.summary.total_unique_assets_responded = len(unique_resp_urls)

        # Resource timing lookup for transfer size
        timing_map = {}
        for entry in self.summary.resource_timing_entries:
            if isinstance(entry, dict) and "name" in entry:
                basename = entry["name"].split("?")[0].split("/")[-1]
                timing_map[basename] = entry.get("transferSize", None)

        # Specifically track observed failure assets: drawers.css, modals.css, and app.js
        for target, attr in (
            ("drawers.css", "drawers_css_observed"),
            ("modals.css", "modals_css_observed"),
            ("app.js", "app_js_observed")
        ):
            matched_req_url = next((u for u in unique_req_urls if u.endswith(target)), None)
            matched_resp_url = next((u for u in unique_resp_urls if u.endswith(target)), None)

            obs = AssetObservation(
                url=matched_req_url or matched_resp_url or target,
                asset_basename=target,
                request_sent=bool(matched_req_url),
                request_timestamp=req_map.get(matched_req_url) if matched_req_url else None,
                response_received=bool(matched_resp_url),
                response_timestamp=resp_map[matched_resp_url][0] if matched_resp_url else None,
                status_code=resp_map[matched_resp_url][1] if matched_resp_url else None,
                transfer_size=timing_map.get(target)
            )
            if obs.request_timestamp and obs.response_timestamp:
                obs.duration_ms = (obs.response_timestamp - obs.request_timestamp) * 1000.0
            setattr(self.summary, attr, obs)

def run_exploratory_screening(launches: int = 25, timeout_per_launch: float = 6.0) -> List[LaunchTelemetrySummary]:
    """
    Executes automated consecutive rapid launches as an exploratory failure-frequency screening.
    """
    results: List[LaunchTelemetrySummary] = []
    print(f"\n{'='*75}")
    print(f"PHASE 1 EXPLORATORY RAPID-LAUNCH SCREENING: {launches} Consecutive Launches")
    print(f"Gated by: {DIAGNOSTIC_ENV_VAR}=1 | Strict Read-Only PyWebView Telemetry")
    print(f"{'='*75}\n")

    for i in range(1, launches + 1):
        probe = Phase1DiagnosticProbe(launch_index=i, timeout_seconds=timeout_per_launch)
        summary = probe.run()
        results.append(summary)

        # Live telemetry console line
        drawers_status = summary.drawers_css_observed.status_code if summary.drawers_css_observed else None
        drawers_sz = summary.drawers_css_observed.transfer_size if summary.drawers_css_observed else None
        app_status = summary.app_js_observed.status_code if summary.app_js_observed else None
        s1 = summary.hydration_status.get("statusStep1_text", "?")
        s1_display = "[HYDRATED]" if summary.hydration_status.get("is_hydrated") else "[RAW_WHITE_CIRCLE]" if summary.hydration_status.get("is_raw_white_circle") else str(s1)

        print(
            f"Launch #{i:02d} | Proto: {summary.protocol.upper():4s} "
            f"| Port: {str(summary.localhost_port):5s} "
            f"| Reqs: {summary.total_requests_sent:02d} "
            f"| Resps: {summary.total_responses_received:02d} "
            f"| drawers.css: {str(drawers_status):4s} ({str(drawers_sz)}B) "
            f"| app.js: {str(app_status):4s} "
            f"| Chip1: {s1_display:11s} "
            f"| Elapsed: {summary.launch_duration_seconds:.2f}s"
        )
        # Short inter-launch pause to simulate rapid container cycling
        time.sleep(0.3)

    return results

def persist_diagnostic_session(results: List[LaunchTelemetrySummary]) -> str:
    """Saves complete diagnostic session telemetry to %TEMP%/cvsu_diagnostics/."""
    diag_dir = os.path.join(tempfile.gettempdir(), "cvsu_diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    session_id = f"session_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    session_file = os.path.join(diag_dir, f"{session_id}.json")

    payload = {
        "session_id": session_id,
        "environment": {
            "CVSU_DIAGNOSTIC_MODE": os.environ.get(DIAGNOSTIC_ENV_VAR),
            "pywebview_version": getattr(webview, "__version__", "6.2.1"),
            "platform": sys.platform,
            "python_version": sys.version
        },
        "total_launches": len(results),
        "launches": [asdict(r) for r in results]
    }

    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return session_file

def print_forensic_summary_report(results: List[LaunchTelemetrySummary], session_file: str):
    """Outputs forensic analysis report across the completed launch batch."""
    total = len(results)
    if total == 0:
        print("No diagnostic launches executed.")
        return

    protocols = set(r.protocol for r in results)
    ports = set(r.localhost_port for r in results if r.localhost_port)
    drawers_success = sum(1 for r in results if r.drawers_css_observed and r.drawers_css_observed.response_received)
    modals_success = sum(1 for r in results if r.modals_css_observed and r.modals_css_observed.response_received)
    app_success = sum(1 for r in results if r.app_js_observed and r.app_js_observed.response_received)
    all_resps = [r.total_responses_received for r in results]
    all_reqs = [r.total_requests_sent for r in results]
    hydrated_count = sum(1 for r in results if r.hydration_status.get("is_hydrated"))
    raw_white_circle_count = sum(1 for r in results if r.hydration_status.get("is_raw_white_circle"))

    # Critical visibility breakdown count
    breakdown_count = sum(
        1 for r in results
        if r.critical_visibility.get("instructorBanner") != "none" or
           r.critical_visibility.get("classesSection") != "none" or
           r.critical_visibility.get("resultsCard") != "none"
    )

    print(f"\n{'='*75}")
    print("PHASE 1 FORENSIC DIAGNOSTIC SCREENING REPORT")
    print(f"{'='*75}")
    print(f"Total Launches Executed:           {total}")
    print(f"Transport Protocol Observed:        {', '.join(protocols).upper()}")
    print(f"Assigned Localhost Ports:           {sorted(list(ports))}")
    print(f"Mean Requests Sent per Launch:      {sum(all_reqs)/total:.1f} (range: {min(all_reqs)} - {max(all_reqs)})")
    print(f"Mean Responses Received per Launch: {sum(all_resps)/total:.1f} (range: {min(all_resps)} - {max(all_resps)})")
    print(f"modals.css Received Count:         {modals_success}/{total} ({modals_success/total*100:.1f}%)")
    print(f"drawers.css Received Count:        {drawers_success}/{total} ({drawers_success/total*100:.1f}%)")
    print(f"app.js Received Count:              {app_success}/{total} ({app_success/total*100:.1f}%)")
    print(f"Hydrated Step Chips (dot/check):    {hydrated_count}/{total} ({hydrated_count/total*100:.1f}%)")
    print(f"Raw Step Chips (white circle):      {raw_white_circle_count}/{total} ({raw_white_circle_count/total*100:.1f}%)")
    print(f"Visual Breakdown Observed:          {breakdown_count}/{total} ({breakdown_count/total*100:.1f}%)")
    print(f"Session Telemetry Log:              {session_file}")
    print(f"{'='*75}\n")

if __name__ == "__main__":
    # If not running with CVSU_DIAGNOSTIC_MODE=1, explicitly gate or enable with notice
    if not is_diagnostic_mode_enabled():
        print(f"[*] {DIAGNOSTIC_ENV_VAR} was not set. Enabling {DIAGNOSTIC_ENV_VAR}=1 for this diagnostic run.")
        os.environ[DIAGNOSTIC_ENV_VAR] = "1"

    launches_arg = 25
    if len(sys.argv) > 1:
        if sys.argv[1] == "--single":
            launches_arg = 1
        elif sys.argv[1].isdigit():
            launches_arg = int(sys.argv[1])
        elif sys.argv[1] == "--launches" and len(sys.argv) > 2 and sys.argv[2].isdigit():
            launches_arg = int(sys.argv[2])

    results = run_exploratory_screening(launches=launches_arg)
    session_path = persist_diagnostic_session(results)
    print_forensic_summary_report(results, session_path)
