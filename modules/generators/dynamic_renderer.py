#!/usr/bin/env python3
"""
modules/generators/dynamic_renderer.py

Unified Dynamic Document Rendering Engine.
Populates Word (.docx) and Excel (.xlsx) templates driven by
DeterministicTemplateAnalyzer and DocxGridTable without hardcoded indices.

Features:
  - Dynamic slot resolution across body paragraphs, tables, and header/footer stories
  - Strict preservation of OpenXML run/paragraph formatting (<w:rPr>, <w:pPr>, <w:tcPr>, fonts, bold, shading)
  - Dynamic repeating table population for student rosters, attendance matrices, and exam return tables
  - Dynamic student name font scaling ladder (<=30 -> 8pt, 31-35 -> 7pt, >35 -> 6pt)
  - Preservation of native list auto-numbering (<w:numPr>) in index columns
  - Preservation of footer rows (totals, signatures, notes) in repeating tables
  - Full structural perturbation resilience (extra decoy tables or prepended paragraphs do not corrupt bindings)
"""

from __future__ import annotations

import copy
import os
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple, Union
from lxml import etree
import openpyxl

from modules.common.logger import logger
from modules.common.docx_utils import (
    load_docx,
    save_docx,
    w,
    get_full_text,
    set_cell_text,
    replace_after_colon,
)
from modules.models.schedule import ClassInfo
from modules.parsers.docx_grid_table import DocxGridTable, DocxGridCell
from modules.models.organization import SignatorySlot
from modules.parsers.template_analyzer import (
    DeterministicTemplateAnalyzer,
    TemplateManifest,
    SemanticSlot,
    RepeatingTableTopology,
)


class DynamicDocumentRenderer:
    """
    Unified Dynamic Document Rendering Engine.
    Executes style-preserving template population driven by DeterministicTemplateAnalyzer
    and DocxGridTable.
    """

    def __init__(self, analyzer: Optional[DeterministicTemplateAnalyzer] = None):
        self.analyzer = analyzer or DeterministicTemplateAnalyzer()

    def render(
        self,
        doc_or_path: Union[str, Tuple[zipfile.ZipFile, etree._Element, etree._Element]],
        data_context: Union[ClassInfo, Dict[str, Any]],
        output_path: Optional[str] = None,
        manifest: Optional[TemplateManifest] = None,
    ) -> Union[str, Tuple[zipfile.ZipFile, etree._Element, etree._Element]]:
        """
        Unified entry point: renders either .docx or .xlsx templates.

        Args:
            doc_or_path: Filepath string or loaded (zin, root, body) tuple for docx.
            data_context: ClassInfo or dictionary containing metadata and student list.
            output_path: Target path to serialize the generated file.
            manifest: Optional precomputed TemplateManifest.

        Returns:
            The output_path string if supplied, or the loaded docx tuple.
        """
        if isinstance(doc_or_path, str):
            ext = os.path.splitext(doc_or_path)[1].lower()
            if ext in (".xlsx", ".xls", ".xlsm"):
                return self.render_xlsx(doc_or_path, data_context, output_path=output_path, manifest=manifest)
        return self.render_docx(doc_or_path, data_context, output_path=output_path, manifest=manifest)

    def _get_context_val(self, field_name: str, context: Union[ClassInfo, Dict[str, Any]]) -> Optional[str]:
        """Resolves field value from ClassInfo instance or dictionary."""
        if isinstance(context, ClassInfo):
            mapping = {
                "instructor": context.instructor,
                "course_section": context.course_section,
                "schedule_code": context.schedule_code,
                "subject": context.subject,
                "time_days_room": context.time_days_room,
                "semester_ay": context.semester_ay,
                "college": getattr(context, "college", ""),
            }
            if field_name in mapping:
                return mapping[field_name]
            return getattr(context, field_name, None)

        elif isinstance(context, dict):
            if field_name in context:
                return context[field_name]
            aliases = {
                "course_section": ["course_sec", "section"],
                "schedule_code": ["sched_code", "class_code"],
                "subject": ["subject_name", "course_title"],
                "time_days_room": ["schedule", "time_room", "time_days"],
                "semester_ay": ["semester", "ay"],
                "month_year": ["month", "month_label"],
            }
            for alias in aliases.get(field_name, []):
                if alias in context:
                    return context[alias]
        return None

    def render_docx(
        self,
        doc_or_path: Union[str, Tuple[zipfile.ZipFile, etree._Element, etree._Element]],
        data_context: Union[ClassInfo, Dict[str, Any]],
        output_path: Optional[str] = None,
        manifest: Optional[TemplateManifest] = None,
    ) -> Union[str, Tuple[zipfile.ZipFile, etree._Element, etree._Element]]:
        """
        Renders a Word (.docx) template using dynamic slot resolution and table population.
        """
        is_path = isinstance(doc_or_path, str)
        if is_path:
            zin, root, body = load_docx(doc_or_path)
            template_path = doc_or_path
        else:
            zin, root, body = doc_or_path
            template_path = getattr(zin, "filename", "") or ""

        # Analyze in-memory tree if manifest is None
        if manifest is None:
            manifest = self.analyzer.analyze_docx_tree(root, body, docx_path=template_path)

        tables = body.findall(w("tbl"))
        paras = body.findall(w("p"))

        # Topology shift guard: if table count or structure shifted, dynamically re-analyze
        if manifest.metadata_table_index is not None and (
            manifest.metadata_table_index >= len(tables)
            or len(tables) != len(manifest.repeating_tables) + (1 if manifest.metadata_table_index is not None else 0)
        ):
            manifest = self.analyzer.analyze_docx_tree(root, body, docx_path=template_path)
            tables = body.findall(w("tbl"))
            paras = body.findall(w("p"))

        # 1. Populate semantic metadata slots
        for slot in manifest.slots:
            val = self._get_context_val(slot.field, data_context)
            if val is None:
                continue

            str_val = str(val)

            if slot.slot_type == "table_cell":
                if slot.table_index is None or slot.table_index >= len(tables):
                    continue
                grid = DocxGridTable(tables[slot.table_index])
                t_r = slot.target_row_index
                t_c = slot.target_col_index
                if t_r is None or t_c is None or t_r >= grid.num_rows or t_c >= grid.num_cols:
                    continue

                if slot.strategy == "replace_after_colon":
                    canonical = grid.get_canonical_cell(t_r, t_c)
                    if canonical and canonical.tc is not None:
                        p = canonical.tc.find(w("p"))
                        if p is not None:
                            replace_after_colon(
                                p,
                                str_val,
                                shrink_threshold=slot.shrink_threshold,
                                shrink_sz=slot.shrink_size,
                            )
                else:
                    grid.set_cell_text(
                        t_r,
                        t_c,
                        str_val,
                        shrink_threshold=slot.shrink_threshold,
                        shrink_sz=slot.shrink_size,
                    )

            elif slot.slot_type == "paragraph_after_colon":
                if slot.paragraph_index is not None and slot.paragraph_index < len(paras):
                    p = paras[slot.paragraph_index]
                    replace_after_colon(
                        p,
                        str_val,
                        shrink_threshold=slot.shrink_threshold,
                        shrink_sz=slot.shrink_size,
                    )

            elif slot.slot_type == "tag_placeholder" or slot.placeholder_tag:
                tag = slot.placeholder_tag or f"{{{{{slot.field.upper()}}}}}"
                self._replace_tag_in_element(body, tag, str_val)

        # 2. Populate explicit template placeholders {{TAG}} / <TAG>
        if manifest.has_explicit_placeholders:
            for tag in manifest.explicit_placeholders:
                field_name = tag.strip("{}<>").lower()
                val = self._get_context_val(field_name, data_context)
                if val:
                    self._replace_tag_in_element(body, tag, str(val))

        # 3. Populate repeating table (student roster)
        roster_top = manifest.roster_table
        if roster_top is not None and roster_top.table_index < len(tables):
            tbl = tables[roster_top.table_index]
            rows = tbl.findall(w("tr"))
            first_data_idx = roster_top.first_data_row_index
            template_idx = roster_top.template_row_index

            if template_idx < len(rows) and first_data_idx <= len(rows):
                template_row = rows[template_idx]
                footer_rows = [rows[i] for i in roster_top.footer_row_indices if i < len(rows)]

                # Clear existing data rows
                for r in rows[first_data_idx:]:
                    tbl.remove(r)

                students = getattr(data_context, "students", None)
                if students is None and isinstance(data_context, dict):
                    students = data_context.get("students", [])
                students = students or []

                for idx, entry in enumerate(students):
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        name, stnum = str(entry[0]), str(entry[1])
                    elif isinstance(entry, dict):
                        name = str(entry.get("name", ""))
                        stnum = str(entry.get("student_number", entry.get("id", "")))
                    else:
                        name, stnum = str(entry), ""

                    tr = copy.deepcopy(template_row)
                    for tc in tr.findall(w("tc")):
                        for p in tc.findall(w("p")):
                            for r in p.findall(w("r")):
                                for t in r.findall(w("t")):
                                    t.text = ""
                    cells = tr.findall(w("tc"))
                    cols = roster_top.columns

                    # Preserves native numPr auto-numbering if present
                    if "index" in cols and cols["index"] < len(cells):
                        idx_tc = cells[cols["index"]]
                        has_numpr = any(
                            p.find(w("pPr")) is not None and p.find(w("pPr")).find(w("numPr")) is not None
                            for p in idx_tc.findall(w("p"))
                        )
                        if not has_numpr:
                            set_cell_text(idx_tc, str(idx + 1))

                    if "name" in cols and cols["name"] < len(cells):
                        set_cell_text(cells[cols["name"]], name, is_student_name=True)

                    if "student_number" in cols and cols["student_number"] < len(cells):
                        set_cell_text(cells[cols["student_number"]], stnum)

                    tbl.append(tr)

                for f_row in footer_rows:
                    tbl.append(f_row)

        # 4. Populate dynamic N-tier signatory slots
        if manifest.signatory_slots:
            self._populate_signatories_docx(tables, paras, manifest.signatory_slots, data_context)

        if output_path:
            save_docx(zin, root, output_path)
            logger.info(f"DynamicDocumentRenderer generated: {os.path.basename(output_path)}")
            return output_path
        return zin, root, body

    def render_xlsx(
        self,
        xlsx_path: str,
        data_context: Union[ClassInfo, Dict[str, Any]],
        output_path: Optional[str] = None,
        manifest: Optional[TemplateManifest] = None,
    ) -> str:
        """
        Renders an Excel (.xlsx) grading sheet template using dynamic cell resolution.
        """
        if not os.path.isfile(xlsx_path):
            raise FileNotFoundError(f"XLSX template not found: {xlsx_path}")

        if manifest is None:
            manifest = self.analyzer.analyze_xlsx(xlsx_path)

        wb = openpyxl.load_workbook(xlsx_path)

        # 1. Populate metadata header cells across worksheets
        for slot in manifest.slots:
            if slot.slot_type == "excel_cell" and slot.sheet_name and slot.cell_coord:
                val = self._get_context_val(slot.field, data_context)
                if val is not None and slot.sheet_name in wb.sheetnames:
                    ws = wb[slot.sheet_name]
                    ws[slot.cell_coord] = str(val)

        # 2. Populate student roster rows on designated worksheet
        roster_top = manifest.roster_table
        if roster_top is not None and roster_top.sheet_name in wb.sheetnames:
            ws = wb[roster_top.sheet_name]
            students = getattr(data_context, "students", None)
            if students is None and isinstance(data_context, dict):
                students = data_context.get("students", [])
            students = students or []

            start_row = roster_top.first_data_row_index + 1  # 1-indexed for openpyxl
            for idx, entry in enumerate(students):
                row_idx = start_row + idx
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    name, stnum = str(entry[0]), str(entry[1])
                elif isinstance(entry, dict):
                    name = str(entry.get("name", ""))
                    stnum = str(entry.get("student_number", entry.get("id", "")))
                else:
                    name, stnum = str(entry), ""

                cols = roster_top.columns
                if "name" in cols:
                    ws.cell(row=row_idx, column=cols["name"] + 1, value=name)
                if "student_number" in cols:
                    ws.cell(row=row_idx, column=cols["student_number"] + 1, value=stnum)

        # 3. Populate dynamic N-tier signatory slots across worksheets
        if manifest.signatory_slots:
            self._populate_signatories_xlsx(wb, manifest.signatory_slots, data_context)

        target_out = output_path or xlsx_path
        wb.save(target_out)
        logger.info(f"DynamicDocumentRenderer generated XLSX: {os.path.basename(target_out)}")
        return target_out

    def _replace_tag_in_element(self, element: etree._Element, token: str, value: str) -> None:
        """
        Replaces placeholder tokens in document paragraphs while strictly
        preserving run formatting (<w:rPr>).
        """
        for p in element.iter(w("p")):
            runs = p.findall(w("r"))
            p_txt = "".join(r.findtext(w("t")) or "" for r in runs)
            while token in p_txt:
                start_pos = p_txt.find(token)
                end_pos = start_pos + len(token)
                char_accum = 0
                start_run_idx = None
                end_run_idx = None
                start_offset = 0
                end_offset = 0
                for r_i, r in enumerate(runs):
                    txt = r.findtext(w("t")) or ""
                    next_accum = char_accum + len(txt)
                    if start_run_idx is None and next_accum > start_pos:
                        start_run_idx = r_i
                        start_offset = start_pos - char_accum
                    if next_accum >= end_pos:
                        end_run_idx = r_i
                        end_offset = end_pos - char_accum
                        break
                    char_accum = next_accum

                if start_run_idx is not None and end_run_idx is not None:
                    if start_run_idx == end_run_idx:
                        t_node = runs[start_run_idx].find(w("t"))
                        if t_node is not None:
                            cur = t_node.text or ""
                            t_node.text = cur[:start_offset] + value + cur[end_offset:]
                    else:
                        t_start = runs[start_run_idx].find(w("t"))
                        t_end = runs[end_run_idx].find(w("t"))
                        if t_start is not None and t_end is not None:
                            start_cur = t_start.text or ""
                            end_cur = t_end.text or ""
                            t_start.text = start_cur[:start_offset] + value
                            t_end.text = end_cur[end_offset:]
                        for mid_i in range(start_run_idx + 1, end_run_idx):
                            for t_mid in runs[mid_i].findall(w("t")):
                                t_mid.text = ""
                p_txt = "".join(r.findtext(w("t")) or "" for r in runs)

    def _resolve_signatory_value(
        self,
        slot: SignatorySlot,
        data_context: Union[ClassInfo, Dict[str, Any]],
    ) -> Optional[str]:
        """
        Resolves the appropriate signatory name/value from data context for a given SignatorySlot.
        Supports:
        - Explicit N-tier signatories list or mapping in data_context['signatories']
        - Bound key matches (e.g., 'department_chair', 'college_dean', 'campus_administrator', 'instructor')
        - Role label / slot_id heuristic fallback for backward compatibility
        """
        # 1. Check nested signatories list/dict
        signatories = getattr(data_context, "signatories", None)
        if signatories is None and isinstance(data_context, dict):
            signatories = data_context.get("signatories")

        if signatories:
            if isinstance(signatories, list):
                for sig in signatories:
                    if isinstance(sig, dict):
                        sid = sig.get("slot_id") or ""
                        lbl = sig.get("label") or ""
                        bkey = sig.get("bound_key") or ""
                        title = sig.get("title") or ""
                        if (
                            (sid and sid == slot.slot_id)
                            or (bkey and bkey == slot.bound_key)
                            or (lbl and lbl.strip().lower() == slot.role_label.strip().lower())
                            or (title and slot.default_title and title.strip().lower() == slot.default_title.strip().lower())
                        ):
                            val = sig.get("name") or sig.get("value")
                            if val:
                                return str(val).strip()
            elif isinstance(signatories, dict):
                for k in (slot.bound_key, slot.slot_id, slot.role_label):
                    if k and k in signatories:
                        val = signatories[k]
                        if val:
                            return str(val).strip()

        # 2. Direct key lookups in data_context
        candidate_keys = []
        if slot.bound_key:
            candidate_keys.append(slot.bound_key)
        if slot.slot_id and slot.slot_id not in candidate_keys:
            candidate_keys.append(slot.slot_id)

        slot_id = slot.slot_id
        bound_key = slot.bound_key
        def_title_lower = slot.default_title.lower() if slot.default_title else ""

        if bound_key == "prepared_by" or slot_id == "prepared_by" or "instructor" in def_title_lower:
            candidate_keys.extend(["instructor", "prepared_by", "faculty", "adviser"])

        if bound_key == "department_chair" or slot_id in ("reviewed_by", "recommending_approval") or "chair" in def_title_lower:
            candidate_keys.extend(["department_chair", "dept_chair", "chair", "chairperson"])

        if bound_key == "college_dean" or "dean" in def_title_lower:
            candidate_keys.extend(["college_dean", "dean", "gs_dean"])

        if bound_key == "campus_administrator" or "administrator" in def_title_lower or "admin" in def_title_lower:
            candidate_keys.extend(["campus_administrator", "campus_admin", "administrator", "admin", "college_dean"])

        if slot_id == "approved_by":
            if "admin" in def_title_lower or "administrator" in def_title_lower:
                candidate_keys.extend(["campus_administrator", "campus_admin", "administrator", "college_dean", "dean", "approved_by"])
            elif "dean" in def_title_lower:
                candidate_keys.extend(["college_dean", "dean", "campus_administrator", "approved_by"])
            else:
                candidate_keys.extend(["approved_by", "college_dean", "campus_administrator", "dean"])

        if slot_id in ("reviewed_by", "recommending_approval"):
            candidate_keys.extend(["department_chair", "dept_chair", "chair", "chairperson"])

        for k in candidate_keys:
            val = None
            if isinstance(data_context, dict):
                val = data_context.get(k)
            else:
                val = getattr(data_context, k, None)
            if val is not None and str(val).strip():
                return str(val).strip()

        return None

    def _populate_signatories_docx(
        self,
        tables: List[etree._Element],
        paragraphs: List[etree._Element],
        signatory_slots: List[SignatorySlot],
        data_context: Union[ClassInfo, Dict[str, Any]],
    ) -> None:
        """
        Populates N-tier signatory slots in docx tables or paragraphs with run formatting preserved.
        """
        for slot in signatory_slots:
            val = self._resolve_signatory_value(slot, data_context)
            if not val:
                continue

            str_val = str(val).strip()

            if slot.slot_type == "table_cell":
                if slot.table_index is None or slot.table_index >= len(tables):
                    continue
                grid = DocxGridTable(tables[slot.table_index])
                t_r = slot.target_row_index
                t_c = slot.target_col_index
                if t_r is not None and t_c is not None and t_r < grid.num_rows and t_c < grid.num_cols:
                    grid.set_cell_text(t_r, t_c, str_val)

            elif slot.slot_type == "paragraph":
                target_p_idx = slot.target_paragraph_index if slot.target_paragraph_index is not None else slot.paragraph_index
                if target_p_idx is not None and target_p_idx < len(paragraphs):
                    p = paragraphs[target_p_idx]
                    runs = p.findall(w("r"))
                    if runs:
                        first_r = runs[0]
                        t_node = first_r.find(w("t"))
                        if t_node is None:
                            t_node = etree.SubElement(first_r, w("t"))
                        t_node.text = str_val
                        for r_extra in runs[1:]:
                            for t_extra in r_extra.findall(w("t")):
                                t_extra.text = ""
                    else:
                        r = etree.SubElement(p, w("r"))
                        t = etree.SubElement(r, w("t"))
                        t.text = str_val

    def _populate_signatories_xlsx(
        self,
        wb: openpyxl.Workbook,
        signatory_slots: List[SignatorySlot],
        data_context: Union[ClassInfo, Dict[str, Any]],
    ) -> None:
        """
        Populates N-tier signatory slots in openpyxl Excel worksheets.
        """
        for slot in signatory_slots:
            val = self._resolve_signatory_value(slot, data_context)
            if not val:
                continue

            sheet_name = slot.sheet_name
            if not sheet_name or sheet_name not in wb.sheetnames:
                ws = wb.active
            else:
                ws = wb[sheet_name]

            target_coord = slot.target_cell_coord
            if target_coord:
                ws[target_coord] = str(val).strip()
            elif slot.target_row_index and slot.target_col_index:
                ws.cell(row=slot.target_row_index, column=slot.target_col_index, value=str(val).strip())


__all__ = ["DynamicDocumentRenderer"]
