"""Differential + golden parity for lowest-common-ancestor functions.

Covers ``lowest_common_ancestor``, ``all_pairs_lowest_common_ancestor``
(DAG) and ``tree_all_pairs_lowest_common_ancestor`` (tree). The
all-pairs variants had no dedicated test file.

br-r37-c1-i11v4
"""

from __future__ import annotations

import random
from functools import wraps

import pytest
import networkx as nx
import franken_networkx as fnx


def _random_dag(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for v in range(1, n):
        for _ in range(rng.randint(1, 2)):
            u = rng.randint(0, v - 1)
            fg.add_edge(u, v)
            ng.add_edge(u, v)
    return fg, ng, n


def _random_tree(seed):
    rng = random.Random(seed * 7 + 1)
    n = rng.randint(3, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for v in range(1, n):
        u = rng.randint(0, v - 1)
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng, n


def _norm(pairs):
    return {tuple(sorted(k)): v for k, v in dict(pairs).items()}


@pytest.mark.parametrize("seed", range(50))
def test_all_pairs_lowest_common_ancestor_matches_networkx(seed):
    fg, ng, _ = _random_dag(seed)
    assert _norm(fnx.all_pairs_lowest_common_ancestor(fg)) == _norm(
        nx.all_pairs_lowest_common_ancestor(ng)
    )


@pytest.mark.parametrize("seed", range(40))
def test_all_pairs_with_explicit_pairs_matches_networkx(seed):
    fg, ng, n = _random_dag(seed)
    rng = random.Random(seed * 11 + 3)
    pairs = [(rng.randrange(n), rng.randrange(n)) for _ in range(4)]
    assert dict(fnx.all_pairs_lowest_common_ancestor(fg, pairs=pairs)) == dict(
        nx.all_pairs_lowest_common_ancestor(ng, pairs=pairs)
    )


@pytest.mark.parametrize("seed", range(40))
def test_tree_all_pairs_lowest_common_ancestor_matches_networkx(seed):
    fg, ng, _ = _random_tree(seed)
    assert _norm(fnx.tree_all_pairs_lowest_common_ancestor(fg)) == _norm(
        nx.tree_all_pairs_lowest_common_ancestor(ng)
    )


def test_lca_goldens():
    # Binary tree: 0 -> {1, 2}, 1 -> {3, 4}.
    g = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
    assert fnx.lowest_common_ancestor(g, 3, 4) == 1
    assert fnx.lowest_common_ancestor(g, 3, 2) == 0
    assert fnx.lowest_common_ancestor(g, 0, 4) == 0


def test_cyclic_graph_raises_like_networkx():
    fg = fnx.DiGraph([(0, 1), (1, 0)])
    ng = nx.DiGraph([(0, 1), (1, 0)])
    with pytest.raises(nx.NetworkXError):
        dict(fnx.all_pairs_lowest_common_ancestor(fg))
    with pytest.raises(nx.NetworkXError):
        dict(nx.all_pairs_lowest_common_ancestor(ng))


_LCA_BACKEND_NAMES = (
    "lowest_common_ancestor",
    "all_pairs_lowest_common_ancestor",
    "tree_all_pairs_lowest_common_ancestor",
)


def _lca_backend_arguments(name):
    if name == "lowest_common_ancestor":
        return {"node1": 3, "node2": 4}
    arguments = {"pairs": [(3, 4), (2, 4), (0, 0)]}
    if name == "tree_all_pairs_lowest_common_ancestor":
        arguments["root"] = 0
    return arguments


@pytest.mark.parametrize("name", _LCA_BACKEND_NAMES)
def test_lca_backend_is_advertised(name):
    import fnx_backend_info
    from franken_networkx.backend import BackendInterface, get_backend_info

    graph = nx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
    assert name in get_backend_info()["functions"]
    assert name in fnx_backend_info.get_backend_info()["functions"]
    assert BackendInterface.can_run(name, (graph,), _lca_backend_arguments(name))


@pytest.mark.parametrize("name", _LCA_BACKEND_NAMES)
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("view", [False, True])
def test_lca_backend_preserves_original_graph_and_results(
    name, cached, automatic, view, monkeypatch
):
    from franken_networkx import backend as backend_module

    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
    subject = nx.subgraph_view(graph) if view else graph
    arguments = _lca_backend_arguments(name)
    expected = getattr(nx, name)(subject, backend="networkx", **arguments)
    if name != "lowest_common_ancestor":
        expected = list(expected)
    if cached:
        nx.relabel_nodes(subject, {}, backend="franken_networkx")
        assert subject.__networkx_cache__["backends"]["franken_networkx"]

    implementation = backend_module._SUPPORTED_ALGORITHMS[name]
    inputs = []

    @wraps(implementation)
    def observed(*args, **kwargs):
        inputs.append(args[0] if args else kwargs["G"])
        return implementation(*args, **kwargs)

    monkeypatch.setitem(backend_module._SUPPORTED_ALGORITHMS, name, observed)
    if automatic:
        monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
        actual = getattr(nx, name)(G=subject, **arguments)
    else:
        actual = getattr(nx, name)(G=subject, backend="franken_networkx", **arguments)
    if name != "lowest_common_ancestor":
        actual = list(actual)
    assert actual == expected
    assert len(inputs) == 1 and inputs[0] is subject
    assert not subject.__networkx_cache__.get("backends")


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("view", [False, True])
@pytest.mark.parametrize("mutation", ["join", "disconnect"])
def test_lca_backend_dag_queries_read_changes_between_pairs(
    cached, view, mutation, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.DiGraph([(0, 1), (1, 2), (1, 3), (4, 5)])
        if mutation == "disconnect":
            graph.add_edge(4, 0)
        subject = nx.subgraph_view(graph) if view else graph
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(subject, {}, backend=backend)
            assert subject.__networkx_cache__["backends"][backend]
        results = nx.all_pairs_lowest_common_ancestor(
            subject, pairs=[(1, 1), (2, 5)], backend=backend
        )
        first = next(results)
        if mutation == "join":
            graph.add_edge(4, 0)
        else:
            graph.remove_edge(4, 0)
        return first, list(results)

    expected = run("networkx")
    assert expected[0] == ((1, 1), 1)
    assert expected[1] == ([((2, 5), 4)] if mutation == "join" else [])
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("view", [False, True])
def test_lca_backend_tree_reads_changes_before_first_advance(cached, view, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.DiGraph([(0, 1), (0, 2), (1, 3)])
        subject = nx.subgraph_view(graph) if view else graph
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(subject, {}, backend=backend)
        results = nx.tree_all_pairs_lowest_common_ancestor(
            subject, root=0, backend=backend
        )
        graph.add_edge(1, 4)
        return list(results)

    expected = run("networkx")
    assert any(4 in pair for pair, _ in expected)
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("name", _LCA_BACKEND_NAMES)
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("error_type", [LookupError, nx.NetworkXNotImplemented])
def test_lca_backend_preserves_live_reader_exceptions(name, cached, error_type, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
        events = []

        def reader(node):
            events.append(node)
            raise error_type("LCA traversal provider stopped")

        if name == "tree_all_pairs_lowest_common_ancestor":
            graph.neighbors = reader
        else:
            graph.predecessors = reader
        with pytest.raises(error_type) as error:
            result = getattr(nx, name)(
                graph, backend=backend, **_lca_backend_arguments(name)
            )
            if name != "lowest_common_ancestor":
                list(result)
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return error.value.args, events

    expected = run("networkx")
    assert expected[0] == ("LCA traversal provider stopped",)
    assert expected[1]
    assert run("franken_networkx") == expected


@pytest.mark.parametrize("name", _LCA_BACKEND_NAMES)
@pytest.mark.parametrize("kind", ["undirected", "empty", "cycle", "missing"])
def test_lca_backend_keeps_validation_and_exception_timing(name, kind):
    def run(backend):
        graph = nx.Graph() if kind == "undirected" else nx.DiGraph()
        if kind != "empty":
            graph.add_edges_from([(0, 1), (0, 2), (1, 3), (1, 4)])
        if kind == "cycle":
            graph.add_edge(3, 0)
        arguments = _lca_backend_arguments(name)
        if kind == "cycle" and name == "tree_all_pairs_lowest_common_ancestor":
            # With an explicit root, NetworkX deliberately skips cycle/source
            # validation. Inferred-root mode must reject a graph with no root.
            arguments.pop("root")
        if kind == "missing":
            if name == "lowest_common_ancestor":
                arguments["node1"] = "absent"
            elif name == "tree_all_pairs_lowest_common_ancestor":
                arguments["root"] = "absent"
            else:
                arguments["pairs"] = [(3, "absent")]
        phase = "call"
        try:
            result = getattr(nx, name)(graph, backend=backend, **arguments)
            if name != "lowest_common_ancestor":
                phase = "advance"
                list(result)
        except Exception as error:
            return phase, type(error), error.args
        raise AssertionError("invalid LCA input unexpectedly succeeded")

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("cached", [False, True])
def test_lca_backend_preserves_default_identity(cached, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.DiGraph()
    graph.add_nodes_from(["left", "right"])
    if cached:
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
    default = object()
    assert nx.lowest_common_ancestor(
        graph, "left", "right", default=default, backend="franken_networkx"
    ) is default


@pytest.mark.parametrize(
    "name", ["all_pairs_lowest_common_ancestor", "tree_all_pairs_lowest_common_ancestor"]
)
def test_lca_backend_close_discards_conversions_without_more_reads(name, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.DiGraph([(0, 1), (0, 2), (1, 3), (1, 4)])
    results = getattr(nx, name)(graph, backend="franken_networkx")
    next(results)
    nx.relabel_nodes(graph, {}, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]

    def refuse(*args, **kwargs):
        raise AssertionError("closing an LCA iterator resumed graph traversal")

    graph.predecessors = refuse
    graph.successors = refuse
    results.close()
    assert not graph.__networkx_cache__.get("backends")
