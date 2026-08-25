import zipfile
from lxml import etree
for name in ['template_exam_midterm.docx','template_exam_finals.docx','template_tos_midterm.docx','template_tos_finals.docx']:
    p=rf'c:\Users\danjo\OneDrive\CVSU GENERATORS\templates\{name}'
    W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    def w(t): return f"{{{W}}}{t}"
    print('\nFILE', name)
    with zipfile.ZipFile(p) as z:
        root=etree.fromstring(z.read('word/document.xml'))
    body=root.find(w('body'))
    paras=["".join((t.text or '') for t in p.iter(w('t'))) for p in body.findall('.//'+w('p'))]
    for i in range(0,18):
        print(i, repr(paras[i]))
    tbls=body.findall('.//'+w('tbl'))
    for ti,tbl in enumerate(tbls[:2]):
        rows=tbl.findall(w('tr'))
        print(' table', ti, 'rows', len(rows))
        for j,row in enumerate(rows[:8]):
            cells=row.findall(w('tc'))
            texts=[''.join((t.text or '') for t in c.iter(w('t'))) for c in cells]
            print('   ',j,texts)
