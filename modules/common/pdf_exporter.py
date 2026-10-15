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

    def __init__(self):
        self._converter_type: Optional[str] = None
        self._soffice_bin: Optional[str] = None
        self._probe_converters()

    def _probe_converters(self) -> None:
        """Probes for available PDF conversion tools on the local system."""
        # 1. Check docx2pdf (optional external library)
        try:
            import importlib
            importlib.import_module("docx2pdf")
            self._converter_type = "docx2pdf"
            return
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"docx2pdf probe failed: {e}")

        # 2. Check soffice in PATH
        which_soffice = shutil.which("soffice") or shutil.which("soffice.exe")
        if which_soffice and os.path.isfile(which_soffice):
            self._converter_type = "soffice"
            self._soffice_bin = which_soffice
            return

        # 3. Check common LibreOffice installation paths on Windows
        for candidate in self._SOFFICE_CANDIDATE_PATHS:
            if os.path.isfile(candidate):
                self._converter_type = "soffice"
                self._soffice_bin = candidate
                return

        self._converter_type = None

    def is_available(self) -> bool:
        """Returns True if a valid local PDF converter is detected."""
        return self._converter_type is not None

    def get_available_converter(self) -> Optional[str]:
        """Returns the identifier of the active converter ('docx2pdf', 'soffice', or None)."""
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
            logger.info("PDF export skipped: no PDF conversion engine (docx2pdf or LibreOffice) installed.")
            return None

        base_name = os.path.splitext(os.path.basename(docx_path))[0]
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(docx_path)), "PDF_Submissions")
        
        os.makedirs(output_dir, exist_ok=True)
        target_pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

        try:
            if self._converter_type == "docx2pdf":
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

    def batch_export(
        self,
        docx_paths: List[str],
        output_base_dir: str,
        cancel_event: Optional[Any] = None,
        progress_cb: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Exports a batch of .docx documents into a 'PDF_Submissions/' subfolder under output_base_dir.

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
