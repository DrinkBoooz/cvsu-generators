#!/usr/bin/env python3
"""
modules/parsers/template_inspector.py

Authoritative Template Inspectors and Compatibility Facade.
DocxTemplateInspector and XlsxTemplateInspector emit RawTemplateRecipeCandidate ONLY.
Inspectors NEVER construct or return ValidatedTemplateRecipe.
RecipeValidator owns validation authority.
"""

import os
import re
import hashlib
from typing import Dict, Any, List, Optional, Tuple

import openpyxl
from openpyxl.utils import get_column_letter

from modules.common.logger import logger
from modules.common.docx_utils import load_docx, get_full_text, w
from modules.models.recipe import (
    TemplateError,
    GeneratorProfile,
    PROFILE_REGISTRY,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    RawTemplateRecipeCandidate,
    ValidatedTemplateRecipe,
)
from modules.parsers.semantic_registry import (
    SemanticRegistry,
    FIELD_INSTRUCTOR,
    FIELD_COURSE_SECTION,
    FIELD_SCHEDULE_CODE,
    FIELD_SUBJECT,
    FIELD_SEMESTER_AY,
    FIELD_DATE,
    FIELD_TIME_DAYS_ROOM,
    ROLE_INSTRUCTOR_SIGNATURE,
)
from modules.parsers.recipe_validator import RecipeValidator


# Standard font shrink thresholds matching CvSU form specs
FIELD_SHRINK_THRESHOLDS = {
    "instructor": 30,
    "course_section": 0,
    "schedule_code": 0,
    "subject": 40,
    "time_days_room": 0,
    "semester_ay": 0,
    "date": 0,
}


# ═══════════════════════════════════════════════════════════════════════════════
# DocxTemplateInspector
# ═══════════════════════════════════════════════════════════════════════════════

class DocxTemplateInspector:
    """
    Analyzes Word (.docx) templates and emits candidate observations.
    CRITICAL: inspect() returns RawTemplateRecipeCandidate.
    DocxTemplateInspector NEVER constructs or returns ValidatedTemplateRecipe.
    """

    def inspect(
        self,
        template_path: str,
        profile_id: str = "academic_docx",
    ) -> RawTemplateRecipeCandidate:
        """
        Inspects a Word (.docx) template file and produces raw candidate observations.
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")

        zin, root, body = load_docx(template_path)
        zin.close()
        tables = body.findall(w("tbl"))
        paragraphs = body.findall(w("p"))

        # Compute file fingerprint
        with open(template_path, "rb") as f:
            fingerprint = hashlib.sha256(f.read()).hexdigest()

        header_candidates: List[Dict[str, Any]] = []
        signature_candidates: List[Dict[str, Any]] = []
        roster_candidate: Optional[Dict[str, Any]] = None

        total_tables = len(tables)

        # 0. Check all tables to detect candidate roster tables
        candidate_roster_tables = []
        for t_idx, tbl in enumerate(tables):
            r_info = self._detect_roster_table(tbl, t_idx)
            if r_info:
                candidate_roster_tables.append(r_info)

        if len(candidate_roster_tables) > 1:
            best_score = max(c.get("score", 0) for c in candidate_roster_tables)
            top_candidates = [c for c in candidate_roster_tables if c.get("score", 0) == best_score]
            if len(top_candidates) > 1:
                raise TemplateError(
                    f"Multiple candidate roster tables detected in '{os.path.basename(template_path)}': "
                    f"tables {[c['table_index'] for c in top_candidates]}. Ambiguous roster tables detected."
                )
            roster_candidate = top_candidates[0]
        elif candidate_roster_tables:
            roster_candidate = candidate_roster_tables[0]
        else:
            roster_candidate = None

        # 1. Inspect Table Cells for Metadata and Signatures
        for t_idx, tbl in enumerate(tables):
            if roster_candidate and t_idx == roster_candidate["table_index"]:
                continue

            rows = tbl.findall(w("tr"))
            if not rows:
                continue

            # Otherwise, inspect table cells for metadata and signatures
            total_rows = len(rows)
            for r_idx, row in enumerate(rows):
                cells = row.findall(w("tc"))
                for c_idx, cell in enumerate(cells):
                    text = SemanticRegistry.normalize_text(get_full_text(cell))
                    if not text:
                        continue

                    # Determine if cell is in signature context
                    is_sig = SemanticRegistry.is_signature_context(
                        text,
                        table_index=t_idx,
                        total_tables=total_tables,
                        row_index=r_idx,
                        total_rows=total_rows,
                    )

                    # Determine value cell adjacent to label cell
                    if len(cells) == 2:
                        target_c_idx = 1
                    elif len(cells) >= 3 and c_idx == 0:
                        cell1_txt = SemanticRegistry.normalize_text(get_full_text(cells[1]))
                        if cell1_txt == ":":
                            target_c_idx = 2
                        else:
                            target_c_idx = 1
                    elif c_idx + 1 < len(cells):
                        target_c_idx = c_idx + 1
                    else:
                        target_c_idx = c_idx

                    # Metadata candidate
                    meta_matches = SemanticRegistry.match_metadata_candidate(text, is_signature_region=is_sig)
                    for field_name, conf in meta_matches:
                        header_candidates.append({
                            "cell_type": "docx_table",
                            "target": (t_idx, r_idx, target_c_idx),
                            "field": field_name,
                            "confidence": conf,
                            "pattern": text,
                            "shrink_threshold": FIELD_SHRINK_THRESHOLDS.get(field_name, 0),
                            "shrink_sz": "18",
                            "is_signature_region": is_sig,
                        })

                    # Signature candidate
                    sig_matches = SemanticRegistry.match_signature_candidate(
                        text,
                        in_signature_table=is_sig,
                        relative_vertical_pos=float(r_idx) / max(total_rows, 1),
                    )
                    for role_name, conf in sig_matches:
                        signature_candidates.append({
                            "role": role_name,
                            "target": (t_idx, r_idx, c_idx),
                            "confidence": conf,
                        })

        # 2. Inspect Paragraphs (Outside tables)
        for p_idx, p in enumerate(paragraphs):
            text = SemanticRegistry.normalize_text(get_full_text(p))
            if not text:
                continue

            # Skip paragraphs that contain explicit template tags (handled by placeholder engine)
            if "{{" in text or "}}" in text or "[[" in text or "]]" in text:
                continue

            # Split paragraph into segments if delimited by '|' or ';'
            segments = [s.strip() for s in re.split(r'[|;]', text)]
            for seg in segments:
                if ":" in seg:
                    lbl_part, _ = seg.split(":", 1)
                    lbl_norm = SemanticRegistry.normalize_text(lbl_part)
                    meta_matches = SemanticRegistry.match_metadata_candidate(lbl_norm, is_signature_region=False)
                    for field_name, conf in meta_matches:
                        header_candidates.append({
                            "cell_type": "docx_paragraph",
                            "target": p_idx,
                            "field": field_name,
                            "confidence": conf * 0.9,
                            "pattern": lbl_norm,
                            "shrink_threshold": FIELD_SHRINK_THRESHOLDS.get(field_name, 0),
                            "shrink_sz": "18",
                            "is_signature_region": False,
                        })

        # 3. Detect explicit placeholder tokens {{...}} or [...]
        placeholders = self._detect_placeholders(body)

        # 4. Observe collisions
        collisions = SemanticRegistry.observe_collisions(header_candidates)

        # 5. Generate title, suffix, and confidence
        title, suffix = self._suggest_title_and_suffix(template_path, paragraphs)
        confidence_score = self._compute_confidence(roster_candidate, header_candidates, placeholders=placeholders)

        metadata = {
            "title": title,
            "suffix": suffix,
            "confidence": confidence_score,
            "total_tables": total_tables,
            "total_paragraphs": len(paragraphs),
            "placeholders": placeholders,
        }

        return RawTemplateRecipeCandidate(
            template_path=template_path,
            profile_id=profile_id,
            fingerprint=fingerprint,
            roster_candidate=roster_candidate,
            header_candidates=header_candidates,
            signature_candidates=signature_candidates,
            collisions=collisions,
            metadata=metadata,
        )

    def _detect_placeholders(self, body: Any) -> List[Dict[str, Any]]:
        """Finds explicit template tags like {{INSTRUCTOR}} or [INSTRUCTOR]."""
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

    def _detect_roster_table(self, tbl, table_index: int) -> Optional[Dict[str, Any]]:
        """
        Detects whether a table is a student roster table by examining header columns.
        """
        rows = tbl.findall(w("tr"))
        if len(rows) < 2:
            return None

        best_score = 0
        best_candidate = None

        # Check rows 0, 1, and 2 for header labels
        for r_idx in range(min(3, len(rows))):
            cells = rows[r_idx].findall(w("tc"))
            if not cells:
                continue

            name_col = None
            id_col = None
            index_col = None
            sig_col = None
            score = 0

            for c_idx, cell in enumerate(cells):
                txt = SemanticRegistry.normalize_text(get_full_text(cell)).lower()
                cleaned = re.sub(r"[^a-z0-9#\.\s]", " ", txt).strip()
                words = set(cleaned.split())

                is_id = any(tok in cleaned for tok in ("student number", "id number", "stud no", "student no", "stud. no", "student id", "studentnumber", "id no", "id.", "numero", "lrn")) or bool(words & {"lrn", "numero", "id"})
                is_index = any(tok in words for tok in ("no", "no.", "#", "item", "bilang", "index")) or cleaned.startswith("#") or cleaned.startswith("no")
                is_sig = any(tok in cleaned for tok in ("signature", "lagda", "sign", "remarks", "grade", "initial", "status", "action taken", "concern", "pirma"))
                is_name = any(tok in cleaned for tok in ("name", "pangalan", "student's name", "name of student", "name of students")) or ("student" in words and not is_id)

                if id_col is None and is_id:
                    id_col = c_idx
                    score += 3
                elif index_col is None and is_index:
                    index_col = c_idx
                    score += 1
                elif sig_col is None and is_sig:
                    sig_col = c_idx
                    score += 1
                elif name_col is None and is_name:
                    name_col = c_idx
                    score += 3

            if name_col is not None and (id_col is not None or sig_col is not None):
                # Scan subsequent rows for secondary header rows (multi-row headers)
                header_row_count = 1
                curr_r = r_idx + 1
                while curr_r < min(r_idx + 4, len(rows)):
                    cand_tr = rows[curr_r]
                    cand_cells = cand_tr.findall(w("tc"))
                    if not cand_cells:
                        break

                    if self._is_secondary_header_row(
                        cand_tr, cand_cells, name_col, id_col, index_col
                    ):
                        header_row_count += 1
                        curr_r += 1
                    else:
                        break

                first_data_row = r_idx + header_row_count
                total_cols = len(rows[first_data_row].findall(w("tc"))) if first_data_row < len(rows) else len(cells)
                capacity_limit = len(rows) - first_data_row

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "table_index": table_index,
                        "header_row_index": r_idx,
                        "header_row_count": header_row_count,
                        "template_row_index": first_data_row,
                        "first_data_row": first_data_row,
                        "first_data_row_index": first_data_row,
                        "name_col": name_col,
                        "id_col": id_col if id_col is not None else 1,
                        "index_col": index_col,
                        "signature_col": sig_col,
                        "total_cols": total_cols,
                        "total_rows": len(rows),
                        "capacity_limit": capacity_limit if capacity_limit > 0 else 50,
                        "has_split_names": False,
                        "score": best_score,
                    }

        return best_candidate

    def _is_secondary_header_row(
        self,
        tr_elem: Any,
        cells: List[Any],
        name_col: int,
        id_col: Optional[int],
        index_col: Optional[int],
    ) -> bool:
        """
        Determines whether a subsequent row is a secondary/continuation header row
        or a template data row.

        Signals combined:
          1. Explicit Word header marker (<w:tblHeader/>).
          2. Student data presence (rejects header classification).
          3. Blank row presence (blank row without <w:tblHeader/> is treated as data template row, NOT header).
          4. Semantic/header continuation markers in non-name/id columns or subheader keywords.
        """
        # 1. Explicit Word header element
        trPr = tr_elem.find(w("trPr"))
        has_tbl_header = False
        if trPr is not None and trPr.find(w("tblHeader")) is not None:
            has_tbl_header = True

        # Extract normalized cell text
        cell_texts = [SemanticRegistry.normalize_text(get_full_text(c)) for c in cells]

        # Check if row is completely blank (all cells empty or whitespace)
        all_blank = all(not t for t in cell_texts)
        if all_blank:
            # A blank row without explicit Word tblHeader is a data template row, NOT a header
            return has_tbl_header

        # 2. Check for student data in id_col or name_col
        # Check student ID patterns in id_col
        if id_col is not None and id_col < len(cell_texts):
            id_txt = cell_texts[id_col].strip()
            clean_digits = re.sub(r"[^\d]", "", id_txt)
            if len(clean_digits) >= 5:
                return False  # Real student ID present, definitely data row

        # Check real student name in name_col
        if name_col < len(cell_texts):
            name_txt = cell_texts[name_col].strip()
            if name_txt:
                lower_name = name_txt.lower()
                is_header_kw = any(kw in lower_name for kw in ("name", "student", "signature", "date", "no.", "no"))
                if "," in name_txt and not is_header_kw and len(name_txt) > 3:
                    return False  # Real student name with comma, definitely data row

        # Check index_col for numbered template row (e.g. '1', '2')
        if index_col is not None and index_col < len(cell_texts):
            idx_txt = cell_texts[index_col].strip()
            if idx_txt.isdigit() and int(idx_txt) >= 1:
                # Check if any other cell has distinct subheader keywords
                has_header_keywords = False
                for c_idx, txt in enumerate(cell_texts):
                    if c_idx == index_col:
                        continue
                    clean_w = set(re.sub(r"[^a-z0-9]", " ", txt.lower()).split())
                    if clean_w & {"date", "day", "days", "week", "weel", "time", "score", "quiz", "exam", "lab", "lec", "remarks"}:
                        has_header_keywords = True
                        break
                if not has_header_keywords and not has_tbl_header:
                    return False  # Pre-numbered row template (e.g. '1', '', '', '')

        # If explicit Word header marker is present, trust it
        if has_tbl_header:
            return True

        # 3. Semantic subheader keywords in other columns
        SUBHEADER_KEYWORDS = {
            "date", "day", "days", "week", "weel", "time", "room", "score", "quiz",
            "exam", "lab", "lec", "lecture", "laboratory", "remarks", "remark",
            "signature", "sig", "total", "subtotal", "grade", "equivalent",
            "status", "initial", "item", "items", "unit", "units", "hours", "hrs",
            "topic", "criteria", "percentage", "m", "f", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
            "first", "last", "middle", "suffix", "period", "month", "year"
        }

        # Check non-name/id cells (or sub-divided header cells) for subheader keywords
        for c_idx, txt in enumerate(cell_texts):
            clean_txt = re.sub(r"[^a-z0-9]", " ", txt.lower()).strip()
            words = set(clean_txt.split())
            if words & SUBHEADER_KEYWORDS:
                return True

        # Check vertical merge continuation (vMerge without val="restart")
        has_vmerge_continuation = False
        for c in cells:
            tcPr = c.find(w("tcPr"))
            if tcPr is not None:
                vm = tcPr.find(w("vMerge"))
                if vm is not None:
                    val = vm.attrib.get(w("val"), "")
                    if val != "restart":
                        has_vmerge_continuation = True
                        break

        if has_vmerge_continuation and not any(len(re.sub(r"[^\d]", "", t)) >= 5 for t in cell_texts):
            return True

        return False

    def _suggest_title_and_suffix(self, template_path: str, paragraphs: List[Any]) -> Tuple[str, str]:
        """Infers document title and file suffix from filename or top paragraphs."""
        basename = os.path.splitext(os.path.basename(template_path))[0]
        clean_name = re.sub(r"^(?:template_|cvsu_|form_)", "", basename, flags=re.IGNORECASE)
        clean_name = re.sub(r"[-_\s]+", "_", clean_name).strip("_")

        title = clean_name.replace("_", " ").title()
        suffix = clean_name.upper()

        for p in paragraphs[:5]:
            txt = SemanticRegistry.normalize_text(get_full_text(p))
            if 5 < len(txt) < 80:
                upper = txt.upper()
                if any(k in upper for k in ("FORM", "ACCEPTANCE", "DISCUSSION", "ACKNOWLEDGMENT", "RETURNS", "RECORD", "LOG", "REPORT")):
                    title = txt.title()
                    sub_suffix = re.sub(r"[^A-Za-z0-9\s]", "", upper)
                    tokens = [t for t in sub_suffix.split() if t not in ("OF", "THE", "AND", "FOR", "CVSU", "CEIT")]
                    if tokens:
                        suffix = "_".join(tokens[:4])
                    break

        return title, suffix

    def _compute_confidence(
        self,
        roster_info: Optional[Dict[str, Any]],
        header_candidates: List[Dict[str, Any]],
        placeholders: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Calculates discovery confidence score 0 - 100."""
        score = 0
        if roster_info:
            score += 25
            if roster_info.get("name_col") is not None:
                score += 10
            if roster_info.get("id_col") is not None:
                score += 10

        bound_fields = {c["field"] for c in header_candidates}
        if placeholders:
            for p in placeholders:
                if "field" in p:
                    bound_fields.add(p["field"])

        core_fields = {"instructor", "course_section", "schedule_code", "subject"}
        found_core = bound_fields.intersection(core_fields)
        score += min(len(found_core) * 10, 40)

        if "semester_ay" in bound_fields or "time_days_room" in bound_fields:
            score += 5
        score += 10  # baseline structure score

        return min(max(score, 0), 100)



# ═══════════════════════════════════════════════════════════════════════════════
# XlsxTemplateInspector
# ═══════════════════════════════════════════════════════════════════════════════

class XlsxTemplateInspector:
    """
    Analyzes Excel (.xlsx) grading sheet templates and emits candidate observations.
    CRITICAL: inspect() returns RawTemplateRecipeCandidate ONLY.
    XlsxTemplateInspector NEVER constructs or returns ValidatedTemplateRecipe.
    RecipeValidator owns final validation and construction authority.
    """

    def inspect(
        self,
        template_path: str,
        profile_id: str = "grade_sheet_xlsx",
    ) -> RawTemplateRecipeCandidate:
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")

        with open(template_path, "rb") as f:
            fingerprint = hashlib.sha256(f.read()).hexdigest()

        wb = openpyxl.load_workbook(template_path, data_only=True)
        sheet_names = wb.sheetnames
        sheet_map = {s.lower().strip(): s for s in sheet_names}

        if "lecture" not in sheet_map:
            raise TemplateError(
                f"Grade sheet template '{os.path.basename(template_path)}' is missing required 'Lecture' worksheet."
            )
        if "grading sheet" not in sheet_map:
            raise TemplateError(
                f"Grade sheet template '{os.path.basename(template_path)}' is missing required 'Grading Sheet' worksheet."
            )

        ws_lec = wb[sheet_map["lecture"]]
        header_candidates: List[Dict[str, Any]] = []
        signature_candidates: List[Dict[str, Any]] = []
        roster_candidate: Optional[Dict[str, Any]] = None

        # 1. Header Metadata Discovery in Lecture sheet (rows 1-6, cols 1-20)
        lec_merges = list(ws_lec.merged_cells.ranges)

        def find_target_for_label(row_idx: int, col_idx: int) -> str:
            row_merges = [
                m for m in lec_merges
                if m.min_row == row_idx and m.min_col > col_idx
            ]
            if row_merges:
                closest_merge = min(row_merges, key=lambda m: m.min_col)
                return f"{get_column_letter(closest_merge.min_col)}{closest_merge.min_row}"
            return f"{get_column_letter(col_idx + 1)}{row_idx}"

        for r in range(1, 7):
            for c in range(1, 20):
                val = ws_lec.cell(r, c).value
                if not val or not isinstance(val, str):
                    continue
                text = val.strip()
                if not text:
                    continue

                matches = SemanticRegistry.match_metadata_candidate(text)
                if matches:
                    matched_field, conf = matches[0]
                    target_coord = find_target_for_label(r, c)
                    header_candidates.append({
                        "cell_type": "xlsx_cell",
                        "target": target_coord,
                        "field": matched_field,
                        "confidence": conf,
                        "pattern": text,
                        "label_cell": ws_lec.cell(r, c).coordinate,
                        "is_signature_region": False,
                    })

        # 2. Institutional College Banner Discovery (Grading Sheet!A9)
        if "grading sheet" in sheet_map:
            ws_grd = wb[sheet_map["grading sheet"]]
            for r in range(1, 15):
                for c in range(1, 10):
                    val = ws_grd.cell(r, c).value
                    if val and isinstance(val, str) and "COLLEGE OF" in val.upper():
                        header_candidates.append({
                            "cell_type": "xlsx_cell",
                            "target": f"{sheet_map['grading sheet']}!{ws_grd.cell(r, c).coordinate}",
                            "field": "college",
                            "confidence": 1.0,
                            "pattern": val.strip(),
                            "label_cell": None,
                            "is_signature_region": False,
                        })
                        break

        # 3. Roster Table Discovery in Lecture sheet
        header_row = None
        index_col = None
        name_col = None
        id_col = None

        for r in range(6, 16):
            for c in range(1, 10):
                c_val = ws_lec.cell(r, c).value
                if not c_val or not isinstance(c_val, str):
                    continue
                norm_c = c_val.strip().lower()
                if norm_c in ("#", "no.", "no", "item"):
                    index_col = c
                    header_row = r
                elif "student name" in norm_c or "name of student" in norm_c or "surname" in norm_c:
                    name_col = c
                elif "student number" in norm_c or "student no" in norm_c or "id number" in norm_c or "id no" in norm_c:
                    id_col = c

            if header_row is not None and name_col is not None and id_col is not None:
                break

        if header_row is not None and name_col is not None and id_col is not None:
            first_data_row = None
            capacity_limit = 0

            check_col = index_col if index_col is not None else 1
            for r in range(header_row + 1, header_row + 20):
                v = ws_lec.cell(r, check_col).value
                if v == 1 or str(v).strip() == "1":
                    first_data_row = r
                    break

            if first_data_row is not None:
                expected_num = 1
                curr_r = first_data_row
                while True:
                    v = ws_lec.cell(curr_r, check_col).value
                    if v == expected_num or str(v).strip() == str(expected_num):
                        capacity_limit += 1
                        expected_num += 1
                        curr_r += 1
                    else:
                        break

            if first_data_row is not None and capacity_limit > 0:
                roster_candidate = {
                    "table_index": 0,
                    "first_data_row_index": first_data_row,
                    "name_col": name_col,
                    "id_col": id_col,
                    "index_col": index_col,
                    "capacity_limit": capacity_limit,
                    "has_split_names": False,
                }

        # 4. Scope-Aware Signature Box Discovery (Structural geometry, Mutation M8 compliant)
        def find_signature_target(ws, sheet_display_name: str, scope_name: str) -> Optional[Dict[str, Any]]:
            label_rng = None
            for rng in ws.merged_cells.ranges:
                top_val = ws.cell(rng.min_row, rng.min_col).value
                if top_val and isinstance(top_val, str) and "INSTRUCTOR" in top_val.upper():
                    label_rng = rng
                    break

            if not label_rng:
                for r in range(40, min(ws.max_row + 1, 100)):
                    for c in range(1, min(ws.max_column + 1, 80)):
                        v = ws.cell(r, c).value
                        if v and isinstance(v, str) and "INSTRUCTOR" in v.upper():
                            return {
                                "role": "instructor" if scope_name == "lecture" else f"instructor:{scope_name}",
                                "scope": scope_name,
                                "target": f"{get_column_letter(c)}{r - 3}",
                                "confidence": 0.85,
                                "derivation_evidence": "proximity_above",
                            }
                return None

            for rng in ws.merged_cells.ranges:
                if rng.min_col == label_rng.min_col and rng.max_col == label_rng.max_col:
                    if rng.max_row == label_rng.min_row - 1:
                        target_cell = f"{get_column_letter(rng.min_col)}{rng.min_row}"
                        return {
                            "role": "instructor" if scope_name == "lecture" else f"instructor:{scope_name}",
                            "scope": scope_name,
                            "target": target_cell,
                            "confidence": 1.0,
                            "derivation_evidence": "structural_merged_box_above_label",
                        }

            fallback_cell = f"{get_column_letter(label_rng.min_col)}{label_rng.min_row - 3}"
            return {
                "role": "instructor" if scope_name == "lecture" else f"instructor:{scope_name}",
                "scope": scope_name,
                "target": fallback_cell,
                "confidence": 0.90,
                "derivation_evidence": "offset_above_label",
            }

        lec_sig = find_signature_target(ws_lec, sheet_map["lecture"], "lecture")
        if lec_sig:
            signature_candidates.append(lec_sig)
            signature_candidates.append({
                "role": ROLE_INSTRUCTOR_SIGNATURE,
                "scope": "lecture",
                "target": lec_sig["target"],
                "confidence": lec_sig["confidence"],
                "derivation_evidence": lec_sig["derivation_evidence"],
            })

        if "laboratory" in sheet_map:
            lab_sig = find_signature_target(wb[sheet_map["laboratory"]], sheet_map["laboratory"], "laboratory")
            if lab_sig:
                signature_candidates.append(lab_sig)

        if "consolidated" in sheet_map:
            con_sig = find_signature_target(wb[sheet_map["consolidated"]], sheet_map["consolidated"], "consolidated")
            if con_sig:
                signature_candidates.append(con_sig)

        return RawTemplateRecipeCandidate(
            template_path=template_path,
            profile_id=profile_id,
            fingerprint=fingerprint,
            roster_candidate=roster_candidate,
            header_candidates=header_candidates,
            signature_candidates=signature_candidates,
            collisions=[],
            metadata={
                "sheet_names": sheet_names,
                "has_lab": "laboratory" in sheet_map,
                "has_consolidated": "consolidated" in sheet_map,
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Backward-Compatibility Facade: TemplateInspector
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateInspector:
    """
    Backward-compatibility facade matching the legacy TemplateInspector interface.
    Internally delegates to DocxTemplateInspector / XlsxTemplateInspector -> RecipeValidator.
    """

    CANONICAL_ACADEMIC_TEMPLATES = {
        "template_syllabus.docx",
        "template_exam_midterm.docx",
        "template_exam_finals.docx",
        "template_tos_midterm.docx",
        "template_tos_finals.docx",
        "Midterm-Grade-Discussion_LATEST.docx",
        "Final-Grade-Discussion_LATEST.docx",
    }

    def __init__(self):
        self._docx_inspector = DocxTemplateInspector()
        self._xlsx_inspector = XlsxTemplateInspector()

    def inspect(self, template_path: str) -> Dict[str, Any]:
        """Legacy inspect() method returning a dictionary representation."""
        if template_path.lower().endswith((".xlsx", ".xls")):
            return self.inspect_xlsx(template_path)
        return self.inspect_docx(template_path)

    def inspect_xlsx(self, template_path: str, profile_id: str = "grade_sheet_xlsx") -> Dict[str, Any]:
        candidate = self._xlsx_inspector.inspect(template_path, profile_id=profile_id)
        profile = PROFILE_REGISTRY.get(profile_id, PROFILE_GRADE_SHEET_XLSX)
        validated_recipe = RecipeValidator.validate(candidate, profile)
        return validated_recipe.to_dict()

    def inspect_xlsx_recipe(
        self,
        template_path: str,
        profile_id: str = "grade_sheet_xlsx",
    ) -> ValidatedTemplateRecipe:
        """Public API returning an authoritative ValidatedTemplateRecipe for XLSX."""
        candidate = self._xlsx_inspector.inspect(template_path, profile_id=profile_id)
        profile = PROFILE_REGISTRY.get(profile_id, PROFILE_GRADE_SHEET_XLSX)
        return RecipeValidator.validate(candidate, profile)

    def inspect_docx(self, template_path: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspects a Word (.docx) file and returns a dictionary matching the legacy API format.
        Internally runs DocxTemplateInspector -> RecipeValidator -> legacy dict format.
        """
        base = os.path.basename(template_path)
        if profile_id is None:
            profile_id = "academic_docx" if base in self.CANONICAL_ACADEMIC_TEMPLATES else "custom_docx"

        candidate = self._docx_inspector.inspect(template_path, profile_id=profile_id)
        from modules.models.recipe import PROFILE_CUSTOM_DOCX
        profile = PROFILE_REGISTRY.get(profile_id, PROFILE_ACADEMIC_DOCX if profile_id == "academic_docx" else PROFILE_CUSTOM_DOCX)
        validated_recipe = RecipeValidator.validate(candidate, profile)

        # Build legacy format expected by existing tests and frontend
        roster_dict = None
        if validated_recipe.roster_binding:
            rb = validated_recipe.roster_binding
            roster_dict = {
                "table_index": rb.table_index,
                "first_data_row": rb.first_data_row_index,
                "first_data_row_index": rb.first_data_row_index,
                "name_col": rb.name_col,
                "id_col": rb.id_col,
                "index_col": candidate.roster_candidate.get("index_col") if candidate.roster_candidate else None,
                "signature_col": candidate.roster_candidate.get("signature_col") if candidate.roster_candidate else None,
                "total_cols": candidate.roster_candidate.get("total_cols", 4) if candidate.roster_candidate else 4,
                "total_rows": candidate.roster_candidate.get("total_rows", 50) if candidate.roster_candidate else 50,
                "capacity_limit": rb.capacity_limit or 50,
                "has_split_names": rb.has_split_names,
            }

        header_bindings_list = []
        detected_fields = []
        for field_name, b in validated_recipe.header_bindings.items():
            t = b.target
            if b.cell_type == "docx_table" and isinstance(t, (tuple, list)) and len(t) == 3:
                legacy_b = {
                    "field": field_name,
                    "type": "table_cell",
                    "table_index": t[0],
                    "row_index": t[1],
                    "cell_index": t[2],
                    "shrink_threshold": b.shrink_threshold,
                    "shrink_sz": b.shrink_sz,
                }
            elif b.cell_type == "docx_paragraph":
                legacy_b = {
                    "field": field_name,
                    "type": "paragraph_colon",
                    "para_index": t,
                    "shrink_threshold": b.shrink_threshold,
                    "shrink_sz": b.shrink_sz,
                }
            else:
                legacy_b = b.to_dict()
            header_bindings_list.append(legacy_b)
            detected_fields.append(field_name)

        confidence = candidate.metadata.get("confidence", 95)
        placeholders = candidate.metadata.get("placeholders", [])

        return {
            "template_path": template_path,
            "title": candidate.metadata.get("title", ""),
            "suffix": candidate.metadata.get("suffix", ""),
            "confidence": confidence,
            "summary": {
                "roster_table_found": roster_dict is not None,
                "detected_fields": detected_fields,
            },
            "roster_table": roster_dict,
            "header_bindings": header_bindings_list,
            "signature_bindings": [s.to_dict() for s in validated_recipe.signature_bindings.values()],
            "placeholders": placeholders,
            "schema_version": validated_recipe.schema_version,
            "fingerprint": validated_recipe.fingerprint,
        }

    def inspect_docx_recipe(
        self,
        template_path: str,
        profile_id: str = "academic_docx",
    ) -> ValidatedTemplateRecipe:
        """
        Public API returning an authoritative ValidatedTemplateRecipe.
        """
        candidate = self._docx_inspector.inspect(template_path, profile_id=profile_id)
        profile = PROFILE_REGISTRY.get(profile_id, PROFILE_ACADEMIC_DOCX)
        return RecipeValidator.validate(candidate, profile)
