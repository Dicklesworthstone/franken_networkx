"""The dijkstra negative-weight guard must read VALUES, not live attr dicts.

br-r37-c1-4m4wb. ``_has_negative_edge_weight_for_dijkstra`` runs on every
weighted shortest-path call. It reads exactly one key - ``weight`` - but walked
``G.edges(data=True)`` (and ``edges(keys=True, data=True)`` for multigraphs),
which hands out the LIVE attr dict of every edge. That is on the verified
CONTAMINATES list in ``test_weighted_store_contamination_map.py``: it permanently
disables the weighted-store fast path for the whole graph
(br-r37-c1-igdzi measured ``size(weight)`` 4.395x -> 0.733x, never lifting).

MULTIGRAPHS TOOK THAT WALK EVERY TIME, because the native negative scan returns
None for them - so a weighted shortest-path call poisoned the graph's weighted
store as a side effect of a guard that only ever looks at one number.

``edges(data=weight, default=1)`` yields the value, is on the verified SAFE list,
and skips materialising a dict per edge.

WHAT THIS FILE CAN AND CANNOT PROVE, stated because the obvious test does not
work. The only Python-visible dirty probe is
``_native_weighted_degree_int_values``, which returns None for ANY non-int weight,
not only for a dirty store - and the Python walk is only REACHED when a weight is
non-finite (simple graphs) or the class is a multigraph (no int-values kernel
exists). Those two sets do not intersect, so there is no configuration in which
the probe can watch this walk contaminate. The contamination argument therefore
rests on the map - ``data=True`` contaminates, ``data=weight`` does not, both
verified there - and not on a measurement here.

What IS pinned here is the part that could actually break: the guard's answer.
``attrs.get(weight, 1)`` and ``edges(data=weight, default=1)`` must agree on
every shape that matters - a missing weight, a negative one, ``-inf``, ``+inf``,
``NaN``, zero, a float, a non-numeric value, parallel edges disagreeing with each
other, and self-loops - because this guard decides whether dijkstra runs at all.
"""

from __future__ import annotations

import math
import numbers

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import _has_negative_edge_weight_for_dijkstra as _guard

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

WEIGHTS = {
    "positive": 3,
    "negative": -1,
    "negative_float": -0.5,
    "zero": 0,
    "neg_inf": -math.inf,
    "pos_inf": math.inf,
    "nan": float("nan"),
    "string": "heavy",
    "none": None,
    "bool_true": True,
    "bool_false": False,
}


def _build(lib, cls, value):
    g = getattr(lib, cls)()
    g.add_edge("a", "b", weight=value)
    g.add_edge("b", "c", weight=2)
    g.add_edge("c", "d")  # weight absent -> nx default of 1
    return g


def _oracle(graph, weight="weight"):
    """The semantics the guard implements, read straight off the edge data."""
    if graph.is_multigraph():
        attrs = [d for *_rest, d in graph.edges(keys=True, data=True)]
    else:
        attrs = [d for *_rest, d in graph.edges(data=True)]
    for d in attrs:
        value = d.get(weight, 1)
        if isinstance(value, numbers.Real) and not (
            isinstance(value, float) and math.isnan(value)
        ):
            if value < 0:
                return True
    return False


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("label", sorted(WEIGHTS))
def test_guard_matches_the_oracle(cls, label):
    graph = _build(fnx, cls, WEIGHTS[label])
    reference = _build(nx, cls, WEIGHTS[label])
    assert _guard(graph, "weight") == _oracle(reference)


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_parallel_edges_disagreeing_are_all_inspected(cls):
    """The multigraph walk must see EVERY parallel edge, not just the first."""
    graph, reference = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (graph, reference):
        g.add_edge("a", "b", weight=5)
        g.add_edge("a", "b", weight=5)
        g.add_edge("a", "b", weight=-3)  # only the third is negative
    assert _guard(graph, "weight") is True
    assert _oracle(reference) is True


@pytest.mark.parametrize("cls", CLASSES)
def test_a_negative_self_loop_is_found(cls):
    graph, reference = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (graph, reference):
        g.add_edge("a", "b", weight=1)
        g.add_edge("c", "c", weight=-2)
    assert _guard(graph, "weight") is True
    assert _oracle(reference) is True


@pytest.mark.parametrize("cls", CLASSES)
def test_a_missing_weight_uses_the_unit_default(cls):
    """`default=1` must reproduce `attrs.get(weight, 1)` — 1 is not negative."""
    graph, reference = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (graph, reference):
        g.add_edge("a", "b")
        g.add_edge("b", "c")
    assert _guard(graph, "weight") is False
    assert _oracle(reference) is False


@pytest.mark.parametrize("cls", CLASSES)
def test_a_non_default_weight_key_is_honoured(cls):
    graph = getattr(fnx, cls)()
    graph.add_edge("a", "b", weight=5, cost=-1)
    assert _guard(graph, "weight") is False
    assert _guard(graph, "cost") is True


@pytest.mark.parametrize("cls", CLASSES)
def test_a_non_string_weight_is_not_scanned(cls):
    """The guard short-circuits on a non-str weight before touching edges."""
    graph = getattr(fnx, cls)()
    graph.add_edge("a", "b", weight=-1)
    assert _guard(graph, None) is False


@pytest.mark.parametrize("cls", CLASSES)
def test_an_empty_graph_is_not_negative(cls):
    assert _guard(getattr(fnx, cls)(), "weight") is False


@pytest.mark.parametrize("cls", CLASSES)
def test_the_end_to_end_dispatch_still_agrees_with_networkx(cls):
    """The guard exists to route dijkstra; check the routing, not just the flag."""
    graph, reference = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (graph, reference):
        g.add_edge("a", "b", weight=1)
        g.add_edge("b", "c", weight=2)
        g.add_edge("a", "c", weight=10)
    assert fnx.dijkstra_path(graph, "a", "c") == nx.dijkstra_path(reference, "a", "c")
    assert fnx.dijkstra_path_length(graph, "a", "c") == nx.dijkstra_path_length(
        reference, "a", "c"
    )

    for g in (graph, reference):
        g.add_edge("c", "d", weight=-4)

    def outcome(lib, g):
        try:
            return ("ok", lib.dijkstra_path(g, "a", "d"))
        except Exception as exc:  # noqa: BLE001 - comparing the raise itself
            return (type(exc).__name__,)

    assert outcome(fnx, graph)[0] == outcome(nx, reference)[0]
