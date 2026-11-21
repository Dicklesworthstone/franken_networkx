"""Differential + golden parity for matching predicates.

Covers ``is_matching``, ``is_maximal_matching`` and
``is_perfect_matching`` (boolean validators over a candidate matching),
plus ``min_weight_matching`` total-weight optimality. The predicates had
little/no dedicated coverage.

br-r37-c1-hjiql
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.5):
    rng = random.Random(seed)
    n = 2 * rng.randint(2, 5)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


@pytest.mark.parametrize("fn", ["is_matching", "is_maximal_matching", "is_perfect_matching"])
@pytest.mark.parametrize("seed", range(50))
def test_predicate_matches_networkx_on_real_matching(fn, seed):
    fg, ng, _ = _pair(seed)
    matching = nx.maximal_matching(ng)  # a genuine matching
    assert getattr(fnx, fn)(fg, matching) == getattr(nx, fn)(ng, matching)


@pytest.mark.parametrize("seed", range(40))
def test_is_matching_rejects_invalid_like_networkx(seed):
    fg, ng, n = _pair(seed)
    rng = random.Random(seed * 11 + 1)
    # A random set of node pairs — usually NOT a valid matching (shared nodes).
    candidate = {
        (u, v)
        for u in range(n)
        for v in range(u + 1, n)
        if rng.random() < 0.3
    }
    assert fnx.is_matching(fg, candidate) == nx.is_matching(ng, candidate)


def test_matching_predicate_goldens():
    c4 = fnx.cycle_graph(4)
    assert fnx.is_perfect_matching(c4, {(0, 1), (2, 3)})
    assert not fnx.is_matching(c4, {(0, 1), (1, 2)})        # shares node 1
    assert not fnx.is_maximal_matching(fnx.path_graph(4), {(0, 1)})  # (2,3) free
    # dict form is accepted by is_matching.
    assert fnx.is_matching(c4, {0: 1, 1: 0, 2: 3, 3: 2})


@pytest.mark.parametrize("seed", range(30))
def test_min_weight_matching_total_weight_matches_networkx(seed):
    rng = random.Random(seed + 7)
    n = 2 * rng.randint(2, 5)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.5:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fm = fnx.min_weight_matching(fg)
    nm = nx.min_weight_matching(ng)
    # Optimal matching is not unique; total weight is the invariant.
    fw = sum(fg[u][v]["weight"] for u, v in fm)
    nw = sum(ng[u][v]["weight"] for u, v in nm)
    assert fw == nw


_PREDICATES = ("is_matching", "is_maximal_matching", "is_perfect_matching")
_GRAPH_KINDS = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")


def _predicate_outcome(function, graph, matching, **kwargs):
    try:
        return "value", function(graph, matching, **kwargs)
    except Exception as exc:  # Both the exception class and arguments are observable.
        return "error", type(exc), exc.args


def _prime_matching_conversion(graph):
    nx.relabel_nodes(graph, {}, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]


@pytest.mark.parametrize("name", _PREDICATES)
@pytest.mark.parametrize("graph_kind", _GRAPH_KINDS)
@pytest.mark.parametrize("call_kind", ["foreign", "view", "backend", "cached_backend"])
@pytest.mark.parametrize("candidate_kind", ["iterator", "mapping"])
def test_matching_predicates_consume_live_candidates(
    name, graph_kind, call_kind, candidate_kind, monkeypatch
):
    """Candidate providers can add an edge after a conversion would snapshot it."""
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(actual):
        module = fnx if actual and call_kind == "view" else nx
        source = getattr(module, graph_kind)()
        source.add_nodes_from(range(4))
        source.add_edge(0, 1)
        graph = module.subgraph_view(source) if call_kind == "view" else source
        if actual and call_kind == "cached_backend":
            _prime_matching_conversion(graph)
        events = []

        def entries():
            events.append("first")
            source.add_edge(2, 3)
            yield 2, 3
            events.append("second")
            yield 0, 1
            events.append("done")

        class Matching(dict):
            def items(self):
                return entries()

        candidate = Matching() if candidate_kind == "mapping" else entries()
        backend_call = actual and call_kind.endswith("backend")
        function = getattr(nx if not actual or backend_call else fnx, name)
        kwargs = {"backend": "franken_networkx" if actual else "networkx"} if (
            backend_call or not actual
        ) else {}
        result = _predicate_outcome(function, graph, candidate, **kwargs)
        if backend_call:
            assert not graph.__networkx_cache__.get("backends")
        return result, events, list(source.edges)

    expected = run(False)
    actual = run(True)
    assert actual == expected
    assert actual[1] == ["first", "second", "done"]


@pytest.mark.parametrize("name", _PREDICATES)
@pytest.mark.parametrize("graph_kind", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("call_kind", ["direct", "backend", "cached_backend"])
def test_matching_predicates_keep_asymmetric_filtered_edges(
    name, graph_kind, call_kind, monkeypatch
):
    """A filtered undirected row need not expose the reciprocal orientation."""
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    outcomes = []
    for actual in (False, True):
        module = fnx if actual and call_kind == "direct" else nx
        source = getattr(module, graph_kind)([(0, 1)])
        asymmetric = False
        graph = module.subgraph_view(
            source, filter_edge=lambda u, v, *key: not asymmetric or u < v
        )
        if actual and call_kind == "cached_backend":
            # Cache a symmetric view that native conversion can represent,
            # then change the live filter without invalidating that snapshot.
            _prime_matching_conversion(graph)
        asymmetric = True
        function = getattr(fnx if actual and call_kind == "direct" else nx, name)
        kwargs = {} if actual and call_kind == "direct" else {
            "backend": "franken_networkx" if actual else "networkx"
        }
        outcomes.append(_predicate_outcome(function, graph, [(1, 0)], **kwargs))
    assert outcomes == [("value", False), ("value", False)]


@pytest.mark.parametrize("name", _PREDICATES)
@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("backend_call", [False, True], ids=["direct", "backend"])
def test_matching_predicates_use_the_original_has_edge_provider(
    name, cached, backend_call, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    source = nx.Graph([(0, 1)])
    if cached:
        _prime_matching_conversion(source)
    calls = []

    def has_edge(u, v):
        calls.append((u, v))
        return False

    source.has_edge = has_edge
    function = getattr(nx if backend_call else fnx.matching, name)
    kwargs = {"backend": "franken_networkx"} if backend_call else {}
    # Keyword binding must preserve the same source as the positional calls.
    assert function(G=source, matching=[(0, 1)], **kwargs) is False
    assert calls == [(0, 1)]


@pytest.mark.parametrize("name", _PREDICATES)
@pytest.mark.parametrize("matching", [[], [(0,)], {0: 0}])
@pytest.mark.parametrize("backend_call", [False, True], ids=["direct", "backend"])
def test_matching_validation_precedes_unrelated_graph_reads(name, matching, backend_call):
    def build():
        graph = nx.Graph()
        graph.add_nodes_from([0, 1])

        def unexpected():
            raise AssertionError("matching validation read graph kind")

        graph.is_directed = graph.is_multigraph = unexpected
        return graph

    expected = _predicate_outcome(getattr(nx, name), build(), matching, backend="networkx")
    function = getattr(nx if backend_call else fnx, name)
    kwargs = {"backend": "franken_networkx"} if backend_call else {}
    assert _predicate_outcome(function, build(), matching, **kwargs) == expected


@pytest.mark.parametrize("name", _PREDICATES)
@pytest.mark.parametrize("error_type", [ValueError, nx.NetworkXNotImplemented])
@pytest.mark.parametrize("cached", [False, True])
def test_matching_backend_keeps_provider_errors_and_invalidates_nested_caches(
    name, error_type, cached, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    source = nx.Graph([(0, 1, {"weight": 1})])
    if cached:
        _prime_matching_conversion(source)
    failure = error_type("matching provider stopped")
    calls = []

    def candidate():
        calls.append("entered")
        _prime_matching_conversion(source)
        source[0][1]["weight"] = 9
        yield from ()
        raise failure

    with pytest.raises(error_type, match="^matching provider stopped$") as caught:
        getattr(nx, name)(source, candidate(), backend="franken_networkx")

    assert caught.value is failure
    assert calls == ["entered"]
    assert source[0][1]["weight"] == 9
    assert not source.__networkx_cache__.get("backends")
