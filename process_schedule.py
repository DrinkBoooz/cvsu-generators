#!/usr/bin/env python3
"""
CvSU Schedule Processor Facade
Re-exports from modules.parsers, modules.services, and modules.common for 100% backward compatibility.
"""

from modules.common.logger import logger, IsolatedLogger
from modules.common.excel_utils import (
    get_long_path,
    sanitize_filename,
    parse_excel_time,
)
from modules.parsers.ceit_directory import (
    BASE_SUBJECT_PREFIXES,
    SUBJECT_PREFIXES,
)
from modules.parsers.schedule_parser import (
    get_day_name,
    get_subject_code,
    format_time,
    find_schedule_file,
    parse_schedule,
    find_blocks_for_section,
    inspect_schedule_file,
    _find_class_details_by_schedule_code,
)
from modules.services.validator import (
    validate_rosters,
    detect_classes,
)
from modules.services.orchestrator import (
    process_all,
)

# For backward compatibility with any direct module references
import ceit_generator
import attendancegen
import roster_parser
from grade_generator import GradeGenerator
from ceit_generator import GeneratorFactory

__all__ = [
    "logger",
    "IsolatedLogger",
    "get_long_path",
    "sanitize_filename",
    "parse_excel_time",
    "BASE_SUBJECT_PREFIXES",
    "SUBJECT_PREFIXES",
    "get_day_name",
    "get_subject_code",
    "format_time",
    "find_schedule_file",
    "parse_schedule",
    "find_blocks_for_section",
    "inspect_schedule_file",
    "_find_class_details_by_schedule_code",
    "validate_rosters",
    "detect_classes",
    "process_all",
    "GradeGenerator",
    "GeneratorFactory",
]

if __name__ == "__main__":
    pass
