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

    def reveal_in_explorer(self, file_path: str):
        """
        Reveal a file or folder in Windows Explorer without invoking subprocess.Popen.
        Uses native Shell32 API (SHParseDisplayName and SHOpenFolderAndSelectItems) on Windows,
        falling back gracefully to os.startfile(parent_dir).
        """
        if not file_path:
            return {"status": "error", "message": "No file path provided"}

        norm_path = strip_long_path_prefix(os.path.normpath(file_path))
        if not os.path.exists(norm_path):
            return {"status": "error", "message": "Path does not exist"}

        if os.name == 'nt':
            try:
                import ctypes
                from ctypes import wintypes

                shell32 = ctypes.windll.shell32
                ole32 = ctypes.windll.ole32

                # Initialize COM for the calling thread
                ole32.CoInitialize(None)

                pidl = wintypes.LPVOID()
                sfgao = wintypes.DWORD()
                hr = shell32.SHParseDisplayName(
                    ctypes.c_wchar_p(norm_path),
                    None,
                    ctypes.byref(pidl),
                    0,
                    ctypes.byref(sfgao)
                )

                if hr == 0 and pidl.value:
                    try:
                        hr_select = shell32.SHOpenFolderAndSelectItems(pidl, 0, None, 0)
                        if hr_select == 0:
                            return {"status": "success"}
                    finally:
                        ole32.CoTaskMemFree(pidl)

                # Fallback if selection failed: open parent folder
                parent_dir = os.path.dirname(norm_path) if os.path.isfile(norm_path) else norm_path
                os.startfile(parent_dir)
                return {"status": "success"}
            except Exception:
                try:
                    parent_dir = os.path.dirname(norm_path) if os.path.isfile(norm_path) else norm_path
                    os.startfile(parent_dir)
                    return {"status": "success"}
                except Exception as e:
                    return {"status": "error", "message": str(e)}
        else:
            parent_dir = os.path.dirname(norm_path) if os.path.isfile(norm_path) else norm_path
            try:
                os.startfile(parent_dir)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

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
