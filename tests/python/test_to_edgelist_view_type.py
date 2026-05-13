"""br-r37-c1-rsvst: regression tests that to_edgelist returns a view
(matching nx) not a materialized list."""

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
def test_to_edgelist_returns_view_type_matching_nx():
    fg = fnx.Graph()
    fg.add_edge(0, 1, weight=1.0)
    ng = nx.Graph()
    ng.add_edge(0, 1, weight=1.0)
    rf = fnx.to_edgelist(fg)
    rn = nx.to_edgelist(ng)
    assert type(rf).__name__ == type(rn).__name__


def test_to_edgelist_iterable_with_data():
    g = fnx.Graph()
    g.add_edge(0, 1, weight=2.5)
    g.add_edge(1, 2, weight=3.5)
    result = list(fnx.to_edgelist(g))
    assert len(result) == 2
    assert all(isinstance(triple, tuple) and len(triple) == 3 for triple in result)


def test_to_edgelist_nodelist_includes_incident_edges():
    """nx.to_edgelist(G, nodelist) includes all edges incident to ANY
    node in nodelist (matching G.edges(nodelist, data=True)), not just
    edges with BOTH endpoints in nodelist."""
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 3)
    # nodelist=[0, 1] includes (0, 1) AND (1, 2) — 1 is in nodelist.
    result = list(fnx.to_edgelist(g, nodelist=[0, 1]))
    edge_set = {(u, v) for u, v, _ in result}
    assert (0, 1) in edge_set
    assert (1, 2) in edge_set


@needs_nx
def test_to_edgelist_nodelist_matches_nx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    rf = list(fnx.to_edgelist(fg, nodelist=[1, 2, 3]))
    rn = list(nx.to_edgelist(ng, nodelist=[1, 2, 3]))
    assert sorted((u, v) for u, v, _ in rf) == sorted((u, v) for u, v, _ in rn)
