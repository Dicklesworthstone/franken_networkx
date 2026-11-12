"""br-r37-c1-67dnc: regression tests for k_edge_components and
k_edge_subgraphs wrong-type handling.

nx's @not_implemented_for('multigraph') is the only decorator —
DiGraph IS supported (k-edge-connected components in directed
graphs are strongly-k-edge-connected). fnx previously rejected
DiGraph (via downstream bridges) and silently accepted MultiGraph
(working on simple-graph projection). Both are now corrected.
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


@pytest.mark.parametrize("k", [1, 2])
def test_k_edge_components_rejects_multigraph(k):
    g = fnx.MultiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        list(fnx.k_edge_components(g, k))


@pytest.mark.parametrize("k", [1, 2])
def test_k_edge_subgraphs_rejects_multigraph(k):
    g = fnx.MultiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        list(fnx.k_edge_subgraphs(g, k))


@needs_nx
def test_k_edge_components_accepts_digraph():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    gx = nx.DiGraph()
    gx.add_edge(0, 1)
    gx.add_edge(1, 2)
    f_comps = [set(c) for c in fnx.k_edge_components(g, 1)]
    n_comps = [set(c) for c in nx.k_edge_components(gx, 1)]
    assert sorted(map(sorted, f_comps)) == sorted(map(sorted, n_comps))


@needs_nx
def test_k_edge_subgraphs_accepts_digraph():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    gx = nx.DiGraph()
    gx.add_edge(0, 1)
    gx.add_edge(1, 2)
    # nx's k_edge_subgraphs on DiGraph yields sets of nodes (component
    # sets, not subgraph objects). Match the nx contract via delegation.
    f_subs = [set(s) if isinstance(s, set) else set(s.nodes()) for s in fnx.k_edge_subgraphs(g, 1)]
    n_subs = [set(s) if isinstance(s, set) else set(s.nodes()) for s in nx.k_edge_subgraphs(gx, 1)]
    assert sorted(map(sorted, f_subs)) == sorted(map(sorted, n_subs))


def test_simple_undirected_still_works():
    g = fnx.path_graph(5)
    comps = [set(c) for c in fnx.k_edge_components(g, 1)]
    assert comps == [{0, 1, 2, 3, 4}]
