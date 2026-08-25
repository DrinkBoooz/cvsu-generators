from lxml import etree
import zipfile
p=r"C:\Users\danjo\OneDrive\CVSU GENERATORS\output\BSCS_1-4_test3\BSCS_1-4\BSCS_1-4_SYLLABUS_ACCEPTANCE.docx"
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"
with zipfile.ZipFile(p) as z:
    root=etree.fromstring(z.read('word/document.xml'))
body=root.find(w('body'))
paras=body.findall('.//'+w('p'))
for i in range(12,18):
    p=paras[i]
    print('\nPARA',i)
    print('TEXT:', ''.join((t.text or '') for t in p.iter(w('t'))))
    print('XML:')
    print(etree.tostring(p, pretty_print=True, encoding='unicode'))
