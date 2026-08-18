"""br-r37-c1-edge-attr-typed-store-pk1nb — the EDGE-side typed-store gap.

Edge attributes written after ``add_edges_from`` never reach the typed store
native kernels read. The miss takes a default, so the kernel returns a plausible
WRONG answer while the Python view shows the correct values.

NOT THE SAME DEFECT AS br-r37-c1-303zo, and the discriminator is ``copy()``. That
bead's own diagnostic is that a rebuild materialises the attributes into the
typed store and repairs the node-side gap. On the edge side it does not:

    edges at construction   nx 10   fnx 10.0   after copy() 10.0   ok
    edges written after     nx 10   fnx  0.0   after copy()  0.0   DIVERGES

so the standard workaround does not apply there, which is why this is filed and
tested separately rather than folded into 303zo.

THESE TESTS CALL ``_fnx.<kernel>`` DIRECTLY, and that is load-bearing. The public
``fnx.min_cost_flow`` is implemented in Python in the shim, so a test through the
public API measures the shim and reports the kernel clean. The bug is DORMANT,
not absent: routing any edge-attr-reading kernel native ships a wrong answer.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

CORRECT_COST = 10.0


def _flow_graph(edge_route):
    """Node demands always go through add_node, isolating the EDGE variable."""
    graph = fnx.DiGraph()
    graph.add_node("s", demand=-5)
    graph.add_node("m")
    graph.add_node("t", demand=5)
    if edge_route == "at_construction":
        graph.add_edges_from(
            [
                ("s", "m", {"weight": 1, "capacity": 10}),
                ("m", "t", {"weight": 1, "capacity": 10}),
            ]
        )
        return graph

    graph.add_edges_from([("s", "m"), ("m", "t")])
    for u, v in (("s", "m"), ("m", "t")):
        graph[u][v]["weight"] = 1
        graph[u][v]["capacity"] = 10
    return graph


def test_edge_attrs_at_construction_reach_the_typed_store():
    """The control. Without it a failure below could be an unrelated bug."""
    graph = _flow_graph("at_construction")
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == CORRECT_COST


def test_the_python_view_is_correct_either_way():
    """Why this is silent: nothing looks wrong from Python."""
    for route in ("at_construction", "written_after"):
        graph = _flow_graph(route)
        assert [graph[u][v]["weight"] for u, v in (("s", "m"), ("m", "t"))] == [1, 1]


def test_copy_does_NOT_repair_the_edge_side():
    """The discriminator against br-r37-c1-303zo, pinned so it cannot be assumed.

    If this ever starts failing, the edge gap has acquired the node side's
    rebuild behaviour and the two beads have converged.
    """
    graph = _flow_graph("written_after")
    assert float(fnx._fnx.min_cost_flow_cost(graph.copy())) != CORRECT_COST


def test_flush_repairs_the_edge_side():
    graph = _flow_graph("written_after")
    fnx.flush_edge_attrs_to_native_store(graph)
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == CORRECT_COST


@pytest.mark.parametrize(
    "cls_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
)
def test_flush_does_not_disturb_the_graph(cls_name):
    """It re-issues add_edge, so pin that no parallel edge appears.

    The multigraph case is the one that could go wrong: re-issuing without the
    KEY would add a parallel edge instead of updating the existing one.
    """
    graph = getattr(fnx, cls_name)()
    multi = graph.is_multigraph()
    graph.add_edges_from([("a", "b"), ("a", "b")] if multi else [("a", "b")])
    if multi:
        for u, v, key in list(graph.edges(keys=True)):
            graph[u][v][key]["w"] = key + 1
    else:
        graph["a"]["b"]["w"] = 1

    before_count = graph.number_of_edges()
    before_pairs = sorted((u, v) for u, v in graph.edges())
    before_attrs = (
        [d.get("w") for *_, d in graph.edges(keys=True, data=True)]
        if multi
        else [d.get("w") for *_, d in graph.edges(data=True)]
    )

    fnx.flush_edge_attrs_to_native_store(graph)

    assert graph.number_of_edges() == before_count
    assert sorted((u, v) for u, v in graph.edges()) == before_pairs
    after_attrs = (
        [d.get("w") for *_, d in graph.edges(keys=True, data=True)]
        if multi
        else [d.get("w") for *_, d in graph.edges(data=True)]
    )
    assert after_attrs == before_attrs


def test_flush_accepts_an_edge_subset():
    graph = _flow_graph("written_after")
    fnx.flush_edge_attrs_to_native_store(graph, edges=[("s", "m"), ("m", "t")])
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == CORRECT_COST


def test_flush_is_a_no_op_on_a_graph_with_no_edge_attributes():
    graph = fnx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])
    fnx.flush_edge_attrs_to_native_store(graph)
    assert graph.number_of_edges() == 2
    assert all(not d for *_, d in graph.edges(data=True))


def test_the_bug_is_still_there_without_the_flush():
    """Pins the DEFECT, so this file fails if the flush stops being needed.

    If the typed store is ever fixed in Rust, this starts failing — the signal to
    delete the primitive and this file rather than leave dead code behind.
    """
    graph = _flow_graph("written_after")
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == 0.0, (
        "post-construction edge attrs now reach the typed store — if the store "
        "was fixed, flush_edge_attrs_to_native_store is dead code"
    )


# --- the census of EDGE-attr kernels ----------------------------------------
#
# Enumerated from the RUST side, which is the lesson br-r37-c1-303zo's audit
# taught the hard way: the Python-side name is not a reliable index of what
# exists (that audit nearly missed two kernels bound under a `_rust` suffix).
# Grepping crates/fnx-algorithms for an edge-attr read with a default on miss
# finds exactly two beyond min_cost_flow:
#
#     prim_raw_edge_weight  13376  .edge_attrs(u,v).get(w).as_f64().unwrap_or(1.0)
#     find_negative_cycle   33113  .edge_attrs(u,v).get(w).as_f64().unwrap_or(1.0)
#
# Both are affected, and both are repaired by the flush.


def _weighted_triangle(route, weights):
    graph = fnx.Graph()
    if route == "at_construction":
        graph.add_edges_from(
            [(u, v, {"weight": w}) for (u, v), w in weights.items()]
        )
        return graph
    graph.add_edges_from(list(weights))
    for (u, v), w in weights.items():
        graph[u][v]["weight"] = w
    return graph


# a-b and b-c are cheap, a-c is expensive: the MST must avoid a-c. With every
# weight defaulted to 1.0 the kernel cannot tell them apart and takes a-c.
_MST_WEIGHTS = {("a", "b"): 1.0, ("b", "c"): 1.0, ("a", "c"): 10.0}
_CORRECT_MST = [("a", "b"), ("b", "c")]
_STALE_MST = [("a", "b"), ("a", "c")]

# one genuinely negative edge: invisible if the weights are not seen.
_NEG_WEIGHTS = {("a", "b"): -5.0, ("b", "c"): 1.0, ("a", "c"): 1.0}
_CORRECT_CYCLE = ["a", "b", "a"]


def _prim(graph):
    edges = fnx._fnx.prim_spanning_edges(
        graph, "weight", True, list(range(graph.number_of_nodes())), False
    )
    return sorted(tuple(sorted((u, v))) for u, v, *_ in edges)


def test_prim_is_correct_when_edge_attrs_reach_the_store():
    """The control."""
    assert _prim(_weighted_triangle("at_construction", _MST_WEIGHTS)) == _CORRECT_MST


def test_prim_takes_the_WRONG_edge_without_the_flush():
    """Pins the defect: every weight defaults to 1.0, so the heavy edge is taken."""
    assert _prim(_weighted_triangle("written_after", _MST_WEIGHTS)) == _STALE_MST, (
        "prim no longer reads a stale edge store — if the store was fixed, "
        "flush_edge_attrs_to_native_store is dead code for this kernel"
    )


def test_flush_repairs_prim():
    graph = _weighted_triangle("written_after", _MST_WEIGHTS)
    fnx.flush_edge_attrs_to_native_store(graph)
    assert _prim(graph) == _CORRECT_MST


def test_find_negative_cycle_is_correct_when_edge_attrs_reach_the_store():
    """The control."""
    graph = _weighted_triangle("at_construction", _NEG_WEIGHTS)
    assert fnx._fnx.find_negative_cycle(graph, "a", "weight") == _CORRECT_CYCLE


def test_find_negative_cycle_MISSES_the_cycle_without_the_flush():
    """The negative edge defaults to 1.0, so the cycle vanishes entirely.

    This one does not merely return a wrong number — it raises, claiming no
    negative cycle exists on a graph that has one.
    """
    graph = _weighted_triangle("written_after", _NEG_WEIGHTS)
    with pytest.raises(Exception, match="[Nn]o negative cycle"):
        fnx._fnx.find_negative_cycle(graph, "a", "weight")


def test_flush_repairs_find_negative_cycle():
    graph = _weighted_triangle("written_after", _NEG_WEIGHTS)
    fnx.flush_edge_attrs_to_native_store(graph)
    assert fnx._fnx.find_negative_cycle(graph, "a", "weight") == _CORRECT_CYCLE
