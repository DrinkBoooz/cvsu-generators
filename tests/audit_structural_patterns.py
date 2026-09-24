#!/usr/bin/env python3
"""
scratch/audit_structural_patterns.py

Automated repository audit script that inspects modules/ for remaining role-detection
assumptions and structural patterns:

A. Forbidden table-index authority:
   tables[0], tables[1], tbls[0], tbls[1] used as fixed role authority.
B. Capacity/session thresholds:
   cap >= ..., cap <= ..., cap < ..., cap > ...,
   sessions_per_week >= ..., sessions_per_week <= ...,
   spw >= ..., spw <= ..., capacity-derived role branching.
C. Fixed geometry role assumptions:
   total_cols == ..., total_rows == ..., fixed worksheet index assumptions.
D. Worksheet-name authority:
   Worksheet names affecting role correctness rather than diagnostics or non-authoritative tie-breakers.
E. Filename authority:
   Filename substrings affecting role correctness.
F. Semantic vocabulary gates in validation:
   Semantic vocabulary checks inside validate_role() or RecipeValidator.

Classifies each finding as:
  A. Physical structural evidence
  B. Semantic candidate evidence
  C. Diagnostic-only hint
  D. Legitimate business logic / template fallback
  E. Prohibited authoritative assumption (MUST BE ZERO)
"""

import os
import re
import sys
from typing import List, Dict, Tuple, Any, Optional

MODULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modules"))

AUDIT_RULES: List[Tuple[str, str, str]] = [
    # Pattern, Rule ID, Description
    (r"tbls\[0\]|tables\[0\]", "table-0-lookup", "Fixed table index 0 lookup"),
    (r"tbls\[1\]|tables\[1\]", "table-1-lookup", "Fixed table index 1 lookup"),
    (r"\"Lecture\"", "literal-Lecture-name", "Literal 'Lecture' worksheet token"),
    (r"\"Laboratory\"", "literal-Laboratory-name", "Literal 'Laboratory' worksheet token"),
    (r"\"Grading Sheet\"", "literal-Grading-Sheet-name", "Literal 'Grading Sheet' worksheet token"),
    (r"\"SYLLABUS\"", "literal-SYLLABUS-token", "Literal 'SYLLABUS' semantic token"),
    (r"\"EXAMINATION RESULTS\"", "literal-EXAM-RESULTS-token", "Literal 'EXAMINATION RESULTS' semantic token"),
    (r"\"TABLE OF SPECIFICATIONS\"", "literal-TOS-token", "Literal 'TABLE OF SPECIFICATIONS' semantic token"),
    (r"\"GRADE DISCUSSION\"", "literal-GRADE-DISCUSSION-token", "Literal 'GRADE DISCUSSION' semantic token"),
    (r"cap\s*/\s*4(\.0)?", "constant-4-week-assumption", "Constant 4-week assumption (/ 4)"),
    (r"fn_indicates", "filename-role-classification", "Filename substring role classification"),
    (r"(?:cap|capacity|sessions_per_week|spw)\s*(?:>=|<=|>|<|==)\s*\d+(?:\.\d+)?", "capacity-session-threshold", "Numeric capacity or sessions-per-week threshold"),
    (r"total_cols\s*==\s*\d+", "total-cols-equality", "Fixed total_cols equality assumption"),
    (r"total_rows\s*==\s*\d+", "total-rows-equality", "Fixed total_rows equality assumption"),
    (r"sheetnames\[0\]|worksheets\[0\]", "worksheet-0-lookup", "Fixed worksheet index 0 lookup"),
    (r"(?:ws_name|sheet_name|s_name)\s*==\s*[\"']", "worksheet-name-equality", "Worksheet name equality check"),
    (r"(?:scored_rosters|scored_summaries|sorted_remaining)\[0\]", "workbook-order-role-selection", "First candidate in sorted or workbook order selected without ambiguity check"),
    (r"sorted\([^)]*roster[^)]*\)\[0\]|sorted\([^)]*summar[^)]*\)\[0\]", "first-candidate-wins", "First candidate selected from sorted candidates without ambiguity check"),
    (r"sorted\([^)]*(?:max_column|max_row)[^)]*\)\[0\]", "dimension-sorted-role-selection", "Prohibited dimension-sorted candidate selection without unique structural lineage"),
    (r"cols1\s*(?:>|<|!=|==)\s*cols2|max_column\s*(?:>|<|!=|==)\s*max_column", "dimension-role-authority", "Prohibited dimension comparison used as authoritative role discriminator"),
    (r"refs1\s*(?:>|<|!=|==)\s*refs2|refs2\s*(?:>|<|!=|==)\s*refs1|(?:ref_count|formula_count)\s*(?:>|<|!=)", "reference-count-role-authority", "Reference or formula count comparison used as authoritative role discriminator"),
    (r"(?:s1_refs_primary|s2_refs_primary)\b", "primary-roster-role-authority", "Hardcoded primary-roster dependency used as mandatory role authority"),
    (r"if\s+s1_refs_s2\s*:\s*(?:con_sheet|lab_sheet|has_consolidated|return)", "direct-dependency-role-authority", "Direct dependency direction alone used as role authority without aggregation check"),
    (r"if\s+(?:is_aggregation_formula|is_consolidation_formula)\([^)]*\)\s*:\s*(?:con_sheet|lab_sheet|role)", "aggregation-formula-role-authority", "Single formula consolidation/aggregation predicate used as direct role authority"),
    (r"non_summary_sheets\s*=", "non-summary-sheet-broad-set", "Overly broad non-summary sheet set without roster verification"),
    (r"if\s+has_operators\s*:\s*return\s+True", "single-source-operator-consolidation", "Single-source operator treated as multi-source consolidation"),
    (r"student_component_sheets\s*=\s*(?:set\([^)]*roster_candidates_by_sheet|\{\s*s\s*for\s*s\s*in\s*roster_candidates_by_sheet)", "summary-in-component-sheets", "Direct treatment of roster candidates as semantic component authority without bounding to verified candidate components"),
    (r"student_component_sheets\s*=\s*(?:set\()?(?:sheet_names|wb\.sheetnames|all_sheets)\)?", "broad-workbook-sheets-as-components", "Broad workbook sheet set treated as student components"),
    (r"for\s+row\s+in\s+ws\.iter_rows\(values_only=True\):", "whole-sheet-consolidation-scan", "Whole-sheet row iteration used for consolidation authority without student data region bounding"),
    (r"(?:first_row\s*\+\s*10|max_column\s*\+\s*1,\s*50)", "arbitrary-sampling-bounds", "Arbitrary row or column sampling boundary used as authoritative role evidence"),
    (r"def\s+(?:is_aggregation_formula|has_aggregation_structure)\([^)]*all_sheets", "all-sheets-compatibility-alias", "Compatibility alias reinterpreting all_sheets as student components"),
    (r"lab_sheet\s*=\s*remaining_assessment_sheets\[0\]", "unverified-candidate-promotion", "Promoting candidate roster sheet to lab_sheet without lineage/role verification"),
]


def classify_finding(rel_path: str, line_num: int, label: str, snippet: str) -> Tuple[str, str]:
    """
    Classifies a raw finding into Category A, B, C, D, or E.
    Returns (Category, Justification).
    """
    # Category E: Unverified promotion of candidate sheet to authoritative role
    if label == "unverified-candidate-promotion":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited unverified promotion of candidate sheet to authoritative role"
        return "D", "Legitimate candidate check"

    # Category E: Single formula aggregation predicate used as direct role authority
    if label == "aggregation-formula-role-authority":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited single formula aggregation predicate used as direct role authority"
        return "D", "Legitimate formula check"

    # Category E: Overly broad non-summary sheet set without roster verification
    if label == "non-summary-sheet-broad-set":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited overly broad non-summary sheet set without roster verification"
        return "D", "Legitimate sheet filtering"

    # Category E: Single-source operator treated as multi-source consolidation
    if label == "single-source-operator-consolidation":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited single-source operator treated as multi-source consolidation"
        return "D", "Legitimate operator logic"

    # Category E: Direct treatment of roster candidates as semantic component authority
    if label == "summary-in-component-sheets":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited direct treatment of roster candidates as semantic component authority"
        return "D", "Legitimate sheet grouping"

    # Category E: Broad workbook sheet sets treated as student components
    if label == "broad-workbook-sheets-as-components":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited broad workbook sheet sets treated as student components"
        return "D", "Legitimate sheet grouping"

    # Category E: Whole-sheet row iteration used for consolidation authority
    if label == "whole-sheet-consolidation-scan":
        if "template_inspector.py" in rel_path:
            return "E", "Prohibited whole-sheet row iteration used for consolidation authority without student data region bounding"
        return "D", "Legitimate row iteration"

    # Category E: Arbitrary row or column sampling boundary used as authoritative role evidence
    if label == "arbitrary-sampling-bounds":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited arbitrary row or column sampling boundary used as authoritative role evidence"
        return "D", "Legitimate sampling"

    # Category E: Compatibility alias reinterpreting all_sheets as student components
    if label == "all-sheets-compatibility-alias":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited compatibility alias reinterpreting all_sheets as student components"
        return "D", "Legitimate function signature"

    # Category E: Dimension-based role authority for secondary assessment sheets
    if label == "dimension-sorted-role-selection":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited dimension-sorted candidate selection without unique structural lineage"
        return "D", "Legitimate geometry calculation"

    if label == "dimension-role-authority":
        if "cols1 == cols2" in snippet and "rows1 == rows2" in snippet:
            return "A", "Physical symmetry check for ambiguous candidate rejection"
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited dimension comparison used as authoritative role discriminator"
        return "D", "Legitimate geometry calculation"

    # Category E: Reference-count role authority for secondary assessment sheets
    if label == "reference-count-role-authority":
        if "refs1 == refs2" in snippet and "cols1 == cols2" in snippet:
            return "A", "Physical symmetry check for ambiguous candidate rejection"
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited reference count comparison used as authoritative role discriminator"
        return "D", "Legitimate reference counting"

    # Category E: Hardcoded primary-roster dependency used as mandatory role authority
    if label == "primary-roster-role-authority":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited hardcoded primary-roster dependency used as mandatory secondary role authority"
        return "D", "Legitimate reference check"

    # Category E: Direct dependency direction alone used as role authority
    if label == "direct-dependency-role-authority":
        if "template_inspector.py" in rel_path or "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited direct dependency direction alone used as role authority without physical aggregation check"
        return "D", "Legitimate dependency resolution"

    # Category E: Workbook-order role selection or first-candidate-wins without ambiguity check
    if label in ("workbook-order-role-selection", "first-candidate-wins"):
        if "template_role_detector.py" in rel_path or "template_inspector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited workbook-order role selection or first-candidate-wins behavior without ambiguity check"
        return "D", "Legitimate sorting"

    # Category E: Constant-4-week assumption
    if label == "constant-4-week-assumption":
        return "E", "Prohibited synthetic four-week assumption"

    # Category E: Filename substring role authority
    if label == "filename-role-classification":
        return "E", "Prohibited filename substring authoritative role classification"

    # Category E: Fixed worksheet index 0 used as role authority
    if label == "worksheet-0-lookup":
        if "template_role_detector.py" in rel_path or "detector" in rel_path:
            return "E", "Prohibited fixed worksheet index 0 used as role authority"
        return "D", "Sequential workbook processing or default sheet selection"

    # Category E: Worksheet name equality used as role authority
    if label == "worksheet-name-equality":
        if "template_role_detector.py" in rel_path or "detector" in rel_path or "validator" in rel_path:
            if any(term in snippet for term in ("role", "ROLE_", "variant", "return")):
                return "E", "Prohibited worksheet name equality used as role authority"
        return "D", "Internal dictionary or config mapping"

    # Category B: Numeric capacity / sessions-per-week thresholds
    if label == "capacity-session-threshold":
        if "recipe_validator.py" in rel_path:
            if "capacity_limit <= 0" in snippet or "session_capacity <= 0" in snippet or "min_val" in snippet:
                return "D", "Physical geometry non-negativity validation"
            return "D", "Physical validation of capacity bounds"
        elif "template_role_detector.py" in rel_path or "detector" in rel_path or "bad_validator" in rel_path:
            if any(term in snippet for term in ("role ==", "ROLE_", "is_dual", "is_single", "return False", "return DetectionResult", "cap >=", "cap <=", "spw >=", "spw <=", "sessions_per_week >=", "sessions_per_week <=")):
                if "cap <= num_weeks" not in snippet:
                    return "E", "Prohibited authoritative capacity or sessions-per-week threshold in role detector"
            if "sessions_per_week" in snippet and ("min(" in snippet or "round(" in snippet):
                return "C", "Diagnostic calculation for sessions-per-week telemetry"
            elif "cap > 0" in snippet or "cap < len(" in snippet or "cap ==" in snippet or "cap <= num_weeks" in snippet:
                return "A", "Physical bounds check on discovered capacity"
            else:
                return "C", "Diagnostic capacity telemetry"
        elif "template_inspector.py" in rel_path:
            if "capacity_limit" in snippet or "cap <" in snippet or "capacity >" in snippet:
                return "A", "Physical inspection bounds check on session/roster capacity"
            return "C", "Diagnostic capacity telemetry"
        else:
            return "D", "Legitimate business logic / scaling check"

    # Category C: Fixed geometry total_cols / total_rows equality
    if label in ("total-cols-equality", "total-rows-equality"):
        if ("template_role_detector.py" in rel_path or "academic" in rel_path or "detector" in rel_path) and ("is_syllabus" in snippet or "role" in snippet or "ROLE_" in snippet or "total_cols == 4" in snippet):
            return "E", "Prohibited fixed total_cols equality used as role authority"
        elif "template_inspector.py" in rel_path:
            return "A", "Physical table column/row inspection"
        else:
            return "D", "Legitimate geometry check"

    # Category D: Worksheet name authority
    if label in ("literal-Lecture-name", "literal-Laboratory-name", "literal-Grading-Sheet-name"):
        if ("template_role_detector.py" in rel_path or "detector" in rel_path) and any(term in snippet for term in ("role =", "return ROLE_", "candidate =")):
            return "E", "Prohibited worksheet name token used as role authority in detector"
        elif "TEMPLATE_FILES" in snippet or "defaults" in snippet.lower():
            return "D", "Legitimate business default / bundled template mapping"
        elif "sheet_map" in snippet or "in sheet_names" in snippet:
            return "B", "Non-authoritative backwards-compatible semantic hint"
        elif "wb[" in snippet or "ws[" in snippet:
            return "D", "Workbook target cell population"
        else:
            return "C", "Diagnostic hint or error message"

    # Category B: Semantic tokens in document text
    if label in ("literal-SYLLABUS-token", "literal-EXAM-RESULTS-token", "literal-TOS-token", "literal-GRADE-DISCUSSION-token"):
        if "validate_role" in snippet:
            return "E", "Prohibited semantic vocabulary gate in authoritative validation"
        if "doc_upper" in snippet or "doc_text" in snippet:
            return "B", "Semantic candidate evidence in document text"
        else:
            return "C", "Diagnostic reference"

    # Category A: Table index 0 or 1 lookup
    if label in ("table-0-lookup", "table-1-lookup"):
        if "template_role_detector.py" in rel_path:
            if "tbls[0]" in snippet or "tables[0]" in snippet:
                if "info_t_idx" not in snippet and "m_tbl_idx" not in snippet and "len(" not in snippet:
                    return "E", "Prohibited fixed table 0 lookup as role authority"
            if "tbls[1]" in snippet or "tables[1]" in snippet:
                if "info_t_idx" not in snippet and "m_tbl_idx" not in snippet and "len(" not in snippet:
                    return "E", "Prohibited fixed table 1 lookup as role authority"
            return "A", "Physical structural table verification"
        elif "template_inspector.py" in rel_path:
            return "A", "Structural table inspection"
        elif "ceit_gen.py" in rel_path or "document_generator.py" in rel_path:
            return "D", "Target coordinate resolution in generator"
        else:
            return "A", "Structural table inspection"

    return "D", "Legitimate business logic"


def scan_source(source_code: str, file_name: str = "mock_file.py") -> List[Tuple[Dict[str, Any], str, str]]:
    """
    Scans a single string of Python source code and returns classified findings.
    Useful for unit testing audit detection.
    """
    lines = source_code.splitlines()
    results = []
    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped.startswith("#"):
            continue
        for pat, label, desc in AUDIT_RULES:
            if re.search(pat, line):
                item = {
                    "file": file_name,
                    "line_num": idx + 1,
                    "label": label,
                    "description": desc,
                    "snippet": line_stripped,
                }
                cat, just = classify_finding(file_name, idx + 1, label, line_stripped)
                results.append((item, cat, just))
    return results


def audit(scan_dir: str = MODULES_DIR) -> int:
    """
    Scans modules directory and returns exit code (0 if Category E == 0, 1 otherwise).
    """
    findings: List[Dict[str, Any]] = []

    for root, _, files in os.walk(scan_dir):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            rel_path = os.path.relpath(path, scan_dir)
            with open(path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()

            for idx, line in enumerate(lines):
                line_stripped = line.strip()
                if line_stripped.startswith("#"):
                    continue
                for pat, label, desc in AUDIT_RULES:
                    if re.search(pat, line):
                        findings.append({
                            "file": rel_path,
                            "line_num": idx + 1,
                            "label": label,
                            "description": desc,
                            "snippet": line_stripped,
                        })

    print(f"=== Expanded Role Detection Structural Audit ===")
    print(f"Total occurrences found across {scan_dir}: {len(findings)}\n")

    classified: List[Tuple[Dict[str, Any], str, str]] = []
    e_violations = []

    for item in findings:
        cat, just = classify_finding(item["file"], item["line_num"], item["label"], item["snippet"])
        classified.append((item, cat, just))
        if cat == "E":
            e_violations.append((item, just))

    # Print summary counts by category
    cats = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    for _, cat, _ in classified:
        cats[cat] = cats.get(cat, 0) + 1

    print("Classification Summary:")
    print(f"  A. Physical structural evidence:       {cats['A']}")
    print(f"  B. Semantic candidate evidence:         {cats['B']}")
    print(f"  C. Diagnostic-only hint:                {cats['C']}")
    print(f"  D. Legitimate business logic:           {cats['D']}")
    print(f"  E. Prohibited authoritative assumption: {cats['E']}")
    print()

    for item, cat, just in classified:
        print(f"[{cat}] {item['file']}:{item['line_num']} ({item['label']}) -> {just}")
        print(f"     Snippet: {item['snippet'][:100]}")

    if e_violations:
        print(f"\n[FAIL] Found {len(e_violations)} prohibited authoritative assumptions (Category E):")
        for v, reason in e_violations:
            print(f"  - {v['file']}:{v['line_num']}: {v['snippet']} ({reason})")
        return 1
    else:
        print("\n[PASS] The current structural audit found zero Category E prohibited authoritative assumptions across modules/.")
        return 0


if __name__ == "__main__":
    sys.exit(audit())
