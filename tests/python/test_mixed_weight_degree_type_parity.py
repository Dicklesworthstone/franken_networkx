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

import json
import random
import sys

import franken_networkx as fnx
import networkx as nx
import pytest

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


# hhj5p.7: these are actual interpreter/oracle differences, not tolerances.
_SUM_BOUNDARIES = {
    "float-cancellation": [1e16, 1.0, -1e16],
    "integer-after-float": [0.0, 1e16, 1, -1e16],
    "prefix-promotion": [3, 0.2, 0.1, 0.1],
    "finite-overflow": [1e308, 1e308, -1e308],
    "signed-zero-negative": [0.0, -0.0, 0, -7, -2.5],
    "missing-weight": [1.5, None, 2, 0.2],
    "bool-generic": [True, 3, 1.5, False],
    "integer-prefix-overflow": [2**63 - 1, 1, -(2**63 - 1), 1.0, 0.1, 0.1],
}


def _exact_number(value):
    return (type(value).__name__, value.hex() if isinstance(value, float) else repr(value))


def _boundary_graph(lib, class_name, values, bulk, reverse):
    graph = getattr(lib, class_name)()
    graph.add_nodes_from(["hub", *range(len(values)), "isolated"])
    items = list(enumerate(values))
    if reverse:
        items.reverse()
    edges = [("hub", i, {} if value is None else {"weight": value})
             for i, value in items]
    edges.append(("hub", "hub", {"weight": 0.1}))
    if graph.is_directed():
        edges.append((0, "hub", {"weight": 0.7}))
    if bulk:
        graph.add_edges_from(edges)
    else:
        for u, v, attrs in edges:
            graph.add_edge(u, v, **attrs)
    if graph.is_multigraph():
        graph.add_edge("hub", "hub", weight=0.2)
    return graph


def _exact_reads(graph):
    result = {}
    names = ("degree", "in_degree", "out_degree") if graph.is_directed() else ("degree",)
    for name in names:
        degree = getattr(graph, name)
        result[name] = [(node, _exact_number(value)) for node, value in degree(weight="weight")]
        result[name + "-one"] = _exact_number(degree("hub", weight="weight"))
        result[name + "-subset"] = [(node, _exact_number(value)) for node, value in
                                    degree(["hub", "isolated", "hub"], weight="weight")]
    result["size"] = _exact_number(graph.size(weight="weight"))
    return result


class _SumInt(int):
    """A non-exact int exits CPython's initial fast integer loop."""


class _SumFloat(float):
    """A non-exact float takes Python's generic addition route."""


class _AddSeven(int):
    def __radd__(self, other):
        return other + int(self) + 7


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("values", [
    [1, _SumInt(1), -1e16, _SumInt(1), -1],
    [_SumInt(0), 1e16, 1.0, -1e16],
    [0.0, 1e16, _SumFloat(1.0), -1e16],
    [0, _AddSeven(1), 1e16, 1.0, -1e16],
], ids=["integer-prefix", "integer-first", "float-middle", "custom-add"])
@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("exposure", ["fresh", "read", "sync", "mutated-sync"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_numeric_subclass_sum_routes_exact(class_name, values, bulk, reverse, exposure, mode):
    """hhj5p.7: numeric equality does not preserve sum's type dispatch."""
    with fnx.compatibility_mode(mode):
        ours = _boundary_graph(fnx, class_name, values, bulk, reverse)
        oracle = _boundary_graph(nx, class_name, values, bulk, reverse)
        if exposure == "read":
            list(ours.edges(data=True))
            list(oracle.edges(data=True))
        if exposure == "mutated-sync":
            for graph in (ours, oracle):
                attrs = graph["hub"][0][0] if graph.is_multigraph() else graph["hub"][0]
                attrs["weight"] = _SumInt(1)
        if "sync" in exposure:
            # Native algorithm wrappers perform this sync; it must not declare
            # a lossy numeric projection exact for subsequent degree/size reads.
            _exact_reads(ours)
            ours._fnx_sync_attrs_to_inner()
        got, want = _exact_reads(ours), _exact_reads(oracle)
    trace = {"python": sys.version, "networkx": nx.__version__, "class_name": class_name,
             "values": [(type(value).__name__, repr(value)) for value in values],
             "bulk": bulk, "reverse": reverse, "exposure": exposure, "mode": mode,
             "got": got, "want": want}
    assert got == want, json.dumps(trace, sort_keys=True)


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("case", list(_SUM_BOUNDARIES))
@pytest.mark.parametrize("bulk", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("exposure", ["fresh", "read", "mutated"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_interpreter_sum_boundaries_exact(class_name, case, bulk, reverse, exposure, mode):
    values = _SUM_BOUNDARIES[case]
    with fnx.compatibility_mode(mode):
        ours = _boundary_graph(fnx, class_name, values, bulk, reverse)
        oracle = _boundary_graph(nx, class_name, values, bulk, reverse)
        for graph in (ours, oracle):
            if exposure != "fresh":
                list(graph.edges(data=True))
            if exposure == "mutated":
                attrs = graph["hub"][0]
                if graph.is_multigraph():
                    attrs = attrs[0]
                attrs["weight"] = 0.2
        got, want = _exact_reads(ours), _exact_reads(oracle)
        record = {
            "python": sys.version, "oracle": nx.__version__, "cls": class_name,
            "case": case, "bulk": bulk, "reverse": reverse, "exposure": exposure,
            "mode": mode, "inputs": [_exact_number(x) for x in values],
            "nodes": list(oracle), "edges": [(u, v, _exact_number(data.get("weight", 1)))
                                           for u, v, data in oracle.edges(data=True)],
            "got": got, "want": want,
        }
        print(json.dumps(record), flush=True)
        assert got == want, record


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("case", ["float-cancellation", "integer-after-float"])
def test_wrong_interpreter_sum_policy_is_detectable(class_name, case):
    values = _SUM_BOUNDARIES[case]
    expected = sum(values)
    compensated = sys.version_info >= ((3, 14) if case == "integer-after-float" else (3, 12))
    wrong_policy_value = 0.0 if compensated else 1.0
    assert _exact_number(expected) != _exact_number(wrong_policy_value)
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, class_name)()
        for i, value in enumerate(values):
            graph.add_edge("hub", i, weight=value)
        graphs.append(graph)
    view = "out_degree" if "Di" in class_name else "degree"
    got = getattr(graphs[0], view)("hub", weight="weight")
    want = getattr(graphs[1], view)("hub", weight="weight")
    assert _exact_number(want) == _exact_number(expected)
    assert _exact_number(got) == _exact_number(want)
    for nodes in (None, ["hub", "hub"]):
        got = [(node, _exact_number(value)) for node, value in
               getattr(graphs[0], view)(nodes, weight="weight")]
        want = [(node, _exact_number(value)) for node, value in
                getattr(graphs[1], view)(nodes, weight="weight")]
        assert got == want, (class_name, case, nodes, got, want)
