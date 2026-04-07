"""Lightweight NetworkX backend metadata provider.

This module must remain safe to import while NetworkX itself is still
initializing. Avoid importing ``franken_networkx`` or ``networkx`` here.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _supported_algorithm_names() -> list[str]:
    backend_source = Path(__file__).with_name("backend.py").read_text(encoding="utf-8")
    module = ast.parse(backend_source, filename="backend.py")
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_SUPPORTED_ALGORITHMS":
                if not isinstance(node.value, ast.Dict):
                    raise RuntimeError("_SUPPORTED_ALGORITHMS is not a dict literal")
                names = []
                for key in node.value.keys:
                    if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                        raise RuntimeError("_SUPPORTED_ALGORITHMS contains a non-string key")
                    names.append(key.value)
                return names
    raise RuntimeError("Unable to find _SUPPORTED_ALGORITHMS in backend.py")


def get_backend_info():
    """Return NetworkX backend metadata for dispatch registration."""
    return {
        "short_summary": "Rust-backed graph algorithms and generators with NetworkX parity goals.",
        "functions": {name: {} for name in _supported_algorithm_names()},
    }
