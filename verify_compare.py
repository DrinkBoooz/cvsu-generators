import filecmp
import os
import zipfile
import tempfile
import shutil

dir1 = r"C:\Users\danjo\Downloads\test-1"
dir2 = r"c:\Users\danjo\OneDrive\CVSU GENERATORS\test_output_gen5"

def compare_zip_files(file1, file2):
    try:
        with zipfile.ZipFile(file1, 'r') as z1, zipfile.ZipFile(file2, 'r') as z2:
            n1 = set(z1.namelist())
            n2 = set(z2.namelist())
            if n1 != n2:
                return False
            for n in n1:
                if n == 'docProps/core.xml':
                    continue
                if z1.read(n) != z2.read(n):
                    return False
            return True
    except zipfile.BadZipFile:
        return False

all_match = True
for root, _, files in os.walk(dir1):
    for f in files:
        rel_path = os.path.relpath(os.path.join(root, f), dir1)
        file1 = os.path.join(dir1, rel_path)
        file2 = os.path.join(dir2, rel_path)
        
        if not os.path.exists(file2):
            print(f"Missing file in generated: {rel_path}")
            all_match = False
            continue
            
        # Try binary match first
        if filecmp.cmp(file1, file2, shallow=False):
            continue
            
        # Try zip contents match (ignoring zip wrapper timestamps)
        if compare_zip_files(file1, file2):
            continue
            
        print(f"File contents differ: {rel_path}")
        all_match = False

if all_match:
    print("All 108 files matched successfully!")
else:
    print("Verification failed!")
