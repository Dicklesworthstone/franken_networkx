"""relabel_nodes edge-case parity with networkx.

Relabeling has subtle behaviors: a non-injective mapping (two nodes -> one
label) MERGES those nodes, mapping to an existing node merges into it, a swap
must not lose edges, and copy vs in-place differ for collisions. These are
exactly the cases where a relabel implementation silently diverges. This pins
fnx to networkx on each.

No mocks: real fnx and real networkx.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def _g(lib):
    return lib.Graph([(0, 1), (1, 2), (2, 3), (0, 3)])


def _edges(g):
    return sorted(tuple(sorted((str(u), str(v)))) for u, v in g.edges())


def _nodes(g):
    return sorted(map(str, g.nodes()))


def _assert_same(fg, ng):
    assert _edges(fg) == _edges(ng)
    assert _nodes(fg) == _nodes(ng)


def test_non_injective_mapping_merges_nodes():
    # 1 and 2 both -> 'X' merges them.
    _assert_same(
        fnx.relabel_nodes(_g(fnx), {1: "X", 2: "X"}, copy=True),
        nx.relabel_nodes(_g(nx), {1: "X", 2: "X"}, copy=True),
    )


def test_collision_inplace_contract():
    def outcome(lib, g):
        try:
            return ("ok", _edges(lib.relabel_nodes(g, {1: "X", 2: "X"}, copy=False)))
        except Exception as exc:  # noqa: BLE001
            return ("err", type(exc).__name__)

    f = outcome(fnx, _g(fnx))
    n = outcome(nx, _g(nx))
    assert f[0] == n[0]
    if f[0] == "err":
        assert f[1] == n[1]


def test_merge_into_existing_node():
    # Mapping 3 -> 0 merges node 3 into existing node 0.
    _assert_same(
        fnx.relabel_nodes(_g(fnx), {3: 0}),
        nx.relabel_nodes(_g(nx), {3: 0}),
    )


def test_swap_preserves_edges():
    _assert_same(
        fnx.relabel_nodes(_g(fnx), {0: 1, 1: 0}),
        nx.relabel_nodes(_g(nx), {0: 1, 1: 0}),
    )


def test_partial_mapping():
    _assert_same(
        fnx.relabel_nodes(_g(fnx), {0: "a"}),
        nx.relabel_nodes(_g(nx), {0: "a"}),
    )


def test_convert_node_labels_to_integers():
    fg = fnx.convert_node_labels_to_integers(
        fnx.Graph([("a", "b"), ("b", "c")]), first_label=10
    )
    ng = nx.convert_node_labels_to_integers(
        nx.Graph([("a", "b"), ("b", "c")]), first_label=10
    )
    _assert_same(fg, ng)
