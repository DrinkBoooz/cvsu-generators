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
        if not self.schedule_path:
            return {"status": "error", "message": "Missing Instructor Schedule. Please attach your Master Schedule .xls context."}
        if not self.rosters:
            return {"status": "error", "message": "Missing Student Rosters. Please attach the student list files."}
        if not self.output_dir:
            return {"status": "error", "message": "Missing Output Directory. Operations cannot resolve without an endpoint."}
        
        try:
            print("Commencing Build Initialization...")
            process_schedule.process_all(self.schedule_path, self.rosters, self.output_dir, type_overrides=type_overrides, date_overrides=date_overrides)
            
            return {"status": "success", "message": f"Successfully generated documentation array for {len(self.rosters)} active class rosters on target path."}
            
        except Exception as e:
            print(f"Error Pipeline Breakdown: {str(e)}")
            return {"status": "error", "message": f"Fatal Generation Fault: {str(e)}"}


if __name__ == '__main__':
    api = ScriptAPI()
    
    html_template = get_resource_path('ui.html')
    
    window = webview.create_window(
        title='CvSU Document Generators',
        url=html_template,
        js_api=api,
        width=750,
        height=620,
        text_select=False
    )
    api._window = window
    
    webview.start()
