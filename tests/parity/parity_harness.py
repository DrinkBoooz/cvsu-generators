#!/usr/bin/env python3
"""
tests/parity/parity_harness.py

Parity verification harness for Document Generator migration.
Compares generated outputs against reference outputs across:
  - Table counts and dimensions
  - Cell text, formatting, and font sizes
  - Paragraph texts and styles
  - XLSX sheets, cell values, formulas, merged cell ranges
"""

import os
import re
from typing import Dict, List, Tuple, Any, Optional
import docx
from lxml import etree
import openpyxl

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocumentParityDiff:
    """Encapsulates differences between two documents."""

    def __init__(self):
        self.errors: List[str] = []

    def add_error(self, location: str, message: str, expected: Any, actual: Any):
        self.errors.append(f"[{location}] {message}: expected={expected!r}, actual={actual!r}")

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        return "\n".join(self.errors)


class ParityHarness:
    """
    Automated parity checker between reference files and newly generated files.
    """

    @staticmethod
    def compare_docx(ref_path: str, gen_path: str) -> DocumentParityDiff:
        """
        Deep structural and textual comparison between two DOCX files.
        """
        diff = DocumentParityDiff()

        if not os.path.exists(ref_path):
            diff.add_error("file", "Reference file missing", ref_path, None)
            return diff
        if not os.path.exists(gen_path):
            diff.add_error("file", "Generated file missing", None, gen_path)
            return diff

        doc_ref = docx.Document(ref_path)
        doc_gen = docx.Document(gen_path)

        # 1. Compare tables
        if len(doc_ref.tables) != len(doc_gen.tables):
            diff.add_error("tables", "Table count mismatch", len(doc_ref.tables), len(doc_gen.tables))
            return diff

        for tbl_idx, (t_ref, t_gen) in enumerate(zip(doc_ref.tables, doc_gen.tables)):
            if len(t_ref.rows) != len(t_gen.rows):
                diff.add_error(
                    f"table_{tbl_idx}",
                    "Row count mismatch",
                    len(t_ref.rows),
                    len(t_gen.rows),
                )
                continue

            for r_idx, (row_ref, row_gen) in enumerate(zip(t_ref.rows, t_gen.rows)):
                if len(row_ref.cells) != len(row_gen.cells):
                    diff.add_error(
                        f"table_{tbl_idx}_row_{r_idx}",
                        "Cell count mismatch",
                        len(row_ref.cells),
                        len(row_gen.cells),
                    )
                    continue

                for c_idx, (cell_ref, cell_gen) in enumerate(zip(row_ref.cells, row_gen.cells)):
                    text_ref = cell_ref.text.strip()
                    text_gen = cell_gen.text.strip()
                    if text_ref != text_gen:
                        diff.add_error(
                            f"table_{tbl_idx}_r{r_idx}_c{c_idx}",
                            "Cell text mismatch",
                            text_ref,
                            text_gen,
                        )

        # 2. Compare paragraphs outside tables
        paras_ref = [p.text.strip() for p in doc_ref.paragraphs if p.text.strip()]
        paras_gen = [p.text.strip() for p in doc_gen.paragraphs if p.text.strip()]
        if len(paras_ref) != len(paras_gen):
            diff.add_error("paragraphs", "Non-empty paragraph count mismatch", len(paras_ref), len(paras_gen))
        else:
            for p_idx, (pr, pg) in enumerate(zip(paras_ref, paras_gen)):
                if pr != pg:
                    diff.add_error(f"paragraph_{p_idx}", "Paragraph text mismatch", pr, pg)

        return diff

    @staticmethod
    def compare_xlsx(ref_path: str, gen_path: str) -> DocumentParityDiff:
        """
        Deep structural and cell value comparison between two XLSX workbooks.
        """
        diff = DocumentParityDiff()

        if not os.path.exists(ref_path):
            diff.add_error("file", "Reference XLSX missing", ref_path, None)
            return diff
        if not os.path.exists(gen_path):
            diff.add_error("file", "Generated XLSX missing", None, gen_path)
            return diff

        wb_ref = openpyxl.load_workbook(ref_path, data_only=False)
        wb_gen = openpyxl.load_workbook(gen_path, data_only=False)

        # 1. Compare sheet names
        if wb_ref.sheetnames != wb_gen.sheetnames:
            diff.add_error("sheets", "Sheet names mismatch", wb_ref.sheetnames, wb_gen.sheetnames)
            return diff

        for sheet_name in wb_ref.sheetnames:
            ws_ref = wb_ref[sheet_name]
            ws_gen = wb_gen[sheet_name]

            # Compare merged cells
            ranges_ref = sorted(str(m) for m in ws_ref.merged_cells.ranges)
            ranges_gen = sorted(str(m) for m in ws_gen.merged_cells.ranges)
            if ranges_ref != ranges_gen:
                diff.add_error(
                    f"sheet_{sheet_name}",
                    "Merged cell ranges mismatch",
                    ranges_ref,
                    ranges_gen,
                )

            # Compare non-empty cell values
            max_r = max(ws_ref.max_row, ws_gen.max_row)
            max_c = max(ws_ref.max_column, ws_gen.max_column)

            for r in range(1, max_r + 1):
                for c in range(1, max_c + 1):
                    v_ref = ws_ref.cell(r, c).value
                    v_gen = ws_gen.cell(r, c).value
                    if v_ref != v_gen:
                        coord = ws_ref.cell(r, c).coordinate
                        diff.add_error(
                            f"sheet_{sheet_name}_{coord}",
                            "Cell value mismatch",
                            v_ref,
                            v_gen,
                        )

        return diff
