"""
Script to send final verification prompt to Gemini Bridge.
"""
import json
import time
import urllib.error
import urllib.request

BRIDGE_URL = "http://localhost:8765/v1/chat/completions"

VERIFICATION_PROMPT = """@GitHub DrinkBoooz/cvsu-generators

Using your authenticated GitHub connection, access my repository DrinkBoooz/cvsu-generators on the `dev` branch and inspect the latest commit (commit 226 / hash 61fcbae).

We have just implemented all 4 of your recommended safeguards and polish items from your previous review:

1. Unified `app.js` and `bridge.js` Lifecycle:
   - In `executable_test/js/app.js`, removed the redundant second `_bridgeCheckTimer` polling loop and unified initialization behind `window.bridgeReadyPromise.then(onBridgeReady)`.

2. Safe Fallback in `callBridge`:
   - In `executable_test/js/bridge.js`, updated `callBridge(method, ...args)` to check `if (!api || typeof api[method] !== 'function')`, log a clear warning, and safely return `null` instead of throwing an unhandled TypeError.

3. Programmatic Scroll-Spy Suppression with `scrollend`:
   - In `executable_test/js/stepper.js`, enhanced `scrollToStep(cardId)` with a lock (`window._scrollSpyLockedUntil = Date.now() + 850`) and an automated `scrollend` listener (`if ('onscrollend' in window)`) so the active step chip never flickers when smooth-scrolling through intermediate cards.

4. Native File Drop Backdrop Guard:
   - In `executable_test/js/bridge.js`, added modal visibility checks inside `window.onScheduleLoaded` and `window.onRostersLoaded`. If a modal backdrop (`.modal-backdrop-custom:not(.d-none)`) is active, accidental background file drops into Step 1 or Step 2 are safely blocked.

Please review commit 61fcbae on `dev` and give your final verdict and verification on these improvements.
"""

def send_verification_request():
    payload = {
        "model": "gemini-web",
        "messages": [
            {"role": "user", "content": VERIFICATION_PROMPT}
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BRIDGE_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    print("[Bridge Client] Dispatching final verification prompt to Gemini Bridge...")
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            res_json = json.loads(resp.read().decode())
            choices = res_json.get("choices", [])
            content = choices[0].get("message", {}).get("content", "") if choices else json.dumps(res_json, indent=2)
            print("\n" + "=" * 60)
            print("GEMINI FINAL VERIFICATION RESPONSE:")
            print("=" * 60)
            print(content)
            with open("scratch/gemini_final_verification_response.txt", "w", encoding="utf-8") as f:
                f.write(content)
    except Exception as e:
        print("[Error] Failed to get response:", e)

if __name__ == "__main__":
    send_verification_request()
