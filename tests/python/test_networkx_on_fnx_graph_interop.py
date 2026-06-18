"""networkx functions operate correctly on franken_networkx graphs (interop).

fnx graph classes are NOT subclasses of networkx's (they are Rust-backed), but
they implement the same mapping interface, so networkx's pure-Python functions
work on them by duck typing. This pins that interop: calling an nx function on an
fnx graph yields the same result as on the equivalent nx graph, and an nx graph
can be constructed from an fnx graph.

This is the consumer side of coexistence (the other test guards fnx not
polluting nx); here we confirm nx can consume fnx graphs.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng, n


def test_fnx_graph_is_not_an_nx_subclass_but_duck_types():
    # Documented: fnx.Graph is a distinct (Rust-backed) class, not an nx subclass.
    assert not issubclass(fnx.Graph, nx.Graph)


@pytest.mark.parametrize("seed", range(30))
def test_networkx_functions_on_fnx_graphs(seed):
    fg, ng, n = _pair(seed)
    # networkx functions called DIRECTLY on the fnx graph match the nx graph.
    assert nx.is_connected(fg) == nx.is_connected(ng)
    assert round(nx.density(fg), 9) == round(nx.density(ng), 9)
    assert nx.number_of_edges(fg) == nx.number_of_edges(ng)
    assert dict(nx.triangles(fg)) == dict(nx.triangles(ng))
    assert dict(nx.degree(fg)) == dict(nx.degree(ng))
    assert int(nx.adjacency_matrix(fg).sum()) == int(nx.adjacency_matrix(ng).sum())


@pytest.mark.parametrize("seed", range(30))
def test_nx_graph_constructible_from_fnx_graph(seed):
    fg, ng, n = _pair(seed)
    rebuilt = nx.Graph(fg)
    assert sorted(map(tuple, map(sorted, rebuilt.edges()))) == (
        sorted(map(tuple, map(sorted, ng.edges())))
    )
    assert sorted(rebuilt.nodes()) == sorted(ng.nodes())
