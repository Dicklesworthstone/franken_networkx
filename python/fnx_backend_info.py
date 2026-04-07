"""Top-level metadata provider for the NetworkX backend entry point.

This must stay outside the ``franken_networkx`` package so importing it does not
trigger ``franken_networkx.__init__`` while NetworkX is still initializing.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _supported_algorithm_names() -> list[str]:
    backend_path = Path(__file__).resolve().parent / "franken_networkx" / "backend.py"
    backend_source = backend_path.read_text(encoding="utf-8")
    module = ast.parse(backend_source, filename=str(backend_path))
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
    return {
        "short_summary": "Rust-backed graph algorithms and generators with NetworkX parity goals.",
        "functions": {name: {} for name in _supported_algorithm_names()},
    }
