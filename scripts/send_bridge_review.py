"""
Script to interface with gemini-bridge and request a repository code & UI review.
Queries http://localhost:8765/v1/chat/completions.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BRIDGE_URL = "http://localhost:8765/v1/chat/completions"
MODELS_URL = "http://localhost:8765/v1/models"

REVIEW_PROMPT = """@GitHub DrinkBoooz/cvsu-generators

Using your authenticated GitHub connection, access my repository DrinkBoooz/cvsu-generators (dev branch).

Context:
This project is the Cavite State University (CvSU) Document Generator. It has a Python backend and a desktop PyWebView frontend in `executable_test/` (`ui.html`, `js/`, `css/`).

Task:
Please perform a comprehensive review of the user interface implementation on the `dev` branch:
1. Inspect `executable_test/ui.html` and the JavaScript modules in `executable_test/js/` (e.g. `stepper.js`, `step1.js`, `step2.js`, `step3.js`, `settings.js`, `templates.js`, `bridge.js`).
2. Identify why the current user interface is broken (structural DOM issues, broken selectors, event listener race conditions with pywebview, or state reset bugs).
3. Provide actionable fixes and drop-in code recommendations.
"""

def check_bridge_connection(timeout=3):
    try:
        req = urllib.request.Request(MODELS_URL)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            active_model = models[0]["id"] if models else "gemini-web"
            return True, active_model
    except Exception as e:
        return False, str(e)

def send_review_request(prompt, timeout=180, wait_for_connection=True, max_wait_sec=120):
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
            print("[Bridge Client] Dispatching review prompt to Gemini Bridge...")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_json = json.loads(resp.read().decode())
                choices = res_json.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return json.dumps(res_json, indent=2)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            if e.code == 503 and wait_for_connection:
                elapsed = int(time.time() - start_wait)
                if elapsed >= max_wait_sec:
                    return f"Timed out after {elapsed}s waiting for browser extension to connect."
                if attempt % 5 == 1:
                    print(f"[Waiting] Browser extension not connected yet ({elapsed}s elapsed). Retrying in 2s...")
                time.sleep(2)
                continue
            return f"HTTP Error {e.code}: {err_body}"
        except Exception as e:
            return f"Request Error: {e}"

if __name__ == "__main__":
    ok, info = check_bridge_connection()
    if not ok:
        print(f"[Error] Gemini Bridge is not reachable on port 8765: {info}")
        sys.exit(1)
        
    print(f"[Bridge Client] Bridge server is online. Active model reported: {info}")
    wait_flag = "--no-wait" not in sys.argv
    response = send_review_request(REVIEW_PROMPT, wait_for_connection=wait_flag, max_wait_sec=15)
    print("\n" + "=" * 60)
    print("BRIDGE RESPONSE:")
    print("=" * 60)
    print(response)
