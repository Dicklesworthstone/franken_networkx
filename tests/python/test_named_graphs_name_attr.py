"""br-r37-c1-61kez: regression — named graph generators must set
``G.graph['name']`` on the default (Rust fast path) just like the
``create_using``-routed path does.

Before this fix, 7 named graphs (petersen, house, bull, chvatal,
diamond, krackhardt_kite, tetrahedral) skipped the name tag when
``create_using=None`` because the Rust kernel returned a raw graph
and the Python wrapper exited without setting the attribute. The
``create_using``-routed path (via ``_classic_named_graph_from_adjlist``)
correctly set the name. Now both paths set the name.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# (generator_name, expected G.graph['name'])
_CASES = [
    ("petersen_graph", "Petersen Graph"),
    ("house_graph", "House Graph"),
    ("bull_graph", "Bull Graph"),
    ("chvatal_graph", "Chvatal Graph"),
    ("diamond_graph", "Diamond Graph"),
    ("krackhardt_kite_graph", "Krackhardt Kite Social Network"),
    ("tetrahedral_graph", "Platonic Tetrahedral Graph"),
]


@needs_nx
@pytest.mark.parametrize("name,expected", _CASES)
def test_named_graph_default_path_sets_name_attr(name, expected):
    """``fnx.NAME_graph()`` (no ``create_using``) must set G.graph['name']
    to match nx.NAME_graph()."""
    g = getattr(fnx, name)()
    assert g.graph.get("name") == expected
    # And it must match nx exactly.
    ng = getattr(nx, name)()
    assert dict(g.graph) == dict(ng.graph)


@needs_nx
@pytest.mark.parametrize("name,expected", _CASES)
def test_named_graph_create_using_path_sets_name_attr(name, expected):
    """``fnx.NAME_graph(create_using=Graph())`` (Python adjlist path)
    must also set G.graph['name']."""
    g = getattr(fnx, name)(create_using=fnx.Graph())
    assert g.graph.get("name") == expected
