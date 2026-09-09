#!/usr/bin/env python3
"""
CvSU CEIT Document Generator Facade
Re-exports from modules.generators.ceit_gen and related modules for 100% backward compatibility.
"""

from modules.models.schedule import ClassInfo
from modules.common.docx_utils import (
    W,
    w,
    wt,
    get_full_text,
    auto_scale_font,
    _auto_scale_font,
    set_run_text,
    replace_after_colon,
    replace_value_run,
    collapse_runs_after_colon,
    set_cell_text,
    load_docx,
    save_docx,
)
from modules.generators.ceit_gen import (
    TemplateError,
    DocumentGenerator,
    SyllabusGenerator,
    ExamReturnsGenerator,
    TOSGenerator,
    GradeDiscussionGenerator,
    GeneratorFactory,
    prompt,
    prompt_choice,
    _build_preset_map,
    parse_class_payload,
    read_class_payload,
    collect_class_info,
    main,
)
from modules.parsers.roster_parser import (
    load_students,
    load_students_excel,
    load_students_csv,
    _fix_encoding,
    _is_id_header,
    _is_name_header,
    _detect_roster_columns,
)

__all__ = [
    "TemplateError",
    "ClassInfo",
    "W",
    "w",
    "wt",
    "get_full_text",
    "auto_scale_font",
    "_auto_scale_font",
    "set_run_text",
    "replace_after_colon",
    "replace_value_run",
    "collapse_runs_after_colon",
    "set_cell_text",
    "load_docx",
    "save_docx",
    "DocumentGenerator",
    "SyllabusGenerator",
    "ExamReturnsGenerator",
    "TOSGenerator",
    "GradeDiscussionGenerator",
    "GeneratorFactory",
    "prompt",
    "prompt_choice",
    "_build_preset_map",
    "parse_class_payload",
    "read_class_payload",
    "collect_class_info",
    "main",
    "load_students",
    "load_students_excel",
    "load_students_csv",
    "_fix_encoding",
    "_is_id_header",
    "_is_name_header",
    "_detect_roster_columns",
]

if __name__ == "__main__":
    main()
