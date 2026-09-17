import threading
import json
from modules.common.logger import logger
from modules.services.orchestrator import process_all

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
        if roster_configs is not None:
            self.roster_configs = roster_configs
        with self._lock:
            if self._is_processing:
                return {"status": "error", "message": "A generation task is already in progress."}
            self._is_processing = True

        if not self.schedule_path:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Instructor Schedule. Please attach your Master Schedule .xls context."}
        if not self.rosters:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Student Rosters. Please attach the student list files."}
        if not self.output_dir:
            with self._lock:
                self._is_processing = False
            return {"status": "error", "message": "Missing Output Directory. Operations cannot resolve without an endpoint."}

        try:
            logger.info("Commencing Build Initialization with real-time telemetry...")
            logger.info(f"Loaded Schedule: {self.schedule_path}")
            logger.info(f"Loaded Rosters: {len(self.rosters)} file(s)")
            logger.info(f"Target Output Directory: {self.output_dir}")
            logger.info(f"Selected Engines: {engine_filter}")
            self._cancel_event.clear()

            active_gen_id = None
            try:
                if not getattr(self, "_is_window_closed", False):
                    active_gen_id = self._window.evaluate_js("window._activeGenerationId")
            except Exception:
                pass

            def _progress_hook(info):
                if getattr(self, "_is_window_closed", False):
                    return
                try:
                    if active_gen_id is not None and isinstance(info, dict) and "generation_id" not in info:
                        info["generation_id"] = active_gen_id
                    js_code = f"if (window.onGenerationProgress) window.onGenerationProgress({json.dumps(info)}, {json.dumps(active_gen_id)});"
                    self._window.evaluate_js(js_code)
                except Exception as pe:
                    logger.debug(f"Telemetry evaluate error: {pe}")

            def _thread_target():
                try:
                    results = process_all(
                        self.schedule_path,
                        self.rosters,
                        self.output_dir,
                        type_overrides=type_overrides,
                        date_overrides=date_overrides,
                        class_filter=class_filter,
                        engine_filter=engine_filter,
                        progress_callback=_progress_hook,
                        cancel_event=self._cancel_event,
                        roster_configs=self.roster_configs
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
                            "output_dir": self.output_dir
                        }
                    elif total_generated == 0:
                        logger.warning(
                            f"Build completed: 0 files generated (Skipped: {total_skipped}, Errors: {total_errors})."
                        )
                        payload = {
                            "status": "error",
                            "message": f"Generation blocked: 0 files generated. Skipped: {total_skipped}. Errors: {total_errors}.",
                            "details": results,
                            "output_dir": self.output_dir
                        }
                    else:
                        logger.info(
                            f"Build completed successfully! {total_generated} file(s) generated (CEIT: {len(gen['ceit'])}, Attendance: {len(gen['attendance'])}, Grades: {len(gen['grades'])})."
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
                            "output_dir": self.output_dir
                        }
                except Exception as e:
                    logger.error(f"Error Pipeline Breakdown: {e}", exc_info=True)
                    payload = {"status": "error", "message": f"Fatal Generation Fault: {str(e)}", "details": None}
                finally:
                    with self._lock:
                        self._is_processing = False

                try:
                    if not getattr(self, "_is_window_closed", False):
                        if active_gen_id is not None and isinstance(payload, dict) and "generation_id" not in payload:
                            payload["generation_id"] = active_gen_id
                        js_code = f"if (window.onGenerationComplete) window.onGenerationComplete({json.dumps(payload)}, {json.dumps(active_gen_id)});"
                        self._window.evaluate_js(js_code)
                except Exception as e:
                    logger.error(f"Failed to execute UI callback: {e}")
                    try:
                        if not getattr(self, "_is_window_closed", False):
                            self._window.evaluate_js("if (window.onGenerationError) window.onGenerationError();")
                    except Exception:
                        pass

            threading.Thread(target=_thread_target, daemon=True).start()
            return None

        except Exception as e:
            with self._lock:
                self._is_processing = False
            logger.error(f"Error starting thread: {e}")
            return {"status": "error", "message": f"Failed to start generation thread: {str(e)}"}
