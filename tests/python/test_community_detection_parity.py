"""Community-detection parity + modularity invariants.

Modularity has a closed-form definition (so a given partition yields a fixed
value, matchable against networkx), partition_quality and is_partition are
deterministic, and greedy_modularity_communities is deterministic. This checks
parity plus modularity's structural invariants (a single all-nodes community
has modularity 0; modularity lies in [-1, 1]).

No mocks: real fnx and real networkx on random graphs + partitions.
"""

from __future__ import annotations

import hashlib
import json
import random

import pytest
import networkx as nx
import franken_networkx as fnx
import franken_networkx.algorithms.community as fcom
import networkx.algorithms.community as ncom


def _graph_and_partition(seed):
    r = random.Random(seed)
    n = r.randint(6, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    k = r.randint(2, 3)
    parts = [set() for _ in range(k)]
    for node in range(n):
        parts[r.randrange(k)].add(node)
    parts = [p for p in parts if p]
    return fg, ng, n, parts


@pytest.mark.parametrize("seed", range(40))
def test_modularity_and_partition_quality_parity(seed):
    fg, ng, n, parts = _graph_and_partition(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("no edges")
    assert round(fcom.modularity(fg, parts), 9) == round(ncom.modularity(ng, parts), 9)
    assert round(fcom.modularity(fg, parts, resolution=2.0), 9) == round(
        ncom.modularity(ng, parts, resolution=2.0), 9
    )
    fq = tuple(round(x, 9) for x in fcom.partition_quality(fg, parts))
    nq = tuple(round(x, 9) for x in ncom.partition_quality(ng, parts))
    assert fq == nq
    assert fcom.is_partition(fg, parts) == ncom.is_partition(ng, parts)


@pytest.mark.parametrize("seed", range(40))
def test_greedy_modularity_communities_parity(seed):
    fg, ng, n, parts = _graph_and_partition(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("no edges")
    fc = sorted(sorted(c) for c in fcom.greedy_modularity_communities(fg))
    nc = sorted(sorted(c) for c in ncom.greedy_modularity_communities(ng))
    assert fc == nc


def test_greedy_modularity_communities_class1_hunt_regression():
    """Pin the exact ordered graph that invalidated the native CNM route."""
    rng = random.Random(13)
    nodes = [str(i) for i in range(220)]
    seen = set()
    edges = []
    while len(edges) < 900:
        u, v = rng.randrange(220), rng.randrange(220)
        if u == v:
            continue
        key = (min(u, v), max(u, v))
        if key in seen:
            continue
        seen.add(key)
        edges.append((str(u), str(v)))

    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)

    fc = sorted(sorted(c) for c in fcom.greedy_modularity_communities(fg))
    nc = sorted(sorted(c) for c in ncom.greedy_modularity_communities(ng))
    assert fc == nc
    assert hashlib.sha256(
        json.dumps(fc, separators=(",", ":")).encode()
    ).hexdigest() == "ab5539dbda21bdcf824b9360f49cecec829bf89d6f8d5170b214f97a051432b4"


@pytest.mark.parametrize("seed", range(20))
def test_modularity_invariants(seed):
    fg, ng, n, parts = _graph_and_partition(seed)
    if fg.number_of_edges() == 0:
        pytest.skip("no edges")
    # The single all-nodes community has modularity exactly 0.
    single = [set(range(n))]
    assert abs(fcom.modularity(fg, single)) < 1e-9
    # Modularity of any valid partition is bounded in [-1, 1].
    q = fcom.modularity(fg, parts)
    assert -1.0 - 1e-9 <= q <= 1.0 + 1e-9


# br-r37-c1-epic-native-algorithms-1g0lj.3: greedy_modularity_communities runs
# networkx's CNM loop natively. The contract is networkx's exact result: the same
# communities in the same order, each a frozenset built the same way (so even
# its iteration order matches).


def _cnm_graph(lib, seed):
    rng = random.Random(seed)
    kind = (lib.Graph, lib.DiGraph, lib.MultiGraph, lib.MultiDiGraph)[seed % 4]
    n = rng.randint(2, 40)
    labels = list(range(n))
    if seed % 3 == 0:
        # "v10" < "v2": label order is not integer order.
        labels = [f"v{i}" for i in labels]
    order = labels[:]
    if seed % 2:
        rng.shuffle(order)
    graph = kind()
    graph.add_nodes_from(order)
    weighting = (seed // 4) % 5
    for _ in range(rng.randint(1, 3 * n)):
        u, v = rng.choice(labels), rng.choice(labels)
        if u == v and rng.random() < 0.7:
            continue
        if weighting == 0 or rng.random() < 0.1:
            graph.add_edge(u, v)
        elif weighting == 1:
            graph.add_edge(u, v, weight=rng.choice([1, 2, 3]))
        elif weighting == 2:
            graph.add_edge(u, v, weight=rng.choice([0.5, 1.5, 0.1, 0.7]))
        elif weighting == 3:
            graph.add_edge(u, v, weight=rng.randint(-2, 5))
        else:
            graph.add_edge(u, v, weight=rng.random() * 10)
    return graph, (None if weighting == 0 else "weight")


def _cnm_outcome(community, graph, **kwargs):
    try:
        result = community.greedy_modularity_communities(graph, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the exception is the observation
        return ("raise", type(exc).__name__, str(exc))
    return ("ok", [type(c).__name__ for c in result], [list(c) for c in result])


def _cnm_variants(seed, n):
    yield {}
    yield {"resolution": (0.5, 2, 1.3)[seed % 3]}
    yield {"cutoff": 1 + seed % min(n, 4)}
    yield {"best_n": max(2, n // (2 + seed % 3))}
    yield {"cutoff": 2 if n >= 3 else 1, "best_n": n}


@pytest.mark.parametrize("start", range(0, 400, 50))
def test_greedy_modularity_communities_equals_networkx_exactly(start):
    for seed in range(start, start + 50):
        fg, weight = _cnm_graph(fnx, seed)
        ng, _ = _cnm_graph(nx, seed)
        for kwargs in _cnm_variants(seed, len(ng)):
            expected = _cnm_outcome(ncom, ng, weight=weight, **kwargs)
            assert _cnm_outcome(fnx.community, fg, weight=weight, **kwargs) == expected, (
                seed,
                kwargs,
            )


@pytest.mark.parametrize("labels", ["int", "str", "shuffled"])
@pytest.mark.parametrize("weighted", [False, True])
def test_greedy_modularity_communities_large_graph_equals_networkx(labels, weighted):
    source = nx.powerlaw_cluster_graph(1200, 3, 0.4, seed=7)
    rng = random.Random(11)
    names = list(source)
    if labels == "str":
        names = [f"n{node}" for node in names]
    elif labels == "shuffled":
        rng.shuffle(names)
    edges = [
        (names[u], names[v], {"weight": rng.choice([1, 2, 3])} if weighted else {})
        for u, v in source.edges()
    ]
    fg, ng = fnx.Graph(), nx.Graph()
    for graph in (fg, ng):
        graph.add_nodes_from(names)
        graph.add_edges_from(edges)
    weight = "weight" if weighted else None
    assert _cnm_outcome(fnx.community, fg, weight=weight) == _cnm_outcome(
        ncom, ng, weight=weight
    )


@pytest.mark.parametrize(
    "kwargs",
    [{"cutoff": 0}, {"cutoff": 9}, {"best_n": 0}, {"best_n": 9}, {"cutoff": 3, "best_n": 2}],
)
def test_greedy_modularity_communities_argument_errors_match(kwargs):
    fg, ng = fnx.path_graph(5), nx.path_graph(5)
    expected = _cnm_outcome(ncom, ng, **kwargs)
    assert expected[0] == "raise"
    assert _cnm_outcome(fnx.community, fg, **kwargs) == expected


def test_greedy_modularity_communities_zero_total_weight_raises_like_networkx():
    fg, ng = fnx.Graph(), nx.Graph()
    for graph in (fg, ng):
        graph.add_edge(0, 1, weight=1)
        graph.add_edge(1, 2, weight=-1)
    expected = _cnm_outcome(ncom, ng, weight="weight")
    assert expected[:2] == ("raise", "ZeroDivisionError")
    assert _cnm_outcome(fnx.community, fg, weight="weight") == expected


def _mixed_label_graph(lib):
    graph = lib.Graph()
    nx.add_path(graph, [0, "a", 1, "b", 2, "c"])
    return graph


def _tuple_label_graph(lib):
    graph = lib.Graph()
    nx.add_cycle(graph, [(0, 1), (1, 0), (0, 0), (1, 1)])
    return graph


def _special_weight_graph(lib, value):
    graph = lib.path_graph(6)
    for u, v in graph.edges():
        graph[u][v]["weight"] = 1.0
    graph[2][3]["weight"] = value
    return graph


@pytest.mark.parametrize(
    "build, weight",
    [
        (_mixed_label_graph, None),
        (_tuple_label_graph, None),
        (lambda lib: _special_weight_graph(lib, float("nan")), "weight"),
        (lambda lib: _special_weight_graph(lib, float("inf")), "weight"),
        (lambda lib: _special_weight_graph(lib, True), "weight"),
        (lambda lib: _special_weight_graph(lib, 2**60), "weight"),
    ],
)
def test_greedy_modularity_communities_unsupported_shapes_match_networkx(build, weight):
    assert _cnm_outcome(fnx.community, build(fnx), weight=weight) == _cnm_outcome(
        ncom, build(nx), weight=weight
    )


def _cnm_networkx_frames(call):
    import sys

    loop_files = ("community/modularity_max.py", "utils/mapped_queue.py")
    seen = []

    def profile(frame, event, arg):
        if event == "call" and frame.f_code.co_filename.endswith(loop_files):
            seen.append(frame.f_code.co_name)

    sys.setprofile(profile)
    try:
        call()
    finally:
        sys.setprofile(None)
    return seen


def test_greedy_modularity_communities_runs_no_networkx_loop():
    graph, weight = _cnm_graph(fnx, 5)
    assert _cnm_networkx_frames(
        lambda: fnx.community.greedy_modularity_communities(graph, weight=weight)
    ) == []
    # The census does see networkx's loop where it runs: a fallback shape.
    tuples = _tuple_label_graph(fnx)
    assert "_greedy_modularity_communities_generator" in _cnm_networkx_frames(
        lambda: fnx.community.greedy_modularity_communities(tuples)
    )


@pytest.mark.parametrize("build", [lambda lib: _cnm_graph(lib, 8)[0], _tuple_label_graph])
def test_greedy_modularity_communities_backend_dispatch_matches_networkx(build):
    graph = build(nx)
    expected = ncom.greedy_modularity_communities(graph)
    result = ncom.greedy_modularity_communities(graph, backend="franken_networkx")
    assert [list(c) for c in result] == [list(c) for c in expected]
