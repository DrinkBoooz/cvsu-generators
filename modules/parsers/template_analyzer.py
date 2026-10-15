#!/usr/bin/env python3
"""
modules/parsers/template_analyzer.py

Deterministic Template Analyzer & Template Manifest Engine.
Performs pure, offline, deterministic structural introspection of Word (.docx)
and Excel (.xlsx) templates without hardcoded cell/row/table indices or brittle heuristics.

Emits structured, serializable TemplateManifest instances cataloging:
  1. Semantic Metadata Slots (labels, locations, target coordinates, replacement strategies)
  2. Repeating Table Topologies (header bounds, first data row, cloneable prototype, capacity, columns)
  3. Explicit Placeholders ({{TAG}} / <TAG>)
  4. Deterministic SHA-256 fingerprint for fast caching
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lxml import etree
import openpyxl

from modules.common.docx_utils import get_full_text, w
from modules.models.organization import OrganizationalContext, SignatorySlot
from modules.parsers.docx_grid_table import DocxGridCell, DocxGridTable


# ─────────────────────────────────────────────────────────────────────────────
# Authoritative Semantic Patterns & Keyword Dictionaries
# ─────────────────────────────────────────────────────────────────────────────

RE_INSTITUTION = re.compile(r"\bCAVITE\s+STATE\s+UNIVERSITY\b", re.IGNORECASE)
RE_CAMPUS = re.compile(
    r"\b((?:(?:Don\s+Severino\s+de\s*las\s*Alas|Don\s+Severino\s+delas\s*Alas|Main|[A-Za-z0-9\.\-–]+)\s+Campus)|(?:CvSU\s*[-–]\s*([A-Za-z0-9\.\-–]+\s+Campus)))\b",
    re.IGNORECASE,
)
RE_COLLEGE = re.compile(
    r"\b((?:COLLEGE\s+OF\s+[A-Za-z0-9\s\.\-&,]+|GRADUATE\s+SCHOOL(?:\s+AND\s+OPEN\s+LEARNING\s+COLLEGE)?|[A-Za-z\s]+COLLEGE))\b",
    re.IGNORECASE,
)
RE_DEPARTMENT = re.compile(
    r"\b(DEPARTMENT\s+OF\s+[A-Za-z0-9\s\.\-&,]+)\b",
    re.IGNORECASE,
)

RE_SIG_ANCHORS = re.compile(
    r"\b(prepared\s*by|reviewed\s*by|recommending\s*approval|noted\s*by|approved\s*by|certified\s*correct|submitted\s*by|checked\s*by)\b",
    re.IGNORECASE,
)

DEFAULT_TITLE_PATTERNS = [
    (re.compile(r"\b(instructor|faculty|professor|teacher|adviser)\b", re.IGNORECASE), "Instructor"),
    (re.compile(r"\b(department\s*chair(?:person)?|dept\.?\s*chair)\b", re.IGNORECASE), "Department Chairperson"),
    (re.compile(r"\b(campus\s*administrator|campus\s*director)\b", re.IGNORECASE), "Campus Administrator"),
    (re.compile(r"\b(college\s*dean|dean,\s*gs-olc|dean)\b", re.IGNORECASE), "College Dean"),
    (re.compile(r"\b(program\s*coordinator|coordinator)\b", re.IGNORECASE), "Program Coordinator"),
]

METADATA_PATTERNS: Dict[str, re.Pattern] = {
    "instructor": re.compile(
        r"\b(instructor|faculty|professor|teacher|adviser)('s|\b)?(\s*name)?\b",
        re.IGNORECASE,
    ),
    "course_section": re.compile(
        r"\b(course\s*(&|and)?\s*sec(tion)?|yr\s*(&|and)?\s*sec|program\s*(&|and)?\s*sec|course\s*\/\s*year\s*\/\s*section|course\s*&?\s*section)\b",
        re.IGNORECASE,
    ),
    "schedule_code": re.compile(
        r"\b(sched(ule)?\s*code|class\s*code)\b",
        re.IGNORECASE,
    ),
    "subject": re.compile(
        r"\b(subject(\s*title)?|course\s*title|descriptive\s*title|subject\s*code\s*\/?\s*(description|title)|course\s*code\s*(&|and|\/)?\s*title)\b",
        re.IGNORECASE,
    ),
    "time_days_room": re.compile(
        r"\b(time\s*(\/|&|and)?\s*days?(\s*(\/|&|and)?\s*rooms?)?|class\s*schedule)\b",
        re.IGNORECASE,
    ),
    "room": re.compile(
        r"\b(room\s*(assignment|no\.?)?|bldg|building)\b",
        re.IGNORECASE,
    ),
    "semester_ay": re.compile(
        r"\b(semester\s*\/?\s*(ay|academic\s*year)|term|sem)\b",
        re.IGNORECASE,
    ),
    "month_year": re.compile(
        r"\b(month\s*(&|and|\/)\s*year|month)\b",
        re.IGNORECASE,
    ),
    "date": re.compile(
        r"\b(date)\b",
        re.IGNORECASE,
    ),
}

COLUMN_NAME_PATTERNS = re.compile(r"\b(name\s*of\s*students?|student\s*name|name|pangalan)\b", re.IGNORECASE)
COLUMN_ID_PATTERNS = re.compile(r"\b(student\s*(number|no)|id\s*number|stud\s*no|lrn)\b", re.IGNORECASE)
COLUMN_INDEX_PATTERNS = re.compile(r"^(no\.?|#|item)$", re.IGNORECASE)
COLUMN_SIGNATURE_PATTERNS = re.compile(r"\b(signature|lagda|sign)\b", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# Serializable Models: Slot, Topology, Manifest
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SemanticSlot:
    """
    Declarative binding slot for document metadata (header, footer, body).
    """
    field: str
    slot_type: str  # "table_cell" | "paragraph_after_colon" | "paragraph_inline" | "tag_placeholder" | "excel_cell"
    label_text: str
    table_index: Optional[int] = None
    row_index: Optional[int] = None
    col_index: Optional[int] = None
    target_row_index: Optional[int] = None
    target_col_index: Optional[int] = None
    paragraph_index: Optional[int] = None
    run_index: Optional[int] = None
    sheet_name: Optional[str] = None
    cell_coord: Optional[str] = None
    strategy: str = "set_cell_text"  # "set_cell_text" | "replace_after_colon" | "collapse_runs_after_colon" | "tag_replace"
    placeholder_tag: Optional[str] = None
    shrink_threshold: int = 0
    shrink_size: str = "18"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SemanticSlot:
        return cls(**data)


@dataclass
class RepeatingTableTopology:
    """
    Structural specification of a table containing repeating data rows.
    """
    table_index: int
    topology_type: str  # "student_roster" | "attendance_matrix" | "cognitive_domain" | "generic_repeating"
    header_rows: List[int]
    first_data_row_index: int
    template_row_index: int
    footer_row_indices: List[int]
    columns: Dict[str, int]  # e.g. {"index": 0, "name": 1, "student_number": 2, "signature": 3}
    total_rows: int
    total_cols: int
    data_rows_capacity: int
    column_headers: Dict[int, str]
    sheet_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RepeatingTableTopology:
        return cls(**data)


@dataclass
class TemplateManifest:
    """
    Authoritative, serializable blueprint of an introspected template.
    """
    template_path: str
    file_type: str  # "docx" | "xlsx"
    content_hash: str  # SHA-256 fingerprint
    template_type: str  # "academic_ceit" | "attendance" | "grading_sheet" | "generic_form"
    suggested_title: str
    suggested_suffix: str
    slots: List[SemanticSlot]
    repeating_tables: List[RepeatingTableTopology]
    roster_table: Optional[RepeatingTableTopology] = None
    metadata_table_index: Optional[int] = None
    has_explicit_placeholders: bool = False
    explicit_placeholders: List[str] = field(default_factory=list)
    organizational_context: Optional[OrganizationalContext] = None
    signatory_slots: List[SignatorySlot] = field(default_factory=list)
    confidence: float = 1.0
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        """Indicates if the template is functionally ready for dynamic population."""
        return bool(
            self.slots
            or self.has_explicit_placeholders
            or self.roster_table
            or self.repeating_tables
            or self.signatory_slots
        )

    def get_diagnostics(self) -> List[str]:
        """Returns actionable diagnostics explaining detected capabilities and missing slots."""
        diag: List[str] = []
        if self.organizational_context:
            org = self.organizational_context
            details = []
            if org.campus:
                details.append(f"Campus: {org.campus}")
            if org.college:
                details.append(f"College: {org.college}")
            if org.department:
                details.append(f"Department: {org.department}")
            if details:
                diag.append(f"Detected Organizational Context ({', '.join(details)}).")

        if not self.slots and not self.has_explicit_placeholders:
            diag.append("No metadata placeholders (e.g. Instructor, Course & Sec, Schedule Code) or {{TAG}} placeholders detected.")
        else:
            if self.slots:
                fields_summary = ", ".join(s.field for s in self.slots[:6])
                if len(self.slots) > 6:
                    fields_summary += f", and {len(self.slots) - 6} more"
                diag.append(f"Detected {len(self.slots)} metadata slot(s): {fields_summary}.")
            if self.has_explicit_placeholders:
                tags_summary = ", ".join(self.explicit_placeholders[:6])
                if len(self.explicit_placeholders) > 6:
                    tags_summary += f", and {len(self.explicit_placeholders) - 6} more"
                diag.append(f"Detected {len(self.explicit_placeholders)} explicit placeholder(s): {tags_summary}.")

        if self.signatory_slots:
            sig_roles = ", ".join(s.role_label.strip(": ") for s in self.signatory_slots)
            diag.append(f"Detected {len(self.signatory_slots)} signatory slot(s): {sig_roles}.")

        if not self.roster_table and not self.repeating_tables:
            diag.append("No repeating student roster or attendance table detected. Template will only render header/metadata fields.")
        elif self.roster_table:
            diag.append(
                f"Detected student roster table (table index {self.roster_table.table_index}) with capacity of {self.roster_table.data_rows_capacity} data row(s)."
            )
        return diag

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_ready"] = self.is_ready
        d["diagnostics"] = self.get_diagnostics()
        d["organizational_context"] = self.organizational_context.to_dict() if self.organizational_context else None
        d["signatory_slots"] = [s.to_dict() for s in self.signatory_slots]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TemplateManifest:
        clean = dict(data)
        clean.pop("is_ready", None)
        clean.pop("diagnostics", None)
        slots = [SemanticSlot.from_dict(s) for s in clean.get("slots", [])]
        repeating = [RepeatingTableTopology.from_dict(r) for r in clean.get("repeating_tables", [])]
        roster = RepeatingTableTopology.from_dict(clean["roster_table"]) if clean.get("roster_table") else None
        org_data = clean.get("organizational_context")
        org_context = OrganizationalContext.from_dict(org_data) if org_data else None
        sig_slots = [SignatorySlot.from_dict(s) for s in clean.get("signatory_slots", [])]
        return cls(
            template_path=clean["template_path"],
            file_type=clean.get("file_type", "docx"),
            content_hash=clean["content_hash"],
            template_type=clean.get("template_type", "generic_form"),
            suggested_title=clean.get("suggested_title", "Custom Document Form"),
            suggested_suffix=clean.get("suggested_suffix", "CUSTOM_FORM"),
            slots=slots,
            repeating_tables=repeating,
            roster_table=roster,
            metadata_table_index=clean.get("metadata_table_index"),
            has_explicit_placeholders=clean.get("has_explicit_placeholders", False),
            explicit_placeholders=clean.get("explicit_placeholders", []),
            organizational_context=org_context,
            signatory_slots=sig_slots,
            confidence=clean.get("confidence", 1.0),
            extra=clean.get("extra", {}),
        )

    def get_slot(self, field_name: str) -> Optional[SemanticSlot]:
        """Finds the first slot registered for the given field name."""
        for slot in self.slots:
            if slot.field == field_name:
                return slot
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Template Analyzer Engine
# ─────────────────────────────────────────────────────────────────────────────

class DeterministicTemplateAnalyzer:
    """
    Authoritative introspection engine for Word (.docx) and Excel (.xlsx) templates.

    Executes in under 20 milliseconds, dynamically discovering metadata coordinates
    and repeating table structures without hardcoded table/row/col indices.
    Employs thread-safe SHA-256 fingerprint caching keyed by file content and mtime.
    """

    _instance: Optional[DeterministicTemplateAnalyzer] = None
    _instance_lock: threading.Lock = threading.Lock()

    _cache: Dict[str, TemplateManifest] = {}
    _mtime_index: Dict[str, Tuple[float, int, str]] = {}  # abs_path -> (mtime, size, content_hash)
    _cache_lock: threading.Lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DeterministicTemplateAnalyzer:
        """Thread-safe singleton accessor."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Computes deterministic SHA-256 fingerprint in chunks."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def invalidate(self, file_path: Optional[str] = None) -> None:
        """Invalidates cache for a specific file or clears entire cache."""
        with self._cache_lock:
            if file_path is None:
                self._cache.clear()
                self._mtime_index.clear()
            else:
                abs_p = os.path.abspath(file_path)
                cached = self._mtime_index.pop(abs_p, None)
                if cached:
                    _, _, chash = cached
                    if not any(entry[2] == chash for entry in self._mtime_index.values()):
                        self._cache.pop(chash, None)

    def analyze(self, template_path: str, force_refresh: bool = False) -> TemplateManifest:
        """
        Introspects any template file (.docx or .xlsx) and returns its TemplateManifest.
        Utilizes fast mtime and SHA-256 content caching to avoid redundant parsing.

        Args:
            template_path: Physical path to .docx or .xlsx template.
            force_refresh: When True, bypasses cache and recomputes manifest.

        Returns:
            TemplateManifest describing detected slots, tables, and fingerprint.
        """
        abs_path = os.path.abspath(template_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Template file does not exist: {template_path}")

        mtime = os.path.getmtime(abs_path)
        size = os.path.getsize(abs_path)

        if not force_refresh:
            with self._cache_lock:
                if abs_path in self._mtime_index:
                    cached_mtime, cached_size, cached_hash = self._mtime_index[abs_path]
                    if cached_mtime == mtime and cached_size == size and cached_hash in self._cache:
                        return self._cache[cached_hash]

        # Compute SHA-256 fingerprint
        content_hash = self.compute_sha256(abs_path)
        if not force_refresh:
            with self._cache_lock:
                if content_hash in self._cache:
                    self._mtime_index[abs_path] = (mtime, size, content_hash)
                    return self._cache[content_hash]

        ext = os.path.splitext(abs_path)[1].lower()
        if ext == ".docx":
            manifest = self.analyze_docx(abs_path)
        elif ext in (".xlsx", ".xls", ".xlsm"):
            manifest = self.analyze_xlsx(abs_path)
        else:
            raise ValueError(f"Unsupported template file format '{ext}' for: {template_path}")

        manifest.content_hash = content_hash
        with self._cache_lock:
            self._cache[content_hash] = manifest
            self._mtime_index[abs_path] = (mtime, size, content_hash)

        return manifest

    def analyze_docx(self, docx_path: str) -> TemplateManifest:
        """
        Deterministically introspects a Word (.docx) template using DocxGridTable.
        """
        if not os.path.isfile(docx_path):
            raise FileNotFoundError(f"DOCX template not found: {docx_path}")

        with open(docx_path, "rb") as f:
            raw_bytes = f.read()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        with zipfile.ZipFile(docx_path, "r") as z:
            doc_xml = z.read("word/document.xml")
        root = etree.fromstring(doc_xml)
        body = root.find(w("body"))
        return self.analyze_docx_tree(root, body, docx_path=docx_path, content_hash=content_hash)

    def analyze_docx_tree(
        self,
        root: etree._Element,
        body: Optional[etree._Element],
        docx_path: str = "",
        content_hash: str = "",
    ) -> TemplateManifest:
        """
        Introspects an in-memory or loaded OpenXML tree (<w:document> / <w:body>).
        """
        tables = body.findall(w("tbl")) if body is not None else []
        paragraphs = body.findall(w("p")) if body is not None else []

        # 1. Normalize all tables into 2D virtual grids
        grid_tables = [DocxGridTable(tbl) for tbl in tables]

        # 2. Check for explicit template placeholders {{TAG}} or <TAG>
        full_doc_text = "".join(root.itertext())
        explicit_placeholders: List[str] = []
        for m in re.finditer(r"\{\{([A-Za-z0-9_]+)\}\}", full_doc_text):
            explicit_placeholders.append(m.group(0))
        for m in re.finditer(r"<([A-Z0-9_]{3,})>", full_doc_text):
            explicit_placeholders.append(m.group(0))

        # 3. Detect repeating table topologies (rosters, cognitive domain rows, attendance)
        repeating_tables: List[RepeatingTableTopology] = []
        roster_table: Optional[RepeatingTableTopology] = None

        for t_idx, grid in enumerate(grid_tables):
            rep = self._detect_repeating_table(grid, t_idx)
            if rep is not None:
                repeating_tables.append(rep)
                if rep.topology_type in ("student_roster", "attendance_matrix"):
                    if roster_table is None or rep.data_rows_capacity > roster_table.data_rows_capacity:
                        roster_table = rep

        # 4. Detect semantic metadata slots across tables and paragraphs
        slots: List[SemanticSlot] = []
        metadata_tbl_idx: Optional[int] = None
        seen_fields: Set[str] = set()

        # Scan tables for metadata labels
        for t_idx, grid in enumerate(grid_tables):
            is_roster = (roster_table is not None and t_idx == roster_table.table_index)
            # If roster table, only check initial header rows for metadata
            max_r = min(5, grid.num_rows) if is_roster else grid.num_rows

            for r_idx in range(max_r):
                for c_idx in range(grid.num_cols):
                    cell = grid.cell(r_idx, c_idx)
                    if not cell.is_origin or not cell.text:
                        continue

                    # Check against metadata keyword patterns
                    for field_name, pattern in METADATA_PATTERNS.items():
                        if field_name in seen_fields:
                            continue
                        if pattern.search(cell.text):
                            target_cell = grid.target_value_cell_right(cell.row, cell.col)
                            strategy = "set_cell_text"
                            t_r: Optional[int] = None
                            t_c: Optional[int] = None

                            if target_cell is not None:
                                t_r = target_cell.row
                                t_c = target_cell.col
                            else:
                                if ":" in cell.text:
                                    strategy = "replace_after_colon"
                                    t_r = cell.row
                                    t_c = cell.col

                            if t_r is not None and t_c is not None:
                                slots.append(SemanticSlot(
                                    field=field_name,
                                    slot_type="table_cell",
                                    label_text=cell.text,
                                    table_index=t_idx,
                                    row_index=cell.row,
                                    col_index=cell.col,
                                    target_row_index=t_r,
                                    target_col_index=t_c,
                                    strategy=strategy,
                                    shrink_threshold=30 if field_name == "instructor" else 0,
                                ))
                                seen_fields.add(field_name)
                                if metadata_tbl_idx is None and not is_roster:
                                    metadata_tbl_idx = t_idx
                                break

        # Scan paragraphs for any unmapped metadata
        for p_idx, p in enumerate(paragraphs):
            p_text = get_full_text(p).strip()
            if not p_text or ":" not in p_text:
                continue

            for field_name, pattern in METADATA_PATTERNS.items():
                if field_name in seen_fields:
                    continue
                if pattern.search(p_text):
                    slots.append(SemanticSlot(
                        field=field_name,
                        slot_type="paragraph_after_colon",
                        label_text=p_text.split(":", 1)[0] + ":",
                        paragraph_index=p_idx,
                        strategy="collapse_runs_after_colon",
                        shrink_threshold=30 if field_name == "instructor" else 0,
                    ))
                    seen_fields.add(field_name)
                    break

        # Also register explicit placeholder tags as slots
        for tag in explicit_placeholders:
            field_name = tag.strip("{}<>").lower()
            if field_name not in seen_fields:
                slots.append(SemanticSlot(
                    field=field_name,
                    slot_type="tag_placeholder",
                    label_text=tag,
                    placeholder_tag=tag,
                    strategy="tag_replace",
                ))
                seen_fields.add(field_name)

        # 5. Extract Dynamic Organizational Context (Institution, Campus, College, Department)
        banner_texts: List[str] = []
        if paragraphs:
            for p in paragraphs[:25]:
                ptxt = get_full_text(p).strip()
                if ptxt:
                    banner_texts.append(ptxt)
        if grid_tables:
            for r_i in range(min(4, grid_tables[0].num_rows)):
                for c_i in range(grid_tables[0].num_cols):
                    cell_t = grid_tables[0].cell(r_i, c_i).text.strip()
                    if cell_t and cell_t not in banner_texts:
                        banner_texts.append(cell_t)

        org_context = self._extract_organizational_context(banner_texts)

        # 6. Discover Dynamic N-Tier Signatory Slots
        sig_slots = self._detect_signatory_slots_docx(grid_tables, paragraphs, roster_table)

        # 7. Infer template type, suggested title, and output suffix
        template_type, title, suffix = self._infer_template_identity(docx_path, full_doc_text, repeating_tables)

        confidence = 1.0 if roster_table is not None and len(slots) >= 3 else 0.85

        return TemplateManifest(
            template_path=docx_path,
            file_type="docx",
            content_hash=content_hash,
            template_type=template_type,
            suggested_title=title,
            suggested_suffix=suffix,
            slots=slots,
            repeating_tables=repeating_tables,
            roster_table=roster_table,
            metadata_table_index=metadata_tbl_idx,
            has_explicit_placeholders=bool(explicit_placeholders),
            explicit_placeholders=explicit_placeholders,
            organizational_context=org_context,
            signatory_slots=sig_slots,
            confidence=confidence,
        )

    def analyze_xlsx(self, xlsx_path: str) -> TemplateManifest:
        """
        Deterministically introspects an Excel (.xlsx) grading sheet template.
        """
        if not os.path.isfile(xlsx_path):
            raise FileNotFoundError(f"XLSX template not found: {xlsx_path}")

        with open(xlsx_path, "rb") as f:
            raw_bytes = f.read()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        wb = openpyxl.load_workbook(xlsx_path, data_only=False)
        sheet_names = wb.sheetnames

        # Identify primary roster sheet (Lecture, Grading Sheet, etc.)
        primary_sheet = None
        for name in ("Lecture", "Grading Sheet", "Summary", sheet_names[0]):
            if name in sheet_names:
                primary_sheet = name
                break

        ws = wb[primary_sheet] if primary_sheet else wb.active
        actual_sheet_name = ws.title

        slots: List[SemanticSlot] = []
        repeating_tables: List[RepeatingTableTopology] = []
        roster_table: Optional[RepeatingTableTopology] = None

        # Scan top 20 rows of worksheet for metadata labels
        seen_fields: Set[str] = set()
        for r in range(1, min(25, ws.max_row + 1)):
            for c in range(1, min(20, ws.max_column + 1)):
                val = ws.cell(row=r, column=c).value
                if not val or not isinstance(val, str):
                    continue

                for field_name, pattern in METADATA_PATTERNS.items():
                    if field_name in seen_fields:
                        continue
                    if pattern.search(val):
                        # Value cell is adjacent right column in same row
                        val_cell = ws.cell(row=r, column=c + 1)
                        coord = f"{openpyxl.utils.get_column_letter(c + 1)}{r}"
                        slots.append(SemanticSlot(
                            field=field_name,
                            slot_type="excel_cell",
                            label_text=val.strip(),
                            sheet_name=actual_sheet_name,
                            row_index=r,
                            col_index=c,
                            target_row_index=r,
                            target_col_index=c + 1,
                            cell_coord=coord,
                            strategy="set_cell_value",
                        ))
                        seen_fields.add(field_name)
                        break

        # Scan for student roster table (Name, Student Number columns)
        for r in range(1, min(35, ws.max_row + 1)):
            row_cols: Dict[str, int] = {}
            col_headers: Dict[int, str] = {}
            for c in range(1, ws.max_column + 1):
                val = ws.cell(row=r, column=c).value
                if not val or not isinstance(val, str):
                    continue
                txt = val.strip()
                col_headers[c - 1] = txt
                if COLUMN_NAME_PATTERNS.search(txt) and "name" not in row_cols:
                    row_cols["name"] = c - 1
                elif COLUMN_ID_PATTERNS.search(txt) and "student_number" not in row_cols:
                    row_cols["student_number"] = c - 1
                elif COLUMN_INDEX_PATTERNS.search(txt) and "index" not in row_cols:
                    row_cols["index"] = c - 1

            if "name" in row_cols or ("student_number" in row_cols and len(row_cols) >= 2):
                max_header_r = r
                for rng in getattr(ws, "merged_cells", {}).ranges if hasattr(ws, "merged_cells") else []:
                    if r in range(rng.min_row, rng.max_row + 1):
                        for c_idx in row_cols.values():
                            if (c_idx + 1) in range(rng.min_col, rng.max_col + 1):
                                if rng.max_row > max_header_r:
                                    max_header_r = rng.max_row

                header_rows = list(range(r - 1, max_header_r))
                first_data_r = max_header_r
                capacity = max(0, ws.max_row - max_header_r)
                roster_table = RepeatingTableTopology(
                    table_index=0,
                    topology_type="student_roster",
                    header_rows=header_rows,
                    first_data_row_index=first_data_r,
                    template_row_index=first_data_r,
                    footer_row_indices=[],
                    columns=row_cols,
                    total_rows=ws.max_row,
                    total_cols=ws.max_column,
                    data_rows_capacity=capacity,
                    column_headers=col_headers,
                    sheet_name=actual_sheet_name,
                )
                repeating_tables.append(roster_table)
                break

        # Collect header lines for OrganizationalContext from top rows
        header_texts: List[str] = []
        for r in range(1, min(15, ws.max_row + 1)):
            for c in range(1, min(15, ws.max_column + 1)):
                val = ws.cell(row=r, column=c).value
                if val and isinstance(val, str) and val.strip():
                    header_texts.append(val.strip())

        org_context = self._extract_organizational_context(header_texts)
        sig_slots = self._detect_signatory_slots_xlsx(ws, actual_sheet_name, start_scan_row=1)

        fname = os.path.basename(xlsx_path).lower()
        is_lab = "lab" in fname
        title = "Grading Sheet (Lecture & Lab)" if is_lab else "Grading Sheet (Lecture)"
        suffix = "GRADING_SHEET_LAB" if is_lab else "GRADING_SHEET"

        return TemplateManifest(
            template_path=xlsx_path,
            file_type="xlsx",
            content_hash=content_hash,
            template_type="grading_sheet",
            suggested_title=title,
            suggested_suffix=suffix,
            slots=slots,
            repeating_tables=repeating_tables,
            roster_table=roster_table,
            organizational_context=org_context,
            signatory_slots=sig_slots,
            confidence=1.0 if roster_table is not None else 0.8,
        )

    def _detect_repeating_table(self, grid: DocxGridTable, t_idx: int) -> Optional[RepeatingTableTopology]:
        """Detects if a DocxGridTable contains a repeating student roster or matrix."""
        if grid.num_rows < 3:
            return None

        header_row_idx: Optional[int] = None
        cols_map: Dict[str, int] = {}
        headers_text: Dict[int, str] = {}

        # Check first 3 rows for table column headers
        for r in range(min(3, grid.num_rows)):
            row_cells = grid.row(r)
            row_cols_map: Dict[str, int] = {}
            for cell in row_cells:
                txt = cell.text.strip()
                c = cell.origin_col
                if txt and c not in headers_text:
                    headers_text[c] = txt
                if COLUMN_NAME_PATTERNS.search(txt) and "name" not in row_cols_map:
                    row_cols_map["name"] = c
                elif COLUMN_ID_PATTERNS.search(txt) and "student_number" not in row_cols_map:
                    row_cols_map["student_number"] = c
                elif COLUMN_INDEX_PATTERNS.search(txt) and "index" not in row_cols_map:
                    row_cols_map["index"] = c
                elif COLUMN_SIGNATURE_PATTERNS.search(txt) and "signature" not in row_cols_map:
                    row_cols_map["signature"] = c

            if "name" in row_cols_map and ("student_number" in row_cols_map or "signature" in row_cols_map):
                header_row_idx = r
                cols_map = row_cols_map
                break

        if header_row_idx is None:
            return None

        # Determine header rows range (accounting for vertical continuation rows)
        max_hspan = max((grid.cell(header_row_idx, c).row_span for c in range(grid.num_cols)), default=1)
        header_rows = list(range(header_row_idx, header_row_idx + max_hspan))
        first_data_row = header_row_idx + max_hspan

        # Detect footer rows (summary or signature blocks at table bottom)
        footer_rows: List[int] = []
        for r in range(grid.num_rows - 1, first_data_row, -1):
            r_text = " ".join(grid.cell(r, c).text for c in range(grid.num_cols)).lower()
            if any(term in r_text for term in ("total", "prepared by", "submitted by", "instructor")):
                footer_rows.insert(0, r)
            else:
                break

        end_data_row = footer_rows[0] if footer_rows else grid.num_rows
        capacity = max(0, end_data_row - first_data_row)

        # Distinguish attendance matrix vs standard student roster
        all_header_text = " ".join(headers_text.values()).lower()
        if "week" in all_header_text or "attendance" in all_header_text or "month" in all_header_text:
            topo_type = "attendance_matrix"
        else:
            topo_type = "student_roster"

        return RepeatingTableTopology(
            table_index=t_idx,
            topology_type=topo_type,
            header_rows=header_rows,
            first_data_row_index=first_data_row,
            template_row_index=first_data_row,
            footer_row_indices=footer_rows,
            columns=cols_map,
            total_rows=grid.num_rows,
            total_cols=grid.num_cols,
            data_rows_capacity=capacity,
            column_headers=headers_text,
        )

    def _infer_template_identity(
        self,
        path: str,
        doc_text: str,
        repeating: List[RepeatingTableTopology],
    ) -> Tuple[str, str, str]:
        """Infers (template_type, suggested_title, output_suffix)."""
        fname = os.path.basename(path).lower()
        text_lower = doc_text.lower()

        if "attendance" in fname or "attendance" in text_lower or any(r.topology_type == "attendance_matrix" for r in repeating):
            return "attendance", "Attendance Sheet", "ATTENDANCE"
        elif "syllabus" in fname or "syllabus" in text_lower:
            return "academic_ceit", "Syllabus Acceptance", "SYLLABUS_ACCEPTANCE"
        elif "tos" in fname or "table of specification" in text_lower:
            if "final" in fname or "finals" in text_lower:
                return "academic_ceit", "Table of Specification (Final)", "TOS_FINALS"
            return "academic_ceit", "Table of Specification (Midterm)", "TOS_MIDTERM"
        elif "exam" in fname or "examination" in text_lower or "test" in text_lower:
            if "final" in fname or "finals" in text_lower:
                return "academic_ceit", "Examination Returns (Final)", "EXAM_RETURNS_FINALS"
            return "academic_ceit", "Examination Returns (Midterm)", "EXAM_RETURNS_MIDTERM"
        elif "discussion" in fname or "grade discussion" in text_lower:
            if "final" in fname or "finals" in text_lower:
                return "academic_ceit", "Grade Discussion (Final)", "FINAL_GRADE_DISCUSSION"
            return "academic_ceit", "Grade Discussion (Midterm)", "MIDTERM_GRADE_DISCUSSION"

        return "generic_form", "Custom Document Form", "CUSTOM_FORM"

    def _extract_organizational_context(self, text_lines: List[str]) -> Optional[OrganizationalContext]:
        """
        Extracts institutional and collegiate hierarchy (Institution, Campus, College, Department)
        from header text lines using deterministic pattern matching without hardcoded dropdown lists.
        """
        institution = "CAVITE STATE UNIVERSITY"
        campus: Optional[str] = None
        college: Optional[str] = None
        department: Optional[str] = None
        raw_headers: List[str] = []

        has_cvsu = False
        for raw_line in text_lines:
            line = raw_line.strip()
            if not line:
                continue

            if RE_INSTITUTION.search(line):
                has_cvsu = True
                raw_headers.append(line)
                continue

            if campus is None:
                m_campus = RE_CAMPUS.search(line)
                if m_campus:
                    extracted = m_campus.group(0).strip()
                    clean_campus = re.sub(r"^CvSU\s*[-–]\s*", "", extracted, flags=re.IGNORECASE).strip()
                    campus = clean_campus
                    raw_headers.append(line)
                    continue

            if college is None:
                m_college = RE_COLLEGE.search(line)
                if m_college:
                    college = m_college.group(0).strip()
                    raw_headers.append(line)
                    continue

            if department is None:
                m_dept = RE_DEPARTMENT.search(line)
                if m_dept:
                    department = m_dept.group(0).strip()
                    raw_headers.append(line)
                    continue

        if not has_cvsu and not campus and not college and not department:
            return None

        return OrganizationalContext(
            institution=institution,
            campus=campus,
            college=college,
            department=department,
            raw_headers=raw_headers,
            confidence=1.0 if has_cvsu and (college or department or campus) else 0.8,
        )

    @staticmethod
    def _infer_signatory_key_and_title(role_label: str, title_text: str = "") -> Tuple[str, str, str]:
        """
        Determines (slot_id, bound_key, normalized_default_title).
        """
        lbl_lower = role_label.lower().strip()
        title_lower = title_text.lower().strip()

        # Find best title
        detected_title = title_text.strip()
        if not detected_title:
            for pat, std_title in DEFAULT_TITLE_PATTERNS:
                if pat.search(title_lower) or pat.search(lbl_lower):
                    detected_title = std_title
                    title_lower = detected_title.lower()
                    break

        if not detected_title:
            if "prepared" in lbl_lower or "submitted" in lbl_lower:
                detected_title = "Instructor"
            elif "reviewed" in lbl_lower or "recommending" in lbl_lower:
                detected_title = "Department Chairperson"
            elif "approved" in lbl_lower:
                detected_title = "College Dean"

        # Determine slot_id and bound_key
        if "prepared" in lbl_lower or "submitted" in lbl_lower:
            slot_id = "prepared_by"
            bound_key = "prepared_by"
        elif "reviewed" in lbl_lower:
            slot_id = "reviewed_by"
            bound_key = "department_chair" if ("chair" in title_lower or "dept" in title_lower) else "reviewed_by"
        elif "recommending" in lbl_lower:
            slot_id = "recommending_approval"
            bound_key = "department_chair" if ("chair" in title_lower or "dept" in title_lower) else "recommending_approval"
        elif "noted" in lbl_lower:
            slot_id = "noted_by"
            bound_key = "program_coordinator" if ("coordinator" in title_lower) else "noted_by"
        elif "approved" in lbl_lower:
            slot_id = "approved_by"
            if "administrator" in title_lower or "admin" in title_lower:
                bound_key = "campus_administrator"
            elif "dean" in title_lower:
                bound_key = "college_dean"
            else:
                bound_key = "approved_by"
        elif "certified" in lbl_lower:
            slot_id = "certified_correct"
            bound_key = "certified_correct"
        else:
            slot_id = re.sub(r"[^a-z0-9_]+", "_", lbl_lower).strip("_") or "signatory"
            bound_key = slot_id

        return slot_id, bound_key, detected_title

    def _detect_signatory_slots_docx(
        self,
        grid_tables: List[DocxGridTable],
        paragraphs: List[etree._Element],
        roster_table: Optional[RepeatingTableTopology],
    ) -> List[SignatorySlot]:
        """
        Scans footer tables, signature rows, and trailing paragraphs for N-tier signatory slots.
        """
        slots: List[SignatorySlot] = []
        seen_coords = set()

        for t_idx, grid in enumerate(grid_tables):
            is_roster = (roster_table is not None and t_idx == roster_table.table_index)
            rows_to_check = roster_table.footer_row_indices if (is_roster and roster_table.footer_row_indices) else range(grid.num_rows)

            for r_idx in rows_to_check:
                for c_idx in range(grid.num_cols):
                    cell = grid.cell(r_idx, c_idx)
                    if not cell.is_origin or not cell.text:
                        continue

                    m_anchor = RE_SIG_ANCHORS.search(cell.text)
                    if not m_anchor:
                        continue

                    role_label = cell.text.strip()
                    lines = [ln.strip() for ln in cell.text.split("\n") if ln.strip()]
                    title_text = ""
                    t_r: Optional[int] = None
                    t_c: Optional[int] = None
                    title_r: Optional[int] = None
                    title_c: Optional[int] = None

                    if r_idx + 1 < grid.num_rows:
                        t_r = r_idx + 1
                        t_c = c_idx
                        if r_idx + 2 < grid.num_rows:
                            title_r = r_idx + 2
                            title_c = c_idx
                            title_text = grid.cell(r_idx + 2, c_idx).text.strip()
                        else:
                            r1_text = grid.cell(r_idx + 1, c_idx).text.strip()
                            r1_lines = [l.strip() for l in r1_text.split("\n") if l.strip()]
                            if len(r1_lines) > 1:
                                title_text = r1_lines[-1]
                    else:
                        if len(lines) >= 3:
                            t_r = r_idx
                            t_c = c_idx
                            title_text = lines[-1]
                        elif c_idx + 1 < grid.num_cols:
                            t_r = r_idx
                            t_c = c_idx + 1

                    if t_r is None or t_c is None:
                        continue

                    coord_key = (t_idx, t_r, t_c)
                    if coord_key in seen_coords:
                        continue
                    seen_coords.add(coord_key)

                    slot_id, bound_key, def_title = self._infer_signatory_key_and_title(role_label, title_text)

                    slots.append(SignatorySlot(
                        slot_id=slot_id,
                        role_label=role_label,
                        default_title=def_title,
                        bound_key=bound_key,
                        slot_type="table_cell",
                        table_index=t_idx,
                        row_index=r_idx,
                        col_index=c_idx,
                        target_row_index=t_r,
                        target_col_index=t_c,
                        title_row_index=title_r,
                        title_col_index=title_c,
                        strategy="set_cell_text",
                    ))

        # Check paragraphs
        for p_idx, p in enumerate(paragraphs):
            p_text = get_full_text(p).strip()
            if not p_text:
                continue

            m_anchor = RE_SIG_ANCHORS.search(p_text)
            if not m_anchor or len(p_text) > 80:
                continue

            role_label = p_text.split(":", 1)[0] + ":" if ":" in p_text else p_text
            target_p = p_idx + 1 if p_idx + 1 < len(paragraphs) else p_idx
            title_p = p_idx + 2 if p_idx + 2 < len(paragraphs) else None
            title_text = get_full_text(paragraphs[title_p]).strip() if title_p is not None else ""

            slot_id, bound_key, def_title = self._infer_signatory_key_and_title(role_label, title_text)

            slots.append(SignatorySlot(
                slot_id=slot_id,
                role_label=role_label,
                default_title=def_title,
                bound_key=bound_key,
                slot_type="paragraph",
                paragraph_index=p_idx,
                target_paragraph_index=target_p,
                title_paragraph_index=title_p,
                strategy="set_paragraph_text",
            ))

        return slots

    def _detect_signatory_slots_xlsx(self, ws, sheet_name: str, start_scan_row: int = 1) -> List[SignatorySlot]:
        """
        Scans worksheet for signatory blocks (Prepared by, Recommending Approval, Approved by).
        """
        slots: List[SignatorySlot] = []
        seen_coords = set()

        for r in range(start_scan_row, min(ws.max_row + 1, 80)):
            for c in range(1, min(ws.max_column + 1, 30)):
                val = ws.cell(row=r, column=c).value
                if not val or not isinstance(val, str):
                    continue

                m_anchor = RE_SIG_ANCHORS.search(val)
                if not m_anchor or len(val) > 80:
                    continue

                role_label = val.strip()
                target_r = r + 1
                target_c = c
                target_coord = f"{openpyxl.utils.get_column_letter(target_c)}{target_r}"
                title_coord = f"{openpyxl.utils.get_column_letter(c)}{r + 2}" if r + 2 <= ws.max_row else None
                title_text = ""
                if r + 2 <= ws.max_row:
                    t_val = ws.cell(row=r + 2, column=c).value
                    if isinstance(t_val, str):
                        title_text = t_val.strip()

                if target_coord in seen_coords:
                    continue
                seen_coords.add(target_coord)

                slot_id, bound_key, def_title = self._infer_signatory_key_and_title(role_label, title_text)

                slots.append(SignatorySlot(
                    slot_id=slot_id,
                    role_label=role_label,
                    default_title=def_title,
                    bound_key=bound_key,
                    slot_type="excel_cell",
                    sheet_name=sheet_name,
                    row_index=r,
                    col_index=c,
                    target_row_index=target_r,
                    target_col_index=target_c,
                    cell_coord=f"{openpyxl.utils.get_column_letter(c)}{r}",
                    target_cell_coord=target_coord,
                    title_cell_coord=title_coord,
                    strategy="set_cell_value",
                ))

        return slots

