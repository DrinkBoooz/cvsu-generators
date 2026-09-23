#!/usr/bin/env python3
"""
modules/parsers/template_role_detector.py

Authoritative Dynamic Template Role Detector.
Preserves:
  INSPECTOR DISCOVERS WHERE.
  VALIDATOR VERIFIES WHERE.
  GENERATOR CONSUMES WHERE.
  NO LAYER MAY FABRICATE MISSING TEMPLATE COORDINATES.

Analyzes physical DOCX and XLSX templates through the authoritative
inspection layer and emits:
  - "confirmed": single unambiguous role with structural evidence
  - "ambiguous": candidate roles list requiring explicit user confirmation
  - "unsupported": physical structure does not match any canonical role

NEVER classifies using filename alone. Filenames are diagnostic hints only.
"""

from dataclasses import dataclass, field
import os
import re
from typing import Dict, Any, List, Optional, Tuple

import openpyxl

from modules.common.logger import logger
from modules.common.docx_utils import load_docx, get_full_text, w
from modules.models.recipe import (
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    PROFILE_REGISTRY,
)
from modules.models.template_set import (
    CANONICAL_ROLES,
    ROLE_PROFILE_MAPPING,
    ROLE_SYLLABUS,
    ROLE_EXAM_RETURNS_MIDTERM,
    ROLE_EXAM_RETURNS_FINAL,
    ROLE_TOS_MIDTERM,
    ROLE_TOS_FINAL,
    ROLE_GRADE_DISCUSSION_MIDTERM,
    ROLE_GRADE_DISCUSSION_FINAL,
    ROLE_ATTENDANCE_LECTURE,
    ROLE_ATTENDANCE_LECTURE_LAB,
    ROLE_GRADE_SHEET_LECTURE,
    ROLE_GRADE_SHEET_LECTURE_LAB,
)
from modules.parsers.template_inspector import (
    DocxTemplateInspector,
    AttendanceTemplateInspector,
    XlsxTemplateInspector,
)
from modules.parsers.recipe_validator import RecipeValidator


@dataclass
class DetectionResult:
    """Represents the outcome of physical template role analysis."""
    file_path: str
    file_name: str
    file_type: str
    status: str  # "confirmed" | "ambiguous" | "unsupported"
    role: Optional[str] = None
    candidate_roles: List[str] = field(default_factory=list)
    structural_evidence: List[str] = field(default_factory=list)
    diagnostic_hints: List[str] = field(default_factory=list)
    profile_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "status": self.status,
            "role": self.role,
            "candidate_roles": list(self.candidate_roles),
            "structural_evidence": list(self.structural_evidence),
            "diagnostic_hints": list(self.diagnostic_hints),
            "profile_id": self.profile_id,
            "error": self.error,
        }


class TemplateRoleDetector:
    """
    Service that analyzes DOCX and XLSX files using physical inspection
    to discover canonical template roles without relying on filename conventions.
    """

    def __init__(self):
        self._docx_inspector = DocxTemplateInspector()
        self._att_inspector = AttendanceTemplateInspector()
        self._xlsx_inspector = XlsxTemplateInspector()
        self._validator = RecipeValidator()

    def detect_role(self, file_path: str) -> DetectionResult:
        """
        Detects possible canonical roles for the given template file.
        Returns a DetectionResult with status 'confirmed', 'ambiguous', or 'unsupported'.
        """
        if not os.path.exists(file_path):
            return DetectionResult(
                file_path=file_path,
                file_name=os.path.basename(file_path),
                file_type="unknown",
                status="unsupported",
                error=f"File not found: {file_path}",
            )

        fn = os.path.basename(file_path)
        ext = os.path.splitext(fn)[1].lower()

        if ext == ".docx":
            return self._detect_docx(file_path, fn)
        elif ext == ".xlsx":
            return self._detect_xlsx(file_path, fn)
        else:
            return DetectionResult(
                file_path=file_path,
                file_name=fn,
                file_type=ext.lstrip("."),
                status="unsupported",
                error=f"Unsupported file format '{ext}'. Must be .docx or .xlsx",
            )

    def _detect_docx(self, file_path: str, file_name: str) -> DetectionResult:
        # Diagnostic filename hint (informational only; never authoritative)
        diag_hints = [f"File extension .docx; filename '{file_name}'"]
        fn_lower = file_name.lower()
        if "midterm" in fn_lower:
            diag_hints.append("Filename hint suggests: Midterm")
        if "final" in fn_lower:
            diag_hints.append("Filename hint suggests: Final")
        if "lec" in fn_lower and "lab" in fn_lower:
            diag_hints.append("Filename hint suggests: Lecture + Lab")
        elif "lec" in fn_lower:
            diag_hints.append("Filename hint suggests: Lecture")

        # 1. Probe for Attendance Sheet structure
        try:
            att_cand = self._att_inspector.inspect(file_path, profile_id="attendance_docx")
            if (
                att_cand.info_candidate is not None
                and att_cand.matrix_candidate is not None
                and att_cand.matrix_candidate.get("template_session_capacity", 0) >= 4
                and not att_cand.collisions
            ):
                return self._classify_attendance(file_path, file_name, att_cand, diag_hints)
        except Exception as e:
            logger.debug(f"Attendance inspection probe skipped or failed for {file_name}: {e}")

        # 2. Probe for Academic CEIT Document structure
        try:
            docx_cand = self._docx_inspector.inspect(file_path, profile_id="academic_docx")
        except AmbiguousTemplateError as e:
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=[
                    ROLE_SYLLABUS,
                    ROLE_EXAM_RETURNS_MIDTERM,
                    ROLE_EXAM_RETURNS_FINAL,
                    ROLE_TOS_MIDTERM,
                    ROLE_TOS_FINAL,
                    ROLE_GRADE_DISCUSSION_MIDTERM,
                    ROLE_GRADE_DISCUSSION_FINAL,
                ],
                structural_evidence=["Multiple candidate roster tables detected with equal prominence"],
                diagnostic_hints=diag_hints,
                error=str(e),
            )
        except Exception as e:
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="unsupported",
                diagnostic_hints=diag_hints,
                error=f"Failed to inspect DOCX structure: {e}",
            )

        return self._classify_academic_docx(file_path, file_name, docx_cand, diag_hints)

    def _classify_attendance(
        self,
        file_path: str,
        file_name: str,
        att_cand: Any,
        diag_hints: List[str],
    ) -> DetectionResult:
        evidence: List[str] = []
        matrix = att_cand.matrix_candidate
        info = att_cand.info_candidate

        info_t_idx = info.get("table_index")
        matrix_t_idx = matrix.get("table_index")
        cap = matrix.get("template_session_capacity", 0)
        date_start = matrix.get("date_columns_start", 0)
        summary_indices = matrix.get("summary_column_indices", ())

        evidence.append(f"Attendance info metadata table verified at table index {info_t_idx}")
        evidence.append(f"Attendance session matrix verified at table index {matrix_t_idx}")
        evidence.append(f"Template session capacity: {cap} columns (date start col {date_start})")

        # Scan text in the document body to inspect schedule/matrix evidence
        zin, root, body = load_docx(file_path)
        zin.close()
        doc_text = " ".join(get_full_text(p).strip() for p in body.findall(w("p")) if get_full_text(p).strip())
        for tbl in body.findall(w("tbl")):
            for tr in tbl.findall(w("tr")):
                for tc in tr.findall(w("tc")):
                    t = get_full_text(tc).strip()
                    if t:
                        doc_text += " " + t
        doc_upper = doc_text.upper()

        has_both_lec_and_lab_text = bool(
            ("LAB" in doc_upper or "LABORATORY" in doc_upper)
            and ("LEC" in doc_upper or "LECTURE" in doc_upper)
        )

        # Structural discrimination:
        # Standard Lecture Attendance has 4 session columns (1 day/week * 4 weeks)
        # Standard Lecture + Lab Attendance has 8 session columns (2 days/week: lab + lec * 4 weeks)
        if cap >= 8:
            evidence.append(f"Capacity {cap} session columns reflects multi-session Lecture + Lab attendance structure")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="confirmed",
                role=ROLE_ATTENDANCE_LECTURE_LAB,
                candidate_roles=[ROLE_ATTENDANCE_LECTURE_LAB],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="attendance_docx",
            )
        elif cap == 4:
            evidence.append("Capacity 4 session columns reflects single-session Lecture-only attendance structure")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="confirmed",
                role=ROLE_ATTENDANCE_LECTURE,
                candidate_roles=[ROLE_ATTENDANCE_LECTURE],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="attendance_docx",
            )
        else:
            # Capacity is non-standard (e.g. 5, 6, 7): return ambiguous candidates for explicit user selection
            evidence.append(f"Session capacity {cap} is non-standard (neither 4 nor 8 slots)")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=[ROLE_ATTENDANCE_LECTURE, ROLE_ATTENDANCE_LECTURE_LAB],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="attendance_docx",
            )

    def _classify_academic_docx(
        self,
        file_path: str,
        file_name: str,
        docx_cand: Any,
        diag_hints: List[str],
    ) -> DetectionResult:
        evidence: List[str] = []

        if docx_cand.roster_candidate:
            r = docx_cand.roster_candidate
            evidence.append(
                f"Student roster table identified at table index {r.get('table_index')} "
                f"(total rows: {r.get('total_rows')}, cols: {r.get('total_cols')})"
            )
        else:
            evidence.append("No student roster table detected (header metadata only)")

        # Inspect document text from paragraphs and table headers
        zin, root, body = load_docx(file_path)
        zin.close()
        doc_paras = [get_full_text(p).strip() for p in body.findall(w("p")) if get_full_text(p).strip()]
        doc_text = " ".join(doc_paras)

        for tbl in body.findall(w("tbl")):
            # Inspect first 10 rows of tables to capture all metadata fields (e.g. row 5 Semester/Term)
            for tr in tbl.findall(w("tr"))[:10]:
                for tc in tr.findall(w("tc")):
                    txt = get_full_text(tc).strip()
                    if txt:
                        doc_text += " " + txt

        doc_upper = doc_text.upper()

        # Semantic & Structural Markers
        is_syllabus = bool(
            "SYLLABUS" in doc_upper
            or "VPAA-QF-12" in doc_upper
            or "RECEIPT OF SYLLABUS" in doc_upper
            or "ACCEPTANCE OF SYLLABUS" in doc_upper
        )

        is_exam = bool(
            "RESULTS OF THE EXAMINATION" in doc_upper
            or "EXAMINATION RESULTS" in doc_upper
            or "EXAM RESULTS" in doc_upper
            or "RESULTS OF EXAMINATION" in doc_upper
            or "RETURN OF EXAMINATION" in doc_upper
            or ("EXAMINATION" in doc_upper and "RESULTS" in doc_upper)
        )

        is_tos = bool(
            "TABLE OF SPECIFICATIONS" in doc_upper
            or re.search(r"\bTOS\b", doc_upper)
        )

        is_discussion = bool(
            "GRADE DISCUSSION" in doc_upper
            or "DISCUSSION OF GRADES" in doc_upper
            or ("PRESENTED" in doc_upper and "DISCUSSED" in doc_upper and "GRADES" in doc_upper)
        )

        has_midterm = bool("MIDTERM" in doc_upper or "GITNANG PANAHON" in doc_upper)
        has_final = bool("FINAL" in doc_upper or "FINALS" in doc_upper or "HULING PANAHON" in doc_upper)

        # 1. Syllabus Acceptance
        if is_syllabus and not (is_exam or is_tos or is_discussion):
            evidence.append("Syllabus receipt/acceptance declarations identified in document text")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="confirmed",
                role=ROLE_SYLLABUS,
                candidate_roles=[ROLE_SYLLABUS],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="syllabus",
            )

        # 2. Exam Returns
        if is_exam and not (is_syllabus or is_tos or is_discussion):
            evidence.append("Examination results presentation declaration identified")
            if has_midterm and not has_final:
                evidence.append("Period term 'Midterm' verified in document body")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_EXAM_RETURNS_MIDTERM,
                    candidate_roles=[ROLE_EXAM_RETURNS_MIDTERM],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="exam_returns",
                )
            elif has_final and not has_midterm:
                evidence.append("Period term 'Final' verified in document body")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_EXAM_RETURNS_FINAL,
                    candidate_roles=[ROLE_EXAM_RETURNS_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="exam_returns",
                )
            else:
                evidence.append("Examination results form detected, but term (Midterm vs Final) requires user confirmation")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_EXAM_RETURNS_MIDTERM, ROLE_EXAM_RETURNS_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="exam_returns",
                )

        # 3. Table of Specifications
        if is_tos and not (is_syllabus or is_exam or is_discussion):
            evidence.append("Table of Specifications declaration identified in document body")
            fn_indicates_final = any("final" in h.lower() for h in diag_hints)
            fn_indicates_midterm = any("midterm" in h.lower() for h in diag_hints)

            if (fn_indicates_final and has_midterm and not has_final) or (fn_indicates_midterm and has_final and not has_midterm):
                evidence.append("Document body text indicates one term but file hint suggests another; flagged as ambiguous for user confirmation")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_TOS_MIDTERM, ROLE_TOS_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                )
            elif has_midterm and not has_final:
                evidence.append("Period term 'Midterm' verified in document body")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_TOS_MIDTERM,
                    candidate_roles=[ROLE_TOS_MIDTERM],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                )
            elif has_final and not has_midterm:
                evidence.append("Period term 'Final' verified in document body")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_TOS_FINAL,
                    candidate_roles=[ROLE_TOS_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                )
            else:
                evidence.append("Table of Specifications detected, but term (Midterm vs Final) requires user confirmation")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_TOS_MIDTERM, ROLE_TOS_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                )

        # 4. Grade Discussion
        if is_discussion and not (is_syllabus or is_exam or is_tos):
            evidence.append("Grade presentation and discussion declaration identified in document body")
            if has_midterm and not has_final:
                evidence.append("Period term 'Midterm' verified in document body")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_GRADE_DISCUSSION_MIDTERM,
                    candidate_roles=[ROLE_GRADE_DISCUSSION_MIDTERM],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="grade_discussion",
                )
            elif has_final and not has_midterm:
                evidence.append("Period term 'Final' verified in document body")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_GRADE_DISCUSSION_FINAL,
                    candidate_roles=[ROLE_GRADE_DISCUSSION_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="grade_discussion",
                )
            else:
                evidence.append("Grade discussion form detected, but term (Midterm vs Final) requires user confirmation")
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_GRADE_DISCUSSION_MIDTERM, ROLE_GRADE_DISCUSSION_FINAL],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="grade_discussion",
                )

        # 5. Overlapping or ambiguous declarations
        matched_categories = []
        if is_syllabus: matched_categories.append(ROLE_SYLLABUS)
        if is_exam: matched_categories.extend([ROLE_EXAM_RETURNS_MIDTERM, ROLE_EXAM_RETURNS_FINAL])
        if is_tos: matched_categories.extend([ROLE_TOS_MIDTERM, ROLE_TOS_FINAL])
        if is_discussion: matched_categories.extend([ROLE_GRADE_DISCUSSION_MIDTERM, ROLE_GRADE_DISCUSSION_FINAL])

        if len(matched_categories) > 1:
            evidence.append(f"Multiple document categories identified with overlapping markers: {matched_categories}")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=matched_categories,
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="academic_docx",
            )

        # 6. Fallback: Generic custom docx
        if docx_cand.header_candidates or docx_cand.roster_candidate:
            evidence.append("Valid DOCX header metadata and table structure discovered, but no specific CEIT category matched")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=list(CANONICAL_ROLES[:7]),
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="custom_docx",
            )

        return DetectionResult(
            file_path=file_path,
            file_name=file_name,
            file_type="docx",
            status="unsupported",
            structural_evidence=["No recognized academic, attendance, or roster table structure found"],
            diagnostic_hints=diag_hints,
            error="Document does not contain recognized institutional form structure",
        )

    def _detect_xlsx(self, file_path: str, file_name: str) -> DetectionResult:
        diag_hints = [f"File extension .xlsx; filename '{file_name}'"]
        fn_lower = file_name.lower()
        if "lab" in fn_lower and "lec" in fn_lower:
            diag_hints.append("Filename hint suggests: Lecture + Lab")
        elif "lec" in fn_lower:
            diag_hints.append("Filename hint suggests: Lecture")
        evidence: List[str] = []

        try:
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()
        except Exception as e:
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="unsupported",
                diagnostic_hints=diag_hints,
                error=f"Failed to read workbook: {e}",
            )

        sheet_map = {s.lower().strip(): s for s in sheet_names}
        evidence.append(f"Worksheets discovered: {sheet_names}")

        has_lec = "lecture" in sheet_map
        has_grading = "grading sheet" in sheet_map
        has_lab = "laboratory" in sheet_map or "lab" in sheet_map

        if not has_lec or not has_grading:
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="unsupported",
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                error="Grading spreadsheet must contain 'Lecture' and 'Grading Sheet' worksheets",
            )

        evidence.append(f"Required worksheets confirmed: '{sheet_map['lecture']}' and '{sheet_map['grading sheet']}'")

        # Discriminate based on actual presence of 'Laboratory' sheet
        if has_lab:
            evidence.append(f"Laboratory worksheet '{sheet_map.get('laboratory') or sheet_map.get('lab')}' confirms Lecture + Lab grading sheet structure")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="confirmed",
                role=ROLE_GRADE_SHEET_LECTURE_LAB,
                candidate_roles=[ROLE_GRADE_SHEET_LECTURE_LAB],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="grade_sheet_xlsx",
            )
        else:
            evidence.append("Absence of Laboratory worksheet confirms Lecture-only grading sheet structure")
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="confirmed",
                role=ROLE_GRADE_SHEET_LECTURE,
                candidate_roles=[ROLE_GRADE_SHEET_LECTURE],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="grade_sheet_xlsx",
            )

    def validate_role(
        self,
        file_path: str,
        role: str,
    ) -> Tuple[bool, Optional[str], Optional[Any]]:
        """
        Validates that a template file actually satisfies the declared canonical role
        using the authoritative physical RecipeValidator.
        Returns (is_valid, error_message, validated_recipe).
        """
        if role not in CANONICAL_ROLES:
            return False, f"Unknown canonical role '{role}'", None

        profile_id = ROLE_PROFILE_MAPPING[role]

        try:
            if profile_id == "attendance_docx":
                raw_cand = self._att_inspector.inspect(file_path, profile_id=profile_id)
                validated = self._validator.validate(raw_cand, profile=profile_id)
            elif profile_id == "grade_sheet_xlsx":
                raw_cand = self._xlsx_inspector.inspect(file_path, profile_id=profile_id)
                validated = self._validator.validate(raw_cand, profile=profile_id)
            else:
                raw_cand = self._docx_inspector.inspect(file_path, profile_id=profile_id)
                validated = self._validator.validate(raw_cand, profile=profile_id)

            return True, None, validated
        except (TemplateError, InvalidRecipeError, AmbiguousTemplateError) as e:
            return False, str(e), None
        except Exception as e:
            logger.error(f"Unexpected error validating role '{role}' for {file_path}: {e}")
            return False, f"Validation failure: {str(e)}", None
