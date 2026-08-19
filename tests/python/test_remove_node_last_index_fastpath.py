"""Removing the highest-indexed isolated node must skip the renumber and change nothing else.

br-r37-c1-qxtlj. fnx stores nodes in a compact integer index, so removing a node
renumbers every position above it and repairs adjacency and edge storage - an
O(|V|+|E|) pass. That floor is architectural. What was NOT architectural is that
it ran even when there was nothing to renumber: removing the LAST index shifts no
position, and removing an ISOLATED node detaches no edge, so for a node that is
both, the whole repair is a no-op over its entire input. It cost the same as any
other removal anyway - 264.86us on a 12800-node Graph against networkx's 0.61us,
identical whether the node sat at the first index or the last.

THIS FILE IS ABOUT THE FAST PATH BEING INVISIBLE. Its speed is measured
elsewhere; what matters here is that a graph which took the shortcut is
indistinguishable from one that did not. The failure mode is not a wrong answer
now, it is a corrupted index that produces a wrong answer several operations
later - so most of these tests keep USING the graph after the removal.

The guard conditions are pinned by their negatives too: a node with edges, a node
in the middle, and a SELF-LOOPED node (whose own index appears in its own
adjacency row, so it is not isolated) must all still take the general path.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _state(g):
    """Everything observable that a corrupted index could disturb."""
    return {
        "nodes": [str(n) for n in g.nodes()],
        "edges": sorted((str(u), str(v)) for u, v in g.edges()),
        "n": g.number_of_nodes(),
        "m": g.number_of_edges(),
        "degree": {str(n): d for n, d in g.degree()},
        "adj": {str(n): sorted(str(x) for x in g[n]) for n in g.nodes()},
    }


def _both(cls):
    return getattr(fnx, cls)(), getattr(nx, cls)()


@pytest.mark.parametrize("cls", CLASSES)
def test_last_index_isolated_removal_matches_networkx(cls):
    got, want = _both(cls)
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(8)])
        g.add_node("scratch")          # highest index, isolated -> fast path
        g.remove_node("scratch")
    assert _state(got) == _state(want)


@pytest.mark.parametrize("cls", CLASSES)
def test_graph_still_works_after_the_fast_path(cls):
    """A corrupted index shows up LATER, not at the removal."""
    got, want = _both(cls)
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}", {"w": i}) for i in range(8)])
        g.add_node("scratch")
        g.remove_node("scratch")
        # keep using it: the new node reuses the freed index
        g.add_edge("fresh", "n3", w=99)
        g.add_edge("n0", "n5", w=1)
        g.remove_edge("n1", "n2")
        g.add_node("another")
    assert _state(got) == _state(want)
    assert [(str(u), str(v), d.get("w")) for u, v, d in sorted(
        got.edges(data=True), key=lambda e: (str(e[0]), str(e[1])))] == [
        (str(u), str(v), d.get("w")) for u, v, d in sorted(
            want.edges(data=True), key=lambda e: (str(e[0]), str(e[1])))]


@pytest.mark.parametrize("cls", CLASSES)
def test_repeated_scratch_cycles(cls):
    """add-then-remove at the tail, many times - the pattern the fix targets."""
    got, want = _both(cls)
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(6)])
        for i in range(25):
            g.add_node(f"tmp{i}")
            g.remove_node(f"tmp{i}")
    assert _state(got) == _state(want)


@pytest.mark.parametrize("cls", CLASSES)
def test_guard_negatives_still_take_the_general_path(cls):
    """Each condition the fast path relies on, violated one at a time."""
    # last index but NOT isolated
    got, want = _both(cls)
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(6)])
        g.add_edge("tail", "n2")       # highest index, has an edge
        g.remove_node("tail")
    assert _state(got) == _state(want)

    # isolated but NOT the last index
    got, want = _both(cls)
    for g in (got, want):
        g.add_node("early")
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(6)])
        g.remove_node("early")
    assert _state(got) == _state(want)

    # last index, SELF-LOOP only: its own index is in its own row, so not isolated
    got, want = _both(cls)
    for g in (got, want):
        g.add_edges_from([(f"n{i}", f"n{i + 1}") for i in range(6)])
        g.add_edge("loop", "loop")
        g.remove_node("loop")
    assert _state(got) == _state(want)


@pytest.mark.parametrize("cls", CLASSES)
def test_removing_the_only_node(cls):
    got, want = _both(cls)
    for g in (got, want):
        g.add_node("only")
        g.remove_node("only")
        assert g.number_of_nodes() == 0
        g.add_node("back")
    assert _state(got) == _state(want)


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_randomised_mutation_sequence_matches_networkx(cls, seed):
    """The real guard: interleave the fast path with everything else.

    A skipped repair corrupts the index silently; only a long mixed sequence
    that keeps reading the graph will surface it.
    """
    rng = random.Random(seed)
    got, want = _both(cls)
    # a FIXED vocabulary: nodes come and go from the graph, but the pool the
    # sequence draws from never shrinks, so the walk cannot run itself dry.
    names = [f"n{i}" for i in range(12)]
    for g in (got, want):
        g.add_edges_from([(names[i], names[i + 1]) for i in range(11)])

    for step in range(120):
        choice = rng.randrange(6)
        a, b = rng.choice(names), rng.choice(names)
        for g in (got, want):
            if choice == 0:
                g.add_node(f"t{step}")
            elif choice == 1 and f"t{step - 1}" in g:
                g.remove_node(f"t{step - 1}")
            elif choice == 2:
                g.add_edge(a, b, w=step)
            elif choice == 3 and g.has_edge(a, b):
                g.remove_edge(a, b)
            elif choice == 4 and a in g:
                g.remove_node(a)
            else:
                g.add_node(a)
        assert _state(got) == _state(want), f"diverged at step {step} (choice {choice})"

    assert _state(got) == _state(want)
