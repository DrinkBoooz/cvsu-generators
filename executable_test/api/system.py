import os
import webview
from modules.common.excel_utils import strip_long_path_prefix

class SystemMixin:
    """Mixin handling native filesystem browsing, shell execution, and logging."""

    def browse_output(self):
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG
        )
        if result and len(result) > 0:
            self.output_dir = result[0]
        return self.output_dir

    def open_output_folder(self, folder_path=None):
        target = folder_path or self.output_dir
        if target:
            # Part G: normalise first, then strip \\?\ prefix at the shell boundary.
            # get_long_path() is used internally for filesystem ops but ShellExecuteW
            # does not accept the \\?\ prefix.
            norm_target = strip_long_path_prefix(os.path.normpath(target))
            if os.path.exists(norm_target):
                try:
                    os.startfile(norm_target)
                    return {"status": "success"}
                except Exception as e:
                    return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Directory does not exist"}

    def open_file(self, file_path):
        if file_path:
            # Part G: strip \\?\ before passing to ShellExecuteW
            norm_path = strip_long_path_prefix(os.path.normpath(file_path))
            if os.path.exists(norm_path):
                try:
                    os.startfile(norm_path)
                    return {"status": "success"}
                except Exception as e:
                    return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "File not found"}

    def get_recent_logs(self, lines=120):
        app_data = os.getenv('APPDATA') or os.path.expanduser("~")
        log_file = os.path.join(app_data, "CVSU_Generators", "logs", "generator.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()
                    return "".join(all_lines[-lines:])
            except Exception as e:
                return f"Could not read log file: {e}"
        return "No log entries found."

    def open_log_folder(self):
        app_data = os.getenv('APPDATA') or os.path.expanduser("~")
        log_dir = strip_long_path_prefix(os.path.normpath(os.path.join(app_data, "CVSU_Generators", "logs")))
        if os.path.exists(log_dir):
            try:
                os.startfile(log_dir)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Logs directory does not exist"}
