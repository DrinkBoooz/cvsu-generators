import os
import ast
import json
import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_EXEC_DIR = os.path.join(WORKSPACE_ROOT, "executable_test")
PROD_EXEC_DIR = os.path.join(WORKSPACE_ROOT, "executable")

def test_production_executable_remains_untouched():
    """Ensure production executable files remain present and untouched."""
    prod_ui = os.path.join(PROD_EXEC_DIR, "ui.html")
    prod_main = os.path.join(PROD_EXEC_DIR, "main.py")
    assert os.path.exists(prod_ui), "Production executable/ui.html must exist"
    assert os.path.exists(prod_main), "Production executable/main.py must exist"
    
    with open(prod_ui, "r", encoding="utf-8") as f:
        content = f.read()
        assert "CvSU Document Generator" in content
        assert "badge-version" in content

def test_react_executable_package_manifest():
    """Verify executable_test package.json structure and dependencies."""
    pkg_path = os.path.join(TEST_EXEC_DIR, "package.json")
    assert os.path.exists(pkg_path), "executable_test/package.json must exist"
    with open(pkg_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    assert pkg.get("name") == "executable_test"
    deps = pkg.get("dependencies", {})
    assert "react" in deps
    assert "react-dom" in deps
    assert "lucide-react" in deps
    assert "tailwindcss" in deps

def test_react_executable_dist_bundle():
    """Verify the React + Vite build artifact exists and has proper asset links."""
    dist_html = os.path.join(TEST_EXEC_DIR, "dist", "index.html")
    assert os.path.exists(dist_html), "executable_test/dist/index.html must exist from build"
    with open(dist_html, "r", encoding="utf-8") as f:
        html = f.read()
    assert "CvSU Document Generator" in html
    assert "./assets/" in html, "Assets must use relative path ./assets/ for desktop PyWebView compatibility"

def test_executable_test_main_py_bridge():
    """Verify executable_test/main.py contains valid Python AST and utilizes ScriptAPI."""
    main_py_path = os.path.join(TEST_EXEC_DIR, "main.py")
    assert os.path.exists(main_py_path), "executable_test/main.py must exist"
    with open(main_py_path, "r", encoding="utf-8") as f:
        code = f.read()
    tree = ast.parse(code)
    
    # Imports ScriptAPI from executable.main
    imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append((node.module, alias.name))
    assert ("executable.main", "ScriptAPI") in imports

def test_executable_test_packaging_artifacts():
    """Verify executable_test mirrors executable's packaging files."""
    required_files = [
        "build.bat",
        "CvSU Gen (Beta).spec",
        "file_version_info.txt",
        "app_icon.ico",
        "sign_exe.ps1",
        "DanJosephOrtega_CvSU.cer"
    ]
    for fname in required_files:
        p = os.path.join(TEST_EXEC_DIR, fname)
        assert os.path.exists(p), f"executable_test/{fname} must exist for packaging parity"

