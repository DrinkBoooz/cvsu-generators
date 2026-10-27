#!/usr/bin/env python3
"""
modules/common/pdf_exporter.py

Headless PDF Export Utility for CvSU Document Deliverables.
Converts generated .docx files into standard PDF format in a dedicated
'PDF_Submissions/' subfolder.

Supports multiple conversion backends:
  1. Windows Word COM Automation via 'docx2pdf'
  2. Headless LibreOffice ('soffice --headless --convert-to pdf')
  3. Graceful non-fatal fallback when no conversion binary is available on the system.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import queue
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional

from modules.common.excel_utils import strip_long_path_prefix
from modules.common.logger import logger


def _get_com_modules():
    """Dynamically loads Windows COM modules (win32com.client, pythoncom) if available."""
    try:
        import importlib
        w32_client = importlib.import_module("win32com.client")
        pycom = importlib.import_module("pythoncom")
        return w32_client, pycom
    except Exception:
        return None, None


class PdfExporter:
    """
    Headless Word-to-PDF export service with multi-backend detection
    and graceful non-fatal fallback.
    """

    _SOFFICE_CANDIDATE_PATHS = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]

    _cached_converter_type: Optional[str] = None
    _cached_soffice_bin: Optional[str] = None
    _probe_completed: bool = False

    def __init__(self):
        self._converter_type: Optional[str] = None
        self._soffice_bin: Optional[str] = None
        self._probe_converters()

    def _probe_converters(self) -> None:
        """Probes for available PDF conversion tools on the local system."""
        if PdfExporter._probe_completed:
            self._converter_type = PdfExporter._cached_converter_type
            self._soffice_bin = PdfExporter._cached_soffice_bin
            return

        # 1. Check native Windows Word COM Automation via win32com
        if sys.platform == "win32":
            try:
                import gc
                win32_client, pythoncom = _get_com_modules()
                if not win32_client or not pythoncom:
                    raise ImportError("win32com / pythoncom not available")
                pythoncom.CoInitialize()
                try:
                    word = win32_client.DispatchEx("Word.Application")
                    word.Visible = False
                    word.DisplayAlerts = 0
                    word.Quit()
                    del word
                    gc.collect()
                    self._converter_type = "win32com"
                    PdfExporter._cached_converter_type = self._converter_type
                    PdfExporter._probe_completed = True
                    return
                finally:
                    pythoncom.CoUninitialize()
            except Exception as e:
                logger.debug(f"win32com Word probe failed: {e}")

        # 2. Check docx2pdf (optional external library)
        try:
            import importlib
            importlib.import_module("docx2pdf")
            self._converter_type = "docx2pdf"
            PdfExporter._cached_converter_type = self._converter_type
            PdfExporter._probe_completed = True
            return
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"docx2pdf probe failed: {e}")

        # 3. Check soffice in PATH
        which_soffice = shutil.which("soffice") or shutil.which("soffice.exe")
        if which_soffice and os.path.isfile(which_soffice):
            self._converter_type = "soffice"
            self._soffice_bin = which_soffice
            PdfExporter._cached_converter_type = self._converter_type
            PdfExporter._cached_soffice_bin = self._soffice_bin
            PdfExporter._probe_completed = True
            return

        # 4. Check common LibreOffice installation paths on Windows
        for candidate in self._SOFFICE_CANDIDATE_PATHS:
            if os.path.isfile(candidate):
                self._converter_type = "soffice"
                self._soffice_bin = candidate
                PdfExporter._cached_converter_type = self._converter_type
                PdfExporter._cached_soffice_bin = self._soffice_bin
                PdfExporter._probe_completed = True
                return

        self._converter_type = None
        PdfExporter._cached_converter_type = None
        PdfExporter._probe_completed = True

    def is_available(self) -> bool:
        """Returns True if a valid local PDF converter is detected."""
        return self._converter_type is not None

    def get_available_converter(self) -> Optional[str]:
        """Returns the identifier of the active converter ('win32com', 'docx2pdf', 'soffice', or None)."""
        return self._converter_type

    def export_to_pdf(self, docx_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        Converts a single .docx document to .pdf.

        Args:
            docx_path: Absolute or relative path to the source .docx file.
            output_dir: Target directory for the resulting .pdf.
                        If omitted, defaults to a 'PDF_Submissions/' subfolder
                        alongside the source document.

        Returns:
            The path to the generated PDF if successful, or None if skipped/failed.
        """
        if not os.path.isfile(docx_path):
            logger.warning(f"PDF export skipped: source file does not exist ({docx_path})")
            return None

        if not self.is_available():
            logger.info("PDF export skipped: no PDF conversion engine (Word COM, docx2pdf, or LibreOffice) installed.")
            return None

        base_name = os.path.splitext(os.path.basename(docx_path))[0]
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(docx_path)), "PDF_Submissions")

        clean_out_dir = strip_long_path_prefix(os.path.abspath(output_dir))
        os.makedirs(clean_out_dir, exist_ok=True)
        target_pdf_path = os.path.join(clean_out_dir, f"{base_name}.pdf")

        clean_docx = strip_long_path_prefix(os.path.abspath(docx_path))
        clean_pdf = strip_long_path_prefix(os.path.abspath(target_pdf_path))

        try:
            if self._converter_type == "win32com":
                win32_client, pythoncom = _get_com_modules()
                if not win32_client or not pythoncom:
                    return None

                pythoncom.CoInitialize()
                word = None
                try:
                    word = win32_client.DispatchEx("Word.Application")
                    word.Visible = False
                    word.DisplayAlerts = 0
                    doc = word.Documents.Open(clean_docx, ReadOnly=True, ConfirmConversions=False)
                    if not doc:
                        logger.warning(f"Word failed to open document: {clean_docx}")
                        return None
                    try:
                        try:
                            doc.SaveAs(clean_pdf, FileFormat=17)  # wdFormatPDF = 17
                        except Exception:
                            doc.ExportAsFixedFormat(clean_pdf, 17, False, 0)
                    finally:
                        doc.Close(False)
                finally:
                    if word:
                        try:
                            word.Quit()
                        except Exception:
                            pass
                        del word
                    import gc
                    gc.collect()
                    try:
                        pythoncom.PumpWaitingMessages()
                    except Exception:
                        pass
                    pythoncom.CoUninitialize()
            elif self._converter_type == "docx2pdf":
                import importlib
                docx2pdf_mod = importlib.import_module("docx2pdf")
                convert_fn = getattr(docx2pdf_mod, "convert")
                convert_fn(clean_docx, clean_pdf)
            elif self._converter_type == "soffice" and self._soffice_bin:
                cmd = [
                    self._soffice_bin,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    clean_out_dir,
                    clean_docx,
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)

            if os.path.isfile(clean_pdf):
                logger.info(f"Exported PDF deliverable: {clean_pdf}")
                return clean_pdf
            else:
                logger.warning(f"PDF export finished but target file not found: {clean_pdf}")
                return None
        except Exception as e:
            logger.warning(f"Non-fatal error exporting {docx_path} to PDF: {e}")
            return None

    def export_excel_to_pdf(self, xlsx_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """Converts an Excel spreadsheet (.xlsx) to .pdf via Windows Excel COM automation."""
        if not os.path.isfile(xlsx_path):
            return None
        if sys.platform != "win32":
            return None
        base_name = os.path.splitext(os.path.basename(xlsx_path))[0]
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(xlsx_path)), "PDF_Submissions")
        clean_out_dir = strip_long_path_prefix(os.path.abspath(output_dir))
        os.makedirs(clean_out_dir, exist_ok=True)
        target_pdf_path = os.path.join(clean_out_dir, f"{base_name}.pdf")

        clean_xlsx = strip_long_path_prefix(os.path.abspath(xlsx_path))
        clean_pdf = strip_long_path_prefix(os.path.abspath(target_pdf_path))

        try:
            win32_client, pythoncom = _get_com_modules()
            if not win32_client or not pythoncom:
                return None

            pythoncom.CoInitialize()
            excel = None
            try:
                excel = win32_client.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                wb = excel.Workbooks.Open(clean_xlsx, ReadOnly=True)
                if not wb:
                    logger.warning(f"Excel failed to open workbook: {clean_xlsx}")
                    return None
                try:
                    wb.ExportAsFixedFormat(0, clean_pdf)  # 0 = xlTypePDF
                finally:
                    wb.Close(False)
            finally:
                if excel:
                    try:
                        excel.Quit()
                    except Exception:
                        pass
                    del excel
                import gc
                gc.collect()
                try:
                    pythoncom.PumpWaitingMessages()
                except Exception:
                    pass
                pythoncom.CoUninitialize()
            if os.path.isfile(clean_pdf):
                return clean_pdf
        except Exception as e:
            logger.warning(f"Error exporting {xlsx_path} to PDF via Excel COM: {e}")
        return None

    def batch_export(
        self,
        docx_paths: List[str],
        output_base_dir: str,
        cancel_event: Optional[Any] = None,
        progress_cb: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Exports a batch of .docx documents into a 'PDF_Submissions/' subfolder under output_base_dir.
        For win32com on Windows, reuses a single Word instance to achieve high-speed batch conversion.

        Returns:
            Dictionary with 'converted', 'failed', 'available', and 'converter' fields.
        """
        converted: List[str] = []
        failed: List[str] = []

        if not self.is_available():
            return {
                "converted": converted,
                "failed": failed,
                "available": False,
                "converter": None,
                "message": "No local PDF converter installed (MS Word or LibreOffice)."
            }

        target_dir = os.path.join(output_base_dir, "PDF_Submissions")
        os.makedirs(target_dir, exist_ok=True)

        clean_target_dir = strip_long_path_prefix(os.path.abspath(target_dir))
        os.makedirs(clean_target_dir, exist_ok=True)

        # High-performance batch path using a single Word.Application instance
        if self._converter_type == "win32com":
            valid_paths = []
            for path in docx_paths:
                if not os.path.isfile(path):
                    logger.warning(f"PDF export skipped: source file does not exist ({path})")
                    failed.append(path)
                else:
                    valid_paths.append(path)

            if not valid_paths or (cancel_event and cancel_event.is_set()):
                return {
                    "converted": converted,
                    "failed": failed,
                    "available": True,
                    "converter": "win32com",
                }

            win32_client, pythoncom = _get_com_modules()
            if not win32_client or not pythoncom:
                return {"available": False, "converted": [], "failed": valid_paths, "converter": None}

            pythoncom.CoInitialize()
            word = None
            try:
                word = win32_client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
                for path in valid_paths:
                    if cancel_event and cancel_event.is_set():
                        break

                    base_name = os.path.splitext(os.path.basename(path))[0]
                    target_pdf_path = os.path.join(clean_target_dir, f"{base_name}.pdf")
                    clean_docx = strip_long_path_prefix(os.path.abspath(path))
                    clean_pdf = strip_long_path_prefix(os.path.abspath(target_pdf_path))
                    doc = None
                    try:
                        doc = word.Documents.Open(clean_docx, ReadOnly=True, ConfirmConversions=False)
                        if not doc:
                            logger.warning(f"Word failed to open document: {clean_docx}")
                            failed.append(path)
                            continue

                        try:
                            doc.SaveAs(clean_pdf, FileFormat=17)
                        except Exception:
                            doc.ExportAsFixedFormat(clean_pdf, 17, False, 0)

                        if os.path.isfile(clean_pdf):
                            converted.append(clean_pdf)
                            logger.info(f"Exported PDF deliverable: {clean_pdf}")
                        else:
                            logger.warning(f"PDF export finished but target file not found: {clean_pdf}")
                            failed.append(path)
                    except Exception as e:
                        logger.warning(f"Error converting {path} to PDF via win32com: {e}")
                        failed.append(path)
                    finally:
                        if doc:
                            try:
                                doc.Close(False)
                            except Exception:
                                pass

                    if progress_cb:
                        try:
                            progress_cb(path)
                        except Exception:
                            pass
            finally:
                if word:
                    try:
                        word.Quit()
                    except Exception:
                        pass
                    del word
                import gc
                gc.collect()
                try:
                    pythoncom.PumpWaitingMessages()
                except Exception:
                    pass
                pythoncom.CoUninitialize()

            return {
                "converted": converted,
                "failed": failed,
                "available": True,
                "converter": "win32com",
            }

        # Standard fallback loop for docx2pdf / soffice
        for path in docx_paths:
            if cancel_event and cancel_event.is_set():
                break
            pdf_path = self.export_to_pdf(path, output_dir=target_dir)
            if pdf_path:
                converted.append(pdf_path)
            else:
                failed.append(path)
            if progress_cb:
                try:
                    progress_cb(path)
                except Exception:
                    pass

        return {
            "converted": converted,
            "failed": failed,
            "available": True,
            "converter": self._converter_type,
        }


def merge_pdfs(pdf_paths: List[str], output_merged_path: str) -> Optional[str]:
    """
    Merges multiple PDF files into a single unified PDF bundle using pypdf.
    Preserves exact vector rendering, fonts, landscape/portrait orientations,
    and page margins with 100% fidelity.

    Args:
        pdf_paths: List of absolute or relative paths to PDF files to merge.
        output_merged_path: Target path for the combined output PDF.

    Returns:
        The output_merged_path if successful, or None on failure.
    """
    if not pdf_paths:
        return None

    valid_pdfs = [p for p in pdf_paths if p and os.path.isfile(p)]
    if not valid_pdfs:
        return None

    clean_out = strip_long_path_prefix(os.path.abspath(output_merged_path))
    os.makedirs(os.path.dirname(clean_out), exist_ok=True)

    try:
        from pypdf import PdfWriter

        writer = PdfWriter()
        for p in valid_pdfs:
            clean_p = strip_long_path_prefix(os.path.abspath(p))
            writer.append(clean_p)

        with open(clean_out, "wb") as f_out:
            writer.write(f_out)
        writer.close()

        if os.path.isfile(clean_out) and os.path.getsize(clean_out) > 0:
            logger.info(f"Generated merged PDF bundle ({len(valid_pdfs)} pages): {clean_out}")
            return clean_out
    except Exception as e:
        logger.warning(f"Error merging PDFs into {output_merged_path}: {e}")
    return None


class ConcurrentPdfPipeline:
    """
    Pipelined asynchronous PDF conversion service.
    Accepts documents concurrently as they are generated by generator engines,
    converting them in a background worker thread using a single persistent
    Word COM session (or LibreOffice CLI) to achieve maximal throughput.
    """

    def __init__(
        self,
        exporter: PdfExporter,
        cancel_event: Optional[Any] = None,
        progress_cb: Optional[Any] = None,
    ):
        self.exporter = exporter
        self.cancel_event = cancel_event
        self.progress_cb = progress_cb
        self._queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._converted: List[str] = []
        self._failed: List[str] = []
        self._by_class_category: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self._is_running = False

    def start(self) -> None:
        """Starts the background conversion worker thread."""
        self._is_running = True
        self._worker_thread = threading.Thread(
            target=self._run_worker,
            name="PdfExportPipelineWorker",
            daemon=True,
        )
        self._worker_thread.start()

    def submit(
        self,
        docx_path: str,
        output_dir: Optional[str] = None,
        category: str = "general",
        class_name: str = "general",
    ) -> None:
        """Enqueues a generated .docx file for concurrent PDF conversion."""
        if self._is_running:
            self._queue.put({
                "docx_path": docx_path,
                "output_dir": output_dir,
                "category": category,
                "class_name": class_name,
            })

    def _run_worker(self) -> None:
        """Worker loop executing conversions concurrently with the generation pipeline."""
        converter = self.exporter.get_available_converter()

        if converter == "win32com":
            self._run_win32com_worker()
        else:
            self._run_fallback_worker()

    def _run_win32com_worker(self) -> None:
        import gc
        win32_client, pythoncom = _get_com_modules()
        if not win32_client or not pythoncom:
            self._run_fallback_worker()
            return

        pythoncom.CoInitialize()
        word = None
        try:
            word = win32_client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0

            while self._is_running or not self._queue.empty():
                try:
                    item = self._queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                if item is None:  # Sentinel
                    self._queue.task_done()
                    break

                if self.cancel_event and self.cancel_event.is_set():
                    self._queue.task_done()
                    break

                docx_path = item["docx_path"]
                output_dir = item["output_dir"]
                category = item.get("category", "general")
                class_name = item.get("class_name", "general")

                if not os.path.isfile(docx_path):
                    self._failed.append(docx_path)
                    self._queue.task_done()
                    continue

                clean_docx = strip_long_path_prefix(os.path.abspath(docx_path))
                if not output_dir:
                    output_dir = os.path.dirname(clean_docx)
                clean_out_dir = strip_long_path_prefix(os.path.abspath(output_dir))
                os.makedirs(clean_out_dir, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(clean_docx))[0]
                clean_pdf = os.path.join(clean_out_dir, f"{base_name}.pdf")

                doc = None
                try:
                    doc = word.Documents.Open(clean_docx, ReadOnly=True, ConfirmConversions=False)
                    if doc:
                        try:
                            doc.SaveAs(clean_pdf, FileFormat=17)
                        except Exception:
                            doc.ExportAsFixedFormat(clean_pdf, 17, False, 0)

                        if os.path.isfile(clean_pdf):
                            self._converted.append(clean_pdf)
                            self._by_class_category[class_name][category].append(clean_pdf)
                            logger.info(f"Pipelined PDF Export: {clean_pdf}")
                            if self.progress_cb:
                                try:
                                    self.progress_cb(clean_pdf)
                                except Exception:
                                    pass
                        else:
                            self._failed.append(docx_path)
                    else:
                        self._failed.append(docx_path)
                except Exception as e:
                    logger.warning(f"Error in pipelined PDF conversion for {docx_path}: {e}")
                    self._failed.append(docx_path)
                finally:
                    if doc:
                        try:
                            doc.Close(False)
                        except Exception:
                            pass
                    self._queue.task_done()
        finally:
            try:
                if word:
                    try:
                        word.Quit()
                    except Exception:
                        pass
                    del word
            except Exception:
                pass
            gc.collect()
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _run_fallback_worker(self) -> None:
        while self._is_running or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                self._queue.task_done()
                break

            if self.cancel_event and self.cancel_event.is_set():
                self._queue.task_done()
                break

            docx_path = item["docx_path"]
            output_dir = item["output_dir"]
            category = item.get("category", "general")
            class_name = item.get("class_name", "general")

            pdf_path = self.exporter.export_to_pdf(docx_path, output_dir=output_dir)
            if pdf_path:
                self._converted.append(pdf_path)
                self._by_class_category[class_name][category].append(pdf_path)
                if self.progress_cb:
                    try:
                        self.progress_cb(pdf_path)
                    except Exception:
                        pass
            else:
                self._failed.append(docx_path)
            self._queue.task_done()

    def finish(self) -> Dict[str, Any]:
        """
        Signals the worker to drain any remaining tasks, terminates the worker thread,
        and returns the consolidated converted and failed files dictionary.
        """
        self._is_running = False
        self._queue.put(None)  # Sentinel
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=120)

        # Convert defaultdict to standard dict for serialization
        plain_by_class = {}
        for c_name, cat_dict in self._by_class_category.items():
            plain_by_class[c_name] = dict(cat_dict)

        return {
            "converted": self._converted,
            "failed": self._failed,
            "by_class_category": plain_by_class,
        }

