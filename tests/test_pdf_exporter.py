"""
tests/test_pdf_exporter.py

Unit and regression test suite for headless PDF export functionality (modules.common.pdf_exporter).
Tests Windows COM automation, batch processing, error handling, cancellation,
and orchestrator integration.
"""

import os
import threading
from unittest.mock import MagicMock, patch

import docx
import pytest

from modules.common.pdf_exporter import PdfExporter


def _create_sample_docx(filepath: str, text: str = "Test document content") -> str:
    """Helper creating a valid minimal .docx file for testing."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    doc = docx.Document()
    doc.add_heading("CvSU Document Generator PDF Test", level=1)
    doc.add_paragraph(text)
    doc.save(filepath)
    return filepath


def test_pdf_exporter_detection():
    """PdfExporter should successfully detect an available converter on Windows (win32com)."""
    exporter = PdfExporter()
    assert exporter.is_available() is True
    converter = exporter.get_available_converter()
    assert converter in ("win32com", "docx2pdf", "soffice")


def test_pdf_exporter_single_convert(tmp_path):
    """PdfExporter.export_to_pdf should convert a valid .docx to .pdf."""
    exporter = PdfExporter()
    docx_file = str(tmp_path / "single_test.docx")
    _create_sample_docx(docx_file, "Single conversion test")

    out_dir = str(tmp_path / "PDF_Submissions")
    pdf_path = exporter.export_to_pdf(docx_file, output_dir=out_dir)

    assert pdf_path is not None
    assert os.path.isfile(pdf_path)
    assert os.path.getsize(pdf_path) > 0
    assert pdf_path.endswith("single_test.pdf")


def test_pdf_exporter_batch_export(tmp_path):
    """PdfExporter.batch_export should convert multiple documents into PDF_Submissions."""
    exporter = PdfExporter()
    doc1 = str(tmp_path / "doc1.docx")
    doc2 = str(tmp_path / "doc2.docx")
    _create_sample_docx(doc1, "Batch Doc 1")
    _create_sample_docx(doc2, "Batch Doc 2")

    progress_calls = []

    res = exporter.batch_export(
        [doc1, doc2],
        output_base_dir=str(tmp_path),
        progress_cb=lambda p: progress_calls.append(p),
    )

    assert res["available"] is True
    assert len(res["converted"]) == 2
    assert len(res["failed"]) == 0
    assert len(progress_calls) == 2
    for pdf in res["converted"]:
        assert os.path.isfile(pdf)
        assert os.path.getsize(pdf) > 0


def test_pdf_exporter_batch_export_cancellation(tmp_path):
    """PdfExporter.batch_export should stop early if cancel_event is set."""
    exporter = PdfExporter()
    doc1 = str(tmp_path / "cancel1.docx")
    doc2 = str(tmp_path / "cancel2.docx")
    _create_sample_docx(doc1, "Cancellation test 1")
    _create_sample_docx(doc2, "Cancellation test 2")

    cancel_ev = threading.Event()
    cancel_ev.set()  # Cancel immediately

    res = exporter.batch_export(
        [doc1, doc2],
        output_base_dir=str(tmp_path),
        cancel_event=cancel_ev,
    )

    assert len(res["converted"]) == 0


def test_pdf_exporter_nonexistent_file(tmp_path):
    """PdfExporter handles missing files gracefully without raising unhandled exceptions."""
    exporter = PdfExporter()
    missing_file = str(tmp_path / "nonexistent.docx")
    res = exporter.export_to_pdf(missing_file)
    assert res is None

    batch_res = exporter.batch_export([missing_file], output_base_dir=str(tmp_path))
    assert missing_file in batch_res["failed"]


def test_pdf_exporter_unavailable_fallback():
    """When no engine is available, batch_export returns graceful fallback dictionary."""
    exporter = PdfExporter()
    with patch.object(exporter, "is_available", return_value=False):
        res = exporter.batch_export(["dummy.docx"], output_base_dir="out")
        assert res["available"] is False
        assert len(res["converted"]) == 0


def test_pdf_exporter_extended_path_prefix(tmp_path):
    """PdfExporter should cleanly convert files even when paths have Windows \\\\?\\ prefix."""
    from modules.common.excel_utils import get_long_path
    exporter = PdfExporter()
    doc_path = str(tmp_path / "long_prefix_test.docx")
    _create_sample_docx(doc_path, "Testing with Windows extended path prefix")

    long_doc_path = get_long_path(doc_path)
    long_out_dir = get_long_path(str(tmp_path / "PDF_Submissions"))

    # Test single export
    pdf_path = exporter.export_to_pdf(long_doc_path, output_dir=long_out_dir)
    assert pdf_path is not None
    assert os.path.isfile(pdf_path)
    assert os.path.getsize(pdf_path) > 0

    # Test batch export
    res = exporter.batch_export([long_doc_path], output_base_dir=get_long_path(str(tmp_path)))
    assert len(res["converted"]) == 1
    assert os.path.isfile(res["converted"][0])

