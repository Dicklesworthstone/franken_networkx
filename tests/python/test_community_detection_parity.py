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
    # Tuple labels use the owned engine; native rejection must not re-enter
    # NetworkX's algorithm or its priority queue implementation.
    tuples = _tuple_label_graph(fnx)
    assert _cnm_networkx_frames(
        lambda: fnx.community.greedy_modularity_communities(tuples)
    ) == []
    assert "_greedy_modularity_communities_generator" in _cnm_networkx_frames(
        lambda: ncom.greedy_modularity_communities(_tuple_label_graph(nx))
    )


@pytest.mark.parametrize("build", [lambda lib: _cnm_graph(lib, 8)[0], _tuple_label_graph])
def test_greedy_modularity_communities_backend_dispatch_matches_networkx(build):
    graph = build(nx)
    expected = ncom.greedy_modularity_communities(graph)
    result = ncom.greedy_modularity_communities(graph, backend="franken_networkx")
    assert [list(c) for c in result] == [list(c) for c in expected]


class _CnmOrderedNode:
    """Comparable labels with collisions, outside the primitive native domain."""

    def __init__(self, value):
        self.value = value

    def __hash__(self):
        return 0

    def __eq__(self, other):
        return isinstance(other, _CnmOrderedNode) and self.value == other.value

    def __lt__(self, other):
        return self.value < other.value

    def __repr__(self):
        return f"CnmNode({self.value})"


def _cnm_owned_graph(lib, kind, seed, labels, weights):
    from fractions import Fraction

    rng = random.Random(seed)
    names = rng.sample(range(11), 11)
    if labels == "tuple":
        names = [(value * 1024, value % 3) for value in names]
    elif labels == "bytes":
        names = [f"n{value}".encode() for value in names]
    else:
        names = [_CnmOrderedNode(value) for value in names]
    graph = getattr(lib, kind)()
    graph.add_nodes_from(names)
    for index in range(24):
        source, target = rng.choices(names, k=2)
        if weights == "fraction":
            value = Fraction(index % 7 + 1, 3)
        elif weights == "large_int":
            value = 2**60 + index
        else:
            value = rng.choice([1, 2, 0.1, 0.5])
        graph.add_edge(source, target, cost=value)
    return graph


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("labels", ["tuple", "bytes", "objects"])
@pytest.mark.parametrize("weights", ["mixed", "fraction", "large_int"])
@pytest.mark.parametrize("seed", range(4))
def test_cnm_owned_merge_schedule_matches_networkx(kind, labels, weights, seed):
    from fractions import Fraction

    fg = _cnm_owned_graph(fnx, kind, seed, labels, weights)
    ng = _cnm_owned_graph(nx, kind, seed, labels, weights)
    for kwargs in (
        {},
        {"resolution": Fraction(2, 3)},
        {"cutoff": 3},
        {"best_n": 2},
    ):
        expected = _cnm_outcome(ncom, ng, weight="cost", **kwargs)
        assert _cnm_outcome(fnx.community, fg, weight="cost", **kwargs) == expected


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("mode", ["view", "assigned"])
def test_cnm_owned_engine_reads_view_and_assigned_rows(kind, mode):
    graphs = []
    for lib in (fnx, nx):
        graph = _cnm_owned_graph(lib, kind, 17, "tuple", "mixed")
        if mode == "view":
            graph = graph.subgraph(list(graph)[2:])
        else:
            replacement = graph.copy()
            graph.clear_edges()
            graph._adj = replacement._adj
            if graph.is_directed():
                graph._succ = replacement._succ
                graph._pred = replacement._pred
        graphs.append(graph)
    expected = _cnm_outcome(ncom, graphs[1], weight="cost")
    assert expected[0] == "ok"
    assert _cnm_outcome(fnx.community, graphs[0], weight="cost") == expected
    assert _cnm_networkx_frames(
        lambda: fnx.community.greedy_modularity_communities(graphs[0], weight="cost")
    ) == []


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_cnm_owned_unordered_priorities_match_networkx(kind, value):
    graphs = [_cnm_owned_graph(lib, kind, 5, "tuple", "mixed") for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_edge(list(graph)[0], list(graph)[1], cost=value)
    for kwargs in ({}, {"cutoff": 3}, {"best_n": 2}):
        assert _cnm_outcome(fnx.community, graphs[0], weight="cost", **kwargs) == (
            _cnm_outcome(ncom, graphs[1], weight="cost", **kwargs)
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cutoff": 2.25},
        {"best_n": 2.25},
        {"cutoff": float("nan")},
        {"resolution": float("nan")},
        {"resolution": float("inf")},
        {"cutoff": 0},
        {"best_n": 0},
        {"cutoff": 4, "best_n": 3},
    ],
)
def test_cnm_owned_boundary_parameters_match_networkx(kwargs):
    fg, ng = (_cnm_owned_graph(lib, "Graph", 3, "tuple", "mixed") for lib in (fnx, nx))
    assert _cnm_outcome(fnx.community, fg, **kwargs) == _cnm_outcome(ncom, ng, **kwargs)


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [b"cost", ("cost", 1), 2, None])
def test_cnm_owned_nonstring_weight_selectors_match_networkx(kind, weight):
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, kind)()
        graph.add_edges_from(
            [((0,), (1,), {weight: 2}), ((1,), (2,), {weight: 1}), ((2,), (0,), {weight: 3})]
        )
        graphs.append(graph)
    expected = _cnm_outcome(ncom, graphs[1], weight=weight)
    assert expected[0] == "ok"
    assert _cnm_outcome(fnx.community, graphs[0], weight=weight) == expected


@pytest.mark.parametrize("node_count", [0, 1, 5])
def test_cnm_owned_edgeless_graph_short_circuits_parameter_validation(node_count):
    fg, ng = fnx.Graph(), nx.Graph()
    for graph in (fg, ng):
        graph.add_nodes_from((node,) for node in range(node_count))
    expected = _cnm_outcome(ncom, ng, cutoff=0, best_n=-1)
    assert expected[0] == "ok"
    assert _cnm_outcome(fnx.community, fg, cutoff=0, best_n=-1) == expected


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("best_n", [None, 1, 2, 3])
def test_cnm_owned_exhausted_frontier_merges_largest_disconnected_groups(kind, best_n):
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, kind)()
        graph.add_nodes_from((node * 1024,) for node in range(9))
        graph.add_edges_from(
            [((0,), (1024,)), ((1024,), (2048,)), ((4096,), (5120,)), ((8192,), (8192,))]
        )
        graphs.append(graph)
    assert _cnm_outcome(fnx.community, graphs[0], best_n=best_n) == _cnm_outcome(
        ncom, graphs[1], best_n=best_n
    )


def test_cnm_owned_graph_protocols_are_read_once_without_conversion():
    class ObservedGraph(nx.Graph):
        def size(self, weight=None):
            self.events.append(("size", weight))
            return super().size(weight)

        def number_of_nodes(self):
            self.events.append("number_of_nodes")
            return super().number_of_nodes()

        def is_directed(self):
            self.events.append("is_directed")
            return super().is_directed()

        def __iter__(self):
            self.events.append("iter")
            return super().__iter__()

    outcomes = []
    for community in (fnx.community, ncom):
        graph = ObservedGraph()
        graph.add_edges_from([((0,), (1,), {"cost": 2}), ((1,), (2,), {"cost": 1})])
        graph.events = []
        result = _cnm_outcome(community, graph, weight="cost")
        outcomes.append((result, graph.events))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("entrypoint", ["direct", "backend", "cached_backend"])
def test_cnm_filtered_providers_keep_their_read_order(kind, entrypoint, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(use_fnx):
        root = getattr(nx, kind)()
        root.add_weighted_edges_from([(0, 1, 2), (1, 2, 1), (2, 0, 3), (2, 3, 1)])
        events = []

        def node_filter(node):
            events.append(("node", node))
            return node != 3

        def edge_filter(*edge):
            events.append(("edge", edge))
            return True

        graph = nx.subgraph_view(root, filter_node=node_filter, filter_edge=edge_filter)
        if use_fnx and entrypoint == "cached_backend":
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        # A direct attribute write does not clear NetworkX's conversion cache.
        # The next call must read the changed original edge even in that state.
        attrs = root[0][1][0] if root.is_multigraph() else root[0][1]
        attrs["weight"] = 7
        events.clear()
        if use_fnx and entrypoint == "direct":
            result = fnx.community.greedy_modularity_communities(graph, weight="weight")
        else:
            result = ncom.greedy_modularity_communities(
                graph, weight="weight", backend="franken_networkx" if use_fnx else "networkx"
            )
        if use_fnx and entrypoint != "direct":
            assert not graph.__networkx_cache__.get("backends")
        return [list(part) for part in result], events

    assert run(True) == run(False)


def test_cnm_instance_method_provider_is_not_probed_twice():
    outcomes = []
    for community in (fnx.community, ncom):
        graph = nx.path_graph(4)
        events = []
        size = graph.size

        def observed_size(weight=None):
            events.append(weight)
            return size(weight)

        graph.size = observed_size
        outcomes.append((_cnm_outcome(community, graph, weight="weight"), events))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("entrypoint", ["direct", "backend", "cached_backend"])
def test_cnm_custom_edge_dictionaries_keep_their_read_order(kind, entrypoint, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(use_fnx):
        graph = getattr(nx, kind)()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 2, 1), (2, 0, 3), (2, 3, 1)])
        if use_fnx and entrypoint == "cached_backend":
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        events = []

        class EdgeData(dict):
            def get(self, key, default=None):
                events.append(("get", key))
                return super().get(key, default)

            def __contains__(self, key):
                events.append(("contains", key))
                return super().__contains__(key)

            def __getitem__(self, key):
                events.append(("item", key))
                return super().__getitem__(key)

        if graph.is_multigraph():
            attrs = EdgeData(graph._adj[0][1][0])
            graph._adj[0][1][0] = attrs
            if graph.is_directed():
                graph._pred[1][0][0] = attrs
        else:
            attrs = EdgeData(graph._adj[0][1])
            graph._adj[0][1] = attrs
            if graph.is_directed():
                graph._pred[1][0] = attrs
            else:
                graph._adj[1][0] = attrs
        attrs["weight"] = 7
        if use_fnx and entrypoint == "direct":
            result = fnx.community.greedy_modularity_communities(graph, weight="weight")
        else:
            result = ncom.greedy_modularity_communities(
                graph, weight="weight", backend="franken_networkx" if use_fnx else "networkx"
            )
        if use_fnx and entrypoint != "direct":
            assert not graph.__networkx_cache__.get("backends")
        return [list(part) for part in result], events

    assert run(True) == run(False)
