from lxml import etree
import zipfile
p=r"c:\Users\danjo\OneDrive\CVSU GENERATORS\output\BSCS_1-4\BSCS_1-4_SYLLABUS_ACCEPTANCE.docx"
with zipfile.ZipFile(p) as z:
    xml=z.read('word/document.xml')
root=etree.fromstring(xml)
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
def w(t): return f"{{{W}}}{t}"
paras=root.findall('.//'+w('p'))
for i,p in enumerate(paras[:40]):
    t=''.join([x.text or '' for x in p.iter(w('t'))])
    print(i,repr(t))
