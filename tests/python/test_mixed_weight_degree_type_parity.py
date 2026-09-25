"""Mixed int/float weights: networkx types the answer PER NODE, and so must fnx.

br-r37-c1-weightupdate-9rts1. fnx carries two whole-graph weighted-degree
accumulators, an integer one and a float one, and falls back to an exact Python
path when neither applies. A graph holding BOTH int and float weights takes the
fallback, which is why a single cross-type weight write drops `size(weight)` from
~5x of networkx to 0.83x.

A mixed accumulator would recover that, and this file is the contract it has to
meet. The contract is subtler than "sum as float", because networkx decides the
result type PER NODE, not per graph:

    node with only int incident weights   -> int
    node with any float incident weight   -> float
    int self-loop, weight 5               -> degree 10 (counted twice), still int
    float self-loop, weight 2.5           -> 5.0, float

So a fast path that promotes the whole graph to float would return 7.0 where
networkx returns 7, on a graph that merely has a float somewhere else. That is a
silent type divergence: it compares equal, so a value-only test passes.

These assertions hold on the exact path today; they exist so they keep holding
when the accumulator is added.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _mixed(lib, class_name):
    graph = getattr(lib, class_name)()
    graph.add_edge("allint_a", "allint_b", weight=3)
    graph.add_edge("allint_a", "x", weight=4)
    graph.add_edge("mixed", "y", weight=2)
    graph.add_edge("mixed", "z", weight=1.5)
    graph.add_edge("loop", "loop", weight=5)
    graph.add_edge("floop", "floop", weight=2.5)
    return graph


def _typed_degrees(graph):
    return {
        str(node): (value, type(value).__name__)
        for node, value in graph.degree(weight="weight")
    }


@pytest.mark.parametrize("class_name", CLASSES)
def test_degree_value_and_type_match_networkx_per_node(class_name):
    got = _typed_degrees(_mixed(fnx, class_name))
    want = _typed_degrees(_mixed(nx, class_name))
    assert got == want, f"{class_name}: per-node weighted degree diverged"


@pytest.mark.parametrize("class_name", CLASSES)
def test_an_all_int_node_stays_int_on_a_graph_that_has_floats(class_name):
    """The cell a whole-graph float promotion would silently break.

    `allint_a` touches only integer weights, so networkx returns an int even
    though the graph holds floats elsewhere. `7 == 7.0` is True, so only a type
    check catches a promotion here.
    """
    got = _typed_degrees(_mixed(fnx, class_name))["allint_a"]
    want = _typed_degrees(_mixed(nx, class_name))["allint_a"]
    assert got == want
    assert got[1] == "int", f"{class_name}: all-int node promoted to {got[1]}"


@pytest.mark.parametrize("class_name", CLASSES)
def test_self_loops_keep_networkxs_doubling_and_type(class_name):
    got = _typed_degrees(_mixed(fnx, class_name))
    want = _typed_degrees(_mixed(nx, class_name))
    assert got["loop"] == want["loop"]
    assert got["floop"] == want["floop"]


@pytest.mark.parametrize("class_name", CLASSES)
def test_size_matches_networkx_in_value_and_type(class_name):
    got = _mixed(fnx, class_name).size(weight="weight")
    want = _mixed(nx, class_name).size(weight="weight")
    assert got == want and type(got) is type(want)


@pytest.mark.parametrize("class_name", CLASSES)
def test_large_integer_weights_keep_exactness(class_name):
    """Above 2**53 an int cannot round-trip through f64.

    A mixed accumulator that converts ints to double must refuse these rather
    than answer approximately; networkx sums them exactly while they stay
    integral.
    """
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=2**53 + 1)
        graph.add_edge("a", "c", weight=2**53 + 3)
    assert dict(got.degree(weight="weight"))["a"] == dict(
        want.degree(weight="weight")
    )["a"]
    assert got.size(weight="weight") == want.size(weight="weight")


@pytest.mark.parametrize("class_name", CLASSES)
def test_cross_type_write_does_not_change_the_answer(class_name):
    """The mutation from the bead: writing an int weight onto a float graph."""
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        for i in range(20):
            graph.add_edge(f"n{i}", f"n{(i + 1) % 20}", weight=float(i) + 0.5)
        graph.add_edge("n0", "n1", weight=99)      # cross-type write
    assert _typed_degrees(got) == _typed_degrees(want)
    assert got.size(weight="weight") == want.size(weight="weight")


@pytest.mark.parametrize("class_name", CLASSES)
def test_bool_weights_match_networkx(class_name):
    """`bool` is an int subclass, but not `PyLong_CheckExact`.

    networkx's `sum` therefore takes its generic `PyNumber_Add` path and still
    answers with an int. A numeric accumulator must not quietly treat True as 1
    in a float total; refusing the graph is fine, answering differently is not.
    """
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=True)
        graph.add_edge("a", "c", weight=3)
        graph.add_edge("a", "d", weight=1.5)
    assert _typed_degrees(got) == _typed_degrees(want)
    assert got.size(weight="weight") == want.size(weight="weight")


@pytest.mark.parametrize("class_name", CLASSES)
def test_a_missing_weight_on_a_float_graph_defaults_to_int_one(class_name):
    """`dd.get(weight, 1)` — an unweighted edge contributes the INT 1.

    A float graph with one weightless edge is mixed for exactly this reason, so
    it lands on the same path as an int/float mixture and must agree per node.
    """
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=2.5)
        graph.add_edge("a", "c")               # no weight at all -> 1
        graph.add_edge("plain", "other")       # neither endpoint weighted
    assert _typed_degrees(got) == _typed_degrees(want)
    assert got.size(weight="weight") == want.size(weight="weight")


@pytest.mark.parametrize("class_name", CLASSES)
def test_a_large_int_beside_a_float_matches_networkx(class_name):
    """The 2**53 case where the integer prefix must CROSS into a float total.

    Unlike the all-int graph above, here the node holds a float too, so the
    integer can no longer stay exact. Whatever the accumulator does — refuse, or
    convert the way CPython's own sum does — the answer has to be networkx's.
    """
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_edge("a", "b", weight=2**53 + 1)
        graph.add_edge("a", "c", weight=0.5)
    assert _typed_degrees(got) == _typed_degrees(want)
    assert got.size(weight="weight") == want.size(weight="weight")


@pytest.mark.parametrize("class_name", CLASSES)
def test_isolated_zero_and_negative_weights_keep_networkxs_types(class_name):
    """`sum(())` is the INT 0, not 0.0 — even on a graph full of floats."""
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for graph in (got, want):
        graph.add_node("isolated")
        graph.add_edge("a", "b", weight=0)
        graph.add_edge("a", "c", weight=-4)
        graph.add_edge("d", "e", weight=-2.5)
        graph.add_edge("d", "f", weight=0.0)
    assert _typed_degrees(got) == _typed_degrees(want)
    assert _typed_degrees(got)["isolated"][1] == "int"
    assert got.size(weight="weight") == want.size(weight="weight")


def _promotion_graph(lib, class_name):
    graph = getattr(lib, class_name)()
    for other, weight in (("a", 3), ("b", 0.2), ("c", 0.1), ("d", 0.1)):
        graph.add_edge("hub", other, weight=weight)
    return graph


@pytest.mark.parametrize("class_name", CLASSES)
def test_the_promoting_add_is_not_compensated(class_name):
    """CPython's `sum` leaves its integer loop with a plain `3 + 0.2`.

    Only the float adds after the promotion are Neumaier-compensated, so
    `sum([3, 0.2, 0.1, 0.1])` is 3.4000000000000004. Compensating the promoting
    add too gives 3.4, and 3.4 != 3.4000000000000004, so the value comparison
    catches it (1 in 20 random mixed lists differed that way).
    """
    want = _typed_degrees(_promotion_graph(nx, class_name))
    assert want["hub"] == (3.4000000000000004, "float")
    assert _typed_degrees(_promotion_graph(fnx, class_name)) == want
    assert _promotion_graph(fnx, class_name).size(weight="weight") == _promotion_graph(
        nx, class_name
    ).size(weight="weight")


def _random_mixed(lib, class_name, seed):
    rng = random.Random(seed)
    graph = getattr(lib, class_name)()
    for _ in range(60):
        weight = rng.choice([1, 2, 3, -7, 0.1, 0.2, 0.7, 1e16, 1.5e-8])
        graph.add_edge(rng.randrange(12), rng.randrange(12), weight=weight)
    return graph


@pytest.mark.parametrize("class_name", CLASSES)
def test_mixed_weight_degrees_are_bit_identical_on_random_graphs(class_name):
    views = ["degree", "in_degree", "out_degree"] if "Di" in class_name else ["degree"]
    for seed in range(80):
        got, want = _random_mixed(fnx, class_name, seed), _random_mixed(nx, class_name, seed)
        for view in views:
            got_all = [(n, d, type(d)) for n, d in getattr(got, view)(weight="weight")]
            want_all = [(n, d, type(d)) for n, d in getattr(want, view)(weight="weight")]
            assert got_all == want_all, (seed, view)
            for node, value, kind in want_all:
                one = getattr(got, view)(node, weight="weight")
                assert (one, type(one)) == (value, kind), (seed, view, node)
        assert got.size(weight="weight") == want.size(weight="weight"), seed


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weights", ["int", "float"])
def test_single_node_weighted_degree_after_removals(class_name, weights):
    """yr2oc.4: between a removal and the next insertion node slots are not
    node positions. The single-node weighted degree reads a node's edges by
    slot; reading slot rows as if they were positions (or positions as slots)
    answers for the wrong node here. Self-loops included, every view."""
    rng = random.Random(3)
    got, want = getattr(fnx, class_name)(), getattr(nx, class_name)()
    for _ in range(150):
        u, v = rng.randrange(30), rng.randrange(30)
        w = rng.choice([1, 2, 5]) if weights == "int" else rng.choice([0.5, 0.25, 1.5])
        for graph in (got, want):
            graph.add_edge(u, v, weight=w)
    views = ["degree", "in_degree", "out_degree"] if "Di" in class_name else ["degree"]
    for victim in [3, 17, 0, 11, 25, 8]:
        for graph in (got, want):
            graph.remove_node(victim)
        for node in list(want):
            for view in views:
                one = getattr(got, view)(node, weight="weight")
                expected = getattr(want, view)(node, weight="weight")
                assert (one, type(one)) == (expected, type(expected)), (victim, view, node)
