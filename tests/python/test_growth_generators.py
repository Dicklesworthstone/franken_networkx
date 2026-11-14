"""Tests for growth-model and degree-model generator wrappers."""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _graph_signature(graph):
    nodes = sorted((repr(node), tuple(sorted(attrs.items()))) for node, attrs in graph.nodes(data=True))
    if graph.is_multigraph():
        edges = sorted(
            (
                *((repr(u), repr(v)) if graph.is_directed() else tuple(sorted((repr(u), repr(v))))),
                key,
                tuple(sorted(attrs.items())),
            )
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (
                *((repr(u), repr(v)) if graph.is_directed() else tuple(sorted((repr(u), repr(v))))),
                tuple(sorted(attrs.items())),
            )
            for u, v, attrs in graph.edges(data=True)
        )
    return (
        graph.is_directed(),
        graph.is_multigraph(),
        tuple(sorted(graph.graph.items())),
        nodes,
        edges,
    )


def test_gnc_and_gnr_graph_shapes():
    gnc = fnx.gnc_graph(6, seed=1)
    gnr = fnx.gnr_graph(6, 0.5, seed=1)

    assert gnc.number_of_nodes() == 6
    assert gnr.number_of_nodes() == 6
    assert gnc.number_of_edges() > 0
    assert gnr.number_of_edges() > 0


_DIRECTED_GROWTH_CASES = [
    ("gn_graph", (8,)),
    ("gnc_graph", (8,)),
    ("gnr_graph", (8, 0.4)),
]


def _directed_growth_signature(graph):
    edge_options = {"keys": True} if graph.is_multigraph() else {}
    return (
        graph.is_directed(), graph.is_multigraph(), dict(graph.graph),
        list(graph.nodes(data=True)), list(graph.edges(data=True, **edge_options)),
        [list(graph.succ[node]) for node in graph],
        [list(graph.pred[node]) for node in graph],
    )


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
@pytest.mark.parametrize("graph_kind", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("use_instance", [False, True], ids=["class", "instance"])
def test_directed_growth_preserves_constructor_and_clear_protocol(
    name, args, graph_kind, use_instance,
):
    def outcome(lib):
        events = []

        class GeneratedGraph(getattr(lib, graph_kind)):
            def __init__(self):
                super().__init__()
                events.append("construct")
                self.graph["created_by_factory"] = len(events)
                self.add_node("factory-node")

            def clear(self):
                events.append("clear")
                super().clear()

        target = GeneratedGraph() if use_instance else GeneratedGraph
        if use_instance:
            events.clear()
        graph = getattr(lib, name)(*args, seed=7, create_using=target)
        if use_instance:
            assert graph is target
        return _directed_growth_signature(graph), events

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
@pytest.mark.parametrize("graph_kind", ["DiGraph", "MultiDiGraph"])
def test_directed_growth_random_callbacks_observe_each_completed_mutation(
    name, args, graph_kind,
):
    def outcome(lib):
        graph = getattr(lib, graph_kind)()
        events = []

        class GraphRandom(random.Random):
            def random(self):
                events.append(("random", tuple(graph), tuple(graph.edges())))
                return 0.6

            def randrange(self, start, stop=None):
                events.append(("randrange", tuple(graph), tuple(graph.edges())))
                if stop is None:
                    start, stop = 0, start
                return start + graph.number_of_edges() % (stop - start)

        result = getattr(lib, name)(*args, seed=GraphRandom(7), create_using=graph)
        assert result is graph
        return _directed_growth_signature(graph), events

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES[1:])
@pytest.mark.parametrize("graph_kind", ["DiGraph", "MultiDiGraph"])
def test_directed_growth_reads_caller_successor_protocol(name, args, graph_kind):
    def outcome(lib):
        events = []

        class GrowthGraph(getattr(lib, graph_kind)):
            def successors(self, node):
                events.append((node, tuple(self.edges())))
                # A graph subclass may expose neighbors through a projection.
                return iter(reversed(list(super().successors(node))))

            def add_edge(self, u, v, **attrs):
                result = super().add_edge(u, v, **attrs)
                if u == 1:
                    super().add_edge(u, "extra-successor")
                return result

        graph = GrowthGraph()
        result = getattr(lib, name)(*args, seed=7, create_using=graph)
        assert result is graph
        return _directed_growth_signature(graph), events

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
def test_directed_growth_default_graph_honors_custom_random_methods(name, args):
    def outcome(lib):
        events = []

        class CustomRandom(random.Random):
            def random(self):
                events.append("random")
                return 0.6

            def randrange(self, start, stop=None):
                events.append(("randrange", start, stop))
                return (start if stop is None else stop) - 1

        rng = CustomRandom(11)
        graph = getattr(lib, name)(*args, seed=rng)
        return _directed_growth_signature(graph), rng.getstate(), events

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
@pytest.mark.parametrize("graph_kind", ["DiGraph", "MultiDiGraph"])
def test_directed_growth_keeps_completed_prefix_when_random_callback_fails(
    name, args, graph_kind,
):
    def outcome(lib):
        graph = getattr(lib, graph_kind)()

        class FailingRandom(random.Random):
            calls = 0

            def _next(self):
                self.calls += 1
                if self.calls == 3:
                    raise RuntimeError("random source stopped")

            def random(self):
                self._next()
                return 0.6

            def randrange(self, start, stop=None):
                self._next()
                return start

        with pytest.raises(RuntimeError, match="random source stopped"):
            getattr(lib, name)(*args, seed=FailingRandom(7), create_using=graph)
        return _directed_growth_signature(graph)

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
@pytest.mark.parametrize("graph_kind", ["Graph", "MultiGraph"])
def test_directed_growth_rejects_undirected_after_initializing_target(
    name, args, graph_kind,
):
    def outcome(lib):
        graph = getattr(lib, graph_kind)()
        graph.add_edge("old", "data")
        graph.graph["old"] = True
        with pytest.raises(lib.NetworkXError) as error:
            getattr(lib, name)(*args, seed=7, create_using=graph)
        return str(error.value), dict(graph.graph), list(graph), list(graph.edges())

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("kind", ["RandomState", "Generator", "legacy-adapter", "bits-adapter"])
@pytest.mark.parametrize("graph_kind", [None, "DiGraph", "MultiDiGraph"])
def test_gn_graph_preserves_numpy_random_stream(kind, graph_kind):
    np = pytest.importorskip("numpy")

    def outcome(lib):
        raw = np.random.RandomState(11) if kind in {"RandomState", "legacy-adapter"} else np.random.default_rng(11)
        seed = nx.utils.create_py_random_state(raw) if kind.endswith("adapter") else raw
        graph = getattr(lib, graph_kind)() if graph_kind else None
        result = lib.gn_graph(10, create_using=graph, seed=seed)
        state = raw.get_state() if isinstance(raw, np.random.RandomState) else raw.bit_generator.state
        return _directed_growth_signature(result), state

    actual, expected = outcome(fnx), outcome(nx)
    assert actual[0] == expected[0]
    np.testing.assert_equal(actual[1], expected[1])


@pytest.mark.parametrize(
    "kind", ["float-subclass", "fraction", "decimal", "huge-int", "nan", "infinity"],
)
def test_gnr_graph_preserves_probability_comparisons(kind):
    from decimal import Decimal
    from fractions import Fraction

    def outcome(lib):
        events = []

        class Probability(float):
            def __gt__(self, value):
                events.append(value)
                return super().__gt__(value)

        probability = {
            "float-subclass": lambda: Probability(0.4),
            "fraction": lambda: Fraction(2, 5),
            "decimal": lambda: Decimal("0.4"),
            "huge-int": lambda: 10**400,
            "nan": lambda: float("nan"),
            "infinity": lambda: float("inf"),
        }[kind]()
        rng = random.Random(11)
        graph = lib.gnr_graph(8, probability, seed=rng)
        return _directed_growth_signature(graph), rng.getstate(), events

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
@pytest.mark.parametrize("n", [-2, 0, 1, False, True, 1.0])
def test_directed_growth_boundary_sizes_match_networkx(name, args, n):
    actual = getattr(fnx, name)(n, *args[1:], seed=7)
    expected = getattr(nx, name)(n, *args[1:], seed=7)
    assert _directed_growth_signature(actual) == _directed_growth_signature(expected)


@pytest.mark.parametrize("name,args", _DIRECTED_GROWTH_CASES)
@pytest.mark.parametrize("n", [0, 6])
def test_directed_growth_accepts_numpy_sizes(name, args, n):
    np = pytest.importorskip("numpy")
    actual = getattr(fnx, name)(np.int64(n), *args[1:], seed=7)
    expected = getattr(nx, name)(np.int64(n), *args[1:], seed=7)
    assert _directed_growth_signature(actual) == _directed_growth_signature(expected)


def test_fast_gnp_random_graph_is_reproducible():
    left = fnx.fast_gnp_random_graph(8, 0.3, seed=7)
    right = fnx.fast_gnp_random_graph(8, 0.3, seed=7)

    assert sorted(left.edges()) == sorted(right.edges())


def test_directed_degree_sequence_generators():
    config = fnx.directed_configuration_model([0, 1], [1, 0], seed=1)
    hakimi = fnx.directed_havel_hakimi_graph([0, 1, 1], [1, 1, 0])

    assert config.is_directed()
    assert config.number_of_edges() == 1
    assert hakimi.is_directed()
    assert sorted(hakimi.in_degree[node] for node in hakimi.nodes()) == [0, 1, 1]
    assert sorted(hakimi.out_degree[node] for node in hakimi.nodes()) == [0, 1, 1]


def test_joint_degree_generators():
    undirected = fnx.joint_degree_graph({1: {2: 2}, 2: {1: 2}}, seed=1)
    directed = fnx.directed_joint_degree_graph([0, 1], [1, 0], {1: {1: 1}}, seed=1)

    assert undirected.number_of_nodes() == 3
    assert undirected.number_of_edges() == 2
    assert directed.is_directed()
    assert sorted(directed.edges()) == [(0, 1)]


def test_expected_degree_graph_returns_graph():
    graph = fnx.expected_degree_graph([1.0, 1.5, 2.0], seed=1, selfloops=False)

    assert graph.number_of_nodes() == 3


def test_native_gnc_and_gnr_graphs_do_not_fallback_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "gnc_graph", fail)
    monkeypatch.setattr(nx, "gnr_graph", fail)

    gnc = fnx.gnc_graph(6, seed=1)
    gnr = fnx.gnr_graph(6, 0.5, seed=1)

    assert sorted(gnc.edges()) == [(1, 0), (2, 0), (3, 0), (3, 1), (4, 0), (5, 0), (5, 1), (5, 3)]
    assert sorted(gnr.edges()) == [(1, 0), (2, 0), (3, 1), (4, 3), (5, 0)]


def test_native_random_generators_do_not_fallback_to_networkx(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "balanced_tree", fail)
    monkeypatch.setattr(nx, "barbell_graph", fail)
    monkeypatch.setattr(nx, "bull_graph", fail)
    monkeypatch.setattr(nx, "cubical_graph", fail)
    monkeypatch.setattr(nx, "desargues_graph", fail)
    monkeypatch.setattr(nx, "diamond_graph", fail)
    monkeypatch.setattr(nx, "dodecahedral_graph", fail)
    monkeypatch.setattr(nx, "empty_graph", fail)
    monkeypatch.setattr(nx, "complete_graph", fail)
    monkeypatch.setattr(nx, "cycle_graph", fail)
    monkeypatch.setattr(nx, "full_rary_tree", fail)
    monkeypatch.setattr(nx, "binomial_tree", fail)
    monkeypatch.setattr(nx, "chordal_cycle_graph", fail)
    monkeypatch.setattr(nx, "chvatal_graph", fail)
    monkeypatch.setattr(nx, "complete_bipartite_graph", fail)
    monkeypatch.setattr(nx, "circulant_graph", fail)
    monkeypatch.setattr(nx, "house_graph", fail)
    monkeypatch.setattr(nx, "house_x_graph", fail)
    monkeypatch.setattr(nx, "heawood_graph", fail)
    monkeypatch.setattr(nx, "circular_ladder_graph", fail)
    monkeypatch.setattr(nx, "complete_multipartite_graph", fail)
    monkeypatch.setattr(nx, "frucht_graph", fail)
    monkeypatch.setattr(nx, "generalized_petersen_graph", fail)
    monkeypatch.setattr(nx, "icosahedral_graph", fail)
    monkeypatch.setattr(nx, "krackhardt_kite_graph", fail)
    monkeypatch.setattr(nx, "ladder_graph", fail)
    monkeypatch.setattr(nx, "lollipop_graph", fail)
    monkeypatch.setattr(nx, "moebius_kantor_graph", fail)
    monkeypatch.setattr(nx, "null_graph", fail)
    monkeypatch.setattr(nx, "octahedral_graph", fail)
    monkeypatch.setattr(nx, "paley_graph", fail)
    monkeypatch.setattr(nx, "path_graph", fail)
    monkeypatch.setattr(nx, "petersen_graph", fail)
    monkeypatch.setattr(nx, "star_graph", fail)
    monkeypatch.setattr(nx, "tadpole_graph", fail)
    monkeypatch.setattr(nx, "truncated_cube_graph", fail)
    monkeypatch.setattr(nx, "truncated_tetrahedron_graph", fail)
    monkeypatch.setattr(nx, "tetrahedral_graph", fail)
    monkeypatch.setattr(nx, "trivial_graph", fail)
    monkeypatch.setattr(nx, "tutte_graph", fail)
    monkeypatch.setattr(nx, "wheel_graph", fail)
    monkeypatch.setattr(nx, "windmill_graph", fail)
    monkeypatch.setattr(nx, "grid_2d_graph", fail)
    monkeypatch.setattr(nx, "gnp_random_graph", fail)
    monkeypatch.setattr(nx, "erdos_renyi_graph", fail)
    monkeypatch.setattr(nx, "fast_gnp_random_graph", fail)
    monkeypatch.setattr(nx, "watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "barabasi_albert_graph", fail)
    monkeypatch.setattr(nx, "newman_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "connected_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "random_regular_graph", fail)
    monkeypatch.setattr(nx, "powerlaw_cluster_graph", fail)
    monkeypatch.setattr(nx, "random_lobster_graph", fail)
    monkeypatch.setattr(nx, "random_shell_graph", fail)

    assert fnx.balanced_tree(2, 2).number_of_nodes() == 7
    assert fnx.barbell_graph(3, 2).number_of_nodes() == 8
    assert fnx.bull_graph().number_of_nodes() == 5
    assert fnx.chordal_cycle_graph(5).number_of_nodes() == 5
    assert fnx.chvatal_graph().number_of_nodes() == 12
    assert fnx.circulant_graph(6, [1, 2]).number_of_nodes() == 6
    assert fnx.complete_graph(4).number_of_nodes() == 4
    assert fnx.cycle_graph(4).number_of_nodes() == 4
    assert fnx.cubical_graph().number_of_nodes() == 8
    assert fnx.desargues_graph().number_of_nodes() == 20
    assert fnx.diamond_graph().number_of_nodes() == 4
    assert fnx.dodecahedral_graph().number_of_nodes() == 20
    assert fnx.empty_graph(4).number_of_nodes() == 4
    assert fnx.full_rary_tree(2, 7).number_of_nodes() == 7
    assert fnx.binomial_tree(3).number_of_nodes() == 8
    assert fnx.complete_bipartite_graph(2, 3).number_of_nodes() == 5
    assert fnx.complete_multipartite_graph(2, 3, 1).number_of_nodes() == 6
    assert fnx.frucht_graph().number_of_nodes() == 12
    assert fnx.generalized_petersen_graph(5, 2).number_of_nodes() == 10
    assert fnx.house_graph().number_of_nodes() == 5
    assert fnx.house_x_graph().number_of_nodes() == 5
    assert fnx.heawood_graph().number_of_nodes() == 14
    assert fnx.icosahedral_graph().number_of_nodes() == 12
    assert fnx.circular_ladder_graph(4).number_of_nodes() == 8
    assert fnx.krackhardt_kite_graph().number_of_nodes() == 10
    assert fnx.ladder_graph(4).number_of_nodes() == 8
    assert fnx.lollipop_graph(4, 3).number_of_nodes() == 7
    assert fnx.moebius_kantor_graph().number_of_nodes() == 16
    assert fnx.null_graph().number_of_nodes() == 0
    assert fnx.octahedral_graph().number_of_nodes() == 6
    assert fnx.paley_graph(5).number_of_nodes() == 5
    assert fnx.path_graph(4).number_of_nodes() == 4
    assert fnx.petersen_graph().number_of_nodes() == 10
    assert fnx.star_graph(3).number_of_nodes() == 4
    assert fnx.tadpole_graph(4, 3).number_of_nodes() == 7
    assert fnx.truncated_cube_graph().number_of_nodes() == 24
    assert fnx.truncated_tetrahedron_graph().number_of_nodes() == 12
    assert fnx.tetrahedral_graph().number_of_nodes() == 4
    assert fnx.trivial_graph().number_of_nodes() == 1
    assert fnx.tutte_graph().number_of_nodes() == 46
    assert fnx.wheel_graph(6).number_of_nodes() == 6
    assert fnx.windmill_graph(3, 4).number_of_nodes() == 10
    assert fnx.grid_2d_graph(2, 3).number_of_nodes() == 6
    assert fnx.gnp_random_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.erdos_renyi_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.fast_gnp_random_graph(7, 0.2, seed=42).number_of_nodes() == 7
    assert fnx.watts_strogatz_graph(7, 3, 0.0, seed=42).number_of_nodes() == 7
    assert fnx.barabasi_albert_graph(8, 2, seed=42).number_of_nodes() == 8
    assert fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42).number_of_nodes() == 7
    assert fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42).number_of_nodes() == 12
    assert fnx.random_regular_graph(2, 6, seed=42).number_of_nodes() == 6
    assert fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42).number_of_nodes() == 10
    assert fnx.random_lobster_graph(8, 0.4, 0.3, seed=1).number_of_nodes() == 2
    assert fnx.random_shell_graph([(4, 8, 0.8)], seed=1).number_of_nodes() == 4


def test_small_world_generators_support_create_using_without_fallback(monkeypatch):
    expected_connected = fnx.readwrite._from_nx_graph(
        nx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42, create_using=None),
        create_using=fnx.Graph(),
    )
    expected_powerlaw = fnx.readwrite._from_nx_graph(
        nx.powerlaw_cluster_graph(10, 2, 0.5, seed=42, create_using=None),
        create_using=fnx.Graph(),
    )
    expected_ws = fnx.readwrite._from_nx_graph(
        nx.watts_strogatz_graph(12, 4, 0.2, seed=42, create_using=None),
        create_using=fnx.Graph(),
    )
    expected_nws = fnx.readwrite._from_nx_graph(
        nx.newman_watts_strogatz_graph(12, 4, 0.2, seed=42, create_using=None),
        create_using=fnx.Graph(),
    )

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "newman_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "connected_watts_strogatz_graph", fail)
    monkeypatch.setattr(nx, "powerlaw_cluster_graph", fail)

    actual_ws = fnx.watts_strogatz_graph(12, 4, 0.2, seed=42, create_using=fnx.Graph())
    actual_nws = fnx.newman_watts_strogatz_graph(12, 4, 0.2, seed=42, create_using=fnx.Graph())
    actual_connected = fnx.connected_watts_strogatz_graph(
        12, 4, 0.2, tries=5, seed=42, create_using=fnx.Graph()
    )
    actual_powerlaw = fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42, create_using=fnx.Graph())

    assert _graph_signature(actual_ws) == _graph_signature(expected_ws)
    assert _graph_signature(actual_nws) == _graph_signature(expected_nws)
    assert _graph_signature(actual_connected) == _graph_signature(expected_connected)
    assert _graph_signature(actual_powerlaw) == _graph_signature(expected_powerlaw)


def test_small_world_generators_match_networkx_for_seeded_random_cases():
    assert _graph_signature(fnx.watts_strogatz_graph(12, 4, 0.2, seed=42)) == _graph_signature(
        nx.watts_strogatz_graph(12, 4, 0.2, seed=42)
    )
    assert _graph_signature(fnx.newman_watts_strogatz_graph(12, 4, 0.2, seed=42)) == _graph_signature(
        nx.newman_watts_strogatz_graph(12, 4, 0.2, seed=42)
    )
    assert _graph_signature(
        fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42)
    ) == _graph_signature(nx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42))
    assert _graph_signature(fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42)) == _graph_signature(
        nx.powerlaw_cluster_graph(10, 2, 0.5, seed=42)
    )


def test_seeded_watts_strogatz_uses_native_fast_path(monkeypatch):
    calls = []
    raw_watts_strogatz_graph = fnx._rust_watts_strogatz_graph

    def spy(n, k, p, seed):
        calls.append((n, k, p, seed))
        return raw_watts_strogatz_graph(n, k, p, seed)

    monkeypatch.setattr(fnx, "_rust_watts_strogatz_graph", spy)

    graph = fnx.watts_strogatz_graph(12, 4, 0.2, seed=42)

    assert calls == [(12, 4, 0.2, 42)]
    expected = nx.watts_strogatz_graph(12, 4, 0.2, seed=42)
    assert _graph_signature(graph) == _graph_signature(expected)


def test_small_world_generators_reject_incompatible_create_using():
    factories = (
        lambda create_using: fnx.watts_strogatz_graph(12, 4, 0.2, seed=42, create_using=create_using),
        lambda create_using: fnx.newman_watts_strogatz_graph(12, 4, 0.2, seed=42, create_using=create_using),
        lambda create_using: fnx.connected_watts_strogatz_graph(
            12, 4, 0.2, tries=5, seed=42, create_using=create_using
        ),
        lambda create_using: fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42, create_using=create_using),
    )

    for factory in factories:
        with pytest.raises(fnx.NetworkXError, match="create_using must not be a multi-graph"):
            factory(fnx.MultiGraph())
        with pytest.raises(fnx.NetworkXError, match="create_using must not be directed"):
            factory(fnx.DiGraph())


def test_lobster_and_shell_generators_support_create_using_without_fallback(monkeypatch):
    expected_lobster = fnx.readwrite._from_nx_graph(
        nx.random_lobster_graph(8, 0.4, 0.3, seed=1, create_using=None),
        create_using=fnx.Graph(),
    )
    expected_shell = fnx.readwrite._from_nx_graph(
        nx.random_shell_graph([(4, 8, 0.8)], seed=1, create_using=None),
        create_using=fnx.Graph(),
    )

    def fail(*args, **kwargs):
        raise AssertionError("networkx fallback was used")

    monkeypatch.setattr(nx, "random_lobster_graph", fail)
    monkeypatch.setattr(nx, "random_shell_graph", fail)

    actual_lobster = fnx.random_lobster_graph(8, 0.4, 0.3, seed=1, create_using=fnx.Graph())
    actual_shell = fnx.random_shell_graph([(4, 8, 0.8)], seed=1, create_using=fnx.Graph())

    assert _graph_signature(actual_lobster) == _graph_signature(expected_lobster)
    assert _graph_signature(actual_shell) == _graph_signature(expected_shell)


def test_lobster_and_shell_generators_match_networkx_for_seeded_cases():
    assert _graph_signature(fnx.random_lobster_graph(8, 0.4, 0.3, seed=1)) == _graph_signature(
        nx.random_lobster_graph(8, 0.4, 0.3, seed=1)
    )
    assert _graph_signature(fnx.random_shell_graph([(4, 8, 0.8)], seed=1)) == _graph_signature(
        nx.random_shell_graph([(4, 8, 0.8)], seed=1)
    )


def test_lobster_and_shell_generators_reject_incompatible_create_using():
    for factory in (
        lambda create_using: fnx.random_lobster_graph(8, 0.4, 0.3, seed=1, create_using=create_using),
        lambda create_using: fnx.random_shell_graph([(4, 8, 0.8)], seed=1, create_using=create_using),
    ):
        with pytest.raises(fnx.NetworkXError, match="create_using must not be a multi-graph"):
            factory(fnx.MultiGraph())
        with pytest.raises(fnx.NetworkXError, match="create_using must not be directed"):
            factory(fnx.DiGraph())
