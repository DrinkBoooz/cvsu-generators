import os
import re
import time
import tempfile
import shutil
import uuid
import openpyxl.utils

def safe_get_column_letter(col_idx: int, zero_based: bool = False) -> str:
    """
    Returns the Excel column letter for a 1-based (default) or 0-based column index.
    Accurately handles all column counts (A..Z, AA..ZZ, AAA..ZZZ) via openpyxl.
    """
    if zero_based:
        idx = col_idx + 1
    else:
        idx = col_idx
    idx = max(1, int(idx))
    try:
        return openpyxl.utils.get_column_letter(idx)
    except Exception:
        return openpyxl.utils.get_column_letter(1)

def safe_temp_copy(file_path: str, retries: int = 3, delay: float = 0.3) -> str:
    """
    Creates a temporary copy of a spreadsheet in the OS temp directory
    to prevent file locks, permission errors on read-only drives, and folder clutter.

    Retries up to `retries` times with `delay`-second backoff on PermissionError
    (e.g., the source is held open by OneDrive sync, an antivirus scanner, or Excel).
    Raises PermissionError with a user-actionable message if the file cannot be
    copied after all retries.
    """
    ext = os.path.splitext(file_path)[1]
    temp_dir = tempfile.gettempdir()
    unique_name = f"cvsu_sched_{uuid.uuid4().hex[:8]}{ext}"
    temp_path = os.path.join(temp_dir, unique_name)
    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            shutil.copy2(file_path, temp_path)
            return temp_path
        except PermissionError as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(delay)
    raise PermissionError(
        f"Cannot read '{os.path.basename(file_path)}' — it may be open in Excel, "
        f"OneDrive, or another application. Please close it and try again. "
        f"({last_exc})"
    ) from last_exc

def parse_excel_time(t_str, is_pm_hint=None) -> str:
    """
    Parses a time string, datetime.time, or Excel decimal float serial into standard 'HH:MM AM/PM'.
    """
    t_str = str(t_str).strip()
    if not t_str:
        return "SEE SCHEDULE"
    
    try:
        if ':' not in t_str:
            val = float(t_str)
            if 0 <= val < 1:
                total_minutes = round(val * 24 * 60)
                h = total_minutes // 60
                m = total_minutes % 60
            else:
                return "SEE SCHEDULE"
        else:
            t_str_clean = t_str.upper().replace('AM', '').replace('PM', '').strip()
            h, m = map(int, t_str_clean.split(':'))
    except ValueError:
        return "SEE SCHEDULE"
        
    has_pm_suffix = 'PM' in t_str.upper()
    has_am_suffix = 'AM' in t_str.upper()
    
    if has_pm_suffix:
        is_pm = True
    elif has_am_suffix:
        is_pm = False
    elif (1 <= h <= 6) or h >= 12:
        is_pm = True
    elif is_pm_hint is not None:
        is_pm = bool(is_pm_hint)
    else:
        is_pm = False
        
    h12 = h % 12
    if h12 == 0:
        h12 = 12
        
    ampm = "PM" if is_pm else "AM"
    return f"{h12:02d}:{m:02d}{ampm}"

def get_long_path(p: str) -> str:
    if not p:
        return p
    p = os.path.abspath(p)
    if os.name == 'nt' and not p.startswith('\\\\?\\'):
        return '\\\\?\\' + p
    return p


def strip_long_path_prefix(p: str) -> str:
    """
    Strips the Windows extended-length path prefix (\\?\\) before passing
    a path to shell operations such as os.startfile() / ShellExecuteW.

    This must ONLY be used at the shell boundary — never on paths passed to
    Python's own filesystem APIs, which accept the \\?\\ prefix.

    Handles:
      * Normal paths (returned unchanged)
      * \\?\\C:\\... local extended-length paths
      * \\?\\UNC\\server\\share... UNC long paths → \\\\server\\share
      * Already-normal paths (idempotent)
    """
    if not p:
        return p
    if p.startswith('\\\\?\\UNC\\'):
        # \\?\UNC\server\share → \\server\share
        return '\\\\' + p[8:]
    if p.startswith('\\\\?\\'):
        return p[4:]
    return p

def sanitize_filename(name: str) -> str:
    """Remove illegal characters for Windows/Linux file paths and prevent directory traversal."""
    if not name:
        return "Unknown"
    name = str(name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\.{2,}', '_', name).strip()
    name = name.strip('. ')
    if not name:
        return "Unknown"
        
    base = name.split('.')[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if base in reserved:
        name = name + "_"
        
    return name
