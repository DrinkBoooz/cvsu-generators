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
from typing import Any, Dict, List, Optional

from modules.common.logger import logger


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
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                try:
                    word = win32com.client.DispatchEx("Word.Application")
                    word.Visible = False
                    word.DisplayAlerts = 0
                    word.Quit()
                    del word
                    gc.collect()
                    try:
                        pythoncom.PumpWaitingMessages()
                    except Exception:
                        pass
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

        os.makedirs(output_dir, exist_ok=True)
        target_pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

        try:
            if self._converter_type == "win32com":
                import pythoncom
                import win32com.client

                pythoncom.CoInitialize()
                word = None
                try:
                    word = win32com.client.DispatchEx("Word.Application")
                    word.Visible = False
                    word.DisplayAlerts = 0
                    abs_docx = os.path.abspath(docx_path)
                    abs_pdf = os.path.abspath(target_pdf_path)
                    doc = word.Documents.Open(abs_docx, ReadOnly=True, ConfirmConversions=False)
                    try:
                        try:
                            doc.SaveAs(abs_pdf, FileFormat=17)  # wdFormatPDF = 17
                        except Exception:
                            doc.ExportAsFixedFormat(abs_pdf, 17, False, 0)
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
                convert_fn(docx_path, target_pdf_path)
            elif self._converter_type == "soffice" and self._soffice_bin:
                cmd = [
                    self._soffice_bin,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    output_dir,
                    docx_path,
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)

            if os.path.isfile(target_pdf_path):
                logger.info(f"Exported PDF deliverable: {target_pdf_path}")
                return target_pdf_path
            else:
                logger.warning(f"PDF export finished but target file not found: {target_pdf_path}")
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
        os.makedirs(output_dir, exist_ok=True)
        target_pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            excel = None
            try:
                excel = win32com.client.DispatchEx("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                abs_xlsx = os.path.abspath(xlsx_path)
                abs_pdf = os.path.abspath(target_pdf_path)
                wb = excel.Workbooks.Open(abs_xlsx, ReadOnly=True)
                try:
                    wb.ExportAsFixedFormat(0, abs_pdf)  # 0 = xlTypePDF
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
            if os.path.isfile(target_pdf_path):
                return target_pdf_path
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

            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            word = None
            try:
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
                for path in valid_paths:
                    if cancel_event and cancel_event.is_set():
                        break

                    base_name = os.path.splitext(os.path.basename(path))[0]
                    target_pdf_path = os.path.join(target_dir, f"{base_name}.pdf")
                    doc = None
                    try:
                        abs_docx = os.path.abspath(path)
                        abs_pdf = os.path.abspath(target_pdf_path)
                        doc = word.Documents.Open(abs_docx, ReadOnly=True, ConfirmConversions=False)
                        try:
                            doc.SaveAs(abs_pdf, FileFormat=17)
                        except Exception:
                            doc.ExportAsFixedFormat(abs_pdf, 17, False, 0)

                        if os.path.isfile(target_pdf_path):
                            converted.append(target_pdf_path)
                            logger.info(f"Exported PDF deliverable: {target_pdf_path}")
                        else:
                            logger.warning(f"PDF export finished but target file not found: {target_pdf_path}")
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
