#!/usr/bin/env python3
"""
Transparent repository entrypoint for the authoritative test orchestration system.
Invokes scripts/test_orchestrator.py with all forwarded arguments.
"""

import sys
import subprocess
from pathlib import Path

ORCHESTRATOR_PATH = Path(__file__).resolve().parent / "test_orchestrator.py"

if __name__ == "__main__":
    cmd = [sys.executable, str(ORCHESTRATOR_PATH)] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
