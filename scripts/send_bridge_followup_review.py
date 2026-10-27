"""
Script to send follow-up review prompt to Gemini Bridge with GitHub integration.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BRIDGE_URL = "http://localhost:8765/v1/chat/completions"
MODELS_URL = "http://localhost:8765/v1/models"

FOLLOWUP_PROMPT = """@GitHub DrinkBoooz/cvsu-generators

Using your authenticated GitHub connection, access my repository DrinkBoooz/cvsu-generators on the `dev` branch and inspect the latest commit (commit 225 / hash 9814643).

### 1. Context & Primary Request
Our initial request to you was:
"Please perform a comprehensive review of the user interface implementation on the dev branch:
1. Inspect executable_test/ui.html and the JavaScript modules in executable_test/js/ (e.g. stepper.js, step1.js, step2.js, step3.js, settings.js, templates.js, bridge.js).
2. Identify why the current user interface is broken (structural DOM issues, broken selectors, event listener race conditions with pywebview, or state reset bugs).
3. Provide actionable fixes and drop-in code recommendations."

### 2. Your First Response & Diagnosis Summary
In your previous review, you identified the following critical root causes:
- A. Empty/truncated `executable_test/css/layout.css` causing catastrophic layout collapse (app header, split-pane workspace, stepper bar, and action dock had 0 styles).
- B. PyWebView bridge race condition in `js/bridge.js` & `js/app.js` (DOM content loaded calls API before `window.pywebview.api` is injected by Webview2).
- C. Global `window.*` scope breakage vs module functions (`goToStep`, `scrollToStep`, `setActiveStepChip`, `updateStepperStatus`).
- D. Stepper & step view visibility desync and drawer tab widths lacking equal flex sizing.
- E. State reset & duplicate listener bugs (`resetDownstreamFromStep1` missing from `state.js`).

### 3. What Was Implemented in Commit 225 (`9814643`)
We have completely implemented your recommendations and fixed related issues:
1. `executable_test/css/layout.css`:
   - Restored the 470+ lines of structural layout CSS (top-nav-bar, top-header, brand-lockup, stepper-bar, stepper-track, step-chip, dashboard-grid, dashboard-col, bottom-action-bar, btn-dock-action, drawer-tab).
   - Added responsive constraints (`max-width: 100vw; overflow: hidden;`) and mobile queries (`@media (max-width: 600px)`) to guarantee zero horizontal overflow across 320px–1440px viewports.
2. `executable_test/js/bridge.js`:
   - Added `bridgeReadyPromise` and `window.callBridge(method, ...args)` with interval polling fallback to queue all backend invocations until `pywebviewready` fires.
3. `executable_test/js/app.js`:
   - Replaced fragile DOMContentLoaded API calls with `onBridgeReady()` callback waiting for `pywebviewready` (with fallback timer) before calling `loadWorkspaceListUI()`, `loadTemplateSetsUI()`, and `loadCustomTemplatesUI()`.
4. `executable_test/js/state.js`:
   - Added `resetDownstreamFromStep1()` and explicitly exported `window.state`, `window.saveRosterConfigs`, `window.escapeHTML`, and `window.resetDownstreamFromStep1`.
5. `executable_test/js/stepper.js`:
   - Explicitly bound stepper lifecycle functions (`scrollToStep`, `setActiveStepChip`, `initScrollAwareDock`, `triggerWorkflowFromDock`, `setGenerationRunningState`, `updateStepperStatus`, `initStepperScrollSpy`) to `window`.
6. `executable_test/ui.html`:
   - Diagnosed and resolved a subtle DOM hierarchy failure: removed an orphaned closing `</div>` tag following `#customTemplateDiagnostics` which had prematurely closed `.modal-body-custom` and `.modal-dialog-custom`, causing `#modalParserSettingsBackdrop` to render the modal dialog and footer side-by-side on mobile.
7. Automated Test Suite Validation:
   - `tests/test_settings_modal_responsive.py`: 5 passed (100%).
   - `tests/test_responsive_ui.py`: 9 passed across all Playwright viewports (320px–1440px).
   - `tests/test_ui_consistency.py`: 6 passed.
   - Authoritative test orchestrator (`scripts/test_orchestrator.py --fast`): 716 passed, 0 failed, 2 skipped (100%).

### 4. Requested Review
Please review the latest commit (`9814643`) on the `dev` branch:
1. Does our implementation completely resolve the root causes identified in your initial diagnosis?
2. Assess the code quality, resilience, and architectural soundness of the bridge promise, event handling, and layout rules.
3. Are there any subtle edge cases or remaining improvements you recommend for the desktop PyWebView frontend?
"""

def send_review_request(prompt, timeout=240, max_wait_sec=60):
    payload = {
        "model": "gemini-web",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BRIDGE_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    start_wait = time.time()
    attempt = 0
    while True:
        attempt += 1
        try:
            print("[Bridge Client] Dispatching follow-up review prompt to Gemini Bridge...")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_json = json.loads(resp.read().decode())
                choices = res_json.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return json.dumps(res_json, indent=2)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            if e.code == 503:
                elapsed = int(time.time() - start_wait)
                if elapsed >= max_wait_sec:
                    return f"Timed out after {elapsed}s waiting for browser extension: {err_body}"
                if attempt % 5 == 1:
                    print(f"[Waiting] Browser extension reconnecting ({elapsed}s elapsed)...")
                time.sleep(2)
                continue
            return f"HTTP Error {e.code}: {err_body}"
        except Exception as e:
            return f"Request Error: {e}"

if __name__ == "__main__":
    resp = send_review_request(FOLLOWUP_PROMPT)
    print("\n" + "=" * 60)
    print("GEMINI FOLLOW-UP REVIEW RESPONSE:")
    print("=" * 60)
    print(resp)
    with open("scratch/gemini_followup_review_response.txt", "w", encoding="utf-8") as f:
        f.write(resp)
