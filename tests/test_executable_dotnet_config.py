"""
Test Suite for .NET Host Application Configuration and Remote Sources Resilience.
Validates that CvSU Gen.exe.config is properly configured, embedded in the PyInstaller
spec, copied by build.bat, and deployed alongside the binary to prevent 0x80131515
RuntimeError exceptions when running from downloaded ZIPs or cloud-synced folders (OneDrive).
"""

import os
import xml.etree.ElementTree as ET
import pytest

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXECUTABLE_DIR = os.path.join(WORKSPACE_DIR, "executable_test")
CONFIG_PATH = os.path.join(EXECUTABLE_DIR, "CvSU Gen.exe.config")
SPEC_PATH = os.path.join(EXECUTABLE_DIR, "CvSU Gen.spec")
BUILD_BAT_PATH = os.path.join(EXECUTABLE_DIR, "build.bat")
MAIN_PY_PATH = os.path.join(EXECUTABLE_DIR, "main.py")
DIST_CONFIG_PATH = os.path.join(EXECUTABLE_DIR, "dist", "CvSU Gen", "CvSU Gen.exe.config")


def test_dotnet_config_file_exists_and_is_valid_xml():
    """Verify that CvSU Gen.exe.config exists and contains well-formed XML."""
    assert os.path.exists(CONFIG_PATH), f"Config file not found at {CONFIG_PATH}"
    tree = ET.parse(CONFIG_PATH)
    root = tree.getroot()
    assert root.tag.lower() == "configuration", f"Root element must be <configuration>, got <{root.tag}>"


def test_dotnet_config_enables_load_from_remote_sources():
    """Verify that <runtime><loadFromRemoteSources enabled='true'/> is configured."""
    tree = ET.parse(CONFIG_PATH)
    root = tree.getroot()
    runtime = root.find("runtime")
    assert runtime is not None, "<configuration> must contain a <runtime> child section"

    load_elem = runtime.find("loadFromRemoteSources")
    assert load_elem is not None, "<runtime> must contain <loadFromRemoteSources>"
    enabled_val = load_elem.attrib.get("enabled", "").lower()
    assert enabled_val in ("true", "1"), f"loadFromRemoteSources must have enabled='true', got '{enabled_val}'"


def test_spec_file_integrates_dotnet_config():
    """Verify that CvSU Gen.spec bundles and copies CvSU Gen.exe.config."""
    assert os.path.exists(SPEC_PATH), f"Spec file not found at {SPEC_PATH}"
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        spec_content = f.read()

    assert "CvSU Gen.exe.config" in spec_content, "CvSU Gen.spec must reference CvSU Gen.exe.config"
    assert "clr_loader" in spec_content, "hiddenimports must include clr_loader"
    assert "pythonnet" in spec_content, "hiddenimports must include pythonnet"


def test_build_bat_integrates_dotnet_config():
    """Verify that build.bat copies CvSU Gen.exe.config to the output directory."""
    assert os.path.exists(BUILD_BAT_PATH), f"build.bat not found at {BUILD_BAT_PATH}"
    with open(BUILD_BAT_PATH, "r", encoding="utf-8") as f:
        bat_content = f.read()

    assert "CvSU Gen.exe.config" in bat_content, "build.bat must copy CvSU Gen.exe.config to distribution bundle"


def test_main_py_resolves_pythonnet_pydll_in_frozen_mode():
    """Verify that main.py defines PYTHONNET_PYDLL fallback when frozen."""
    assert os.path.exists(MAIN_PY_PATH), f"main.py not found at {MAIN_PY_PATH}"
    with open(MAIN_PY_PATH, "r", encoding="utf-8") as f:
        main_content = f.read()

    assert "PYTHONNET_PYDLL" in main_content, "main.py must set PYTHONNET_PYDLL for pythonnet loader"


def test_dist_bundle_has_synchronized_config_if_dist_present():
    """If a compiled dist bundle exists, ensure CvSU Gen.exe.config is placed adjacent to the executable."""
    dist_dir = os.path.join(EXECUTABLE_DIR, "dist", "CvSU Gen")
    if os.path.isdir(dist_dir):
        assert os.path.exists(DIST_CONFIG_PATH), f"Distribution bundle missing {DIST_CONFIG_PATH}"
        with open(CONFIG_PATH, "r", encoding="utf-8") as f1, open(DIST_CONFIG_PATH, "r", encoding="utf-8") as f2:
            assert f1.read() == f2.read(), "Distribution bundle config must match source config exactly"

