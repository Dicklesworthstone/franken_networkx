"""Node-order parity for ``relabel_nodes`` and dict-returning metrics.

``fnx.relabel_nodes`` produces the same node iteration order as networkx,
and dict-returning metrics emit keys in that same order on a relabelled
graph. The contract only holds when the *source* graphs are built
identically (same node-construction order) — graph node order is
construction-order-sensitive, so comparing a fnx graph built nodes-first
against an nx graph built edges-first is a probe pitfall, not a divergence.

br-r37-c1-fvge2
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _identical_pair(seed, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    nodes = list(range(n))
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(nodes)        # identical node-construction order
    ng.add_nodes_from(nodes)
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(40))
def test_relabel_nodes_node_order_matches_networkx(seed):
    fg, ng, n = _identical_pair(seed)
    mapping = {i: f"r{i}" for i in range(n)}
    assert list(fnx.relabel_nodes(fg, mapping).nodes()) == (
        list(nx.relabel_nodes(ng, mapping).nodes())
    )
    int_mapping = {i: i + 100 for i in range(n)}
    assert list(fnx.relabel_nodes(fg, int_mapping).nodes()) == (
        list(nx.relabel_nodes(ng, int_mapping).nodes())
    )


@pytest.mark.parametrize(
    "metric", ["degree_centrality", "closeness_centrality", "betweenness_centrality"]
)
@pytest.mark.parametrize("seed", range(30))
def test_centrality_key_order_matches_networkx_on_relabeled(metric, seed):
    fg, ng, n = _identical_pair(seed, p=0.5)
    if not nx.is_connected(ng):
        pytest.skip("disconnected")
    mapping = {i: f"r{i}" for i in range(n)}
    fr = fnx.relabel_nodes(fg, mapping)
    nr = nx.relabel_nodes(ng, mapping)
    assert list(getattr(fnx, metric)(fr)) == list(getattr(nx, metric)(nr))
