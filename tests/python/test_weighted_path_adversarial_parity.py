"""Adversarial weighted shortest-path differential parity vs networkx.

br-r37-c1-wpathfuzz: weighted shortest paths are a documented bug-density area
(SPFA processing-order tie-breaks, dijkstra finalize/dict order, negative-weight
Bellman-Ford, negative-cycle detection). This deterministically fuzzes random
weighted graphs and asserts EXACT parity vs networkx for:

  * dijkstra_path_length (non-negative)
  * dijkstra_path VALUE (equal-length tie-break selection)
  * single_source_bellman_ford_path_length with NEGATIVE weights (directed)
  * negative_edge_cycle detection (directed)

fnx is byte-exact here (validated 0 mismatches over 22k+ checks at authoring);
this locks that against regressions. Uses exact ``==`` (not tolerance) because
the paths/lengths are integer-weighted and the selections are deterministic.
"""

from fractions import Fraction
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(seed, directed, allow_neg):
    rng = random.Random(seed)
    fcls = fnx.DiGraph if directed else fnx.Graph
    ncls = nx.DiGraph if directed else nx.Graph
    Gf, Gn = fcls(), ncls()
    n = rng.randint(4, 8)
    for _ in range(rng.randint(n, n * 3)):
        a, b = rng.randrange(n), rng.randrange(n)
        if a == b:
            continue
        w = rng.randint(-3, 6) if allow_neg else rng.randint(1, 6)
        Gf.add_edge(a, b, weight=w)
        Gn.add_edge(a, b, weight=w)
    return Gf, Gn


def _both(ff, nf):
    """Return (fnx_result, nx_result), mapping exceptions to a comparable tag."""
    try:
        rf = ff()
    except Exception as e:  # noqa: BLE001 - parity includes error type
        rf = ("EXC", type(e).__name__)
    try:
        rn = nf()
    except Exception as e:  # noqa: BLE001
        rn = ("EXC", type(e).__name__)
    return rf, rn


@pytest.mark.parametrize("directed", [False, True])
def test_dijkstra_path_and_length_parity(directed):
    mismatches = []
    for seed in range(300):
        Gf, Gn = _build(seed, directed, allow_neg=False)
        nodes = sorted(set(Gn.nodes()) & set(Gf.nodes()))
        for s in nodes[:3]:
            for t in nodes[:3]:
                if s == t:
                    continue
                rf, rn = _both(
                    lambda s=s, t=t: fnx.dijkstra_path_length(Gf, s, t, weight="weight"),
                    lambda s=s, t=t: nx.dijkstra_path_length(Gn, s, t, weight="weight"),
                )
                if rf != rn:
                    mismatches.append(("len", seed, s, t, rf, rn))
                rf, rn = _both(
                    lambda s=s, t=t: fnx.dijkstra_path(Gf, s, t, weight="weight"),
                    lambda s=s, t=t: nx.dijkstra_path(Gn, s, t, weight="weight"),
                )
                if rf != rn:
                    mismatches.append(("path", seed, s, t, rf, rn))
    assert not mismatches, (
        f"dijkstra divergence (directed={directed}): {len(mismatches)}; "
        f"first={mismatches[0]}"
    )


def test_bellman_ford_negative_and_cycle_parity():
    mismatches = []
    for seed in range(400):
        Gf, Gn = _build(seed, directed=True, allow_neg=True)
        nodes = sorted(set(Gn.nodes()) & set(Gf.nodes()))
        for s in nodes[:2]:
            rf, rn = _both(
                lambda s=s: dict(
                    fnx.single_source_bellman_ford_path_length(Gf, s, weight="weight")
                ),
                lambda s=s: dict(
                    nx.single_source_bellman_ford_path_length(Gn, s, weight="weight")
                ),
            )
            if rf != rn:
                mismatches.append(("bf_len", seed, s, rf, rn))
        rf, rn = _both(
            lambda: fnx.negative_edge_cycle(Gf, weight="weight"),
            lambda: nx.negative_edge_cycle(Gn, weight="weight"),
        )
        if rf != rn:
            mismatches.append(("negcycle", seed, rf, rn))
    assert not mismatches, f"bellman-ford divergence: {len(mismatches)}; first={mismatches[0]}"


def _exact_outcome(call):
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001 - exact public error parity
        return ("EXC", type(exc).__name__, str(exc))
    if isinstance(result, tuple) and len(result) == 2:
        length, path = result
        return ("OK", type(length).__name__, length, path)
    return ("OK", result)


def _build_weighted_multigraph(seed):
    rng = random.Random(seed)
    nodes = [f"node-{idx}" for idx in range(rng.randint(4, 10))]
    rng.shuffle(nodes)
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    fnx_graph.add_nodes_from(nodes)
    nx_graph.add_nodes_from(nodes)
    weights = (0, 0.5, 1, 1, 1.5, 2, 2, 3)
    for _ in range(rng.randint(len(nodes), len(nodes) * 4)):
        left = rng.choice(nodes)
        right = rng.choice(nodes)
        for _ in range(rng.randint(1, 3)):
            attrs = {} if rng.random() < 0.2 else {"weight": rng.choice(weights)}
            fnx_graph.add_edge(left, right, **attrs)
            nx_graph.add_edge(left, right, **attrs)
    return fnx_graph, nx_graph, nodes


def test_multigraph_bidirectional_and_shortest_path_randomized_exact_parity():
    mismatches = []
    for seed in range(96):
        fnx_graph, nx_graph, nodes = _build_weighted_multigraph(seed)
        pairs = (
            (nodes[0], nodes[-1]),
            (nodes[-1], nodes[0]),
            (nodes[1], nodes[-2]),
        )
        for source, target in pairs:
            for name in ("bidirectional_dijkstra", "shortest_path"):
                fnx_result = _exact_outcome(
                    lambda name=name, source=source, target=target: getattr(fnx, name)(
                        fnx_graph, source, target, weight="weight"
                    )
                )
                nx_result = _exact_outcome(
                    lambda name=name, source=source, target=target: getattr(nx, name)(
                        nx_graph, source, target, weight="weight"
                    )
                )
                if fnx_result != nx_result:
                    mismatches.append(
                        (seed, name, source, target, fnx_result, nx_result)
                    )
    assert not mismatches, (
        f"multigraph weighted path divergence: {len(mismatches)}; "
        f"first={mismatches[0]}"
    )


def test_multigraph_bidirectional_backward_row_tie_parity():
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    for left, right, weight in (
        ("s", "a", 1),
        ("t", "b", 1),
        ("s", "b", 1),
        ("t", "a", 1),
        ("s", "a", 9),
        ("t", "b", 9),
    ):
        fnx_graph.add_edge(left, right, weight=weight)
        nx_graph.add_edge(left, right, weight=weight)

    assert fnx.bidirectional_dijkstra(
        fnx_graph, "s", "t", weight="weight"
    ) == nx.bidirectional_dijkstra(nx_graph, "s", "t", weight="weight") == (
        2,
        ["s", "b", "t"],
    )
    assert fnx.shortest_path(
        fnx_graph, "s", "t", weight="weight"
    ) == nx.shortest_path(nx_graph, "s", "t", weight="weight") == ["s", "b", "t"]
    assert fnx.bidirectional_dijkstra(
        fnx_graph, "t", "s", weight="weight"
    ) == nx.bidirectional_dijkstra(nx_graph, "t", "s", weight="weight") == (
        2,
        ["t", "a", "s"],
    )
    assert fnx.dijkstra_path(fnx_graph, "s", "t", weight="weight") == ["s", "a", "t"]


def test_multigraph_bidirectional_node_indices_follow_remove_readd():
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    for graph in (fnx_graph, nx_graph):
        graph.add_nodes_from(("prefix", "s", "a", "b", "t"))
        graph.add_edge("s", "a", weight=1)
        graph.add_edge("a", "t", weight=1)
        graph.add_edge("s", "b", weight=1)
        graph.add_edge("b", "t", weight=1)

    def assert_exact_parity():
        for source, target in (("s", "t"), ("t", "s")):
            for name in ("bidirectional_dijkstra", "shortest_path"):
                assert _exact_outcome(
                    lambda name=name, source=source, target=target: getattr(fnx, name)(
                        fnx_graph, source, target, weight="weight"
                    )
                ) == _exact_outcome(
                    lambda name=name, source=source, target=target: getattr(nx, name)(
                        nx_graph, source, target, weight="weight"
                    )
                )

    assert_exact_parity()
    for graph in (fnx_graph, nx_graph):
        graph.remove_node("prefix")
    assert_exact_parity()

    for graph in (fnx_graph, nx_graph):
        graph.remove_node("a")
    assert_exact_parity()

    for graph in (fnx_graph, nx_graph):
        graph.add_edge("s", "a", weight=1)
        graph.add_edge("a", "t", weight=1)
    assert_exact_parity()

    for graph in (fnx_graph, nx_graph):
        graph.remove_node("b")
    assert_exact_parity()

    for graph in (fnx_graph, nx_graph):
        graph.remove_node("a")
    assert_exact_parity()


@pytest.mark.parametrize(
    ("parallel_attrs", "expected_length", "expected_type"),
    (
        (({"weight": 1.0}, {}), 3.0, float),
        (({}, {"weight": 1.0}), 3, int),
        (({"weight": 7}, {}), 3, int),
    ),
)
def test_multigraph_parallel_default_weight_and_length_type_parity(
    parallel_attrs, expected_length, expected_type
):
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    for attrs in parallel_attrs:
        fnx_graph.add_edge("s", "a", **attrs)
        nx_graph.add_edge("s", "a", **attrs)
    fnx_graph.add_edge("a", "t", weight=2)
    nx_graph.add_edge("a", "t", weight=2)

    fnx_result = fnx.bidirectional_dijkstra(fnx_graph, "s", "t", weight="weight")
    nx_result = nx.bidirectional_dijkstra(nx_graph, "s", "t", weight="weight")
    assert fnx_result == nx_result == (expected_length, ["s", "a", "t"])
    assert type(fnx_result[0]) is type(nx_result[0]) is expected_type


@pytest.mark.parametrize("weight", (-1, float("inf"), "not-numeric"))
def test_multigraph_store_only_hostile_weight_delegates_exactly(weight):
    fnx_base = fnx.Graph()
    fnx_base.add_edge("s", "t", weight=weight)
    fnx_graph = fnx.MultiGraph(fnx_base)
    nx_graph = nx.MultiGraph()
    nx_graph.add_edge("s", "t", weight=weight)

    assert _exact_outcome(
        lambda: fnx.bidirectional_dijkstra(fnx_graph, "s", "t", weight="weight")
    ) == _exact_outcome(
        lambda: nx.bidirectional_dijkstra(nx_graph, "s", "t", weight="weight")
    )


def test_multigraph_lossy_weight_domains_and_graph_views_delegate_exactly():
    from fractions import Fraction

    for weight in (float("nan"), 2**53 + 1, Fraction(1, 3)):
        fnx_graph = fnx.MultiGraph()
        nx_graph = nx.MultiGraph()
        fnx_graph.add_edge("s", "t", weight=weight)
        nx_graph.add_edge("s", "t", weight=weight)
        fnx_result = fnx.bidirectional_dijkstra(
            fnx_graph, "s", "t", weight="weight"
        )
        nx_result = nx.bidirectional_dijkstra(nx_graph, "s", "t", weight="weight")
        if isinstance(weight, float) and weight != weight:
            assert fnx_result[1] == nx_result[1]
            assert fnx_result[0] != fnx_result[0]
            assert nx_result[0] != nx_result[0]
        else:
            assert fnx_result == nx_result
            assert type(fnx_result[0]) is type(nx_result[0])

    fnx_graph = fnx.MultiGraph()
    fnx_graph.add_edge("s", "a", weight=1)
    fnx_graph.add_edge("a", "t", weight=1)
    view = fnx_graph.subgraph(("s", "a", "t"))
    assert fnx.bidirectional_dijkstra(view, "s", "t", weight="weight") == (
        2,
        ["s", "a", "t"],
    )

    foreign = nx.MultiGraph()
    foreign.add_edge("s", "t", weight=2)
    assert fnx.bidirectional_dijkstra(foreign, "s", "t", weight="weight") == (
        2,
        ["s", "t"],
    )


def test_multigraph_attr_key_collision_and_error_boundaries_delegate_exactly():
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    fnx_graph.add_edge("s", "t", **{"1": 2})
    nx_graph.add_edge("s", "t", **{"1": 2})
    fnx_graph["s"]["t"][0][1] = 5
    nx_graph["s"]["t"][0][1] = 5
    assert fnx.bidirectional_dijkstra(fnx_graph, "s", "t", weight="1") == (
        2,
        ["s", "t"],
    )

    fnx_graph.add_node("isolated")
    nx_graph.add_node("isolated")
    for source, target in (
        ("s", "s"),
        ("missing", "s"),
        ("s", "missing"),
        ("s", "isolated"),
    ):
        assert _exact_outcome(
            lambda source=source, target=target: fnx.bidirectional_dijkstra(
                fnx_graph, source, target, weight="1"
            )
        ) == _exact_outcome(
            lambda source=source, target=target: nx.bidirectional_dijkstra(
                nx_graph, source, target, weight="1"
            )
        )


def test_multigraph_mixed_node_display_objects_delegate_exactly():
    fnx_graph = fnx.MultiGraph()
    nx_graph = nx.MultiGraph()
    for left, right in (("s", 1.0), (1, "t")):
        fnx_graph.add_edge(left, right, weight=1)
        nx_graph.add_edge(left, right, weight=1)

    for source, target in (("s", "t"), ("t", "s")):
        fnx_length, fnx_path = fnx.bidirectional_dijkstra(
            fnx_graph, source, target, weight="weight"
        )
        nx_length, nx_path = nx.bidirectional_dijkstra(
            nx_graph, source, target, weight="weight"
        )
        assert (type(fnx_length), fnx_length) == (type(nx_length), nx_length)
        assert [(type(node), node) for node in fnx_path] == [
            (type(node), node) for node in nx_path
        ]
        fnx_shortest = fnx.shortest_path(
            fnx_graph, source, target, weight="weight"
        )
        nx_shortest = nx.shortest_path(nx_graph, source, target, weight="weight")
        assert [(type(node), node) for node in fnx_shortest] == [
            (type(node), node) for node in nx_shortest
        ]

    endpoint_fnx = fnx.MultiGraph()
    endpoint_nx = nx.MultiGraph()
    endpoint_fnx.add_edge(1, "t", weight=1)
    endpoint_nx.add_edge(1, "t", weight=1)
    for source in (1.0, True):
        fnx_path = fnx.bidirectional_dijkstra(
            endpoint_fnx, source, "t", weight="weight"
        )[1]
        nx_path = nx.bidirectional_dijkstra(
            endpoint_nx, source, "t", weight="weight"
        )[1]
        assert [(type(node), node) for node in fnx_path] == [
            (type(node), node) for node in nx_path
        ]

    class StringNode(str):
        pass

    source = StringNode("s")
    string_fnx = fnx.MultiGraph()
    string_nx = nx.MultiGraph()
    string_fnx.add_edge("s", "t", weight=1)
    string_nx.add_edge("s", "t", weight=1)
    fnx_path = fnx.bidirectional_dijkstra(
        string_fnx, source, "t", weight="weight"
    )[1]
    nx_path = nx.bidirectional_dijkstra(
        string_nx, source, "t", weight="weight"
    )[1]
    assert [(type(node), node) for node in fnx_path] == [
        (type(node), node) for node in nx_path
    ]


def test_multigraph_exact_string_domain_gate_is_bidirectional_only(monkeypatch):
    graph = fnx.MultiGraph()
    graph.add_edge(1, 2, weight=1)

    assert fnx._should_delegate_dijkstra_to_networkx(graph, "weight") is False
    assert (
        fnx._should_delegate_dijkstra_to_networkx(
            graph, "weight", _require_exact_string_nodes=True
        )
        is True
    )

    monkeypatch.setattr(fnx, "_native_check_dijkstra_weights_fast", None)
    assert fnx._should_delegate_dijkstra_to_networkx(graph, "weight") is False
    assert (
        fnx._should_delegate_dijkstra_to_networkx(
            graph, "weight", _require_exact_string_nodes=True
        )
        is True
    )


def test_shortest_path_exact_multigraph_runs_one_authoritative_weight_scan(monkeypatch):
    graph = fnx.MultiGraph()
    graph.add_edge("s", "m", weight=1)
    graph.add_edge("m", "t", weight=2)
    original = fnx._should_delegate_dijkstra_to_networkx
    calls = []

    def counted(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(fnx, "_should_delegate_dijkstra_to_networkx", counted)

    assert fnx.shortest_path(graph, "s", "t", weight="weight") == ["s", "m", "t"]
    assert len(calls) == 1
    assert calls[0][1] == {"_require_exact_string_nodes": True}


# ---------------------------------------------------------------------------
# br-r37-c1-svsam: a search that checks only the rows it expands
# ---------------------------------------------------------------------------
# On a weight-scan cache miss - a fresh graph, or any write - these searches no
# longer scan all E weights before running natively. The native search checks
# the weights on the rows it expanded, and a weight the gate would route on any
# of them re-runs the call through the whole-graph gate. So a hostile weight
# INSIDE the searched region must still give networkx's exact outcome (value,
# type, or exception), and the same weight in a component the search never
# reaches must leave the native answer equal to networkx's.

_HOSTILE = {
    "negative": -3,
    "nan": float("nan"),
    "inf": float("inf"),
    "string": "heavy",
    "fraction": Fraction(1, 3),
    "huge_int": 2**60,
}

_ROW_CHECKED = {
    "dijkstra_path": lambda m, g: m.dijkstra_path(g, 0, 5),
    "dijkstra_path_length": lambda m, g: m.dijkstra_path_length(g, 0, 5),
    "single_source_dijkstra_target": lambda m, g: m.single_source_dijkstra(g, 0, target=5),
    "single_source_dijkstra_cutoff": lambda m, g: m.single_source_dijkstra(g, 0, cutoff=6),
    "ss_dijkstra_path_length_cutoff": lambda m, g: m.single_source_dijkstra_path_length(
        g, 0, cutoff=6
    ),
    "bidirectional_dijkstra": lambda m, g: m.bidirectional_dijkstra(g, 0, 5),
    "astar_path": lambda m, g: m.astar_path(g, 0, 5),
    "bellman_ford_path": lambda m, g: m.bellman_ford_path(g, 0, 5),
    "bellman_ford_path_length": lambda m, g: m.bellman_ford_path_length(g, 0, 5),
    "dijkstra_path_absent_target": lambda m, g: m.dijkstra_path(g, 0, "absent"),
    "bellman_ford_path_absent_target": lambda m, g: m.bellman_ford_path(g, 0, "absent"),
    "bellman_ford_path_length_absent_target": lambda m, g: m.bellman_ford_path_length(
        g, 0, "absent"
    ),
    "shortest_path_weighted": lambda m, g: m.shortest_path(g, 0, 5, weight="weight"),
    "shortest_path_length_weighted": lambda m, g: m.shortest_path_length(g, 0, 5, weight="weight"),
    "multi_source_dijkstra_cutoff": lambda m, g: m.multi_source_dijkstra(g, [0, 3], cutoff=6),
    "multi_source_dijkstra_target": lambda m, g: m.multi_source_dijkstra(g, [0, 3], target=5),
    "multi_source_dijkstra_absent_target": lambda m, g: m.multi_source_dijkstra(
        g, [0], target="absent"
    ),
    "multi_source_dijkstra_path_length": lambda m, g: m.multi_source_dijkstra_path_length(
        g, [0, 3]
    ),
    "single_source_bellman_ford_path_length": lambda m, g: (
        m.single_source_bellman_ford_path_length(g, 0)
    ),
}


def _hostile_graph(lib, directed, where, value, written):
    """A weighted 10-node path the searches cover, beside a 50-node ring they
    never reach. The hostile weight sits on (1, 2) or on a ring edge, either
    from construction or written into the edge dict after a first query."""
    graph = (lib.DiGraph if directed else lib.Graph)()
    edge = (1, 2) if where == "reached" else (110, 111)
    edges = [(i, i + 1, 1 + i % 3) for i in range(9)] + [(0, 2, 2), (2, 5, 1)]
    edges += [(100 + i, 100 + (i + 1) % 50, 1) for i in range(50)]
    for u, v, w in edges:
        graph.add_edge(u, v, weight=value if (u, v) == edge and not written else w)
    if written:
        _exact_outcome(lambda: lib.dijkstra_path(graph, 0, 5))
        graph[edge[0]][edge[1]]["weight"] = value
    return graph


@pytest.mark.parametrize("written", [False, True])
@pytest.mark.parametrize("where", ["reached", "unreached"])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("hostile", sorted(_HOSTILE))
@pytest.mark.parametrize("label", sorted(_ROW_CHECKED))
def test_row_checked_search_meets_networkx_on_hostile_weights(
    label, hostile, directed, where, written
):
    if label == "astar_path" and hostile == "negative" and not directed and where == "reached":
        pytest.skip("an undirected negative edge is a negative cycle; networkx's A* never ends")
    call = _ROW_CHECKED[label]
    outcomes = {}
    for lib in (fnx, nx):
        graph = _hostile_graph(lib, directed, where, _HOSTILE[hostile], written)
        outcomes[lib.__name__] = repr(_exact_outcome(lambda: call(lib, graph)))
    assert outcomes["franken_networkx"] == outcomes["networkx"]


def test_row_checked_search_past_its_budget_reruns_on_the_cached_scan():
    """A search reading more than an eighth of the edges is not checked row by
    row: it re-runs on the whole-graph scan, which is then cached."""
    graphs = {lib: lib.Graph() for lib in (fnx, nx)}
    for graph in graphs.values():
        graph.add_edges_from((i, (i + 1) % 3000, {"weight": 1 + i % 4}) for i in range(3000))
    assert "_fnx_weight_scan_cache" not in vars(graphs[fnx])
    expected = list(nx.single_source_dijkstra_path_length(graphs[nx], 0).items())
    assert list(fnx.single_source_dijkstra_path_length(graphs[fnx], 0).items()) == expected
    assert "_fnx_weight_scan_cache" in vars(graphs[fnx])


def test_row_checks_per_revision_are_bounded_then_the_scan_is_cached():
    """Repeated queries on an unchanged graph must not re-check rows forever:
    after _ROW_CHECKS_PER_REVISION of them the whole scan runs and is cached,
    and a write starts a fresh allowance."""
    graph = fnx.Graph()
    graph.add_weighted_edges_from((i, i + 1, 1 + i % 3) for i in range(9))
    for _ in range(fnx._ROW_CHECKS_PER_REVISION):
        assert fnx.dijkstra_path(graph, 0, 5) == [0, 1, 2, 3, 4, 5]
        assert "_fnx_weight_scan_cache" not in vars(graph)
    assert fnx.dijkstra_path(graph, 0, 5) == [0, 1, 2, 3, 4, 5]
    assert "_fnx_weight_scan_cache" in vars(graph)
    graph.add_edge(20, 21)
    assert fnx.dijkstra_path(graph, 0, 5) == [0, 1, 2, 3, 4, 5]
    assert vars(graph)["_fnx_weight_row_checks"][1] == 1


# ---------------------------------------------------------------------------
# br-r37-c1-0g2tj: whole-graph emitters on long-path shapes
# ---------------------------------------------------------------------------
# On a ring or a grid every path is long and shares its prefix with its
# predecessor's, which is where the emitters lost to networkx (0.58-0.72x on a
# 32k ring). single_source_dijkstra builds each path as its predecessor's list
# plus the node, and the length call emits from index space; both must keep
# networkx's dict order, int / float types, and independent path lists.


def _long_path_shapes(lib):
    ring = lib.Graph()
    ring.add_weighted_edges_from((i, (i + 1) % 300, 1 + i % 3) for i in range(300))
    ring_float = lib.Graph()
    ring_float.add_weighted_edges_from((i, (i + 1) % 200, 0.5 + i % 2) for i in range(200))
    grid = lib.Graph()
    for r in range(15):
        for c in range(15):
            if c < 14:
                grid.add_edge((r, c), (r, c + 1), weight=1 + (r + c) % 3)
            if r < 14:
                grid.add_edge((r, c), (r + 1, c), weight=1 + (r * c) % 2)
    # int distances up to 2**51 - native (the gate routes a graph whose int
    # weights sum past 2**53 to networkx) and past any 32-bit shortcut.
    chain = lib.DiGraph()
    chain.add_weighted_edges_from((i, i + 1, 2**49) for i in range(4))
    chain.add_edge(0, 4, weight=2**51 + 1)
    return {"ring": (ring, 0), "ring_float": (ring_float, 7), "grid": (grid, (0, 0)), "big_ints": (chain, 0)}


def _typed(mapping):
    return [(k, type(v).__name__, v) for k, v in mapping.items()]


@pytest.mark.parametrize("shape", ["ring", "ring_float", "grid", "big_ints"])
@pytest.mark.parametrize("cutoff", [None, 5])
def test_long_path_single_source_dijkstra_matches_networkx(shape, cutoff):
    fg, fs = _long_path_shapes(fnx)[shape]
    ng, ns = _long_path_shapes(nx)[shape]
    fd, fp = fnx.single_source_dijkstra(fg, fs, cutoff=cutoff)
    nd, np_ = nx.single_source_dijkstra(ng, ns, cutoff=cutoff)
    assert _typed(fd) == _typed(nd)
    assert list(fp.items()) == list(np_.items())
    assert _typed(fnx.single_source_dijkstra_path_length(fg, fs, cutoff=cutoff)) == _typed(
        nx.single_source_dijkstra_path_length(ng, ns, cutoff=cutoff)
    )


def test_single_source_dijkstra_paths_are_independent_lists():
    graph = fnx.Graph()
    graph.add_weighted_edges_from((i, i + 1, 1) for i in range(6))
    _, paths = fnx.single_source_dijkstra(graph, 0)
    assert len({id(path) for path in paths.values()}) == len(paths)
    paths[3].append("x")
    assert paths[4] == [0, 1, 2, 3, 4]
    assert paths[2] == [0, 1, 2]


# ---------------------------------------------------------------------------
# br-r37-c1-m0cj7: multi_source_dijkstra in index space
# ---------------------------------------------------------------------------
# Every source starts at distance 0 in iteration order and displays as the
# object PASSED; cutoff and target act inside the search; distances keep
# networkx's int / float types (float weights used to be sent to networkx);
# a path to a given target ends in the target object as passed.


def _two_components(lib, directed, floats=False):
    graph = (lib.DiGraph if directed else lib.Graph)()
    scale = 0.5 if floats else 1
    graph.add_weighted_edges_from((i, i + 1, (1 + i % 3) * scale) for i in range(9))
    graph.add_weighted_edges_from([(0, 2, 2 * scale), (2, 5, 1), (7, 3, 0)])
    graph.add_weighted_edges_from((20 + i, 20 + (i + 1) % 6, 1) for i in range(6))
    graph.add_edge(3, 4, weight=0)  # a zero-weight edge between two sources
    return graph


_MULTI_SOURCE_CALLS = {
    "set": lambda m, g: m.multi_source_dijkstra(g, {0, 3}),
    "list_repeats": lambda m, g: m.multi_source_dijkstra(g, [3, 0, 3, 4]),
    "two_components": lambda m, g: m.multi_source_dijkstra(g, [21, 0]),
    "cutoff_int": lambda m, g: m.multi_source_dijkstra(g, [0, 3], cutoff=3),
    "cutoff_float": lambda m, g: m.multi_source_dijkstra(g, [0, 3], cutoff=2.5),
    "cutoff_negative": lambda m, g: m.multi_source_dijkstra(g, [0, 3], cutoff=-1),
    "cutoff_nan": lambda m, g: m.multi_source_dijkstra(g, [0], cutoff=float("nan")),
    "cutoff_inf": lambda m, g: m.multi_source_dijkstra(g, [0], cutoff=float("inf")),
    "cutoff_huge_int": lambda m, g: m.multi_source_dijkstra(g, [0], cutoff=2**60),
    "cutoff_fraction": lambda m, g: m.multi_source_dijkstra(g, [0], cutoff=Fraction(5, 2)),
    "target": lambda m, g: m.multi_source_dijkstra(g, [0, 21], target=8),
    "target_as_float": lambda m, g: m.multi_source_dijkstra(g, [0], target=8.0),
    "target_is_source": lambda m, g: m.multi_source_dijkstra(g, [0, 3], target=3.0),
    "target_unreachable": lambda m, g: m.multi_source_dijkstra(g, [0], target=21),
    "target_absent": lambda m, g: m.multi_source_dijkstra(g, [0], target="absent"),
    "source_absent": lambda m, g: m.multi_source_dijkstra(g, [0, "absent"]),
    "length": lambda m, g: m.multi_source_dijkstra_path_length(g, [3, 0]),
    "length_cutoff": lambda m, g: m.multi_source_dijkstra_path_length(g, {0, 21}, cutoff=2),
    "path": lambda m, g: m.multi_source_dijkstra_path(g, [0, 3], cutoff=4),
}


def _exact(value):
    """Order, value, type and object identity class of a result."""
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], dict):
        return (_exact(value[0]), _exact(value[1]))
    if isinstance(value, dict):
        return [(repr(k), type(k).__name__, _exact(v)) for k, v in value.items()]
    if isinstance(value, list):
        return [(repr(x), type(x).__name__) for x in value]
    if isinstance(value, tuple):
        return tuple(_exact(x) for x in value)
    return (repr(value), type(value).__name__)


@pytest.mark.parametrize("floats", [False, True])
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("label", sorted(_MULTI_SOURCE_CALLS))
def test_multi_source_dijkstra_matches_networkx_exactly(label, directed, floats):
    outcomes = {}
    for lib in (fnx, nx):
        graph = _two_components(lib, directed, floats)
        try:
            outcomes[lib.__name__] = _exact(_MULTI_SOURCE_CALLS[label](lib, graph))
        except Exception as exc:  # noqa: BLE001 - exact public error parity
            outcomes[lib.__name__] = ("EXC", type(exc).__name__, str(exc))
    assert outcomes["franken_networkx"] == outcomes["networkx"]


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_multi_source_dijkstra_keeps_networkx_results(cls):
    outcomes = {}
    for lib in (fnx, nx):
        graph = getattr(lib, cls)()
        graph.add_weighted_edges_from([(0, 1, 3), (0, 1, 1), (1, 2, 2), (2, 3, 1), (5, 6, 1)])
        outcomes[lib.__name__] = (
            _exact(lib.multi_source_dijkstra(graph, [0, 5])),
            _exact(lib.multi_source_dijkstra(graph, [0], cutoff=2)),
            _exact(lib.multi_source_dijkstra_path_length(graph, [0, 5])),
        )
    assert outcomes["franken_networkx"] == outcomes["networkx"]


# ---------------------------------------------------------------------------
# br-r37-c1-0g2tj: single_source_bellman_ford_path_length types in the kernel
# ---------------------------------------------------------------------------
# networkx's distance is dist[u] + w of the relaxation that SET it, so a node
# first reached through a float edge and then improved along an int path is an
# int (and the reverse a float). The SPFA core now carries that type instead of
# a Python pass re-deriving it from a second, paths-carrying traversal.

# Float distances are kept INTEGRAL (2.0, 3.0): a fractional one prints as a
# float whatever the kernel's type flag says, so it could not catch a kernel
# that typed every distance int.
_BF_TYPE_SHAPES = {
    "float_then_int": [(0, 1, 1.5), (0, 2, 1), (2, 1, 0), (1, 3, 2)],
    "int_then_float": [(0, 1, 3), (0, 2, 1), (2, 1, 1.0), (1, 3, 2)],
    "negative_ints": [(0, 1, 4), (1, 2, -2), (0, 2, 3), (2, 3, 1)],
    "bool_missing": [(0, 1, True), (1, 2, None), (2, 3, 2.0), (0, 3, 9)],
    "all_float": [(0, 1, 1.0), (1, 2, 2.0), (0, 2, 4.0)],
}


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("shape", sorted(_BF_TYPE_SHAPES))
def test_single_source_bellman_ford_path_length_types_match_networkx(shape, directed):
    if shape == "negative_ints" and not directed:
        pytest.skip("an undirected negative edge is a negative cycle")
    outcomes = {}
    for lib in (fnx, nx):
        graph = (lib.DiGraph if directed else lib.Graph)()
        for u, v, w in _BF_TYPE_SHAPES[shape]:
            if w is None:
                graph.add_edge(u, v)
            else:
                graph.add_edge(u, v, weight=w)
        outcomes[lib.__name__] = _exact(lib.single_source_bellman_ford_path_length(graph, 0))
    assert outcomes["franken_networkx"] == outcomes["networkx"]


def test_single_source_bellman_ford_path_length_fixtures_decide_the_type():
    """The two relaxation-order fixtures must type differently in networkx
    itself, or the parity test above could pass on graph-wide typing."""
    types = []
    for shape in ("float_then_int", "int_then_float"):
        graph = nx.DiGraph()
        graph.add_weighted_edges_from(_BF_TYPE_SHAPES[shape])
        types.append(type(nx.single_source_bellman_ford_path_length(graph, 0)[1]))
    assert types == [int, float]


@pytest.mark.parametrize("shape", ["ring", "ring_float", "grid", "big_ints"])
def test_long_path_single_source_bellman_ford_path_length_matches_networkx(shape):
    fg, fs = _long_path_shapes(fnx)[shape]
    ng, ns = _long_path_shapes(nx)[shape]
    assert _typed(fnx.single_source_bellman_ford_path_length(fg, fs)) == _typed(
        nx.single_source_bellman_ford_path_length(ng, ns)
    )


@pytest.mark.parametrize("directed", [False, True])
def test_single_source_bellman_ford_path_length_negative_cycle(directed):
    outcomes = {}
    for lib in (fnx, nx):
        graph = (lib.DiGraph if directed else lib.Graph)()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, -3), (2, 0, 1), (2, 3, 1)])
        try:
            outcomes[lib.__name__] = lib.single_source_bellman_ford_path_length(graph, 0)
        except Exception as exc:  # noqa: BLE001 - exact public error parity
            outcomes[lib.__name__] = (type(exc).__name__, str(exc))
    assert outcomes["franken_networkx"] == outcomes["networkx"]
