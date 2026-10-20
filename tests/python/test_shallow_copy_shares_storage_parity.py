"""``copy.copy(G)`` must share storage with its source, as networkx's does.

br-r37-c1-copyshare-2h5uj / br-r37-c1-epic-storage-architecture-yr2oc.3:
networkx defines no ``__copy__`` on Graph, so ``copy.copy(G)`` takes the default:
a new instance whose ``__dict__`` is copied shallowly, which means ``_adj`` and
``_node`` are the SAME dict objects. Everything is therefore shared -- the graph
attrs dict, every node and edge attr dict, and the STRUCTURE itself: adding a
node or an edge to the source appears in the copy, and vice versa.
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
    seen = _observe(
        cls_name,
        lambda g, c: g.graph.__setitem__("gattr", "changed"),
        lambda g, c: g.graph.get("gattr"),
    )
    assert seen["fnx"] == seen["nx"], (
        f"{cls_name}: copy.copy must share the graph attrs dict. networkx gave "
        f"{seen['nx']!r}, fnx gave {seen['fnx']!r}."
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


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("what", ["node", "edge"])
def test_shallow_copy_shares_structure(cls_name, what):
    """nx shares `_adj`/`_node` outright so structural mutations are visible in both."""
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


@pytest.mark.parametrize("cls_name", CLASSES)
def test_shallow_copy_bidirectional_mutations_and_private_dict_identity(cls_name):
    fg = _build(fnx, cls_name)
    ng = _build(nx, cls_name)
    fc = copymod.copy(fg)
    nc = copymod.copy(ng)

    assert fc.graph is fg.graph
    assert fc._node is fg._node
    assert fc._adj is fg._adj
    if fg.is_directed():
        assert fc._succ is fg._succ
        assert fc._pred is fg._pred

    fc.add_node("from_copy", tag=7)
    nc.add_node("from_copy", tag=7)
    fc.add_edge("b", "from_copy", weight=3.5)
    nc.add_edge("b", "from_copy", weight=3.5)

    assert ("from_copy" in fg) == ("from_copy" in ng) is True
    assert fg.nodes["from_copy"] == ng.nodes["from_copy"] == {"tag": 7}
    assert fg.has_edge("b", "from_copy") == ng.has_edge("b", "from_copy") is True
    assert dict(fg.degree()) == dict(ng.degree())

