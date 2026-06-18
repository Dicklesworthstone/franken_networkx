"""Namespace routings survive submodule imports (import-order stability).

The 2qsqf namespace routings rebind fnx submodule functions to fnx natives. A
later import of an algorithms submodule must NOT revert them to networkx's
implementation (the algorithms package re-runs aliasing on import — the same
mechanism that caused the dispersion clobber, 0ouoj). This pins routing
stability across submodule imports.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import importlib

import pytest
import networkx as nx
import franken_networkx as fnx

# (submodule, routed function) pairs from the 2qsqf namespace sweep.
_ROUTED = [
    ("linalg", "adjacency_matrix"),
    ("components", "connected_components"),
    ("clique", "find_cliques"),
    ("core", "core_number"),
    ("chordal", "is_chordal"),
    ("traversal", "bfs_tree"),
    ("dag", "topological_sort"),
    ("connectivity", "node_connectivity"),
]


def _is_routed(submodule, fn):
    mod = importlib.import_module(f"franken_networkx.{submodule}")
    return getattr(mod, fn) is not getattr(nx, fn)


@pytest.mark.parametrize("submodule,fn", _ROUTED)
def test_routing_holds_at_baseline(submodule, fn):
    assert _is_routed(submodule, fn)


@pytest.mark.parametrize("submodule,fn", _ROUTED)
def test_routing_survives_algorithms_submodule_imports(submodule, fn):
    # Importing several algorithms submodules re-runs the aliasing machinery.
    for sub in ("centrality", "isomorphism", "components", "flow", "tree",
                "operators", "traversal", "connectivity"):
        try:
            importlib.import_module(f"franken_networkx.algorithms.{sub}")
        except ImportError:
            pass
    # The routing must still point at the fnx native, not networkx's.
    assert _is_routed(submodule, fn)


def test_flattened_algorithms_routing_survives_imports():
    import franken_networkx.algorithms as fa
    for fn in ("connected_components", "find_cliques", "core_number",
               "node_connectivity", "is_chordal"):
        assert getattr(fa, fn) is not getattr(nx, fn)
