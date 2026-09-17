#!/usr/bin/env python3
"""
modules/generators/document_generator.py

Department-Neutral DOCX Document Generator Engine.
Provides the DocumentGenerator abstract base class (template method pattern)
and ConfigurableDocumentGenerator for dynamic template generation driven by
authoritative ValidatedTemplateRecipe instances.
"""

from abc import ABC, abstractmethod
import copy
import os
from typing import Optional, Any, Union, Dict, List, Tuple
from lxml import etree

from modules.common.logger import logger
from modules.common.docx_utils import (
    w,
    set_cell_text,
    replace_after_colon,
    load_docx,
    save_docx,
)
from modules.models.schedule import ClassInfo
from modules.models.recipe import ValidatedTemplateRecipe, TemplateError
from modules.parsers.recipe_validator import RecipeValidator
from modules.generators.field_resolver import FieldResolver, resolve_field_value


class DocumentGenerator(ABC):
    """
    Abstract base — defines the template method pattern for DOCX generation.
    Pure execution engine driven by an authoritative ValidatedTemplateRecipe.
    Contains no heuristic template scanning or discovery.
    """

    def __init__(self, template_path: str, recipe: ValidatedTemplateRecipe):
        if not isinstance(recipe, ValidatedTemplateRecipe):
            raise TypeError(
                f"DocumentGenerator requires a ValidatedTemplateRecipe instance, got {type(recipe).__name__}"
            )
        self._template_path = template_path
        self._recipe = recipe

    @property
    def template_path(self) -> str:
        return self._template_path

    @property
    def recipe(self) -> ValidatedTemplateRecipe:
        return self._recipe

    @property
    def output_folder(self) -> str:
        """Target subfolder relative to <Course_Sec>/ for output document placement."""
        return self._recipe.metadata.get("output_folder") or "CEIT_Forms"

    def fill_header(self, body, info: ClassInfo) -> None:
        """Fills header fields driven strictly by recipe header_bindings and placeholders."""
        tables = body.findall(w("tbl"))
        paras = body.findall(w("p"))

        for field_name, b in self._recipe.header_bindings.items():
            val = resolve_field_value(field_name, info, self._recipe)
            thresh = b.shrink_threshold if self._recipe.profile_id != "custom_docx" else 0
            sz = b.shrink_sz or "18"

            if b.cell_type == "docx_table":
                t = b.target
                if isinstance(t, (tuple, list)) and len(t) == 3:
                    tbl_idx, r_idx, c_idx = t
                    if tbl_idx < len(tables):
                        rows = tables[tbl_idx].findall(w("tr"))
                        if r_idx < len(rows):
                            cells = rows[r_idx].findall(w("tc"))
                            if c_idx < len(cells):
                                set_cell_text(cells[c_idx], val, shrink_threshold=thresh, shrink_sz=sz)
            elif b.cell_type == "docx_paragraph":
                p_idx = b.target
                if isinstance(p_idx, int) and p_idx < len(paras):
                    replace_after_colon(paras[p_idx], val, shrink_threshold=thresh, shrink_sz=sz)

        # Placeholders if present in metadata
        placeholders = self._recipe.metadata.get("placeholders", [])
        if placeholders:
            for p_holder in placeholders:
                token = p_holder.get("tag") or f"{{{{{p_holder.get('raw_token', '')}}}}}"
                field_name = p_holder.get("field")
                val = resolve_field_value(field_name, info, self._recipe)
                if not token or not val:
                    continue
                for t in body.iter(w("t")):
                    if t.text and token in t.text:
                        t.text = t.text.replace(token, val)
                for p in body.iter(w("p")):
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
                                cur = t_node.text or ""
                                t_node.text = cur[:start_offset] + val + cur[end_offset:]
                            else:
                                t_start = runs[start_run_idx].find(w("t"))
                                t_end = runs[end_run_idx].find(w("t"))
                                start_cur = t_start.text or ""
                                end_cur = t_end.text or ""
                                t_start.text = start_cur[:start_offset] + val
                                t_end.text = end_cur[end_offset:]
                                for mid_i in range(start_run_idx + 1, end_run_idx):
                                    for t_mid in runs[mid_i].findall(w("t")):
                                        t_mid.text = ""
                        p_txt = "".join(r.findtext(w("t")) or "" for r in runs)

    def fill_table(self, body, info: ClassInfo) -> None:
        """Fills student roster table driven strictly by recipe roster_binding."""
        rb = self._recipe.roster_binding
        if rb is None:
            return

        tables = body.findall(w("tbl"))
        if rb.table_index >= len(tables):
            raise TemplateError(
                f"Roster table index {rb.table_index} not found in template ({len(tables)} tables present)."
            )

        target = tables[rb.table_index]
        rows = target.findall(w("tr"))
        if len(rows) <= rb.first_data_row_index:
            raise TemplateError(
                f"Student list table must have at least {rb.first_data_row_index + 1} rows."
            )

        template_row = rows[rb.first_data_row_index]

        for tr in rows[rb.first_data_row_index:]:
            target.remove(tr)

        for idx, (name, stnum) in enumerate(info.students):
            tr = copy.deepcopy(template_row)
            for tc in tr.findall(w("tc")):
                for p in tc.findall(w("p")):
                    for r in p.findall(w("r")):
                        for t in r.findall(w("t")):
                            t.text = ""
            cells = tr.findall(w("tc"))
            while len(cells) < 3:
                new_tc = etree.Element(w("tc"))
                tr.append(new_tc)
                cells = tr.findall(w("tc"))
            self._fill_student_row(cells, idx, name, stnum)
            target.append(tr)

    def _fill_student_row(self, cells: list, idx: int, name: str, stnum: str) -> None:
        """Fills one student row's cells based on recipe."""
        rb = self._recipe.roster_binding
        if rb is None:
            return
        if self._recipe.profile_id == "custom_docx" and rb.index_col is not None and rb.index_col < len(cells):
            set_cell_text(cells[rb.index_col], str(idx + 1))
        if rb.name_col is not None and rb.name_col < len(cells):
            set_cell_text(cells[rb.name_col], name, shrink_threshold=32, shrink_sz="18")
        if rb.id_col is not None and rb.id_col < len(cells):
            set_cell_text(cells[rb.id_col], stnum)

    def generate(self, info: ClassInfo, output_path: str) -> None:
        """Template method — orchestrates the full generation pipeline."""
        zin, root, body = load_docx(self._template_path)
        self.fill_header(body, info)
        self.fill_table(body, info)
        save_docx(zin, root, output_path)
        logger.info(f"Generated {os.path.basename(output_path)}")


class ConfigurableDocumentGenerator(DocumentGenerator):
    """
    Dynamic generator that populates custom templates based on an authoritative recipe.
    Zero mutable dictionary access; delegates core execution to DocumentGenerator base class.
    """

    def __init__(
        self,
        template_path: str,
        recipe: Union[ValidatedTemplateRecipe, Dict[str, Any]],
        profile_id: str = "custom_docx",
    ):
        if isinstance(recipe, ValidatedTemplateRecipe):
            validated_recipe = recipe
        elif isinstance(recipe, dict):
            validated_recipe = RecipeValidator.validate_dict(recipe, profile_id)
        else:
            raise TypeError(
                f"ConfigurableDocumentGenerator requires ValidatedTemplateRecipe or dict, got {type(recipe).__name__}"
            )

        super().__init__(template_path, validated_recipe)
        self._title = validated_recipe.metadata.get("title") or "Custom Document"
        self._suffix = validated_recipe.metadata.get("suffix") or "CUSTOM_FORM"

    @property
    def title(self) -> str:
        return self._title

    @property
    def suffix(self) -> str:
        return self._suffix


__all__ = [
    "TemplateError",
    "DocumentGenerator",
    "ConfigurableDocumentGenerator",
    "FieldResolver",
    "resolve_field_value",
]
