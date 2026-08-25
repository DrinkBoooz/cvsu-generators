import zipfile
from lxml import etree
p=r"C:\Users\danjo\OneDrive\CVSU GENERATORS\output\BSCS_1-4\BSCS_1-4_SYLLABUS_ACCEPTANCE.docx"
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"
with zipfile.ZipFile(p) as z:
    root=etree.fromstring(z.read('word/document.xml'))
body=root.find(w('body'))
tbls=body.findall('.//'+w('tbl'))
if not tbls:
    print('No tables')
    raise SystemExit(1)
tbl=tbls[0]
rows=tbl.findall(w('tr'))
for i,row in enumerate(rows[:10]):
    cells=row.findall(w('tc'))
    texts=["".join((t.text or '') for t in c.iter(w('t'))) for c in cells]
    print('ROW',i,texts)
