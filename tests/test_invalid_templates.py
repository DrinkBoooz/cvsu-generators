import os
import pytest
from modules.generators.ceit_gen import GeneratorFactory

def test_missing_canonical_template_fails_explicitly(tmp_path):
    """E0: Missing canonical native template raises FileNotFoundError explicitly,
    proving no shadow-template fallback survives."""
    empty_templates_dir = tmp_path / "templates"
    empty_templates_dir.mkdir()

    factory = GeneratorFactory(str(empty_templates_dir))
    all_gens = factory.get_all(include_custom=False)
    assert len(all_gens) == 7

    for gen_factory, suffix in all_gens:
        with pytest.raises(FileNotFoundError) as exc_info:
            gen_factory()
        assert "Template not found" in str(exc_info.value)
