"""br-r37-c1-rgmef — `G._adj[u][v] = {...}` raises where networkx accepts it.

networkx's `G._adj` IS a raw `dict`, and networkx's own algorithms mutate it in
place. fnx exposes an `AdjacencyView`, so item assignment into private storage
raises — `TypeError` on `Graph`, `AttributeError` on the other three.

    type(G._adj)    nx dict    fnx AdjacencyView
    type(G._node)   nx dict    fnx _PrivateNodeFacade

FOUND BY RE-AUDITING THE FAMILY, not by a bug report. An earlier ad-hoc check on
`get_edge_data` tested two dimensions and pronounced the surface understood; a
systematic sweep of the same accessor found eight divergences. Rebuilt as
`scripts/reference_semantics_probe.py` over 388 (accessor x dimension) cells,
the re-audit surfaced this — which no public-API probe could have seen, because
the private surface is exactly the one library code reaches for and the public
one is clean.

THE NODE SIDE IS FINE and is asserted below as the control: `G._node[n]['k'] = v`
and `G._node[new] = {}` both work. The defect is specific to adjacency, which is
what makes "fnx's private storage is read-only" the wrong summary and
"fnx's private ADJACENCY is read-only" the right one.

The exception TYPE also differs across classes, so a caller catching `TypeError`
on `Graph` will not catch `AttributeError` on `DiGraph`. That is pinned too: a
fix that unified the exception without allowing the write would be an
improvement, and this file would show it.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b", w=1.0)
        graph.add_edge("b", "c", w=2.0)
    return gnx, gfx


def _cell(cls_name):
    """The value shape a row maps to: attrs for simple, keydict for multi."""
    return {0: {"w": 7.0}} if cls_name.startswith("Multi") else {"w": 7.0}


# --- the incumbent contract, pinned so the target cannot drift -------------


@pytest.mark.parametrize("cls_name", ALL)
def test_networkx_private_adjacency_is_a_plain_mutable_dict(cls_name):
    gnx = _pair(cls_name)[0]
    assert isinstance(gnx._adj, dict)
    gnx._adj["a"]["zz"] = _cell(cls_name)
    assert "zz" in gnx["a"]


# --- the control: the node side already works ------------------------------


@pytest.mark.parametrize("cls_name", ALL)
def test_private_node_storage_accepts_mutation_in_both(cls_name):
    """The control that localises the defect to adjacency.

    If this failed too, the summary would be "private storage is read-only" and
    the fix would be a different, larger one.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph._node["a"]["tag"] = 7
        graph._node["fresh"] = {}
    assert gfx.nodes["a"]["tag"] == gnx.nodes["a"]["tag"] == 7
    assert ("fresh" in gfx._node) == ("fresh" in gnx._node) is True


# --- the divergence --------------------------------------------------------


# br-r37-c1-rgmef is FIXED FOR DiGraph and still open for the other three, for
# two different reasons that are worth keeping apart:
#
#   Graph        blocked in RUST. Its public row is the native `_fnx.AtlasView`
#                (br-r37-c1-ey6ob's C-slot win) and that pyclass is not declared
#                `subclass`, so no writable row subclass can be built in Python.
#                Using the Python `AtlasView` instead would make the private
#                row's read methods differ from the public row's, which
#                test_private_adj_read_path_stays_native.py forbids. A one-line
#                Rust change unblocks it.
#   Multi*       blocked in PYTHON. A private twin can be built, but its READS
#                diverge from the public view's, which the same lock catches.
_STILL_OPEN = {
    "Graph": "native _fnx.AtlasView row is not declared `subclass` in Rust",
    "MultiGraph": "private twin's reads diverge from the public view",
    "MultiDiGraph": "private twin's reads diverge from the public view",
}
_BY_CLASS = [
    pytest.param(
        name,
        marks=pytest.mark.xfail(
            strict=True, reason=f"br-r37-c1-rgmef: {_STILL_OPEN[name]}"
        ),
    )
    if name in _STILL_OPEN
    else name
    for name in ALL
]


@pytest.mark.parametrize("cls_name", _BY_CLASS)
def test_private_adjacency_item_assignment_reaches_the_graph(cls_name):
    """FIXED for DiGraph by br-r37-c1-rgmef; xfail elsewhere with the reason."""
    gfx = _pair(cls_name)[1]
    gfx._adj["a"]["zz"] = _cell(cls_name)
    assert "zz" in gfx["a"]


@pytest.mark.parametrize("cls_name", _BY_CLASS)
def test_private_adjacency_row_delete_reaches_the_graph(cls_name):
    """`del G._adj[u][v]` removes the edge, as it does on networkx's raw dict."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        del graph._adj["a"]["b"]
    assert gfx.has_edge("a", "b") == gnx.has_edge("a", "b") is False


def test_private_pred_assignment_writes_the_edge_in_the_right_DIRECTION():
    """`_pred[v][u] = cell` describes u -> v, so the endpoints must swap.

    A twin that ignored direction would write the edge backwards -- the one bug
    in this shape that reads correct at the assignment site.

    A DELIBERATE DIVERGENCE IS PINNED HERE, and it is not the one I first wrote.
    I asserted fnx would agree with networkx and it does not, because networkx
    does something no caller should rely on: `_pred[v][u] = cell` inserts into
    the pred dict ALONE, so `pred['a']` shows the neighbour while `has_edge` is
    False, the node is absent from `nodes`, and `edges()` omits it. Measured on
    networkx directly rather than assumed.

    fnx has ONE store and cannot represent half an edge, so it writes the whole
    edge -- and keeps `set(_adj) == set(_node)`, which networkx breaks here.
    """
    gfx = _pair("DiGraph")[1]
    gfx._pred["a"]["zz"] = {"w": 3.0}
    assert gfx.has_edge("zz", "a") is True
    assert gfx.has_edge("a", "zz") is False
    assert set(gfx._adj) == set(gfx._node)


def test_the_complete_pattern_library_code_uses_agrees_with_networkx():
    """Writing `_node`, `_succ` and `_pred` -- how networkx builds a digraph by
    hand -- gives identical graphs on both libraries."""
    gnx, gfx = _pair("DiGraph")
    for graph in (gnx, gfx):
        graph._node["zz"] = {}
        graph._succ["zz"] = {"a": {"w": 3.0}}
        graph._pred["a"]["zz"] = {"w": 3.0}
    assert sorted(gfx.edges()) == sorted(gnx.edges())
    assert sorted(gfx.nodes()) == sorted(gnx.nodes())
    assert sorted(gfx.pred["a"]) == sorted(gnx.pred["a"])


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.xfail(strict=True, reason="br-r37-c1-rgmef: multigraph keydicts are read-only too")
def test_private_adjacency_nested_attr_assignment_reaches_the_graph(cls_name):
    gfx = _pair(cls_name)[1]
    gfx._adj["a"]["b"]["w"] = 9.0
    assert gfx["a"]["b"]["w"] == 9.0


@pytest.mark.parametrize("cls_name", sorted(_STILL_OPEN))
def test_the_rejection_is_currently_inconsistent_across_classes(cls_name):
    """Records the SHAPE of the defect, and passes today.

    `Graph` raises `TypeError` while the other three raise `AttributeError`, so
    a caller cannot write one except clause. This is deliberately not an xfail:
    it documents current behaviour, and when br-r37-c1-rgmef is fixed the writes
    stop raising and this test needs deleting along with the xfails above.
    """
    gfx = _pair(cls_name)[1]
    with pytest.raises((TypeError, AttributeError)):
        gfx._adj["a"]["zz"] = _cell(cls_name)


@pytest.mark.parametrize("cls_name", ALL)
def test_public_adjacency_is_read_only_in_both(cls_name):
    """The public surface AGREES, which is why this hid.

    Any probe that stopped at the public API would report this family healthy.
    """
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        with pytest.raises(TypeError):
            graph.adj["a"]["zz"] = _cell(cls_name)
