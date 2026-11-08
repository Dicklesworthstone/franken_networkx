"""Owned Louvain levels retain graph, numeric, random and iterator protocols."""

from decimal import Decimal
from fractions import Fraction
import random

import networkx as nx
import pytest

import franken_networkx as fnx
import franken_networkx.community as community


_NX_LEVELS = nx.community.louvain_partitions
_NX_COMMUNITIES = nx.community.louvain_communities
_RANDOM_STATE = random.Random.getstate
_GRAPH_NAMES = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _reject(*args, **kwargs):
    raise AssertionError("unexpected Louvain delegation, conversion, or native admission")


@pytest.fixture
def no_delegation(monkeypatch):
    monkeypatch.setattr(community._nx_community, "louvain_partitions", _reject)
    monkeypatch.setattr(community._nx_community, "louvain_communities", _reject)
    monkeypatch.setattr(fnx, "_networkx_graph_for_parity", _reject)


@pytest.fixture
def owned(no_delegation, monkeypatch):
    monkeypatch.setattr(community, "_louvain_native_arguments", lambda *args: None)


def _pair(name="Graph", key="weight", make_weight=int):
    mine, theirs = getattr(fnx, name)(), getattr(nx, name)()
    order = list(range(24))
    rng = random.Random(319)
    rng.shuffle(order)
    edges = []
    for u in order:
        for v in order:
            if (u != v and rng.random() < 0.12) or u == v == 3:
                cost = make_weight(1 + len(edges) % 7)
                edges.append((u, v, {key: cost}))
                if "Multi" in name and len(edges) % 3 == 0:
                    edges.append((u, v, {key: make_weight(2)}))
    for graph in (mine, theirs):
        graph.add_nodes_from(order)
        graph.add_edges_from((u, v, dict(data)) for u, v, data in edges)
    return mine, theirs


def _outcome(call):
    try:
        return ("value", call())
    except Exception as error:
        return ("error", type(error), str(error))


@pytest.mark.parametrize("name", _GRAPH_NAMES)
@pytest.mark.parametrize("key", ["weight", None, 7, ("cost", 0)])
def test_owned_weighted_levels_and_state_on_every_graph_class(owned, name, key):
    mine, theirs = _pair(name, key, lambda n: Fraction(n, 3))
    for seed in range(4):
        left, right = random.Random(seed), random.Random(seed)
        kwargs = {"weight": key, "resolution": 0.75 if seed % 2 else 1}
        expected = list(_NX_LEVELS(theirs, seed=right, **kwargs))
        actual = list(community.louvain_partitions(mine, seed=left, **kwargs))
        assert actual == expected
        assert left.getstate() == right.getstate()
        for partition in actual:
            assert set().union(*partition) == set(theirs)
            assert sum(map(len, partition)) == len(theirs)
        assert community.louvain_communities(mine, seed=seed, **kwargs) == expected[-1]


@pytest.mark.parametrize("name", _GRAPH_NAMES)
@pytest.mark.parametrize("value", [Decimal("1.25"), 10**400, "heavy", 0, float("inf")])
def test_owned_numeric_errors_and_rng_consumption(owned, name, value):
    mine, theirs = getattr(fnx, name)(), getattr(nx, name)()
    for graph in (mine, theirs):
        graph.add_edge(0, 1, weight=value)
    left, right = random.Random(7), random.Random(7)
    expected = _outcome(lambda: list(_NX_LEVELS(theirs, seed=right)))
    actual = _outcome(lambda: list(community.louvain_partitions(mine, seed=left)))
    assert actual == expected
    assert left.getstate() == right.getstate()


@pytest.mark.parametrize("name", _GRAPH_NAMES)
def test_huge_fraction_weights_keep_degree_and_size_domain(owned, name):
    """Finite rational weights must not overflow when a float degree is squared."""
    mine, theirs = getattr(fnx, name)(), getattr(nx, name)()
    for graph in (mine, theirs):
        graph.add_edge(0, 1, weight=Fraction(10**200))
    left, right = random.Random(7), random.Random(7)
    expected = list(_NX_LEVELS(theirs, seed=right))
    assert list(community.louvain_partitions(mine, seed=left)) == expected
    assert left.getstate() == right.getstate()
    assert community.louvain_communities(mine, seed=7) == expected[-1]


@pytest.mark.parametrize("name", _GRAPH_NAMES)
@pytest.mark.parametrize("key", [False, True])
def test_literal_boolean_weight_selectors_keep_errors(owned, name, key):
    mine, theirs = _pair(name)
    assert _outcome(lambda: list(community.louvain_partitions(mine, weight=key, seed=1))) == (
        _outcome(lambda: list(_NX_LEVELS(theirs, weight=key, seed=1)))
    )


@pytest.mark.parametrize("name", _GRAPH_NAMES)
def test_native_ordinary_routes_are_retained(no_delegation, monkeypatch, name):
    mine, theirs = _pair(name)
    final_calls, iterator_calls = [], []
    raw = fnx._raw_louvain_communities
    start = community._native_louvain_partitions_start

    def final(*args):
        final_calls.append(True)
        return raw(*args)

    def levels(*args):
        iterator_calls.append(True)
        return start(*args)

    monkeypatch.setattr(fnx, "_raw_louvain_communities", final)
    monkeypatch.setattr(community, "_native_louvain_partitions_start", levels)
    assert community.louvain_communities(mine, seed=4) == _NX_COMMUNITIES(theirs, seed=4)
    assert list(community.louvain_partitions(mine, seed=4)) == list(_NX_LEVELS(theirs, seed=4))
    assert final_calls == iterator_calls == [True]


def _hooked_rng(name, calls):
    rng = random.Random(42)
    original = getattr(rng, name)

    def hook(*args):
        calls.append(name)
        if name == "shuffle":
            args[0].reverse()
            return None
        return original(*args)

    setattr(rng, name, hook)
    return rng


@pytest.mark.parametrize("hook", ["shuffle", "_randbelow", "getrandbits", "random", "getstate", "setstate"])
@pytest.mark.parametrize("iterator", [False, True])
def test_instance_random_hooks_use_owned_engine(no_delegation, monkeypatch, hook, iterator):
    monkeypatch.setattr(fnx, "_raw_louvain_communities", _reject)
    monkeypatch.setattr(community, "_native_louvain_partitions_start", _reject)
    mine, theirs = fnx.cycle_graph(12), nx.cycle_graph(12)
    actual_calls, expected_calls = [], []
    left, right = _hooked_rng(hook, actual_calls), _hooked_rng(hook, expected_calls)
    if iterator:
        actual = list(community.louvain_partitions(mine, seed=left))
        expected = list(_NX_LEVELS(theirs, seed=right))
    else:
        actual = community.louvain_communities(mine, seed=left)
        expected = _NX_COMMUNITIES(theirs, seed=right)
    assert actual == expected
    assert actual_calls == expected_calls
    assert _RANDOM_STATE(left) == _RANDOM_STATE(right)


def test_random_subclass_and_hook_added_before_first_resume(no_delegation, monkeypatch):
    class ReverseRandom(random.Random):
        def shuffle(self, values):
            values.reverse()

    monkeypatch.setattr(fnx, "_raw_louvain_communities", _reject)
    monkeypatch.setattr(community, "_native_louvain_partitions_start", _reject)
    mine, theirs = fnx.cycle_graph(6), nx.cycle_graph(6)
    assert community.louvain_communities(mine, seed=ReverseRandom(4)) == (
        _NX_COMMUNITIES(theirs, seed=ReverseRandom(4))
    )
    left, right = random.Random(4), random.Random(4)
    actual, expected = community.louvain_partitions(mine, seed=left), _NX_LEVELS(theirs, seed=right)
    left.shuffle = right.shuffle = lambda values: values.reverse()
    assert list(actual) == list(expected)


@pytest.mark.parametrize("hook", ["shuffle", "_randbelow", "getrandbits", "random", "getstate", "setstate", "seed", "__init__"])
@pytest.mark.parametrize("seed", [3, 2**80])
def test_class_random_hooks_after_import_disable_native(no_delegation, monkeypatch, hook, seed):
    original = getattr(random.Random, hook)
    calls = []

    def override(self, *args):
        calls.append(hook)
        if hook == "seed" and args and type(args[0]) is int:
            args = (args[0] + 991, *args[1:])
        return original(self, *args)

    monkeypatch.setattr(random.Random, hook, override)
    monkeypatch.setattr(fnx, "_raw_louvain_communities", _reject)
    monkeypatch.setattr(community, "_native_louvain_partitions_start", _reject)
    mine, theirs = fnx.cycle_graph(10), nx.cycle_graph(10)
    expected = _NX_COMMUNITIES(theirs, seed=seed)
    expected_calls = calls.copy()
    calls.clear()
    assert community.louvain_communities(mine, seed=seed) == expected
    assert calls == expected_calls


@pytest.mark.parametrize("seed", [None, random])
def test_global_random_alias_preserves_hooks_and_state(no_delegation, monkeypatch, seed):
    old_state = random.getstate()
    try:
        monkeypatch.setattr(random._inst, "shuffle", lambda values: values.reverse())
        monkeypatch.setattr(fnx, "_raw_louvain_communities", _reject)
        mine, theirs = fnx.cycle_graph(6), nx.cycle_graph(6)
        random.seed(42)
        expected = _NX_COMMUNITIES(theirs, seed=seed)
        expected_state = random.getstate()
        random.seed(42)
        assert community.louvain_communities(mine, seed=seed) == expected
        assert random.getstate() == expected_state
    finally:
        random.setstate(old_state)


@pytest.mark.parametrize("kind", ["Generator", "RandomState"])
def test_numpy_random_sources_and_weights(no_delegation, kind):
    np = pytest.importorskip("numpy")
    factory = np.random.default_rng if kind == "Generator" else np.random.RandomState
    left, right = factory(9), factory(9)
    mine, theirs = _pair("MultiDiGraph", make_weight=np.int64)
    actual = list(community.louvain_partitions(mine, seed=left))
    expected = list(_NX_LEVELS(theirs, seed=right))
    assert actual == expected
    assert left.random() == right.random()


@pytest.mark.parametrize("name", _GRAPH_NAMES)
@pytest.mark.parametrize("key", [None, 7, ("cost", 0)])
def test_filtered_views_read_actual_weight_attributes(no_delegation, name, key):
    mine, theirs = _pair(name, key)
    mine = fnx.subgraph_view(mine, filter_node=lambda node: node < 20)
    theirs = nx.subgraph_view(theirs, filter_node=lambda node: node < 20)
    assert list(community.louvain_partitions(mine, weight=key, seed=4)) == (
        list(_NX_LEVELS(theirs, weight=key, seed=4))
    )


@pytest.mark.parametrize("name", _GRAPH_NAMES)
def test_assigned_private_graphs_use_logical_storage(no_delegation, monkeypatch, name):
    mine = getattr(fnx, name)()
    _, theirs = _pair(name)
    mine.add_edge("native", "decoy", weight=1000)
    mine._node = theirs._node
    if theirs.is_directed():
        mine._succ, mine._pred = theirs._succ, theirs._pred
    else:
        mine._adj = theirs._adj
    monkeypatch.setattr(fnx, "_raw_louvain_communities", _reject)
    monkeypatch.setattr(community, "_native_louvain_partitions_start", _reject)
    assert list(community.louvain_partitions(mine, seed=6)) == list(_NX_LEVELS(theirs, seed=6))


@pytest.mark.parametrize("mode", ["order", "memberships"])
def test_simple_subclass_constructors_control_working_nodes(no_delegation, mode):
    def build(base):
        class Preset(base):
            def __init__(self):
                super().__init__()
                self.add_nodes_from([0, 1])
                if mode == "memberships":
                    for node in self:
                        self.nodes[node]["nodes"] = {100}

        graph = Preset()
        if mode == "order":
            graph.remove_node(0)
        graph.add_edge(1, 0, weight=1)
        return graph

    mine, theirs = build(fnx.Graph), build(nx.Graph)
    assert list(community.louvain_partitions(mine, seed=1)) == list(_NX_LEVELS(theirs, seed=1))


def test_owned_levels_suspend_graph_work_rng_and_set_updates(owned):
    mine, theirs = fnx.Graph(), nx.Graph()
    topology = nx.barabasi_albert_graph(80, 3, seed=11)
    rng = random.Random(42)
    edges = [(u, v, {"weight": Fraction(rng.randrange(1, 50), 7)}) for u, v in topology.edges]
    for graph in (mine, theirs):
        graph.add_edges_from(edges)
    left, right = random.Random(3), random.Random(3)
    actual = community.louvain_partitions(mine, seed=left)
    expected = _NX_LEVELS(theirs, seed=right)
    assert left.getstate() == right.getstate()
    for graph in (mine, theirs):
        graph.add_edge(0, 79, weight=Fraction(35))
    first, first_expected = next(actual), next(expected)
    assert first == first_expected
    assert left.random() == right.random()
    first[0].clear()
    first_expected[0].clear()
    for graph in (mine, theirs):
        graph.add_edge("ignored", 79, weight="not a number")
    rest, rest_expected = list(actual), list(expected)
    assert rest == rest_expected
    assert rest  # the mutations and interleaved draw reach a subsequent level
    assert left.getstate() == right.getstate()


@pytest.mark.parametrize("max_level", [None, True, 1, 2, 0, -1, 1.5, "2", 2**65])
def test_level_limits_and_seed_error_timing(owned, max_level):
    mine, theirs = _pair(make_weight=lambda n: Fraction(n, 5))
    left, right = random.Random(3), random.Random(3)
    actual = _outcome(lambda: community.louvain_communities(mine, max_level=max_level, seed=left))
    expected = _outcome(lambda: _NX_COMMUNITIES(theirs, max_level=max_level, seed=right))
    assert actual == expected
    assert left.getstate() == right.getstate()
    # Invalid seed validation precedes even invalid level-limit validation.
    assert _outcome(lambda: community.louvain_communities(mine, max_level=max_level, seed="bad")) == (
        _outcome(lambda: _NX_COMMUNITIES(theirs, max_level=max_level, seed="bad"))
    )


@pytest.mark.parametrize("nodes", [[], [0], [0, 1, 2]])
def test_edgeless_graph_never_shuffles(no_delegation, nodes):
    mine, theirs = fnx.Graph(), nx.Graph()
    mine.add_nodes_from(nodes)
    theirs.add_nodes_from(nodes)
    left, right = random.Random(3), random.Random(3)
    left.shuffle = right.shuffle = _reject
    assert list(community.louvain_partitions(mine, seed=left)) == list(_NX_LEVELS(theirs, seed=right))


def test_partition_seed_validation_is_eager_but_weight_errors_are_lazy(owned):
    mine, theirs = _pair()
    mine[0][next(iter(mine[0]))]["weight"] = "bad"
    theirs[0][next(iter(theirs[0]))]["weight"] = "bad"
    actual = community.louvain_partitions(mine, seed=1)
    expected = _NX_LEVELS(theirs, seed=1)
    assert _outcome(lambda: next(actual)) == _outcome(lambda: next(expected))
    assert _outcome(lambda: community.louvain_partitions(mine, seed="bad")) == (
        _outcome(lambda: _NX_LEVELS(theirs, seed="bad"))
    )
