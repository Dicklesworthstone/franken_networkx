"""The native nbunch kernel raises where networkx completes, on three classes.

br-r37-c1-hihrf. networkx lets you add an edge between two BRAND NEW nodes while
iterating ``G.edges(nbunch)``: it walks the adjacency rows of the nbunch, and a
brand-new node touches none of them. fnx's native nbunch kernel raises
RuntimeError instead.

MEASURED MAP of where fnx and networkx disagree, adding ("brand", "new") on the
first yielded edge:

    class          order   nbunch   networkx           fnx
    Graph            500        4   completes          completes
    Graph            500       16   completes          RuntimeError   <-
    Graph          20000        4   completes          completes
    Graph          20000       16   completes          completes
    DiGraph          500       16   completes          RuntimeError   <-
    DiGraph        20000       16   completes          RuntimeError   <-
    MultiGraph       500        4   completes          RuntimeError   <-
    MultiGraph     20000       16   completes          RuntimeError   <-
    MultiDiGraph     500        4   completes          RuntimeError   <-
    MultiDiGraph   20000       16   completes          RuntimeError   <-

Two separate things are going on, and the mutation-kind sweep at the bottom of
this file separates them:

  * Graph and DiGraph DO have the faithful walk, and inside the gate they
    reproduce networkx on every mutation kind tested - including the one where
    networkx itself raises. They diverge only once the nbunch exceeds
    ``_edges_nbunch_py_walk_limit`` (``max(8, order // 250)``) and the call is
    handed to the kernel.
  * MultiGraph and MultiDiGraph never reach it at all: they raise at nbunch=4 on
    a 500-node graph, which is comfortably inside the gate.

WHY IT WAS NOT CAUGHT. The existing coverage in
test_edges_nbunch_py_walk_threshold_parity.py builds an order-20000 graph, where
that limit is 80, and tests the undirected class - the one combination the gate
does rescue. The defect lives everywhere else.

THIS ALSO PINS A PERF DECISION. The gate costs ~2x: forcing both paths at the
same size, the native kernel runs a 50-node nbunch in ~15.7us against the walk's
~32.8us, flat across a 16x range in graph order. It cannot simply be retired for
that 2x, because retiring it routes MORE calls onto the kernel that raises. The
order of work is therefore: fix the kernel, THEN drop the gate to its floor and
take the 2x. Removing these xfails is what unlocks that.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

# Cells measured to diverge today. Anything NOT listed here is asserted to match,
# so this set is a claim in both directions: shrink it when the kernel is fixed.
# br-r37-c1-hihrf: the MULTIGRAPH cells are gone - the nbunch guard now applies
# networkx's row rule, so those classes no longer raise where networkx completes.
# What is left is the SIMPLE classes above `_edges_nbunch_py_walk_limit`
# (max(8, order // 250)), where the call leaves the faithful Python walk for the
# native kernel and the coarse guard still applies. Those call sites do not yet
# pass their nbunch to the guard; the two multigraph ones do.
DIVERGENT = {
    ("Graph", 500, 16),
    ("DiGraph", 500, 16),
    ("DiGraph", 20000, 16),
}

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
ORDERS = [500, 20000]
SIZES = [4, 16]


def _iterate_and_mutate(lib, class_name, order, size):
    """Add an edge between two brand-new nodes during an nbunch iteration."""
    graph = getattr(lib, class_name)()
    graph.add_edges_from([(f"n{i}", f"n{(i + 1) % order}") for i in range(order)])
    nbunch = [f"n{i}" for i in range(size)]
    try:
        seen = 0
        for _edge in graph.edges(nbunch):
            seen += 1
            if seen == 1:
                graph.add_edge("brand", "new")
        return ("completes", seen)
    except RuntimeError:
        return ("RuntimeError",)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("class_name", CLASSES)
def test_nbunch_mutation_matches_networkx(class_name, order, size):
    if (class_name, order, size) in DIVERGENT:
        pytest.xfail(
            "native nbunch kernel raises where networkx completes "
            "(br-r37-c1-hihrf); the Python walk is the faithful path and it is "
            "reached only for undirected Graph within the order-scaled limit"
        )
    expected = _iterate_and_mutate(nx, class_name, order, size)
    actual = _iterate_and_mutate(fnx, class_name, order, size)
    assert actual == expected, (
        f"{class_name}, order={order}, nbunch={size}: networkx {expected}, fnx "
        f"{actual}. An edge between two brand-new nodes touches no row the "
        f"iteration is walking, so networkx completes."
    )


def test_the_undirected_gate_is_what_rescues_graph():
    """Graph at nbunch=16 flips on graph ORDER alone - that is the gate.

    Same class, same nbunch, same mutation: divergent at order 500 where the
    limit is its floor of 8, faithful at order 20000 where the limit is 80. If
    this ever stops holding, the gate has moved and the DIVERGENT map above is
    stale.
    """
    small = _iterate_and_mutate(fnx, "Graph", 500, 16)
    large = _iterate_and_mutate(fnx, "Graph", 20000, 16)
    assert small == ("RuntimeError",), small
    assert large == _iterate_and_mutate(nx, "Graph", 20000, 16)


# ---------------------------------------------------------------------------
# WHICH mutations diverge, not just which sizes
# ---------------------------------------------------------------------------
# br-r37-c1-hihrf. Sweeping mutation KIND at a size below the gate's floor
# localises the defect much more sharply than sweeping size did. Measured at
# nbunch=[n0..n3], order 500, mutation applied after the first yielded edge:
#
#   mutation                   Graph    DiGraph   MultiGraph   MultiDiGraph
#   add edge new<->new         match    match     RAISES       RAISES
#   add node only              match    match     RAISES       RAISES
#   add edge TO nbunch[0]      match*   match*    match*       match*
#   add edge TO nbunch[3]      match    match     RAISES       RAISES
#   add edge far from nbunch   match    match     RAISES       RAISES
#   remove far edge            match    match     RAISES       RAISES
#   remove nbunch[3] edge      match    match     RAISES       RAISES
#
#   (*) the one case where networkx ITSELF raises: nbunch[0]'s row is the row
#       being iterated when the mutation lands, so CPython's own dict guard
#       fires. Graph and DiGraph reproduce that exactly.
#
# So Graph and DiGraph are faithful on ALL SEVEN kinds - including the subtle
# one - while the multigraph classes raise on six of seven, i.e. on everything
# except the case where raising is correct. The faithful walk is simply NOT
# WIRED for MultiGraph/MultiDiGraph.
#
# That matters for how this gets fixed: the shared per-edge guard in
# _FailFastEdgeIterator is NOT the thing to change. It is already producing
# networkx's answer wherever the walk is reached. The work is to reach the walk
# on the multigraph classes.

MUTATIONS = {
    "add_edge_new_to_new": lambda g: g.add_edge("brand", "new"),
    "add_node_only": lambda g: g.add_node("brand"),
    "add_edge_to_walked_row": lambda g: g.add_edge("n0", "brand"),
    "add_edge_to_later_nbunch_node": lambda g: g.add_edge("n3", "brand"),
    "add_edge_far_from_nbunch": lambda g: g.add_edge("n250", "brand"),
    "remove_far_edge": lambda g: g.remove_edge("n250", "n251"),
    "remove_later_nbunch_edge": lambda g: g.remove_edge("n3", "n4"),
}

# br-r37-c1-hihrf: mutations that touch a nbunch row the walk has NOT reached
# yet. networkx re-reads each row lazily when it gets there, so it sees the
# change; fnx materialises the multigraph nbunch result up front, so it does not.
# This is a VALUE difference (edge count), never a spurious raise, and it is the
# last thing standing between here and full parity - it needs a lazy multigraph
# nbunch view, which the simple classes already have and the list-subclass
# multigraph ones do not.
LAZY_ROW_DIVERGENT = {"add_edge_to_later_nbunch_node", "remove_later_nbunch_edge"}
FAITHFUL_CLASSES = {"Graph", "DiGraph"}


def _iterate_with_mutation(lib, class_name, mutation):
    graph = getattr(lib, class_name)()
    graph.add_edges_from([(f"n{i}", f"n{(i + 1) % 500}") for i in range(500)])
    nbunch = [f"n{i}" for i in range(4)]
    try:
        seen = 0
        for _edge in graph.edges(nbunch):
            seen += 1
            if seen == 1:
                MUTATIONS[mutation](graph)
        return ("completes", seen)
    except RuntimeError:
        return ("RuntimeError",)


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
@pytest.mark.parametrize("class_name", CLASSES)
def test_mutation_kind_matches_networkx(class_name, mutation):
    expected = _iterate_with_mutation(nx, class_name, mutation)
    if class_name not in FAITHFUL_CLASSES and mutation in LAZY_ROW_DIVERGENT:
        pytest.xfail(
            "fnx materialises the multigraph nbunch result, so a mutation to a "
            "row the walk has not reached yet is not picked up; networkx reads "
            "each row lazily (br-r37-c1-hihrf). A VALUE difference, not a "
            "spurious raise."
        )
    actual = _iterate_with_mutation(fnx, class_name, mutation)
    assert actual == expected, (
        f"{class_name}, mutation={mutation}: networkx {expected}, fnx {actual}"
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_every_class_raises_when_the_walked_row_changes(class_name):
    """The case networkx DOES raise on, which all four classes get right.

    Mutating nbunch[0]'s row while that row is the one being iterated is a real
    concurrent modification, and CPython's dict guard fires for networkx. This
    is the control that keeps the xfails above honest: they are about raising
    where networkx does NOT, never about failing to raise where it does.
    """
    assert _iterate_with_mutation(nx, class_name, "add_edge_to_walked_row") == (
        "RuntimeError",
    )
    assert _iterate_with_mutation(fnx, class_name, "add_edge_to_walked_row") == (
        "RuntimeError",
    )


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("iteration", [1, 2, 3])
def test_the_row_guard_survives_repeated_iteration(class_name, iteration):
    """A view is iterated more than once; the guard must hold every time.

    br-r37-c1-hihrf: the nbunch was first stored as `graph.nbunch_iter(...)`,
    a ONE-SHOT generator. The first iteration consumed it and every later one
    saw an empty row snapshot and silently stopped guarding - so the view
    matched networkx on pass one and diverged on pass two. Caught by iterating
    the same view twice, which no single-pass test would have done.
    """
    graph = getattr(fnx, class_name)()
    reference = getattr(nx, class_name)()
    for g in (graph, reference):
        g.add_edges_from([(f"n{i}", f"n{(i + 1) % 50}") for i in range(50)])

    def outcome(g):
        view = g.edges(["n0", "n1", "n2"])
        for _ in range(iteration - 1):
            for _edge in view:
                pass
        try:
            seen = 0
            for _edge in view:
                seen += 1
                if seen == 1:
                    g.add_edge("n0", "brand")   # resize the row being walked
            return ("completes", seen)
        except RuntimeError:
            return ("RuntimeError",)

    assert outcome(graph) == outcome(reference)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "br-r37-c1-hihrf: an nbunch ABOVE the walk gate takes the coarse "
        "'did anything change' guard and raises where networkx completes. "
        "Passing nbunch_rows to _FailFastEdgeIterator fixes it and was reverted "
        "as a measured loss - see the test below for the cost."
    ),
)
def test_an_nbunch_above_the_gate_matches_networkx():
    """The gap the ORDER-scaled gate leaves open, pinned as an acceptance test.

    ``test_the_undirected_gate_is_what_rescues_graph`` shows Graph at nbunch=16
    is rescued once the order-scaled limit passes 16. It cannot be rescued for
    every nbunch, because the limit is ``max(8, order // 250)`` and a caller may
    pass more nodes than that: at order 20000 the limit is 80, so nbunch=120
    lands back on the kernel and back on the divergence.

    So this is the same defect as the map above, reached by growing the NBUNCH
    instead of shrinking the graph - and it is the shape that says the gate is a
    mitigation rather than a fix. Measured: networkx ('completes', 223), fnx
    RuntimeError('dictionary changed size during iteration').
    """
    assert _iterate_and_mutate(fnx, "Graph", 20000, 120) == _iterate_and_mutate(
        nx, "Graph", 20000, 120
    )


def test_the_row_rule_baseline_is_what_makes_the_obvious_fix_expensive():
    """WHY the fix above is reverted rather than pending: it is not free.

    The row rule needs, per nbunch node, the size that row had when iteration
    started. Taking that snapshot means asking the graph for a degree per node,
    and every one of those hashes a full-length node key - so the guard becomes
    O(nbunch x key length) on a call networkx answers without touching the keys
    at all. This test states the cost as a fact rather than an opinion, so a
    future cheaper baseline (an index-keyed snapshot that never hashes a key, or
    holding the row objects the way the Python walk does) has a number to beat.

    Asserted as a RATIO against the graph's own short-key cost, so it measures
    the key-length slope rather than the host.
    """
    import time

    def snapshot_cost(key_length):
        graph = fnx.Graph()
        nodes = [f"n{i}".ljust(key_length, "x") for i in range(400)]
        graph.add_edges_from(
            [(nodes[i], nodes[(i + 1) % 400]) for i in range(400)]
        )
        nbunch = nodes[:200]
        pairs = graph._native_degree_pairs_subset
        best = None
        for _ in range(5):
            start = time.perf_counter_ns()
            dict(pairs(list(nbunch)))
            elapsed = time.perf_counter_ns() - start
            best = elapsed if best is None else min(best, elapsed)
        return best

    short, long = snapshot_cost(3), snapshot_cost(2000)
    assert long > short * 5, (
        "the row-rule baseline no longer grows with key length - if a cheaper "
        f"snapshot landed, the revert in EdgeDataView.__iter__ can be revisited "
        f"(short={short}ns long={long}ns)"
    )
