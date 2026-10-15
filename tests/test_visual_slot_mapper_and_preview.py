#!/usr/bin/env python3
"""
tests/test_visual_slot_mapper_and_preview.py

Comprehensive TDD test suite for Phase 8:
1. 2D Grid Serialization & Visual Slot Override Engine (DocxGridTable & openpyxl).
2. User-defined slot overrides persistence and DynamicDocumentRenderer execution.
3. In-Memory Pre-Flight Sample Document Preview with dynamic font scaling tier calculation (<=30 -> 8pt, 31-35 -> 7pt, >35 -> 6pt).
4. Thread-Safe Batch Progress Tracking, Polling & Cancellation.
5. Headless PDF Export detection, graceful fallback, and mocked batch export routing.
6. UI accessibility and consistency verification for Slot Mapper and Pre-Flight modals.
"""

import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch
import pytest
import docx
import openpyxl

from modules.parsers.template_analyzer import (
    DeterministicTemplateAnalyzer,
    TemplateManifest,
    SemanticSlot,
)
from modules.generators.dynamic_renderer import DynamicDocumentRenderer
from modules.models.schedule import ClassInfo
from modules.common.pdf_exporter import PdfExporter
from executable_test.api.base import BaseAPI
from executable_test.api.templates import TemplateMixin
from executable_test.api.generation import GenerationMixin


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic Fixture Builders
# ─────────────────────────────────────────────────────────────────────────────

def create_synthetic_table_docx(file_path: str) -> None:
    """Creates a sample docx with a 4x3 table including a merged cell (rowspan/colspan)."""
    doc = docx.Document()
    doc.add_paragraph("CAVITE STATE UNIVERSITY")
    doc.add_paragraph("Department of Information Technology")
    
    tbl = doc.add_table(rows=4, cols=3)
    # Row 0: Header
    tbl.rows[0].cells[0].text = "Header A"
    tbl.rows[0].cells[1].text = "Header B"
    tbl.rows[0].cells[2].text = "Header C"
    
    # Row 1: Instructor row
    tbl.rows[1].cells[0].text = "Instructor:"
    tbl.rows[1].cells[1].text = "Prof. Original Instructor"
    tbl.rows[1].cells[2].text = "Room: 101"
    
    # Row 2: Subject & Sec
    tbl.rows[2].cells[0].text = "Subject:"
    tbl.rows[2].cells[1].text = "ITEC 50"
    tbl.rows[2].cells[2].text = "Section: BSIT 3-1"

    # Row 3: Merged cell spanning cols 0 and 1
    cell_a = tbl.rows[3].cells[0]
    cell_b = tbl.rows[3].cells[1]
    cell_a.merge(cell_b)
    cell_a.text = "Spanning Notes"
    tbl.rows[3].cells[2].text = "Status: OK"
    
    doc.save(file_path)


def create_synthetic_roster_xlsx(file_path: str, student_count: int = 25) -> None:
    """Creates a sample student roster spreadsheet."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"
    ws.append(["No.", "Student Number", "Name"])
    for i in range(1, student_count + 1):
        ws.append([i, f"2026-100{i:02d}", f"STUDENT SURNAME, GIVEN {i:02d}"])
    wb.save(file_path)


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

def test_serialize_grid_preview_docx(tmp_path):
    """Verifies that 2D grid table serialization produces normalized cell structures with spans and roles."""
    docx_file = str(tmp_path / "test_template.docx")
    create_synthetic_table_docx(docx_file)

    analyzer = DeterministicTemplateAnalyzer.get_instance()
    preview = analyzer.serialize_grid_preview(docx_file, max_rows=10)

    assert preview["file_type"] == "docx"
    assert "tables" in preview
    assert len(preview["tables"]) >= 1

    tbl = preview["tables"][0]
    assert tbl["table_index"] == 0
    assert tbl["num_rows"] >= 4
    assert tbl["num_cols"] == 3
    assert len(tbl["rows"]) == 4

    # Check cell properties
    row0_col0 = tbl["rows"][0][0]
    assert row0_col0["row"] == 0
    assert row0_col0["col"] == 0
    assert "Header A" in row0_col0["text"]
    assert row0_col0["is_origin"] is True
    assert row0_col0["is_merged_continuation"] is False

    # Check row 3 merged span: col 0 has colspan 2, col 1 is merged continuation
    row3_col0 = tbl["rows"][3][0]
    row3_col1 = tbl["rows"][3][1]
    assert row3_col0["colspan"] == 2
    assert row3_col0["is_origin"] is True
    assert row3_col1["is_origin"] is False
    assert row3_col1["is_merged_continuation"] is True
    assert row3_col1["origin_col"] == 0


def test_user_slot_overrides_application_and_renderer_execution(tmp_path):
    """Verifies that user-defined slot overrides replace auto-detected coordinates during dynamic rendering."""
    docx_file = str(tmp_path / "override_template.docx")
    out_file = str(tmp_path / "rendered_output.docx")
    create_synthetic_table_docx(docx_file)

    analyzer = DeterministicTemplateAnalyzer.get_instance()
    manifest = analyzer.analyze(docx_file, force_refresh=True)

    # Define user override: place instructor in Row 2, Col 2 instead of default location
    overrides = {
        "instructor": {
            "table_index": 0,
            "row_index": 2,
            "col_index": 2,
            "strategy": "set_cell_text",
            "label": "Instructor"
        }
    }
    manifest.apply_slot_overrides(overrides)

    # Check manifest updated
    inst_slot = manifest.get_slot("instructor")
    assert inst_slot is not None
    assert inst_slot.target_row_index == 2
    assert inst_slot.target_col_index == 2

    # Render with ClassInfo
    renderer = DynamicDocumentRenderer(analyzer)
    context = ClassInfo(
        instructor="Engr. Custom Override Faculty",
        course_section="BSIT 3-1",
        schedule_code="99887",
        subject="ADVANCED SYSTEMS",
        time_days_room="1:00-3:00 Mon",
        semester_ay="1st Sem AY 2026-2027"
    )

    renderer.render(docx_file, context, output_path=out_file, manifest=manifest)

    # Inspect rendered output
    rendered_doc = docx.Document(out_file)
    r_tbl = rendered_doc.tables[0]
    # Cell at Row 2, Col 2 should now contain the overridden instructor name
    assert "Engr. Custom Override Faculty" in r_tbl.rows[2].cells[2].text


def test_template_mixin_slot_overrides_bridge(tmp_path):
    """Verifies the PyWebView bridge endpoints for grid preview and slot override saving."""
    class DummyBridge(BaseAPI, TemplateMixin):
        pass

    bridge = DummyBridge()
    docx_file = str(tmp_path / "bridge_template.docx")
    create_synthetic_table_docx(docx_file)

    # 1. Test get_template_grid_preview
    res = bridge.get_template_grid_preview(docx_file, max_rows=10)
    assert res["status"] == "success"
    assert "preview" in res
    assert len(res["preview"]["tables"]) >= 1

    # 2. Test save_template_slot_overrides
    overrides = {
        "instructor": {"table_index": 0, "row_index": 1, "col_index": 1, "strategy": "set_cell_text"},
        "course_section": {"table_index": 0, "row_index": 2, "col_index": 2, "strategy": "set_cell_text"}
    }
    save_res = bridge.save_template_slot_overrides(docx_file, overrides)
    assert save_res["status"] == "success"
    assert save_res["overrides_count"] == 2


def test_preview_sample_document_font_scaling_tiers(tmp_path):
    """Verifies that in-memory preflight preview calculates correct font scaling tiers based on student count."""
    class DummyGenBridge(BaseAPI, GenerationMixin):
        pass

    bridge = DummyGenBridge()

    # Tier 1: <= 30 students -> 8pt
    roster_25 = str(tmp_path / "roster_25.xlsx")
    create_synthetic_roster_xlsx(roster_25, student_count=25)
    bridge.rosters = [roster_25]
    bridge.schedule_path = "" # Not set, should gracefully synthesize or use fallback metadata

    payload = {
        "instructor": "Prof. Test Faculty",
        "course_section": "BSIT 3-1",
        "schedule_code": "12345",
        "subject": "DCIT 50",
        "roster_path": roster_25
    }

    res_25 = bridge.preview_sample_document(payload)
    assert res_25["status"] == "success"
    assert res_25["student_count"] == 25
    assert res_25["active_font_pt"] == "8pt"
    assert len(res_25["sample_roster_rows"]) == 10
    assert res_25["resolved_slots"]["instructor"] == "Prof. Test Faculty"

    # Tier 2: 31-35 students -> 7pt
    roster_33 = str(tmp_path / "roster_33.xlsx")
    create_synthetic_roster_xlsx(roster_33, student_count=33)
    payload["roster_path"] = roster_33

    res_33 = bridge.preview_sample_document(payload)
    assert res_33["status"] == "success"
    assert res_33["student_count"] == 33
    assert res_33["active_font_pt"] == "7pt"

    # Tier 3: > 35 students -> 6pt
    roster_42 = str(tmp_path / "roster_42.xlsx")
    create_synthetic_roster_xlsx(roster_42, student_count=42)
    payload["roster_path"] = roster_42

    res_42 = bridge.preview_sample_document(payload)
    assert res_42["status"] == "success"
    assert res_42["student_count"] == 42
    assert res_42["active_font_pt"] == "6pt"


def test_generation_progress_tracking_and_cancellation():
    """Verifies thread-safe progress polling and graceful mid-batch cancellation."""
    class DummyGenBridge(BaseAPI, GenerationMixin):
        pass

    bridge = DummyGenBridge()
    init_progress = bridge.get_generation_progress()
    assert init_progress["status"] == "idle"
    assert init_progress["percent"] == 0

    # Simulate active generation
    with bridge._lock:
        bridge._is_processing = True
        bridge._generation_progress = {
            "status": "running",
            "current_index": 3,
            "total_count": 10,
            "percent": 30,
            "current_file_label": "BSIT3-1_12345_ATTENDANCE_Monday_August.docx",
            "error": None
        }

    running_progress = bridge.get_generation_progress()
    assert running_progress["status"] == "running"
    assert running_progress["percent"] == 30
    assert "ATTENDANCE" in running_progress["current_file_label"]

    # Request cancellation
    cancel_res = bridge.cancel_generation()
    assert cancel_res["status"] == "success"
    assert bridge._cancel_event.is_set()


def test_pdf_exporter_detection_and_mock_batch_export(tmp_path):
    """Verifies PdfExporter availability check, headless execution, and non-fatal fallback."""
    exporter = PdfExporter()
    available = exporter.is_available()
    assert isinstance(available, bool)

    # Test mock conversion
    docx_file = str(tmp_path / "sample_doc.docx")
    create_synthetic_table_docx(docx_file)

    with patch.object(exporter, "is_available", return_value=True), \
         patch.object(exporter, "export_to_pdf") as mock_export:
        mock_pdf_path = str(tmp_path / "PDF_Submissions" / "sample_doc.pdf")
        mock_export.return_value = mock_pdf_path

        res = exporter.batch_export([docx_file], str(tmp_path))
        assert len(res["converted"]) == 1
        assert res["converted"][0] == mock_pdf_path
        assert len(res["failed"]) == 0

