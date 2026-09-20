import os
import pytest
from modules.models.recipe import (
    RECIPE_SCHEMA_VERSION,
    _PRIVATE_CONSTRUCTION_SENTINEL,
    TemplateError,
    AmbiguousTemplateError,
    InvalidRecipeError,
    RosterBinding,
    HeaderCellBinding,
    SignatureBinding,
    GeneratorProfile,
    PROFILE_ACADEMIC_DOCX,
    PROFILE_GRADE_SHEET_XLSX,
    RawTemplateRecipeCandidate,
    ValidatedTemplateRecipe,
)
from modules.parsers.semantic_registry import (
    SemanticRegistry,
    FIELD_INSTRUCTOR,
    FIELD_SCHEDULE_CODE,
    ROLE_INSTRUCTOR_SIGNATURE,
)
from modules.parsers.recipe_validator import RecipeValidator
from modules.services.template_recipe_service import TemplateRecipeResolver


def test_validated_recipe_direct_construction_forbidden():
    """Verify ValidatedTemplateRecipe enforces private construction token guard."""
    with pytest.raises(PermissionError) as exc:
        ValidatedTemplateRecipe(
            schema_version=2,
            profile_id="academic_docx",
            fingerprint="fake",
            template_path="fake.docx",
            roster_binding=None,
            header_bindings={},
            signature_bindings={},
            metadata={},
        )
    assert "Direct instantiation is forbidden" in str(exc.value)

    # Even with forged token
    with pytest.raises(PermissionError):
        ValidatedTemplateRecipe(
            schema_version=2,
            profile_id="academic_docx",
            fingerprint="fake",
            template_path="fake.docx",
            roster_binding=None,
            header_bindings={},
            signature_bindings={},
            metadata={},
            _construction_token="forged_token",
        )


def test_recipe_to_dict_never_contains_construction_token():
    """Verify _construction_token never leaks into to_dict()."""
    candidate = RawTemplateRecipeCandidate(
        template_path="test.docx",
        profile_id="custom_docx",
        fingerprint="abc123hash",
        roster_candidate=None,
        header_candidates=[],
        signature_candidates=[],
        collisions=[],
        metadata={"title": "Test Doc"},
    )
    custom_profile = GeneratorProfile(
        profile_id="custom_docx",
        document_family="custom_docx",
        required_fields=(),
    )
    recipe = RecipeValidator.validate(candidate, custom_profile)
    assert isinstance(recipe, ValidatedTemplateRecipe)

    d = recipe.to_dict()
    assert "_construction_token" not in d
    assert d["schema_version"] == 2
    assert d["fingerprint"] == "abc123hash"


def test_strict_schema_version_rejection():
    """Verify strict rejection of schema versions other than 2."""
    base_data = {
        "profile_id": "custom_docx",
        "fingerprint": "abc123hash",
        "template_path": "test.docx",
        "roster_binding": None,
        "header_bindings": {},
        "signature_bindings": {},
        "metadata": {},
    }

    # Missing schema_version
    with pytest.raises(InvalidRecipeError) as exc1:
        RecipeValidator.validate_dict(base_data)
    assert "Unsupported recipe schema_version: None" in str(exc1.value)

    # v1 schema
    v1_data = dict(base_data)
    v1_data["schema_version"] = 1
    with pytest.raises(InvalidRecipeError) as exc2:
        RecipeValidator.validate_dict(v1_data)
    assert "Unsupported recipe schema_version: 1" in str(exc2.value)

    # v3 schema
    v3_data = dict(base_data)
    v3_data["schema_version"] = 3
    with pytest.raises(InvalidRecipeError) as exc3:
        RecipeValidator.validate_dict(v3_data)
    assert "Unsupported recipe schema_version: 3" in str(exc3.value)

    # v2 schema succeeds
    v2_data = dict(base_data)
    v2_data["schema_version"] = 2
    recipe = RecipeValidator.validate_dict(v2_data)
    assert recipe.schema_version == 2


def test_grade_sheet_capacity_limit_mandatory():
    """Verify grade_sheet requires capacity_limit > 0."""
    # Missing capacity_limit
    candidate_no_cap = RawTemplateRecipeCandidate(
        template_path="grading.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "capacity_limit": None,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "M4", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(TemplateError) as exc1:
        RecipeValidator.validate(candidate_no_cap, PROFILE_GRADE_SHEET_XLSX)
    assert "requires capacity_limit > 0" in str(exc1.value)

    # Zero capacity_limit
    candidate_zero_cap = RawTemplateRecipeCandidate(
        template_path="grading.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "capacity_limit": 0,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "M4", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    with pytest.raises(TemplateError) as exc2:
        RecipeValidator.validate(candidate_zero_cap, PROFILE_GRADE_SHEET_XLSX)
    assert "requires capacity_limit > 0" in str(exc2.value)

    # Valid positive capacity_limit
    candidate_valid = RawTemplateRecipeCandidate(
        template_path="grading.xlsx",
        profile_id="grade_sheet_xlsx",
        fingerprint="fp1",
        roster_candidate={
            "table_index": 0,
            "first_data_row_index": 7,
            "name_col": 3,
            "id_col": 1,
            "capacity_limit": 50,
        },
        header_candidates=[
            {"cell_type": "xlsx_cell", "target": "M4", "field": "instructor", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "M1", "field": "course_section", "confidence": 1.0},
            {"cell_type": "xlsx_cell", "target": "C1", "field": "schedule_code", "confidence": 1.0},
        ],
    )
    recipe = RecipeValidator.validate(candidate_valid, PROFILE_GRADE_SHEET_XLSX)
    assert recipe.roster_binding.capacity_limit == 50


def test_semantic_registry_metadata_vs_signature_disambiguation():
    """Verify semantic registry prevents instructor metadata from binding signature regions."""
    # Top header table row
    is_sig_top = SemanticRegistry.is_signature_context(
        text="INSTRUCTOR: ORTEGA, DAN JOSEPH",
        table_index=0,
        total_tables=3,
        row_index=1,
        total_rows=4,
    )
    assert is_sig_top is False

    # Candidate in top table
    top_candidates = SemanticRegistry.match_metadata_candidate("INSTRUCTOR:", is_signature_region=is_sig_top)
    assert any(c[0] == FIELD_INSTRUCTOR for c in top_candidates)

    # Bottom sign-off row
    is_sig_bottom = SemanticRegistry.is_signature_context(
        text="INSTRUCTOR / PROFESSOR",
        table_index=2,
        total_tables=3,
        row_index=3,
        total_rows=4,
    )
    assert is_sig_bottom is True

    # Candidate in bottom table returns no metadata binding
    bottom_meta_candidates = SemanticRegistry.match_metadata_candidate(
        "INSTRUCTOR / PROFESSOR",
        is_signature_region=is_sig_bottom,
    )
    assert len(bottom_meta_candidates) == 0

    # Instead matches signature role
    bottom_sig_candidates = SemanticRegistry.match_signature_candidate(
        "INSTRUCTOR / PROFESSOR",
        in_signature_table=True,
    )
    assert any(c[0] == ROLE_INSTRUCTOR_SIGNATURE for c in bottom_sig_candidates)


def test_collision_and_ambiguity_rejection():
    """Verify equal-confidence collisions on required fields raise AmbiguousTemplateError."""
    collisions = SemanticRegistry.observe_collisions([
        {"field": "instructor", "target": (0, 1, 1), "confidence": 0.9},
        {"field": "instructor", "target": (0, 2, 1), "confidence": 0.9},
    ])
    assert len(collisions) == 1

    candidate = RawTemplateRecipeCandidate(
        template_path="ambiguous.docx",
        profile_id="academic_docx",
        fingerprint="fp_ambig",
        roster_candidate={
            "table_index": 1,
            "first_data_row_index": 2,
            "name_col": 0,
            "id_col": 1,
        },
        header_candidates=[
            {"cell_type": "docx_table", "target": (0, 1, 1), "field": "instructor", "confidence": 0.9},
            {"cell_type": "docx_table", "target": (0, 2, 1), "field": "instructor", "confidence": 0.9},
            {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 0.9},
            {"cell_type": "docx_table", "target": (0, 0, 3), "field": "schedule_code", "confidence": 0.9},
            {"cell_type": "docx_table", "target": (0, 1, 3), "field": "subject", "confidence": 0.9},
        ],
        collisions=collisions,
    )

    with pytest.raises(AmbiguousTemplateError) as exc:
        RecipeValidator.validate(candidate, PROFILE_ACADEMIC_DOCX)
    assert "Ambiguous template binding" in str(exc.value)


def test_template_recipe_resolver_caching_and_stale_invalidation(tmp_path):
    """Verify TemplateRecipeResolver 3-tuple caching and stale fingerprint invalidation."""
    tmpl_file = tmp_path / "test_template.docx"
    tmpl_file.write_text("initial content v1")

    resolver = TemplateRecipeResolver()

    # Register mock inspector
    class MockInspector:
        def __init__(self):
            self.inspect_count = 0

        def inspect(self, path, profile_id):
            self.inspect_count += 1
            return RawTemplateRecipeCandidate(
                template_path=path,
                profile_id=profile_id,
                fingerprint="",
                roster_candidate={
                    "table_index": 0,
                    "first_data_row_index": 1,
                    "name_col": 0,
                    "id_col": 1,
                },
                header_candidates=[
                    {"cell_type": "docx_table", "target": (0, 0, 0), "field": "instructor", "confidence": 0.95},
                    {"cell_type": "docx_table", "target": (0, 0, 1), "field": "course_section", "confidence": 0.95},
                    {"cell_type": "docx_table", "target": (0, 0, 2), "field": "schedule_code", "confidence": 0.95},
                    {"cell_type": "docx_table", "target": (0, 0, 3), "field": "subject", "confidence": 0.95},
                ],
            )

    mock_insp = MockInspector()
    resolver.register_profile_inspector(".docx", "academic_docx", mock_insp)

    # 1. First resolution: inspection & validation occur
    r1 = resolver.resolve_recipe(str(tmpl_file), profile_id="academic_docx")
    assert r1 is not None
    assert mock_insp.inspect_count == 1
    fp1 = r1.fingerprint

    # 2. Second resolution without modification: served from cache
    r2 = resolver.resolve_recipe(str(tmpl_file), profile_id="academic_docx")
    assert r2 is r1
    assert mock_insp.inspect_count == 1

    # 3. Modify template file: changes fingerprint, triggers stale cache eviction
    tmpl_file.write_text("updated content v2 with different bytes")
    r3 = resolver.resolve_recipe(str(tmpl_file), profile_id="academic_docx")
    assert r3 is not None
    assert r3.fingerprint != fp1
    assert mock_insp.inspect_count == 2
