import io
import os
import copy
import zipfile
import tempfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"

def w(tag: str) -> str:
    """Returns tag qualified with OpenXML wordprocessingml namespace."""
    return f"{{{W}}}{tag}"

def wt(tag: str) -> str:
    """Returns tag qualified with Word 2010 wordml namespace."""
    return f"{{{W14}}}{tag}"

def get_full_text(el) -> str:
    """Extracts all text content recursively from an element's w:t nodes."""
    return "".join(t.text or "" for t in el.iter(w("t")))

def get_student_name_font_sz(text: str) -> str:
    """
    Dynamic font scaling ladder for student names:
      - <= 30 characters: 8pt (sz="16", matching reference SCHOOL FILES 2026)
      - 31-35 characters: 7pt (sz="14")
      - > 35 characters: 6pt (sz="12")
    """
    length = len(text.strip())
    if length <= 30:
        return "16"  # 8pt
    elif length <= 35:
        return "14"  # 7pt
    else:
        return "12"  # 6pt

def apply_font_size(r_el, sz_val: str):
    """Explicitly sets w:sz and w:szCs on a run's rPr."""
    rpr = r_el.find(w("rPr"))
    if rpr is None:
        rpr = etree.Element(w("rPr"))
        r_el.insert(0, rpr)
    sz = rpr.find(w("sz"))
    if sz is None:
        sz = etree.SubElement(rpr, w("sz"))
    sz.set(w("val"), sz_val)
    sz_cs = rpr.find(w("szCs"))
    if sz_cs is None:
        sz_cs = etree.SubElement(rpr, w("szCs"))
    sz_cs.set(w("val"), sz_val)

def auto_scale_font(r_el, text: str, shrink_threshold: int, sz_val: str):
    """Automatically scales the font size of a run if text length exceeds threshold."""
    if shrink_threshold > 0 and len(text) > shrink_threshold:
        apply_font_size(r_el, sz_val)

def set_run_text(run, text: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """Replaces text in a single run, preserving its rPr and scaling font if needed."""
    for t in run.findall(w("t")):
        run.remove(t)
        
    auto_scale_font(run, text, shrink_threshold, shrink_sz)
        
    t_el = etree.SubElement(run, w("t"))
    t_el.text = text
    if text and (text[0] == " " or text[-1] == " "):
        t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

def replace_after_colon(para, value: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """
    Keeps the label run (up to and including ':'), sets the following run to value,
    and removes all runs in between.
    """
    runs = para.findall(w("r"))
    if not runs:
        return

    full_text = "".join(r.findtext(w("t")) or "" for r in runs)
    colon_pos = full_text.find(":")
    if colon_pos == -1:
        return

    char_count = 0
    colon_run_idx = 0
    char_in_colon_run = 0
    for idx, r in enumerate(runs):
        txt = r.findtext(w("t")) or ""
        if char_count + len(txt) > colon_pos:
            colon_run_idx = idx
            char_in_colon_run = colon_pos - char_count
            break
        char_count += len(txt)

    colon_run = runs[colon_run_idx]
    colon_txt = colon_run.findtext(w("t")) or ""
    label_part = colon_txt[:char_in_colon_run + 1]

    if colon_run_idx == len(runs) - 1:
        t_el = colon_run.find(w("t"))
        t_el.text = label_part
        r_val = etree.SubElement(para, w("r"))
        colon_rpr = colon_run.find(w("rPr"))
        if colon_rpr is not None:
            r_val.insert(0, copy.deepcopy(colon_rpr))
        auto_scale_font(r_val, value, shrink_threshold, shrink_sz)
        t_new = etree.SubElement(r_val, w("t"))
        t_new.text = " " + value
        t_new.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    else:
        t_el = colon_run.find(w("t"))
        t_el.text = label_part
        for r in runs[colon_run_idx + 1:-1]:
            para.remove(r)
        last_run = runs[-1]
        for t in last_run.findall(w("t")):
            last_run.remove(t)
        auto_scale_font(last_run, value, shrink_threshold, shrink_sz)
        t_new = etree.SubElement(last_run, w("t"))
        t_new.text = " " + value
        t_new.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

_auto_scale_font = auto_scale_font

def replace_value_run(para, run_index: int, value: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """
    Keep runs [0..run_index-1] as-is (label), set run[run_index] to value,
    and remove all runs after run_index.
    """
    runs = para.findall(w("r"))
    if not runs:
        return
    run_index = min(run_index, len(runs) - 1)
    for r in runs[run_index + 1:]:
        para.remove(r)
    prefix = "".join(get_full_text(r) for r in runs[:run_index])
    if prefix.rstrip().endswith(":") and value and not value.startswith(" "):
        value = " " + value

    set_run_text(runs[run_index], value, shrink_threshold, shrink_sz)
    ppr = para.find(w("pPr"))
    if ppr is not None:
        ind = ppr.find(w("ind"))
        if ind is not None:
            ppr.remove(ind)

def collapse_runs_after_colon(para, value: str, shrink_threshold: int = 0, shrink_sz: str = "18"):
    """Replaces text after a colon, consolidating runs and fixing paragraph indents."""
    runs = para.findall(w("r"))
    if not runs:
        return

    full = "".join(r.findtext(w("t")) or "" for r in runs)
    colon_pos = full.find(":")
    if colon_pos == -1:
        return

    label_text = full[:colon_pos + 1]
    for r in runs:
        para.remove(r)

    r_lbl = etree.SubElement(para, w("r"))
    t_lbl = etree.SubElement(r_lbl, w("t"))
    t_lbl.text = label_text

    r_val = etree.SubElement(para, w("r"))
    auto_scale_font(r_val, value, shrink_threshold, shrink_sz)
    t_val = etree.SubElement(r_val, w("t"))
    t_val.text = " " + value
    t_val.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

    ppr = para.find(w("ppr"))
    if ppr is not None:
        ind = ppr.find(w("ind"))
        if ind is not None:
            ppr.remove(ind)

def set_cell_text(tc, text: str, remove_num: bool = False, shrink_threshold: int = 0, shrink_sz: str = "18", is_student_name: bool = False):
    """Replaces text in first paragraph of a cell, preserving run formatting, alignment, and applying font scaling."""
    p = tc.find(w("p"))
    if p is None:
        p = etree.SubElement(tc, w("p"))
    ppr = p.find(w("pPr"))
    if ppr is not None:
        if remove_num:
            numpr = ppr.find(w("numPr"))
            if numpr is not None:
                ppr.remove(numpr)
        ind = ppr.find(w("ind"))
        if ind is not None:
            ppr.remove(ind)
        jc = ppr.find(w("jc"))
        if jc is not None and jc.get(w("val")) == "both":
            jc.set(w("val"), "left")
            
    runs = p.findall(w("r"))
    if not runs:
        r = etree.SubElement(p, w("r"))
        ppr_rpr = ppr.find(w("rPr")) if ppr is not None else None
        if ppr_rpr is not None:
            r.append(copy.deepcopy(ppr_rpr))
        if is_student_name:
            apply_font_size(r, get_student_name_font_sz(text))
        else:
            auto_scale_font(r, text, shrink_threshold, shrink_sz)
        t = etree.SubElement(r, w("t"))
        t.text = text
        if text and text[0] == " ":
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        return
        
    first_rpr = runs[0].find(w("rPr"))
    for r in runs:
        p.remove(r)
    r_new = etree.SubElement(p, w("r"))
    if first_rpr is not None:
        r_new.insert(0, copy.deepcopy(first_rpr))
    elif ppr is not None and ppr.find(w("rPr")) is not None:
        r_new.insert(0, copy.deepcopy(ppr.find(w("rPr"))))
        
    if is_student_name:
        apply_font_size(r_new, get_student_name_font_sz(text))
    else:
        auto_scale_font(r_new, text, shrink_threshold, shrink_sz)
        
    t = etree.SubElement(r_new, w("t"))
    t.text = text
    if text and text[0] == " ":
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

def load_docx(path: str):
    """Loads a docx and returns (zin, root, body) with transient lock retry for Windows/OneDrive."""
    import time
    last_err = None
    data = None
    for attempt in range(6):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            break
        except FileNotFoundError:
            raise
        except (PermissionError, OSError) as err:
            last_err = err
            if attempt < 5:
                time.sleep(0.08 * (attempt + 1))
    if data is None:
        raise last_err

    zin = zipfile.ZipFile(io.BytesIO(data))
    safe_parser = etree.XMLParser(resolve_entities=False)
    root = etree.fromstring(zin.read("word/document.xml"), parser=safe_parser)
    body = root.find(w("body"))
    return zin, root, body

def save_docx(zin, root, output_path: str):
    """Serializes root back into a docx zip using atomic file writing."""
    new_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    buf = io.BytesIO()
    zout = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        zout.writestr(item, new_xml if item.filename == "word/document.xml" else zin.read(item.filename))
    zout.close()
    zin.close()
    
    dir_name = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(dir_name, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dir_name, delete=False, suffix=".tmp") as fh:
        fh.write(buf.getvalue())
        tmp_name = fh.name
        
    for attempt in range(5):
        try:
            os.replace(tmp_name, output_path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)
    else:
        try:
            os.remove(tmp_name)
        except Exception:
            pass
        raise PermissionError(f"Could not overwrite {output_path} (file is likely locked by another process).")
