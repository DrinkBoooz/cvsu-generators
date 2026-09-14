"""
Packaged Windows Executable (CvSU Gen.exe) Smoke Test Suite.
Validates the actual compiled PyInstaller binary, PE version information,
Authenticode code-signing certificate, and live process launch/termination lifecycle.
"""

import os
import sys
import time
import subprocess
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PATH = os.path.join(WORKSPACE_DIR, "executable_test", "dist", "CvSU Gen.exe")


def test_packaged_executable_binary_and_pe_metadata():
    """Verify packaged binary exists, has valid PE metadata, and version conforms to Release v1.0.1."""
    assert os.path.exists(EXE_PATH), f"Compiled binary not found at {EXE_PATH}"
    size_bytes = os.path.getsize(EXE_PATH)
    assert size_bytes > 15 * 1024 * 1024, f"Binary size {size_bytes} is unexpectedly small (< 15MB)"

    # Inspect Windows PE VersionInfo
    ps_cmd = f"(Get-Item '{EXE_PATH}').VersionInfo | ConvertTo-Json"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        check=True
    )
    import json
    vinfo = json.loads(result.stdout)

    assert vinfo.get("FileVersion") == "1.0.1.0", f"Expected FileVersion 1.0.1.0, got {vinfo.get('FileVersion')}"
    assert vinfo.get("ProductVersion") == "1.0.1.0", f"Expected ProductVersion 1.0.1.0, got {vinfo.get('ProductVersion')}"
    assert "Dan Joseph Ortega" in vinfo.get("CompanyName", ""), "CompanyName must contain Dan Joseph Ortega"
    assert "Dan Joseph Ortega" in vinfo.get("LegalCopyright", ""), "LegalCopyright must contain Dan Joseph Ortega"
    assert vinfo.get("ProductName") == "CvSU Document Generator", "ProductName must match CvSU Document Generator"


def test_packaged_executable_authenticode_signature():
    """Verify that CvSU Gen.exe is digitally signed with a Valid Authenticode certificate."""
    assert os.path.exists(EXE_PATH), f"Compiled binary not found at {EXE_PATH}"

    ps_status_cmd = f"(Get-AuthenticodeSignature -FilePath '{EXE_PATH}').Status.ToString()"
    res_status = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_status_cmd],
        capture_output=True,
        text=True,
        check=True
    )
    status = res_status.stdout.strip()
    assert status == "Valid", f"Authenticode signature is not Valid: {status}"

    ps_subject_cmd = f"(Get-AuthenticodeSignature -FilePath '{EXE_PATH}').SignerCertificate.Subject"
    res_subject = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_subject_cmd],
        capture_output=True,
        text=True,
        check=True
    )
    subject = res_subject.stdout.strip()
    assert "Dan Joseph Ortega" in subject, f"Signer subject does not contain Dan Joseph Ortega: {subject}"


def test_packaged_executable_launch_and_cleanup():
    """
    Spawns CvSU Gen.exe in an isolated process group, verifies that it initializes
    without crashing within a 2-second startup stability window, and guarantees clean process tree termination.
    """
    assert os.path.exists(EXE_PATH), f"Compiled binary not found at {EXE_PATH}"

    # Pre-check: Ensure no lingering instance is running to prevent cross-test pollution
    subprocess.run(["taskkill", "/F", "/IM", "CvSU Gen.exe"], capture_output=True, check=False)
    time.sleep(0.5)

    # Launch isolated process in a new process group
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen([EXE_PATH], creationflags=creationflags)

    try:
        # Startup stability window (2.0 seconds)
        time.sleep(2.0)
        exit_code = proc.poll()
        assert exit_code is None, f"CvSU Gen.exe terminated prematurely with exit code {exit_code}"

    finally:
        # Guaranteed cleanup: kill entire process tree including PyInstaller children
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
        try:
            proc.wait(timeout=3)
        except Exception:
            pass

        # Verify PID is completely gone
        verify_gone = subprocess.run(
            ["tasklist", "/FI", f"PID eq {proc.pid}"],
            capture_output=True,
            text=True,
            check=False
        )
        assert str(proc.pid) not in verify_gone.stdout, f"Process PID {proc.pid} was not properly cleaned up"
