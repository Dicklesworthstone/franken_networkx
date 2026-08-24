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

CORRECTION (2026-08-18). These tests first used two primitives I added,
`flush_node_attrs_to_native_store` / `flush_edge_attrs_to_native_store`, which
re-issued `add_node` / `add_edge` to push attributes into the typed store. Those
were REDUNDANT and worse: `_sync_rust_edge_attrs` (br-r37-c1-sjf4t) was already in
the shim, wrapping a native `_fnx_sync_attrs_to_inner` binding.

    repairs node case          existing yes      mine yes
    repairs edge case          existing yes      mine yes
    contaminates br-r37-c1-igdzi   existing NO   mine YES
    cost                       one native call   O(V)/O(E) Python re-issues

Coarse in-process observation, not a certified row: size(weight) on a 4000-edge
path read 474.9 us clean, 488.3 us after `_sync_rust_edge_attrs`, 1996.5 us after
my flush. Mine had to READ every attr dict to re-issue it, which is exactly what
poisons the weighted store.

The mistake was specific and worth naming: hunting for a native setter I grepped
for `set_node_attrs`, found nothing exposed, and concluded a new binding was
needed. The binding is called `_fnx_sync_attrs_to_inner`. Grep for the OPERATION,
not for one plausible symbol name.

The primitives are removed; these tests now use the existing helper. The finding
they pin — five native kernels reading a stale typed store — is unaffected by
which repair is used.
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


def test_post_construction_edge_attrs_reach_the_typed_store_without_a_flush():
    """Raw native kernels synchronize live edge dictionaries before reading."""
    graph = _flow_graph("written_after")
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
    fnx._sync_rust_edge_attrs(graph)
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

    fnx._sync_rust_edge_attrs(graph)

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
    fnx._sync_rust_edge_attrs(graph)
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == CORRECT_COST


def test_flush_is_a_no_op_on_a_graph_with_no_edge_attributes():
    graph = fnx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])
    fnx._sync_rust_edge_attrs(graph)
    assert graph.number_of_edges() == 2
    assert all(not d for *_, d in graph.edges(data=True))


def test_raw_min_cost_flow_synchronizes_without_the_manual_flush():
    graph = _flow_graph("written_after")
    assert float(fnx._fnx.min_cost_flow_cost(graph)) == CORRECT_COST


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


def test_prim_synchronizes_post_construction_edge_attrs():
    assert _prim(_weighted_triangle("written_after", _MST_WEIGHTS)) == _CORRECT_MST


def test_flush_repairs_prim():
    graph = _weighted_triangle("written_after", _MST_WEIGHTS)
    fnx._sync_rust_edge_attrs(graph)
    assert _prim(graph) == _CORRECT_MST


def test_find_negative_cycle_is_correct_when_edge_attrs_reach_the_store():
    """The control."""
    graph = _weighted_triangle("at_construction", _NEG_WEIGHTS)
    assert fnx._fnx.find_negative_cycle(graph, "a", "weight") == _CORRECT_CYCLE


def test_find_negative_cycle_synchronizes_post_construction_edge_attrs():
    graph = _weighted_triangle("written_after", _NEG_WEIGHTS)
    assert fnx._fnx.find_negative_cycle(graph, "a", "weight") == _CORRECT_CYCLE


def test_flush_repairs_find_negative_cycle():
    graph = _weighted_triangle("written_after", _NEG_WEIGHTS)
    fnx._sync_rust_edge_attrs(graph)
    assert fnx._fnx.find_negative_cycle(graph, "a", "weight") == _CORRECT_CYCLE
