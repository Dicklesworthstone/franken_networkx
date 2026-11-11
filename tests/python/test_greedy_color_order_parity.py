"""Greedy coloring order, owned strategy routing, and live provider contracts.

Bead br-r37-c1-vevfq. fnx.greedy_color returned dict keys in arbitrary
Rust internal order. nx returns them in the order the strategy
processed them (e.g. for the default 'largest_first': nodes sorted
by degree descending). Drop-in code that iterates the result broke.

The owned driver keeps the strategy's graph and color dictionary live while
preserving the native largest-first route for ordinary simple graphs.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_str_graph(lib):
    g = lib.Graph()
    for u, v in [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e")]:
        g.add_edge(u, v)
    return g


@needs_nx
def test_default_strategy_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_default_strategy_values_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert dict(f) == dict(n)


@needs_nx
def test_saturation_largest_first_keys_match_networkx():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = fnx.greedy_color(g, strategy="saturation_largest_first")
    n = nx.greedy_color(gx, strategy="saturation_largest_first")
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_int_path_graph_largest_first():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_complete_graph_largest_first():
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_callable_strategy_still_works():
    """Custom callable strategies retain their chosen node order."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    strategy = lambda G, colors: list(G.nodes())  # noqa: E731
    f = fnx.greedy_color(g, strategy=strategy)
    n = nx.greedy_color(gx, strategy=strategy)
    assert list(f.keys()) == list(n.keys())


@needs_nx
def test_empty_graph_returns_empty_dict():
    g = fnx.Graph()
    gx = nx.Graph()
    f = fnx.greedy_color(g)
    n = nx.greedy_color(gx)
    assert f == n == {}


def _outcome(call):
    try:
        return ("colors", list(call().items()))
    except Exception as exc:
        return ("error", type(exc).__name__, exc.args)


@needs_nx
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("strategy", [
    "largest_first", "smallest_last", "independent_set", "connected_sequential",
    "connected_sequential_bfs", "connected_sequential_dfs", "saturation_largest_first",
    "DSATUR", "random_sequential",
])
def test_named_strategies_are_owned_and_match_networkx(monkeypatch, graph_type, strategy):
    graphs = [getattr(module, graph_type)() for module in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from([4, 1, 5, 0, 3, 2, 6])
        graph.add_edges_from([(2, 1), (0, 2), (1, 4), (3, 0), (4, 5), (5, 3), (2, 1)])

    def no_delegation(*args, **kwargs):
        raise AssertionError("greedy coloring delegated to NetworkX")

    saved_random_state = random.getstate()
    try:
        random.seed(721)
        expected = _outcome(lambda: nx.greedy_color(graphs[1], strategy=strategy))
        monkeypatch.setattr(fnx, "_greedy_color_structural_nx", no_delegation)
        monkeypatch.setattr(nx, "greedy_color", no_delegation)
        random.seed(721)
        actual = _outcome(lambda: fnx.greedy_color(graphs[0], strategy=strategy))
    finally:
        random.setstate(saved_random_state)
    assert actual == expected


def _live_strategy_observations(color, graph):
    graph.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 1)])
    graph.add_node(3)
    payload = []
    graph.graph["payload"] = payload
    graph.nodes[0]["payload"] = payload
    trace = []
    passed_colors = []

    def strategy(received, colors):
        assert received is graph
        assert received.graph["payload"] is payload
        assert received.nodes[0]["payload"] is payload
        passed_colors.append(colors)
        trace.append(list(colors.items()))
        yield 0
        trace.append(list(colors.items()))
        received.add_edge(0, 2)
        received.add_edge(2, 0)
        received.graph["payload"].append("edge-added")
        yield 2
        trace.append(list(colors.items()))
        yield 1
        received.add_edge(0, 4)
        received.add_edge(4, 0)
        yield 4
        trace.append(list(colors.items()))

    result = color(graph, strategy=strategy)
    assert result is passed_colors[0]
    assert graph.has_edge(0, 2) and graph.has_edge(0, 4)
    assert result == {0: 0, 2: 1, 1: 2, 4: 1}
    return list(result.items()), trace, payload


@needs_nx
@pytest.mark.parametrize("input_module", ["fnx", "nx"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_callable_strategy_keeps_original_graph_and_shared_colors(input_module, graph_type):
    module = fnx if input_module == "fnx" else nx
    actual = _live_strategy_observations(fnx.greedy_color, getattr(module, graph_type)())
    expected = _live_strategy_observations(nx.greedy_color, getattr(nx, graph_type)())
    assert actual == expected


@needs_nx
@pytest.mark.parametrize("input_module", ["fnx", "nx"])
@pytest.mark.parametrize("view_kind", ["subgraph", "reverse"])
def test_callable_strategy_keeps_original_views(input_module, view_kind):
    module = fnx if input_module == "fnx" else nx
    graph = module.DiGraph([(0, 1), (1, 2), (2, 0), (2, 3)])
    view = graph.subgraph([0, 1, 2]) if view_kind == "subgraph" else graph.reverse(copy=False)
    observed = []

    def strategy(received, colors):
        assert received is view
        observed.append(colors)
        received.nodes[0]["called"] = True
        yield from received

    result = fnx.greedy_color(view, strategy=strategy)
    assert observed == [result]
    assert observed[0] is result
    assert graph.nodes[0]["called"] is True
    expected = nx.greedy_color(nx.DiGraph(view), strategy=lambda G, colors: iter(G))
    assert list(result.items()) == list(expected.items())


@needs_nx
@pytest.mark.parametrize("after_yield", [False, True])
def test_strategy_exceptions_keep_identity_and_prior_graph_writes(after_yield):
    graph = fnx.path_graph(3)
    failure = RuntimeError("strategy failed")
    held_colors = []

    def strategy(received, colors):
        assert received is graph
        held_colors.append(colors)
        received.graph["before_error"] = True
        if after_yield:
            yield 0
        raise failure

    with pytest.raises(RuntimeError) as caught:
        fnx.greedy_color(graph, strategy=strategy)
    assert caught.value is failure
    assert graph.graph["before_error"] is True
    assert held_colors == [{0: 0} if after_yield else {}]


@needs_nx
@pytest.mark.parametrize("strategy", [[], {}, None, 7, "missing"])
@pytest.mark.parametrize("empty", [False, True])
def test_strategy_validation_matches_networkx(strategy, empty):
    fg = fnx.Graph() if empty else fnx.path_graph(2)
    ng = nx.Graph() if empty else nx.path_graph(2)
    assert _outcome(lambda: fnx.greedy_color(fg, strategy=strategy)) == _outcome(
        lambda: nx.greedy_color(ng, strategy=strategy)
    )


@needs_nx
def test_unhashable_callable_matches_networkx_validation():
    class UnhashableStrategy:
        __hash__ = None

        def __call__(self, G, colors):
            return iter(G)

    strategy = UnhashableStrategy()
    assert _outcome(lambda: fnx.greedy_color(fnx.path_graph(2), strategy)) == _outcome(
        lambda: nx.greedy_color(nx.path_graph(2), strategy)
    )
    assert fnx.greedy_color(fnx.Graph(), strategy) == nx.greedy_color(nx.Graph(), strategy) == {}


@needs_nx
@pytest.mark.parametrize("input_module", ["fnx", "nx"])
def test_largest_first_keeps_assigned_degree_provider(input_module):
    module = fnx if input_module == "fnx" else nx
    graph = module.path_graph(3)
    expected_graph = nx.path_graph(3)
    degrees = {0: 2, 1: 4, 2: 6}
    graph.degree = degrees.__getitem__
    expected_graph.degree = degrees.__getitem__
    result = fnx.greedy_color(graph)
    expected = nx.greedy_color(expected_graph)
    assert list(result.items()) == list(expected.items()) == [(2, 0), (1, 1), (0, 0)]


@needs_nx
@pytest.mark.parametrize("input_module", ["fnx", "nx"])
def test_largest_first_keeps_subclass_adjacency_reader(input_module):
    module = fnx if input_module == "fnx" else nx

    class ReadGraph(module.Graph):
        def __getitem__(self, node):
            self.graph["reads"].append(node)
            return super().__getitem__(node)

    graph = ReadGraph([(0, 1), (1, 2)])
    graph.graph["reads"] = []
    result = fnx.greedy_color(graph)
    assert list(result.items()) == [(1, 0), (0, 1), (2, 1)]
    assert graph.graph["reads"] == [1, 0, 2]


@needs_nx
def test_named_strategy_override_runs_on_original_graph(monkeypatch):
    graph = fnx.path_graph(3)
    held_colors = []

    def replacement(received, colors):
        assert received is graph
        held_colors.append(colors)
        return [2, 1, 0]

    monkeypatch.setitem(fnx.coloring.STRATEGIES, "largest_first", replacement)
    monkeypatch.setattr(fnx.coloring, "strategy_largest_first", replacement)
    result = fnx.greedy_color(graph)
    assert list(result.items()) == [(2, 0), (1, 1), (0, 0)]
    assert held_colors == [result]
