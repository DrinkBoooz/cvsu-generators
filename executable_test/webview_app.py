"""
Desktop Webview Application Module.
Provides safe string evaluation without using eval() and exports entrypoint primitives.
"""

import ast
import os
import sys

def _parse_eval_String(s: str):
    """
    Safely parse a string literal using AST literal_eval.
    Eliminates bare eval() calls and related antivirus heuristic signatures.
    """
    if not isinstance(s, str):
        raise ValueError("Input expression must be a string")
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Safe literal evaluation failed: {e}") from e

# Forward common exports to main application components
try:
    from .main import create_app, main
    from .api import ScriptAPI
except (ImportError, ValueError):
    try:
        from main import create_app, main
        from api import ScriptAPI
    except ImportError:
        pass

__all__ = ["_parse_eval_String"]

