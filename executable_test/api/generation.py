"""
Generation mixin — background document generation worker, cancellation, and
real-time UI telemetry.

Part B/C: window lifecycle state is checked via api._window_state before every
evaluate_js call.  All WebView dispatch goes through _safe_evaluate_js().

Part D: schedule_path, rosters, roster_configs, and output_dir are snapshotted
under self._lock at generation-start so the worker thread never races against
UI mutations.
"""

import threading
import json
from modules.common.logger import logger


def _safe_evaluate_js(window, js_code: str, *, window_state: str = "OPEN",
                      context: str = "") -> bool:
    """
    Centralized, lifecycle-aware WebView dispatch helper.

    Checks the window lifecycle state before attempting evaluate_js.
    Catches all Python-level exceptions (including any that propagate from
    the .NET CLR bridge layer in pythonnet).

    Returns True on success, False on any guarded or exceptional failure.
    Failures are logged at DEBUG level (expected during teardown) or WARNING
    level (unexpected while window is still OPEN).

    Telemetry failures must NEVER abort generation — callers must never rely
    on the return value for correctness; they may use it for diagnostics only.
    """
    if window_state in ("CLOSING", "CLOSED"):
        # Expected — suppress silently.
        return False
    if window is None:
        logger.debug(f"_safe_evaluate_js: window is None ({context})")
        return False
    try:
        window.evaluate_js(js_code)
        return True
    except Exception as e:
        # Log at WARNING only when the window was believed to be OPEN —
        # this is an unexpected WebView failure, not a normal teardown.
        if window_state == "OPEN":
            logger.warning(
                f"evaluate_js failed unexpectedly ({context}): "
                f"{type(e).__name__}: {e}"
            )
        else:
            logger.debug(
                f"evaluate_js suppressed during teardown ({context}): "
                f"{type(e).__name__}: {e}"
            )
        return False


class GenerationMixin:
    """Mixin handling background generation worker thread, cancellation, and real-time telemetry."""

    def cancel_generation(self):
        with self._lock:
            if self._is_processing and self._cancel_event:
                self._cancel_event.set()
                if hasattr(self, "_generation_progress"):
                    self._generation_progress["status"] = "cancelled"
                logger.info("User requested generation cancellation.")
                return {"status": "success", "message": "Cancellation requested."}
        return {"status": "error", "message": "No active generation to cancel."}

    def get_generation_progress(self):
        """Returns thread-safe generation progress snapshot for UI polling."""
        with self._lock:
            return dict(getattr(self, "_generation_progress", {
                "status": "idle",
                "current_index": 0,
                "total_count": 0,
                "percent": 0,
                "current_file_label": "",
                "current_class": "",
                "error": None,
            }))

    def preview_sample_document(self, payload=None):
        """
        In-memory pre-flight sample preview of the first detected section and roster.
        Calculates exact font scaling tier (<=30 -> 8pt, 31-35 -> 7pt, >35 -> 6pt),
        resolves metadata slots, and returns sample roster rows without writing files to disk.
        """
        import os
        try:
            payload = payload or {}
            target_sched = payload.get("schedule_path") or self.schedule_path
            target_roster = payload.get("roster_path")
            if not target_roster and self.rosters:
                target_roster = self.rosters[0]

            instructor = payload.get("instructor") or ""
            course_sec = payload.get("course_section") or ""
            schedule_code = payload.get("schedule_code") or ""
            subject_name = payload.get("subject") or ""
            semester_ay = payload.get("semester_ay") or "1st Sem AY 2026-2027"
            time_days_room = payload.get("time_days_room") or "TBA"

            # 1. Parse schedule if provided and metadata missing
            if target_sched and os.path.isfile(target_sched) and (not course_sec or not instructor):
                from modules.parsers.schedule_parser import parse_schedule
                schedules = parse_schedule(target_sched)
                if schedules:
                    s0 = schedules[0]
                    instructor = instructor or s0.get("instructor", "")
                    course_sec = course_sec or s0.get("course_sec", "")
                    schedule_code = schedule_code or s0.get("schedule_code", "")
                    subject_name = subject_name or s0.get("subject_name", "")
                    semester_ay = semester_ay or s0.get("semester_ay", semester_ay)
                    time_days_room = time_days_room or s0.get("time_days_room", time_days_room)

            # 2. Parse roster if available
            students = []
            if target_roster and os.path.isfile(target_roster):
                from modules.parsers.roster_parser import load_students
                cfg = (self.roster_configs or {}).get(target_roster) or {}
                raw_students = load_students(
                    target_roster,
                    header_row=cfg.get("header_row"),
                    name_col=cfg.get("name_col"),
                    id_col=cfg.get("id_col")
                )
                students = raw_students or []



            # Fallback if no students loaded
            if not students:
                sample_count = int(payload.get("student_count", 25))
                from modules.models.student import Student
                students = [
                    Student(name=f"SAMPLE STUDENT SURNAME, GIVEN {i:02d}", student_number=f"2026-100{i:02d}")
                    for i in range(1, sample_count + 1)
                ]


            student_count = len(students)
            if student_count <= 30:
                active_font_pt = "8pt"
            elif student_count <= 35:
                active_font_pt = "7pt"
            else:
                active_font_pt = "6pt"

            if not instructor:
                instructor = "Prof. Juan Dela Cruz"
            if not course_sec:
                course_sec = "BSIT 3-1"
            if not schedule_code:
                schedule_code = "12345"
            if not subject_name:
                subject_name = "ITEC 50 - Web Systems and Technologies"

            resolved_slots = {
                "instructor": instructor,
                "course_section": course_sec,
                "schedule_code": schedule_code,
                "subject": subject_name,
                "time_days_room": time_days_room,
                "semester_ay": semester_ay,
                "college": "College of Engineering and Information Technology",
                "department": "Department of Information Technology",
                "student_count": str(student_count),
                "active_font_pt": active_font_pt,
            }

            sample_roster_rows = [
                {
                    "index": i + 1,
                    "student_number": getattr(s, "student_number", "") or (s.get("student_number") if isinstance(s, dict) else ""),
                    "name": getattr(s, "name", "") or (s.get("name") if isinstance(s, dict) else ""),
                }
                for i, s in enumerate(students[:10])
            ]

            org_context = {
                "institution": "Cavite State University",
                "campus": "Don Severino de las Alas Campus (Main Campus)",
                "college": "College of Engineering and Information Technology",
                "department": "Department of Information Technology",
            }
            signatory_chain = [
                {"role": "Instructor", "title": "Instructor", "name": instructor},
                {"role": "Department Chairperson", "title": "Department Chairperson", "name": "Department Chairperson"},
                {"role": "College Dean", "title": "College Dean", "name": "College Dean"},
            ]

            return {
                "status": "success",
                "section": course_sec,
                "schedule_code": schedule_code,
                "subject": subject_name,
                "instructor": instructor,
                "student_count": student_count,
                "active_font_pt": active_font_pt,
                "resolved_slots": resolved_slots,
                "sample_roster_rows": sample_roster_rows,
                "organizational_context": org_context,
                "signatory_chain": signatory_chain,
            }
        except Exception as e:
            logger.error(f"Failed to generate pre-flight sample preview: {e}")
            return {"status": "error", "message": str(e)}

    def run_generation(self, type_overrides=None, date_overrides=None, class_filter=None, engine_filter=None, roster_configs=None, export_pdf=False):
        # ── Part D: acquire lock and snapshot all mutable UI state ──────────
        with self._lock:
            if self._is_processing:
                return {"status": "error", "message": "A generation task is already in progress."}
            self._is_processing = True
            self._generation_progress = {
                "status": "running",
                "current_index": 0,
                "total_count": 0,
                "percent": 0,
                "current_file_label": "Initializing...",
                "current_class": "",
                "error": None,
            }


            # Snapshot inputs under the lock so the worker thread gets a
            # consistent, immutable view even if the UI mutates state later.
            if roster_configs is not None:
                self.roster_configs = roster_configs

            snap_schedule = self.schedule_path
            snap_rosters = list(self.rosters)           # shallow copy of the list
            snap_roster_configs = dict(self.roster_configs)
            snap_output_dir = self.output_dir
            self._cancel_event.clear()

        # ── Validate before spawning thread ──────────────────────────────────
        if not snap_schedule:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Instructor Schedule. Please attach your Master Schedule .xls context."}
        if not snap_rosters:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Student Rosters. Please attach the student list files."}
        if not snap_output_dir:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Output Directory. Operations cannot resolve without an endpoint."}

        try:
            logger.info("Commencing Build Initialization with real-time telemetry...")
            logger.info(f"Loaded Schedule: {snap_schedule}")
            logger.info(f"Loaded Rosters: {len(snap_rosters)} file(s)")
            logger.info(f"Target Output Directory: {snap_output_dir}")
            logger.info(f"Selected Engines: {engine_filter}")

            # Read active_gen_id before spawning the thread so we don't race
            # against window teardown on this call either.
            active_gen_id = None
            try:
                if getattr(self, "_window_state", "OPEN") == "OPEN":
                    active_gen_id = self._window.evaluate_js("window._activeGenerationId")
            except Exception:
                pass

            # Emit diagnostic milestone if diagnostics are active
            try:
                emit = getattr(getattr(self, "_window", None), "_diag_emit", None)
                if callable(emit):
                    emit("generation_started",
                         schedule=snap_schedule,
                         roster_count=len(snap_rosters),
                         engine_filter=engine_filter)
            except Exception:
                pass

            def _progress_hook(info):
                # ── Update thread-safe progress snapshot ───────────────
                try:
                    with self._lock:
                        if isinstance(info, dict):
                            self._generation_progress["current_index"] = info.get("step", self._generation_progress["current_index"])
                            self._generation_progress["total_count"] = info.get("total_steps", self._generation_progress["total_count"])
                            self._generation_progress["percent"] = info.get("percent", self._generation_progress["percent"])
                            self._generation_progress["current_file_label"] = info.get("current_task", self._generation_progress["current_file_label"])
                            self._generation_progress["current_class"] = info.get("current_class", self._generation_progress["current_class"])
                except Exception:
                    pass

                # ── Part C: safe dispatch — never block, never raise ─────────
                state = getattr(self, "_window_state", "OPEN")
                if state in ("CLOSING", "CLOSED"):
                    return
                try:
                    if active_gen_id is not None and isinstance(info, dict) and "generation_id" not in info:
                        info["generation_id"] = active_gen_id
                    js_code = (
                        f"if (window.onGenerationProgress) "
                        f"window.onGenerationProgress({json.dumps(info)}, {json.dumps(active_gen_id)});"
                    )
                    _safe_evaluate_js(
                        self._window, js_code,
                        window_state=state,
                        context="progress_hook"
                    )
                    # Diagnostic milestone
                    try:
                        emit = getattr(getattr(self, "_window", None), "_diag_emit", None)
                        if callable(emit):
                            emit("generation_progress",
                                 step=info.get("step") if isinstance(info, dict) else None)
                    except Exception:
                        pass
                except Exception as pe:
                    logger.debug(f"Telemetry progress hook error: {pe}")

            def _thread_target():
                from modules.services.orchestrator import process_all

                # Diagnostic milestone
                try:
                    emit = getattr(getattr(self, "_window", None), "_diag_emit", None)
                    if callable(emit):
                        emit("generation_worker_created",
                             thread=threading.current_thread().name)
                except Exception:
                    pass

                results = None
                try:
                    # ── Part D: worker uses snapshots, NOT self.schedule_path etc. ──
                    results = process_all(
                        snap_schedule,
                        snap_rosters,
                        snap_output_dir,
                        type_overrides=type_overrides,
                        date_overrides=date_overrides,
                        class_filter=class_filter,
                        engine_filter=engine_filter,
                        progress_callback=_progress_hook,
                        cancel_event=self._cancel_event,
                        roster_configs=snap_roster_configs,
                        export_pdf=export_pdf,
                    )

                    gen = results["generated"]
                    skp = results["skipped"]
                    err = results["errors"]

                    total_generated = len(gen["attendance"]) + len(gen["grades"]) + len(gen["ceit"]) + len(gen.get("pdf", []))
                    total_skipped = len(skp["attendance"]) + len(skp["grades"]) + len(skp["ceit"]) + len(skp["rosters"]) + len(skp.get("pdf", []))
                    total_errors = len(err["attendance"]) + len(err["grades"]) + len(err["ceit"]) + len(err["rosters"]) + len(err.get("pdf", []))

                    if results.get("cancelled"):
                        logger.info(
                            f"Build cancelled by user. {total_generated} file(s) generated."
                        )
                        payload = {
                            "status": "cancelled",
                            "message": f"Generation stopped by user. {total_generated} file(s) were generated.",
                            "stats": {
                                "generated": total_generated,
                                "errors": total_errors,
                                "skipped": total_skipped
                            },
                            "details": results,
                            "output_dir": snap_output_dir
                        }
                    elif total_generated == 0:
                        logger.warning(
                            f"Build completed: 0 files generated (Skipped: {total_skipped}, Errors: {total_errors})."
                        )
                        payload = {
                            "status": "error",
                            "message": f"Generation blocked: 0 files generated. Skipped: {total_skipped}. Errors: {total_errors}.",
                            "details": results,
                            "output_dir": snap_output_dir
                        }
                    pdf_skipped = skp.get("pdf", [])
                    pdf_count = len(gen.get("pdf", []))
                    skip_pdf_notice = f" (Note: PDF export skipped - {pdf_skipped[0]})" if (export_pdf and pdf_count == 0 and pdf_skipped) else ""

                    logger.info(
                        f"Build completed successfully! {total_generated} file(s) generated "
                        f"(CEIT: {len(gen['ceit'])}, Attendance: {len(gen['attendance'])}, "
                        f"Grades: {len(gen['grades'])}, PDF: {pdf_count}).{skip_pdf_notice}"
                    )
                    payload = {
                        "status": "success",
                        "message": f"Generation complete! {total_generated} files generated successfully.{skip_pdf_notice}",
                        "stats": {
                            "generated": total_generated,
                            "errors": total_errors,
                            "skipped": total_skipped
                        },
                        "details": results,
                        "output_dir": snap_output_dir
                    }
                except Exception as e:
                    logger.error(f"Error Pipeline Breakdown: {e}", exc_info=True)
                    payload = {"status": "error", "message": f"Fatal Generation Fault: {str(e)}", "details": None}
                finally:
                    with self._lock:
                        self._is_processing = False
                        if results and results.get("cancelled"):
                            self._generation_progress["status"] = "cancelled"
                        elif payload.get("status") == "success":
                            self._generation_progress["status"] = "completed"
                            self._generation_progress["percent"] = 100
                        else:
                            self._generation_progress["status"] = payload.get("status", "error")


                # ── Part C: safe completion dispatch ────────────────────────
                try:
                    state = getattr(self, "_window_state", "OPEN")
                    if active_gen_id is not None and isinstance(payload, dict) and "generation_id" not in payload:
                        payload["generation_id"] = active_gen_id
                    js_code = (
                        f"if (window.onGenerationComplete) "
                        f"window.onGenerationComplete({json.dumps(payload)}, {json.dumps(active_gen_id)});"
                    )
                    success = _safe_evaluate_js(
                        self._window, js_code,
                        window_state=state,
                        context="completion_callback"
                    )
                    if not success and state == "OPEN":
                        # Attempt minimal fallback only if window was believed open
                        _safe_evaluate_js(
                            self._window,
                            "if (window.onGenerationError) window.onGenerationError();",
                            window_state=state,
                            context="completion_fallback"
                        )
                    # Diagnostic milestone
                    try:
                        emit = getattr(getattr(self, "_window", None), "_diag_emit", None)
                        if callable(emit):
                            emit("last_successful_ui_dispatch" if success else "ui_dispatch_skipped",
                                 context="completion_callback",
                                 window_state=state)
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Unexpected error in completion dispatch: {e}")

            t = threading.Thread(target=_thread_target, daemon=True,
                                 name="CvSUGenerationWorker")
            t.start()
            return None

        except Exception as e:
            with self._lock:
                self._is_processing = False
            logger.error(f"Error starting thread: {e}")
            return {"status": "error", "message": f"Failed to start generation thread: {str(e)}"}
