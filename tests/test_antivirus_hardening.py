"""
Automated regression tests for antivirus / VirusTotal false-positive hardening.
Validates:
- Safe literal parsing (_parse_eval_String) avoiding eval()
- Frozen and dev path resolution in BaseAPI
- reveal_in_explorer implementation avoiding subprocess
- PyInstaller spec onedir + upx=False configuration
- Inno Setup installer.iss structure and directives
- PE version metadata in version_info.txt
"""

import os
import sys
import pytest
from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTABLE_DIR = os.path.join(WORKSPACE_DIR, "executable_test")


def test_parse_eval_string_safe_parsing():
    """Verify that _parse_eval_String safely parses literals and blocks arbitrary code execution."""
    from dev.webview_app import _parse_eval_String as dev_parse
    from executable_test.webview_app import _parse_eval_String as app_parse

    for fn in (dev_parse, app_parse):
        # Valid literals
        assert fn("123") == 123
        assert fn("'hello'") == "hello"
        assert fn("[1, 2, 3]") == [1, 2, 3]
        assert fn("{'key': 'value'}") == {"key": "value"}
        assert fn("True") is True
        assert fn("None") is None

        # Arbitrary code execution attempts must raise ValueError
        with pytest.raises(ValueError):
            fn("__import__('os').system('dir')")

        with pytest.raises(ValueError):
            fn("lambda x: x * 2")

        with pytest.raises(ValueError):
            fn("1 + 1")  # BinOp is rejected by literal_eval

        # Non-string input must raise ValueError
        with pytest.raises(ValueError):
            fn(12345)


def test_base_api_onedir_resolution():
    """Verify that BaseAPI properly sets base_dir in dev and frozen modes."""
    from executable_test.api.base import BaseAPI

    api = BaseAPI()
    assert os.path.exists(api.base_dir)
    assert hasattr(api, "_get_gen_module")

    # Module loader returns valid generator in dev mode
    mod = api._get_gen_module("ceit_gen")
    assert mod is not None


def test_reveal_in_explorer_no_subprocess():
    """Verify reveal_in_explorer in SystemMixin works without importing subprocess."""
    from executable_test.api.system import SystemMixin

    mixin = SystemMixin()
    assert hasattr(mixin, "reveal_in_explorer")

    # Verify subprocess is not imported in system.py
    import executable_test.api.system as sys_mod
    assert "subprocess" not in dir(sys_mod)

    # Calling with nonexistent file returns graceful error
    res = mixin.reveal_in_explorer("C:\\nonexistent_folder_xyz_12345")
    assert res["status"] == "error"
    assert "exist" in res["message"].lower()

    # Calling with empty file path returns graceful error
    res_empty = mixin.reveal_in_explorer("")
    assert res_empty["status"] == "error"


def test_spec_onedir_and_upx_disabled():
    """Verify that CvSU Gen.spec is configured for clean --onedir distribution without UPX."""
    spec_path = os.path.join(EXECUTABLE_DIR, "CvSU Gen.spec")
    assert os.path.exists(spec_path)

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_text = f.read()

    assert "exclude_binaries=True" in spec_text
    assert "upx=False" in spec_text
    assert "COLLECT(" in spec_text
    assert "version='version_info.txt'" in spec_text
    for mod in ["'ceit_generator'", "'attendancegen'", "'grading_generator'", "'generic_doc_generator'"]:
        assert mod in spec_text


def test_inno_setup_script_structure():
    """Verify Inno Setup installer.iss script syntax, app metadata, and low privilege settings."""
    iss_path = os.path.join(EXECUTABLE_DIR, "installer.iss")
    assert os.path.exists(iss_path)

    with open(iss_path, "r", encoding="utf-8") as f:
        iss_text = f.read()

    assert 'MyAppName "CvSU Document Generator"' in iss_text
    assert 'MyAppPublisher "Cavite State University - CEIT"' in iss_text
    assert "PrivilegesRequired=lowest" in iss_text
    assert r'Source: "dist\CvSU Gen\*"' in iss_text
    assert "OutputBaseFilename=CvSU_Gen_Setup_v" in iss_text
    assert "Compression=lzma2/ultra64" in iss_text


def test_version_info_metadata_structure():
    """Verify that version_info.txt is valid and parses successfully."""
    vinfo_path = os.path.join(EXECUTABLE_DIR, "version_info.txt")
    assert os.path.exists(vinfo_path)

    vi = load_version_info_from_text_file(vinfo_path)
    assert vi is not None

    string_table = vi.kids[0].kids[0]
    metadata = {item.name: item.val for item in string_table.kids}

    assert metadata["CompanyName"] == "Cavite State University - CEIT"
    assert metadata["FileDescription"] == "CvSU Document Generator Desktop Application"
    assert metadata["FileVersion"] == "1.1.0.0"
    assert metadata["InternalName"] == "CvSU Gen"
    assert metadata["LegalCopyright"] == "Copyright (c) 2026 Dan Joseph Ortega - Cavite State University"
    assert metadata["OriginalFilename"] == "CvSU Gen.exe"
    assert metadata["ProductName"] == "CvSU Document Generator"
    assert metadata["ProductVersion"] == "1.1.0.0"

