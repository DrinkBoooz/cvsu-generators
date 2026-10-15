#!/usr/bin/env python3
"""
modules/parsers/docx_grid_table.py

OpenXML Table Grid-Topology Normalizer (DocxGridTable).
Normalizes WordprocessingML table elements (<w:tbl>) into a true 2D matrix,
resolving horizontal spans (w:gridSpan) and vertical continuation merges (w:vMerge)
into visual (row, col) coordinates pointing to canonical origin cells.

Prevents the python-docx coordinate trap where merged cells result in irregular
row lengths, broken column indexing, and duplicate text mutation on continuation cells.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from lxml import etree

from modules.common.docx_utils import (
    get_full_text,
    set_cell_text as docx_set_cell_text,
    w,
)


@dataclass
class DocxGridCell:
    """
    Normalized cell in the 2D visual grid representation of an OpenXML table.

    Attributes:
        tc: The canonical XML element (<w:tc>) containing the cell content.
            For merged regions, this always references the top-left origin <w:tc>.
        raw_tc: The physical XML element (<w:tc>) present in the document at this
            visual coordinate (which may be a continuation cell carrying <w:vMerge/>).
        row: Visual grid row index (0-based).
        col: Visual grid column index (0-based).
        row_span: Number of visual rows spanned by this cell (>= 1).
        col_span: Number of visual columns spanned by this cell (>= 1).
        is_origin: True if this cell is the top-left origin of its merged region.
        origin_row: Visual grid row index of the origin cell.
        origin_col: Visual grid column index of the origin cell.
        text: Normalized text content extracted from the origin cell.
        raw_text: Raw unstripped text content from the origin cell.
        xml_row_index: Physical index of the <w:tr> element in <w:tbl>.
        xml_cell_index: Physical index of the <w:tc> element in <w:tr>.
    """
    tc: Any
    raw_tc: Any
    row: int
    col: int
    row_span: int
    col_span: int
    is_origin: bool
    origin_row: int
    origin_col: int
    text: str
    raw_text: str
    xml_row_index: int
    xml_cell_index: int

    @property
    def is_continuation(self) -> bool:
        """True if this visual coordinate is a continuation of a merged cell."""
        return not self.is_origin

    @property
    def is_vmerge_continuation(self) -> bool:
        """True if this cell continues a vertical merge from a row above."""
        return self.is_continuation and (self.row != self.origin_row)

    @property
    def is_hmerge_continuation(self) -> bool:
        """True if this cell continues a horizontal merge from a column to the left."""
        return self.is_continuation and (self.col != self.origin_col)

    @property
    def span_shape(self) -> Tuple[int, int]:
        """Returns (row_span, col_span)."""
        return self.row_span, self.col_span

    def __repr__(self) -> str:
        origin_tag = "*" if self.is_origin else f"->({self.origin_row},{self.origin_col})"
        return (
            f"DocxGridCell(pos=({self.row},{self.col}) {origin_tag} "
            f"span={self.row_span}x{self.col_span} text={self.text!r})"
        )


class DocxGridTable:
    """
    Deterministic 2D virtual grid mapper over OpenXML <w:tbl> elements.

    Normalizes complex Word tables containing arbitrary combinations of
    w:gridSpan (horizontal merges) and w:vMerge (vertical continuations) into
    a uniform rectangular matrix where table[r, c] maps reliably to visual cells.
    """

    def __init__(self, tbl_element: Any):
        """
        Initializes DocxGridTable from an lxml <w:tbl> element or python-docx Table.

        Args:
            tbl_element: lxml.etree._Element representing <w:tbl>, or
                         python-docx Table instance.
        """
        # Support python-docx Table objects transparently
        if hasattr(tbl_element, "_tbl"):
            self.tbl = tbl_element._tbl
            self._docx_table = tbl_element
        else:
            self.tbl = tbl_element
            self._docx_table = None

        self._grid: List[List[DocxGridCell]] = []
        self._mutated_cells: Set[Tuple[int, int]] = set()
        self._build_grid()

    def _build_grid(self) -> None:
        """Builds the 2D grid matrix resolving all gridSpan and vMerge declarations."""
        rows = self.tbl.findall(w("tr"))
        if not rows:
            self._grid = []
            return

        # Query <w:tblGrid> column definitions if present
        tbl_grid = self.tbl.find(w("tblGrid"))
        grid_cols_count = len(tbl_grid.findall(w("gridCol"))) if tbl_grid is not None else 0

        # Active vertical merges per visual column:
        # col_idx -> (origin_row, origin_col, origin_tc, col_span)
        active_vmerges: Dict[int, Tuple[int, int, Any, int]] = {}
        raw_grid: List[List[Optional[DocxGridCell]]] = []

        for r_idx, tr in enumerate(rows):
            current_row: List[Optional[DocxGridCell]] = []
            c_idx = 0
            tc_elements = tr.findall(w("tc"))
            tc_iter = iter(enumerate(tc_elements))

            # Lookahead peekable iterator for physical <w:tc> elements in this row
            next_peeked = [next(tc_iter, None)]

            def peek_next() -> Optional[Tuple[int, Any]]:
                return next_peeked[0]

            def consume_next() -> Optional[Tuple[int, Any]]:
                item = next_peeked[0]
                next_peeked[0] = next(tc_iter, None)
                return item

            while True:
                peek_item = peek_next()

                # Case A: Current column is covered by an active vertical merge from above
                if c_idx in active_vmerges:
                    orig_r, orig_c, orig_tc, span_c = active_vmerges[c_idx]

                    # Verify if the physical <w:tc> in this row is a genuine continuation cell
                    is_cont = False
                    if peek_item is not None:
                        _, tc_cand = peek_item
                        tcpr = tc_cand.find(w("tcPr"))
                        if tcpr is not None:
                            vm = tcpr.find(w("vMerge"))
                            # In OpenXML, vMerge with no val or val="continue" continues the merge
                            if vm is not None and vm.get(w("val")) != "restart":
                                is_cont = True

                    if is_cont:
                        xml_c_idx, cont_tc = consume_next()  # type: ignore
                        for offset in range(span_c):
                            cell_obj = DocxGridCell(
                                tc=orig_tc,
                                raw_tc=cont_tc,
                                row=r_idx,
                                col=c_idx + offset,
                                row_span=1,  # Finalized in second pass
                                col_span=span_c,
                                is_origin=False,
                                origin_row=orig_r,
                                origin_col=orig_c,
                                text=get_full_text(orig_tc).strip(),
                                raw_text=get_full_text(orig_tc),
                                xml_row_index=r_idx,
                                xml_cell_index=xml_c_idx,
                            )
                            current_row.append(cell_obj)
                        c_idx += span_c
                        continue
                    else:
                        # The vertical merge ended before or at this row
                        del active_vmerges[c_idx]
                        # Continue processing at c_idx with the current peek_item

                if peek_item is None:
                    break

                # Case B: Standard cell (origin cell or horizontal span)
                xml_c_idx, tc = consume_next()  # type: ignore

                tcpr = tc.find(w("tcPr"))
                gspan = 1
                vmerge_val = None

                if tcpr is not None:
                    gs = tcpr.find(w("gridSpan"))
                    if gs is not None:
                        try:
                            gspan = max(1, int(gs.get(w("val"), 1)))
                        except (ValueError, TypeError):
                            gspan = 1
                    vm = tcpr.find(w("vMerge"))
                    if vm is not None:
                        vmerge_val = vm.get(w("val"), "continue")

                # If this cell initiates a vertical merge, record it
                if vmerge_val == "restart":
                    for span_offset in range(gspan):
                        active_vmerges[c_idx + span_offset] = (r_idx, c_idx, tc, gspan)

                cell_raw_text = get_full_text(tc)
                cell_text = cell_raw_text.strip()
                origin_r = r_idx
                origin_c = c_idx

                for offset in range(gspan):
                    is_orig = (offset == 0)
                    cell_obj = DocxGridCell(
                        tc=tc,
                        raw_tc=tc,
                        row=r_idx,
                        col=c_idx + offset,
                        row_span=1,  # Finalized in second pass
                        col_span=gspan,
                        is_origin=is_orig,
                        origin_row=origin_r,
                        origin_col=origin_c,
                        text=cell_text,
                        raw_text=cell_raw_text,
                        xml_row_index=r_idx,
                        xml_cell_index=xml_c_idx,
                    )
                    current_row.append(cell_obj)

                c_idx += gspan

            raw_grid.append(current_row)

        # Normalize grid to a complete rectangular matrix
        max_cols = max((len(r) for r in raw_grid), default=0)
        if grid_cols_count > max_cols:
            max_cols = grid_cols_count

        for r_idx, r in enumerate(raw_grid):
            while len(r) < max_cols:
                col_pos = len(r)
                r.append(DocxGridCell(
                    tc=None,
                    raw_tc=None,
                    row=r_idx,
                    col=col_pos,
                    row_span=1,
                    col_span=1,
                    is_origin=True,
                    origin_row=r_idx,
                    origin_col=col_pos,
                    text="",
                    raw_text="",
                    xml_row_index=r_idx,
                    xml_cell_index=-1,
                ))

        self._grid = raw_grid

        # Second pass: compute accurate row_span for every origin cell
        for r_idx in range(len(self._grid)):
            for c_idx in range(len(self._grid[r_idx])):
                cell = self._grid[r_idx][c_idx]
                if cell.is_origin:
                    span = 1
                    while r_idx + span < len(self._grid):
                        below_cell = self._grid[r_idx + span][c_idx]
                        if (
                            not below_cell.is_origin
                            and below_cell.origin_row == r_idx
                            and below_cell.origin_col == c_idx
                        ):
                            span += 1
                        else:
                            break
                    cell.row_span = span

    @property
    def num_rows(self) -> int:
        """Total number of visual rows in the normalized grid."""
        return len(self._grid)

    @property
    def num_cols(self) -> int:
        """Total number of visual columns in the normalized grid."""
        return len(self._grid[0]) if self._grid else 0

    @property
    def dimensions(self) -> Tuple[int, int]:
        """Returns (num_rows, num_cols) of the visual grid."""
        return self.num_rows, self.num_cols

    def cell(self, row: int, col: int) -> DocxGridCell:
        """
        Retrieves the visual cell at coordinates (row, col).

        Raises:
            IndexError: If row or col is out of visual grid bounds.
        """
        if row < 0 or row >= self.num_rows:
            raise IndexError(f"Row {row} out of range [0, {self.num_rows})")
        if col < 0 or col >= self.num_cols:
            raise IndexError(f"Col {col} out of range [0, {self.num_cols})")
        return self._grid[row][col]

    def get_cell(self, row: int, col: int) -> Optional[DocxGridCell]:
        """Safely retrieves the visual cell at (row, col), or None if out of bounds."""
        if 0 <= row < self.num_rows and 0 <= col < self.num_cols:
            return self._grid[row][col]
        return None


    def __getitem__(self, index: Tuple[int, int]) -> DocxGridCell:
        """Enables 2D subscript access: table[row, col]."""
        r, c = index
        return self.cell(r, c)

    def get_canonical_cell(self, row: int, col: int) -> DocxGridCell:
        """
        Returns the top-left origin cell for the cell at (row, col).
        If the cell is not merged, returns the cell itself.
        """
        c = self.cell(row, col)
        if c.is_origin:
            return c
        return self._grid[c.origin_row][c.origin_col]

    def row(self, r: int) -> List[DocxGridCell]:
        """Returns all visual cells in row r."""
        if r < 0 or r >= self.num_rows:
            raise IndexError(f"Row {r} out of range [0, {self.num_rows})")
        return list(self._grid[r])

    def col(self, c: int) -> List[DocxGridCell]:
        """Returns all visual cells in column c."""
        if c < 0 or c >= self.num_cols:
            raise IndexError(f"Col {c} out of range [0, {self.num_cols})")
        return [self._grid[r][c] for r in range(self.num_rows)]

    def unique_cells(self) -> List[DocxGridCell]:
        """Returns all unique canonical origin cells (excluding continuation duplicates)."""
        cells = []
        for r in range(self.num_rows):
            for c in range(self.num_cols):
                cell = self._grid[r][c]
                if cell.is_origin and cell.tc is not None:
                    cells.append(cell)
        return cells

    def unique_row_cells(self, r: int) -> List[DocxGridCell]:
        """Returns unique origin cells whose origin starts in row r."""
        seen = set()
        result = []
        for cell in self.row(r):
            if cell.is_origin and cell.tc is not None:
                key = (cell.origin_row, cell.origin_col)
                if key not in seen:
                    seen.add(key)
                    result.append(cell)
        return result

    def adjacent_right(self, row: int, col: int) -> Optional[DocxGridCell]:
        """
        Returns the visual cell immediately to the right of this cell's horizontal span.
        Calculates target column as `origin_col + col_span`.
        """
        c = self.cell(row, col)
        target_col = c.origin_col + c.col_span
        if target_col < self.num_cols:
            return self.get_canonical_cell(row, target_col)
        return None

    def adjacent_below(self, row: int, col: int) -> Optional[DocxGridCell]:
        """
        Returns the visual cell immediately below this cell's vertical span.
        Calculates target row as `origin_row + row_span`.
        """
        c = self.cell(row, col)
        target_row = c.origin_row + c.row_span
        if target_row < self.num_rows:
            return self.get_canonical_cell(target_row, col)
        return None

    def target_value_cell_right(self, row: int, col: int) -> Optional[DocxGridCell]:
        """
        Resolves the target data value cell to the right of a label cell.

        If the cell immediately to the right contains only a colon (e.g. ":"),
        skips past the colon and returns the cell to the right of the colon.
        Otherwise, returns adjacent_right.
        """
        adj = self.adjacent_right(row, col)
        if adj is not None and adj.text in (":", ":-", "-"):
            return self.adjacent_right(adj.row, adj.col)
        return adj

    def find_cells(self, predicate: Callable[[DocxGridCell], bool], origin_only: bool = True) -> List[DocxGridCell]:
        """Finds all cells matching the given predicate."""
        matched = []
        for r in range(self.num_rows):
            for c in range(self.num_cols):
                cell = self._grid[r][c]
                if origin_only and not cell.is_origin:
                    continue
                if predicate(cell):
                    matched.append(cell)
        return matched

    def find_cells_by_regex(self, pattern: str | re.Pattern, origin_only: bool = True) -> List[DocxGridCell]:
        """Finds all cells whose text matches the regex pattern."""
        rx = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern
        return self.find_cells(lambda c: bool(rx.search(c.text)), origin_only=origin_only)

    def find_cell_by_text(self, text_or_regex: str | re.Pattern, origin_only: bool = True) -> Optional[DocxGridCell]:
        """Finds the first cell matching the given text or regex, or None."""
        matches = self.find_cells_by_regex(text_or_regex, origin_only=origin_only)
        return matches[0] if matches else None

    def set_cell_text(
        self,
        row: int,
        col: int,
        text: str,
        remove_num: bool = False,
        shrink_threshold: int = 0,
        shrink_sz: str = "18",
        is_student_name: bool = False,
        allow_duplicate_write: bool = True,
    ) -> DocxGridCell:
        """
        Safely updates the text of a cell in the visual grid.

        Always targets the canonical origin <w:tc> element and NEVER mutates
        continuation cells, preventing duplicate or overlapping text in Word.

        Args:
            row: Visual row coordinate.
            col: Visual column coordinate.
            text: Text to set in the cell.
            remove_num: Whether to strip numbering properties.
            shrink_threshold: Character threshold for font auto-scaling.
            shrink_sz: Font size to apply when threshold is exceeded.
            is_student_name: Apply student name font ladder scaling.
            allow_duplicate_write: If False, raises ValueError if the canonical
                origin cell was already mutated in this table.

        Returns:
            The canonical DocxGridCell that was updated.
        """
        orig = self.get_canonical_cell(row, col)
        if orig.tc is None:
            raise ValueError(f"Cannot set text on empty grid padding cell ({row}, {col})")

        origin_key = (orig.origin_row, orig.origin_col)
        if not allow_duplicate_write and origin_key in self._mutated_cells:
            raise ValueError(
                f"Cell at visual ({row}, {col}) resolves to origin ({orig.origin_row}, {orig.origin_col}) "
                f"which has already been mutated in this table."
            )

        # Mutate the canonical XML element
        docx_set_cell_text(
            orig.tc,
            text,
            remove_num=remove_num,
            shrink_threshold=shrink_threshold,
            shrink_sz=shrink_sz,
            is_student_name=is_student_name,
        )

        # Update cached text in all visual cells pointing to this origin
        cleaned_text = text.strip()
        orig.text = cleaned_text
        orig.raw_text = text

        for r in range(orig.origin_row, orig.origin_row + orig.row_span):
            for c in range(orig.origin_col, orig.origin_col + orig.col_span):
                if r < self.num_rows and c < self.num_cols:
                    grid_cell = self._grid[r][c]
                    grid_cell.text = cleaned_text
                    grid_cell.raw_text = text

        self._mutated_cells.add(origin_key)
        return orig

    def has_mutated(self, row: int, col: int) -> bool:
        """Returns True if the canonical origin of (row, col) has been mutated."""
        orig = self.get_canonical_cell(row, col)
        return (orig.origin_row, orig.origin_col) in self._mutated_cells

    @property
    def mutated_cells(self) -> Set[Tuple[int, int]]:
        """Returns the set of origin (row, col) coordinates mutated in this table."""
        return set(self._mutated_cells)
