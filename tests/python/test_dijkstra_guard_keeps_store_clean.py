"""fnx's own dijkstra negative-weight guard must not poison the caller's store.

br-r37-c1-4m4wb. ``_has_negative_edge_weight_for_dijkstra`` sweeps for ``-inf`` weights.
It used to do that with ``G.edges(data=True)``, which HANDS OUT the live edge attr dicts
and therefore marks the weighted store dirty for the life of the graph
(br-r37-c1-igdzi) -- so merely asking fnx for a shortest path could permanently slow every
later ``size(weight=...)`` / ``degree(weight=...)`` the caller makes, on a graph the caller
never mutated.

SCOPE, because the bead is broader than what actually reproduces on HEAD. The sweep runs
only when the native non-finite scan reports True, i.e. only on a graph that already holds
a non-finite weight; an all-finite graph skips it entirely, which is why an ordinary
dijkstra call never showed the defect. And only ``Graph`` pays: ``DiGraph``'s weighted read
does not use the whole-graph fallback that the dirty flag forces. So the case under test is
"Graph with a non-finite weight", and that is what these assertions pin.

The earlier fix was REVERTED because ``data=weight`` measured 2.88x ``data=True`` on this
scan. That trade was backwards: the 2.88x is a ONE-TIME cost on a rare path, and what it
bought was a PERMANENT whole-graph penalty on every later weighted read.
"""

import math
import sys

import networkx as nx
import pytest

import franken_networkx as fnx

NONFINITE = [
    ("plus_inf", math.inf),
    ("minus_inf", -math.inf),
]


def _build(module, cls_name, injected, n=200):
    graph = getattr(module, cls_name)()
    for i in range(n):
        graph.add_edge(f"n{i}", f"n{(i * 7 + 3) % n}", weight=float(i % 17))
    if injected is not None:
        graph.add_edge("n0", "n3", weight=injected)
    return graph


def _weighted_read_materialises_whole_graph(graph):
    """True when ``size(weight=...)`` took the whole-graph materialisation fallback.

    Frame-based rather than timed, so it means the same thing on a contended host as on an
    idle one -- this defect was found and fixed in a window at loadavg 49 with run queue 72,
    where a timing assertion would have been worthless.
    """
    seen = []

    def record(frame, event, _arg):
        if event == "call":
            seen.append(frame.f_code.co_name)

    graph.size(weight="weight")
    sys.setprofile(record)
    try:
        graph.size(weight="weight")
    finally:
        sys.setprofile(None)
    return "to_dict_of_dicts" in seen


@pytest.mark.parametrize(("label", "injected"), NONFINITE, ids=[n for n, _ in NONFINITE])
def test_guard_does_not_poison_the_store_on_a_nonfinite_graph(label, injected):
    """THE REGRESSION TEST. Running the guard must leave the store usable.

    Fails on the pre-fix arm, where the ``data=True`` sweep handed out every attr dict.
    """
    graph = _build(fnx, "Graph", injected)
    assert not _weighted_read_materialises_whole_graph(graph), (
        f"fixture with a {label} weight is already contaminated before the guard runs; "
        f"this test cannot mean anything if it starts dirty"
    )

    guard = fnx.__dict__["_has_negative_edge_weight_for_dijkstra"]
    guard(graph, "weight")

    assert not _weighted_read_materialises_whole_graph(graph), (
        f"fnx's own dijkstra guard poisoned the caller's weighted store on a graph "
        f"carrying a {label} weight. The -inf sweep is back on edges(data=True), which "
        f"hands out live attr dicts (br-r37-c1-4m4wb / br-r37-c1-igdzi)."
    )


@pytest.mark.parametrize(("label", "injected"), NONFINITE, ids=[n for n, _ in NONFINITE])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_guard_verdict_is_unchanged_by_the_spelling(cls_name, label, injected):
    """The sweep must still DETECT what it detected before.

    `data=True` gave `attrs.get(weight, 1)`; `data=weight, default=1` gives that same
    value. This asserts the verdict rather than trusting the equivalence: a -inf weight
    must be reported, a +inf weight must not.
    """
    guard = fnx.__dict__["_has_negative_edge_weight_for_dijkstra"]
    graph = _build(fnx, cls_name, injected)
    assert guard(graph, "weight") is (injected == -math.inf), (
        f"{cls_name} with a {label} weight: the guard must report negative-weight "
        f"presence for -inf and not for +inf"
    )


@pytest.mark.parametrize(("label", "injected"), NONFINITE, ids=[n for n, _ in NONFINITE])
@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_shortest_path_matches_networkx_on_nonfinite_weights(cls_name, label, injected):
    """The guard exists to delegate these graphs to networkx; that must still happen.

    A sweep that stopped detecting -inf would not fail the store test -- it would silently
    run fnx's dijkstra on a graph networkx rejects, and return a -inf-cost path. So the
    end-to-end behaviour is compared, exceptions included.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = _build(module, cls_name, injected)
        try:
            result = module.single_source_dijkstra_path_length(graph, "n0", weight="weight")
            outcomes[name] = ("ok", sorted(dict(result).items())[:8])
        except Exception as exc:  # noqa: BLE001 - the exception IS the contract
            outcomes[name] = (type(exc).__name__, str(exc)[:80])
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name} with a {label} weight: networkx gave {outcomes['nx']}, "
        f"fnx gave {outcomes['fnx']}."
    )


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
def test_missing_weight_key_still_defaults_to_one(cls_name):
    """`default=1` must reproduce `attrs.get(weight, 1)` for edges with no weight.

    The negative case for the spelling swap: an edge carrying no `weight` key at all. Read
    through `data=True` it produced the default from `.get`; read through `data=weight` it
    has to come from `default=1`, and getting that wrong would make an unweighted edge look
    like `None` to the comparison.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = getattr(module, cls_name)()
        graph.add_edge("a", "b", weight=1.0)
        graph.add_edge("b", "c")  # no weight key
        graph.add_edge("c", "d", weight=-math.inf)
        outcomes[name] = sorted(
            (u, v, d.get("weight", 1)) for u, v, d in graph.edges(data=True)
        )
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: default handling diverged. networkx {outcomes['nx']}, "
        f"fnx {outcomes['fnx']}"
    )

    guard = fnx.__dict__["_has_negative_edge_weight_for_dijkstra"]
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b", weight=1.0)
    graph.add_edge("b", "c")
    assert guard(graph, "weight") is False, (
        f"{cls_name}: an edge with no weight key must count as the default 1, not as a "
        f"missing value that trips the negative-weight check"
    )
