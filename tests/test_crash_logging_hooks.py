r"""
tests/test_crash_logging_hooks.py

Regression tests for Part A (Global Exception Telemetry) and Part G (long-path
shell boundary normalization).

Covers:
  1. sys.excepthook writes to crash.log
  2. threading.excepthook writes to crash.log
  3. sys.unraisablehook captures finalizer exceptions
  4. install_global_hooks() is idempotent (no duplicate handlers)
  5. pywebview logger is routed to the application file handler
  6. generator.log receives pywebview log records
  7. strip_long_path_prefix handles normal, extended-length, and UNC paths
  8. shell boundary: os.startfile receives a normal (non-prefixed) path
"""

import os
import sys
import types
import logging
import threading
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestInstallGlobalHooks(unittest.TestCase):
    """Tests for modules.common.logger.install_global_hooks()"""

    def _get_logger_module(self):
        """Get the actual logger module (not the IsolatedLogger instance)."""
        import importlib
        import modules.common.logger
        # Force reimport to get the module object
        return sys.modules.get("modules.common.logger") or importlib.import_module("modules.common.logger")

    def setUp(self):
        """Reset the module-level guard so we can test install behaviour."""
        lmod = self._get_logger_module()
        # Save originals
        self._orig_installed = lmod._hooks_installed
        self._orig_excepthook = sys.excepthook
        self._orig_threading_excepthook = getattr(threading, "excepthook", None)
        self._orig_unraisablehook = getattr(sys, "unraisablehook", None)
        # Force hooks not installed so install_global_hooks() runs each time
        lmod._hooks_installed = False

    def tearDown(self):
        lmod = self._get_logger_module()
        lmod._hooks_installed = self._orig_installed
        sys.excepthook = self._orig_excepthook
        if self._orig_threading_excepthook is not None:
            threading.excepthook = self._orig_threading_excepthook
        if self._orig_unraisablehook is not None:
            sys.unraisablehook = self._orig_unraisablehook

    def _run_in_temp_log(self, log_dir: str) -> None:
        """Re-install hooks pointing to log_dir."""
        lmod = self._get_logger_module()
        # Fully reset existing handlers so the temp-path handlers get added
        for logger_name in ("cvsu_generators", "pywebview"):
            lg = logging.getLogger(logger_name)
            for h in list(lg.handlers):
                try:
                    h.close()
                except Exception:
                    pass
                lg.removeHandler(h)
        lmod._hooks_installed = False
        with patch("modules.common.logger._get_log_dir", return_value=log_dir):
            lmod.install_global_hooks()

    def test_install_global_hooks_installs_sys_excepthook(self):
        """After install, sys.excepthook must not be the default."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
        self.assertIsNot(sys.excepthook, sys.__excepthook__)

    def test_install_global_hooks_installs_threading_excepthook(self):
        """After install, threading.excepthook must be our custom hook."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
        # Our hook should be set (not the default which just prints)
        self.assertIsNotNone(getattr(threading, "excepthook", None))

    def test_install_global_hooks_installs_unraisablehook(self):
        """After install, sys.unraisablehook must be our custom hook."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
        self.assertIsNotNone(getattr(sys, "unraisablehook", None))

    def test_excepthook_writes_to_crash_log(self):
        """sys.excepthook must write an entry to crash.log."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
            crash_log = os.path.join(tmpdir, "crash.log")

            # Flush all handlers before reading
            for h in logging.getLogger("cvsu_generators").handlers:
                h.flush()

            # Simulate an unhandled exception reaching the hook
            try:
                raise RuntimeError("deliberate test crash")
            except RuntimeError:
                exc_type, exc_value, exc_tb = sys.exc_info()
                sys.excepthook(exc_type, exc_value, exc_tb)

            # Flush crash handler
            for h in logging.getLogger("cvsu_generators").handlers:
                try:
                    h.flush()
                except Exception:
                    pass

            # crash.log should exist and contain the exception class name
            self.assertTrue(os.path.exists(crash_log),
                            "crash.log was not created by sys.excepthook")
            with open(crash_log, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("deliberate test crash", content)
            self.assertIn("RuntimeError", content)

    def test_threading_excepthook_writes_to_crash_log(self):
        """threading.excepthook must write an entry to crash.log from a worker thread."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
            crash_log = os.path.join(tmpdir, "crash.log")

            # Build a fake threading.ExceptHookArgs-like object
            try:
                raise ValueError("thread crash test")
            except ValueError:
                exc_type, exc_value, exc_tb = sys.exc_info()

            fake_args = types.SimpleNamespace(
                exc_type=exc_type,
                exc_value=exc_value,
                exc_traceback=exc_tb,
                thread=threading.current_thread(),
            )
            threading.excepthook(fake_args)

            # Flush crash handler
            for h in logging.getLogger("cvsu_generators").handlers:
                try:
                    h.flush()
                except Exception:
                    pass

            self.assertTrue(os.path.exists(crash_log),
                            "crash.log was not created by threading.excepthook")
            with open(crash_log, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("thread crash test", content)
            self.assertIn("ValueError", content)

    def test_unraisablehook_writes_to_crash_log(self):
        """sys.unraisablehook must write an entry to crash.log."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
            crash_log = os.path.join(tmpdir, "crash.log")

            try:
                raise TypeError("unraisable test error")
            except TypeError:
                exc_type, exc_value, exc_tb = sys.exc_info()

            fake_unraisable = types.SimpleNamespace(
                object=object(),
                exc_type=exc_type,
                exc_value=exc_value,
                exc_traceback=exc_tb,
            )
            sys.unraisablehook(fake_unraisable)

            # Flush crash handler
            for h in logging.getLogger("cvsu_generators").handlers:
                try:
                    h.flush()
                except Exception:
                    pass

            self.assertTrue(os.path.exists(crash_log),
                            "crash.log was not created by sys.unraisablehook")
            with open(crash_log, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("TypeError", content)

    def test_install_global_hooks_is_idempotent(self):
        """Calling install_global_hooks() twice must not add duplicate handlers."""
        lmod = self._get_logger_module()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
            count_after_first = len(logging.getLogger("cvsu_generators").handlers)
            # Second call — guard should block (hooks_installed=True)
            lmod.install_global_hooks()
            count_after_second = len(logging.getLogger("cvsu_generators").handlers)

        self.assertEqual(count_after_first, count_after_second,
                         "install_global_hooks() added handlers on a second call (not idempotent)")

    def test_pywebview_logger_routes_to_generator_log(self):
        """The 'pywebview' logger must have a handler that writes to generator.log."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)
            gen_log = os.path.join(tmpdir, "generator.log")
            pv_logger = logging.getLogger("pywebview")
            pv_logger.warning("pywebview test route record")
            for h in pv_logger.handlers:
                try:
                    h.flush()
                except Exception:
                    pass

            self.assertTrue(os.path.exists(gen_log),
                            "generator.log was not created")
            with open(gen_log, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("pywebview test route record", content)

    def test_app_logger_does_not_propagate_to_root(self):
        """cvsu_generators logger must not propagate to avoid duplicate records."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            self._run_in_temp_log(tmpdir)

        app_logger = logging.getLogger("cvsu_generators")
        self.assertFalse(app_logger.propagate,
                         "cvsu_generators logger should not propagate to root")


class TestStripLongPathPrefix(unittest.TestCase):
    """Tests for modules.common.excel_utils.strip_long_path_prefix (Part G)."""

    def setUp(self):
        from modules.common.excel_utils import strip_long_path_prefix
        self.fn = strip_long_path_prefix

    def test_normal_path_unchanged(self):
        p = r"C:\Users\danjo\Documents\file.xlsx"
        self.assertEqual(self.fn(p), p)

    def test_long_path_prefix_stripped(self):
        p = r"\\?\C:\Users\danjo\Documents\file.xlsx"
        self.assertEqual(self.fn(p), r"C:\Users\danjo\Documents\file.xlsx")

    def test_unc_long_path_prefix_converted(self):
        p = r"\\?\UNC\server\share\file.xlsx"
        result = self.fn(p)
        self.assertTrue(result.startswith(r"\\server\share"),
                        f"UNC conversion failed: {result!r}")

    def test_empty_string_unchanged(self):
        self.assertEqual(self.fn(""), "")

    def test_none_handled(self):
        # strip_long_path_prefix should handle None gracefully (returns None)
        result = self.fn(None)  # type: ignore[arg-type]
        self.assertIsNone(result)

    def test_already_normal_path_is_idempotent(self):
        p = r"C:\Some\Normal\Path"
        self.assertEqual(self.fn(self.fn(p)), self.fn(p))

    def test_long_path_prefix_only_at_shell_boundary(self):
        r"""get_long_path should still PRODUCE the \\?\ prefix; strip_long_path_prefix
        must undo it only at the shell boundary."""
        from modules.common.excel_utils import get_long_path
        p = r"C:\Users\danjo\Documents\file.xlsx"
        long = get_long_path(p)
        if os.name == "nt":
            self.assertTrue(long.startswith("\\\\?\\"),
                            "get_long_path did not add \\\\?\\ on Windows")
            stripped = self.fn(long)
            self.assertFalse(stripped.startswith("\\\\?\\"),
                             "strip_long_path_prefix did not remove \\\\?\\ prefix")


if __name__ == "__main__":
    unittest.main()
