import os
import re
import csv
import zipfile
from xml.etree import ElementTree as ET
from modules.common.excel_utils import safe_get_column_letter
from modules.parsers.ceit_directory import CEIT_PREFIX_MAP, get_prefix_metadata, parse_filename_hints

# Pre-compiled regular expressions for speed and memory efficiency
RE_ALPHANUM_ONLY = re.compile(r'[^a-z0-9]')
RE_NAME_TOKEN = re.compile(r'\bname\b', re.IGNORECASE)
RE_NON_NAME_CONTEXT = re.compile(r'\b(subject|course|file|sheet|school|college|dept|department)\b', re.IGNORECASE)
RE_STUD_ID_TOKEN = re.compile(r'\b(student|stud)\b.*\b(no|num|number|id|#)\b', re.IGNORECASE)
RE_DIGITS_ONLY = re.compile(r'\d+')
RE_XML_SHEET = re.compile(r"^xl/worksheets/sheet\d+\.xml$")

def _fix_encoding(text: str) -> str:
    """Normalize common encoding issues (e.g. accents, enye, curly quotes)."""
    if not text:
        return ""
    s = str(text).strip()
    for enc in ("cp1252", "latin1"):
        try:
            decoded = s.encode(enc).decode("utf-8")
            if decoded and ("\ufffd" not in decoded):
                s = decoded.strip()
                break
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
    # Normalize isolated corrupted Ã / ã that university portal exports create for Ñ / ñ
    s = re.sub(r'Ã(?=[A-Za-z\s])', 'Ñ', s)
    s = re.sub(r'ã(?=[a-z\s])', 'ñ', s)
    s = s.replace('Ã', 'Ñ')
    return s.strip()

def _is_id_header(header: str, custom_tokens: list = None) -> bool:
    """Detect if header cell text represents a student number / ID."""
    h = str(header).lower().strip()
    clean_h = RE_ALPHANUM_ONLY.sub('', h)
    if not clean_h:
        return False
    id_tokens = [
        "studentnumber", "studentno", "studentnum", "studentid",
        "idnumber", "idno", "studno", "studnumber", "studnum",
        "student#", "stud#", "id#", "id", "studid", "student_no", "student_id",
        "lrn", "studentkey", "matricula", "registrationno"
    ]
    if custom_tokens:
        id_tokens.extend([RE_ALPHANUM_ONLY.sub('', str(t).lower()) for t in custom_tokens if t])
    if clean_h in id_tokens:
        return True
    if any(tok in clean_h for tok in ["studentno", "studentid", "idnumber", "studno"]):
        return True
    if RE_STUD_ID_TOKEN.search(h):
        return True
    return False

def _is_name_header(header: str, custom_tokens: list = None) -> bool:
    """Detect if header cell text represents a student name."""
    if _is_id_header(header, custom_tokens):
        return False
    h = str(header).lower().strip()
    if "," in h and not any(w in h for w in ["last", "first", "middle", "suffix"]):
        return False
    clean_h = RE_ALPHANUM_ONLY.sub('', h)
    if not clean_h:
        return False
    name_tokens = [
        "name", "studentname", "fullname", "studentsname", "names",
        "student", "lastname", "studentfullname", "completename", "pangalan"
    ]
    if custom_tokens:
        name_tokens.extend([RE_ALPHANUM_ONLY.sub('', str(t).lower()) for t in custom_tokens if t])
    if clean_h in name_tokens:
        return True
    if any(tok in clean_h for tok in ["studentname", "fullname", "studentsname", "lastname", "completename"]):
        return True
    words = h.split()
    if len(words) <= 3 and RE_NAME_TOKEN.search(h) and not RE_NON_NAME_CONTEXT.search(h):
        if len(words) > 1 and not any(w in h for w in ["student", "full", "complete", "last", "first", "official", "display"]):
            return False
        return True
    return False

def _detect_roster_columns(rows: list, custom_id_tokens: list = None, custom_name_tokens: list = None):
    """Scans the first 6 rows to locate Name and Student Number headers."""
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
                    col_let = safe_get_column_letter(c, zero_based=True)
                    val = sheet.cell_value(r, c)
                    if isinstance(val, float) and val.is_integer():
                        val = str(int(val))
                    else:
                        val = str(val).strip()
                    r_dict[col_let] = val
                if any(r_dict.values()):
                    row_dicts.append(r_dict)
                    max_cols = max(max_cols, len(r_dict))
            available_cols = [safe_get_column_letter(c, zero_based=True) for c in range(max_cols)]
            return row_dicts, available_cols
        except Exception:
            pass

    # .xlsx via direct XML streaming
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

        sheet_files = [f for f in z.namelist() if RE_XML_SHEET.match(f)]
        sheet_file = sorted(sheet_files)[0] if sheet_files else "xl/worksheets/sheet1.xml"
        ws_tree = ET.fromstring(z.read(sheet_file))

        row_dicts = []
        seen_cols = set()
        for row_el in ws_tree.findall(f".//{{{NS}}}sheetData/{{{NS}}}row"):
            cell_dict = {}
            for c_el in row_el.findall(f"{{{NS}}}c"):
                ref = c_el.get("r", "")
                col_let = RE_DIGITS_ONLY.sub('', ref).upper()
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
    """Reads raw rows from a CSV file with automatic encoding & delimiter detection (csv.Sniffer)."""
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1", "utf-16"]
    for enc in encodings:
        try:
            with open(path, newline="", encoding=enc) as f:
                sample = f.read(4096)
                f.seek(0)
                delimiter = ','
                try:
                    sniffed = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                    delimiter = sniffed.delimiter
                except Exception:
                    delimiter = ','
                reader = csv.reader(f, delimiter=delimiter)
                raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
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
    Displays raw spreadsheet rows, candidate columns, detected headers, and live parsed results.
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

        auto_name, auto_id, auto_header_idx = _detect_roster_columns(raw_rows)

        raw_name = overrides.get("name_col") if overrides.get("name_col") is not None else overrides.get("name_column")
        raw_id = overrides.get("id_col") if overrides.get("id_col") is not None else overrides.get("id_column")
        raw_header = overrides.get("header_row")

        if raw_name is not None:
            if is_excel:
                if isinstance(raw_name, int) and 0 <= raw_name < len(available_cols):
                    name_col = available_cols[raw_name]
                elif str(raw_name).isdigit() and 0 <= int(raw_name) < len(available_cols):
                    name_col = available_cols[int(raw_name)]
                else:
                    name_col = str(raw_name).upper()
            else:
                try:
                    name_col = int(raw_name)
                except (ValueError, TypeError):
                    name_col = raw_name
        else:
            name_col = auto_name

        if raw_id is not None:
            if is_excel:
                if isinstance(raw_id, int) and 0 <= raw_id < len(available_cols):
                    id_col = available_cols[raw_id]
                elif str(raw_id).isdigit() and 0 <= int(raw_id) < len(available_cols):
                    id_col = available_cols[int(raw_id)]
                else:
                    id_col = str(raw_id).upper()
            else:
                try:
                    id_col = int(raw_id)
                except (ValueError, TypeError):
                    id_col = raw_id
        else:
            id_col = auto_id

        if raw_header is not None:
            try:
                header_row = int(raw_header)
            except (ValueError, TypeError):
                header_row = auto_header_idx
        else:
            header_row = auto_header_idx

        raw_rows_list = []
        preview_rows = []
        for r_idx in range(min(max_rows, len(raw_rows))):
            row_data = raw_rows[r_idx]
            if is_excel and isinstance(row_data, dict):
                row_cells = {c: row_data.get(c, "") for c in available_cols}
                row_as_list = [row_data.get(c, "") for c in available_cols]
            elif isinstance(row_data, list):
                row_cells = {c: (row_data[c] if c < len(row_data) else "") for c in available_cols}
                row_as_list = [str(row_data[c]) if c < len(row_data) else "" for c in range(len(available_cols))]
            else:
                row_cells = {}
                row_as_list = []
            raw_rows_list.append(row_as_list)
            preview_rows.append({
                "row_index": r_idx,
                "is_header": (r_idx == header_row),
                "cells": row_cells
            })

        available_cols_obj = []
        for idx, col_ref in enumerate(available_cols):
            col_header = ""
            if header_row is not None and 0 <= header_row < len(raw_rows):
                hr = raw_rows[header_row]
                if is_excel and isinstance(hr, dict):
                    col_header = hr.get(col_ref, "")
                elif isinstance(hr, list) and idx < len(hr):
                    col_header = str(hr[idx])
            col_name = f"Col {col_ref}: {col_header}" if col_header else f"Column {col_ref}"
            available_cols_obj.append({
                "index": idx,
                "col_ref": col_ref,
                "letter": str(col_ref),
                "name": col_name
            })

        auto_name_idx = available_cols.index(auto_name) if auto_name in available_cols else 0
        auto_id_idx = available_cols.index(auto_id) if auto_id in available_cols else (1 if len(available_cols) > 1 else 0)

        students = load_students(
            path,
            name_col=name_col,
            id_col=id_col,
            header_row=header_row
        )

        parsed_students_obj = [
            {"name": s[0], "student_number": s[1]}
            for s in students
        ]

        hints = parse_filename_hints(filename)
        fmt = "XLSX" if ext in (".xlsx", ".xlsm") else ("XLS" if ext == ".xls" else "CSV")

        return {
            "status": "success",
            "filename": filename,
            "path": path,
            "is_excel": is_excel,
            "format": fmt,
            "total_rows": len(raw_rows),
            "available_columns": available_cols_obj,
            "columns": available_cols,
            "raw_rows": raw_rows_list,
            "raw_preview": preview_rows,
            "detected_header_row": auto_header_idx,
            "detected_name_column": auto_name_idx,
            "detected_id_column": auto_id_idx,
            "auto_name_col": auto_name,
            "auto_id_col": auto_id,
            "auto_header_row": auto_header_idx,
            "active_name_col": name_col,
            "active_id_col": id_col,
            "active_header_row": header_row,
            "parsed_students": parsed_students_obj,
            "parsed_preview": students[:6],
            "student_count": len(students),
            "ceit_metadata": get_prefix_metadata(filename),
            "filename_hints": hints,
            "recommended_filename": hints.get("recommended_filename", "")
        }
    except Exception as e:
        return {
            "status": "error",
            "filename": filename,
            "path": path,
            "message": str(e)
        }

def load_students(path: str, name_col=None, id_col=None, header_row=None, custom_aliases=None) -> list:
    """Unified loader for student rosters (.xlsx, .xls, .csv). Returns normalized [(name, student_number), ...] tuples."""
    ext = os.path.splitext(path)[1].lower()
    is_excel = ext in (".xlsx", ".xls", ".xlsm")

    if is_excel:
        raw_rows, _ = _read_excel_raw_rows(path)
    else:
        raw_rows, _ = _read_csv_raw_rows(path)

    if not raw_rows:
        return []

    auto_name, auto_id, auto_header = _detect_roster_columns(
        raw_rows,
        custom_id_tokens=custom_aliases.get("id") if custom_aliases else None,
        custom_name_tokens=custom_aliases.get("name") if custom_aliases else None
    )

    use_name = name_col if name_col is not None else auto_name
    use_id = id_col if id_col is not None else auto_id
    use_header = header_row if header_row is not None else auto_header

    start_row = use_header + 1 if (use_header is not None and use_header >= 0) else 0

    header_val_str = ""
    if use_header is not None and 0 <= use_header < len(raw_rows):
        h_row = raw_rows[use_header]
        if is_excel and isinstance(h_row, dict):
            header_val_str = str(h_row.get(use_name, "")).strip().lower()
        elif isinstance(h_row, list) and use_name is not None:
            try:
                n_idx = int(use_name)
                if n_idx < len(h_row):
                    header_val_str = str(h_row[n_idx]).strip().lower()
            except (ValueError, TypeError):
                pass

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

        if not a:
            continue
        # Only skip if repeated literal header row text
        if header_val_str and a.lower() == header_val_str:
            continue
        students.append((_fix_encoding(a), _fix_encoding(b)))

    return students

def load_students_excel(path: str) -> list:
    return load_students(path)

def load_students_csv(path: str) -> list:
    return load_students(path)

def normalize_name(name: str) -> str:
    """Clean and normalize student name string."""
    if not name:
        return ""
    cleaned = _fix_encoding(str(name)).strip()
    return re.sub(r'\s+', ' ', cleaned)

def sanitize_name(name: str) -> str:
    return normalize_name(name)

def sanitize_stnum(stnum: str) -> str:
    if not stnum:
        return ""
    st = str(stnum).strip()
    if isinstance(stnum, float) and stnum.is_integer():
        return str(int(stnum))
    if st.endswith(".0"):
        st = st[:-2]
    return st
