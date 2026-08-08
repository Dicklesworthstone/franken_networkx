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


# br-r37-c1-sfemy: `_nodes` / `_edges` above map every label through `str()` and
# sort. On THIS surface that is a poor fit twice over: relabel maps between
# types (``{3: 0}`` produces an int label, ``{0: "a"}`` a str), so a relabel
# emitting the string "0" where networkx emits the int 0 compares equal; and
# relabel node ORDER is load-bearing enough that two other modules exist for it
# (test_relabel_node_order_parity, test_relabel_order_parity_vs_networkx).
_MAPPINGS = [
    ("non_injective_merge", {1: "X", 2: "X"}),
    ("merge_into_existing", {3: 0}),
    ("swap", {0: 1, 1: 0}),
    ("partial", {0: "a"}),
]


@pytest.mark.parametrize("name,mapping", _MAPPINGS)
def test_relabel_preserves_label_types_and_order(name, mapping):
    fg = fnx.relabel_nodes(_g(fnx), mapping)
    ng = nx.relabel_nodes(_g(nx), mapping)
    # `==` on raw lists compares label VALUE and TYPE, not str(label).
    assert list(fg.nodes()) == list(ng.nodes())
    assert [type(n) for n in fg.nodes()] == [type(n) for n in ng.nodes()]
    assert list(fg.edges()) == list(ng.edges())


def test_convert_node_labels_to_integers_label_types_and_order():
    fg = fnx.convert_node_labels_to_integers(
        fnx.Graph([("a", "b"), ("b", "c")]), first_label=10
    )
    ng = nx.convert_node_labels_to_integers(
        nx.Graph([("a", "b"), ("b", "c")]), first_label=10
    )
    assert list(fg.nodes()) == list(ng.nodes())
    assert [type(n) for n in fg.nodes()] == [type(n) for n in ng.nodes()]
    assert list(fg.edges()) == list(ng.edges())


def _attributed(lib):
    """br-r37-c1-sfemy: the fixture above carries NO attributes, so nothing
    tested what relabel does with them — and a MERGE has to resolve a conflict.
    """
    g = lib.Graph()
    for n in range(4):
        g.add_node(n, tag=f"t{n}")
    for u, v in [(0, 1), (1, 2), (2, 3), (0, 3)]:
        g.add_edge(u, v, w=u * 10 + v)
    return g


@pytest.mark.parametrize("name,mapping", _MAPPINGS)
def test_relabel_carries_attributes(name, mapping):
    fg = fnx.relabel_nodes(_attributed(fnx), mapping)
    ng = nx.relabel_nodes(_attributed(nx), mapping)
    assert {str(k): dict(v) for k, v in fg.nodes(data=True)} == (
        {str(k): dict(v) for k, v in ng.nodes(data=True)}
    )
    assert sorted(
        (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in fg.edges(data=True)
    ) == sorted(
        (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in ng.edges(data=True)
    )


def test_merge_resolves_attribute_conflict_last_writer_wins():
    """The subtle half of a non-injective merge: nodes 1 and 2 both become "X",
    so ONE set of node attributes survives. networkx keeps the LAST mapped
    node's — ``tag == "t2"``, not "t1" — and fnx matches. Pinning the winner
    matters because a merge that kept the first would still produce the right
    node and edge sets and pass every other assertion in this module
    (br-r37-c1-sfemy).
    """
    fg = fnx.relabel_nodes(_attributed(fnx), {1: "X", 2: "X"})
    ng = nx.relabel_nodes(_attributed(nx), {1: "X", 2: "X"})
    assert fg.nodes["X"] == ng.nodes["X"]
    assert fg.nodes["X"]["tag"] == "t2"
