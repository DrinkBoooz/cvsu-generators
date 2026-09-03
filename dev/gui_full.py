import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

class GeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CvSU Document Generators")
        self.root.geometry("620x380")
        
        # Configure a modern theme and styling (No external libraries required)
        style = ttk.Style(self.root)
        # 'clam' provides a flat, clean interface compared to the rigid native legacy look
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        style.configure("TFrame", background="#F5F6FA")
        style.configure("TLabel", background="#F5F6FA", foreground="#2F3640", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#192A56")
        
        style.configure(
            "Primary.TButton", 
            font=("Segoe UI", 11, "bold"), 
            background="#44BD32", 
            foreground="white",
            padding=8
        )
        style.map("Primary.TButton", background=[("active", "#4CD137")])
        
        style.configure(
            "Secondary.TButton", 
            font=("Segoe UI", 9), 
            background="#DCDDE1",
            foreground="#2F3640",
            padding=4
        )
        style.map("Secondary.TButton", background=[("active", "#E1B12C")])

        self.root.configure(bg="#F5F6FA")

        # Variables
        self.schedule_path = tk.StringVar()
        self.rosters = []
        self.rosters_display = tk.StringVar(value="Waiting for input...")
        self.output_dir = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="20 20 20 20")
        main_frame.pack(fill="both", expand=True)

        # Header Title
        ttk.Label(main_frame, text="Generate Documents", style="Header.TLabel").pack(anchor="w", pady=(0, 20))

        # 1. Schedule Selection
        ttk.Label(main_frame, text="Instructor Schedule (Excel):").pack(anchor="w", pady=(0, 5))
        frame1 = ttk.Frame(main_frame)
        frame1.pack(fill="x", pady=(0, 15))
        ttk.Entry(frame1, textvariable=self.schedule_path, state="readonly", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(frame1, text="Browse", style="Secondary.TButton", command=self.browse_schedule).pack(side="right")

        # 2. Roster Selection
        ttk.Label(main_frame, text="Student Rosters (CSV):").pack(anchor="w", pady=(0, 5))
        frame2 = ttk.Frame(main_frame)
        frame2.pack(fill="x", pady=(0, 15))
        ttk.Entry(frame2, textvariable=self.rosters_display, state="readonly", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(frame2, text="Browse", style="Secondary.TButton", command=self.browse_rosters).pack(side="right")

        # 3. Output Directory
        ttk.Label(main_frame, text="Output Workspace Folder:").pack(anchor="w", pady=(0, 5))
        frame3 = ttk.Frame(main_frame)
        frame3.pack(fill="x", pady=(0, 25))
        ttk.Entry(frame3, textvariable=self.output_dir, state="readonly", font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(frame3, text="Browse", style="Secondary.TButton", command=self.browse_output).pack(side="right")

        # 4. Generate Button
        ttk.Button(main_frame, text="INITIALIZE GENERATOR", style="Primary.TButton", command=self.run_generation).pack(fill="x")

    def browse_schedule(self):
        path = filedialog.askopenfilename(
            title="Select Excel Schedule",
            filetypes=(("Excel files", "*.xls;*.xlsx;*.xlsm"), ("All files", "*.*"))
        )
        if path:
            self.schedule_path.set(path)

    def browse_rosters(self):
        paths = filedialog.askopenfilenames(
            title="Select Student Rosters",
            filetypes=(("Student Lists", "*.csv;*.xlsx;*.xls"), ("All files", "*.*"))
        )
        if paths:
            self.rosters = list(paths)
            self.rosters_display.set(f"Loaded {len(paths)} class rosters")

    def browse_output(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_dir.set(path)

    def run_generation(self):
        if not self.schedule_path.get():
            messagebox.showerror("Validation Error", "Missing Schedule Configuration.\nPlease supply an Excel schedule before generating.")
            return
        if not self.rosters:
            messagebox.showerror("Validation Error", "Missing Rosters.\nPlease supply at least one CSV roster before generating.")
            return
        if not self.output_dir.get():
            messagebox.showerror("Validation Error", "Missing Target Folder.\nPlease declare an Output Directory before generating.")
            return

        messagebox.showinfo("Generating Workloads", "Systems activated! Please check the terminal logs.")
        # Real generator functions would hook in right here!

if __name__ == "__main__":
    root = tk.Tk()
    app = GeneratorApp(root)
    root.mainloop()
