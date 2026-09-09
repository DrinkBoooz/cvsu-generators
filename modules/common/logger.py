import os
import sys
import logging
from logging.handlers import RotatingFileHandler

def _get_live_logger():
    app_data = os.getenv('APPDATA') or os.path.expanduser("~")
    log_dir = os.path.join(app_data, "CVSU_Generators", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "generator.log")
    
    live_logger = logging.getLogger("cvsu_generators")
    if not live_logger.handlers:
        live_logger.setLevel(logging.DEBUG)
        handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        live_logger.addHandler(handler)
    return live_logger

class IsolatedLogger:
    """Delegates logging to live logger in production, and to a null logger under test runners."""
    def _target(self):
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
