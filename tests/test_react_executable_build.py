import os
import ast
import pytest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_EXEC_DIR = os.path.join(WORKSPACE_ROOT, "executable_test")
PROD_EXEC_DIR = os.path.join(WORKSPACE_ROOT, "executable")

def test_production_executable_remains_untouched():
    """Ensure main executable_test files remain present and valid."""
    prod_ui = os.path.join(TEST_EXEC_DIR, "ui.html")
    prod_main = os.path.join(TEST_EXEC_DIR, "main.py")
    assert os.path.exists(prod_ui), "executable_test/ui.html must exist"
    assert os.path.exists(prod_main), "executable_test/main.py must exist"

    with open(prod_ui, "r", encoding="utf-8") as f:
        content = f.read()
        assert "CvSU Gen" in content
        assert "badge-version" in content

def test_executable_test_modular_css_manifest():
    """Verify executable_test/css contains all modular stylesheets."""
    css_dir = os.path.join(TEST_EXEC_DIR, "css")
    assert os.path.isdir(css_dir), "executable_test/css directory must exist"

    expected_css = [
        "tokens.css",
        "base.css",
        "layout.css",
        "components.css",
        "tables.css",
        "modals.css",
        "drawers.css"
    ]
    for css_file in expected_css:
        path = os.path.join(css_dir, css_file)
        assert os.path.exists(path), f"CSS module {css_file} must exist"
        assert os.path.getsize(path) > 0, f"CSS module {css_file} must not be empty"

def test_executable_test_modular_js_manifest():
    """Verify executable_test/js contains all modular scripts."""
    js_dir = os.path.join(TEST_EXEC_DIR, "js")
    assert os.path.isdir(js_dir), "executable_test/js directory must exist"

    expected_js = [
        "state.js",
        "toast.js",
        "modal.js",
        "stepper.js",
        "bridge.js",
        "theme.js",
        "drawers.js",
        "step1.js",
        "step2.js",
        "step3.js",
        "settings.js",
        "templates.js",
        "app.js"
    ]
    for js_file in expected_js:
        path = os.path.join(js_dir, js_file)
        assert os.path.exists(path), f"JS module {js_file} must exist"
        assert os.path.getsize(path) > 0, f"JS module {js_file} must not be empty"

def test_executable_test_ui_html_links_all_modules():
    """Verify executable_test/ui.html links all CSS and JS modules without inline blobs."""
    ui_path = os.path.join(TEST_EXEC_DIR, "ui.html")
    assert os.path.exists(ui_path), "executable_test/ui.html must exist"

    with open(ui_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Verify CSS links
    for css_name in ["tokens.css", "base.css", "layout.css", "components.css", "tables.css", "modals.css", "drawers.css"]:
        assert f'href="css/{css_name}"' in html, f"ui.html must link css/{css_name}"

    # Verify JS scripts
    for js_name in ["state.js", "toast.js", "modal.js", "theme.js", "drawers.js", "stepper.js", "bridge.js", "step1.js", "step2.js", "step3.js", "settings.js", "templates.js", "app.js"]:
        assert f'src="js/{js_name}"' in html, f"ui.html must link js/{js_name}"

def test_executable_test_python_package_structure():
    """Verify executable_test Python package modular structure and AST validity."""
    api_dir = os.path.join(TEST_EXEC_DIR, "api")
    native_dir = os.path.join(TEST_EXEC_DIR, "native")
    assert os.path.isdir(api_dir), "executable_test/api must exist"
    assert os.path.isdir(native_dir), "executable_test/native must exist"

    for py_name in ["__init__.py", "base.py", "schedule_roster.py", "config.py", "templates.py", "system.py", "generation.py"]:
        p = os.path.join(api_dir, py_name)
        assert os.path.exists(p), f"api/{py_name} must exist"
        with open(p, "r", encoding="utf-8") as f:
            ast.parse(f.read())

    native_init = os.path.join(native_dir, "__init__.py")
    native_dnd = os.path.join(native_dir, "dnd.py")
    assert os.path.exists(native_init)
    assert os.path.exists(native_dnd)
    with open(native_dnd, "r", encoding="utf-8") as f:
        ast.parse(f.read())

    main_py = os.path.join(TEST_EXEC_DIR, "main.py")
    with open(main_py, "r", encoding="utf-8") as f:
        ast.parse(f.read())

def test_executable_test_packaging_artifacts():
    """Verify executable_test mirrors packaging files and bundles css/ and js/."""
    required_files = [
        "build.bat",
        "CvSU Gen.spec",
        "file_version_info.txt",
        "app_icon.ico",
        "sign_exe.ps1",
        "DanJosephOrtega_CvSU.cer"
    ]
    for fname in required_files:
        p = os.path.join(TEST_EXEC_DIR, fname)
        assert os.path.exists(p), f"executable_test/{fname} must exist for packaging parity"

    # Check spec includes css and js
    spec_path = os.path.join(TEST_EXEC_DIR, "CvSU Gen.spec")
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()
    assert "('css', 'css')" in spec_content
    assert "('js', 'js')" in spec_content

    # Check build.bat includes css and js
    build_path = os.path.join(TEST_EXEC_DIR, "build.bat")
    with open(build_path, "r", encoding="utf-8") as f:
        build_content = f.read()
    assert '--add-data "css;css/"' in build_content
    assert '--add-data "js;js/"' in build_content
