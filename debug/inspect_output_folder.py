import zipfile, glob, os
from lxml import etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"
import sys
folder = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\danjo\OneDrive\CVSU GENERATORS\output\BSCS_1-4"
files=glob.glob(os.path.join(folder,'*.docx'))
if not files:
    print('No docx files found')
for p in files:
    print('\n==',os.path.basename(p))
    with zipfile.ZipFile(p) as z:
        root=etree.fromstring(z.read('word/document.xml'))
    body=root.find(w('body'))
    tbls=body.findall('.//'+w('tbl'))
    print('Tables:',len(tbls))
    for ti,tbl in enumerate(tbls[:2]):
        rows=tbl.findall(w('tr'))
        print(' Table',ti,'rows',len(rows))
        for i,row in enumerate(rows[:4]):
            cells=row.findall(w('tc'))
            texts=["".join((t.text or '') for t in c.iter(w('t'))) for c in cells]
            print('  ROW',i,texts)
