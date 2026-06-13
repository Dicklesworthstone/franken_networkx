"""Adjacency-order parity for nx -> fnx graph construction.

Beads br-r37-c1-k6few / br-r37-c1-5doou (both PHANTOM — comparison
artifacts, not bugs).

When you build a graph *from another graph* — ``nx.Graph(G)`` or
``fnx.Graph(G)`` — networkx does NOT preserve the source's per-node
neighbour insertion order. ``nx.convert.to_networkx_graph`` walks
``G.adj`` via ``from_dict_of_dicts``, which rebuilds every node's
adjacency in adjacency-traversal order, so a node's neighbour list can
flip relative to the original::

    Gx = nx.Graph(); Gx.add_edge(0, 1); Gx.add_edge(1, 2); Gx.add_edge(2, 0)
    list(Gx.neighbors(2))            -> [1, 0]   (original insertion order)
    list(nx.Graph(Gx).neighbors(2))  -> [0, 1]   (nx reorders on rebuild)
    list(fnx.Graph(Gx).neighbors(2)) -> [0, 1]   (fnx matches nx exactly)

fnx reproduces nx's reordering *byte-for-byte*. The apparent "k6few /
5doou divergence" came from an unfair comparison: a round-tripped fnx
graph (``fnx.Graph(G)``, reordered) measured against nx running on the
*non*-round-tripped original ``G``. The fair comparison — both sides
constructed the same way — shows zero divergence (verified below and on
delegated, RCM-sensitive consumers like
approximate_current_flow_betweenness_centrality).

The invariant fnx actually owes networkx is therefore
``fnx.Graph(G) == nx.Graph(G)`` (and the directed analogue), NOT
``fnx.Graph(G) == G``. These tests pin the real invariant.
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


def _triangle(lib):
    g = lib.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 0)
    return g


def _undirected_corpus():
    return {
        "triangle": _triangle(nx),
        "karate": nx.karate_club_graph(),
        "ws": nx.connected_watts_strogatz_graph(80, 6, 0.3, seed=7),
        "gnp": nx.gnp_random_graph(50, 0.12, seed=3),
        "grid": nx.convert_node_labels_to_integers(nx.grid_2d_graph(6, 7)),
        "barbell": nx.barbell_graph(10, 5),
    }


# --- Native build path: fnx matches nx neighbour order exactly. -------------

@needs_nx
def test_native_build_preserves_insertion_order():
    """Building edge-by-edge, fnx keeps nx's insertion order."""
    gf = _triangle(fnx)
    gx = _triangle(nx)
    for node in gx.nodes():
        assert list(gf.neighbors(node)) == list(gx.neighbors(node)), node


# --- The real invariant: fnx.Graph(G) is byte-faithful to nx.Graph(G). ------

@needs_nx
@pytest.mark.parametrize("name", list(_undirected_corpus()))
def test_graph_construction_matches_networkx(name):
    """fnx.Graph(G) reproduces nx.Graph(G) adjacency order node-for-node.

    nx reorders on rebuild (from_dict_of_dicts); fnx reorders identically.
    """
    G = _undirected_corpus()[name]
    nxc = nx.Graph(G)
    fxc = fnx.Graph(G)
    assert list(nxc.nodes()) == list(fxc.nodes())
    for node in nxc.nodes():
        assert list(fxc.neighbors(node)) == list(nxc.neighbors(node)), (
            f"{name} node {node}: fnx={list(fxc.neighbors(node))} "
            f"nx={list(nxc.neighbors(node))}"
        )


@needs_nx
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_digraph_construction_matches_networkx(seed):
    """fnx.DiGraph(DG) reproduces nx.DiGraph(DG) succ/pred order."""
    DG = nx.gnp_random_graph(40, 0.08, seed=seed, directed=True)
    nxc = nx.DiGraph(DG)
    fxc = fnx.DiGraph(DG)
    for node in nxc.nodes():
        assert list(fxc.successors(node)) == list(nxc.successors(node)), node
        assert list(fxc.predecessors(node)) == list(nxc.predecessors(node)), node


@needs_nx
def test_to_dict_of_lists_matches_when_fairly_constructed():
    """to_dict_of_lists agrees once both sides are constructed the same way.

    Comparing fnx.to_dict_of_lists(fnx.Graph(G)) against
    nx.to_dict_of_lists(G) (the original) is the artifact that looked
    like a bug; against nx.to_dict_of_lists(nx.Graph(G)) it is identical.
    """
    for G in _undirected_corpus().values():
        assert fnx.to_dict_of_lists(fnx.Graph(G)) == nx.to_dict_of_lists(nx.Graph(G))


@needs_nx
def test_delegated_rcm_consumer_matches_when_fairly_constructed():
    """approximate_current_flow_betweenness (RCM-ordering sensitive, the
    br-r37-c1-5doou function) is byte-identical to nx under a fair
    comparison; the ~0.1 "divergence" was original-vs-round-tripped."""
    for N, seed in [(30, 1), (80, 2), (60, 3)]:
        G = nx.connected_watts_strogatz_graph(N, 4, 0.3, seed=seed)
        fr = fnx.approximate_current_flow_betweenness_centrality(
            fnx.Graph(G), seed=42
        )
        nr = nx.approximate_current_flow_betweenness_centrality(
            nx.Graph(G), seed=42
        )
        assert set(fr) == set(nr)
        assert max(abs(fr[k] - nr[k]) for k in fr) == 0.0
