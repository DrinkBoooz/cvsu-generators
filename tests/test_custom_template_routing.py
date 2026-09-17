#!/usr/bin/env python3
"""
tests/test_custom_template_routing.py

Unit and integration tests for custom template output folder routing:
- Safe relative path validation (traversal, absolute, drive letters, reserved names, dot/space endings)
- Recipe validator metadata preservation of output_folder
- DocumentGenerator and ConfigurableDocumentGenerator output_folder property
- ConfigManager template saving with single source of truth in recipe.metadata
- Orchestrator dynamic routing to custom folders
- Backward compatibility for legacy templates without output_folder
"""

import os
import pytest
from modules.common.path_utils import validate_output_folder
from modules.models.recipe import ValidatedTemplateRecipe, PROFILE_CUSTOM_DOCX
from modules.parsers.recipe_validator import RecipeValidator
from modules.parsers.template_inspector import TemplateInspector
from modules.generators.generic_doc_gen import ConfigurableDocumentGenerator
from modules.generators.ceit_gen import DocumentGenerator, SyllabusGenerator
from modules.common.config_manager import ParserConfigManager
from modules.models.schedule import ClassInfo

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")


# ── Path Validation Tests ───────────────────────────────────────────────────

def test_validate_output_folder_defaults():
    assert validate_output_folder(None) == "CEIT_Forms"
    assert validate_output_folder("") == "CEIT_Forms"
    assert validate_output_folder("   ") == "CEIT_Forms"
    assert validate_output_folder(None, default="Attendance") == "Attendance"


def test_validate_output_folder_valid_paths():
    assert validate_output_folder("CEIT_Forms") == "CEIT_Forms"
    assert validate_output_folder("Attendance") == "Attendance"
    assert validate_output_folder("Custom_Folder") == "Custom_Folder"
    # Nested relative subfolders
    expected_nested = os.path.normpath("Advising/Logs")
    assert validate_output_folder("Advising/Logs") == expected_nested
    assert validate_output_folder("Advising\\Logs") == expected_nested


def test_validate_output_folder_rejects_absolute_and_drive():
    with pytest.raises(ValueError, match="Drive-qualified"):
        validate_output_folder("C:/evil")
    with pytest.raises(ValueError, match="Drive-qualified"):
        validate_output_folder("D:\\evil")
    with pytest.raises(ValueError, match="Drive-qualified"):
        validate_output_folder("C:evil")
    with pytest.raises(ValueError, match="Absolute"):
        validate_output_folder("/etc/passwd")
    with pytest.raises(ValueError, match="Absolute"):
        validate_output_folder("\\windows\\system32")


def test_validate_output_folder_rejects_traversal():
    with pytest.raises(ValueError, match="Path traversal"):
        validate_output_folder("..")
    with pytest.raises(ValueError, match="Path traversal"):
        validate_output_folder(".")
    with pytest.raises(ValueError, match="Path traversal"):
        validate_output_folder("../evil")
    with pytest.raises(ValueError, match="Path traversal"):
        validate_output_folder("sub/../../evil")
    with pytest.raises(ValueError, match="Path traversal"):
        validate_output_folder("sub/./evil")


def test_validate_output_folder_rejects_invalid_chars():
    for char in ('<', '>', ':', '"', '|', '?', '*'):
        with pytest.raises(ValueError, match="Invalid path characters"):
            validate_output_folder(f"folder{char}name")


def test_validate_output_folder_rejects_reserved_windows_names():
    for name in ("CON", "con", "prn", "AUX", "nul", "COM1", "LPT9"):
        with pytest.raises(ValueError, match="Reserved Windows device name"):
            validate_output_folder(name)
        with pytest.raises(ValueError, match="Reserved Windows device name"):
            validate_output_folder(f"sub/{name}")


def test_validate_output_folder_rejects_dots_and_spaces_at_segment_end():
    with pytest.raises(ValueError, match="cannot end with a dot or space"):
        validate_output_folder("folder.")
    with pytest.raises(ValueError, match="cannot end with a dot or space"):
        validate_output_folder("sub/folder ")
    with pytest.raises(ValueError, match="cannot end with a dot or space"):
        validate_output_folder("sub/folder...")


def test_validate_output_folder_rejects_non_string():
    with pytest.raises(TypeError, match="must be a string"):
        validate_output_folder(12345)


# ── Recipe Metadata & Generator Property Tests ──────────────────────────────

def test_recipe_validator_preserves_output_folder():
    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    inspector = TemplateInspector()
    recipe_dict = inspector.inspect_docx(source_template)

    # 1. Default when missing
    validated = RecipeValidator.validate_dict(recipe_dict, PROFILE_CUSTOM_DOCX)
    assert validated.metadata.get("output_folder") == "CEIT_Forms"

    # 2. Configured output_folder in metadata
    recipe_dict["metadata"] = {"output_folder": "Attendance", "title": "Test", "suffix": "TEST"}
    validated2 = RecipeValidator.validate_dict(recipe_dict, PROFILE_CUSTOM_DOCX)
    assert validated2.metadata["output_folder"] == "Attendance"

    # 3. Serialization to_dict() preserves it
    serialized = validated2.to_dict()
    assert serialized["metadata"]["output_folder"] == "Attendance"

    # 4. Deserialization from dictionary
    validated3 = RecipeValidator.validate_dict(serialized, PROFILE_CUSTOM_DOCX)
    assert validated3.metadata["output_folder"] == "Attendance"


def test_document_generator_output_folder_property():
    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    inspector = TemplateInspector()
    recipe_dict = inspector.inspect_docx(source_template)

    # Native syllabus generator defaults to CEIT_Forms
    recipe_dict["metadata"] = {"output_folder": "CEIT_Forms"}
    validated = RecipeValidator.validate_dict(recipe_dict, PROFILE_CUSTOM_DOCX)
    gen_default = ConfigurableDocumentGenerator(source_template, validated)
    assert gen_default.output_folder == "CEIT_Forms"

    # Custom generator with Attendance
    recipe_dict["metadata"] = {"output_folder": "Attendance"}
    validated_att = RecipeValidator.validate_dict(recipe_dict, PROFILE_CUSTOM_DOCX)
    gen_att = ConfigurableDocumentGenerator(source_template, validated_att)
    assert gen_att.output_folder == "Attendance"


# ── ConfigManager Single Source of Truth Tests ──────────────────────────────

def test_config_manager_output_folder_single_source_of_truth(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path / "config"))
    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    recipe = TemplateInspector().inspect_docx(source_template)
    recipe["metadata"] = {"output_folder": "Attendance"}

    res = mgr.save_custom_template(
        source_path=source_template,
        title="Custom Attendance Log",
        suffix="CUSTOM_ATTENDANCE_LOG",
        recipe=recipe,
        enabled=True,
    )
    assert res["status"] == "success"

    templates = mgr.get_custom_templates()
    assert len(templates) == 1
    t = templates[0]

    # Sole source of truth is recipe.metadata["output_folder"]
    assert t["recipe"]["metadata"]["output_folder"] == "Attendance"
    # No duplicate top-level keys
    assert "output_folder" not in t


def test_custom_template_generator_properties_and_resolution(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path / "config"))
    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    inspector = TemplateInspector()

    # 1. Custom template routing to Attendance
    recipe_att = inspector.inspect_docx(source_template)
    recipe_att["metadata"] = {"output_folder": "Attendance"}
    mgr.save_custom_template(
        source_path=source_template,
        title="Custom Attendance",
        suffix="CUSTOM_ATTENDANCE",
        recipe=recipe_att,
        enabled=True,
    )

    # 2. Custom template routing to nested subfolder Advising/Logs
    recipe_adv = inspector.inspect_docx(source_template)
    recipe_adv["metadata"] = {"output_folder": "Advising/Logs"}
    mgr.save_custom_template(
        source_path=source_template,
        title="Custom Advising",
        suffix="CUSTOM_ADVISING",
        recipe=recipe_adv,
        enabled=True,
    )

    # 3. Custom template with no output_folder (defaults to CEIT_Forms)
    recipe_def = inspector.inspect_docx(source_template)
    recipe_def["metadata"] = {}
    mgr.save_custom_template(
        source_path=source_template,
        title="Custom Default",
        suffix="CUSTOM_DEFAULT",
        recipe=recipe_def,
        enabled=True,
    )

    from modules.generators.ceit_gen import GeneratorFactory
    factory = GeneratorFactory(TEMPLATES_DIR, config_manager=mgr)
    all_gens = factory.get_all(include_custom=True)

    custom_pairs = [
        (gen_factory(), suffix) for gen_factory, suffix in all_gens
        if suffix in ("CUSTOM_ATTENDANCE", "CUSTOM_ADVISING", "CUSTOM_DEFAULT")
    ]
    assert len(custom_pairs) == 3

    gens_by_suffix = {suffix: gen for gen, suffix in custom_pairs}
    assert gens_by_suffix["CUSTOM_ATTENDANCE"].output_folder == "Attendance"
    assert gens_by_suffix["CUSTOM_ADVISING"].output_folder == os.path.normpath("Advising/Logs")
    assert gens_by_suffix["CUSTOM_DEFAULT"].output_folder == "CEIT_Forms"


def test_orchestrator_custom_template_routing(monkeypatch, tmp_path):
    import sys
    from modules.services.orchestrator import process_all

    mgr = ParserConfigManager(config_dir=str(tmp_path / "config"))
    monkeypatch.setattr(sys.modules["modules.common.config_manager"], "config_manager", mgr)

    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    inspector = TemplateInspector()

    # 1. Custom template routing to Attendance
    recipe_att = inspector.inspect_docx(source_template)
    recipe_att["metadata"] = {"output_folder": "Attendance"}
    mgr.save_custom_template(
        source_path=source_template,
        title="Custom Attendance",
        suffix="CUSTOM_ATTENDANCE",
        recipe=recipe_att,
        enabled=True,
    )

    # 2. Custom template routing to nested subfolder Advising/Logs
    recipe_adv = inspector.inspect_docx(source_template)
    recipe_adv["metadata"] = {"output_folder": "Advising/Logs"}
    mgr.save_custom_template(
        source_path=source_template,
        title="Custom Advising",
        suffix="CUSTOM_ADVISING",
        recipe=recipe_adv,
        enabled=True,
    )

    # 3. Custom template with no output_folder (defaults to CEIT_Forms)
    recipe_def = inspector.inspect_docx(source_template)
    recipe_def["metadata"] = {}
    mgr.save_custom_template(
        source_path=source_template,
        title="Custom Default",
        suffix="CUSTOM_DEFAULT",
        recipe=recipe_def,
        enabled=True,
    )

    schedule_path = os.path.join(REPO_ROOT, "ORTEGA_SCHEDULE.xls")
    assert os.path.isfile(schedule_path)

    roster_file = tmp_path / "BSCS1-4 List of Students for 202612040-DCIT 21A - INTRODUCTION TO COMPUTING.csv"
    roster_file.write_text("Name,Student number\nOrtega, Dan,20261001\n", encoding="utf-8")

    out_dir = tmp_path / "output"
    out_dir.mkdir()

    results = process_all(
        schedule_path=schedule_path,
        xlsx_files=[str(roster_file)],
        output_dir_base=str(out_dir),
        class_filter=["202612040_CS1-4"],
        engine_filter=["ceit"],
    )

    assert results["errors"]["ceit"] == []
    course_dir = os.path.join(str(out_dir), "CS1-4")

    # 1. Verify custom template with metadata.output_folder = "Attendance" produces file in <Course>/Attendance/
    att_file = os.path.join(course_dir, "Attendance", "CS1-4_202612040_CUSTOM_ATTENDANCE.docx")
    assert os.path.isfile(att_file), f"Expected attendance file at {att_file}"

    # 2. Verify nested Advising/Logs produces the nested path
    nested_adv_file = os.path.join(course_dir, os.path.normpath("Advising/Logs"), "CS1-4_202612040_CUSTOM_ADVISING.docx")
    assert os.path.isfile(nested_adv_file), f"Expected nested file at {nested_adv_file}"

    # 3. Verify missing output_folder defaults to <Course>/CEIT_Forms/
    def_file = os.path.join(course_dir, "CEIT_Forms", "CS1-4_202612040_CUSTOM_DEFAULT.docx")
    assert os.path.isfile(def_file), f"Expected default file at {def_file}"

    # 4. Verify native CEIT behavior remains unchanged (files generated in <Course>/CEIT_Forms/)
    native_syllabus = os.path.join(course_dir, "CEIT_Forms", "CS1-4_202612040_SYLLABUS_ACCEPTANCE.docx")
    native_tos = os.path.join(course_dir, "CEIT_Forms", "CS1-4_202612040_TOS_MIDTERM.docx")
    native_exam = os.path.join(course_dir, "CEIT_Forms", "CS1-4_202612040_EXAM_RETURNS_MIDTERM.docx")
    native_grade = os.path.join(course_dir, "CEIT_Forms", "CS1-4_202612040_GRADE_DISCUSSION_MIDTERM.docx")

    assert os.path.isfile(native_syllabus), f"Expected native syllabus at {native_syllabus}"
    assert os.path.isfile(native_tos), f"Expected native TOS at {native_tos}"
    assert os.path.isfile(native_exam), f"Expected native exam returns at {native_exam}"
    assert os.path.isfile(native_grade), f"Expected native grade discussion at {native_grade}"
