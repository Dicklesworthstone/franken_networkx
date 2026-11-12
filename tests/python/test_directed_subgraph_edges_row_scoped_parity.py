"""A directed subgraph's edges() must read only the rows it was asked for.

``DiGraph.subgraph(nbunch).edges()`` built the WHOLE parent adjacency on every
call in order to read the handful of rows the subgraph actually covers. An
earlier fix (br-cvsubedges) had already taken it from O(V*(V+E)) to O(V+E) by
hoisting that snapshot out of the per-source loop, but O(V+E) is still the whole
parent graph, and networkx is O(rows asked for). So the loss grew without bound
with the parent's size rather than sitting at a constant factor:

    N        nx us    fnx us     t_nx/t_fnx
    500      36.19     135.24      0.2676
    2000     31.79     587.29      0.0541
    8000     34.04    3122.74      0.0109
    32000    32.60   21254.29      0.0015     <- 667x slower than networkx

DiGraph was alone in this. Graph (2.17-2.43x), MultiGraph and MultiDiGraph
(~1.2x) were all flat in N and winning across the same range, which is what
identified the directed branch as the defect rather than the shape of the call.

The fix reads each requested row through the per-row accessor that was already
bound in that branch for the data=True merge. That accessor carries identical
key ORDER and identical VALUES to the whole-graph snapshot — verified across
every node at two graph sizes before the change was made, since the old code's
``live.get(target, keyrow[target])`` fallback implied they might differ.

These tests are differential against live networkx, and they deliberately vary
the parent size: a correctness test at one size cannot tell a row-scoped read
from a whole-graph one, and it was exactly that blind spot which let an O(V+E)
read look finished.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(lib, cls_name, order):
    graph = getattr(lib, cls_name)()
    for i in range(order):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}", weight=float(i % 11))
    graph.add_edge("n0", "n0", weight=-1.0)  # self-loop
    if graph.is_multigraph():
        graph.add_edge("n0", "n1", weight=99.0)  # parallel edge
    graph.add_node("isolated")
    return graph


def _canonical(edges, directed):
    out = []
    for edge in edges:
        u, v = edge[0], edge[1]
        head = (u, v) if directed else tuple(sorted((u, v)))
        rest = tuple(sorted(edge[2].items())) if len(edge) > 2 and isinstance(edge[2], dict) else edge[2:]
        out.append(head + rest)
    return sorted(out, key=repr)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("order", [40, 400, 3000])
@pytest.mark.parametrize("data", [False, True], ids=["nodata", "data"])
def test_subgraph_edges_match_networkx_at_every_parent_size(cls_name, order, data):
    """The parent size is a PARAMETER, because that is what the bug moved with."""
    nbunch = [f"n{i}" for i in range(10)] + ["isolated", "n0"]
    results = []
    for lib in (nx, fnx):
        graph = _build(lib, cls_name, order)
        sub = graph.subgraph(nbunch)
        results.append(_canonical(sub.edges(data=data), sub.is_directed()))
    assert results[1] == results[0], (cls_name, order, data)


@pytest.mark.parametrize("order", [40, 400, 3000])
def test_directed_subgraph_edge_ORDER_matches_networkx(order):
    """Not just the same edges — the same sequence.

    The old path took key order from a whole-graph snapshot and the new one from
    the per-row accessor. Those were verified to agree before the change; this
    keeps them agreeing, and a set comparison would not.
    """
    nbunch = [f"n{i}" for i in range(12)]
    gnx, gfx = _build(nx, "DiGraph", order), _build(fnx, "DiGraph", order)
    assert list(gfx.subgraph(nbunch).edges()) == list(gnx.subgraph(nbunch).edges())
    assert list(gfx.subgraph(nbunch).edges(data=True)) == list(
        gnx.subgraph(nbunch).edges(data=True)
    )


@pytest.mark.parametrize("order", [40, 400])
def test_edge_subgraph_and_restricted_view_also_match(order):
    """The sibling filtered views share the branch that was changed."""
    gnx, gfx = _build(nx, "DiGraph", order), _build(fnx, "DiGraph", order)
    pairs = [("n0", "n3"), ("n1", "n10"), ("n0", "n0")]
    pairs = [p for p in pairs if gnx.has_edge(*p)]
    assert _canonical(gfx.edge_subgraph(pairs).edges(), True) == _canonical(
        gnx.edge_subgraph(pairs).edges(), True
    )
    hidden = [f"n{i}" for i in range(5)]
    assert _canonical(
        nx.restricted_view(gfx, hidden, []).edges(), True
    ) == _canonical(nx.restricted_view(gnx, hidden, []).edges(), True)


def test_subgraph_edges_stay_live_after_parent_mutation():
    """A subgraph view is live; reading rows per call must not have frozen it."""
    gnx, gfx = _build(nx, "DiGraph", 200), _build(fnx, "DiGraph", 200)
    nbunch = [f"n{i}" for i in range(10)]
    views = [g.subgraph(nbunch) for g in (gnx, gfx)]
    for graph in (gnx, gfx):
        graph.add_edge("n1", "n2", weight=7.0)
        graph.remove_edge("n0", "n3") if graph.has_edge("n0", "n3") else None
    assert _canonical(views[1].edges(data=True), True) == _canonical(
        views[0].edges(data=True), True
    )


def test_the_directed_row_accessor_agrees_with_the_whole_graph_snapshot():
    """Pins the equivalence the fix rests on.

    If the per-row accessor ever stops matching the whole-graph snapshot in key
    order or value, the substitution above is no longer sound and this fails
    before any user notices through edges().
    """
    graph = _build(fnx, "DiGraph", 300)
    full = graph._native_adjacency_dict()
    for source in graph:
        row = graph._native_successor_row_dict(source)
        assert list(row) == list(full[source]), source
        for target in full[source]:
            assert row[target] == full[source][target], (source, target)
