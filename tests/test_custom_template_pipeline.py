import os
import shutil
import pytest
from modules.common.config_manager import ParserConfigManager
from modules.parsers.template_inspector import TemplateInspector
from modules.generators.ceit_gen import GeneratorFactory
from executable_test.main import ScriptAPI

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(REPO_ROOT, "templates")


@pytest.fixture
def custom_cfg_mgr(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path / "config"))
    return mgr


def test_custom_template_crud(custom_cfg_mgr, tmp_path):
    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")
    assert os.path.exists(source_template)

    inspector = TemplateInspector()
    recipe = inspector.inspect_docx(source_template)

    # 1. Save
    res = custom_cfg_mgr.save_custom_template(
        source_path=source_template,
        title="Custom Consultation Log",
        suffix="CONSULTATION_LOG",
        recipe=recipe,
        enabled=True,
    )
    assert res["status"] == "success"
    assert res["template"]["id"] == "consultation_log"
    assert res["template"]["suffix"] == "CONSULTATION_LOG"

    # 2. Get
    templates = custom_cfg_mgr.get_custom_templates()
    assert len(templates) == 1
    assert templates[0]["id"] == "consultation_log"
    assert os.path.exists(templates[0]["file_path"])

    # 3. Toggle
    toggle_res = custom_cfg_mgr.toggle_custom_template("consultation_log", False)
    assert toggle_res["status"] == "success"
    templates = custom_cfg_mgr.get_custom_templates()
    assert templates[0]["enabled"] is False

    # 4. Delete
    del_res = custom_cfg_mgr.delete_custom_template("consultation_log")
    assert del_res["status"] == "success"
    templates = custom_cfg_mgr.get_custom_templates()
    assert len(templates) == 0


def test_generator_factory_includes_custom_templates(monkeypatch, tmp_path):
    import sys
    test_mgr = ParserConfigManager(config_dir=str(tmp_path / "config"))
    monkeypatch.setattr(sys.modules["modules.common.config_manager"], "config_manager", test_mgr)

    factory = GeneratorFactory(TEMPLATES_DIR)
    # Default built-in
    gens_initial = factory.get_all()
    assert len(gens_initial) == 7

    # Register custom template
    source_template = os.path.join(TEMPLATES_DIR, "template_tos_midterm.docx")
    recipe = TemplateInspector().inspect_docx(source_template)
    test_mgr.save_custom_template(
        source_path=source_template,
        title="Test Custom Form",
        suffix="CUSTOM_TEST_FORM",
        recipe=recipe,
        enabled=True,
    )

    # Generator factory should now return 8 generators
    gens_updated = factory.get_all()
    assert len(gens_updated) == 8
    suffixes = [s for _, s in gens_updated]
    assert "CUSTOM_TEST_FORM" in suffixes

    # When disabled, returns back to 7
    test_mgr.toggle_custom_template("custom_test_form", False)
    gens_disabled = factory.get_all()
    assert len(gens_disabled) == 7


def test_script_api_custom_template_endpoints(monkeypatch, tmp_path):
    import sys

    test_mgr = ParserConfigManager(config_dir=str(tmp_path / "config"))
    monkeypatch.setattr(sys.modules["modules.common.config_manager"], "config_manager", test_mgr)

    api = ScriptAPI()
    source_template = os.path.join(TEMPLATES_DIR, "template_syllabus.docx")

    # 1. inspect_custom_template
    inspect_res = api.inspect_custom_template(source_template)
    assert inspect_res["status"] == "success"
    assert "recipe" in inspect_res

    # 2. save_custom_template
    save_res = api.save_custom_template(
        source_template, "API Form", "API_FORM", inspect_res["recipe"]
    )
    assert save_res["status"] == "success"

    # 3. get_custom_templates
    templates = api.get_custom_templates()
    assert len(templates) == 1
    assert templates[0]["suffix"] == "API_FORM"

    # 4. toggle_custom_template
    toggle_res = api.toggle_custom_template("api_form", False)
    assert toggle_res["status"] == "success"

    # 5. delete_custom_template
    delete_res = api.delete_custom_template("api_form")
    assert delete_res["status"] == "success"
    assert len(api.get_custom_templates()) == 0
