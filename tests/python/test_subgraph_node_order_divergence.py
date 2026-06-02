"""Documented divergence + behavior lock for subgraph/edge_subgraph node order.

NetworkX's ``G.subgraph(nbunch)`` / ``edge_subgraph`` return a view whose node
iteration order is produced by ``FilterAtlas.__iter__``. That iterator has a
size-based optimization: when ``2 * len(induced_nodes) < len(G)`` it iterates
the *induced node set* (a Python ``set`` — CPython hash-table slot order)
instead of the original graph's insertion order. So on a large graph the
node order of a small induced subgraph is whatever CPython's ``set`` iteration
happens to be (e.g. ``list({8,3,1,5}) == [8, 1, 3, 5]``); on a small graph
(``2*|sub| >= |G|``) it falls back to original-graph order.

franken_networkx's SubgraphView always iterates in stable original-graph
(insertion-filtered) order. That is:
  * **identical to networkx whenever nx does NOT take the set-order shortcut**
    (the common ``2*|sub| >= |G|`` regime), and
  * a deliberate, defensible divergence in the shortcut regime — replicating
    CPython's ``set`` hash-ordering in the Rust-backed view is impractical
    (it varies by node hash / Python build) and depends on ``set`` ordering
    that is explicitly undocumented and not part of nx's API contract.

This test locks fnx's deterministic order and documents the nx divergence so a
future probe doesn't re-file it as a bug, and so a regression in fnx's stable
ordering is caught. See the intentional-divergences ledger.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _build(mod, n_extra):
    g = mod.Graph()
    # Deliberately non-monotonic insertion order.
    g.add_nodes_from([5, 3, 8, 1] + list(range(100, 100 + n_extra)))
    g.add_edges_from([(5, 3), (3, 8), (8, 1), (3, 1)])
    return g


SUBSET = [8, 3, 1, 5]
SUBSET_SET = {8, 3, 1, 5}


def _original_order(g):
    return [n for n in g.nodes() if n in SUBSET_SET]


@pytest.mark.parametrize("n_extra", [0, 1, 2, 3])  # 2*4 >= total -> nx uses original order
def test_subgraph_order_matches_nx_when_no_set_shortcut(n_extra):
    gn = _build(nx, n_extra)
    gf = _build(fnx, n_extra)
    assert list(gn.subgraph(SUBSET).nodes()) == list(gf.subgraph(SUBSET).nodes())
    # ...and it is the stable original-graph order.
    assert list(gf.subgraph(SUBSET).nodes()) == _original_order(gf)


@pytest.mark.parametrize("n_extra", [0, 1, 2, 3, 5, 8])
def test_fnx_subgraph_order_is_always_stable_original_order(n_extra):
    # fnx's contract: subgraph node order is independent of graph size and of
    # the nbunch argument's order — always the original-graph insertion order
    # filtered to the induced set.
    gf = _build(fnx, n_extra)
    expected = _original_order(gf)
    assert list(gf.subgraph(SUBSET).nodes()) == expected
    assert list(gf.subgraph([1, 5, 8, 3]).nodes()) == expected  # nbunch order irrelevant
    assert list(gf.edge_subgraph([(5, 3), (3, 8), (8, 1)]).nodes()) == expected


def test_set_shortcut_regime_is_a_known_divergence():
    # In the shortcut regime (2*|sub| < |G|) nx iterates the induced set in
    # CPython hash order; fnx keeps stable original order. We assert the
    # *shape* of the divergence (fnx stays original-order; the two contain the
    # same nodes) without hard-coding CPython's set order, which is not a
    # stable contract.
    gn = _build(nx, 8)   # total 12, subset 4 -> 8 < 12 -> shortcut on
    gf = _build(fnx, 8)
    nx_order = list(gn.subgraph(SUBSET).nodes())
    fnx_order = list(gf.subgraph(SUBSET).nodes())
    assert set(nx_order) == set(fnx_order) == SUBSET_SET  # same membership
    assert fnx_order == _original_order(gf)               # fnx stays original-order
    # Document that nx took its set-order shortcut here (order != original).
    assert nx_order == list(SUBSET_SET)  # nx == CPython set iteration of induced nodes
