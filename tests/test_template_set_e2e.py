#!/usr/bin/env python3
"""
tests/test_template_set_e2e.py

Real End-to-End Generation Test for the User Template Set Subsystem:
  - Takes an actual template and visibly customizes it (adding an identifiable college title marker).
  - Activates the custom template set.
  - Executes real generation via GeneratorFactory and SyllabusGenerator.
  - Verifies that generated output physically contains the custom marker and student data.
  - Deactivates the custom set and switches back to built-in default CvSU templates.
  - Executes generation again and verifies the generated output reverts to the built-in CvSU template.
  - Confirms zero generator source code modifications were required to replace the template set.
"""

import os
import pytest

from modules.common.docx_utils import load_docx, save_docx, get_full_text, set_run_text, w
from modules.models.schedule import ClassInfo
from modules.models.template_set import (
    ROLE_SYLLABUS,
    CANONICAL_ROLES,
)
from modules.services.template_set_manager import (
    TemplateSetManager,
    BUILTIN_SET_ID,
)
from modules.generators.ceit_gen import GeneratorFactory


CUSTOM_MARKER = "[CUSTOM_INSTITUTION_INNOVATIVE_COMPUTING_2026]"


@pytest.fixture
def project_templates_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))


@pytest.fixture
def sample_class_info():
    return ClassInfo(
        instructor="PROF. DAN JOSEPH ORTEGA",
        course_section="BSCS 3-1",
        schedule_code="202611223",
        subject="COSC 101 - ADVANCED SYSTEMS ARCHITECTURE",
        time_days_room="08:00AM-11:00AM / TF / ITC 301",
        semester_ay="1ST Semester / 2026-2027",
        students=[
            ("DELA CRUZ, JUAN A.", "202610001"),
            ("SANTOS, MARIA B.", "202610002"),
        ],
    )


def test_real_generation_custom_template_set_e2e(tmp_path, project_templates_dir, sample_class_info, monkeypatch):
    # 1. Prepare isolated TemplateSetManager
    mgr = TemplateSetManager(base_dir=str(tmp_path / "appdata"))
    monkeypatch.setattr(TemplateSetManager, "get_instance", lambda: mgr)

    # 2. Create physically modified custom template
    orig_syl = os.path.join(project_templates_dir, "template_syllabus.docx")
    zin, root, body = load_docx(orig_syl)

    modified_paragraph = False
    for p in body.findall(w("p")):
        txt = get_full_text(p)
        if "COLLEGE OF ENGINEERING" in txt:
            # Modify run text to insert custom marker
            runs = p.findall(w("r"))
            if runs:
                set_run_text(runs[0], f"COLLEGE OF INNOVATIVE COMPUTING {CUSTOM_MARKER}")
                modified_paragraph = True
                break

    assert modified_paragraph, "Failed to modify college title in template"

    custom_template_path = str(tmp_path / "custom_syllabus_modified.docx")
    save_docx(zin, root, custom_template_path)
    assert os.path.exists(custom_template_path)

    # 3. Create user template set and add custom template
    user_set = mgr.create_template_set("Institution Alpha", fallback_to_default=True)
    mgr.add_template_to_set(user_set.set_id, ROLE_SYLLABUS, custom_template_path)

    # 4. Activate custom set
    mgr.activate_template_set(user_set.set_id)
    assert mgr.get_active_template_set_id() == user_set.set_id

    # 5. Resolve generator through GeneratorFactory
    factory = GeneratorFactory(project_templates_dir)
    gens = factory.get_all(include_custom=False)
    # Syllabus is index 0
    syl_gen_custom = gens[0][0]()

    # Verify physical path is inside the custom template set
    assert "institution_alpha" in syl_gen_custom.template_path

    # 6. Run REAL generation with custom set
    out_custom_doc = str(tmp_path / "Generated_Custom_Syllabus.docx")
    syl_gen_custom.generate(sample_class_info, out_custom_doc)
    assert os.path.exists(out_custom_doc)

    # 7. Inspect generated document: CUSTOM MARKER must be present!
    zin_out, _, body_out = load_docx(out_custom_doc)
    zin_out.close()
    generated_text = " ".join(get_full_text(p) for p in body_out.findall(w("p")))
    assert CUSTOM_MARKER in generated_text
    assert "COLLEGE OF INNOVATIVE COMPUTING" in generated_text

    # Verify student data was filled in custom template output
    table_text = " ".join(get_full_text(tc) for tbl in body_out.findall(w("tbl")) for tc in tbl.findall(".//" + w("tc")))
    assert "DELA CRUZ, JUAN A." in table_text
    assert "202610001" in table_text

    # 8. Deactivate custom set -> Revert to built-in default CvSU templates
    mgr.activate_template_set(BUILTIN_SET_ID)
    assert mgr.get_active_template_set_id() == BUILTIN_SET_ID

    # 9. Resolve generator again through GeneratorFactory
    factory_builtin = GeneratorFactory(project_templates_dir)
    gens_builtin = factory_builtin.get_all(include_custom=False)
    syl_gen_builtin = gens_builtin[0][0]()

    # Verify physical path is the built-in template
    assert "institution_alpha" not in syl_gen_builtin.template_path
    assert "template_syllabus.docx" in syl_gen_builtin.template_path

    # 10. Run REAL generation with built-in set
    out_builtin_doc = str(tmp_path / "Generated_Builtin_Syllabus.docx")
    syl_gen_builtin.generate(sample_class_info, out_builtin_doc)
    assert os.path.exists(out_builtin_doc)

    # 11. Inspect built-in generated document: CUSTOM MARKER must NOT be present!
    zin_b, _, body_b = load_docx(out_builtin_doc)
    zin_b.close()
    builtin_text = " ".join(get_full_text(p) for p in body_b.findall(w("p")))
    assert CUSTOM_MARKER not in builtin_text
    assert "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY" in builtin_text
