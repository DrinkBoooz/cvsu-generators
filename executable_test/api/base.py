import os
import sys
import re

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and invalid OS characters."""
    if not filename:
        return "unnamed_file"
    base = os.path.basename(filename)
    clean = re.sub(r'[\r\n\t\\/:*?"<>|]', '_', base).strip().strip('.')
    return clean or "unnamed_file"

def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Resolve to directory of the main executable entrypoint
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)

class BaseAPI:
    """Base API containing shared state, locks, and thread synchronization primitives."""
    def __init__(self):
        import threading
        self._window = None
        self.schedule_path = ""
        self.output_dir = ""
        self.rosters = []
        self.roster_configs = {}
        self._is_processing = False
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
