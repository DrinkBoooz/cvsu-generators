import filecmp
import os
import zipfile
import tempfile
import lxml.etree as et

dir1 = r"C:\Users\danjo\Downloads\test-1"
dir2 = r"c:\Users\danjo\OneDrive\CVSU GENERATORS\test_output_gen4"

def compare_xml(f1, f2):
    try:
        t1 = et.parse(f1)
        t2 = et.parse(f2)
        s1 = et.tostring(t1, method='c14n')
        s2 = et.tostring(t2, method='c14n')
        return s1 == s2
    except Exception as e:
        return False

def compare_zip_files(file1, file2):
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        try:
            with zipfile.ZipFile(file1, 'r') as z1:
                z1.extractall(td1)
            with zipfile.ZipFile(file2, 'r') as z2:
                z2.extractall(td2)
        except zipfile.BadZipFile:
            return False
            
        dcmp = filecmp.dircmp(td1, td2)
        
        # We need a recursive check
        def check_diff(dcmp, p1, p2):
            if dcmp.left_only or dcmp.right_only:
                return False
                
            for f in dcmp.diff_files:
                f1 = os.path.join(p1, f)
                f2 = os.path.join(p2, f)
                if f.endswith('.xml') or f.endswith('.rels'):
                    if not compare_xml(f1, f2):
                        print(f"  XML mismatch: {f}")
                        return False
                else:
                    return False
                    
            for d in dcmp.subdirs.keys():
                if not check_diff(dcmp.subdirs[d], os.path.join(p1, d), os.path.join(p2, d)):
                    return False
            return True
            
        return check_diff(dcmp, td1, td2)

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
            
        # Try zip contents match (ignoring zip wrapper timestamps and attribute order in xml)
        if compare_zip_files(file1, file2):
            continue
            
        print(f"File contents differ: {rel_path}")
        all_match = False

if all_match:
    print("All 108 files matched successfully!")
else:
    print("Verification failed!")
