#!/usr/bin/env python3
"""
modules/generators/generic_doc_gen.py

Configurable Generic Document Generator.
Consumes an authoritative ValidatedTemplateRecipe (or validates incoming recipe dict)
to populate any .docx template dynamically with ClassInfo and student rosters.
Re-exports DocumentGenerator, ConfigurableDocumentGenerator, and TemplateError
from modules.generators.document_generator for 100% backward compatibility.
"""

from modules.generators.document_generator import (
    DocumentGenerator,
    ConfigurableDocumentGenerator,
    TemplateError,
    FieldResolver,
    resolve_field_value,
)

__all__ = [
    "DocumentGenerator",
    "ConfigurableDocumentGenerator",
    "TemplateError",
    "FieldResolver",
    "resolve_field_value",
]
