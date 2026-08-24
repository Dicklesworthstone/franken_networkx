"""A held row view disagrees with networkx after its own node is removed and re-added.

FOUND BY A SEEDED MUTATION FUZZER, not by reading code, and it is PRE-EXISTING:
the identical divergence reproduces byte-for-byte on builds either side of
br-r37-c1-2ndmw's row-membership index path, so it is not caused by that change.

THE SHAPE. Hold `row = G.adj[u]`, remove `u`, then add `u` back with a different
edge. networkx's `AtlasView` wraps the `_adj[u]` DICT OBJECT, and removing the
node detaches that dict — so the held view keeps reporting the pre-removal
neighbours forever, and never sees the re-added ones. FrankenNetworkX's row view
reads live by node NAME, so once `u` exists again the same held view reports the
NEW neighbours:

    G = MultiGraph(); G.add_edge("u", "a")
    row = G.adj["u"]
    G.remove_node("u")
    G.add_edge("u", "b")

    networkx : "a" in row -> True    "b" in row -> False    len(row) == 1
    fnx      : "a" in row -> False   "b" in row -> True     len(row) == 1

Neither is a counting bug — both report one neighbour. They disagree about WHICH
graph the held view still belongs to. networkx binds the view to an object
identity that a removal destroys; fnx binds it to a name that a re-add revives.

WHY IT IS NARROW, and the reason the passing tests below matter as much as the
xfailing one: liveness is otherwise IDENTICAL. Holding a row across an edge
addition, an edge removal, an unrelated node addition, or an unrelated node
REMOVAL (which renumbers internal positions) agrees with networkx exactly. Only
re-identification of the row's own node diverges. Any fix must preserve all four
of those, which is why they are pinned here rather than left implicit — the
obvious repair, detaching the row view on node removal, is easy to over-apply.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _probe(mod, cls_name, script):
    g = getattr(mod, cls_name)()
    return script(g)


def _both(cls_name, script):
    return _probe(nx, cls_name, script), _probe(fnx, cls_name, script)


# --------------------------------------------------------------- the divergence


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_after_node_removal_and_readd_matches_networkx(cls_name):
    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"]
        g.remove_node("u")
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("source", ["adj", "getitem"])
def test_held_row_after_batch_removal_and_readd_matches_networkx(cls_name, source):
    """Both public row spellings must detach before ``remove_nodes_from``."""

    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"] if source == "adj" else g["u"]
        g.remove_nodes_from(["missing", "u"])
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}/{source}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("source", ["succ", "pred"])
def test_held_directed_row_after_removal_and_readd_matches_networkx(cls_name, source):
    """The directed aliases carry independent row caches and both detach."""

    def script(g):
        if source == "succ":
            g.add_edge("u", "a")
            row = g.succ["u"]
            g.remove_node("u")
            g.add_edge("u", "b")
            old, new = "a", "b"
        else:
            g.add_edge("a", "u")
            row = g.pred["u"]
            g.remove_node("u")
            g.add_edge("b", "u")
            old, new = "a", "b"
        return {"old": old in row, "new": new in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}/{source}: nx={want} fnx={got}"


# ------------------------------------------------- the liveness that AGREES today
# These pass now and must keep passing: they bound any repair of the case above.


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_tracks_edge_addition(cls_name):
    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"]
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_tracks_edge_removal(cls_name):
    def script(g):
        g.add_edge("u", "a")
        g.add_edge("u", "b")
        row = g.adj["u"]
        g.remove_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_survives_unrelated_node_addition(cls_name):
    def script(g):
        g.add_edge("u", "a")
        row = g.adj["u"]
        g.add_node("newnode")
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_survives_unrelated_node_removal(cls_name):
    """The renumbering case. Removing a node reorders internal positions, and the
    row view caches its node's position — so this is the one that would break if
    that cache were not generation-stamped."""

    def script(g):
        g.add_edge("u", "a")
        g.add_node("z")
        row = g.adj["u"]
        g.remove_node("z")
        g.add_edge("u", "b")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_held_row_of_an_untouched_node_is_unaffected_by_a_neighbours_removal(cls_name):
    """Removing the NEIGHBOUR, not the row's own node, must agree — this is the
    boundary of the divergence and the case a fix is most likely to overreach on."""

    def script(g):
        g.add_edge("u", "a")
        g.add_edge("u", "b")
        row = g.adj["u"]
        g.remove_node("a")
        return {"a": "a" in row, "b": "b" in row, "len": len(row)}

    want, got = _both(cls_name, script)
    assert got == want, f"{cls_name}: nx={want} fnx={got}"
