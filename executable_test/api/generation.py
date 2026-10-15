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
                logger.info("User requested generation cancellation.")
                return {"status": "success", "message": "Cancellation requested."}
        return {"status": "error", "message": "No active generation to cancel."}

    def run_generation(self, type_overrides=None, date_overrides=None, class_filter=None, engine_filter=None, roster_configs=None):
        # ── Part D: acquire lock and snapshot all mutable UI state ──────────
        with self._lock:
            if self._is_processing:
                return {"status": "error", "message": "A generation task is already in progress."}
            self._is_processing = True

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
                        roster_configs=snap_roster_configs
                    )

                    gen = results["generated"]
                    skp = results["skipped"]
                    err = results["errors"]

                    total_generated = len(gen["attendance"]) + len(gen["grades"]) + len(gen["ceit"])
                    total_skipped = len(skp["attendance"]) + len(skp["grades"]) + len(skp["ceit"]) + len(skp["rosters"])
                    total_errors = len(err["attendance"]) + len(err["grades"]) + len(err["ceit"]) + len(err["rosters"])

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
                    else:
                        logger.info(
                            f"Build completed successfully! {total_generated} file(s) generated "
                            f"(CEIT: {len(gen['ceit'])}, Attendance: {len(gen['attendance'])}, "
                            f"Grades: {len(gen['grades'])})."
                        )
                        payload = {
                            "status": "success",
                            "message": f"Generation complete! {total_generated} files generated successfully.",
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
