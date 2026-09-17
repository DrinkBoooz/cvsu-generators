#!/usr/bin/env python3
"""
modules/common/path_utils.py

Safe path validation and normalization utilities for CVSU Document Generator.
Ensures custom template output folders remain strictly sandboxed inside target class directories.
"""

import os
import re
from typing import Optional

# Windows reserved device names (case-insensitive)
RESERVED_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Invalid characters in Windows directory/file names
INVALID_PATH_CHARS = set('<>:"|?*')


def validate_output_folder(folder: Optional[str], default: str = "CEIT_Forms") -> str:
    """
    Validates and normalizes an output subfolder for custom document templates.
    Must be a strictly relative path intended to live inside <Course_Sec>/.

    Rejects:
      - Absolute paths (starts with / or \\)
      - Drive-qualified paths (e.g. C:, D:)
      - Directory traversal ('..' or '.')
      - Reserved Windows device names (CON, NUL, AUX, PRN, COM1-9, LPT1-9)
      - Segments ending in spaces or dots
      - Invalid characters (<, >, :, ", |, ?, *)

    Returns:
      Normalized relative subfolder string (e.g. 'CEIT_Forms', 'Attendance', 'Custom/Sub').
    """
    if folder is None:
        return default
    if not isinstance(folder, str):
        raise TypeError(f"output_folder must be a string, got {type(folder).__name__}")

    if not folder.strip():
        return default

    # Normalize slashes to forward slashes for segment parsing
    norm_slash = folder.replace("\\", "/")

    # Reject drive-qualified paths (e.g. C:, D:, C:/foo)
    if os.path.splitdrive(norm_slash)[0] or (len(norm_slash) >= 2 and norm_slash[1] == ":"):
        raise ValueError(f"Drive-qualified paths are prohibited: {folder!r}")

    # Reject absolute paths starting with /
    if norm_slash.startswith("/"):
        raise ValueError(f"Absolute paths are prohibited: {folder!r}")

    segments = norm_slash.split("/")
    clean_segments = []

    for raw_seg in segments:
        if not raw_seg or not raw_seg.strip():
            raise ValueError(f"Empty or whitespace path segment in {folder!r}")
        if raw_seg in ("..", "."):
            raise ValueError(f"Path traversal ('..' or '.') is prohibited: {folder!r}")
        if raw_seg.endswith(".") or raw_seg.endswith(" "):
            raise ValueError(f"Path segment cannot end with a dot or space: {raw_seg!r}")
        if raw_seg.startswith(" "):
            raise ValueError(f"Path segment cannot start with a space: {raw_seg!r}")

        if any(c in INVALID_PATH_CHARS for c in raw_seg):
            raise ValueError(f"Invalid path characters in segment {raw_seg!r}: {folder!r}")

        # Check for reserved Windows device names (CON, NUL, etc.)
        base_seg = os.path.splitext(raw_seg)[0].upper()
        if base_seg in RESERVED_DEVICE_NAMES:
            raise ValueError(f"Reserved Windows device name prohibited in segment {raw_seg!r}: {folder!r}")

        clean_segments.append(raw_seg)

    # Normalize relative path using os.path.normpath
    safe_rel = os.path.normpath(os.path.join(*clean_segments))

    # Guard against normalized path escaping
    if safe_rel == "." or safe_rel.startswith("..") or os.path.isabs(safe_rel):
        raise ValueError(f"Path escapes course directory: {folder!r}")

    return safe_rel
