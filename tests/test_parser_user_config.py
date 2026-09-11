import os
import pytest
from modules.common.config_manager import config_manager
import modules.parsers.ceit_directory as ceit_dir
from modules.parsers.roster_parser import _is_id_header, _is_name_header
from modules.parsers.schedule_parser import parse_schedule

def test_dynamic_prefix_and_metadata():
    # Save original config
    original_cfg = config_manager.get_config()
    try:
        cfg = config_manager.get_config()
        cfg["ceit_prefix_map"]["BMGT"] = {
            "name": "Business Management",
            "dept": "Department of Management",
            "dept_code": "DOM",
            "icon": "💼",
            "badge": "💼 DOM"
        }
        config_manager.save_config(cfg)

        # ceit_directory should immediately recognize BMGT
        meta = ceit_dir.get_prefix_metadata("BMGT 11 - Principles of Management")
        assert meta is not None
        assert meta["prefix"] == "BMGT"
        assert meta["dept_code"] == "DOM"
        assert meta["badge"] == "💼 DOM"

        # parse_filename_hints should also pick up the prefix
        hints = ceit_dir.parse_filename_hints("BSBM 1-1 BMGT 11.xlsx")
        assert hints["subject_prefix"] == "BMGT"
        assert hints["ceit_metadata"] is not None
        assert hints["ceit_metadata"]["dept_code"] == "DOM"
    finally:
        config_manager.save_config(original_cfg)

def test_dynamic_lab_subject_detection():
    original_cfg = config_manager.get_config()
    try:
        assert ceit_dir.is_known_lab_subject("CHEM 101") is False

        cfg = config_manager.get_config()
        cfg["known_lab_subjects"].append("CHEM 101")
        config_manager.save_config(cfg)

        assert ceit_dir.is_known_lab_subject("CHEM 101") is True
        assert ceit_dir.is_known_lab_subject("CHEM101") is True
    finally:
        config_manager.save_config(original_cfg)

def test_dynamic_program_aliases():
    original_cfg = config_manager.get_config()
    try:
        cfg = config_manager.get_config()
        cfg["program_aliases"]["NURS"] = "BSN"
        config_manager.save_config(cfg)

        hints = ceit_dir.parse_filename_hints("NURS 2-1 NURS 101.xlsx")
        assert hints["course_sec"] == "BSN 2-1"
    finally:
        config_manager.save_config(original_cfg)

def test_dynamic_roster_keywords():
    original_cfg = config_manager.get_config()
    try:
        assert _is_id_header("Learner Ref No") is False
        assert _is_name_header("Pangalan ng Mag-aaral") is False

        cfg = config_manager.get_config()
        cfg["roster_keywords"]["id_tokens"].append("learnerrefno")
        cfg["roster_keywords"]["name_tokens"].append("pangalanngmagaaral")
        config_manager.save_config(cfg)

        assert _is_id_header("Learner Ref No") is True
        assert _is_name_header("Pangalan ng Mag-aaral") is True
    finally:
        config_manager.save_config(original_cfg)
