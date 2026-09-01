import zipfile
from lxml import etree
p=r"c:\Users\danjo\OneDrive\CVSU GENERATORS\templates\template_syllabus.docx"
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"
with zipfile.ZipFile(p) as z:
    xml=z.read('word/document.xml')
root=etree.fromstring(xml)
body=root.find(w('body'))
paras=["".join((t.text or '') for t in p.iter(w('t'))) for p in body.findall('.//'+w('p'))]
print('Total paras:', len(paras))
for i in range(0,30):
    if i < len(paras):
        print(i,repr(paras[i]))
    else:
        break
# print first table rows
tbls=body.findall('.//'+w('tbl'))
print('\nTables:', len(tbls))
if tbls:
    rows=tbls[0].findall(w('tr'))
    print('Table0 rows:', len(rows))
    for i,row in enumerate(rows[:6]):
        cells=row.findall(w('tc'))
        texts=["".join((t.text or '') for t in c.iter(w('t'))) for c in cells]
        print('ROW',i,texts)
