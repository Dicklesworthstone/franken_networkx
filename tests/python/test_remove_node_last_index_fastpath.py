"""Removing the highest-indexed isolated node must skip the renumber and change nothing else.

br-r37-c1-qxtlj. fnx serves nodes by a dense integer position. Removing a node
used to renumber every position above it with an O(|V|+|E|) repair, even for the
LAST index with no edges, where there was nothing to renumber (264.86us on a
12800-node Graph against networkx's 0.61us). Since yr2oc.1 a removal renumbers
nothing on Graph/DiGraph: it frees the node's slot, and positional readers
translate slots to positions until the next insertion compacts. Either way, a
graph that skipped or deferred the repair must be indistinguishable from one that
did not.

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


def _positional_state(g, lib):
    """What the native positional readers serve, in networkx's order."""
    first = next(iter(g))
    components = lib.weakly_connected_components if g.is_directed() else lib.connected_components
    keyed = {"keys": True} if g.is_multigraph() else {}
    state = {
        "nodes": list(g),
        "edges": list(g.edges(data=True, **keyed)),
        "rows": [(n, list(g.adj[n])) for n in g],
        "wdegree": [(n, d, type(d).__name__) for n, d in g.degree(weight="w")],
        "wdegree_each": [(n, g.degree(n, weight="w")) for n in g],
        "size": g.size(weight="w"),
        "bfs": list(lib.bfs_edges(g, first)),
        "sssp": list(lib.single_source_shortest_path_length(g, first).items()),
        "components": sorted(sorted(map(str, c)) for c in components(g)),
    }
    if g.is_directed():
        state["preds"] = [(n, list(g.pred[n])) for n in g]
        state["in_edges"] = list(g.in_edges(**keyed))
    return state


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("seed", range(6))
def test_a_run_of_removals_keeps_positional_readers_matching_networkx(cls, seed):
    """yr2oc.1: slots and positions stay apart through a run of removals.

    A removal tombstones the node's entry in the node order instead of
    renumbering the graph, so until the order compacts a node's position is its
    rank among the live entries, not its slot. `Graph`/`DiGraph` compact at the
    next insertion, `MultiGraph` reuses the freed slot for the next new node,
    and all four compact once tombstones outnumber live nodes. Everything read
    by position in between (weighted degree, the BFS / shortest-path /
    component kernels, edge and in-edge iteration) goes through that
    translation; reading slots as positions diverges from networkx here.
    """
    rng = random.Random(seed)
    got, want = _both(cls)
    n = 40
    for _ in range(4 * n):
        u, v = rng.randrange(n), rng.randrange(n)
        w = rng.choice([1, 2, 3, 0.5, 2.25])
        for g in (got, want):
            g.add_edge(u, v, w=w)
    for _ in range(n // 3):
        victim = rng.choice(list(want)[:-1])
        for g in (got, want):
            g.remove_node(victim)
        assert _positional_state(got, fnx) == _positional_state(want, nx)
    for g in (got, want):
        g.add_edge("fresh", victim)
    assert _positional_state(got, fnx) == _positional_state(want, nx)
    # Removals interleaved with insertions: new nodes land in reused slots
    # (MultiGraph) or after tombstones (MultiDiGraph).
    for step in range(2 * n):
        if rng.random() < 0.5 and len(want) > 2:
            victim = rng.choice(list(want))
            for g in (got, want):
                g.remove_node(victim)
        else:
            u, v = f"x{step}", rng.choice(list(want))
            for g in (got, want):
                g.add_edge(u, v, w=step)
        assert _positional_state(got, fnx) == _positional_state(want, nx), step


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("build", ["one_by_one", "batch_then_touched", "batch"])
def test_removed_edges_leave_no_attributes_behind(cls, build):
    """yr2oc.1: removing a node drops its edges' attribute mirrors.

    `remove_node` walks the incident edges' Python attribute mirrors only when
    a mirror holds anything. A graph built edge by edge fills them eagerly, a
    batch-built one leaves them empty until an attribute is touched. Whatever
    the mirrors held, re-adding a removed edge bare must come back bare, as it
    does in networkx; a stale mirror entry would hand the old attributes back.
    """
    rng = random.Random(len(cls) + len(build))
    got, want = _both(cls)
    n = 30
    edges = [(rng.randrange(n), rng.randrange(n)) for _ in range(3 * n)]
    for g in (got, want):
        if build == "one_by_one":
            for i, (u, v) in enumerate(edges):
                g.add_edge(u, v, w=i)
        else:
            g.add_edges_from(edges)
    if build == "batch_then_touched":
        for i, (u, v) in enumerate(edges[::3]):
            for g in (got, want):
                for key in list(g[u][v]) if g.is_multigraph() else [None]:
                    data = g[u][v][key] if key is not None else g[u][v]
                    data["w"] = i
    victims = rng.sample(range(n), n // 3)
    for victim in victims:
        for g in (got, want):
            g.remove_node(victim)
    for u, v in edges:
        if u in victims or v in victims:
            for g in (got, want):
                g.add_edge(u, v)
    keyed = {"keys": True} if got.is_multigraph() else {}
    assert list(got.edges(data=True, **keyed)) == list(want.edges(data=True, **keyed))
