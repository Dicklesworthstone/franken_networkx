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
