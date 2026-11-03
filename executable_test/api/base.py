import os
import sys
import re
import importlib

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
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)

class BaseAPI:
    """Base API containing shared state, locks, and thread synchronization primitives."""
    def __init__(self):
        import threading
        if getattr(sys, 'frozen', False):
            self.base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self._window = None
        self.schedule_path = ""
        self.output_dir = ""
        self.rosters = []
        self.roster_configs = {}
        self._is_processing = False
        self._is_window_closed = False
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._generation_progress = {
            "status": "idle",
            "current_index": 0,
            "total_count": 0,
            "percent": 0,
            "current_file_label": "",
            "current_class": "",
            "error": None,
        }

    def _get_gen_module(self, name: str):
        """
        Dynamically retrieve generator module. In frozen mode, uses standard static
        importlib.import_module to allow PyInstaller PYZ resolution without raw disk loading.
        In development mode, falls back to importlib.util.spec_from_file_location for hot-reloading.
        """
        if getattr(sys, 'frozen', False):
            try:
                return importlib.import_module(name)
            except ImportError:
                return importlib.import_module(f"modules.generators.{name}")
        else:
            import importlib.util
            potential_paths = [
                os.path.join(self.base_dir, "modules", "generators", f"{name}.py"),
                os.path.join(self.base_dir, f"{name}.py"),
            ]
            for p in potential_paths:
                if os.path.exists(p):
                    spec = importlib.util.spec_from_file_location(name, p)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[name] = mod
                        spec.loader.exec_module(mod)
                        return mod
            try:
                return importlib.import_module(name)
            except ImportError:
                return importlib.import_module(f"modules.generators.{name}")
