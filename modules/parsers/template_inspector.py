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

from modules.common.logger import logger
from modules.common.docx_utils import load_docx, get_full_text, w
from modules.models.recipe import (
    TemplateError,
    GeneratorProfile,
    PROFILE_REGISTRY,
    PROFILE_ACADEMIC_DOCX,
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

        # 1. Inspect Tables
        for t_idx, tbl in enumerate(tables):
            rows = tbl.findall(w("tr"))
            if not rows:
                continue

            # Check if this table is the student roster table
            r_info = self._detect_roster_table(tbl, t_idx)
            if r_info and roster_candidate is None:
                roster_candidate = r_info
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
                first_data_row = r_idx + 1
                total_cols = len(rows[first_data_row].findall(w("tc"))) if first_data_row < len(rows) else len(cells)
                capacity_limit = len(rows) - first_data_row

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "table_index": table_index,
                        "header_row_index": r_idx,
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
                    }

        return best_candidate

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
# XlsxTemplateInspector Skeleton (To be extended in Stage 6)
# ═══════════════════════════════════════════════════════════════════════════════

class XlsxTemplateInspector:
    """
    Analyzes Excel (.xlsx) templates and emits candidate observations.
    CRITICAL: inspect() returns RawTemplateRecipeCandidate.
    XlsxTemplateInspector NEVER constructs or returns ValidatedTemplateRecipe.
    """

    def inspect(
        self,
        template_path: str,
        profile_id: str = "grade_sheet_xlsx",
    ) -> RawTemplateRecipeCandidate:
        """
        Inspects an Excel grading template and returns raw candidate observations.
        Full implementation integrated in Stage 6.
        """
        import openpyxl

        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")

        with open(template_path, "rb") as f:
            fingerprint = hashlib.sha256(f.read()).hexdigest()

        wb = openpyxl.load_workbook(template_path, data_only=True)
        sheet_names = [s.lower() for s in wb.sheetnames]
        name_map = {s.lower(): s for s in wb.sheetnames}

        if "lecture" not in sheet_names:
            raise TemplateError("Missing required 'Lecture' sheet in grading template")

        ws = wb[name_map["lecture"]]
        is_lab = "laboratory" in sheet_names

        # Header candidates
        header_candidates = [
            {"cell_type": "xlsx_cell", "target": "C1", "field": "schedule_code", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "C2", "field": "subject_code", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M2", "field": "semester", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "C3", "field": "subject_title", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M3", "field": "school_year", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "C4", "field": "units", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M4", "field": "instructor", "confidence": 1.0},
        ]

        # Roster candidates: row 12 for lab, row 11 for lecture only
        first_row = 12 if is_lab else 11
        capacity = 40
        roster_candidate = {
            "table_index": 0,
            "first_data_row_index": first_row,
            "name_col": 2,
            "id_col": 3,
            "capacity_limit": capacity,
            "has_split_names": False,
        }

        # Signature candidates
        signature_candidates = []
        if is_lab:
            signature_candidates.append({
                "role": "instructor_signature",
                "target": "BI57",
                "confidence": 0.95,
            })
            signature_candidates.append({
                "role": "lab_instructor_signature",
                "target": "AO59",
                "confidence": 0.95,
            })

        return RawTemplateRecipeCandidate(
            template_path=template_path,
            profile_id=profile_id,
            fingerprint=fingerprint,
            roster_candidate=roster_candidate,
            header_candidates=header_candidates,
            signature_candidates=signature_candidates,
            collisions=[],
            metadata={"is_lab": is_lab, "capacity": capacity},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Backward-Compatibility Facade: TemplateInspector
# ═══════════════════════════════════════════════════════════════════════════════

class TemplateInspector:
    """
    Backward-compatibility facade matching the legacy TemplateInspector interface.
    Internally delegates to DocxTemplateInspector -> RecipeValidator.
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

    def inspect(self, template_path: str) -> Dict[str, Any]:
        """Legacy inspect() method returning a dictionary representation."""
        return self.inspect_docx(template_path)

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
