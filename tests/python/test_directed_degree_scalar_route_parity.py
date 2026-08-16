"""Parity lock for br-r37-c1-5noxi — the pre-resolved scalar degree route.

`G.in_degree[n]` used to re-derive, on every subscript, three things that cannot
change for the life of the view: whether the weight is None, whether the graph
is a filtered or reverse view, and which direction the view is. That was two
Python frames and an isinstance pair around a native call, on an operation
networkx completes in ~0.15us end to end.

The fix resolves them once in `__init__` and stores the native counter. This is
a PERFORMANCE change, so what needs locking is that the decision made at
construction is the same one the old per-call logic would have made — every
route it must NOT take:

* a FILTERED graph (subgraph / edge_subgraph) must keep the adjacency walk,
  because the native counters read the Rust base, which is empty for a view
  (br-r37-c1-vfytj);
* a REVERSE view likewise;
* a WEIGHTED view must not use the unweighted counter;
* the missing-node KeyError (br-r37-c1-i89jx) and the unhashable TypeError must
  survive, since the guard now sits after a different call.

Every assertion is differential against live networkx.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

DIRECTED = ["DiGraph", "MultiDiGraph"]
ACCESSORS = ["in_degree", "out_degree", "degree"]


def _build(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", weight=2.0)
    graph.add_edge("b", "c", weight=3.0)
    graph.add_edge("c", "a", weight=4.0)
    graph.add_node("iso")
    return graph


GRAPH_KINDS = {
    "plain": lambda g: g,
    "subgraph": lambda g: g.subgraph(["a", "b", "iso"]),
    "edge_subgraph": lambda g: g.edge_subgraph(
        [("a", "b", 0)] if g.is_multigraph() else [("a", "b")]
    ),
    "reverse": lambda g: g.reverse(copy=False),
    "subgraph_of_reverse": lambda g: g.reverse(copy=False).subgraph(["a", "b", "iso"]),
    "reverse_of_subgraph": lambda g: g.subgraph(["a", "b", "iso"]).reverse(copy=False),
}


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("kind", list(GRAPH_KINDS))
@pytest.mark.parametrize("accessor", ACCESSORS)
@pytest.mark.parametrize("weighted", [False, True], ids=["unweighted", "weighted"])
@pytest.mark.parametrize("node", ["a", "b", "c", "iso"])
def test_scalar_degree_matches_networkx_on_every_route(
    cls_name, kind, accessor, weighted, node
):
    """The routes the construction-time decision has to get right.

    A filtered or reverse view must NOT take the native counter — those read
    the Rust base, which is empty for a view, so taking it there would answer
    0 for every node.
    """
    make = GRAPH_KINDS[kind]
    results = []
    for lib in (nx, fnx):
        graph = make(_build(lib, cls_name))
        view = getattr(graph, accessor)
        if weighted:
            view = view(weight="weight")
        try:
            results.append(("ok", view[node]))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__, exc.args))
    assert results[1] == results[0], (cls_name, kind, accessor, weighted, node)


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("kind", list(GRAPH_KINDS))
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_missing_node_still_raises_on_every_route(cls_name, kind, accessor):
    """br-r37-c1-i89jx: the guard now follows a different call; it must still fire."""
    make = GRAPH_KINDS[kind]
    results = []
    for lib in (nx, fnx):
        graph = make(_build(lib, cls_name))
        view = getattr(graph, accessor)
        try:
            results.append(("ok", view["zzz"]))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__,))
    assert results[1] == results[0], (cls_name, kind, accessor)
    assert results[0][0] == "KeyError"


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_unhashable_index_still_raises_typeerror(cls_name, accessor):
    """br-r37-c1-sc825 / i89jx: hashability is checked before membership."""
    for lib in (nx, fnx):
        graph = _build(lib, cls_name)
        with pytest.raises(TypeError):
            getattr(graph, accessor)[["not", "hashable"]]


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_scalar_and_iteration_agree(cls_name, accessor):
    """The subscript and the iteration must not drift apart.

    They take different routes now — the subscript uses the pre-resolved
    counter, iteration uses the bulk path — so this is the assertion that keeps
    them honest against each other AND against networkx.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    view_nx, view_fx = getattr(gnx, accessor), getattr(gfx, accessor)
    assert dict(view_fx) == dict(view_nx)
    for node, degree in view_nx:
        assert view_fx[node] == degree, node


@pytest.mark.parametrize("cls_name", DIRECTED)
@pytest.mark.parametrize("accessor", ACCESSORS)
def test_route_survives_graph_mutation(cls_name, accessor):
    """The route is chosen once; the ANSWERS must still be live.

    br-r37-c1-vfc2t made these views live. Resolving the counter at
    construction must not have frozen anything with it.
    """
    gnx, gfx = _build(nx, cls_name), _build(fnx, cls_name)
    view_nx, view_fx = getattr(gnx, accessor), getattr(gfx, accessor)
    for graph in (gnx, gfx):
        graph.add_edge("a", "zz")
        graph.remove_edge("b", "c")
    for node in ("a", "b", "c", "zz"):
        assert view_fx[node] == view_nx[node], node
    assert dict(view_fx) == dict(view_nx)
