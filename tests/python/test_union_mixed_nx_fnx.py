"""br-r37-c1-i2uub: regression — fnx.union accepts nx graph args via
coercion at the Python wrapper boundary.

Before this fix, ``fnx.union(nx.Graph(...), fnx.Graph(...))`` raised
``TypeError: expected Graph, DiGraph, MultiGraph, or MultiDiGraph``
because the PyO3-bound ``_raw_union`` strictly checks fnx graph
types. The Python wrapper now coerces nx-typed args to fnx via
``_from_nx_graph`` before delegating.
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


@needs_nx
def test_union_nx_first_arg_fnx_second():
    ng = nx.Graph([(0, 1)])
    fg = fnx.Graph([(2, 3)])
    u = fnx.union(ng, fg)
    assert sorted(u.edges()) == [(0, 1), (2, 3)]
    # output is fnx-typed
    assert isinstance(u, fnx.Graph)


@needs_nx
def test_union_fnx_first_arg_nx_second():
    fg = fnx.Graph([(0, 1)])
    ng = nx.Graph([(2, 3)])
    u = fnx.union(fg, ng)
    assert sorted(u.edges()) == [(0, 1), (2, 3)]
    assert isinstance(u, fnx.Graph)


@needs_nx
def test_union_nx_nx_args():
    ng1 = nx.Graph([(0, 1)])
    ng2 = nx.Graph([(2, 3)])
    u = fnx.union(ng1, ng2)
    assert sorted(u.edges()) == [(0, 1), (2, 3)]


@needs_nx
def test_union_mixed_digraph():
    ng = nx.DiGraph([(0, 1)])
    fg = fnx.DiGraph([(2, 3)])
    u = fnx.union(ng, fg)
    assert sorted(u.edges()) == [(0, 1), (2, 3)]


@needs_nx
def test_union_mixed_with_rename():
    ng = nx.Graph([(0, 1)])
    fg = fnx.Graph([(0, 1)])
    u = fnx.union(ng, fg, rename=("a_", "b_"))
    assert sorted(u.edges()) == [("a_0", "a_1"), ("b_0", "b_1")]


@needs_nx
def test_union_fnx_fnx_no_regression():
    g1 = fnx.Graph([(0, 1)])
    g2 = fnx.Graph([(2, 3)])
    u = fnx.union(g1, g2)
    assert sorted(u.edges()) == [(0, 1), (2, 3)]


@needs_nx
def test_union_mixed_with_node_attrs():
    """Attributes from the nx-coerced graph survive the conversion."""
    ng = nx.Graph()
    ng.add_node(0, color="red")
    ng.add_node(1, color="blue")
    ng.add_edge(0, 1)
    fg = fnx.Graph([(2, 3)])
    u = fnx.union(ng, fg)
    assert u.nodes[0]["color"] == "red"
    assert u.nodes[1]["color"] == "blue"
