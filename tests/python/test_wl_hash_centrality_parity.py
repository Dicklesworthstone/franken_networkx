"""Phase B certification: Weisfeiler-Lehman graph/subgraph hashes
(deterministic, deeply iteration-order-sensitive — a strong invariant)
and advanced spectral centralities (numeric value + python-float type).
Zero divergences.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _mk(seed=37, n=14, m=45):
    R = random.Random(seed)
    ue = [(u, v) for u, v in ((R.randrange(n), R.randrange(n)) for _ in range(m)) if u != v]
    return fnx.Graph(ue), nx.Graph(ue)


def test_wl_graph_hash():
    gf, gn = _mk()
    assert fnx.weisfeiler_lehman_graph_hash(gf) == nx.weisfeiler_lehman_graph_hash(gn)
    assert fnx.weisfeiler_lehman_graph_hash(gf, iterations=5) == nx.weisfeiler_lehman_graph_hash(
        gn, iterations=5
    )


def test_wl_graph_hash_edge_attr():
    ue = _mk()[1].edges()
    gfa, gna = fnx.Graph(), nx.Graph()
    for i, (u, v) in enumerate(ue):
        gfa.add_edge(u, v, color="rgb"[i % 3])
        gna.add_edge(u, v, color="rgb"[i % 3])
    assert fnx.weisfeiler_lehman_graph_hash(gfa, edge_attr="color") == nx.weisfeiler_lehman_graph_hash(
        gna, edge_attr="color"
    )


def test_wl_subgraph_hashes():
    gf, gn = _mk()
    assert {repr(k): v for k, v in fnx.weisfeiler_lehman_subgraph_hashes(gf).items()} == {
        repr(k): v for k, v in nx.weisfeiler_lehman_subgraph_hashes(gn).items()
    }


def _D(d):
    return sorted((repr(k), round(float(v), 6), type(v).__name__) for k, v in d.items())


@pytest.mark.parametrize(
    "fn",
    ["subgraph_centrality", "communicability_betweenness_centrality", "second_order_centrality"],
)
def test_advanced_centrality_value_and_type(fn):
    gf, gn = _mk()
    assert _D(getattr(fnx, fn)(gf)) == _D(getattr(nx, fn)(gn)), fn
