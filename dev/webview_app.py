import webview
import os
from tkinter import Tk, filedialog

class ScriptAPI:
    def __init__(self):
        self.schedule_path = ""
        self.output_dir = ""
        self.rosters = []

    def browse_schedule(self):
        # We can still use tkinter internally JUST for the native file popups!
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askopenfilename(
            title="Select Excel Schedule",
            filetypes=(("Excel files", "*.xls;*.xlsx;*.xlsm"), ("All files", "*.*"))
        )
        root.destroy()
        if path:
            self.schedule_path = path
        return self.schedule_path

    def browse_rosters(self):
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        paths = filedialog.askopenfilenames(
            title="Select Student Rosters",
            filetypes=(("Student Lists", "*.csv;*.xlsx;*.xls"), ("All files", "*.*"))
        )
        root.destroy()
        if paths:
            self.rosters = list(paths)
        return len(self.rosters)

    def browse_output(self):
        root = Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askdirectory(title="Select Output Folder")
        root.destroy()
        if path:
            self.output_dir = path
        return self.output_dir

    def run_generation(self):
        if not self.schedule_path:
            return {"status": "error", "message": "Missing Instructor Schedule."}
        if not self.rosters:
            return {"status": "error", "message": "Missing Student Rosters."}
        if not self.output_dir:
            return {"status": "error", "message": "Missing Output Directory."}
        
        # Real Python code hooks here!
        print(f"Backend Recieved -> Schedule: {self.schedule_path}")
        print(f"Backend Recieved -> Rosters: {len(self.rosters)}")
        
        return {"status": "success", "message": f"Successfully initialized generation against {str(len(self.rosters))} rosters! Check terminal logs."}


if __name__ == '__main__':
    api = ScriptAPI()
    
    html_template = os.path.join(os.path.dirname(__file__), 'ui.html')
    
    # Creates the Pywebview window wrapping the local HTML, exposing the api object implicitly to javascript.
    window = webview.create_window(
        title='CvSU Document Generators',
        url=f'file://{html_template}',
        js_api=api,
        width=700,
        height=550
    )
    
    webview.start()
