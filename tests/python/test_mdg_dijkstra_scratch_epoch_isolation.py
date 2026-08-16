"""A large graph's dijkstra state must not leak into a later, smaller graph.

br-r37-c1-4q95e. ``multidigraph_single_source_dijkstra_path_length`` runs on a
THREAD-LOCAL scratch that is reused for every MultiDiGraph in the process. That
scratch deliberately does not clear its parallel arrays between runs — an epoch
counter is bumped instead, and each array is read through a stamp check so a
value left by a previous run reads as absent. It is a real optimisation: it turns
an O(n) reset into a counter increment.

``predecessors`` was the one array read WITHOUT that check:

    let predecessor = (scratch.predecessors[node_idx] != usize::MAX)
        .then_some(scratch.predecessors[node_idx]);

So after a 30-node graph left ``predecessors[1] = 22``, a later 3-node graph
reported node 1's predecessor as 22, and the caller's ``nodes[*parent_idx]``
panicked:

    pyo3_runtime.PanicException: index out of bounds: the len is 3 but the index is 22

That is a PANIC, not an exception — it unwinds through the interpreter rather
than raising something a caller can catch — and it is reachable from plain
``single_source_dijkstra_path_length`` on a small graph in any process that has
already built a larger one. Which is every long-running program.

WHY ``seen_epoch`` COULD NOT SERVE AS THE GUARD, i.e. why a new stamp array was
needed rather than reusing an existing one: the SOURCE node is stamped seen (its
distance is set to zero) while no predecessor is ever written for it. Guarding on
``seen_epoch`` would therefore still read a stale predecessor for exactly the
source node — the one node guaranteed to be visited.

THE SHAPE THAT MATTERS. Every test here runs the large graph FIRST, in the same
process, and only then the small one. A test that builds only small graphs, or
that runs each case in a fresh process, cannot fail no matter how broken the
scratch is — which is why the original defect survived a 59k-test suite and was
only found through an unrelated test file's incidental ordering.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

# 30 > 3, so an index left by the large graph is out of bounds for the small one.
LARGE = 30
SMALL = 3


def _ring(mod, n, weight=1.0):
    graph = mod.MultiDiGraph()
    for i in range(n):
        graph.add_edge(f"n{i}", f"n{(i + 1) % n}", weight=weight)
    return graph


def _drain_large(mod):
    """Populate the shared scratch from a graph big enough to poison it.

    THE SOURCE MUST NOT BE ``n0``, and that is the whole subtlety of this bug.

    A node's predecessor slot is overwritten whenever the current run relaxes
    into it, so a stale value only survives for a node this run never relaxes
    into — and the one node guaranteed never to be relaxed into is the SOURCE.
    Running the large graph from ``n0`` therefore poisons nothing at index 0, and
    a later small graph sourced at ``n0`` reads a clean slot: no panic, and the
    bug hides.

    Running it from ``n1`` instead means index 0 is REACHED (its predecessor
    becomes index ``LARGE - 1``). The later small graph is then sourced at
    ``n0``, never writes that slot, and reads the stale large index straight out
    of the previous graph's run.

    Verified against the pre-fix binary: this shape raises
    ``PanicException: index out of bounds: the len is 3 but the index is 29``
    while the ``n0``-sourced shape returns a correct answer.
    """
    big = _ring(mod, LARGE)
    mod.single_source_dijkstra_path_length(big, "n1", weight="weight")
    return big


def test_small_graph_after_large_does_not_panic():
    """The reported panic, reduced to two calls."""
    _drain_large(fnx)
    small = _ring(fnx, SMALL)
    got = fnx.single_source_dijkstra_path_length(small, "n0", weight="weight")
    assert got == nx.single_source_dijkstra_path_length(
        _ring(nx, SMALL), "n0", weight="weight"
    )


@pytest.mark.parametrize("small_n", [1, 2, 3, 5, 11])
def test_descending_sizes_match_networkx(small_n):
    """Any smaller graph after a larger one, not just 3 after 30."""
    _drain_large(fnx)
    got = fnx.single_source_dijkstra_path_length(
        _ring(fnx, small_n), "n0", weight="weight"
    )
    want = nx.single_source_dijkstra_path_length(
        _ring(nx, small_n), "n0", weight="weight"
    )
    assert got == want


def test_alternating_sizes_stay_correct():
    """Alternate large/small repeatedly — the scratch is reused every time.

    A fix that cleared the array once, or only on growth, passes a single
    large-then-small pair and fails here on the second cycle.
    """
    for _ in range(6):
        _drain_large(fnx)
        small = _ring(fnx, SMALL)
        assert fnx.single_source_dijkstra_path_length(
            small, "n0", weight="weight"
        ) == {"n0": 0, "n1": 1, "n2": 2}


def test_disconnected_small_graph_after_large():
    """Unreachable nodes are where a stale predecessor is most likely read.

    A node that is never relaxed in THIS run keeps whatever predecessor the
    previous run left. Here nodes n3/n4 are unreachable from n0, so nothing
    writes their predecessor slot.
    """
    _drain_large(fnx)
    graph = fnx.MultiDiGraph()
    graph.add_edge("n0", "n1", weight=1.0)
    graph.add_edge("n3", "n4", weight=1.0)
    reference = nx.MultiDiGraph()
    reference.add_edge("n0", "n1", weight=1.0)
    reference.add_edge("n3", "n4", weight=1.0)
    assert fnx.single_source_dijkstra_path_length(
        graph, "n0", weight="weight"
    ) == nx.single_source_dijkstra_path_length(reference, "n0", weight="weight")


def test_path_reconstruction_after_large_graph():
    """The same scratch backs the TARGET-PATH walk, which follows the chain.

    That walk reads predecessors in a loop to rebuild the route, so a stale entry
    there either returns a wrong path or walks out of bounds. The fix must return
    "no path" rather than a partial chain when the chain does not reach the
    source.
    """
    _drain_large(fnx)
    graph = fnx.MultiDiGraph()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("b", "c", weight=1.0)
    reference = nx.MultiDiGraph()
    reference.add_edge("a", "b", weight=1.0)
    reference.add_edge("b", "c", weight=1.0)

    assert fnx.dijkstra_path(graph, "a", "c", weight="weight") == nx.dijkstra_path(
        reference, "a", "c", weight="weight"
    )
    assert fnx.dijkstra_path_length(
        graph, "a", "c", weight="weight"
    ) == nx.dijkstra_path_length(reference, "a", "c", weight="weight")

    # No route from "c" back to "a": networkx raises, and so must fnx.
    with pytest.raises(nx.NetworkXNoPath):
        nx.dijkstra_path(reference, "c", "a", weight="weight")
    with pytest.raises(nx.NetworkXNoPath):
        fnx.dijkstra_path(graph, "c", "a", weight="weight")


def test_cutoff_after_large_graph():
    """`cutoff` prunes relaxations, leaving more slots unwritten this run."""
    _drain_large(fnx)
    got = fnx.single_source_dijkstra_path_length(
        _ring(fnx, 8), "n0", weight="weight", cutoff=2
    )
    want = nx.single_source_dijkstra_path_length(
        _ring(nx, 8), "n0", weight="weight", cutoff=2
    )
    assert got == want
