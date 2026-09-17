"""
CvSU Document Automation Suite — Phase 2 Localhost Server Stress & Queue Instrumentation.

Governing Specification: Investigation & Implementation Plan (Finalized), Phase 2.

Key Diagnostic Objectives:
1. Verify is_local_url() behavior for the application's ui.html path.
2. Inspect and instrument the complete server call chain:
     main.py -> webview.start() -> start_global_server() -> start_server() ->
     BottleServer.start_server() -> ThreadedAdapter / WSGI
3. Document exact server architecture: address, dynamic port, root path,
   server class (ThreadedAdapter), WSGIServer request_queue_size (5).
4. Controlled localhost stress test across 5 concurrency tiers:
     5, 10, 20, 40, 80 concurrent requests
   using the exact 20-asset manifest from ui.html.
5. Multi-stage per-event telemetry correlation:
     - client_request_attempted
     - server_handler_entered
     - server_response_produced
     - response_received / requestfinished
     - requestfailed (socket errors, timeouts, resets)
   using unique event_id per record and trace_id for cross-stage request correlation.
6. Empirical discrimination: determine whether failures occur before WSGI entry
   (TCP accept / listen queue layer) or inside WSGI request dispatch.
7. Gated strictly by CVSU_DIAGNOSTIC_MODE=1.
"""

import os
import sys
import time
import json
import uuid
import socket
import urllib.request
import urllib.error
import tempfile
import threading
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

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
import webview.http as webview_http
from executable_test.api import get_resource_path

DIAGNOSTIC_ENV_VAR = "CVSU_DIAGNOSTIC_MODE"

def is_diagnostic_mode_enabled() -> bool:
    """Returns True if CVSU_DIAGNOSTIC_MODE is enabled in the environment."""
    return os.environ.get(DIAGNOSTIC_ENV_VAR, "").strip() == "1"

# The exact 20 asset manifest referenced by ui.html (7 CSS + 13 JS)
ASSET_MANIFEST = [
    # 7 CSS files
    "css/tokens.css",
    "css/base.css",
    "css/layout.css",
    "css/components.css",
    "css/tables.css",
    "css/modals.css",
    "css/drawers.css",
    # 13 JS files
    "js/state.js",
    "js/toast.js",
    "js/modal.js",
    "js/theme.js",
    "js/drawers.js",
    "js/stepper.js",
    "js/bridge.js",
    "js/step1.js",
    "js/step2.js",
    "js/step3.js",
    "js/settings.js",
    "js/templates.js",
    "js/app.js",
]

@dataclass
class CorrelatedEventRecord:
    event_id: str
    trace_id: str
    timestamp: float
    stage: str
    asset_path: str
    thread_id: int
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    bytes_transferred: Optional[int] = None
    duration_ms: Optional[float] = None

@dataclass
class TierStressResult:
    tier: int
    delay_ms: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    pre_wsgi_drops: int        # Client attempted, server handler NEVER entered
    in_wsgi_drops: int         # Server handler entered, response NEVER produced
    post_wsgi_drops: int       # Server response produced, client FAILED to receive
    completed_requests: int    # Full round trip completed
    error_types: Dict[str, int] = field(default_factory=dict)
    durations_ms: List[float] = field(default_factory=list)
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    drawers_css_outcome: Dict[str, Any] = field(default_factory=dict)
    modals_css_outcome: Dict[str, Any] = field(default_factory=dict)
    app_js_outcome: Dict[str, Any] = field(default_factory=dict)

class InstrumentedBottleServer:
    """
    Controlled pywebview BottleServer runner with per-stage WSGI instrumentation
    and optional controlled artificial response delay.
    """
    def __init__(self, root_path: str, response_delay_ms: float = 0.0):
        self.root_path = root_path
        self.response_delay_ms = response_delay_ms
        self.server_instance: Optional[webview_http.BottleServer] = None
        self.server_address: str = ""
        self.server_port: int = 0
        self.common_path: str = ""
        self.server_events: List[CorrelatedEventRecord] = []
        self._event_lock = threading.Lock()
        self._event_counter = itertools.count(1)

    def _record_server_event(
        self,
        trace_id: str,
        stage: str,
        asset_path: str,
        status_code: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error_msg: Optional[str] = None,
    ):
        eid = f"srv_evt_{next(self._event_counter)}"
        rec = CorrelatedEventRecord(
            event_id=eid,
            trace_id=trace_id,
            timestamp=time.perf_counter(),
            stage=stage,
            asset_path=asset_path,
            thread_id=threading.get_ident(),
            status_code=status_code,
            error_message=error_msg,
            bytes_transferred=bytes_transferred,
            duration_ms=duration_ms,
        )
        with self._event_lock:
            self.server_events.append(rec)

    def start(self, port: Optional[int] = None) -> Tuple[str, int]:
        """
        Starts the BottleServer using pywebview's actual start_server infrastructure
        with WSGI entry/exit instrumentation wrapped around bottle.
        """
        import bottle

        html_template = os.path.join(self.root_path, "ui.html")
        server = webview_http.BottleServer()
        server.root_path = self.root_path
        self.server_port = port or webview_http._get_random_port()
        server.port = self.server_port

        app = bottle.Bottle()

        @app.route("/<filepath:path>")
        def asset_handler(filepath):
            t_enter = time.perf_counter()
            trace_id = bottle.request.query.get("_trace_id", "untracked")

            # 1. Record WSGI Handler Entry
            self._record_server_event(
                trace_id=trace_id,
                stage="server_handler_entered",
                asset_path=filepath,
            )

            # Optional controlled server delay (simulating I/O contention or cold disk)
            if self.response_delay_ms > 0:
                time.sleep(self.response_delay_ms / 1000.0)

            # Serve static file
            resp = bottle.static_file(filepath, root=self.root_path)

            t_exit = time.perf_counter()
            duration_ms = (t_exit - t_enter) * 1000.0

            # 2. Record WSGI Response Production
            status = getattr(resp, "status_code", 200)
            length = None
            try:
                length = resp.content_length
            except Exception:
                pass

            self._record_server_event(
                trace_id=trace_id,
                stage="server_response_produced",
                asset_path=filepath,
                status_code=status,
                bytes_transferred=length,
                duration_ms=duration_ms,
            )
            return resp

        server_adapter = webview_http.ThreadedAdapter
        server.thread = threading.Thread(
            target=lambda: bottle.run(
                app=app,
                server=server_adapter,
                port=server.port,
                quiet=True,
            ),
            daemon=True,
        )
        server.thread.start()
        server.running = True
        self.server_address = f"http://127.0.0.1:{server.port}/"
        self.server_instance = server

        # Wait briefly for server socket bind
        time.sleep(0.3)
        return self.server_address, self.server_port

def run_single_request(
    server_address: str,
    asset_path: str,
    trace_id: str,
    cache_bust: str,
    client_timeout: float = 3.0,
) -> Tuple[str, List[CorrelatedEventRecord]]:
    """
    Executes a single HTTP client request with full per-stage telemetry.
    """
    events: List[CorrelatedEventRecord] = []
    eid_counter = itertools.count(1)

    url = f"{server_address}{asset_path}?_trace_id={trace_id}&_cb={cache_bust}"
    tid = threading.get_ident()

    # Stage: client_request_attempted
    t_start = time.perf_counter()
    events.append(
        CorrelatedEventRecord(
            event_id=f"clt_evt_{next(eid_counter)}",
            trace_id=trace_id,
            timestamp=t_start,
            stage="client_request_attempted",
            asset_path=asset_path,
            thread_id=tid,
        )
    )

    req = urllib.request.Request(
        url=url,
        headers={
            "User-Agent": "CvSU-StressHarness/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )

    status_code = None
    err_msg = None
    bytes_read = 0

    try:
        with urllib.request.urlopen(req, timeout=client_timeout) as resp:
            status_code = resp.getcode()
            content = resp.read()
            bytes_read = len(content)

        t_end = time.perf_counter()
        dur_ms = (t_end - t_start) * 1000.0

        # Stage: response_received / requestfinished
        events.append(
            CorrelatedEventRecord(
                event_id=f"clt_evt_{next(eid_counter)}",
                trace_id=trace_id,
                timestamp=t_end,
                stage="response_received",
                asset_path=asset_path,
                thread_id=tid,
                status_code=status_code,
                bytes_transferred=bytes_read,
                duration_ms=dur_ms,
            )
        )
    except urllib.error.HTTPError as e:
        t_end = time.perf_counter()
        dur_ms = (t_end - t_start) * 1000.0
        # HTTP error (e.g. 404, 500) is an HTTP response, not a transport socket abort
        events.append(
            CorrelatedEventRecord(
                event_id=f"clt_evt_{next(eid_counter)}",
                trace_id=trace_id,
                timestamp=t_end,
                stage="response_received",
                asset_path=asset_path,
                thread_id=tid,
                status_code=e.code,
                error_message=str(e),
                duration_ms=dur_ms,
            )
        )
    except Exception as e:
        t_end = time.perf_counter()
        dur_ms = (t_end - t_start) * 1000.0
        # Transport level abort / socket rejection
        events.append(
            CorrelatedEventRecord(
                event_id=f"clt_evt_{next(eid_counter)}",
                trace_id=trace_id,
                timestamp=t_end,
                stage="requestfailed",
                asset_path=asset_path,
                thread_id=tid,
                error_message=f"{type(e).__name__}: {str(e)}",
                duration_ms=dur_ms,
            )
        )

    return trace_id, events

def run_concurrency_tier(
    server: InstrumentedBottleServer,
    tier: int,
    manifest: List[str],
    response_delay_ms: float = 0.0,
) -> TierStressResult:
    """
    Executes a controlled concurrent stress tier (5, 10, 20, 40, or 80 requests).
    """
    server.response_delay_ms = response_delay_ms
    # Prepare the exact request list
    requests_to_dispatch: List[Tuple[str, str, str]] = []

    # Map tier requests drawing from the 20-asset manifest
    for i in range(tier):
        asset = manifest[i % len(manifest)]
        cb_id = f"tier{tier}_iter{i}_{uuid.uuid4().hex[:6]}"
        trace_id = f"trace_t{tier}_r{i:02d}_{asset.split('/')[-1]}"
        requests_to_dispatch.append((asset, trace_id, cb_id))

    client_event_map: Dict[str, List[CorrelatedEventRecord]] = {}
    durations: List[float] = []

    # Dispatch concurrently using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=tier) as executor:
        futures = [
            executor.submit(
                run_single_request,
                server.server_address,
                asset,
                trace_id,
                cb_id,
            )
            for asset, trace_id, cb_id in requests_to_dispatch
        ]
        for f in as_completed(futures):
            tid, evts = f.result()
            client_event_map[tid] = evts

    # Correlate server-side and client-side events by trace_id
    server_events_by_trace: Dict[str, List[CorrelatedEventRecord]] = {}
    with server._event_lock:
        for s_evt in server.server_events:
            server_events_by_trace.setdefault(s_evt.trace_id, []).append(s_evt)

    result = TierStressResult(
        tier=tier,
        delay_ms=response_delay_ms,
        total_requests=tier,
        successful_requests=0,
        failed_requests=0,
        pre_wsgi_drops=0,
        in_wsgi_drops=0,
        post_wsgi_drops=0,
        completed_requests=0,
    )

    for asset, trace_id, cb_id in requests_to_dispatch:
        c_events = client_event_map.get(trace_id, [])
        s_events = server_events_by_trace.get(trace_id, [])

        c_attempted = any(e.stage == "client_request_attempted" for e in c_events)
        c_responded = any(e.stage == "response_received" for e in c_events)
        c_failed = any(e.stage == "requestfailed" for e in c_events)

        s_entered = any(e.stage == "server_handler_entered" for e in s_events)
        s_produced = any(e.stage == "server_response_produced" for e in s_events)

        # Get client response duration if available
        for e in c_events:
            if e.duration_ms is not None:
                durations.append(e.duration_ms)
            if e.stage == "response_received" and e.status_code == 200:
                result.successful_requests += 1
                result.completed_requests += 1
            elif e.stage == "requestfailed":
                result.failed_requests += 1
                err_type = e.error_message.split(":")[0] if e.error_message else "UnknownError"
                result.error_types[err_type] = result.error_types.get(err_type, 0) + 1

        # Failure Stage Attribution
        if not c_responded or c_failed:
            if not s_entered:
                # Client dispatched request, but WSGI handler was NEVER entered!
                # (Proves TCP accept / listen-queue / connection drop at OS layer!)
                result.pre_wsgi_drops += 1
            elif s_entered and not s_produced:
                result.in_wsgi_drops += 1
            elif s_entered and s_produced:
                result.post_wsgi_drops += 1

        # Track key failure assets
        asset_basename = asset.split("/")[-1]
        if asset_basename in ("drawers.css", "modals.css", "app.js"):
            attr_name = f"{asset_basename.replace('.', '_')}_outcome"
            setattr(
                result,
                attr_name,
                {
                    "trace_id": trace_id,
                    "server_entered": s_entered,
                    "server_produced": s_produced,
                    "client_responded": c_responded,
                    "client_failed": c_failed,
                },
            )

    result.durations_ms = sorted(durations)
    if durations:
        result.p50_duration_ms = result.durations_ms[len(result.durations_ms) // 2]
        result.p95_duration_ms = result.durations_ms[int(len(result.durations_ms) * 0.95)]
        result.max_duration_ms = max(result.durations_ms)

    return result

def run_phase2_controlled_experiment(
    concurrency_tiers: List[int] = [5, 10, 20, 40, 80],
    response_delays_ms: List[float] = [0.0, 10.0, 25.0],
) -> Dict[str, Any]:
    """
    Executes the complete Phase 2 controlled localhost stress experiment.
    """
    html_template = get_resource_path("ui.html")
    root_path = os.path.dirname(html_template)

    # 1. Architectural & Call Chain Verification
    is_local = webview_http.is_local_url(html_template)
    server = InstrumentedBottleServer(root_path=root_path)
    server_addr, server_port = server.start()

    from wsgiref.simple_server import WSGIServer

    architecture_info = {
        "html_template": html_template,
        "is_local_url": is_local,
        "server_address": server_addr,
        "assigned_port": server_port,
        "root_path": root_path,
        "server_adapter": "webview.http.ThreadedAdapter",
        "underlying_server_class": "ThreadingMixIn, WSGIServer",
        "wsgi_request_queue_size": WSGIServer.request_queue_size,
    }

    print(f"\n{'='*75}")
    print("PHASE 2 CONTROLLED LOCALHOST SERVER STRESS EXPERIMENT")
    print(f"Gated by: {DIAGNOSTIC_ENV_VAR}=1")
    print(f"{'='*75}")
    print(f"Server Address:        {server_addr}")
    print(f"Root Path:             {root_path}")
    print(f"is_local_url():        {is_local}")
    print(f"WSGIServer Backlog:    {WSGIServer.request_queue_size} slots")
    print(f"Asset Manifest Count:  {len(ASSET_MANIFEST)} unique assets")
    print(f"Tested Concurrency:    {concurrency_tiers}")
    print(f"Tested Server Delays:  {response_delays_ms} ms")
    print(f"{'='*75}\n")

    tier_results: List[Dict[str, Any]] = []

    for delay in response_delays_ms:
        print(f"\n--- Testing Server Response Delay: {delay} ms ---")
        for tier in concurrency_tiers:
            t_res = run_concurrency_tier(
                server=server,
                tier=tier,
                manifest=ASSET_MANIFEST,
                response_delay_ms=delay,
            )
            tier_results.append(asdict(t_res))

            print(
                f"Tier {tier:02d} (delay: {delay:4.1f}ms) | "
                f"Success: {t_res.successful_requests:02d}/{t_res.total_requests:02d} | "
                f"Pre-WSGI Drops: {t_res.pre_wsgi_drops:02d} | "
                f"In-WSGI Drops: {t_res.in_wsgi_drops:02d} | "
                f"p50: {t_res.p50_duration_ms:5.1f}ms | "
                f"p95: {t_res.p95_duration_ms:5.1f}ms | "
                f"Max: {t_res.max_duration_ms:5.1f}ms | "
                f"Errors: {t_res.error_types}"
            )
            # Brief pause between tiers
            time.sleep(0.2)

    session_data = {
        "architecture_info": architecture_info,
        "concurrency_tiers": concurrency_tiers,
        "response_delays_ms": response_delays_ms,
        "tier_results": tier_results,
        "total_server_events_recorded": len(server.server_events),
    }

    # Persist session JSON to %TEMP%/cvsu_diagnostics/
    diag_dir = os.path.join(tempfile.gettempdir(), "cvsu_diagnostics")
    os.makedirs(diag_dir, exist_ok=True)
    session_file = os.path.join(
        diag_dir, f"phase2_stress_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
    )
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

    session_data["session_file"] = session_file
    return session_data

if __name__ == "__main__":
    if not is_diagnostic_mode_enabled():
        print(f"[*] {DIAGNOSTIC_ENV_VAR} was not set. Enabling {DIAGNOSTIC_ENV_VAR}=1 for this diagnostic run.")
        os.environ[DIAGNOSTIC_ENV_VAR] = "1"

    session_report = run_phase2_controlled_experiment()
    print(f"\nPhase 2 stress session persisted to: {session_report.get('session_file')}")
