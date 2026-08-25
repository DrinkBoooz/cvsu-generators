import sys, zipfile
from lxml import etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"
if len(sys.argv) < 2:
    print('Usage: inspect_doc_file.py <path.docx>')
    raise SystemExit(1)
path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    root = etree.fromstring(z.read('word/document.xml'))
body = root.find(w('body'))
print('File:', path)
# print first 10 paras
paras = body.findall('.//'+w('p'))
for i,p in enumerate(paras[:20]):
    texts = ''.join(t.text or '' for t in p.iter(w('t')))
    print(f'para[{i}]', repr(texts))
# print first 2 tables
tbls = body.findall('.//'+w('tbl'))
print('Tables:', len(tbls))
for ti,tbl in enumerate(tbls[:2]):
    rows = tbl.findall(w('tr'))
    print(' Table',ti,'rows',len(rows))
    for i,row in enumerate(rows[:8]):
        cells = row.findall(w('tc'))
        texts=["".join((t.text or '') for t in c.iter(w('t'))) for c in cells]
        print('  ROW',i,texts)
