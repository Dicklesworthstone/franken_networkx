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
