"""Differential parity for less-tested centrality parameter combinations.

Default-parameter centrality is covered elsewhere; this exercises the
non-default knobs that are a common source of subtle bugs: ``endpoints``,
``weight``, ``normalized``, ``distance`` and ``wf_improved``.

br-r37-c1-2pzqb
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_weighted(seed, directed):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (directed or u < v) and rng.random() < 0.5:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    ok = nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
    return (fg, ng) if ok else None


def _close(a, b, tol=1e-7):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol, rel=1e-6)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_betweenness_parameter_variants(directed, seed):
    pair = _connected_weighted(seed, directed)
    if pair is None:
        pytest.skip("not connected")
    fg, ng = pair
    _close(fnx.betweenness_centrality(fg, endpoints=True),
           nx.betweenness_centrality(ng, endpoints=True))
    _close(fnx.betweenness_centrality(fg, weight="weight"),
           nx.betweenness_centrality(ng, weight="weight"))
    _close(fnx.betweenness_centrality(fg, normalized=False),
           nx.betweenness_centrality(ng, normalized=False))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_closeness_parameter_variants(directed, seed):
    pair = _connected_weighted(seed, directed)
    if pair is None:
        pytest.skip("not connected")
    fg, ng = pair
    _close(fnx.closeness_centrality(fg, distance="weight"),
           nx.closeness_centrality(ng, distance="weight"))
    _close(fnx.closeness_centrality(fg, wf_improved=False),
           nx.closeness_centrality(ng, wf_improved=False))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_edge_betweenness_variants(directed, seed):
    pair = _connected_weighted(seed, directed)
    if pair is None:
        pytest.skip("not connected")
    fg, ng = pair

    def _norm(d):
        return {(tuple(sorted(k)) if not directed else k): v for k, v in d.items()}

    _close(_norm(fnx.edge_betweenness_centrality(fg)),
           _norm(nx.edge_betweenness_centrality(ng)))
    _close(_norm(fnx.edge_betweenness_centrality(fg, weight="weight")),
           _norm(nx.edge_betweenness_centrality(ng, weight="weight")))


_TRUTH_OPTIONS = [
    ("betweenness_centrality", "normalized"),
    ("betweenness_centrality", "endpoints"),
    ("edge_betweenness_centrality", "normalized"),
]


@pytest.mark.parametrize("name,parameter", _TRUTH_OPTIONS)
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("route", ["native", "foreign", "backend", "cached-backend"])
@pytest.mark.parametrize("action", ["edge", "node", "toggle", "raise"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("k", [None, 2])
def test_betweenness_truth_providers_preserve_live_order(
    name, parameter, graph_type, route, action, weight, k, monkeypatch
):
    """Option truth belongs to each accumulation/rescale on the live graph."""
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def outcome(actual):
        module = fnx if actual and route == "native" else nx
        graph = getattr(module, graph_type)()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (2, 3, 1)])
        if actual and route == "cached-backend":
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
        calls = []

        class Truth:
            def __bool__(self):
                calls.append((tuple(graph), tuple(graph.edges())))
                if action == "raise":
                    raise LookupError("betweenness option callback")
                if action == "edge" and len(calls) == 1:
                    graph.add_edge(0, 3, weight=0.25)
                if action == "node" and len(calls) == 1:
                    graph.add_node(4)
                return len(calls) % 2 == 0 if action == "toggle" else True

        options = {parameter: Truth(), "weight": weight, "k": k, "seed": 7}
        if actual and route in ("backend", "cached-backend"):
            call = getattr(nx, name)
            options["backend"] = "franken_networkx"
        elif actual:
            call = getattr(fnx, name)
        else:
            call = getattr(nx, name)
            options["backend"] = "networkx"
        try:
            scores, failure = call(graph, **options), None
        except Exception as exc:
            scores, failure = None, (type(exc), exc.args)
        return scores, failure, calls, list(graph.edges(data=True)), list(graph)

    expected = outcome(False)
    actual = outcome(True)
    assert expected[2], "the oracle must exercise the option provider"
    assert actual[1:] == expected[1:]
    if expected[0] is not None:
        assert list(actual[0]) == list(expected[0])
        assert actual[0] == pytest.approx(expected[0], rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("name", ["betweenness_centrality", "edge_betweenness_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("count", [0, 1])
@pytest.mark.parametrize("route", ["native", "foreign", "backend", "cached-backend"])
def test_betweenness_small_graphs_preserve_normalization_boundary(
    name, graph_type, count, route, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    calls = []

    class UnusedTruth:
        def __bool__(self):
            calls.append("normalized")
            raise LookupError("small-graph normalization callback")

    def outcome(call, graph, **options):
        calls.clear()
        try:
            scores, failure = call(graph, normalized=UnusedTruth(), **options), None
        except Exception as exc:
            scores, failure = None, (type(exc), exc.args)
        return scores, failure, tuple(calls)

    oracle = getattr(nx, graph_type)()
    oracle.add_nodes_from(range(count))
    # Older NetworkX versions read normalized even when current versions
    # return early. Preserve the installed oracle's boundary in either case.
    expected = outcome(getattr(nx, name), oracle, backend="networkx")
    module = fnx if route == "native" else nx
    graph = getattr(module, graph_type)()
    graph.add_nodes_from(range(count))
    if route == "cached-backend":
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    if route in ("backend", "cached-backend"):
        actual = outcome(getattr(nx, name), graph, backend="franken_networkx")
    else:
        actual = outcome(getattr(fnx, name), graph)
    assert actual == expected


@pytest.mark.parametrize("name,parameter", _TRUTH_OPTIONS)
def test_betweenness_truth_admission_does_not_evaluate_providers(name, parameter):
    class UnreadTruth:
        def __bool__(self):
            raise AssertionError("admission cannot read option truth")

    for graph in (fnx.path_graph(4), nx.path_graph(4)):
        assert fnx._betweenness_uses_live_python_rows(
            graph, None, **{parameter: UnreadTruth()}
        )


@pytest.mark.parametrize("name", ["betweenness_centrality", "edge_betweenness_centrality"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("k", [None, 2])
def test_betweenness_plain_boolean_options_keep_native_route(
    name, graph_type, weight, k, monkeypatch
):
    def unexpected_owned_route(*args, **kwargs):
        raise AssertionError("ordinary Boolean options must retain native Brandes")

    monkeypatch.setattr(fnx, "_betweenness_centrality_inproc", unexpected_owned_route)
    monkeypatch.setattr(fnx, "_edge_betweenness_centrality_inproc", unexpected_owned_route)
    graphs = [getattr(module, graph_type)() for module in (nx, fnx)]
    for graph in graphs:
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 2), (2, 3, 1)])
    options = {"normalized": False, "weight": weight, "k": k, "seed": 7}
    if name == "betweenness_centrality":
        options["endpoints"] = True
    expected = getattr(nx, name)(graphs[0], **options, backend="networkx")
    actual = getattr(fnx, name)(graphs[1], **options)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("endpoints,expected", [(False, 2 / 3), (True, 1 / 3)])
def test_legacy_betweenness_rescale_reads_endpoint_truth_once(endpoints, expected):
    """NetworkX 3.4's normalization branch has one endpoint truth boundary."""
    calls = []

    class Endpoints:
        def __bool__(self):
            calls.append("endpoints")
            if len(calls) != 1:
                raise AssertionError("legacy normalization re-read endpoint truth")
            return endpoints

    scores = {"center": 4.0}
    actual = fnx._rescale_betweenness_legacy_local(
        scores, 4, normalized=True, directed=False, endpoints=Endpoints()
    )
    assert calls == ["endpoints"]
    assert actual is scores
    assert actual["center"] == pytest.approx(expected)
