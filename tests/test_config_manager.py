import os
import json
import pytest
from modules.common.config_manager import ParserConfigManager, get_default_config_dict

def test_config_manager_defaults(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path))
    cfg = mgr.get_config()

    assert cfg["version"] == "1.0"
    assert "COSC" in cfg["ceit_prefix_map"]
    assert "DCIT 21" in cfg["known_lab_subjects"]
    assert "CS" in cfg["program_aliases"]
    assert "name" in cfg["roster_keywords"]["name_tokens"]
    assert "studentnumber" in cfg["roster_keywords"]["id_tokens"]
    assert mgr.is_lab_subject("DCIT 21") is True
    assert mgr.is_lab_subject("GNED 01") is False

def test_config_manager_save_and_reload(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path))
    cfg = mgr.get_config()

    # Add custom prefix CRIM (Criminology)
    cfg["ceit_prefix_map"]["CRIM"] = {
        "name": "Criminology",
        "dept": "Department of Criminology",
        "dept_code": "DCRIM",
        "icon": "🛡️",
        "badge": "🛡️ DCRIM"
    }
    # Add custom lab course
    cfg["known_lab_subjects"].append("CHEM 101")
    # Add custom program alias
    cfg["program_aliases"]["CRIM"] = "BSCRIM"
    # Add custom roster keyword
    cfg["roster_keywords"]["id_tokens"].append("lrn_cvsu")

    res = mgr.save_config(cfg)
    assert res["status"] == "success"

    # Verify file persisted on disk
    assert os.path.exists(mgr.config_file)

    # Create new manager pointing to same directory
    mgr2 = ParserConfigManager(config_dir=str(tmp_path))
    meta = mgr2.get_prefix_metadata("CRIM 101")
    assert meta is not None
    assert meta["prefix"] == "CRIM"
    assert meta["dept_code"] == "DCRIM"
    assert mgr2.is_lab_subject("CHEM 101") is True
    assert "CRIM" in mgr2.get_subject_prefixes()
    assert "lrn_cvsu" in mgr2.get_roster_keywords()["id_tokens"]
    assert mgr2.get_program_aliases().get("CRIM") == "BSCRIM"

def test_config_manager_reset_to_defaults(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path))
    cfg = mgr.get_config()
    cfg["ceit_prefix_map"]["CUSTOM"] = {
        "name": "Custom",
        "dept": "Custom Dept",
        "dept_code": "CD",
        "icon": "⭐",
        "badge": "⭐ CD"
    }
    mgr.save_config(cfg)
    assert "CUSTOM" in mgr.get_ceit_prefix_map()

    reset_res = mgr.reset_to_defaults()
    assert reset_res["status"] == "success"
    assert "CUSTOM" not in mgr.get_ceit_prefix_map()
    assert "COSC" in mgr.get_ceit_prefix_map()
    assert not os.path.exists(mgr.config_file)

def test_config_manager_export_and_import(tmp_path):
    mgr = ParserConfigManager(config_dir=str(tmp_path / "cfg1"))
    cfg = mgr.get_config()
    cfg["ceit_prefix_map"]["NURS"] = {
        "name": "Nursing",
        "dept": "College of Nursing",
        "dept_code": "CON",
        "icon": "🏥",
        "badge": "🏥 CON"
    }
    mgr.save_config(cfg)

    export_path = str(tmp_path / "exported_config.json")
    exp_res = mgr.export_config(export_path)
    assert exp_res["status"] == "success"
    assert os.path.exists(export_path)

    mgr2 = ParserConfigManager(config_dir=str(tmp_path / "cfg2"))
    assert "NURS" not in mgr2.get_ceit_prefix_map()

    imp_res = mgr2.import_config(export_path)
    assert imp_res["status"] == "success"
    assert "NURS" in mgr2.get_ceit_prefix_map()
    meta = mgr2.get_prefix_metadata("NURS 101")
    assert meta["dept_code"] == "CON"
