import webview
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import process_schedule

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ScriptAPI:
    def __init__(self):
        self._window = None
        self.schedule_path = ""
        self.output_dir = ""
        self.rosters = []
        self._is_processing = False

    def browse_schedule(self):
        file_types = ('Excel files (*.xls;*.xlsx;*.xlsm)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=file_types
        )
        if result and len(result) > 0:
            self.schedule_path = result[0]
        return self.schedule_path

    def browse_rosters(self):
        file_types = ('Student Lists (*.csv;*.xlsx;*.xls)', 'All files (*.*)')
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=file_types
        )
        if result:
            self.rosters = list(result)
        return len(self.rosters)

    def browse_output(self):
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG
        )
        if result and len(result) > 0:
            self.output_dir = result[0]
        return self.output_dir

    def detect_classes(self):
        if not self.schedule_path or not self.rosters:
            return []
        try:
            return process_schedule.detect_classes(self.schedule_path, self.rosters)
        except Exception as e:
            print(f"Error in detect_classes: {str(e)}")
            return []

    def run_generation(self, type_overrides=None, date_overrides=None):
        if self._is_processing:
            return {"status": "error", "message": "A generation task is already in progress."}
            
        if not self.schedule_path:
            return {"status": "error", "message": "Missing Instructor Schedule. Please attach your Master Schedule .xls context."}
        if not self.rosters:
            return {"status": "error", "message": "Missing Student Rosters. Please attach the student list files."}
        if not self.output_dir:
            return {"status": "error", "message": "Missing Output Directory. Operations cannot resolve without an endpoint."}
        
        try:
            self._is_processing = True
            print("Commencing Build Initialization...")
            import threading
            import json

            def _thread_target():
                try:
                    results = process_schedule.process_all(self.schedule_path, self.rosters, self.output_dir, type_overrides=type_overrides, date_overrides=date_overrides)
                    
                    gen = results["generated"]
                    skp = results["skipped"]
                    err = results["errors"]
                    
                    total_generated = len(gen["attendance"]) + len(gen["grades"]) + len(gen["ceit"])
                    total_skipped = len(skp["attendance"]) + len(skp["grades"]) + len(skp["ceit"]) + len(skp["rosters"])
                    total_errors = len(err["attendance"]) + len(err["grades"]) + len(err["ceit"]) + len(err["rosters"])
                    
                    if total_generated == 0:
                        payload = {"status": "error", "message": f"Generation blocked: 0 files generated. Skipped: {total_skipped}. Errors: {total_errors}."}
                    else:
                        payload = {"status": "success", "message": f"Generation complete: {total_generated} files generated. {total_errors} errors. {total_skipped} skipped."}
                except Exception as e:
                    print(f"Error Pipeline Breakdown: {str(e)}")
                    payload = {"status": "error", "message": f"Fatal Generation Fault: {str(e)}"}
                finally:
                    self._is_processing = False
                
                # Use evaluate_js to update the UI from the background thread
                try:
                    # json.dumps ensures the payload is a valid JavaScript object string
                    js_code = f"onGenerationComplete({json.dumps(payload)});"
                    self._window.evaluate_js(js_code)
                except Exception as e:
                    process_schedule.logger.error(f"Failed to execute UI callback: {e}")
                    try:
                        self._window.evaluate_js("document.getElementById('processBtn').disabled = false; document.getElementById('processBtn').innerText = 'Initialize Workflow';")
                    except Exception:
                        pass

            # Spawn and start the background thread
            threading.Thread(target=_thread_target, daemon=True).start()
            
            # Return None to UI, letting the thread invoke onGenerationComplete later
            return None
            
        except Exception as e:
            print(f"Error starting thread: {str(e)}")
            return {"status": "error", "message": f"Failed to start generation thread: {str(e)}"}


if __name__ == '__main__':
    api = ScriptAPI()
    
    html_template = get_resource_path('ui.html')
    
    window = webview.create_window(
        title='CvSU Gen (Beta)',
        url=html_template,
        js_api=api,
        width=750,
        height=620,
        text_select=False
    )
    api._window = window
    
    webview.start()
