"""MultiDiGraph bellman_ford_path_length weight/error contract vs networkx.

br-r37-c1-mg7hw. The multigraph branch of ``bellman_ford_path_length`` reaches the simple
kernel through ``_multigraph_collapse_min_weight_bellman``, a per-call collapse that
builds a whole new simple graph and costs 75.3% of the operation (41.5M of 55.1M Ir/call
at N=800; networkx's entire call is 20.1M). Routing straight to the native
``_raw_bellman_ford_path_length``, which accepts a MultiDiGraph directly, is 1.24x cheaper
(44.3M) and is the obvious thing to try.

IT IS WRONG, AND THIS FILE IS WHY. The collapse is not purely an optimization: it also
carries the weight-validation the raw kernel has no notion of. Measured against the raw
kernel as the unfixed arm, 12 of the 18 rows below diverge from networkx - including
SILENT WRONG ANSWERS, where a NaN, inf or non-numeric weight returns 2.0 instead of
raising or returning -inf. A guard is worth nothing until it has been seen to fail on the
implementation it forbids, so those divergences are recorded here:

    plain int              nx 3      raw 3.0     (int-vs-float length type lost)
    missing weight attr    nx 2      raw 2.0
    source == target       nx 0      raw 0.0
    bool weight            nx 2      raw 2.0
    nan weight             nx raises NetworkXNoPath        raw returns 2.0
    inf weight             nx raises NetworkXNoPath        raw returns 2.0
    non-numeric weight     nx raises TypeError             raw returns 2.0
    neg inf weight         nx returns -inf                 raw returns 2.0
    negative cycle         nx "Negative cycle detected."   raw "Negative cost cycle ..."
    unreachable target     nx "node z not reachable from a"
                           raw "No path between str:1:a and str:1:z."  (canonical key
                           leaking into a user-facing message, the br-r37-c1-rmzr6 class)
    missing source         nx "Source zz not in G"         raw "Source 'zz' is not in G"
    missing target         nx raises NetworkXNoPath        raw raises NodeNotFound

So this file locks the CONTRACT the collapse provides, not the collapse itself. Any future
change that makes the multigraph branch cheaper - a cached collapse keyed on a revision
token, or a native multigraph kernel that learns weight validation - is free to land as
long as these rows stay green.

Exception ARGS are compared, not just types: a type-only sweep reports false green.
"""

import math

import networkx as nx
import pytest

import franken_networkx as fnx

# (id, edges, source, target, extra isolated nodes)
CASES = [
    ("plain_float", [("a", "b", 1.0), ("b", "c", 2.0)], "a", "c", ()),
    ("plain_int", [("a", "b", 1), ("b", "c", 2)], "a", "c", ()),
    ("parallel_min_wins", [("a", "b", 5.0), ("a", "b", 2.0), ("b", "c", 1.0)], "a", "c", ()),
    ("parallel_int_float_mix", [("a", "b", 5), ("a", "b", 2.0), ("b", "c", 1)], "a", "c", ()),
    ("negative_weight", [("a", "b", -1.0), ("b", "c", 2.0)], "a", "c", ()),
    ("negative_cycle", [("a", "b", 1.0), ("b", "a", -5.0), ("b", "c", 1.0)], "a", "c", ()),
    ("nan_weight", [("a", "b", float("nan")), ("b", "c", 1.0)], "a", "c", ()),
    ("inf_weight", [("a", "b", float("inf")), ("b", "c", 1.0)], "a", "c", ()),
    ("neg_inf_weight", [("a", "b", float("-inf")), ("b", "c", 1.0)], "a", "c", ()),
    ("non_numeric_weight", [("a", "b", "heavy"), ("b", "c", 1.0)], "a", "c", ()),
    ("missing_weight_attr", [("a", "b"), ("b", "c")], "a", "c", ()),
    ("source_equals_target", [("a", "b", 1.0)], "a", "a", ()),
    ("unreachable_target", [("a", "b", 1.0)], "a", "z", ("z",)),
    ("missing_source", [("a", "b", 1.0)], "zz", "b", ()),
    ("missing_target", [("a", "b", 1.0)], "a", "zz", ()),
    ("self_loop", [("a", "a", 1.0), ("a", "b", 2.0)], "a", "b", ()),
    ("zero_weight", [("a", "b", 0.0), ("b", "c", 0.0)], "a", "c", ()),
    ("bool_weight", [("a", "b", True), ("b", "c", 1)], "a", "c", ()),
]


def _build(module, edges, nodes):
    graph = module.MultiDiGraph()
    for node in nodes:
        graph.add_node(node)
    for edge in edges:
        if len(edge) == 3:
            u, v, weight = edge
            graph.add_edge(u, v, weight=weight)
        else:
            graph.add_edge(*edge)
    return graph


def _outcome(module, edges, source, target, nodes):
    graph = _build(module, edges, nodes)
    try:
        value = module.bellman_ford_path_length(graph, source, target, weight="weight")
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return ("raise", type(exc).__name__, tuple(str(a) for a in exc.args))
    # NaN never equals itself; nothing else is normalised, because the int-vs-float
    # distinction in the returned length is one of the things under test.
    if isinstance(value, float) and math.isnan(value):
        return ("ok", "nan")
    return ("ok", repr(value), type(value).__name__)


@pytest.mark.parametrize(
    ("edges", "source", "target", "nodes"),
    [pytest.param(e, s, t, n, id=i) for i, e, s, t, n in CASES],
)
def test_multidigraph_bellman_ford_length_matches_networkx(edges, source, target, nodes):
    assert _outcome(fnx, edges, source, target, nodes) == _outcome(
        nx, edges, source, target, nodes
    )
