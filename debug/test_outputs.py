import os, glob, zipfile, re
from lxml import etree

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"

def check_file(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml')
    root = etree.fromstring(xml)
    body = root.find(w('body'))
    paras = ["".join((t.text or "") for t in p.iter(w('t'))) for p in body.findall('.//'+w('p'))]
    tbls = body.findall('.//'+w('tbl'))
    
    text_content = "".join(paras)
    has_ortega = "ORTEGA" in text_content or "IT PT2" in text_content
    has_table = len(tbls) > 0
    row_count = len(tbls[0].findall(w('tr'))) if has_table else 0
    return has_ortega, row_count

total = 0
failed = 0
for root, dirs, files in os.walk('output'):
    for file in files:
        if file.endswith('.docx'):
            fpath = os.path.join(root, file)
            ortega, rows = check_file(fpath)
            total += 1
            if not ortega or rows < 5:
                print(f"FAILED: {fpath} - Ortega/IT PT2 Check: {ortega}, Rows: {rows}")
                failed += 1

print(f"\\nVerification Complete!\\nTotal Documents Checked: {total}\\nFailed: {failed}")
