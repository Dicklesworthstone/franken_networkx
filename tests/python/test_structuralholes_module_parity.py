"""Parity coverage for the ``franken_networkx.structuralholes`` module."""

from __future__ import annotations

import importlib
import inspect

import franken_networkx as fnx
import networkx as nx
import pytest


PUBLIC_FUNCTIONS = ("constraint", "local_constraint", "effective_size")


def _build_pair():
    weighted_edges = [(0, 1, 2), (1, 2, 3), (2, 0, 5), (2, 3, 7)]
    fnx_graph = fnx.Graph()
    nx_graph = nx.Graph()
    for u, v, weight in weighted_edges:
        fnx_graph.add_edge(u, v, weight=weight)
        nx_graph.add_edge(u, v, weight=weight)
    return fnx_graph, nx_graph


def test_direct_structuralholes_module_import_exposes_wrappers():
    module = importlib.import_module("franken_networkx.structuralholes")

    for name in PUBLIC_FUNCTIONS:
        assert callable(getattr(module, name))


def test_algorithms_structuralholes_import_routes_to_same_module():
    direct = importlib.import_module("franken_networkx.structuralholes")
    via_algorithms = importlib.import_module(
        "franken_networkx.algorithms.structuralholes"
    )

    assert via_algorithms is direct
    assert fnx.algorithms.structuralholes is direct


def test_structuralholes_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    expected = importlib.import_module("networkx.algorithms.structuralholes")

    assert set(module.__all__) == set(expected.__all__)


def test_structuralholes_function_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    expected = importlib.import_module("networkx.algorithms.structuralholes")

    for name in PUBLIC_FUNCTIONS:
        actual_repr = str(inspect.signature(getattr(module, name)))
        expected_repr = str(inspect.signature(getattr(expected, name)))
        if actual_repr != expected_repr:
            raise AssertionError(
                f"{name} signature mismatch: "
                f"{actual_repr} != {expected_repr}"
            )


def test_structuralholes_measures_match_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph, nx_graph = _build_pair()

    assert module.constraint(fnx_graph) == nx.constraint(nx_graph)
    assert module.constraint(fnx_graph, weight="weight") == nx.constraint(
        nx_graph, weight="weight"
    )
    assert module.local_constraint(fnx_graph, 0, 1, weight="weight") == (
        nx.local_constraint(nx_graph, 0, 1, weight="weight")
    )
    assert module.effective_size(fnx_graph) == nx.effective_size(nx_graph)
    assert module.effective_size(fnx_graph, weight="weight") == nx.effective_size(
        nx_graph, weight="weight"
    )


def test_local_constraint_digraph_missing_u_message_matches_networkx():
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph = fnx.DiGraph([(0, 1)])
    nx_graph = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXError) as fnx_exc:
        module.local_constraint(fnx_graph, "missing", 1)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.local_constraint(nx_graph, "missing", 1)
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("graph_factory", [fnx.Graph, fnx.DiGraph])
def test_local_constraint_missing_v_matches_networkx_zero(graph_factory):
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph = graph_factory([(0, 1)])
    nx_graph = getattr(nx, graph_factory.__name__)([(0, 1)])

    assert module.local_constraint(fnx_graph, 1, "missing") == nx.local_constraint(
        nx_graph, 1, "missing"
    )


def test_structuralholes_rejects_backend_kwargs_like_networkx_dispatch():
    module = importlib.import_module("franken_networkx.structuralholes")
    fnx_graph, _ = _build_pair()

    with pytest.raises(TypeError):
        module.constraint(fnx_graph, unsupported=True)


# br-r37-c1-14vcl: on a multigraph networkx's two routes read parallel edges
# differently - the nodes=None matrix path sums them, the mutual_weight loop
# (local_constraint, nodes=...) counts each edge once via G[u][v].get(weight, 1)
# on the keydict. fnx read an unweighted undirected multigraph as a simple graph
# and summed parallel weights in the loop, so both routes disagreed.
def _multigraphs(lib, cls):
    import random

    karate = getattr(lib, cls)(lib.karate_club_graph())
    karate.add_edge(0, 1, weight=7)
    graphs = [karate]
    rng = random.Random(5)
    for _ in range(3):
        graph = getattr(lib, cls)()
        for _ in range(60):
            u, v = rng.randrange(15), rng.randrange(15)
            if u != v:
                graph.add_edge(u, v, weight=rng.randint(1, 5))
        graphs.append(graph)
    return graphs


def _same(a, b):
    import math

    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    return abs(a - b) <= 1e-9


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph", "Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_structuralholes_with_parallel_edges_match_networkx(cls, weight):
    for graph_nx, graph_fnx in zip(_multigraphs(nx, cls), _multigraphs(fnx, cls)):
        for nodes in (None, [0, 1, 2, 3]):
            for name in ("constraint", "effective_size"):
                expected = getattr(nx, name)(graph_nx, nodes=nodes, weight=weight)
                actual = getattr(fnx, name)(graph_fnx, nodes=nodes, weight=weight)
                assert _same(actual, expected), (name, nodes)
        for u, v in [(0, 1), (1, 2), (3, 0)]:
            if u in graph_nx and v in graph_nx:
                expected = nx.local_constraint(graph_nx, u, v, weight=weight)
                actual = fnx.local_constraint(graph_fnx, u, v, weight=weight)
                assert _same(actual, expected), ("local_constraint", u, v)


def _structural_graph(module, cls, weight="cost", value_type=int):
    graph = getattr(module, cls)()
    graph.add_nodes_from(range(7))
    graph.add_edges_from(
        (u, v, {weight: value_type(value)})
        for u, v, value in [
            (0, 0, 2), (0, 1, 3), (1, 0, 5), (0, 2, 7),
            (1, 2, 2), (2, 3, 1), (3, 1, 4), (4, 4, 6),
        ]
    )
    return graph


def _observable_result(call):
    """Retain result order, numeric types and public error wording."""
    import math

    try:
        answer = call()
    except Exception as error:
        return ("error", type(error).__name__, str(error))
    items = answer.items() if isinstance(answer, dict) else [(None, answer)]
    return [
        (node, type(value), "nan" if isinstance(value, float) and math.isnan(value) else value)
        for node, value in items
    ]


def _forbid_networkx_fallback(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("structural-hole analysis must use the owned implementation")

    monkeypatch.setattr(fnx, "_call_networkx_submodule_for_parity", fail)
    monkeypatch.setattr(fnx, "_call_networkx_for_parity", fail)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "cost", 0, ("cost",)])
@pytest.mark.parametrize("container", [list, tuple, iter])
@pytest.mark.parametrize("name", ["constraint", "effective_size"])
def test_owned_structural_holes_match_scalar_contract(cls, weight, container, name, monkeypatch):
    ng = _structural_graph(nx, cls, weight)
    fg = _structural_graph(fnx, cls, weight)
    requested = [3, 0, 4, 6, 1, 3]
    expected = _observable_result(
        lambda: getattr(nx, name)(ng, nodes=container(requested), weight=weight)
    )
    _forbid_networkx_fallback(monkeypatch)
    actual = _observable_result(
        lambda: getattr(fnx, name)(fg, nodes=container(requested), weight=weight)
    )
    assert actual == expected


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "cost"])
@pytest.mark.parametrize("name", ["constraint", "effective_size"])
@pytest.mark.parametrize("missing", ["numpy", "scipy"])
def test_owned_structural_holes_without_optional_dependencies(
    cls, weight, name, missing, monkeypatch
):
    import builtins

    fg = _structural_graph(fnx, cls, weight)
    ng = _structural_graph(nx, cls, weight)
    original_import = builtins.__import__

    def unavailable(module, *args, **kwargs):
        if module == missing or module.startswith(missing + "."):
            raise ImportError("optional dependency unavailable")
        return original_import(module, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    expected = _observable_result(lambda: getattr(nx, name)(ng, weight=weight))
    _forbid_networkx_fallback(monkeypatch)
    assert _observable_result(lambda: getattr(fnx, name)(fg, weight=weight)) == expected


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["constraint", "effective_size"])
@pytest.mark.parametrize("requested", [[], ["missing"], [[]]])
def test_empty_and_invalid_structural_hole_subsets(cls, name, requested):
    fg, ng = getattr(fnx, cls)(), getattr(nx, cls)()
    assert _observable_result(
        lambda: getattr(fnx, name)(fg, nodes=requested)
    ) == _observable_result(lambda: getattr(nx, name)(ng, nodes=requested))


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("kind", ["fraction", "decimal", "huge_integer"])
@pytest.mark.parametrize("name", PUBLIC_FUNCTIONS)
def test_structural_holes_preserve_exact_numeric_domains(cls, kind, name, monkeypatch):
    from decimal import Decimal
    from fractions import Fraction

    value_type = {
        "fraction": lambda value: Fraction(value, 7),
        "decimal": Decimal,
        "huge_integer": lambda value: value * 10**400,
    }[kind]
    fg = _structural_graph(fnx, cls, value_type=value_type)
    ng = _structural_graph(nx, cls, value_type=value_type)
    args = (0, 1) if name == "local_constraint" else ()
    kwargs = {"weight": "cost"}
    if name != "local_constraint":
        kwargs["nodes"] = [3, 0, 1, 4, 6]
    expected = _observable_result(lambda: getattr(nx, name)(ng, *args, **kwargs))
    _forbid_networkx_fallback(monkeypatch)
    assert _observable_result(lambda: getattr(fnx, name)(fg, *args, **kwargs)) == expected


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["constraint", "effective_size"])
@pytest.mark.parametrize("backend", [False, True])
@pytest.mark.parametrize("warm_cache", [False, True])
def test_structural_holes_consume_live_subset_iterators(cls, name, backend, warm_cache):
    def run(module, dispatched):
        graph = _structural_graph(module, cls)
        if dispatched and warm_cache:
            nx.shortest_path_length(graph, 0, 3, backend="franken_networkx")

        def nodes():
            yield 0
            graph.add_edge(0, 5, cost=11)
            yield 1
            graph.remove_edge(1, 2)
            yield 0
            yield 3

        options = {"backend": "franken_networkx"} if dispatched else {}
        return _observable_result(
            lambda: getattr(module, name)(graph, nodes=nodes(), weight="cost", **options)
        )

    expected = run(nx, False)
    assert run(nx if backend else fnx, backend) == expected


@pytest.mark.parametrize("name", PUBLIC_FUNCTIONS)
@pytest.mark.parametrize("backend", [False, True])
def test_structural_holes_keep_numeric_callbacks_live(name, backend):
    def run(module, dispatched):
        graph = module.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 2), (1, 0, 3), (0, 2, 4), (2, 1, 5)])
        events = []

        class MutatingWeight(float):
            def __add__(self, other):
                events.append(("add", float(other)))
                if len(events) == 1:
                    graph[0][2]["weight"] = 13
                return float(self) + other

            def __radd__(self, other):
                events.append(("radd", float(other)))
                if len(events) == 1:
                    graph[0][2]["weight"] = 13
                return other + float(self)

        graph[0][1]["weight"] = MutatingWeight(2)
        args = (0, 1) if name == "local_constraint" else ()
        kwargs = {"weight": "weight"}
        if name != "local_constraint":
            kwargs["nodes"] = [0, 1]
        if dispatched:
            kwargs["backend"] = "franken_networkx"
        result = _observable_result(lambda: getattr(module, name)(graph, *args, **kwargs))
        return result, events, graph[0][2]["weight"]

    expected = run(nx, False)
    assert expected[1], "the fixture must exercise observable numeric operations"
    assert run(nx if backend else fnx, backend) == expected


@pytest.mark.parametrize("backend", [False, True])
def test_effective_size_preserves_caller_ego_graph_providers(backend):
    def run(dispatched):
        events = []

        class GraphWithSize(nx.Graph):
            def subgraph(self, nodes):
                events.append(("subgraph", tuple(nodes)))
                return super().subgraph(nodes)

            def size(self, weight=None):
                events.append(("size", tuple(self)))
                return 2 * super().size(weight=weight)

        graph = GraphWithSize([(0, 1), (1, 2), (2, 0), (2, 3)])
        if dispatched is None:
            answer = nx.effective_size(graph, nodes=[0, 2])
        elif dispatched:
            answer = nx.effective_size(graph, nodes=[0, 2], backend="franken_networkx")
        else:
            answer = fnx.effective_size(graph, nodes=[0, 2])
        return answer, events

    expected = run(None)
    assert expected[0][0] == 0, "the subclass size must affect the ego formula"
    assert run(backend) == expected
