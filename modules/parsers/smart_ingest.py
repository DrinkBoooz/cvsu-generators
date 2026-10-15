import os
import re
import json
from typing import Dict, List, Any, Optional
from modules.common.logger import logger


CATEGORY_SCHEDULE = "schedule"
CATEGORY_ROSTER = "roster"
CATEGORY_TEMPLATE = "template"
CATEGORY_CALENDAR = "calendar"
CATEGORY_ORG_PRESET = "org_preset"
CATEGORY_WORKSPACE = "workspace"
CATEGORY_UNKNOWN = "unknown"

SUPPORTED_EXTENSIONS = {
    ".xlsx", ".xls", ".xlsm", ".csv",
    ".docx", ".ics", ".json"
}


class SmartIngestClassifier:
    """
    Deterministic file classifier and router for the CvSU Generator workflow.
    Inspects file extensions, filename patterns, and internal structure/content
    to auto-classify dropped or selected files.
    """

    def classify_file(self, file_path: str) -> Dict[str, Any]:
        """Classifies a single file by path and returns detection telemetry."""
        if not file_path or not isinstance(file_path, str):
            return {
                "path": file_path or "",
                "filename": "",
                "category": CATEGORY_UNKNOWN,
                "confidence": 0.0,
                "details": {"error": "Invalid or empty path"}
            }

        filename = os.path.basename(file_path)
        lower_name = filename.lower()
        ext = os.path.splitext(file_path)[1].lower()

        if "\x00" in file_path:
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_UNKNOWN,
                "confidence": 0.0,
                "details": {"error": "Null byte in path"}
            }

        # ── 1. Specific compound extensions & .ics ────────────────────────────
        if lower_name.endswith(".cvsu-workspace.json"):
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_WORKSPACE,
                "confidence": 1.0,
                "details": {"reason": "Named .cvsu-workspace.json extension"}
            }

        if lower_name.endswith(".cvsu-org.json"):
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_ORG_PRESET,
                "confidence": 1.0,
                "details": {"reason": "Named .cvsu-org.json extension"}
            }

        if ext == ".ics":
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_CALENDAR,
                "confidence": 1.0,
                "details": {"reason": "iCalendar (.ics) format"}
            }

        if ext == ".docx":
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_TEMPLATE,
                "confidence": 1.0,
                "details": {"reason": "Word document (.docx) template"}
            }

        # ── 2. Generic JSON payload inspection ───────────────────────────────
        if ext == ".json":
            return self._classify_json(file_path, filename)

        # ── 3. Spreadsheets & Delimited Files (.xlsx, .xls, .csv) ───────────
        if ext in (".xlsx", ".xls", ".xlsm", ".csv"):
            return self._classify_tabular(file_path, filename, ext)

        return {
            "path": file_path,
            "filename": filename,
            "category": CATEGORY_UNKNOWN,
            "confidence": 0.0,
            "details": {"reason": f"Unsupported file extension: {ext}"}
        }

    def _classify_json(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Inspects JSON structure to distinguish workspaces, presets, and calendars."""
        if not os.path.isfile(file_path):
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_UNKNOWN,
                "confidence": 0.0,
                "details": {"error": "File does not exist"}
            }

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_UNKNOWN,
                "confidence": 0.0,
                "details": {"error": f"Invalid JSON: {e}"}
            }

        if isinstance(data, dict):
            # Check for Workspace snapshot keys
            if any(k in data for k in ("workspace_id", "roster_mappings", "selected_classes")) or (
                "schedule_path" in data and "rosters" in data
            ):
                return {
                    "path": file_path,
                    "filename": filename,
                    "category": CATEGORY_WORKSPACE,
                    "confidence": 0.95,
                    "details": {"workspace_name": data.get("name", ""), "workspace_id": data.get("workspace_id", "")}
                }

            # Check for Org Preset keys
            if "organization_preset" in data or "signatories" in data or (
                "campus" in data and "college" in data and "department" in data
            ):
                return {
                    "path": file_path,
                    "filename": filename,
                    "category": CATEGORY_ORG_PRESET,
                    "confidence": 0.95,
                    "details": {"campus": data.get("campus", ""), "college": data.get("college", "")}
                }

            # Check for Calendar config keys
            if "calendar_config" in data or "calendar_exceptions" in data or "recurrence_rules" in data:
                return {
                    "path": file_path,
                    "filename": filename,
                    "category": CATEGORY_CALENDAR,
                    "confidence": 0.95,
                    "details": {"reason": "JSON calendar configuration"}
                }

        return {
            "path": file_path,
            "filename": filename,
            "category": CATEGORY_UNKNOWN,
            "confidence": 0.2,
            "details": {"reason": "Unrecognized JSON schema"}
        }

    def _classify_tabular(self, file_path: str, filename: str, ext: str) -> Dict[str, Any]:
        """Distinguishes schedule vs roster vs grading template for tabular files."""
        lower_name = filename.lower()

        # Filename heuristic signals
        has_sched_name = any(k in lower_name for k in ("sched", "schedule", "faculty_load", "load", "faculty"))
        has_roster_name = any(k in lower_name for k in ("roster", "student", "students", "class_list", "classlist", "list of"))
        has_grading_name = any(k in lower_name for k in ("grade", "grading", "grading_sheet", "gradingsheet"))

        if has_grading_name and not has_roster_name and not has_sched_name:
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_TEMPLATE,
                "confidence": 0.9,
                "details": {"reason": "Grading spreadsheet template filename"}
            }

        # Content Inspection
        if os.path.isfile(file_path):
            try:
                from modules.parsers.schedule_parser import inspect_schedule_file
                from modules.parsers.roster_parser import _detect_roster_columns, _read_excel_raw_rows, _read_csv_raw_rows

                # Check schedule structure
                sched_meta = inspect_schedule_file(file_path)
                has_sched_slots = bool(sched_meta and sched_meta.get("total_slots", 0) > 0)
                has_sched_classes = bool(sched_meta and sched_meta.get("classes"))

                # Check roster structure
                if ext in (".xlsx", ".xls", ".xlsm"):
                    raw_rows, _ = _read_excel_raw_rows(file_path)
                else:
                    raw_rows, _ = _read_csv_raw_rows(file_path)

                has_roster_cols = False
                if raw_rows:
                    auto_name, auto_id, _ = _detect_roster_columns(raw_rows)
                    has_roster_cols = bool(auto_name is not None and auto_id is not None)

                # Disambiguate based on combined content + name signals
                if has_sched_slots or (has_sched_classes and not has_roster_name):
                    confidence = 0.95 if has_sched_name else 0.85
                    return {
                        "path": file_path,
                        "filename": filename,
                        "category": CATEGORY_SCHEDULE,
                        "confidence": confidence,
                        "details": {
                            "instructor": sched_meta.get("instructor", "") if sched_meta else "",
                            "total_slots": sched_meta.get("total_slots", 0) if sched_meta else 0,
                            "classes_count": len(sched_meta.get("classes", [])) if sched_meta else 0,
                        }
                    }

                if has_roster_cols or has_roster_name:
                    confidence = 0.95 if has_roster_name else 0.85
                    return {
                        "path": file_path,
                        "filename": filename,
                        "category": CATEGORY_ROSTER,
                        "confidence": confidence,
                        "details": {
                            "rows_detected": len(raw_rows) if raw_rows else 0,
                            "has_roster_cols": has_roster_cols,
                        }
                    }

            except Exception as e:
                logger.warning(f"Content inspection failed for {filename}: {e}")

        # Fallback to pure filename hints if file couldn't be deeply read
        if has_sched_name:
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_SCHEDULE,
                "confidence": 0.7,
                "details": {"reason": "Filename matches schedule keyword"}
            }

        if has_roster_name:
            return {
                "path": file_path,
                "filename": filename,
                "category": CATEGORY_ROSTER,
                "confidence": 0.7,
                "details": {"reason": "Filename matches roster keyword"}
            }

        # Default fallback for CSV/XLSX without strong schedule marker is roster
        return {
            "path": file_path,
            "filename": filename,
            "category": CATEGORY_ROSTER,
            "confidence": 0.5,
            "details": {"reason": "Default tabular heuristic fallback"}
        }

    def classify_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Classifies an array of files, expanding directories where necessary."""
        results = []
        if not file_paths:
            return results

        expanded_paths = []
        for p in file_paths:
            if not p:
                continue
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if not f.startswith(".") and f != "Thumbs.db":
                            expanded_paths.append(os.path.join(root, f))
            else:
                expanded_paths.append(p)

        for p in expanded_paths:
            results.append(self.classify_file(p))
        return results

    def ingest_files(self, file_paths: List[str], app_api: Any = None) -> Dict[str, Any]:
        """
        Classifies and deterministically routes a batch of files into the application state.
        Executes corresponding API actions (setting schedule, loading rosters, importing workspaces).
        """
        classified = self.classify_files(file_paths)
        applied_actions = []
        diagnostics = []

        roster_files_to_add = []
        schedule_file = None
        workspaces_to_load = []
        presets_to_apply = []
        calendars_to_import = []
        templates_detected = []

        for item in classified:
            cat = item.get("category")
            path = item.get("path")
            fname = item.get("filename")

            if cat == CATEGORY_WORKSPACE:
                workspaces_to_load.append(path)
            elif cat == CATEGORY_SCHEDULE:
                schedule_file = path
            elif cat == CATEGORY_ROSTER:
                roster_files_to_add.append(path)
            elif cat == CATEGORY_ORG_PRESET:
                presets_to_apply.append(path)
            elif cat == CATEGORY_CALENDAR:
                calendars_to_import.append(path)
            elif cat == CATEGORY_TEMPLATE:
                templates_detected.append(path)
            else:
                diagnostics.append(f"Skipped unrecognized item: {fname}")

        # If an application API bridge instance is provided, execute actions
        if app_api is not None:
            # 1. Apply workspaces first (may configure base state)
            for ws_path in workspaces_to_load:
                try:
                    res = app_api.import_workspace_file(ws_path)
                    if res.get("status") == "success":
                        ws_data = res.get("workspace", {})
                        ws_name = ws_data.get("name") or os.path.basename(ws_path)
                        app_api.load_workspace(ws_data.get("workspace_id") or ws_name)
                        applied_actions.append(f"Loaded workspace snapshot: {ws_name}")
                except Exception as e:
                    diagnostics.append(f"Failed loading workspace {ws_path}: {e}")

            # 2. Apply schedule if present
            if schedule_file:
                try:
                    res = app_api.handle_dropped_schedule(os.path.basename(schedule_file), original_path=schedule_file)
                    applied_actions.append(f"Loaded instructor schedule: {os.path.basename(schedule_file)}")
                except Exception as e:
                    diagnostics.append(f"Failed applying schedule {schedule_file}: {e}")

            # 3. Apply rosters
            if roster_files_to_add:
                try:
                    payloads = [{"filename": os.path.basename(p), "path": p, "data": None} for p in roster_files_to_add]
                    res = app_api.handle_dropped_rosters(payloads)
                    applied_actions.append(f"Added {len(roster_files_to_add)} student roster(s)")
                except Exception as e:
                    diagnostics.append(f"Failed applying rosters: {e}")

            # 4. Apply organization presets
            for preset_path in presets_to_apply:
                try:
                    res = app_api.import_org_preset(preset_path)
                    if res.get("status") == "success":
                        applied_actions.append(f"Applied organization preset: {os.path.basename(preset_path)}")
                except Exception as e:
                    diagnostics.append(f"Failed applying org preset {preset_path}: {e}")

            # 5. Apply calendar files
            for cal_path in calendars_to_import:
                try:
                    res = app_api.import_calendar_ics(cal_path)
                    if res.get("status") == "success":
                        applied_actions.append(f"Imported calendar: {os.path.basename(cal_path)} ({res.get('count', 0)} events)")
                except Exception as e:
                    diagnostics.append(f"Failed importing calendar {cal_path}: {e}")

        return {
            "status": "success",
            "classified_items": classified,
            "applied_actions": applied_actions,
            "diagnostics": diagnostics,
            "summary": {
                "schedule": os.path.basename(schedule_file) if schedule_file else None,
                "rosters_added": len(roster_files_to_add),
                "workspaces_loaded": len(workspaces_to_load),
                "calendars_imported": len(calendars_to_import),
                "presets_applied": len(presets_to_apply),
                "templates_detected": len(templates_detected),
            }
        }
