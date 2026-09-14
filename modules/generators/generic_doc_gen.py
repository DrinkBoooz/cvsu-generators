#!/usr/bin/env python3
"""
modules/generators/generic_doc_gen.py

Configurable Generic Document Generator.
Consumes an authoritative ValidatedTemplateRecipe (or validates incoming recipe dict)
to populate any .docx template dynamically with ClassInfo and student rosters.
"""

from typing import Dict, Any, Union
from modules.models.schedule import ClassInfo
from modules.models.recipe import ValidatedTemplateRecipe
from modules.parsers.recipe_validator import RecipeValidator
from modules.generators.ceit_gen import DocumentGenerator, TemplateError


class ConfigurableDocumentGenerator(DocumentGenerator):
    """
    Dynamic generator that populates custom templates based on an authoritative recipe.
    Zero mutable dictionary access; delegates core execution to DocumentGenerator base class.
    """

    def __init__(
        self,
        template_path: str,
        recipe: Union[ValidatedTemplateRecipe, Dict[str, Any]],
        profile_id: str = "custom_docx",
    ):
        if isinstance(recipe, ValidatedTemplateRecipe):
            validated_recipe = recipe
        elif isinstance(recipe, dict):
            validated_recipe = RecipeValidator.validate_dict(recipe, profile_id)
        else:
            raise TypeError(
                f"ConfigurableDocumentGenerator requires ValidatedTemplateRecipe or dict, got {type(recipe).__name__}"
            )

        super().__init__(template_path, validated_recipe)
        self._title = validated_recipe.metadata.get("title") or "Custom Document"
        self._suffix = validated_recipe.metadata.get("suffix") or "CUSTOM_FORM"

    @property
    def title(self) -> str:
        return self._title

    @property
    def suffix(self) -> str:
        return self._suffix
