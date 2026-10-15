"""
CvSU Generators — Centralised Logging Infrastructure.

Provides:
  * IsolatedLogger  — thin wrapper that delegates to the named logger in
                      production and to a NullHandler logger under pytest.
  * install_global_hooks()
                    — installs sys.excepthook / threading.excepthook /
                      sys.unraisablehook and attaches file handlers to both
                      the 'cvsu_generators' logger and the 'pywebview' logger.
                      Safe to call multiple times (idempotent via module guard).

Log destinations (production only):
  generator.log — all application log records (DEBUG and above)
  crash.log     — only CRITICAL/unhandled-exception records (immediate flush)
"""

import os
import sys
import atexit
import logging
import threading
import traceback
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Module-level guard so install_global_hooks() never installs handlers twice
# even if this module is imported from multiple package paths.
# ---------------------------------------------------------------------------
_hooks_installed = False
_install_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_log_dir() -> str:
    app_data = os.getenv("APPDATA") or os.path.expanduser("~")
    log_dir = os.path.join(app_data, "CVSU_Generators", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _make_rotating_handler(log_path: str,
                            max_bytes: int = 5 * 1024 * 1024,
                            backup_count: int = 3) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    return handler


def _flush_all_handlers() -> None:
    """atexit callback — flush every handler attached to both named loggers."""
    for name in ("cvsu_generators", "pywebview"):
        lg = logging.getLogger(name)
        for h in lg.handlers:
            try:
                h.flush()
            except Exception:
                pass


def _build_crash_record(exc_type, exc_value, exc_tb, *, thread_name: str = "") -> str:
    """Build a rich crash record string for crash.log and generator.log."""
    try:
        import platform
        try:
            import webview  # pywebview
            pv_version = getattr(webview, "__version__", "unknown")
        except Exception:
            pv_version = "not-imported"

        tb_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        frozen = "frozen" if getattr(sys, "frozen", False) else "source"
        record_parts = [
            f"{'='*72}",
            f"UNHANDLED EXCEPTION",
            f"{'='*72}",
            f"Thread      : {thread_name or threading.current_thread().name}",
            f"Thread ID   : {threading.current_thread().ident}",
            f"Process ID  : {os.getpid()}",
            f"Python      : {sys.version}",
            f"pywebview   : {pv_version}",
            f"Build mode  : {frozen}",
            f"Platform    : {platform.platform()}",
            f"Exception   : {exc_type.__name__ if exc_type else 'unknown'}",
            f"Message     : {exc_value}",
            f"{'─'*72}",
            tb_lines.rstrip(),
            f"{'='*72}",
        ]
        return "\n".join(record_parts)
    except Exception as meta_err:
        # The crash record builder itself must never crash the hook.
        return f"UNHANDLED EXCEPTION (meta-error building record: {meta_err})\n{exc_type}: {exc_value}"

# ---------------------------------------------------------------------------
# Primary logger setup
# ---------------------------------------------------------------------------

def _get_live_logger() -> logging.Logger:
    """
    Returns the 'cvsu_generators' logger with a RotatingFileHandler attached.
    Called lazily so that the log directory is not created under pytest.
    """
    live_logger = logging.getLogger("cvsu_generators")
    if not live_logger.handlers:
        live_logger.setLevel(logging.DEBUG)
        log_dir = _get_log_dir()
        handler = _make_rotating_handler(os.path.join(log_dir, "generator.log"))
        handler.setLevel(logging.DEBUG)
        live_logger.addHandler(handler)
        live_logger.propagate = False  # Do NOT propagate to root — avoids duplication
    return live_logger

# ---------------------------------------------------------------------------
# Public API: install global exception hooks
# ---------------------------------------------------------------------------

def install_global_hooks() -> None:
    """
    Install sys.excepthook, threading.excepthook, sys.unraisablehook, and
    attach file handlers to 'cvsu_generators' and 'pywebview' loggers.

    Safe to call multiple times — subsequent calls are no-ops.
    Must be called as early as possible in main.py before any other import
    that might raise.

    Does NOT install a handler on the root logger to avoid duplicating records.
    """
    global _hooks_installed
    with _install_lock:
        if _hooks_installed:
            return
        _hooks_installed = True

    # ------------------------------------------------------------------ #
    # 1. Ensure both named loggers have file handlers                      #
    # ------------------------------------------------------------------ #
    try:
        log_dir = _get_log_dir()
        gen_log = os.path.join(log_dir, "generator.log")
        crash_log = os.path.join(log_dir, "crash.log")

        # cvsu_generators logger (primary application log)
        app_logger = logging.getLogger("cvsu_generators")
        if not app_logger.handlers:
            app_logger.setLevel(logging.DEBUG)
            app_handler = _make_rotating_handler(gen_log)
            app_handler.setLevel(logging.DEBUG)
            app_logger.addHandler(app_handler)
            app_logger.propagate = False

        # pywebview logger (routed to same file — no duplication because
        # pywebview is a separate named logger tree)
        pv_logger = logging.getLogger("pywebview")
        if not pv_logger.handlers:
            pv_logger.setLevel(logging.DEBUG)
            pv_handler = _make_rotating_handler(gen_log)
            pv_handler.setLevel(logging.DEBUG)
            pv_logger.addHandler(pv_handler)
            pv_logger.propagate = False

        # Dedicated crash log handler (critical only, immediate flush)
        crash_handler = _make_rotating_handler(crash_log, max_bytes=2 * 1024 * 1024, backup_count=5)
        crash_handler.setLevel(logging.CRITICAL)

        # Attach crash handler to cvsu_generators (it writes only CRITICAL records)
        if not any(getattr(h, "_is_crash_handler", False) for h in app_logger.handlers):
            crash_handler._is_crash_handler = True  # type: ignore[attr-defined]
            app_logger.addHandler(crash_handler)

    except Exception:
        # If we can't even open the log files, there is nothing we can do.
        pass

    # ------------------------------------------------------------------ #
    # 2. sys.excepthook — main-thread unhandled exceptions                 #
    # ------------------------------------------------------------------ #
    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            record = _build_crash_record(exc_type, exc_value, exc_tb)
            lg = logging.getLogger("cvsu_generators")
            lg.critical(record)
            for h in lg.handlers:
                try:
                    h.flush()
                except Exception:
                    pass
        except Exception:
            pass
        # Always call the original hook so the process exits normally
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    # ------------------------------------------------------------------ #
    # 3. threading.excepthook — worker-thread unhandled exceptions         #
    # ------------------------------------------------------------------ #
    def _threading_excepthook(args):
        try:
            name = getattr(args.thread, "name", "<unknown thread>")
            record = _build_crash_record(
                args.exc_type, args.exc_value, args.exc_traceback,
                thread_name=name
            )
            lg = logging.getLogger("cvsu_generators")
            lg.critical(record)
            for h in lg.handlers:
                try:
                    h.flush()
                except Exception:
                    pass
        except Exception:
            pass

    threading.excepthook = _threading_excepthook

    # ------------------------------------------------------------------ #
    # 4. sys.unraisablehook — finalizer/GC exceptions                     #
    # ------------------------------------------------------------------ #
    def _unraisablehook(unraisable):
        try:
            lg = logging.getLogger("cvsu_generators")
            msg = (
                f"Unraisable exception in {unraisable.object!r}: "
                f"{unraisable.exc_type.__name__}: {unraisable.exc_value}"
            )
            if unraisable.exc_traceback:
                tb_str = "".join(traceback.format_tb(unraisable.exc_traceback))
                msg = msg + "\n" + tb_str
            lg.critical(msg)
            for h in lg.handlers:
                try:
                    h.flush()
                except Exception:
                    pass
        except Exception:
            pass

    sys.unraisablehook = _unraisablehook

    # ------------------------------------------------------------------ #
    # 5. atexit flush — normal-exit safeguard (not primary crash mechanism)#
    # ------------------------------------------------------------------ #
    atexit.register(_flush_all_handlers)


# ---------------------------------------------------------------------------
# IsolatedLogger — unchanged public API, delegates to named loggers
# ---------------------------------------------------------------------------

class IsolatedLogger:
    """Delegates logging to live logger in production, and to a null logger under test runners."""
    def _target(self) -> logging.Logger:
        if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
            test_logger = logging.getLogger("cvsu_generators_test")
            if not test_logger.handlers:
                test_logger.setLevel(logging.DEBUG)
                test_logger.addHandler(logging.NullHandler())
            return test_logger
        return _get_live_logger()

    def info(self, msg, *args, **kwargs):
        self._target().info(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._target().error(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._target().warning(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self._target().debug(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._target().exception(msg, *args, **kwargs)


logger = IsolatedLogger()
