"""NetworkX backend metadata provider that is safe during nx import.

NetworkX loads ``networkx.backend_info`` entry points while
``networkx.__init__`` is still finishing. This module intentionally
stays outside the ``franken_networkx`` package so importing the entry
point does not execute ``franken_networkx.__init__`` or load the PyO3
extension while NetworkX is partially initialized.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["get_backend_info"]


def _supported_algorithm_names() -> list[str]:
    backend_source = (
        Path(__file__).with_name("franken_networkx") / "backend.py"
    ).read_text(encoding="utf-8")
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
