#!/usr/bin/env python3
"""
modules/generators/generic_doc_gen.py

Configurable Generic Document Generator.
Consumes a declarative recipe produced by TemplateInspector (or edited by the user)
to populate any .docx template dynamically with ClassInfo and student rosters.
"""

import copy
import os
from typing import Dict, Any, List
from lxml import etree

from modules.common.logger import logger
from modules.common.docx_utils import (
    w,
    load_docx,
    save_docx,
    set_cell_text,
    replace_after_colon,
    get_full_text,
)
from modules.models.schedule import ClassInfo
from modules.generators.ceit_gen import DocumentGenerator, TemplateError


class ConfigurableDocumentGenerator(DocumentGenerator):
    """
    Dynamic generator that populates custom templates based on a declarative recipe.
    """

    def __init__(self, template_path: str, recipe: Dict[str, Any]):
        super().__init__(template_path)
        self._recipe = recipe
        self._title = recipe.get("title", "Custom Document")
        self._suffix = recipe.get("suffix", "CUSTOM_FORM")

    @property
    def title(self) -> str:
        return self._title

    @property
    def suffix(self) -> str:
        return self._suffix

    @property
    def recipe(self) -> Dict[str, Any]:
        return self._recipe

    def fill_header(self, body, info: ClassInfo) -> None:
        """
        Fills metadata fields into tables and paragraphs according to recipe bindings.
        """
        tables = body.findall(w("tbl"))
        paras = body.findall(w("p"))

        field_values = {
            "instructor": info.instructor or "",
            "course_section": info.course_section or "",
            "schedule_code": info.schedule_code or "",
            "subject": info.subject or "",
            "time_days_room": info.time_days_room or "",
            "semester_ay": info.semester_ay or "",
            "date": "",  # Standard CvSU practice: left blank for faculty date/signature
        }

        # 1. Apply Table & Paragraph Bindings
        for b in self._recipe.get("header_bindings", []):
            field_name = b.get("field")
            val = field_values.get(field_name, "")
            thresh = b.get("shrink_threshold", 0)
            binding_type = b.get("type", "table_cell")

            if binding_type == "table_cell":
                tbl_idx = b.get("table_index", 0)
                r_idx = b.get("row_index", 0)
                c_idx = b.get("cell_index", 1)

                if tbl_idx < len(tables):
                    tbl = tables[tbl_idx]
                    rows = tbl.findall(w("tr"))
                    if r_idx < len(rows):
                        cells = rows[r_idx].findall(w("tc"))
                        if c_idx < len(cells):
                            set_cell_text(cells[c_idx], val, shrink_threshold=thresh, shrink_sz="18")

            elif binding_type == "paragraph_colon":
                p_idx = b.get("para_index", 0)
                if p_idx < len(paras):
                    replace_after_colon(paras[p_idx], val, shrink_threshold=thresh, shrink_sz="18")

        # 2. Apply explicit placeholder tokens if configured (e.g. {{INSTRUCTOR}})
        placeholders = self._recipe.get("placeholders", [])
        if placeholders:
            for p_holder in placeholders:
                token = p_holder.get("tag") or f"{{{{{p_holder.get('raw_token', '')}}}}}"
                field_name = p_holder.get("field")
                val = field_values.get(field_name, "")
                if not token or not val:
                    continue

                # First pass: direct text node replacement
                for t in body.iter(w("t")):
                    if t.text and token in t.text:
                        t.text = t.text.replace(token, val)

                # Second pass: paragraph-level check in case Word fragmented the placeholder across multiple runs
                for p in body.iter(w("p")):
                    runs = p.findall(w("r"))
                    p_txt = "".join(r.findtext(w("t")) or "" for r in runs)
                    if token in p_txt:
                        new_p_txt = p_txt.replace(token, val)
                        if runs:
                            t0 = runs[0].find(w("t"))
                            if t0 is not None:
                                t0.text = new_p_txt
                            for r in runs[1:]:
                                for t_node in r.findall(w("t")):
                                    t_node.text = ""

    def _fill_student_row(self, cells: List[Any], idx: int, name: str, stnum: str) -> None:
        """
        Fills a cloned student row's cells based on recipe column mappings.
        """
        roster = self._recipe.get("roster_table") or {}
        index_col = roster.get("index_col")
        name_col = roster.get("name_col")
        id_col = roster.get("id_col")

        if index_col is not None and index_col < len(cells):
            set_cell_text(cells[index_col], str(idx + 1))

        if name_col is not None and name_col < len(cells):
            # Auto-scale names to prevent awkward table wrapping
            set_cell_text(cells[name_col], name, shrink_threshold=32, shrink_sz="18")

        if id_col is not None and id_col < len(cells):
            set_cell_text(cells[id_col], stnum)

    def fill_table(self, body, info: ClassInfo) -> None:
        """
        Clones template student row and writes info.students using the detected table structure.
        """
        roster = self._recipe.get("roster_table")
        if not roster:
            # Fallback to standard CEIT table detector if no recipe table given
            return super().fill_table(body, info)

        tables = body.findall(w("tbl"))
        tbl_idx = roster.get("table_index", 1)
        if tbl_idx >= len(tables):
            raise TemplateError(
                f"Roster table index {tbl_idx} not found in template (template contains {len(tables)} tables)."
            )

        target_table = tables[tbl_idx]
        rows = target_table.findall(w("tr"))
        tmpl_idx = roster.get("template_row_index", 1)

        if len(rows) <= tmpl_idx:
            raise TemplateError(
                f"Roster table must have at least {tmpl_idx + 1} rows to clone template student row."
            )

        template_row = rows[tmpl_idx]
        total_cols = roster.get("total_cols", len(template_row.findall(w("tc"))))

        # Clear existing rows from template row downwards
        for tr in rows[tmpl_idx:]:
            target_table.remove(tr)

        # Append populated student rows
        for idx, (name, stnum) in enumerate(info.students):
            tr = copy.deepcopy(template_row)

            # Clear all text in the cloned row
            for tc in tr.findall(w("tc")):
                for p in tc.findall(w("p")):
                    for r in p.findall(w("r")):
                        for t in r.findall(w("t")):
                            t.text = ""

            cells = tr.findall(w("tc"))
            while len(cells) < total_cols:
                new_tc = etree.Element(w("tc"))
                tr.append(new_tc)
                cells = tr.findall(w("tc"))

            self._fill_student_row(cells, idx, name, stnum)
            target_table.append(tr)
