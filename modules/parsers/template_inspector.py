#!/usr/bin/env python3
"""
modules/parsers/template_inspector.py

Deterministic Heuristic Template Analyzer for CvSU Document Generator.
Performs 100% offline, local analysis (< 20ms) of any Word (.docx) document
without using any external AI, LLMs, or cloud dependencies.

Analyzes:
  1. Metadata bindings (Instructor, Course/Section, Schedule Code, Subject, Time/Days/Room, Semester/AY)
     across header tables, paragraphs, and placeholder tags.
  2. Student roster tables (identifies index, name, student number, and signature columns).
  3. Template row structure and font scaling thresholds.
  4. Suggested document title and file suffix.
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple

from modules.common.logger import logger
from modules.common.docx_utils import load_docx, get_full_text, w


FIELD_PATTERNS = {
    "instructor": re.compile(
        r"\b(?:instructor(?:['’]s)?(?:\s+name)?(?:\s*(?:and|/)?\s*signature)?|faculty|teacher|professor)\b",
        re.IGNORECASE,
    ),
    "course_section": re.compile(
        r"\b(?:course\s*(?:and|&|/)?\s*(?:year|yr\.?)?\s*(?:and|&|/)?\s*section|course\s*(?:and|&|/)?\s*sec(?:tion)?|section|degree\s*program)\b",
        re.IGNORECASE,
    ),
    "schedule_code": re.compile(
        r"\b(?:schedule\s*code|sched\.?\s*code|class\s*code|course\s*code)\b",
        re.IGNORECASE,
    ),
    "subject": re.compile(
        r"\b(?:subject(?:\s*code)?(?:\s*(?:and|/)?\s*title)?|course\s*(?:code|title)|descriptive\s*title)\b",
        re.IGNORECASE,
    ),
    "time_days_room": re.compile(
        r"\b(?:time\s*(?:and|&|/)?\s*days?\s*(?:and|&|/)?\s*room(?:\s*no\.?)?|class\s*hours?|time\s*and\s*day|schedule)\b",
        re.IGNORECASE,
    ),
    "semester_ay": re.compile(
        r"\b(?:semester\s*(?:and|&|/)?\s*(?:academic\s*year|ay|a\.y\.)|academic\s*year|term|a\.y\.)\b",
        re.IGNORECASE,
    ),
    "date": re.compile(
        r"\b(?:date(?:\s*(?:and|/)?\s*time)?|petsa)\b",
        re.IGNORECASE,
    ),
}

# Standard font shrink thresholds matching CvSU form specs
FIELD_SHRINK_THRESHOLDS = {
    "instructor": 30,
    "course_section": 0,
    "schedule_code": 0,
    "subject": 35,
    "time_days_room": 45,
    "semester_ay": 0,
    "date": 0,
}

# Roster column tokens
INDEX_TOKENS = {"no.", "no", "#", "item", "bilang", "index"}
NAME_TOKENS = {"name", "student", "pangalan", "student's name", "name of student", "name of students"}
ID_TOKENS = {"student number", "id number", "stud no", "student no", "stud. no", "id", "lrn", "numero", "studentnumber"}
SIGNATURE_TOKENS = {"signature", "lagda", "sign", "remarks", "grade", "initial"}


class TemplateInspector:
    """
    Deterministic inspector that inspects .docx templates and produces a declarative recipe.
    """

    def inspect_docx(self, template_path: str) -> Dict[str, Any]:
        """
        Main entry point. Inspects template_path and returns structured analysis dictionary.
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found: {template_path}")

        zin, root, body = load_docx(template_path)
        tables = body.findall(w("tbl"))
        paragraphs = body.findall(w("p"))

        # Step 1: Detect student roster table
        roster_info = self._detect_roster_table(tables)

        # Step 2: Detect header metadata bindings
        header_bindings = self._detect_header_bindings(tables, paragraphs, roster_info)

        # Step 3: Detect placeholders (e.g. {{INSTRUCTOR}})
        placeholders = self._detect_placeholders(body)

        # Step 4: Suggest title and suffix
        title, suffix = self._suggest_title_and_suffix(template_path, paragraphs)

        # Step 5: Compute confidence score
        confidence = self._compute_confidence(roster_info, header_bindings, placeholders)

        # Sample preview of what was found
        detected_fields = [b["field"] for b in header_bindings]
        summary = {
            "roster_table_found": roster_info is not None,
            "roster_columns": {
                "index_col": roster_info["index_col"] if roster_info else None,
                "name_col": roster_info["name_col"] if roster_info else None,
                "id_col": roster_info["id_col"] if roster_info else None,
                "signature_col": roster_info["signature_col"] if roster_info else None,
            } if roster_info else {},
            "detected_fields": detected_fields,
            "total_tables": len(tables),
            "total_paragraphs": len(paragraphs),
        }

        recipe = {
            "title": title,
            "suffix": suffix,
            "template_file": os.path.basename(template_path),
            "confidence": confidence,
            "header_bindings": header_bindings,
            "roster_table": roster_info,
            "placeholders": placeholders,
            "summary": summary,
        }
        return recipe

    def _detect_roster_table(self, tables: List[Any]) -> Optional[Dict[str, Any]]:
        """
        Scans tables to find the student roster table.
        Scores candidate rows based on presence of name, id, index, signature tokens.
        """
        best_candidate = None
        best_score = -1

        for tbl_idx, tbl in enumerate(tables):
            rows = tbl.findall(w("tr"))
            if len(rows) < 2:
                # Need at least a header row and 1 template row
                continue

            for r_idx, row in enumerate(rows[:5]):  # Check first few rows for header
                cells = row.findall(w("tc"))
                if not cells:
                    continue

                cell_texts = [get_full_text(c).strip().lower() for c in cells]
                
                # Check if this row is an info table row (Instructor / Course / etc.)
                all_text = " ".join(cell_texts)
                if any(k in all_text for k in ("instructor", "course /", "schedule code", "time / days")):
                    continue

                index_col = None
                name_col = None
                id_col = None
                signature_col = None

                score = 0

                for c_idx, txt in enumerate(cell_texts):
                    cleaned = re.sub(r"[^a-z0-9#\.\s]", " ", txt).strip()
                    words = set(cleaned.split())

                    # Check ID first (specific phrases or tokens)
                    is_id = any(tok in cleaned for tok in ("student number", "id number", "stud no", "student no", "stud. no", "student id", "studentnumber", "id no", "id.")) or bool(words & {"lrn", "numero", "id"})
                    # Check Index
                    is_index = any(tok in words for tok in ("no", "no.", "#", "item", "bilang", "index")) or cleaned.startswith("#") or cleaned.startswith("no")
                    # Check Signature / Remarks
                    is_sig = any(tok in cleaned for tok in ("signature", "lagda", "sign", "remarks", "grade", "initial", "status", "action taken", "concern"))

                    if id_col is None and is_id:
                        id_col = c_idx
                        score += 3
                    elif index_col is None and is_index:
                        index_col = c_idx
                        score += 1
                    elif signature_col is None and is_sig:
                        signature_col = c_idx
                        score += 1
                    elif name_col is None and (any(tok in cleaned for tok in ("name", "pangalan", "student's name", "name of student", "name of students")) or ("student" in words and not is_id)):
                        name_col = c_idx
                        score += 3

                # A valid roster header must have at least a Name column
                if name_col is not None and (id_col is not None or signature_col is not None):
                    template_row_idx = r_idx + 1
                    total_cols = len(rows[template_row_idx].findall(w("tc"))) if template_row_idx < len(rows) else len(cells)

                    if score > best_score:
                        best_score = score
                        best_candidate = {
                            "table_index": tbl_idx,
                            "header_row_index": r_idx,
                            "template_row_index": template_row_idx,
                            "index_col": index_col,
                            "name_col": name_col,
                            "id_col": id_col,
                            "signature_col": signature_col,
                            "total_cols": total_cols,
                            "header_labels": [get_full_text(c).strip() for c in cells],
                        }

        return best_candidate

    def _detect_header_bindings(
        self, tables: List[Any], paragraphs: List[Any], roster_info: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Finds where class metadata should be populated.
        Prioritizes tables (e.g. Table 0 in CEIT forms), then paragraphs with colons.
        """
        bindings = []
        found_fields = set()

        roster_tbl_idx = roster_info["table_index"] if roster_info else -1

        # 1. Search Tables
        for tbl_idx, tbl in enumerate(tables):
            if tbl_idx == roster_tbl_idx:
                continue

            rows = tbl.findall(w("tr"))
            for r_idx, row in enumerate(rows):
                cells = row.findall(w("tc"))
                if not cells:
                    continue

                for c_idx, cell in enumerate(cells):
                    cell_text = get_full_text(cell).strip()
                    if not cell_text:
                        continue

                    # Test against known fields
                    for field_key, pattern in FIELD_PATTERNS.items():
                        if field_key in found_fields:
                            continue

                        if pattern.search(cell_text):
                            # Determine target value cell
                            target_cell_idx = None
                            method = "set_cell"

                            if len(cells) == 2:
                                target_cell_idx = 1
                            elif len(cells) >= 3:
                                # Check if cell 1 is ":" separator
                                cell1_txt = get_full_text(cells[1]).strip()
                                if cell1_txt == ":":
                                    target_cell_idx = 2
                                elif c_idx + 1 < len(cells):
                                    target_cell_idx = c_idx + 1
                                else:
                                    target_cell_idx = c_idx
                            else:
                                target_cell_idx = 0

                            thresh = FIELD_SHRINK_THRESHOLDS.get(field_key, 0)
                            bindings.append({
                                "field": field_key,
                                "type": "table_cell",
                                "table_index": tbl_idx,
                                "row_index": r_idx,
                                "cell_index": target_cell_idx,
                                "shrink_threshold": thresh,
                                "label_found": cell_text,
                            })
                            found_fields.add(field_key)
                            break

        # 2. Fallback: Search Paragraphs for any fields not yet bound
        for p_idx, para in enumerate(paragraphs):
            p_text = get_full_text(para).strip()
            if not p_text or ":" not in p_text:
                continue

            # Skip paragraphs that contain explicit template tags (handled by placeholder engine)
            if "{{" in p_text or "}}" in p_text or "[[" in p_text:
                continue

            left_part = p_text.split(":", 1)[0].strip()

            for field_key, pattern in FIELD_PATTERNS.items():
                if field_key in found_fields:
                    continue

                if pattern.search(left_part):
                    thresh = FIELD_SHRINK_THRESHOLDS.get(field_key, 0)
                    bindings.append({
                        "field": field_key,
                        "type": "paragraph_colon",
                        "para_index": p_idx,
                        "shrink_threshold": thresh,
                        "label_found": left_part,
                    })
                    found_fields.add(field_key)
                    break

        return bindings

    def _detect_placeholders(self, body: Any) -> List[Dict[str, Any]]:
        """
        Finds explicit template tags like {{INSTRUCTOR}}, {{COURSE}}, etc. in paragraphs or tables.
        """
        placeholders = []
        full_text = "".join(t.text or "" for t in body.iter(w("t")))

        placeholder_pattern = re.compile(r"\{\{([A-Z0-9_]+)\}\}|\[([A-Z0-9_]+)\]")
        matches = placeholder_pattern.findall(full_text)

        tag_mapping = {
            "INSTRUCTOR": "instructor",
            "FACULTY": "instructor",
            "COURSE": "course_section",
            "COURSE_SECTION": "course_section",
            "SECTION": "course_section",
            "SCHEDULE_CODE": "schedule_code",
            "SCHED_CODE": "schedule_code",
            "SUBJECT": "subject",
            "SUBJECT_CODE": "subject",
            "TIME_DAYS_ROOM": "time_days_room",
            "TIME_ROOM": "time_days_room",
            "SEMESTER": "semester_ay",
            "SEMESTER_AY": "semester_ay",
        }

        seen = set()
        for match in matches:
            tag = match[0] or match[1]
            if tag in tag_mapping and tag not in seen:
                seen.add(tag)
                placeholders.append({
                    "field": tag_mapping[tag],
                    "tag": f"{{{{{tag}}}}}" if match[0] else f"[{tag}]",
                    "raw_token": tag,
                })

        return placeholders

    def _suggest_title_and_suffix(
        self, template_path: str, paragraphs: List[Any]
    ) -> Tuple[str, str]:
        """
        Derives user-friendly form title and uppercase file suffix.
        """
        basename = os.path.splitext(os.path.basename(template_path))[0]

        # Clean basename for suffix
        clean_name = re.sub(r"^(?:template_|cvsu_|form_)", "", basename, flags=re.IGNORECASE)
        clean_name = re.sub(r"[-_\s]+", "_", clean_name).strip("_")

        title = clean_name.replace("_", " ").title()
        suffix = clean_name.upper()

        # Check top paragraphs for formal title
        for p in paragraphs[:5]:
            txt = get_full_text(p).strip()
            if len(txt) > 5 and len(txt) < 80:
                upper = txt.upper()
                if any(w_token in upper for w_token in ("FORM", "ACCEPTANCE", "DISCUSSION", "ACKNOWLEDGMENT", "RETURNS", "RECORD", "LOG", "REPORT")):
                    title = txt.title()
                    # Generate concise suffix
                    sub_suffix = re.sub(r"[^A-Za-z0-9\s]", "", upper)
                    tokens = [t for t in sub_suffix.split() if t not in ("OF", "THE", "AND", "FOR", "CVSU", "CEIT")]
                    if tokens:
                        suffix = "_".join(tokens[:4])
                    break

        return title, suffix

    def _compute_confidence(
        self,
        roster_info: Optional[Dict[str, Any]],
        header_bindings: List[Dict[str, Any]],
        placeholders: List[Dict[str, Any]],
    ) -> int:
        """
        Calculates confidence score 0 - 100.
        """
        score = 0

        # Roster table detection (up to 45 pts)
        if roster_info:
            score += 25
            if roster_info.get("name_col") is not None:
                score += 10
            if roster_info.get("id_col") is not None:
                score += 10

        # Header bindings detection (up to 45 pts)
        bound_fields = {b["field"] for b in header_bindings} | {p["field"] for p in placeholders}
        core_fields = {"instructor", "course_section", "schedule_code", "subject"}
        found_core = bound_fields.intersection(core_fields)

        score += min(len(found_core) * 10, 40)
        if "semester_ay" in bound_fields or "time_days_room" in bound_fields:
            score += 5

        # Suffix / structure (10 pts)
        score += 10

        return min(max(score, 0), 100)
