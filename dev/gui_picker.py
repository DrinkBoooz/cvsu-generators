import os
import tkinter as tk
from tkinter import filedialog, messagebox
import sys

def prompt_for_files():
    # Hide the main tkinter root window
    root = tk.Tk()
    root.withdraw()

    # Make the dialog boxes appear on top of other windows
    root.attributes('-topmost', True)

    messagebox.showinfo(
        "CvSU Generators",
        "Please select your Excel Schedule file (.xls, .xlsx, .xlsm)."
    )

    schedule_path = filedialog.askopenfilename(
        title="Select Excel Schedule",
        filetypes=(
            ("Excel files", "*.xls;*.xlsx;*.xlsm"),
            ("All files", "*.*")
        )
    )

    if not schedule_path:
        messagebox.showerror("Error", "No schedule file selected. Exiting.")
        sys.exit(1)

    messagebox.showinfo(
        "CvSU Generators",
        "Please select your Student Roster lists (.xlsx, .csv)."
    )

    student_rosters = filedialog.askopenfilenames(
        title="Select Student Rosters",
        filetypes=(
            ("Student Lists", "*.xlsx;*.xls;*.csv"),
            ("All files", "*.*")
        )
    )

    if not student_rosters:
        messagebox.showerror("Error", "No student rosters selected. Exiting.")
        sys.exit(1)

    messagebox.showinfo(
        "CvSU Generators",
        "Finally, please select the Output Folder where the generated schedules will be saved."
    )

    output_dir = filedialog.askdirectory(
        title="Select Output Folder"
    )

    if not output_dir:
        messagebox.showerror("Error", "No output directory selected. Exiting.")
        sys.exit(1)

    return schedule_path, list(student_rosters), output_dir

if __name__ == "__main__":
    schedule_file, rosters, out_dir = prompt_for_files()
    
    # Just printing the output to terminal for prototype
    print(f"✅ Picked Schedule: {schedule_file}")
    print(f"✅ Picked {len(rosters)} Rosters:")
    for r in rosters:
        print(f"   - {r}")
    print(f"📂 Output will be saved to: {out_dir}")
