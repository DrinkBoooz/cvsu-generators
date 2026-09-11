import os
import glob
import pytest
from modules.parsers.template_inspector import TemplateInspector

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")


def test_template_inspector_detects_all_ceit_templates():
    inspector = TemplateInspector()
    docx_files = glob.glob(os.path.join(TEMPLATES_DIR, "*.docx"))
    assert len(docx_files) >= 7, f"Expected at least 7 templates, found {len(docx_files)}"

    for t_path in docx_files:
        recipe = inspector.inspect_docx(t_path)
        assert recipe["confidence"] >= 90, f"Low confidence {recipe['confidence']}% for {t_path}"
        assert recipe["summary"]["roster_table_found"] is True
        assert recipe["roster_table"] is not None
        assert recipe["roster_table"]["name_col"] is not None
        assert recipe["roster_table"]["total_cols"] >= 3

        # Must have detected core metadata fields
        detected = recipe["summary"]["detected_fields"]
        assert "instructor" in detected, f"Instructor missing in {t_path}"
        assert "course_section" in detected, f"Course section missing in {t_path}"
        assert "subject" in detected, f"Subject missing in {t_path}"
        assert "schedule_code" in detected, f"Schedule code missing in {t_path}"


def test_template_inspector_syllabus_columns():
    inspector = TemplateInspector()
    syllabus_path = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    assert os.path.exists(syllabus_path)

    recipe = inspector.inspect_docx(syllabus_path)
    roster = recipe["roster_table"]
    # Syllabus has No. (0), Name (1), ID (2), Signature (3)
    assert roster["index_col"] == 0
    assert roster["name_col"] == 1
    assert roster["id_col"] == 2
    assert roster["signature_col"] == 3
    assert roster["total_cols"] == 4


def test_template_inspector_exam_columns():
    inspector = TemplateInspector()
    exam_path = os.path.join(TEMPLATES_DIR, "template_exam_midterm.docx")
    assert os.path.exists(exam_path)

    recipe = inspector.inspect_docx(exam_path)
    roster = recipe["roster_table"]
    # Exam returns has Name (0), ID (1), Signature (2)
    assert roster["name_col"] == 0
    assert roster["id_col"] == 1
    assert roster["signature_col"] == 2
    assert roster["total_cols"] == 3


def test_template_inspector_file_not_found():
    inspector = TemplateInspector()
    with pytest.raises(FileNotFoundError):
        inspector.inspect_docx("non_existent_template.docx")
