"""Lock for br-r37-c1-k3vnp — filtered adjacency rows yield keys without values.

``FilterAdjacency.__iter__`` needs only the edge KEYS of each (node, neighbour)
pair, to ask whether ANY of them is visible. It reached them through
``row.items()`` / ``row[neighbour]``, which builds the whole keydict VALUE view
per neighbour: cProfile showed ``AdjacencyView.__getitem__`` and
``_multi_edge_keydict`` at 14.7 calls each per single ``adj[u]`` lookup, and the
row measured 0.0860x against networkx. ``_native_edge_key_set`` answers the same
question 11.6x cheaper. The simple-graph branch was worse still: it bound
``edge_data`` from ``.items()`` and never used it.

THE TRAP THIS FILE EXISTS FOR. A reverse/filtered view DELEGATES
``_native_edge_key_set`` to something underneath it without reorienting, and on
a reverse view it answers the EMPTY SET for both orientations. A ``getattr``
probe therefore finds a method that is present, callable, and silently wrong,
and ``reverse_view(G).edge_subgraph(...)`` came back empty. The accessor is
gated to CONCRETE multigraph parents for that reason, and the gate is pinned
below — a `getattr`-only gate would pass every behavioural test that does not
involve a reverse view.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=1)
        graph.add_edge("b", "c", weight=2)
        graph.add_edge("c", "a", weight=3)
        graph.add_edge("a", "a", weight=4)  # self-loop
        if graph.is_multigraph():
            graph.add_edge("a", "b", weight=5)  # parallel
            graph.add_edge("a", "b", weight=6)
        made.append(graph)
    return made


def _rows(view, nodes):
    return {n: sorted(map(str, view.adj[n])) for n in nodes if n in view}


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "make",
    [
        ("all-pass-edge", lambda lib, g: lib.subgraph_view(g, filter_edge=lambda *a: True)),
        ("no-edge", lambda lib, g: lib.subgraph_view(g, filter_edge=lambda *a: False)),
        ("some-edge", lambda lib, g: lib.subgraph_view(
            g, filter_edge=lambda u, v, *k: str(u) < str(v))),
        ("node+edge", lambda lib, g: lib.subgraph_view(
            g, filter_node=lambda n: n != "c", filter_edge=lambda u, v, *k: True)),
        ("restricted", lambda lib, g: lib.restricted_view(g, ["c"], [])),
    ],
    ids=lambda m: m[0],
)
def test_filtered_row_keys_match_networkx(cls_name, make):
    gnx, gfx = _pair(cls_name)
    vnx, vfx = make[1](nx, gnx), make[1](fnx, gfx)
    assert _rows(vfx, "abc") == _rows(vnx, "abc")
    assert sorted(map(str, vfx.edges())) == sorted(map(str, vnx.edges()))


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_edge_subgraph_still_finds_its_edges(cls_name):
    """The regression the concrete-parent gate exists to prevent.

    Without the gate this returned an EMPTY graph, because the delegated
    key-set accessor answered the empty set for both orientations.
    """
    gnx, gfx = _pair(cls_name)
    selected = [("b", "a", 0)] if cls_name.startswith("Multi") else [("b", "a")]
    enx = nx.reverse_view(gnx).edge_subgraph(selected)
    efx = fnx.reverse_view(gfx).edge_subgraph(selected)
    assert sorted(map(str, efx.edges())) == sorted(map(str, enx.edges()))
    assert list(efx.edges()), "the reverse view's edge_subgraph came back empty"


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_rows_match_networkx(cls_name):
    gnx, gfx = _pair(cls_name)
    vnx = nx.subgraph_view(nx.reverse_view(gnx), filter_edge=lambda *a: True)
    vfx = fnx.subgraph_view(fnx.reverse_view(gfx), filter_edge=lambda *a: True)
    assert _rows(vfx, "abc") == _rows(vnx, "abc")
    assert sorted(map(str, vfx.edges())) == sorted(map(str, vnx.edges()))


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_the_key_set_accessor_is_gated_to_concrete_parents(cls_name):
    """Pin the gate itself, not just the behaviour it protects.

    A ``getattr``-only gate passes every behavioural test that does not involve
    a reverse view, so assert the accessor really is absent-or-wrong on a view
    and correct on a concrete parent.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b")
    graph.add_edge("a", "b")
    assert set(graph._native_edge_key_set("a", "b")) == set(graph["a"]["b"])

    if graph.is_directed():  # reverse_view is directed-only
        reverse = fnx.reverse_view(graph)
        assert type(reverse) not in (fnx.MultiGraph, fnx.MultiDiGraph), (
            "a reverse view now reports a concrete type; the gate would let it "
            "through and its key-set accessor is not reoriented"
        )


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_key_set_equals_the_keydict_keys(cls_name):
    """The equivalence the substitution rests on."""
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b", w=1)
    graph.add_edge("a", "b", w=2)
    graph.add_edge("b", "c", w=3)
    graph.add_edge("a", "a", w=4)
    for u in graph:
        for v in graph[u]:
            assert set(graph._native_edge_key_set(u, v)) == set(graph[u][v]), (u, v)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_rows_are_live_after_mutation(cls_name):
    gnx, gfx = _pair(cls_name)
    vnx = nx.subgraph_view(gnx, filter_edge=lambda *a: True)
    vfx = fnx.subgraph_view(gfx, filter_edge=lambda *a: True)
    for graph in (gnx, gfx):
        graph.add_edge("a", "z", weight=9)
    assert _rows(vfx, "az") == _rows(vnx, "az")
    for graph in (gnx, gfx):
        graph.remove_node("z")
    assert _rows(vfx, "a") == _rows(vnx, "a")
