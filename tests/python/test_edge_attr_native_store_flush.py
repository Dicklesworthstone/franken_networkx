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
