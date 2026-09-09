"""
Unified Roster Parser Module for CvSU Document Generators
Provides robust spreadsheet (.xlsx, .xls) and CSV parsing, intelligent header detection,
manual column/row overrides, CEIT department prefix metadata, and diagnostic inspection.
"""

import os
import re
import csv
import zipfile
from xml.etree import ElementTree as ET

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


def get_prefix_metadata(text: str) -> dict:
    """Extract recognized CEIT subject prefix from text/filename and return department metadata."""
    if not text:
        return None
    cleaned = str(text).upper()
    for prefix, meta in CEIT_PREFIX_MAP.items():
        if re.search(r'(?:^|[^A-Z0-9])' + re.escape(prefix) + r'(?=$|[^A-Z0-9])', cleaned):
            return {
                "prefix": prefix,
                "name": meta["name"],
                "dept": meta["dept"],
                "dept_code": meta["dept_code"],
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


def _fix_encoding(text: str) -> str:
    """Normalize common encoding issues (e.g. accents, enye, curly quotes)."""
    if not text:
        return ""
    s = str(text).strip()
    for enc in ("cp1252", "latin1"):
        try:
            decoded = s.encode(enc).decode("utf-8")
            if decoded:
                return decoded.strip()
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    replacements = {
        "\u00f1": "ñ", "\u00d1": "Ñ",
        "Ã±": "ñ", "Ã‘": "Ñ",
        "â€™": "’", "â€˜": "‘",
        "â€œ": "“", "â€": "”",
        "\u2019": "’", "\u2018": "‘",
        "\u201c": "“", "\u201d": "”",
        "\u00e9": "é", "\u00c9": "É",
        "\u00e1": "á", "\u00c1": "Á"
    }
    for bad, good in replacements.items():
        s = s.replace(bad, good)
    return s.strip()


def _is_id_header(header: str, custom_tokens: list = None) -> bool:
    """Detect if header cell text represents a student number / ID."""
    h = str(header).lower().strip()
    clean_h = re.sub(r'[^a-z0-9]', '', h)
    if not clean_h:
        return False
    id_tokens = [
        "studentnumber", "studentno", "studentnum", "studentid",
        "idnumber", "idno", "studno", "studnumber", "studnum",
        "student#", "stud#", "id#", "id", "studid", "student_no", "student_id",
        "lrn", "studentkey", "matricula", "registrationno"
    ]
    if custom_tokens:
        id_tokens.extend([re.sub(r'[^a-z0-9]', '', str(t).lower()) for t in custom_tokens if t])
    if clean_h in id_tokens:
        return True
    if any(tok in clean_h for tok in ["studentno", "studentid", "idnumber", "studno"]):
        return True
    if re.search(r'\b(student|stud)\b.*\b(no|num|number|id|#)\b', h):
        return True
    return False


def _is_name_header(header: str, custom_tokens: list = None) -> bool:
    """Detect if header cell text represents a student name."""
    if _is_id_header(header, custom_tokens):
        return False
    h = str(header).lower().strip()
    clean_h = re.sub(r'[^a-z0-9]', '', h)
    if not clean_h:
        return False
    name_tokens = [
        "name", "studentname", "fullname", "studentsname", "names",
        "student", "lastname", "studentfullname", "completename", "pangalan"
    ]
    if custom_tokens:
        name_tokens.extend([re.sub(r'[^a-z0-9]', '', str(t).lower()) for t in custom_tokens if t])
    if clean_h in name_tokens:
        return True
    if any(tok in clean_h for tok in ["studentname", "fullname", "studentsname", "lastname", "completename"]):
        return True
    if re.search(r'\bname\b', h) and not re.search(r'\b(subject|course|file|sheet|school|college|dept|department)\b', h):
        return True
    return False


def _detect_roster_columns(rows: list, custom_id_tokens: list = None, custom_name_tokens: list = None):
    """
    Scans the first 6 rows to locate Name and Student Number headers.
    Returns (name_col, id_col, header_row_index).
    If no header row is identified:
      - Checks first row data heuristics (numbers vs text)
      - Returns (name_col, id_col, -1) where -1 means no header row to skip
    """
    for r_idx in range(min(6, len(rows))):
        row = rows[r_idx]
        col_items = row.items() if isinstance(row, dict) else list(enumerate(row))
        found_name = None
        found_id = None
        for col_key, val in col_items:
            val_str = str(val).strip()
            if not val_str:
                continue
            if _is_id_header(val_str, custom_id_tokens) and found_id is None:
                found_id = col_key
            elif _is_name_header(val_str, custom_name_tokens) and found_name is None:
                found_name = col_key
        if found_name is not None and found_id is not None:
            return found_name, found_id, r_idx

    for r_idx in range(min(6, len(rows))):
        row = rows[r_idx]
        col_items = row.items() if isinstance(row, dict) else list(enumerate(row))
        found_name = None
        for col_key, val in col_items:
            val_str = str(val).strip()
            if _is_name_header(val_str, custom_name_tokens):
                found_name = col_key
                break
        if found_name is not None:
            other_cols = [k for k, _ in col_items if k != found_name]
            id_col = other_cols[0] if other_cols else None
            return found_name, id_col, r_idx

    if rows:
        first_row = rows[0]
        col_items = list(first_row.items()) if isinstance(first_row, dict) else list(enumerate(first_row))
        if len(col_items) >= 2:
            k0, v0 = col_items[0]
            k1, v1 = col_items[1]
            s0 = str(v0).strip()
            s1 = str(v1).strip()
            if (re.match(r'^\d{2,}-\d+$', s0) or re.match(r'^\d{6,12}$', s0)) and re.search(r'[A-Za-z]', s1):
                return k1, k0, -1
            if (re.match(r'^\d{2,}-\d+$', s1) or re.match(r'^\d{6,12}$', s1)) and re.search(r'[A-Za-z]', s0):
                return k0, k1, -1
            return k0, k1, -1
        elif len(col_items) == 1:
            k0, _ = col_items[0]
            return k0, None, -1

    default_a = 'A' if (rows and isinstance(rows[0], dict)) else 0
    default_b = 'B' if (rows and isinstance(rows[0], dict)) else 1
    return default_a, default_b, -1


def _read_excel_raw_rows(path: str) -> tuple:
    """Reads raw rows from an Excel file (.xlsx via XML, .xls via xlrd). Returns (row_dicts, available_cols)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xls":
        try:
            import xlrd
            wb = xlrd.open_workbook(path)
            sheet = wb.sheet_by_index(0)
            row_dicts = []
            max_cols = 0
            for r in range(sheet.nrows):
                r_dict = {}
                for c in range(sheet.ncols):
                    col_let = chr(65 + c) if c < 26 else f"A{chr(65 + c - 26)}"
                    val = sheet.cell_value(r, c)
                    if isinstance(val, float) and val.is_integer():
                        val = str(int(val))
                    else:
                        val = str(val).strip()
                    r_dict[col_let] = val
                if any(r_dict.values()):
                    row_dicts.append(r_dict)
                    max_cols = max(max_cols, len(r_dict))
            available_cols = [chr(65 + c) if c < 26 else f"A{chr(65 + c - 26)}" for c in range(max_cols)]
            return row_dicts, available_cols
        except Exception:
            pass

    # .xlsx via direct XML
    NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    with zipfile.ZipFile(path, "r") as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            s_tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in s_tree.findall(f"{{{NS}}}si"):
                t = "".join(elem.text or "" for elem in si.iter(f"{{{NS}}}t"))
                strings.append(t)

        def cell_val(c):
            t_type = c.get("t")
            v_el = c.find(f"{{{NS}}}v")
            if v_el is None or v_el.text is None:
                is_el = c.find(f"{{{NS}}}is")
                if is_el is not None:
                    return "".join(elem.text or "" for elem in is_el.iter(f"{{{NS}}}t"))
                return ""
            if t_type == "s":
                idx = int(v_el.text)
                return strings[idx] if idx < len(strings) else ""
            return v_el.text

        sheet_files = [f for f in z.namelist() if re.match(r"^xl/worksheets/sheet\d+\.xml$", f)]
        sheet_file = sorted(sheet_files)[0] if sheet_files else "xl/worksheets/sheet1.xml"
        ws_tree = ET.fromstring(z.read(sheet_file))

        row_dicts = []
        seen_cols = set()
        for row_el in ws_tree.findall(f".//{{{NS}}}sheetData/{{{NS}}}row"):
            cell_dict = {}
            for c_el in row_el.findall(f"{{{NS}}}c"):
                ref = c_el.get("r", "")
                col_let = re.sub(r'\d+', '', ref).upper()
                if col_let:
                    cell_dict[col_let] = cell_val(c_el).strip()
                    seen_cols.add(col_let)
            if any(cell_dict.values()):
                row_dicts.append(cell_dict)

        def col_key(c):
            return (len(c), c)
        available_cols = sorted(list(seen_cols), key=col_key) if seen_cols else ["A", "B"]
        return row_dicts, available_cols


def _read_csv_raw_rows(path: str) -> tuple:
    """Reads raw rows from a CSV file with automatic encoding detection. Returns (raw_rows, available_cols)."""
    encodings = ["utf-8", "utf-16", "utf-8-sig", "cp1252", "latin1"]
    for enc in encodings:
        try:
            with open(path, newline="", encoding=enc) as f:
                raw_rows = [row for row in csv.reader(f) if any(cell.strip() for cell in row)]
                if not raw_rows:
                    return [], [0, 1]
                max_cols = max(len(r) for r in raw_rows)
                available_cols = list(range(max_cols))
                return raw_rows, available_cols
        except (UnicodeDecodeError, csv.Error):
            continue
    raise RuntimeError(f"Could not parse CSV {path} with any known encoding.")


def inspect_roster(path: str, max_rows: int = 8, overrides: dict = None) -> dict:
    """
    Returns rich diagnostic and preview information for a roster file.
    Can be called by the pywebview frontend to display raw spreadsheet rows,
    candidate columns, detected headers, and live parsed results.
    """
    if not os.path.exists(path):
        return {"status": "error", "message": f"File not found: {path}"}

    filename = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    overrides = overrides or {}

    try:
        is_excel = ext in (".xlsx", ".xls", ".xlsm")
        if is_excel:
            raw_rows, available_cols = _read_excel_raw_rows(path)
        else:
            raw_rows, available_cols = _read_csv_raw_rows(path)

        if not raw_rows:
            return {
                "status": "empty",
                "filename": filename,
                "path": path,
                "total_rows": 0,
                "available_columns": [],
                "raw_preview": [],
                "parsed_preview": [],
                "student_count": 0,
                "ceit_metadata": get_prefix_metadata(filename)
            }

        # Determine columns & header row
        auto_name, auto_id, auto_header_idx = _detect_roster_columns(raw_rows)

        name_col = overrides.get("name_col") if overrides.get("name_col") is not None else auto_name
        id_col = overrides.get("id_col") if overrides.get("id_col") is not None else auto_id
        header_row = overrides.get("header_row") if overrides.get("header_row") is not None else auto_header_idx

        # If name_col or id_col are integers in string format, normalize
        if not is_excel:
            try:
                name_col = int(name_col) if name_col is not None else auto_name
            except (ValueError, TypeError):
                pass
            try:
                id_col = int(id_col) if id_col is not None else auto_id
            except (ValueError, TypeError):
                pass

        # Build raw table preview
        preview_rows = []
        for r_idx in range(min(max_rows, len(raw_rows))):
            row_data = raw_rows[r_idx]
            if is_excel and isinstance(row_data, dict):
                row_cells = {c: row_data.get(c, "") for c in available_cols}
            elif isinstance(row_data, list):
                row_cells = {c: (row_data[c] if c < len(row_data) else "") for c in available_cols}
            else:
                row_cells = {}
            preview_rows.append({
                "row_index": r_idx,
                "is_header": (r_idx == header_row),
                "cells": row_cells
            })

        # Parse students with active config
        students = load_students(
            path,
            name_col=name_col,
            id_col=id_col,
            header_row=header_row
        )

        hints = parse_filename_hints(filename)
        return {
            "status": "success",
            "filename": filename,
            "path": path,
            "is_excel": is_excel,
            "total_rows": len(raw_rows),
            "available_columns": available_cols,
            "columns": available_cols,
            "auto_name_col": auto_name,
            "auto_id_col": auto_id,
            "auto_header_row": auto_header_idx,
            "active_name_col": name_col,
            "active_id_col": id_col,
            "active_header_row": header_row,
            "raw_preview": preview_rows,
            "parsed_preview": students[:6],
            "student_count": len(students),
            "ceit_metadata": get_prefix_metadata(filename),
            "filename_hints": hints
        }
    except Exception as e:
        return {
            "status": "error",
            "filename": filename,
            "path": path,
            "message": str(e)
        }


def load_students(path: str, name_col=None, id_col=None, header_row=None, custom_aliases=None) -> list:
    """
    Unified loader for student rosters (.xlsx, .xls, .csv).
    Accepts optional explicit column and header row overrides.
    Returns normalized [(name, student_number), ...] tuples.
    """
    ext = os.path.splitext(path)[1].lower()
    is_excel = ext in (".xlsx", ".xls", ".xlsm")

    if is_excel:
        raw_rows, _ = _read_excel_raw_rows(path)
    else:
        raw_rows, _ = _read_csv_raw_rows(path)

    if not raw_rows:
        return []

    # Detect if overrides not specified
    auto_name, auto_id, auto_header = _detect_roster_columns(
        raw_rows,
        custom_id_tokens=custom_aliases.get("id") if custom_aliases else None,
        custom_name_tokens=custom_aliases.get("name") if custom_aliases else None
    )

    use_name = name_col if name_col is not None else auto_name
    use_id = id_col if id_col is not None else auto_id
    use_header = header_row if header_row is not None else auto_header

    start_row = use_header + 1 if (use_header is not None and use_header >= 0) else 0

    students = []
    for row in raw_rows[start_row:]:
        if is_excel and isinstance(row, dict):
            a = row.get(use_name, "").strip() if use_name else ""
            b = row.get(use_id, "").strip() if use_id else ""
        elif isinstance(row, list):
            try:
                n_idx = int(use_name) if use_name is not None else None
            except (ValueError, TypeError):
                n_idx = None
            try:
                i_idx = int(use_id) if use_id is not None else None
            except (ValueError, TypeError):
                i_idx = None

            a = row[n_idx].strip() if (n_idx is not None and n_idx < len(row)) else ""
            b = row[i_idx].strip() if (i_idx is not None and i_idx < len(row)) else ""
        else:
            continue

        if not a or _is_name_header(a):
            continue
        students.append((_fix_encoding(a), _fix_encoding(b)))

    return students


# Aliases for backward compatibility
def load_students_excel(path: str) -> list:
    return load_students(path)

def load_students_csv(path: str) -> list:
    return load_students(path)
