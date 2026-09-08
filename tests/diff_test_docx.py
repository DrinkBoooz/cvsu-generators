import zipfile
import filecmp
import tempfile
import os

if __name__ == "__main__":
    z1_path = r'C:\Users\danjo\Downloads\test-1\CS1-4\Attendance\CS1-4_202612040_ATTENDANCE_Mon_August.docx'
    z2_path = r'c:\Users\danjo\OneDrive\CVSU GENERATORS\test_output_gen3\CS1-4\Attendance\CS1-4_202612040_ATTENDANCE_Mon_August.docx'
    if os.path.exists(z1_path) and os.path.exists(z2_path):
        z1 = zipfile.ZipFile(z1_path)
        z2 = zipfile.ZipFile(z2_path)

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            z1.extractall(td1)
            z2.extractall(td2)
            dcmp = filecmp.dircmp(td1, td2)
            
            def print_diffs(d, path=''):
                if d.diff_files:
                    print(f"Diff in {path}: {d.diff_files}")
                if d.left_only:
                    print(f"Left only in {path}: {d.left_only}")
                if d.right_only:
                    print(f"Right only in {path}: {d.right_only}")
                for k, v in d.subdirs.items():
                    print_diffs(v, os.path.join(path, k))
                    
            print_diffs(dcmp)

