import os
import re

# Official College of Engineering and Information Technology (CEIT) Subject Prefix & Department Directory
CEIT_PREFIX_MAP = {
    "AGEN": {
        "name": "Agricultural and Biosystems Engineering",
        "dept": "Department of Agricultural and Food Engineering",
        "dept_code": "DAFE",
        "icon": "🌱",
        "badge": "🌱 DAFE"
    },
    "ABEN": {
        "name": "Agricultural and Biosystems Engineering",
        "dept": "Department of Agricultural and Food Engineering",
        "dept_code": "DAFE",
        "icon": "🌱",
        "badge": "🌱 DAFE"
    },
    "ARCH": {
        "name": "Architecture",
        "dept": "Department of Civil Engineering",
        "dept_code": "DCE",
        "icon": "📐",
        "badge": "📐 Architecture"
    },
    "CENG": {
        "name": "Civil Engineering",
        "dept": "Department of Civil Engineering",
        "dept_code": "DCE",
        "icon": "🏛️",
        "badge": "🏛️ Civil Eng"
    },
    "CIVL": {
        "name": "Civil Engineering",
        "dept": "Department of Civil Engineering",
        "dept_code": "DCE",
        "icon": "🏛️",
        "badge": "🏛️ Civil Eng"
    },
    "COSC": {
        "name": "Computer Science",
        "dept": "Department of Information Technology",
        "dept_code": "DIT",
        "icon": "🖥️",
        "badge": "🖥️ Computer Science"
    },
    "CPEN": {
        "name": "Computer Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "⚡",
        "badge": "⚡ Computer Eng"
    },
    "DCEE": {
        "name": "Computer Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "⚡",
        "badge": "⚡ Computer Eng"
    },
    "DCIT": {
        "name": "DIT Core / Common IT",
        "dept": "Department of Information Technology",
        "dept_code": "DIT",
        "icon": "💻",
        "badge": "💻 DIT Core"
    },
    "ECEN": {
        "name": "Electronics Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "📡",
        "badge": "📡 Electronics Eng"
    },
    "EENG": {
        "name": "Electrical Engineering",
        "dept": "Department of Computer and Electronics Engineering",
        "dept_code": "DCEE",
        "icon": "🔌",
        "badge": "🔌 Electrical Eng"
    },
    "IENG": {
        "name": "Industrial Engineering",
        "dept": "Department of Industrial Engineering and Technology",
        "dept_code": "DIET",
        "icon": "🏭",
        "badge": "🏭 Industrial Eng"
    },
    "INDT": {
        "name": "Industrial Technology",
        "dept": "Department of Industrial Engineering and Technology",
        "dept_code": "DIET",
        "icon": "🔧",
        "badge": "🔧 Industrial Tech"
    },
    "SMT": {
        "name": "Industrial Technology",
        "dept": "Department of Industrial Engineering and Technology",
        "dept_code": "DIET",
        "icon": "🔧",
        "badge": "🔧 Industrial Tech"
    },
    "ITEC": {
        "name": "Information Technology",
        "dept": "Department of Information Technology",
        "dept_code": "DIT",
        "icon": "🌐",
        "badge": "🌐 Info Tech"
    }
}

BASE_SUBJECT_PREFIXES = (
    "CVSU", "DCIT", "COSC", "ITEC", "INSY", "GNED", "MATH", "STAT",
    "FITT", "NSTP", "PHYS", "PHED", "ECON", "BAMG", "ENGR", "BSCE",
    "COEN", "ELET", "MECH", "AENG", "CHEM", "BIOL", "FILI", "HIST",
    "COMM", "SOCS", "HUMA", "AGRI", "CRIM", "BMGT"
)
SUBJECT_PREFIXES = tuple(sorted(set(list(BASE_SUBJECT_PREFIXES) + list(CEIT_PREFIX_MAP.keys()))))

def get_prefix_metadata(text: str) -> dict:
    """Extract recognized CEIT subject prefix from text/filename and return department metadata."""
    if not text:
        return None
    cleaned = str(text).upper()
    for prefix, meta in CEIT_PREFIX_MAP.items():
        if re.search(r'(?:^|[^A-Z])' + re.escape(prefix) + r'(?=$|[^A-Z])', cleaned):
            return {
                "prefix": prefix,
                "name": meta["name"],
                "dept": meta["dept"],
                "dept_code": meta["dept_code"],
                "department_name": meta["dept"],
                "department_code": meta["dept_code"],
                "icon": meta["icon"],
                "badge": meta["badge"]
            }
    return None

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
        if prog == "CS":
            prog = "BSCS"
        elif prog == "IT":
            prog = "BSIT"
        elif prog in ("CPE", "CPEN"):
            prog = "BSCPE"
        elif prog in ("CE", "CIVL", "CENG"):
            prog = "BSCE"
        elif prog in ("EE", "EENG"):
            prog = "BSEE"
        elif prog in ("ECE", "ECEN"):
            prog = "BSECE"
        elif prog in ("ABE", "ABEN", "AGEN"):
            prog = "BSABE"
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

# Known subjects containing laboratory components in the CvSU CEIT curriculum
KNOWN_LAB_SUBJECT_CODES = {
    "DCIT 21", "DCIT 22", "DCIT 23", "DCIT 24", "DCIT 25", "DCIT 26",
    "DCIT21", "DCIT22", "DCIT23", "DCIT24", "DCIT25", "DCIT26",
    "COSC 111", "COSC 111A", "COSC 55", "COSC 60", "COSC 65", "COSC 70", "COSC 75", "COSC 80", "COSC 85", "COSC 101",
    "COSC111", "COSC111A", "COSC55", "COSC60", "COSC65", "COSC70", "COSC75", "COSC80", "COSC85", "COSC101",
    "ITEC 50", "ITEC 55", "ITEC 60", "ITEC 65", "ITEC 70", "ITEC 75", "ITEC 80", "ITEC 85", "ITEC 90",
    "ITEC50", "ITEC55", "ITEC60", "ITEC65", "ITEC70", "ITEC75", "ITEC80", "ITEC85", "ITEC90",
}

NORMALIZED_LAB_SUBJECT_CODES = {re.sub(r'[^A-Za-z0-9]', '', c).upper() for c in KNOWN_LAB_SUBJECT_CODES}

def is_known_lab_subject(subject_str: str) -> bool:
    """Returns True if the given subject name or code contains a laboratory component."""
    if not subject_str:
        return False
    prefix = re.split(r'[-–—―−]', str(subject_str))[0].upper()
    prefix = re.sub(r'\(.*?\)', '', prefix).strip()
    norm = re.sub(r'[^A-Za-z0-9]', '', prefix)
    return norm in NORMALIZED_LAB_SUBJECT_CODES or prefix in KNOWN_LAB_SUBJECT_CODES
