"""Parity guard: native 4-tuple explicit-key MultiDiGraph edge batch.

br-edgekeyedbatch (bt). add_edges_from with EXPLICIT-KEY 4-tuples ``(u, v, key, attrs)``
on a fresh MultiDiGraph bailed the auto-key batch (which only takes 2-3 tuples) and ran
the per-edge PyO3 loop (~0.33x vs nx). A keyed batch (collect-then-commit, reusing the
auto-key commit's IndexMap insertion-order key storage) brings it to ~parity (~4.7x faster
than per-edge). It bails to per-edge for anything outside the safe subset — custom/string
keys, negative keys, non-scalar attrs, duplicate (u,v,key), non-fresh graph — so all of
nx's keyed/error/update contracts are preserved.
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
    return edges, list(g.nodes(data=True))


def _assert_parity(edges):
    gn = nx.MultiDiGraph()
    gf = fnx.MultiDiGraph()
    gn.add_edges_from(list(edges))
    gf.add_edges_from(list(edges))
    assert _sig(gn) == _sig(gf)
    return gf


def test_sequential_keys():
    _assert_parity([(i, i + 1, 0, {"weight": i}) for i in range(10)])


def test_parallel_keys_one_pair():
    _assert_parity([(0, 1, k, {"weight": k * 2}) for k in range(12)])


def test_gapped_and_out_of_order_keys():
    _assert_parity(
        [
            (0, 1, 3, {"a": 1}), (0, 1, 1, {"a": 2}), (0, 1, 2, {"a": 3}),
            (2, 3, 0, {"a": 4}), (2, 3, 1, {"a": 5}), (0, 1, 0, {"a": 6}),
            (4, 5, 9, {"a": 7}), (4, 5, 2, {"a": 8}), (6, 7, 0, {"a": 9}),
        ]
    )


def test_duplicate_uvkey_overwrite_bails_to_peredge():
    # nx: a later (u,v,key) overwrites the earlier edge's data. The batch must bail
    # so the per-edge path replays that exactly.
    _assert_parity(
        [
            (0, 1, 0, {"w": 1}), (2, 3, 0, {"w": 2}), (0, 1, 0, {"w": 99}),
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


def test_none_attr_value():
    _assert_parity([(i, i + 1, 0, {"x": None, "w": i}) for i in range(10)])


def test_small_batch_per_edge():
    _assert_parity([(0, 1, 0, {"w": 1}), (1, 2, 0, {"w": 2})])


def test_attr_dict_identity_and_post_mutation():
    gf = fnx.MultiDiGraph()
    gf.add_edges_from([(i, i + 1, 0, {"weight": i}) for i in range(10)])
    assert gf[0][1][0] is gf[0][1][0]
    gf[0][1][0]["weight"] = 777
    assert gf[0][1][0]["weight"] == 777


def test_auto_add_after_keyed_batch_new_edge_key():
    eb = [(0, 1, k, {"w": k}) for k in [0, 2, 5]] + [
        (i, i + 1, 0, {"w": i}) for i in range(2, 9)
    ]
    gn = nx.MultiDiGraph()
    gf = fnx.MultiDiGraph()
    gn.add_edges_from(eb)
    gf.add_edges_from(eb)
    gn.add_edge(0, 1, weight=100)  # auto-key: new_edge_key over {0,2,5}
    gf.add_edge(0, 1, weight=100)
    assert _sig(gn) == _sig(gf)
