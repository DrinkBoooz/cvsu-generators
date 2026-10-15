from .ceit_directory import CEIT_PREFIX_MAP, SUBJECT_PREFIXES, get_prefix_metadata, parse_filename_hints
from .roster_parser import inspect_roster, load_students, load_students_excel, load_students_csv, compute_roster_diff
from .schedule_parser import (
    find_schedule_file, parse_schedule, find_blocks_for_section,
    inspect_schedule_file, _find_class_details_by_schedule_code,
    _find_candidate_classes_from_hints, get_day_name, get_subject_code,
    normalize_room, format_canonical_schedule
)
from .template_inspector import (
    TemplateInspector,
    DocxTemplateInspector,
    XlsxTemplateInspector,
    AttendanceTemplateInspector,
)
from .recipe_validator import RecipeValidator
from .template_role_detector import TemplateRoleDetector, DetectionResult
from .docx_grid_table import DocxGridTable, DocxGridCell
from .template_analyzer import (
    DeterministicTemplateAnalyzer,
    TemplateManifest,
    SemanticSlot,
    RepeatingTableTopology,
)
from .smart_ingest import SmartIngestClassifier

__all__ = [
    "SmartIngestClassifier",
    "compute_roster_diff",
    "CEIT_PREFIX_MAP",
    "SUBJECT_PREFIXES",
    "get_prefix_metadata",
    "parse_filename_hints",
    "inspect_roster",
    "load_students",
    "load_students_excel",
    "load_students_csv",
    "find_schedule_file",
    "parse_schedule",
    "find_blocks_for_section",
    "normalize_room",
    "format_canonical_schedule",
    "inspect_schedule_file",
    "_find_class_details_by_schedule_code",
    "_find_candidate_classes_from_hints",
    "get_day_name",
    "get_subject_code",
    "TemplateInspector",
    "DocxTemplateInspector",
    "XlsxTemplateInspector",
    "AttendanceTemplateInspector",
    "RecipeValidator",
    "TemplateRoleDetector",
    "DetectionResult",
    "DocxGridTable",
    "DocxGridCell",
    "DeterministicTemplateAnalyzer",
    "TemplateManifest",
    "SemanticSlot",
    "RepeatingTableTopology",
]

