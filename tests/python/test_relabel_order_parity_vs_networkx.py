"""Relabelled node order and dict key order must match networkx, not just fnx.

br-r37-c1-fvge2. `test_relabeling_invariance_invariants.py` already checks that
relabelling is value- and order-equivariant *within fnx* — base graph against
relabelled graph, both fnx. That is self-consistency. It would stay green if fnx
and networkx drifted apart together.

This file compares against the oracle: build the same graph on both sides, relabel
both with the same mapping, and require identical node iteration order and
identical dict KEY order from the metrics that return per-node dicts.

THE IDENTICAL-SOURCE REQUIREMENT the bead documents is load-bearing and is
asserted here rather than only described. Node order depends on CONSTRUCTION
order, so a probe that builds fnx nodes-first and networkx edges-first compares
two different graphs and "finds" a divergence that is not one. Verified on both
libraries with an edge list that introduces nodes out of order:

    nodes-first  -> [0, 1, 2, 3]
    edges-first  -> [2, 3, 0, 1]      (SAME on networkx and fnx)

so the pitfall is shared upstream behaviour, not an fnx quirk.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

# Introduces nodes out of numeric order, so construction order is observable.
_EDGES = [(2, 3), (0, 1), (1, 2), (3, 0), (0, 2)]
_MAPPING = {0: "delta", 1: "charlie", 2: "bravo", 3: "alpha"}

_CLASS_PAIRS = [
    pytest.param(nx.Graph, fnx.Graph, id="Graph"),
    pytest.param(nx.DiGraph, fnx.DiGraph, id="DiGraph"),
    pytest.param(nx.MultiGraph, fnx.MultiGraph, id="MultiGraph"),
    pytest.param(nx.MultiDiGraph, fnx.MultiDiGraph, id="MultiDiGraph"),
]

# Per-node dict-returning metrics. Restricted to ones defined for every class
# above and cheap on a 4-node graph.
_NODE_METRICS = ["degree_centrality", "closeness_centrality", "betweenness_centrality"]


def _identical_source(cls):
    """Nodes FIRST, then edges — the same order on both libraries.

    This is the identical-source discipline: without it the two graphs differ in
    node order before any relabelling happens, and every order comparison below
    becomes meaningless.
    """
    graph = cls()
    graph.add_nodes_from(range(4))
    graph.add_edges_from(_EDGES)
    return graph


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_relabelled_node_order_matches_networkx(nx_cls, fnx_cls):
    nx_relabelled = nx.relabel_nodes(_identical_source(nx_cls), _MAPPING)
    fnx_relabelled = fnx.relabel_nodes(_identical_source(fnx_cls), _MAPPING)
    assert list(fnx_relabelled) == list(nx_relabelled)


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_relabelled_edge_order_matches_networkx(nx_cls, fnx_cls):
    nx_relabelled = nx.relabel_nodes(_identical_source(nx_cls), _MAPPING)
    fnx_relabelled = fnx.relabel_nodes(_identical_source(fnx_cls), _MAPPING)
    assert list(fnx_relabelled.edges()) == list(nx_relabelled.edges())


@pytest.mark.parametrize("metric", _NODE_METRICS)
def test_metric_key_order_matches_networkx_after_relabelling(metric):
    """Key ORDER, not just the key set — the property a dict comparison misses."""
    nx_relabelled = nx.relabel_nodes(_identical_source(nx.Graph), _MAPPING)
    fnx_relabelled = fnx.relabel_nodes(_identical_source(fnx.Graph), _MAPPING)

    expected = getattr(nx, metric)(nx_relabelled)
    actual = getattr(fnx, metric)(fnx_relabelled)

    assert list(actual) == list(expected), f"{metric} key ORDER diverged"
    for node, value in expected.items():
        assert actual[node] == pytest.approx(value)


@pytest.mark.parametrize("metric", _NODE_METRICS)
def test_metric_key_order_matches_networkx_before_relabelling(metric):
    """Control: the same comparison on the unrelabelled graph.

    If this fails too, the divergence is not about relabelling at all, and the
    test above would otherwise be blamed for it.
    """
    expected = getattr(nx, metric)(_identical_source(nx.Graph))
    actual = getattr(fnx, metric)(_identical_source(fnx.Graph))
    assert list(actual) == list(expected)


def test_construction_order_changes_node_order_on_both_libraries():
    """Pin the pitfall itself, as SHARED behaviour.

    A probe that builds one side nodes-first and the other edges-first compares
    two different graphs. Asserting that both libraries behave the same way here
    is what makes the identical-source discipline above a requirement rather
    than a superstition — and if networkx ever stops doing this, the tests above
    need re-deriving, and this one says so first.
    """
    for cls_nx, cls_fnx in ((nx.Graph, fnx.Graph), (nx.DiGraph, fnx.DiGraph)):
        nodes_first_nx = cls_nx()
        nodes_first_nx.add_nodes_from(range(4))
        nodes_first_nx.add_edges_from(_EDGES)
        edges_first_nx = cls_nx()
        edges_first_nx.add_edges_from(_EDGES)

        nodes_first_fnx = cls_fnx()
        nodes_first_fnx.add_nodes_from(range(4))
        nodes_first_fnx.add_edges_from(_EDGES)
        edges_first_fnx = cls_fnx()
        edges_first_fnx.add_edges_from(_EDGES)

        # The orders differ from each other...
        assert list(nodes_first_nx) != list(edges_first_nx)
        # ...and fnx reproduces networkx in BOTH constructions.
        assert list(nodes_first_fnx) == list(nodes_first_nx)
        assert list(edges_first_fnx) == list(edges_first_nx)
