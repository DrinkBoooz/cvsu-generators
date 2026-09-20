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

                    if name in ("ValidatedTemplateRecipe", "ValidatedAttendanceTemplateRecipe"):
                        rel = os.path.relpath(fpath, REPO_ROOT)
                        violations.append(f"{rel}:{node.lineno}")

    assert not violations, (
        f"Direct construction of ValidatedTemplateRecipe or ValidatedAttendanceTemplateRecipe is forbidden in generators/services:\n"
        + "\n".join(violations)
    )


def test_ast_no_hardcoded_template_bindings_in_ceit_gen():
    """Rule 2: ceit_gen.py and attendance_gen.py must not contain hardcoded positional table/cell bindings
    (e.g. tables[0], tables[1], rows[0].cells[1] for metadata binding)."""
    target_files = [
        os.path.join(REPO_ROOT, "modules", "generators", "ceit_gen.py"),
        os.path.join(REPO_ROOT, "modules", "generators", "attendance_gen.py"),
    ]
    violations = []
    for fpath in target_files:
        with open(fpath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=fpath)

        for node in ast.walk(tree):
            # Check for subscript access like tables[0] or tables[1]
            if isinstance(node, ast.Subscript):
                if isinstance(node.value, ast.Name) and node.value.id in ("tables", "doc_tables"):
                    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                        rel = os.path.relpath(fpath, REPO_ROOT)
                        violations.append(f"{rel}: Subscript on tables[{node.slice.value}] at line {node.lineno}")

    assert not violations, (
        f"Found hardcoded positional table indexing in generators:\n"
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
    """Rule 4: All generator classes in ceit_gen.py, grade_gen.py, and attendance_gen.py must require a recipe parameter in __init__."""
    target_files = [
        os.path.join(REPO_ROOT, "modules", "generators", "ceit_gen.py"),
        os.path.join(REPO_ROOT, "modules", "generators", "grade_gen.py"),
        os.path.join(REPO_ROOT, "modules", "generators", "attendance_gen.py"),
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


def test_ast_no_positional_template_assumptions_in_generators():
    """Rule 6: Production generators (especially attendance_gen.py) must not use
    unexplained positional assumptions to select semantic template cells or rows:
    - [-1] on row_cells, cells, or summary cells
    - Direct fixed row constants (e.g. rows[2]) for student template extraction
    - Direct selection of summary cells by last position or negative slicing (e.g. [:-3], [-3:])
    - Direct selection of date template cells without recipe authority
    """
    attendance_gen_path = os.path.join(REPO_ROOT, "modules", "generators", "attendance_gen.py")
    with open(attendance_gen_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=attendance_gen_path)

    violations = []
    for node in ast.walk(tree):
        # 1. Check for [-1] subscript on cell/row collections
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.UnaryOp) and isinstance(node.slice.op, ast.USub):
                if isinstance(node.slice.operand, ast.Constant):
                    target_name = ""
                    if isinstance(node.value, ast.Name):
                        target_name = node.value.id
                    elif isinstance(node.value, ast.Attribute):
                        target_name = node.value.attr

                    if any(kw in target_name.lower() for kw in ("cell", "row", "summary", "orig")):
                        violations.append(
                            f"Prohibited negative subscript '[ -{node.slice.operand.value} ]' on '{target_name}' at line {node.lineno}"
                        )

            # Check for negative slice like [:-3] or [-3:] on row/cells
            if isinstance(node.slice, ast.Slice):
                for bound in (node.slice.lower, node.slice.upper):
                    if isinstance(bound, ast.UnaryOp) and isinstance(bound.op, ast.USub):
                        target_name = ""
                        if isinstance(node.value, ast.Name):
                            target_name = node.value.id
                        elif isinstance(node.value, ast.Attribute):
                            target_name = node.value.attr
                        if any(kw in target_name.lower() for kw in ("cell", "row", "summary")):
                            violations.append(
                                f"Prohibited negative slice on '{target_name}' at line {node.lineno}"
                            )

            # 2. Check for hardcoded student prototype row index rows[2] on tables
            if isinstance(node.slice, ast.Constant) and node.slice.value == 2:
                if isinstance(node.value, ast.Attribute) and node.value.attr == "rows":
                    violations.append(
                        f"Hardcoded row subscript 'rows[2]' for student prototype row at line {node.lineno}; must use recipe.matrix_binding.student_template_row_index"
                    )

    assert not violations, (
        f"Found prohibited positional template assumptions in attendance_gen.py:\n"
        + "\n".join(violations)
    )


def test_ast_rule_6_detector_catches_violations():
    """Verify that Rule 6 AST detector correctly flags offending positional patterns."""
    bad_code = """
def bad_generator(matrix_tbl, row_cells):
    summary_cell = row_cells[-1]
    prototype_row = matrix_tbl.rows[2]
    date_cells = row_cells[:-3]
"""
    tree = ast.parse(bad_code)
    detected = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.UnaryOp) and isinstance(node.slice.op, ast.USub):
                if isinstance(node.slice.operand, ast.Constant):
                    target_name = ""
                    if isinstance(node.value, ast.Name):
                        target_name = node.value.id
                    elif isinstance(node.value, ast.Attribute):
                        target_name = node.value.attr
                    if any(kw in target_name.lower() for kw in ("cell", "row", "summary", "orig")):
                        detected.append("negative_subscript")
            if isinstance(node.slice, ast.Slice):
                for bound in (node.slice.lower, node.slice.upper):
                    if isinstance(bound, ast.UnaryOp) and isinstance(bound.op, ast.USub):
                        target_name = ""
                        if isinstance(node.value, ast.Name):
                            target_name = node.value.id
                        elif isinstance(node.value, ast.Attribute):
                            target_name = node.value.attr
                        if any(kw in target_name.lower() for kw in ("cell", "row", "summary")):
                            detected.append("negative_slice")
            if isinstance(node.slice, ast.Constant) and node.slice.value == 2:
                if isinstance(node.value, ast.Attribute) and node.value.attr == "rows":
                    detected.append("rows_2")

    assert "negative_subscript" in detected
    assert "negative_slice" in detected
    assert "rows_2" in detected

