"""The dijkstra weight guards must be native for multigraphs, and still correct.

br-r37-c1-mgnegscan-8l53h. ``graph_has_negative_edge_weight`` and
``graph_has_nonfinite_edge_weight`` returned ``None`` for both multigraph arms, and the
shim reads ``None`` as "no native scan available" and answers with a per-edge Python walk
over ``G.edges(keys=True, data=True)``. Both guards run on every weighted shortest-path
call, so MultiGraph and MultiDiGraph paid a full Python pass over every edge each time
while the simple classes were served natively: 1635 and 1236 Python frames for one guard
call on a 400-edge graph, against 4 for Graph and DiGraph.

THE NEGATIVE CASE IS PARALLEL EDGES, and it is the reason this is a correctness test and
not only a perf one. A multigraph edge is (u, v, key). A scan that looked at one edge per
(u, v) pair would miss a negative weight hiding on a second parallel edge, and the symptom
is not slowness — it is fnx running its own dijkstra where networkx delegates and raises.
``test_negative_weight_on_a_parallel_edge_is_detected`` puts the negative weight on the
SECOND parallel edge specifically.

Semantics are mirrored from the simple-class scans rather than improved: only FINITE
negatives count. The shim depends on that, because it runs a separate ``-inf`` sweep
afterwards precisely because the native scan does not report ``-inf``.
"""

import math
import sys

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
ALL_CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

NEG_GUARD = "_has_negative_edge_weight_for_dijkstra"
INF_GUARD = "_has_positive_infinity_edge_weight_for_dijkstra"


def _build(module, cls_name, n=120):
    graph = getattr(module, cls_name)()
    for i in range(n):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % n}", weight=float(i % 17))
    return graph


def _guard_frames(graph, guard_name):
    """Python frames one guard call costs. Load-independent, so it holds under load."""
    guard = fnx.__dict__[guard_name]
    guard(graph, "weight")  # warm
    seen = []

    def record(frame, event, _arg):
        if event == "call":
            seen.append(frame.f_code.co_name)

    sys.setprofile(record)
    try:
        guard(graph, "weight")
    finally:
        sys.setprofile(None)
    return len(seen)


@pytest.mark.parametrize("guard_name", [NEG_GUARD, INF_GUARD])
@pytest.mark.parametrize("cls_name", ALL_CLASSES)
def test_guard_does_not_walk_the_edges_in_python(cls_name, guard_name):
    """THE REGRESSION TEST, and it is a frame count rather than a timing.

    A per-edge walk is O(E) frames; the native path is a small constant. The bound is set
    well above the constant and far below one-frame-per-edge on a 120-edge fixture, so it
    cannot be tripped by ordinary churn but fails immediately if the multigraph gate or the
    ``None`` arm comes back.
    """
    graph = _build(fnx, cls_name)
    frames = _guard_frames(graph, guard_name)
    assert frames < 20, (
        f"{cls_name} {guard_name} cost {frames} Python frames on a 120-edge graph, i.e. it "
        f"is walking the edges in Python again. Either the native multigraph arm went back "
        f"to returning None or the `not G.is_multigraph()` gate is back in the shim."
    )


@pytest.mark.parametrize("cls_name", MULTI)
def test_negative_weight_on_a_parallel_edge_is_detected(cls_name):
    """NEGATIVE CASE. The negative weight sits on the SECOND parallel edge.

    A scan keyed by (u, v) rather than (u, v, key) returns False here, and fnx then runs
    its own dijkstra on a graph networkx rejects -- a wrong answer, not a slow one.
    """
    guard = fnx.__dict__[NEG_GUARD]
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("a", "b", weight=-5.0)  # second PARALLEL edge, negative
    graph.add_edge("b", "c", weight=2.0)
    assert guard(graph, "weight") is True, (
        f"{cls_name}: a negative weight on a parallel edge must be detected; a scan that "
        f"inspects one edge per (u, v) pair misses it"
    )


@pytest.mark.parametrize("cls_name", MULTI)
def test_nonfinite_on_a_parallel_edge_is_detected(cls_name):
    """Same case for the non-finite scan, which gates the +inf guard's fast return."""
    guard = fnx.__dict__[INF_GUARD]
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("a", "b", weight=math.inf)  # second PARALLEL edge, +inf
    assert guard(graph, "weight") is True, (
        f"{cls_name}: a +inf weight on a parallel edge must be detected"
    )


@pytest.mark.parametrize("cls_name", MULTI)
def test_finite_only_multigraph_reports_no_negative(cls_name):
    """The common case must still answer False, or everything delegates to networkx."""
    guard = fnx.__dict__[NEG_GUARD]
    graph = _build(fnx, cls_name)
    assert guard(graph, "weight") is False


WEIGHT_SHAPES = [
    ("all finite", None),
    ("a negative", -3.0),
    ("minus inf", -math.inf),
    ("plus inf", math.inf),
    ("a nan", math.nan),
    ("missing weight", "OMIT"),
]


@pytest.mark.parametrize(
    ("label", "injected"), WEIGHT_SHAPES, ids=[s[0].replace(" ", "-") for s in WEIGHT_SHAPES]
)
@pytest.mark.parametrize("cls_name", MULTI)
def test_shortest_path_matches_networkx_across_weight_shapes(cls_name, label, injected):
    """End-to-end parity. The guards exist to decide when to delegate to networkx.

    A scan whose verdict shifted would not fail the frame-count test -- it would silently
    change which graphs fnx computes itself. Exceptions are compared too, because the -inf
    case is a delegation that RAISES in networkx.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = _build(module, cls_name, n=40)
        if injected == "OMIT":
            graph.add_edge("a", "b")  # parallel-free edge with no weight key
        elif injected is not None:
            graph.add_edge("n0", "n3", weight=injected)  # a PARALLEL edge
        try:
            result = module.single_source_dijkstra_path_length(graph, "n0", weight="weight")
            outcomes[name] = ("ok", sorted(dict(result).items())[:6])
        except Exception as exc:  # noqa: BLE001 - the exception IS the contract
            outcomes[name] = (type(exc).__name__, str(exc)[:80])
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name} with {label}: networkx gave {outcomes['nx']}, fnx gave {outcomes['fnx']}."
    )
