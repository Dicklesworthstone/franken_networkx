"""``copy.copy(G)`` must share storage with its source, as networkx's does.

br-r37-c1-copyshare-2h5uj. networkx defines no ``__copy__`` on Graph, so ``copy.copy(G)``
takes the default: a new instance whose ``__dict__`` is copied shallowly, which means
``_adj`` and ``_node`` are the SAME dict objects. Everything is therefore shared -- the
graph attrs dict, every node and edge attr dict, and the STRUCTURE itself: adding a node or
an edge to the source appears in the copy.

fnx shares only the graph attrs dict. Measured against networkx on all four classes by
writing through the SOURCE and asking what the copy observes, 16 of 20 cells diverge. So
``copy.copy(G)`` in fnx behaves roughly like ``G.copy()``, which is a different operation.

WHY THIS IS XFAIL RATHER THAN FIXED. It is not reachable by re-pointing ``_adj`` / ``_node``
at the source's mappings: br-r37-c1-4wqn9 tried that and it produced SILENT WRITE-LOSS --
``h.add_edge`` wrote to h's own Rust store while ``h.edges`` read through the override
pointing at g. Sharing requires two Python graph objects backed by ONE Rust store, which
the store does not currently support (br-r37-c1-himzq is the neighbouring gap). The xfails
are ``strict=True`` so they fail loudly the moment that capability lands and this module
turns into the acceptance test for it.

The graph-attrs row is NOT xfail: the shim shares that dict explicitly today, and it is
carried here so a future change cannot quietly drop the one part that does work.
"""

import copy as copymod

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(module, cls_name):
    graph = getattr(module, cls_name)()
    graph.graph["gattr"] = "orig"
    graph.add_node("a", nattr="orig")
    graph.add_edge("a", "b", eattr="orig")
    return graph


def _edge_attrs(graph, cls_name):
    return graph["a"]["b"][0] if cls_name.startswith("Multi") else graph["a"]["b"]


def _observe(cls_name, mutate, observe):
    """Write through the SOURCE, report what the copy sees, for both libraries."""
    seen = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        source = _build(module, cls_name)
        duplicate = copymod.copy(source)
        mutate(source, cls_name)
        seen[name] = observe(duplicate, cls_name)
    return seen


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_shares_the_graph_attrs_dict(cls_name):
    """The one kind of sharing fnx already does. Not xfail -- a regression guard."""
    seen = _observe(
        cls_name,
        lambda g, c: g.graph.__setitem__("gattr", "changed"),
        lambda g, c: g.graph.get("gattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: copy.copy must share the graph attrs dict. networkx gave "
        f"{seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-copyshare-2h5uj: copy.copy does not share node attr dicts",
)
@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_shares_node_attr_dicts(cls_name):
    seen = _observe(
        cls_name,
        lambda g, c: g.nodes["a"].__setitem__("nattr", "changed"),
        lambda g, c: g.nodes["a"].get("nattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: networkx gave {seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-copyshare-2h5uj: copy.copy does not share edge attr dicts",
)
@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_shares_edge_attr_dicts(cls_name):
    seen = _observe(
        cls_name,
        lambda g, c: _edge_attrs(g, c).__setitem__("eattr", "changed"),
        lambda g, c: _edge_attrs(g, c).get("eattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: networkx gave {seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )


@pytest.mark.xfail(
    strict=True,
    reason="br-r37-c1-copyshare-2h5uj: copy.copy does not share structure (_adj/_node)",
)
@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("what", ["node", "edge"])
def test_shallow_copy_shares_structure(cls_name, what):
    """The row that decides the fix: nx shares `_adj`/`_node` outright.

    A write-proxying attr mapping would cover the two attribute rows above and still fail
    here, so this is what says the fix has to be a shared backing store rather than a
    smarter mapping object.
    """
    if what == "node":
        seen = _observe(
            cls_name,
            lambda g, c: g.add_node("zz"),
            lambda g, c: "zz" in g,
        )
    else:
        seen = _observe(
            cls_name,
            lambda g, c: g.add_edge("q", "r"),
            lambda g, c: g.has_edge("q", "r"),
        )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: adding a {what} to the source must be visible in copy.copy's result. "
        f"networkx gave {seen['nx']!r}, fnx gave {seen['fnx']!r}."
    )
