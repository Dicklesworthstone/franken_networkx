"""br-r37-c1-2ndmw — the contract a native multigraph row view must preserve.

`Graph` gets native row views: `AdjacencyView.__getitem__` has

    if type(owner) is Graph and not _has_networkx_private_storage(owner):
        view = _fnx.AtlasView(owner, node)

so simple graphs reach a C-level `__getitem__` slot (and, since
br-r37-c1-ptiz2, a cached row node index). Every other class — DiGraph,
MultiGraph, MultiDiGraph — falls to the Python `AtlasView`, and the multigraph
branch of `AtlasView.__getitem__` short-circuits on its FIRST line:

    if self._fnx_multi_edge_owner is not None:
        return self._atlas()[node]

which bypasses the live-keydict, generation-cached and single-edge-native fast
paths below it. Measured, `Graph G[u][v]` is at parity (0.93-1.01x) while
`MultiGraph`/`MultiDiGraph` sit at 0.25-0.27x — a fixed ~810 ns per call, NOT a
complexity problem (see below).

WHAT THIS FILE IS FOR. Closing that gap means routing multigraph rows onto a
native view, and br-r37-c1-native_view_classes says routing a native view into
place is a PARITY change before it is a performance change. These tests pin the
observable contract FIRST, so the eventual lever is gated by them rather than
written and then justified.

TWO HYPOTHESES WERE TESTED AND REFUTED BEFORE THIS FILE WAS WRITTEN, and they
are recorded because both would have sent the lever the wrong way:

  * O(degree) per subscript. The comment on the simple-graph fast path says
    distinct `G[u][v]` was "0.04x vs nx precisely because each cold access built
    u's entire row (O(degree))". Multigraphs bypass that fix, so the natural
    guess is that they still pay it. They do not: fnx is FLAT in degree —
    1112.9 / 1084.1 / 1661.0 / 1420.7 ns at degree 2 / 20 / 200 / 2000, against
    a 1000x span. `_atlas()` returns an identity-stable `MultiAtlasView`, so the
    row is not rebuilt per call.
  * A view-vs-copy divergence. `G[u][v]` returns a non-identical object on each
    call in fnx, which is the same shape as the br-r37-c1-f3i50 defect in
    unkeyed `get_edge_data`. It is NOT a defect here: networkx behaves
    identically (non-identical wrapper, read-only, new-key insertion raises
    TypeError), and this file pins that agreement so a future native view cannot
    quietly "fix" it into a live mutable mapping.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name, edges):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        for u, v, attrs in edges:
            graph.add_edge(u, v, **attrs)
    return gnx, gfx


EDGES = [
    ("hub", "s0", {"w": 1.0}),
    ("hub", "s0", {"w": 2.0}),
    ("hub", "s1", {"w": 3.0}),
    ("s1", "s2", {"w": 4.0}),
    ("hub", "hub", {"w": 5.0}),
]


@pytest.mark.parametrize("cls_name", ALL)
def test_row_subscript_value_matches_networkx(cls_name):
    gnx, gfx = _pair(cls_name, EDGES)
    for u in ("hub", "s1"):
        for v in gnx[u]:
            assert dict(gfx[u][v]) == dict(gnx[u][v]), (cls_name, u, v)


@pytest.mark.parametrize("cls_name", MULTI)
def test_inner_attr_dict_identity_is_preserved(cls_name):
    """THE constraint on any faster path.

    `G[u][v][key]` must be the SAME live attr dict object across calls, because
    `G[u][v][key]['w'] = x` is the documented way to mutate an edge. A native
    view that returned freshly built inner dicts would pass every value
    comparison in this file and still break every caller that mutates.
    """
    gfx = _pair(cls_name, EDGES)[1]
    first = gfx["hub"]["s0"][0]
    assert gfx["hub"]["s0"][0] is first
    first["w"] = 99.0
    assert gfx["hub"]["s0"][0]["w"] == 99.0
    assert gfx.get_edge_data("hub", "s0", 0)["w"] == 99.0
    assert gfx.edges["hub", "s0", 0]["w"] == 99.0


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_outer_keydict_wrapper_matches_networkx_in_mutability(cls_name):
    """networkx's wrapper is READ-ONLY and non-identical; fnx must match.

    This is deliberately pinned because the same shape IS a real divergence one
    level over, in unkeyed `get_edge_data` (br-r37-c1-f3i50). The difference is
    that networkx returns the live keydict there and a read-only view here, so
    "make it live" is the correct fix in one place and a regression in the
    other.
    """
    gnx, gfx = _pair(cls_name, EDGES)
    for graph in (gnx, gfx):
        row_a, row_b = graph["hub"]["s0"], graph["hub"]["s0"]
        assert row_a is not row_b
        with pytest.raises(TypeError):
            row_a[7] = {"w": 7.0}


@pytest.mark.parametrize("cls_name", ALL)
def test_missing_keys_raise_the_same_exception_and_args(cls_name):
    """Type AND args — a type-only check reports false green (exception sweep)."""
    gnx, gfx = _pair(cls_name, EDGES)
    for u, v in [("hub", "absent"), ("s2", "hub")]:
        want = got = None
        try:
            gnx[u][v]
        except Exception as exc:  # noqa: BLE001 - comparing the exception itself
            want = (type(exc), exc.args)
        try:
            gfx[u][v]
        except Exception as exc:  # noqa: BLE001
            got = (type(exc), exc.args)
        assert got == want, (cls_name, u, v)


@pytest.mark.parametrize("cls_name", ALL)
def test_absent_row_raises_the_same_exception_and_args(cls_name):
    gnx, gfx = _pair(cls_name, EDGES)
    want = got = None
    try:
        gnx["nope"]
    except Exception as exc:  # noqa: BLE001
        want = (type(exc), exc.args)
    try:
        gfx["nope"]
    except Exception as exc:  # noqa: BLE001
        got = (type(exc), exc.args)
    assert got == want, cls_name


@pytest.mark.parametrize("cls_name", ALL)
def test_unhashable_subscript_raises_typeerror_like_networkx(cls_name):
    """nx reaches `self._adj[u][v]`, so an unhashable key is a TypeError."""
    gnx, gfx = _pair(cls_name, EDGES)
    with pytest.raises(TypeError):
        gnx["hub"][["unhashable"]]
    with pytest.raises(TypeError):
        gfx["hub"][["unhashable"]]
    with pytest.raises(TypeError):
        gnx[["unhashable"]]
    with pytest.raises(TypeError):
        gfx[["unhashable"]]


@pytest.mark.parametrize("cls_name", MULTI)
def test_keydict_order_matches_networkx(cls_name):
    """Parallel-edge key order is observable through iteration."""
    gnx, gfx = _pair(cls_name, EDGES)
    for graph in (gnx, gfx):
        graph.add_edge("hub", "s0", key="named", w=6.0)
        graph.add_edge("hub", "s0", w=7.0)
    assert list(gfx["hub"]["s0"]) == list(gnx["hub"]["s0"])
    assert [dict(d) for d in gfx["hub"]["s0"].values()] == [
        dict(d) for d in gnx["hub"]["s0"].values()
    ]


@pytest.mark.parametrize("cls_name", ALL)
def test_row_order_matches_networkx(cls_name):
    gnx, gfx = _pair(cls_name, EDGES)
    assert list(gfx["hub"]) == list(gnx["hub"])
    assert list(gfx["s1"]) == list(gnx["s1"])


@pytest.mark.parametrize("cls_name", ALL)
def test_self_loop_row_entry(cls_name):
    gnx, gfx = _pair(cls_name, EDGES)
    assert ("hub" in gfx["hub"]) == ("hub" in gnx["hub"])
    if "hub" in gnx["hub"]:
        assert dict(gfx["hub"]["hub"]) == dict(gnx["hub"]["hub"])


@pytest.mark.parametrize("cls_name", ALL)
def test_row_reflects_later_edge_mutation(cls_name):
    """A held row must be LIVE for edge changes — nx's rows are.

    A cached native row that froze its contents would pass every test above and
    fail here, which is the failure mode a generation stamp exists to prevent.
    """
    gnx, gfx = _pair(cls_name, EDGES)
    rnx, rfx = gnx["hub"], gfx["hub"]
    for graph in (gnx, gfx):
        graph.add_edge("hub", "late", w=8.0)
    assert ("late" in rfx) == ("late" in rnx)
    assert dict(rfx["late"]) == dict(rnx["late"])
    assert list(rfx) == list(rnx)


@pytest.mark.parametrize("cls_name", ALL)
def test_row_after_owner_node_removed_matches_networkx(cls_name):
    """The renumbering hazard, at the row level.

    Node removal renumbers indices underneath any cached row index. Whatever a
    held row does after its owner is removed, it must do what nx does.
    """
    gnx, gfx = _pair(cls_name, EDGES)
    rnx, rfx = gnx["hub"], gfx["hub"]
    for graph in (gnx, gfx):
        graph.remove_node("s1")
    assert list(rfx) == list(rnx), cls_name
    for v in list(rnx):
        assert dict(rfx[v]) == dict(rnx[v])
    # and a freshly taken row agrees too
    assert list(gfx["hub"]) == list(gnx["hub"])


@pytest.mark.parametrize("cls_name", ALL)
def test_row_index_stability_across_node_removal(cls_name):
    """br-r37-c1-ptiz2's stamp hazard, stated as observable behaviour.

    Removing an EARLIER node renumbers every later index. A row view holding an
    unstamped index would name a different node afterwards. Warm a row, remove
    an earlier node, then read a LATER row and check it is still its own.
    """
    edges = [(f"n{i}", f"n{i + 1}", {"tag": f"e{i}"}) for i in range(6)]
    gnx, gfx = _pair(cls_name, edges)
    warm_nx, warm_fx = gnx["n4"], gfx["n4"]
    assert list(warm_fx) == list(warm_nx)
    for graph in (gnx, gfx):
        graph.remove_node("n0")
    assert list(gfx["n4"]) == list(gnx["n4"]), cls_name
    for v in list(gnx["n4"]):
        assert dict(gfx["n4"][v]) == dict(gnx["n4"][v]), (cls_name, v)


@pytest.mark.parametrize("cls_name", ALL)
def test_subgraph_rows_match_networkx(cls_name):
    """Filtered rows take a different atlas; the gate must not swallow them."""
    gnx, gfx = _pair(cls_name, EDGES)
    keep = ["hub", "s0", "s1"]
    snx, sfx = gnx.subgraph(keep), gfx.subgraph(keep)
    assert list(sfx["hub"]) == list(snx["hub"])
    for v in list(snx["hub"]):
        assert dict(sfx["hub"][v]) == dict(snx["hub"][v])
    with pytest.raises(KeyError):
        snx["hub"]["s2"]
    with pytest.raises(KeyError):
        sfx["hub"]["s2"]


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_directed_row_is_successors_only(cls_name):
    """`G[u]` is the SUCC row for directed classes, not the union."""
    gnx, gfx = _pair(cls_name, EDGES)
    assert list(gfx["s1"]) == list(gnx["s1"])
    assert ("hub" in gfx["s1"]) == ("hub" in gnx["s1"])
    assert list(gfx.pred["s1"]) == list(gnx.pred["s1"])


@pytest.mark.parametrize("cls_name", ALL)
def test_row_mapping_protocol_matches_networkx(cls_name):
    """len/iter/contains/get/keys/items, not just __getitem__.

    A native row view has to serve the whole Mapping surface; a lever that only
    routed __getitem__ would leave these on the old path and could diverge.
    """
    gnx, gfx = _pair(cls_name, EDGES)
    rnx, rfx = gnx["hub"], gfx["hub"]
    assert len(rfx) == len(rnx)
    assert list(iter(rfx)) == list(iter(rnx))
    assert ("s0" in rfx) == ("s0" in rnx)
    assert ("absent" in rfx) == ("absent" in rnx)
    assert rfx.get("absent") is rnx.get("absent")
    assert list(rfx.keys()) == list(rnx.keys())
    assert [k for k, _ in rfx.items()] == [k for k, _ in rnx.items()]


@pytest.mark.parametrize("cls_name", ALL)
def test_non_string_node_keys_round_trip(cls_name):
    """The native path is exact-`str` gated; other key types must still work."""
    edges = [(1, 2, {"w": 1.0}), (2, (3, 4), {"w": 2.0}), (1, 1, {"w": 3.0})]
    gnx, gfx = _pair(cls_name, edges)
    for u in (1, 2):
        assert list(gfx[u]) == list(gnx[u]), (cls_name, u)
        for v in list(gnx[u]):
            assert dict(gfx[u][v]) == dict(gnx[u][v]), (cls_name, u, v)


def test_the_gate_this_bead_is_about_is_still_where_it_is_claimed():
    """Pins the PREMISE, so this file fails loudly once the lever lands.

    br-r37-c1-2ndmw claims simple Graph reaches a native row view and the other
    three classes do not. If someone widens that gate, these tests should be
    re-read as the parity gate for the new path rather than silently continuing
    to pass against the old one.
    """
    g = fnx.Graph()
    g.add_edge("a", "b")
    m = fnx.MultiGraph()
    m.add_edge("a", "b")
    graph_row_is_native = type(g["a"]).__module__.startswith("franken_networkx")
    assert graph_row_is_native
    getter = type(m["a"]).__dict__.get("__getitem__")
    assert getter is None or type(getter).__name__ == "function", (
        "MultiGraph row __getitem__ is no longer a Python function — the "
        "br-r37-c1-2ndmw lever may have landed; re-read this file as its "
        "parity gate"
    )
