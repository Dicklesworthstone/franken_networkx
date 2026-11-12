"""``number_of_selfloops`` must not be "cleaned up" onto the slower native twin.

br-r37-c1-hkijj. ``_fnx.number_of_selfloops_rust`` is exported, referenced from
nowhere, and CORRECT: it returns the same count as the wired path on all four
graph classes. That is precisely what makes it a trap. The simple-graph branch
of ``number_of_selfloops`` currently spells the answer

    len(_fnx.nodes_with_selfloops_rust(G))

and swapping in the count-returning function reads as an obvious cleanup - it
drops a list materialisation and says exactly what it means.

It would REGRESS DiGraph. ``number_of_selfloops_rust`` calls ``gr.undirected()``,
which builds the entire O(|V| + |E|) undirected copy; the doc comment on
``nodes_with_selfloops_rust`` records that projection as the ENTIRE former cost
of ``number_of_selfloops`` on a DiGraph (~24ms at 3600 edges), which is why that
function grew a directed O(|V|) index scan and became the wired path.

WHY THIS FILE EXISTS AT ALL: no VALUE test can catch the swap, because the two
routes return equal answers - that equality is the whole problem. So this pins
the ROUTING instead. It is the same shape as the GEXF conversion spies: when two
implementations agree on output, the only testable difference is which one runs.

Under a build freeze a benchmark cannot be run either, so a comment at the call
site, a doc comment at the definition, and this assertion are the entire defence.
"""

from __future__ import annotations

import pytest
import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(cls, n=40, loops=5):
    g = getattr(fnx, cls)()
    for i in range(n):
        g.add_edge("n%d" % i, "n%d" % ((i + 1) % n))
    for i in range(loops):
        g.add_edge("n%d" % i, "n%d" % i)
    return g


@pytest.mark.parametrize("cls", CLASSES)
def test_the_projecting_twin_is_never_called(cls):
    """THE GUARD. Swapping the call sites is the regression this catches."""
    graph = _build(cls)
    calls = []
    original = fnx._fnx.number_of_selfloops_rust

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    fnx._fnx.number_of_selfloops_rust = spy
    try:
        assert fnx.number_of_selfloops(graph) == 5
    finally:
        fnx._fnx.number_of_selfloops_rust = original

    assert calls == [], (
        f"{cls}: number_of_selfloops routed through number_of_selfloops_rust, "
        "which projects a DiGraph to its undirected form (O(|V|+|E|)). The "
        "counts are equal, so only this assertion can tell you."
    )


@pytest.mark.parametrize("cls", CLASSES)
def test_the_twin_still_agrees_on_the_count(cls):
    """The trap only exists BECAUSE they agree; pin that so the note stays true.

    If this ever fails, the dead function has drifted and the call-site comment
    describing it as 'correct but slower' is stale.
    """
    graph = _build(cls)
    assert fnx._fnx.number_of_selfloops_rust(graph) == fnx.number_of_selfloops(graph)


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("loops", [0, 1, 7])
def test_counts_are_correct_across_shapes(cls, loops):
    graph = _build(cls, n=25, loops=loops)
    assert fnx.number_of_selfloops(graph) == loops
    assert len(list(fnx.selfloop_edges(graph))) == loops


def test_an_empty_graph_counts_zero():
    for cls in CLASSES:
        assert fnx.number_of_selfloops(getattr(fnx, cls)()) == 0


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_parallel_self_loops_are_counted_separately(cls):
    """Multigraphs route through a different native, which must stay separate."""
    graph = getattr(fnx, cls)()
    graph.add_edge("a", "a")
    graph.add_edge("a", "a")
    graph.add_edge("b", "c")
    assert fnx.number_of_selfloops(graph) == 2


def _loop_count_graph(module, cls):
    graph = getattr(module, cls)()
    graph.add_nodes_from(range(5))
    graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])
    if graph.is_multigraph():
        graph.add_edges_from([
            (0, 0, "keep"), (0, 0, "hidden"), (1, 1, "keep"),
            (4, 4, "keep"), (4, 4, "hidden"),
        ])
    else:
        graph.add_edges_from([(0, 0), (1, 1), (4, 4)])
    return graph


def _loop_count_view(module, graph, kind, visible, blocked):
    if kind == "subgraph":
        return graph.subgraph(visible)
    if kind == "edge_subgraph":
        edges = (
            [(0, 0, "keep"), (1, 1, "keep"), (0, 1, 0)]
            if graph.is_multigraph() else [(0, 0), (1, 1), (0, 1)]
        )
        return graph.edge_subgraph(edges)
    if kind == "copy":
        return graph.copy(as_view=True)
    if kind == "directed":
        return graph.to_directed(as_view=True)
    if kind == "undirected":
        return graph.to_undirected(as_view=True)
    if kind == "reverse":
        return graph.reverse(copy=False)
    edge_filter = (
        (lambda u, v, key: u != v or (u != 1 and key not in blocked))
        if graph.is_multigraph() else (lambda u, v: u != v or u not in blocked)
    )
    view = module.subgraph_view(
        graph, filter_node=lambda node: node in visible, filter_edge=edge_filter
    )
    if kind == "nested":
        return view.to_directed(as_view=True).reverse(copy=False)
    return view


_LOOP_COUNT_VIEW_CASES = [
    (cls, kind)
    for cls in CLASSES
    for kind in ("subgraph", "edge_subgraph", "copy", "directed", "undirected", "filtered", "nested")
] + [(cls, "reverse") for cls in ("DiGraph", "MultiDiGraph")]


@pytest.mark.parametrize("cls,kind", _LOOP_COUNT_VIEW_CASES)
def test_view_selfloop_counts_follow_live_logical_topology_without_copy(monkeypatch, cls, kind):
    graph = _loop_count_graph(fnx, cls)
    reference = _loop_count_graph(nx, cls)
    visible, blocked = {0, 1, 2, 3}, {1, "hidden"}
    view = _loop_count_view(fnx, graph, kind, visible, blocked)
    expected = _loop_count_view(nx, reference, kind, visible, blocked)
    attempts = []

    def copying_forbidden(*args, **kwargs):
        attempts.append("copy")
        raise AssertionError("self-loop counting must read the logical topology directly")

    monkeypatch.setattr(fnx, "_materialize_view", copying_forbidden)
    for base in (fnx._FilteredGraphView, fnx._ConversionGraphViewBase, fnx._ReverseDirectedViewBase):
        monkeypatch.setattr(base, "copy", copying_forbidden)

    def check():
        assert fnx.number_of_selfloops(view) == nx.number_of_selfloops(expected)
        assert attempts == []

    check()
    for current in (graph, reference):
        if current.is_multigraph():
            current.add_edge(0, 0, key="late")
            current.add_edge(2, 2, key="late")
        else:
            current.add_edge(2, 2)
    check()
    # Filters can change without advancing a native topology epoch.
    visible.discard(0)
    blocked.add("late" if graph.is_multigraph() else 2)
    check()
    graph.remove_node(1)
    reference.remove_node(1)
    check()
    graph.clear()
    reference.clear()
    check()


@pytest.mark.parametrize("cls", CLASSES)
def test_assigned_private_selfloop_counts_use_logical_rows(monkeypatch, cls):
    graph = getattr(fnx, cls)()
    graph.add_edge("native", "native")
    graph._node = {0: {}, 1: {}}
    adjacency = (
        {0: {0: {"a": {}, "b": {}}}, 1: {1: {"c": {}}}}
        if graph.is_multigraph() else {0: {0: {}}, 1: {1: {}}}
    )
    graph._adj = adjacency

    def copying_forbidden(*args, **kwargs):
        raise AssertionError("assigned mappings are already the authoritative topology")

    monkeypatch.setattr(fnx, "_materialize_view", copying_forbidden)
    assert fnx.number_of_selfloops(graph) == (3 if graph.is_multigraph() else 2)
    del adjacency[0][0]
    assert fnx.number_of_selfloops(graph) == 1


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("filtered", [False, True])
def test_foreign_graph_selfloop_counts_keep_conversion_compatibility(cls, filtered):
    graph = _loop_count_graph(nx, cls)
    if filtered:
        graph = nx.subgraph_view(graph, filter_node=lambda node: node != 4)
    assert fnx.number_of_selfloops(graph) == nx.number_of_selfloops(graph)


@pytest.mark.parametrize("value", [None, 7, [], {}])
def test_selfloop_count_invalid_inputs_keep_public_errors(value):
    with pytest.raises(AttributeError, match="is_multigraph"):
        fnx.number_of_selfloops(value)
