import ast
import os
import glob
import pytest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_python_files(directory):
    return [
        os.path.join(root, f)
        for root, _, files in os.walk(directory)
        for f in files
        if f.endswith(".py")
    ]


def test_ast_no_direct_validated_recipe_construction():
    """Rule 1: ValidatedTemplateRecipe must NEVER be constructed directly outside
    modules/parsers/recipe_validator.py and modules/models/recipe.py."""
    forbidden_dirs = [
        os.path.join(REPO_ROOT, "modules", "generators"),
        os.path.join(REPO_ROOT, "modules", "services"),
    ]

    violations = []
    for fdir in forbidden_dirs:
        for fpath in get_python_files(fdir):
            with open(fpath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=fpath)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = None
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr

                    if name == "ValidatedTemplateRecipe":
                        rel = os.path.relpath(fpath, REPO_ROOT)
                        violations.append(f"{rel}:{node.lineno}")

    assert not violations, (
        f"Direct construction of ValidatedTemplateRecipe is forbidden in generators/services:\n"
        + "\n".join(violations)
    )


def test_ast_no_hardcoded_template_bindings_in_ceit_gen():
    """Rule 2: ceit_gen.py must not contain hardcoded positional table/cell bindings
    (e.g. tables[0], tables[1], rows[0].cells[1] for metadata binding)."""
    ceit_gen_path = os.path.join(REPO_ROOT, "modules", "generators", "ceit_gen.py")
    with open(ceit_gen_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=ceit_gen_path)

    violations = []
    for node in ast.walk(tree):
        # Check for subscript access like tables[0] or tables[1]
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id in ("tables", "doc_tables"):
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                    violations.append(f"Subscript on tables[{node.slice.value}] at line {node.lineno}")

    assert not violations, (
        f"Found hardcoded positional table indexing in ceit_gen.py:\n"
        + "\n".join(violations)
    )


def test_ast_no_hardcoded_cell_coordinates_in_grade_gen():
    """Rule 3: grade_gen.py must not contain hardcoded template coordinate assignments
    like ws['C1'] =, ws['AO59'] =, or hardcoded start_row = 11."""
    grade_gen_path = os.path.join(REPO_ROOT, "modules", "generators", "grade_gen.py")
    with open(grade_gen_path, "r", encoding="utf-8") as f:
        code = f.read()
        tree = ast.parse(code, filename=grade_gen_path)

    forbidden_coords = {
        "C1", "M1", "C2", "M2", "C3", "M3", "C4", "M4",
        "BI57", "AO59", "J56", "A18", "B18", "C18", "D60", "A77", "BI60", "AO62", "J59",
    }

    violations = []
    for node in ast.walk(tree):
        # Look for Subscript where slice is a string constant in forbidden_coords
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                coord = node.slice.value.upper()
                if coord in forbidden_coords:
                    violations.append(f"Hardcoded cell coordinate '{coord}' at line {node.lineno}")

        # Look for hardcoded assignments start_row = 11 or 12
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("start_row", "first_row"):
                    if isinstance(node.value, ast.Constant) and node.value.value in (10, 11, 12):
                        violations.append(f"Hardcoded start row constant '{node.value.value}' at line {node.lineno}")

    assert not violations, (
        f"Found hardcoded template cell coordinates in grade_gen.py:\n"
        + "\n".join(violations)
    )


def test_ast_generators_require_recipe_in_init():
    """Rule 4: All generator classes in ceit_gen.py and grade_gen.py must require a recipe parameter in __init__."""
    target_files = [
        os.path.join(REPO_ROOT, "modules", "generators", "ceit_gen.py"),
        os.path.join(REPO_ROOT, "modules", "generators", "grade_gen.py"),
    ]

    for fpath in target_files:
        with open(fpath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=fpath)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name.endswith("Generator") and node.name != "DocumentGenerator":
                    # Find __init__ method
                    init_method = next(
                        (n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"),
                        None
                    )
                    if init_method:
                        arg_names = [a.arg for a in init_method.args.args]
                        assert "recipe" in arg_names, (
                            f"Generator class {node.name} in {os.path.basename(fpath)} must take 'recipe' parameter in __init__"
                        )


def test_ast_construction_token_never_in_to_dict():
    """Rule 5: _construction_token must never be present in any to_dict() serialization dictionary keys."""
    recipe_models_path = os.path.join(REPO_ROOT, "modules", "models", "recipe.py")
    with open(recipe_models_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=recipe_models_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "to_dict":
            for subnode in ast.walk(node):
                if isinstance(subnode, ast.Constant) and subnode.value == "_construction_token":
                    pytest.fail(f"Found '_construction_token' serialized in to_dict() at line {subnode.lineno}")
