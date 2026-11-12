"""Parity guard: native fresh 4-tuple explicit-key MultiGraph edge batch.

br-edgekeyedbatch (bt). add_edges_from with EXPLICIT-KEY 4-tuples ``(u, v, key, attrs)``
on a FRESH MultiGraph had no native batch (MG's "fresh_keyed" collector is actually a
3-tuple auto-key one), so it ran the per-edge PyO3 loop (~0.31x vs nx). A fresh 4-tuple
collector (node first-seen order + given (u,v) edge order = the per-edge symmetric-adjacency
layout) reuses the auto-key commit and brings it to ~parity (~4x faster than per-edge).

The undirected risk is edges() ORIENTATION, so these assert byte-identical output (orientation,
node order, keys, attrs), including reverse-orientation duplicates of the same undirected edge
and self-loops; that the canonical ``(min(u,v), max(u,v), key)`` dup bails to per-edge; and that
custom/negative keys and non-scalar attrs bail.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None

pytestmark = pytest.mark.skipif(nx is None, reason="networkx not installed")


def _sig(g):
    edges = [
        (str(u), str(v), str(k), tuple(sorted(d.items())))
        for u, v, k, d in g.edges(keys=True, data=True)
    ]
    return edges, list(map(str, g.nodes()))


def _assert_parity(edges):
    gn = nx.MultiGraph()
    gf = fnx.MultiGraph()
    gn.add_edges_from(list(edges))
    gf.add_edges_from(list(edges))
    assert _sig(gn) == _sig(gf)


def test_sequential_keys():
    _assert_parity([(i, i + 1, 0, {"weight": i}) for i in range(10)])


def test_parallel_keys_one_pair():
    _assert_parity([(0, 1, k, {"w": k * 2}) for k in range(12)])


def test_gapped_and_out_of_order_keys():
    _assert_parity(
        [
            (0, 1, 3, {"a": 1}), (0, 1, 1, {"a": 2}), (2, 3, 0, {"a": 3}),
            (0, 1, 2, {"a": 4}), (4, 5, 9, {"a": 5}), (4, 5, 2, {"a": 6}),
            (2, 3, 1, {"a": 7}), (0, 1, 0, {"a": 8}), (6, 7, 0, {"a": 9}),
        ]
    )


def test_reverse_orientation_same_undirected_edge():
    _assert_parity(
        [
            (1, 0, 0, {"a": 1}), (2, 3, 0, {"a": 2}), (0, 1, 1, {"a": 3}),
            (4, 5, 0, {"a": 4}), (5, 4, 1, {"a": 5}), (6, 7, 0, {"a": 6}),
            (8, 9, 0, {"a": 7}), (3, 2, 1, {"a": 8}), (7, 6, 2, {"a": 9}),
        ]
    )


def test_self_loops():
    _assert_parity([(i, i, 0, {"w": i}) for i in range(10)])


def test_canonical_duplicate_bails_to_peredge():
    # (1,0,0) == (0,1,0) undirected; nx overwrites -> batch must bail.
    _assert_parity(
        [
            (0, 1, 0, {"w": 1}), (2, 3, 0, {"w": 2}), (1, 0, 0, {"w": 99}),
            (4, 5, 0, {"w": 3}), (6, 7, 0, {"w": 4}), (8, 9, 0, {"w": 5}),
            (1, 2, 0, {"w": 6}), (3, 4, 0, {"w": 7}), (5, 6, 0, {"w": 8}),
        ]
    )


def test_nonscalar_attr_bails():
    _assert_parity([(i, i + 1, 0, {"meta": [1, 2], "w": i}) for i in range(10)])


def test_custom_string_keys_bail():
    _assert_parity([(i, i + 1, f"k{i}", {"w": i}) for i in range(10)])


def test_negative_key_bails():
    _assert_parity([(i, i + 1, -1 if i == 0 else i, {"w": i}) for i in range(10)])


def test_attr_identity_and_post_mutation():
    gf = fnx.MultiGraph()
    gf.add_edges_from([(i, i + 1, 0, {"weight": i}) for i in range(10)])
    assert gf[0][1][0] is gf[0][1][0]
    gf[0][1][0]["weight"] = 777
    assert gf[0][1][0]["weight"] == 777


def test_auto_add_after_fresh_keyed_batch_new_edge_key():
    eb = [(0, 1, k, {"w": k}) for k in [0, 2, 5]] + [
        (i, i + 1, 0, {"w": i}) for i in range(2, 9)
    ]
    gn = nx.MultiGraph()
    gf = fnx.MultiGraph()
    gn.add_edges_from(eb)
    gf.add_edges_from(eb)
    gn.add_edge(0, 1, weight=100)
    gf.add_edge(0, 1, weight=100)
    assert _sig(gn) == _sig(gf)
