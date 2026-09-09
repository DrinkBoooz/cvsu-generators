"""
Unified Roster Parser Facade for CvSU Document Generators
Re-exports from modules.parsers.roster_parser and modules.parsers.ceit_directory
for 100% backward compatibility with all scripts and test suites.
"""

from modules.parsers.ceit_directory import (
    CEIT_PREFIX_MAP,
    BASE_SUBJECT_PREFIXES,
    SUBJECT_PREFIXES,
    get_prefix_metadata,
    parse_filename_hints,
)

from modules.parsers.roster_parser import (
    normalize_name,
    sanitize_name,
    sanitize_stnum,
    _fix_encoding,
    _is_id_header,
    _is_name_header,
    _detect_roster_columns,
    load_students_excel,
    load_students_csv,
    load_students,
    inspect_roster,
)

__all__ = [
    "CEIT_PREFIX_MAP",
    "BASE_SUBJECT_PREFIXES",
    "SUBJECT_PREFIXES",
    "get_prefix_metadata",
    "parse_filename_hints",
    "normalize_name",
    "sanitize_name",
    "sanitize_stnum",
    "_fix_encoding",
    "_is_id_header",
    "_is_name_header",
    "_detect_roster_columns",
    "load_students_excel",
    "load_students_csv",
    "load_students",
    "inspect_roster",
]
