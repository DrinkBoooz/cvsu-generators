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
    ROLE_FILE_TYPE_MAPPING,
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
class RoleCandidate:
    """
    Detailed structural evidence for a candidate role proposed by TemplateRoleDetector.

    CRITICAL SEMANTIC NOTICE:
    `confidence` is heuristic discovery metadata intended solely for UI ranking or diagnostic hints.
    It is NEVER treated as a statistically calibrated probability or used as validation authority.
    Final role acceptance is strictly governed by authoritative structural validation via
    RecipeValidator, independent of heuristic confidence scores.
    """
    role: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0
    structural_dominance: float = 1.0
    is_compatible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "structural_dominance": self.structural_dominance,
            "is_compatible": self.is_compatible,
        }


@dataclass
class DetectionResult:
    """Represents the outcome of physical template role analysis."""
    file_path: str
    file_name: str
    file_type: str
    status: str  # "confirmed" | "ambiguous" | "unsupported"
    role: Optional[str] = None
    candidate_roles: List[str] = field(default_factory=list)
    candidates: List[RoleCandidate] = field(default_factory=list)
    structural_evidence: List[str] = field(default_factory=list)
    diagnostic_hints: List[str] = field(default_factory=list)
    profile_id: Optional[str] = None
    family: Optional[str] = None
    variant: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "status": self.status,
            "role": self.role,
            "candidate_roles": list(self.candidate_roles),
            "candidates": [c.to_dict() for c in self.candidates],
            "structural_evidence": list(self.structural_evidence),
            "diagnostic_hints": list(self.diagnostic_hints),
            "profile_id": self.profile_id,
            "family": self.family,
            "variant": self.variant,
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
                and att_cand.matrix_candidate.get("template_session_capacity", 0) >= 1
                and not att_cand.collisions
            ):
                return self._classify_attendance(file_path, file_name, att_cand, diag_hints)
        except Exception as e:
            logger.debug(f"Attendance inspection probe skipped or failed for {file_name}: {e}")

        # 2. Probe for Academic CEIT Document structure
        try:
            docx_cand = self._docx_inspector.inspect(file_path, profile_id="academic_docx")
        except AmbiguousTemplateError as e:
            all_academic_roles = [
                ROLE_SYLLABUS,
                ROLE_EXAM_RETURNS_MIDTERM,
                ROLE_EXAM_RETURNS_FINAL,
                ROLE_TOS_MIDTERM,
                ROLE_TOS_FINAL,
                ROLE_GRADE_DISCUSSION_MIDTERM,
                ROLE_GRADE_DISCUSSION_FINAL,
            ]
            cands = [
                RoleCandidate(role=r, evidence=["Multiple candidate roster tables detected with equal prominence"], confidence=0.2, structural_dominance=0.2)
                for r in all_academic_roles
            ]
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=all_academic_roles,
                candidates=cands,
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
        summary_names = [str(n).lower() for n in matrix.get("summary_column_names", ())]

        evidence.append(f"Attendance info metadata table verified at table index {info_t_idx}")
        evidence.append(f"Attendance session matrix verified at table index {matrix_t_idx}")
        evidence.append(f"Template session capacity: {cap} columns (date start col {date_start})")

        # Scan text in the document body and tables to inspect schedule/matrix evidence
        zin, root, body = load_docx(file_path)
        zin.close()
        tbls = body.findall(w("tbl"))

        # Analyze week columns in Row 0 of matrix table
        num_weeks = 0
        if matrix_t_idx < len(tbls):
            m_rows = tbls[matrix_t_idx].findall(w("tr"))
            if m_rows:
                prev_week = None
                for tc in m_rows[0].findall(w("tc")):
                    txt = get_full_text(tc).strip().upper()
                    if "WEEK" in txt or "LINGGO" in txt or re.match(r"^W\d+$", txt):
                        tc_pr = tc.find(w("tcPr"))
                        has_gridspan = tc_pr is not None and tc_pr.find(w("gridSpan")) is not None
                        if txt != prev_week or has_gridspan:
                            num_weeks += 1
                        prev_week = txt
                    else:
                        prev_week = None

        sessions_per_week = (cap / float(num_weeks)) if num_weeks > 0 else None

        # Check info table for explicit lecture/lab scheduling and room assignments
        info_text = ""
        if info_t_idx is not None and info_t_idx < len(tbls):
            for tr in tbls[info_t_idx].findall(w("tr")):
                for tc in tr.findall(w("tc")):
                    info_text += " " + get_full_text(tc).strip().upper()
        has_lab_schedule = bool(
            ("LAB:" in info_text and "LEC:" in info_text)
            or ("LABORATORY" in info_text and "LECTURE" in info_text)
            or (" CCL " in info_text or "COMP LAB" in info_text)
        )

        # Check for physically paired session columns or multi-session week blocks
        has_paired_columns = False
        has_multi_session_weeks = False
        has_single_session_weeks = False
        if matrix_t_idx < len(tbls):
            m_rows = tbls[matrix_t_idx].findall(w("tr"))
            if len(m_rows) > 0:
                tc_r0 = m_rows[0].findall(w("tc"))
                week_cells = tc_r0[date_start:date_start + cap] if cap > 0 else tc_r0[date_start:]
                week_texts = []
                for tc in week_cells:
                    txt = get_full_text(tc).strip().upper()
                    if txt:
                        week_texts.append(txt)
                    tc_pr = tc.find(w("tcPr"))
                    if tc_pr is not None:
                        gs = tc_pr.find(w("gridSpan"))
                        if gs is not None:
                            try:
                                span_val = int(gs.attrib.get(w("val"), "1"))
                                if span_val >= 2 and ("WEEK" in txt or "LINGGO" in txt or re.match(r"^W\d+$", txt)):
                                    has_multi_session_weeks = True
                            except (ValueError, TypeError):
                                pass
                for i in range(len(week_texts) - 1):
                    if week_texts[i] == week_texts[i + 1]:
                        has_multi_session_weeks = True
                        break

            if len(m_rows) > 1:
                date_cells = [get_full_text(tc).strip() for tc in m_rows[1].findall(w("tc"))[date_start:date_start + cap]]
                duplicate_adjacent = sum(1 for i in range(len(date_cells) - 1) if date_cells[i] and date_cells[i] == date_cells[i + 1])
                if duplicate_adjacent >= 2:
                    has_paired_columns = True

            if num_weeks > 0 and cap <= num_weeks:
                has_multi_session_weeks = False

            if num_weeks > 0 and num_weeks == cap and not has_multi_session_weeks and not has_paired_columns:
                has_single_session_weeks = True

        sched_text = ""
        if info_t_idx is not None and info_t_idx < len(tbls):
            bindings = info.get("bindings", {})
            sched_target = bindings.get("class_schedule")
            if sched_target and len(sched_target) == 2:
                r_i, c_i = sched_target
                t_rows = tbls[info_t_idx].findall(w("tr"))
                if r_i < len(t_rows):
                    t_cells = t_rows[r_i].findall(w("tc"))
                    if c_i < len(t_cells):
                        sched_text = get_full_text(t_cells[c_i]).strip()

        sched_intervals = len(re.findall(r"\b\d{1,2}:\d{2}", sched_text))
        has_single_sched_interval = bool(sched_intervals == 2 and "," not in sched_text and ";" not in sched_text)

        has_single_summary_only = bool(
            any("lec" in n or "lc" in n or "theory" in n for n in summary_names)
            and not any("lab" in n or "lb" in n or "prac" in n for n in summary_names)
        )
        has_dual_tracking = bool(
            (any("lab" in n or "lb" in n or "prac" in n for n in summary_names) and any("lec" in n or "lc" in n or "theory" in n for n in summary_names))
        )

        if sessions_per_week is None:
            diag_hints.append(f"No explicit week column headers detected in matrix (capacity: {cap} sessions)")
            evidence.append("Session headers omit explicit week blocks; evaluating independent physical structure")
        else:
            diag_hints.append(f"Diagnostic session structure: {sessions_per_week:.1f} sessions/week across {num_weeks} weeks")

        # Multi-signal structural discrimination (strictly independent of numeric capacity/ratio thresholds):
        # 1. Dual instructional component structural indicators:
        has_dual_instructional_structure = bool(
            has_lab_schedule
            or has_paired_columns
            or has_multi_session_weeks
        )

        # 2. Single instructional component structural indicators:
        has_single_instructional_component = bool(
            not has_dual_instructional_structure
            and not (re.search(r"\bLAB\b", info_text) or "LABORATORY" in info_text or " CCL " in info_text or "COMP LAB" in info_text)
            and (
                has_single_summary_only
                or ("LEC:" in info_text or "LECTURE" in info_text or "THEORY" in info_text)
                or has_single_session_weeks
                or (not has_paired_columns and not has_multi_session_weeks and has_single_sched_interval)
            )
        )

        is_dual_component = has_dual_instructional_structure

        if is_dual_component:
            evidence.append(
                f"Dual instructional component verified: confirms Lecture + Lab attendance structure "
                f"(capacity: {cap} sessions)"
            )
            if has_lab_schedule:
                evidence.append("Dual instructional component (LEC/LAB) markers identified in schedule/room assignment")
            if has_dual_tracking:
                evidence.append("Summary columns track both lecture (LC) and laboratory (LB) absences")
            if has_paired_columns:
                evidence.append("Paired session columns indicate multi-session weekly instructional periods")
            if has_multi_session_weeks:
                evidence.append("Multi-column week blocks indicate multi-session weekly instructional periods")

            role_cand = RoleCandidate(
                role=ROLE_ATTENDANCE_LECTURE_LAB,
                evidence=list(evidence),
                confidence=1.0,
                structural_dominance=1.0,
            )
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="confirmed",
                role=ROLE_ATTENDANCE_LECTURE_LAB,
                candidate_roles=[ROLE_ATTENDANCE_LECTURE_LAB],
                candidates=[role_cand],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="attendance_docx",
                family="attendance",
                variant="lecture_lab",
            )
        elif has_single_instructional_component:
            evidence.append(
                f"Single instructional component verified without secondary laboratory tracking: "
                f"confirms Lecture attendance structure (capacity: {cap} sessions)"
            )
            if "LEC:" in info_text or "LECTURE" in info_text:
                evidence.append("Schedule and room assignments establish single lecture instructional component")
            if sessions_per_week is not None:
                evidence.append(f"Weekly session structure indicates {sessions_per_week:.1f} sessions/week across {num_weeks} weeks")

            role_cand = RoleCandidate(
                role=ROLE_ATTENDANCE_LECTURE,
                evidence=list(evidence),
                confidence=1.0,
                structural_dominance=1.0,
            )
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="confirmed",
                role=ROLE_ATTENDANCE_LECTURE,
                candidate_roles=[ROLE_ATTENDANCE_LECTURE],
                candidates=[role_cand],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="attendance_docx",
                family="attendance",
                variant="lecture",
            )
        else:
            evidence.append(
                f"Attendance template structure (capacity: {cap} sessions) lacks conclusive "
                f"instructional component distinction (Lecture vs Lecture+Lab); flagged for user confirmation"
            )
            cands = [
                RoleCandidate(role=ROLE_ATTENDANCE_LECTURE, evidence=list(evidence), confidence=0.5, structural_dominance=0.5),
                RoleCandidate(role=ROLE_ATTENDANCE_LECTURE_LAB, evidence=list(evidence), confidence=0.5, structural_dominance=0.5),
            ]
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=[ROLE_ATTENDANCE_LECTURE, ROLE_ATTENDANCE_LECTURE_LAB],
                candidates=cands,
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="attendance_docx",
                family="attendance",
                variant="ambiguous",
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

        # Check for TOS specification matrix or blueprint table structure
        has_tos_matrix = False
        for tbl in body.findall(w("tbl")):
            tbl_trs = tbl.findall(w("tr"))
            if len(tbl_trs) >= 2:
                header_texts = [get_full_text(tc).strip().upper() for tc in tbl_trs[0].findall(w("tc"))]
                combined_hdr = " ".join(header_texts)
                is_student_roster = any(n in combined_hdr for n in ("STUDENT", "NAME", "MATRICULATION", "PANGALAN", "ID NUMBER", "STUDENT NUMBER"))
                if not is_student_roster:
                    if any(k in combined_hdr for k in ("TOPIC", "COMPETENC", "COGNITIVE", "DOMAIN", "OBJECTIVE", "PLACEMENT", "ALLOCATION")) or ("ITEM" in combined_hdr and any(k in combined_hdr for k in ("DISTRIBUTION", "COUNT", "TOTAL", "LEVEL", "SPECIFICATION", "PLACEMENT"))):
                        has_tos_matrix = True
                        break

        # ── Step 1: Detect Document Family ────────────────────────────────
        is_syllabus = bool(
            "SYLLABUS" in doc_upper
            or "SILABUS" in doc_upper
            or "VPAA-QF-12" in doc_upper
            or "COURSE OUTLINE" in doc_upper
            or "COURSE SPECIFICATION" in doc_upper
            or "TEACHING PLAN" in doc_upper
            or "LEARNING PLAN" in doc_upper
            or "CURRICULUM GUIDE" in doc_upper
            or "ACCEPTANCE OF SYLLABUS" in doc_upper
            or "RECEIPT OF SYLLABUS" in doc_upper
            or "RECEIPT OF COURSE OUTLINE" in doc_upper
        )

        is_exam = bool(
            "RESULTS OF THE EXAMINATION" in doc_upper
            or "EXAMINATION RESULTS" in doc_upper
            or "EXAM RESULTS" in doc_upper
            or "RESULTS OF EXAMINATION" in doc_upper
            or "RETURN OF EXAMINATION" in doc_upper
            or "ASSESSMENT RESULTS" in doc_upper
            or "STUDENT EXAMINATION REPORT" in doc_upper
            or "EXAMINATION REPORT" in doc_upper
            or "TEST RESULTS" in doc_upper
            or "EVALUATION RESULTS" in doc_upper
            or "ASSESSMENT RECORD" in doc_upper
            or "STUDENT PERFORMANCE FORM" in doc_upper
            or "STUDENT PERFORMANCE" in doc_upper
            or ("PERFORMANCE" in doc_upper and "RECORD" in doc_upper)
            or ("ASSESSMENT" in doc_upper and "BLUEPRINT" not in doc_upper and any(k in doc_upper for k in ("RECORD", "REPORT", "FORM", "SUMMARY", "SCORE", "RESULTS", "EVALUATION")))
            or ("EXAMINATION" in doc_upper and any(k in doc_upper for k in ("RESULTS", "RETURN", "RECEIVE", "REVIEW", "BUNGA", "PAPER", "REPORT")))
            or ("EXAM" in doc_upper and any(k in doc_upper for k in ("RESULTS", "RETURN", "REVIEW", "PAPER", "REPORT")))
        )

        is_tos = bool(
            has_tos_matrix
            or "TABLE OF SPECIFICATIONS" in doc_upper
            or re.search(r"\bTOS\b", doc_upper)
            or "TALAHANAYAN NG ESPESIPIKASYON" in doc_upper
            or "ASSESSMENT BLUEPRINT" in doc_upper
            or "TEST BLUEPRINT" in doc_upper
            or ("SPECIFICATION" in doc_upper and any(k in doc_upper for k in ("TABLE", "ITEM", "COGNITIVE", "OBJECTIVE", "COMPETENC", "DISTRIBUTION", "BLUEPRINT")))
            or ("COMPETENC" in doc_upper and "ITEM" in doc_upper and "COGNITIVE" in doc_upper)
            or ("COGNITIVE LEVEL" in doc_upper or "ITEM DISTRIBUTION" in doc_upper)
            or (any(k in doc_upper for k in ("TOPIC", "COMPETENC", "SKILL")) and any(k in doc_upper for k in ("COGNITIVE", "ITEM DISTRIBUTION", "ITEM COUNT", "ALLOCATION", "BLUEPRINT", "SPECIFICATION")))
        )

        is_discussion = bool(
            "GRADE DISCUSSION" in doc_upper
            or "DISCUSSION OF GRADES" in doc_upper
            or "GRADE CONSULTATION" in doc_upper
            or "GRADE PRESENTATION" in doc_upper
            or "ACKNOWLEDGEMENT OF GRADES" in doc_upper
            or "CONSULTATION OF MARKS" in doc_upper
            or "REVIEW OF GRADES" in doc_upper
            or "PAGTALAKAY NG MARKA" in doc_upper
            or ("PRESENTED" in doc_upper and "DISCUSSED" in doc_upper and ("GRADE" in doc_upper or "MARKA" in doc_upper))
            or (any(g in doc_upper for g in ("GRADE", "MARK", "RATING", "SCORE")) and any(k in doc_upper for k in ("DISCUSS", "CONSULT", "ACKNOWLEDG", "PRESENT", "CONFERENCE", "REVIEW", "FEEDBACK")))
        )

        # ── Step 2: Detect Period Variant ─────────────────────────────────
        has_midterm = bool("MIDTERM" in doc_upper or "GITNANG PANAHON" in doc_upper or "PRELIM" in doc_upper or "FIRST TERM" in doc_upper)
        has_final = bool("FINAL" in doc_upper or "FINALS" in doc_upper or "HULING PANAHON" in doc_upper or "END TERM" in doc_upper or "LAST TERM" in doc_upper)

        # 1. Syllabus Acceptance (Single variant)
        if is_syllabus and not (is_exam or is_tos or is_discussion):
            evidence.append("Syllabus / course outline declarations identified in document text")
            role_cand = RoleCandidate(role=ROLE_SYLLABUS, evidence=list(evidence), confidence=1.0)
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="confirmed",
                role=ROLE_SYLLABUS,
                candidate_roles=[ROLE_SYLLABUS],
                candidates=[role_cand],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="syllabus",
                family="syllabus",
                variant=None,
            )

        # 2. Exam Returns
        if is_exam and not (is_syllabus or is_tos or is_discussion):
            evidence.append("Examination results presentation declaration identified in document body")
            if has_midterm and not has_final:
                evidence.append("Period term 'Midterm' verified in document body")
                role_cand = RoleCandidate(role=ROLE_EXAM_RETURNS_MIDTERM, evidence=list(evidence), confidence=1.0)
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_EXAM_RETURNS_MIDTERM,
                    candidate_roles=[ROLE_EXAM_RETURNS_MIDTERM],
                    candidates=[role_cand],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="exam_returns",
                    family="exam_returns",
                    variant="midterm",
                )
            elif has_final and not has_midterm:
                evidence.append("Period term 'Final' verified in document body")
                role_cand = RoleCandidate(role=ROLE_EXAM_RETURNS_FINAL, evidence=list(evidence), confidence=1.0)
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_EXAM_RETURNS_FINAL,
                    candidate_roles=[ROLE_EXAM_RETURNS_FINAL],
                    candidates=[role_cand],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="exam_returns",
                    family="exam_returns",
                    variant="final",
                )
            else:
                evidence.append("Examination results form detected, but term (Midterm vs Final) requires user confirmation")
                cands = [
                    RoleCandidate(role=ROLE_EXAM_RETURNS_MIDTERM, evidence=list(evidence), confidence=0.5),
                    RoleCandidate(role=ROLE_EXAM_RETURNS_FINAL, evidence=list(evidence), confidence=0.5),
                ]
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_EXAM_RETURNS_MIDTERM, ROLE_EXAM_RETURNS_FINAL],
                    candidates=cands,
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="exam_returns",
                    family="exam_returns",
                )

        # 3. Table of Specifications
        if is_tos and not (is_syllabus or is_exam or is_discussion):
            evidence.append("Table of Specifications declaration identified in document body")
            if has_midterm and not has_final:
                evidence.append("Period term 'Midterm' verified in document body")
                role_cand = RoleCandidate(role=ROLE_TOS_MIDTERM, evidence=list(evidence), confidence=1.0)
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_TOS_MIDTERM,
                    candidate_roles=[ROLE_TOS_MIDTERM],
                    candidates=[role_cand],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                    family="tos",
                    variant="midterm",
                )
            elif has_final and not has_midterm:
                evidence.append("Period term 'Final' verified in document body")
                role_cand = RoleCandidate(role=ROLE_TOS_FINAL, evidence=list(evidence), confidence=1.0)
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_TOS_FINAL,
                    candidate_roles=[ROLE_TOS_FINAL],
                    candidates=[role_cand],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                    family="tos",
                    variant="final",
                )
            else:
                evidence.append("Table of Specifications detected, but term (Midterm vs Final) requires user confirmation")
                cands = [
                    RoleCandidate(role=ROLE_TOS_MIDTERM, evidence=list(evidence), confidence=0.5),
                    RoleCandidate(role=ROLE_TOS_FINAL, evidence=list(evidence), confidence=0.5),
                ]
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_TOS_MIDTERM, ROLE_TOS_FINAL],
                    candidates=cands,
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="tos",
                    family="tos",
                )

        # 4. Grade Discussion
        if is_discussion and not (is_syllabus or is_exam or is_tos):
            evidence.append("Grade presentation and discussion declaration identified in document body")
            if has_midterm and not has_final:
                evidence.append("Period term 'Midterm' verified in document body")
                role_cand = RoleCandidate(role=ROLE_GRADE_DISCUSSION_MIDTERM, evidence=list(evidence), confidence=1.0)
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_GRADE_DISCUSSION_MIDTERM,
                    candidate_roles=[ROLE_GRADE_DISCUSSION_MIDTERM],
                    candidates=[role_cand],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="grade_discussion",
                    family="grade_discussion",
                    variant="midterm",
                )
            elif has_final and not has_midterm:
                evidence.append("Period term 'Final' verified in document body")
                role_cand = RoleCandidate(role=ROLE_GRADE_DISCUSSION_FINAL, evidence=list(evidence), confidence=1.0)
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="confirmed",
                    role=ROLE_GRADE_DISCUSSION_FINAL,
                    candidate_roles=[ROLE_GRADE_DISCUSSION_FINAL],
                    candidates=[role_cand],
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="grade_discussion",
                    family="grade_discussion",
                    variant="final",
                )
            else:
                evidence.append("Grade discussion form detected, but term (Midterm vs Final) requires user confirmation")
                cands = [
                    RoleCandidate(role=ROLE_GRADE_DISCUSSION_MIDTERM, evidence=list(evidence), confidence=0.5),
                    RoleCandidate(role=ROLE_GRADE_DISCUSSION_FINAL, evidence=list(evidence), confidence=0.5),
                ]
                return DetectionResult(
                    file_path=file_path,
                    file_name=file_name,
                    file_type="docx",
                    status="ambiguous",
                    candidate_roles=[ROLE_GRADE_DISCUSSION_MIDTERM, ROLE_GRADE_DISCUSSION_FINAL],
                    candidates=cands,
                    structural_evidence=evidence,
                    diagnostic_hints=diag_hints,
                    profile_id="grade_discussion",
                    family="grade_discussion",
                )

        # 5. Overlapping or ambiguous declarations
        matched_categories = []
        if is_syllabus: matched_categories.append(ROLE_SYLLABUS)
        if is_exam: matched_categories.extend([ROLE_EXAM_RETURNS_MIDTERM, ROLE_EXAM_RETURNS_FINAL])
        if is_tos: matched_categories.extend([ROLE_TOS_MIDTERM, ROLE_TOS_FINAL])
        if is_discussion: matched_categories.extend([ROLE_GRADE_DISCUSSION_MIDTERM, ROLE_GRADE_DISCUSSION_FINAL])

        if len(matched_categories) > 1:
            evidence.append(f"Multiple document categories identified with overlapping markers: {matched_categories}")
            cands = [RoleCandidate(role=r, evidence=list(evidence), confidence=1.0/len(matched_categories)) for r in matched_categories]
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=matched_categories,
                candidates=cands,
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="academic_docx",
            )

        # 6. Fallback: Generic custom docx
        if docx_cand.header_candidates or docx_cand.roster_candidate:
            evidence.append("Valid DOCX header metadata and table structure discovered, but no specific CEIT category matched")
            canonical_7 = list(CANONICAL_ROLES[:7])
            cands = [RoleCandidate(role=r, evidence=list(evidence), confidence=0.1) for r in canonical_7]
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="docx",
                status="ambiguous",
                candidate_roles=canonical_7,
                candidates=cands,
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
            cand = self._xlsx_inspector.inspect(file_path, profile_id="grade_sheet_xlsx")
        except AmbiguousTemplateError as e:
            err_str = str(e)
            is_secondary = "secondary assessment" in err_str.lower()
            if is_secondary:
                cand_roles = [ROLE_GRADE_SHEET_LECTURE_LAB]
                cands = [
                    RoleCandidate(
                        role=ROLE_GRADE_SHEET_LECTURE_LAB,
                        evidence=[
                            "Multiple candidate secondary assessment worksheets detected",
                            err_str,
                        ],
                        confidence=0.5,
                        structural_dominance=0.5,
                    )
                ]
                diag = list(diag_hints) + ["Secondary assessment sheets remain structurally unresolved"]
            else:
                cand_roles = [
                    ROLE_GRADE_SHEET_LECTURE,
                    ROLE_GRADE_SHEET_LECTURE_LAB,
                ]
                cands = [
                    RoleCandidate(
                        role=r,
                        evidence=[err_str],
                        confidence=0.5,
                        structural_dominance=0.5,
                    )
                    for r in cand_roles
                ]
                diag = diag_hints

            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="ambiguous",
                role=None,
                candidate_roles=cand_roles,
                candidates=cands,
                structural_evidence=[err_str],
                diagnostic_hints=diag,
                error=err_str,
            )
        except TemplateError as e:
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="unsupported",
                structural_evidence=[str(e)],
                diagnostic_hints=diag_hints,
                error=str(e),
            )
        except Exception as e:
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="unsupported",
                structural_evidence=[f"Failed to inspect XLSX workbook: {e}"],
                diagnostic_hints=diag_hints,
                error=f"Failed to inspect XLSX workbook: {e}",
            )

        meta = cand.metadata
        sheet_names = meta.get("sheet_names", [])
        roster_sheet = meta.get("roster_sheet")
        summary_sheet = meta.get("summary_sheet")
        has_lab = meta.get("has_lab", False)
        capacity = cand.roster_candidate.get("capacity_limit", 0) if cand.roster_candidate else 0

        evidence.append(f"Worksheets discovered: {sheet_names}")
        evidence.append(f"Primary student roster and assessment sheet verified: '{roster_sheet}' (capacity: {capacity} students)")
        evidence.append(f"Summary rating sheet verified: '{summary_sheet}'")

        if has_lab:
            evidence.append("Laboratory component verified; confirms Lecture + Lab grading sheet structure")
            role_cand = RoleCandidate(
                role=ROLE_GRADE_SHEET_LECTURE_LAB,
                evidence=list(evidence),
                confidence=1.0,
                structural_dominance=1.0,
            )
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="confirmed",
                role=ROLE_GRADE_SHEET_LECTURE_LAB,
                candidate_roles=[ROLE_GRADE_SHEET_LECTURE_LAB],
                candidates=[role_cand],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="grade_sheet_xlsx",
                family="grade_sheet",
                variant="lecture_lab",
            )
        else:
            evidence.append("Single instructional component verified with no secondary laboratory sheet")
            role_cand = RoleCandidate(
                role=ROLE_GRADE_SHEET_LECTURE,
                evidence=list(evidence),
                confidence=1.0,
                structural_dominance=1.0,
            )
            return DetectionResult(
                file_path=file_path,
                file_name=file_name,
                file_type="xlsx",
                status="confirmed",
                role=ROLE_GRADE_SHEET_LECTURE,
                candidate_roles=[ROLE_GRADE_SHEET_LECTURE],
                candidates=[role_cand],
                structural_evidence=evidence,
                diagnostic_hints=diag_hints,
                profile_id="grade_sheet_xlsx",
                family="grade_sheet",
                variant="lecture",
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
        expected_type = ROLE_FILE_TYPE_MAPPING[role]
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        if ext != expected_type:
            return False, f"Invalid file format '{ext}' for role '{role}' (expected '{expected_type}')", None

        try:
            if profile_id == "attendance_docx":
                raw_cand = self._att_inspector.inspect(file_path, profile_id=profile_id)

                # Variant compatibility check: Lecture+Lab requires multi-session or lab component structure
                if role == ROLE_ATTENDANCE_LECTURE_LAB:
                    mat = raw_cand.matrix_candidate
                    inf = raw_cand.info_candidate
                    summary_names = [str(n).lower() for n in mat.get("summary_column_names", [])] if mat else []
                    has_single_summary_only = bool(
                        any("lec" in n or "lc" in n or "theory" in n for n in summary_names)
                        and not any("lab" in n or "lb" in n or "prac" in n for n in summary_names)
                    )

                    zin, root, body = load_docx(file_path)
                    zin.close()
                    tbls = body.findall(w("tbl"))

                    info_t_idx = inf.get("table_index") if inf else None
                    info_text = ""
                    if info_t_idx is not None and info_t_idx < len(tbls):
                        for tr in tbls[info_t_idx].findall(w("tr")):
                            for tc in tr.findall(w("tc")):
                                info_text += " " + get_full_text(tc).strip().upper()

                    has_lab_schedule = bool(
                        ("LAB:" in info_text and "LEC:" in info_text)
                        or ("LABORATORY" in info_text and "LECTURE" in info_text)
                        or (" CCL " in info_text or "COMP LAB" in info_text)
                        or ("LAB" in info_text and ("LEC" in info_text or "THEORY" in info_text))
                    )

                    mat_t_idx = mat.get("table_index") if mat else None
                    cap = mat.get("template_session_capacity", 0) if mat else 0
                    date_start = mat.get("date_columns_start", 0) if mat else 0

                    has_paired_columns = False
                    has_multi_session_weeks = False
                    num_weeks = 0
                    if mat_t_idx is not None and mat_t_idx < len(tbls):
                        m_rows = tbls[mat_t_idx].findall(w("tr"))
                        if len(m_rows) > 0:
                            prev_w = None
                            for tc in m_rows[0].findall(w("tc")):
                                txt = get_full_text(tc).strip().upper()
                                if "WEEK" in txt or "LINGGO" in txt or re.match(r"^W\d+$", txt):
                                    tc_pr = tc.find(w("tcPr"))
                                    has_gridspan = tc_pr is not None and tc_pr.find(w("gridSpan")) is not None
                                    if txt != prev_w or has_gridspan:
                                        num_weeks += 1
                                    prev_w = txt
                                else:
                                    prev_w = None

                            tc_r0 = m_rows[0].findall(w("tc"))
                            week_cells = tc_r0[date_start:date_start + cap] if cap > 0 else tc_r0[date_start:]
                            week_texts = []
                            for tc in week_cells:
                                txt = get_full_text(tc).strip().upper()
                                if txt:
                                    week_texts.append(txt)
                                tc_pr = tc.find(w("tcPr"))
                                if tc_pr is not None:
                                    gs = tc_pr.find(w("gridSpan"))
                                    if gs is not None:
                                        try:
                                            span_val = int(gs.attrib.get(w("val"), "1"))
                                            if span_val >= 2 and ("WEEK" in txt or "LINGGO" in txt or re.match(r"^W\d+$", txt)):
                                                has_multi_session_weeks = True
                                        except (ValueError, TypeError):
                                            pass
                            for i in range(len(week_texts) - 1):
                                if week_texts[i] == week_texts[i + 1]:
                                    has_multi_session_weeks = True
                                    break

                        if len(m_rows) > 1:
                            date_cells = [get_full_text(tc).strip() for tc in m_rows[1].findall(w("tc"))[date_start:date_start + cap]]
                            duplicate_adjacent = sum(1 for i in range(len(date_cells) - 1) if date_cells[i] and date_cells[i] == date_cells[i + 1])
                            if duplicate_adjacent >= 2:
                                has_paired_columns = True

                    if num_weeks > 0 and cap <= num_weeks:
                        has_multi_session_weeks = False

                    has_single_session_weeks = bool(num_weeks > 0 and num_weeks == cap and not has_multi_session_weeks and not has_paired_columns)

                    is_demonstrably_single = bool(
                        has_single_summary_only
                        or (
                            has_single_session_weeks
                            and not has_lab_schedule
                            and not has_paired_columns
                            and not has_multi_session_weeks
                            and not (re.search(r"\bLAB\b", info_text) or "LABORATORY" in info_text or " CCL " in info_text or "COMP LAB" in info_text)
                        )
                    )
                    if is_demonstrably_single:
                        return False, f"Template defines a single instructional component and lacks required secondary laboratory or multi-session instructional structure for role '{role}'", None

                validated = self._validator.validate(raw_cand, profile=profile_id)
            elif profile_id == "grade_sheet_xlsx":
                raw_cand = self._xlsx_inspector.inspect(file_path, profile_id=profile_id)
                has_lab = raw_cand.metadata.get("has_lab", False)

                # Variant compatibility check: Lecture+Lab requires secondary practical/lab component
                if role == ROLE_GRADE_SHEET_LECTURE_LAB and not has_lab:
                    return False, f"Template lacks required secondary laboratory/practical component for role '{role}'", None

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
