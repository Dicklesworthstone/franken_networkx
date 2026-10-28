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


def test_multidigraph_bellman_ford_collapse_cache_invalidation():
    g = fnx.MultiDiGraph()
    g.add_edge("a", "b", weight=1.0)
    g.add_edge("b", "c", weight=2.0)

    len1 = fnx.bellman_ford_path_length(g, "a", "c", weight="weight")
    assert len1 == 3.0
    # Cache hit on second call
    len2 = fnx.bellman_ford_path_length(g, "a", "c", weight="weight")
    assert len2 == 3.0

    # In-place edge attribute write invalidates cache
    g["a"]["b"][0]["weight"] = 99.0
    len3 = fnx.bellman_ford_path_length(g, "a", "c", weight="weight")
    assert len3 == 101.0

    # Adding an edge updates revision tokens
    g.add_edge("a", "c", weight=5.0)
    len4 = fnx.bellman_ford_path_length(g, "a", "c", weight="weight")
    assert len4 == 5.0

    # Undirected MultiGraph
    mg = fnx.MultiGraph()
    mg.add_edge("x", "y", weight=10.0)
    mg.add_edge("y", "z", weight=20.0)
    assert fnx.bellman_ford_path_length(mg, "x", "z", weight="weight") == 30.0
    assert fnx.bellman_ford_path_length(mg, "x", "z", weight="weight") == 30.0
    mg["x"]["y"][0]["weight"] = 50.0
    assert fnx.bellman_ford_path_length(mg, "x", "z", weight="weight") == 70.0


@pytest.mark.parametrize("graph_class", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_bellman_ford_collapse_cache_hits_on_an_unchanged_graph(graph_class):
    """The cache above is only worth its invalidation rules if it ever HITS.

    7c93b9d86 (urjxk) added attr_rewrites to the revision token and to the lookup key, but
    the stores kept the old 3-item key, so for a month every call missed and paid the full
    collapse (75.3% of bellman_ford_path_length per mg7hw). An unchanged graph must get the
    very same collapse back; a weight write must not.
    """
    from franken_networkx._impl.s19_single_source_dijkstra import (
        _multigraph_collapse_min_weight_bellman as collapse,
    )

    g = getattr(fnx, graph_class)()
    g.add_edge("a", "b", weight=5.0)
    g.add_edge("a", "b", weight=2.0)
    g.add_edge("b", "c", weight=1.0)

    first = collapse(g, "weight")
    assert first[1] is False
    assert collapse(g, "weight") is first

    # A write through an escaped edge dict raises edge_attrs_dirty, which turns the cache
    # off for this graph: the collapse is rebuilt and sees the new weight.
    g["a"]["b"][0]["weight"] = 0.5
    refreshed = collapse(g, "weight")
    assert refreshed is not first
    assert refreshed[0]["a"]["b"]["weight"] == 0.5
    assert fnx.bellman_ford_path_length(g, "a", "c", weight="weight") == 1.5
