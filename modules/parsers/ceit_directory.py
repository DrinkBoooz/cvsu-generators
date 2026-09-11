import os
import re
from modules.common.config_manager import config_manager

# Official Subject Prefix & Department Directory (Backed by ParserConfigManager)
CEIT_PREFIX_MAP = config_manager.get_ceit_prefix_map()
BASE_SUBJECT_PREFIXES = tuple(config_manager.get_config().get("base_subject_prefixes", []))
SUBJECT_PREFIXES = config_manager.get_subject_prefixes()
KNOWN_LAB_SUBJECT_CODES = config_manager.get_known_lab_subjects()
NORMALIZED_LAB_SUBJECT_CODES = config_manager.get_normalized_lab_subjects()

def _sync_globals(new_cfg=None):
    """Synchronize module-level constants when configuration is updated."""
    global CEIT_PREFIX_MAP, BASE_SUBJECT_PREFIXES, SUBJECT_PREFIXES
    global KNOWN_LAB_SUBJECT_CODES, NORMALIZED_LAB_SUBJECT_CODES
    CEIT_PREFIX_MAP = config_manager.get_ceit_prefix_map()
    BASE_SUBJECT_PREFIXES = tuple(config_manager.get_config().get("base_subject_prefixes", []))
    SUBJECT_PREFIXES = config_manager.get_subject_prefixes()
    KNOWN_LAB_SUBJECT_CODES = config_manager.get_known_lab_subjects()
    NORMALIZED_LAB_SUBJECT_CODES = config_manager.get_normalized_lab_subjects()

config_manager.register_listener(_sync_globals)


def get_prefix_metadata(text: str) -> dict:
    """Extract recognized subject prefix from text/filename and return department metadata."""
    return config_manager.get_prefix_metadata(text)


def parse_filename_hints(filename: str) -> dict:
    """
    Intelligently extracts whatever partial class details can be inferred from a non-standard
    or incomplete roster filename (e.g. 'CS1-4 DCIT21.xlsx' or 'BSCS 3-1 COSC 70.csv').
    Identifies detected fields, missing fields, and forms an official recommended filename.
    """
    if not filename:
        return {
            "course_sec": "",
            "schedule_code": "",
            "subject_prefix": "",
            "subject_code": "",
            "subject_name": "",
            "missing": ["course_sec", "schedule_code", "subject_name"],
            "recommended_filename": "CourseSec List of Students for ScheduleCode-Subject.xlsx",
            "ceit_metadata": None
        }

    base = os.path.splitext(os.path.basename(filename))[0]
    cleaned = base.replace("_", " ").strip()

    # 1. Look for Schedule Code (digits of length 8-9)
    sched_m = re.search(r'\b(20\d{6,7}|\d{8,9})\b', cleaned)
    schedule_code = sched_m.group(1) if sched_m else ""

    # 2. Look for Section pattern (e.g. BSCS 1-4, CS1-4, IT 3-2, CpE 4-1, 1-4)
    course_sec = ""
    sec_m = re.search(r'\b(?:BS)?([A-Za-z]{2,4})\s*(\d)-(\d+)\b', cleaned, re.IGNORECASE)
    if sec_m:
        prog = sec_m.group(1).upper()
        aliases = config_manager.get_program_aliases()
        if prog in aliases:
            prog = aliases[prog]
        elif not prog.startswith("BS") and len(prog) <= 3:
            prog = f"BS{prog}"
        course_sec = f"{prog} {sec_m.group(2)}-{sec_m.group(3)}"
    else:
        gen_m = re.search(r'\b(\d)-(\d+)\b', cleaned)
        if gen_m:
            course_sec = f"{gen_m.group(1)}-{gen_m.group(2)}"

    # 3. Look for Subject Prefix & Course Number (e.g. DCIT21, DCIT 21, COSC 70, ITEC 50)
    subject_code = ""
    subject_prefix = ""
    ceit_meta = get_prefix_metadata(cleaned)
    if ceit_meta:
        subject_prefix = ceit_meta["prefix"]
        num_m = re.search(r'\b' + re.escape(subject_prefix) + r'[\s_-]*(\d{1,3}[A-Za-z]?)\b', cleaned, re.IGNORECASE)
        if num_m:
            subject_code = f"{subject_prefix} {num_m.group(1).upper()}"
        else:
            subject_code = subject_prefix

    # 4. Subject Name / Title
    subject_name = subject_code
    dash_m = re.search(r'-\s*([A-Za-z\s]{4,})', cleaned)
    if dash_m:
        title_cand = dash_m.group(1).strip()
        if subject_code and not title_cand.upper().startswith(subject_code):
            subject_name = f"{subject_code} - {title_cand}"
        else:
            subject_name = title_cand

    # Identify missing fields
    missing = []
    if not course_sec:
        missing.append("course_sec")
    if not schedule_code:
        missing.append("schedule_code")
    if not subject_name or subject_name == subject_prefix:
        missing.append("subject_name")

    # Generate recommended official registrar filename
    norm_course = course_sec.replace(" ", "") if course_sec else "CourseSec"
    disp_sched = schedule_code or "ScheduleCode"
    disp_subj = subject_name or (f"{subject_code} - SubjectTitle" if subject_code else "SubjectTitle")
    recommended_filename = f"{norm_course} List of Students for {disp_sched}-{disp_subj}.xlsx"

    return {
        "course_sec": course_sec,
        "schedule_code": schedule_code,
        "subject_prefix": subject_prefix,
        "subject_code": subject_code,
        "subject_name": subject_name,
        "missing": missing,
        "recommended_filename": recommended_filename,
        "ceit_metadata": ceit_meta
    }


def is_known_lab_subject(subject_str: str) -> bool:
    """Returns True if the given subject name or code contains a laboratory component."""
    return config_manager.is_lab_subject(subject_str)
