"""Differential + golden parity for the core link-prediction family.

``jaccard_coefficient``, ``adamic_adar_index``,
``resource_allocation_index`` and ``preferential_attachment`` each return
a lazy iterator of ``(u, v, score)`` triples — over a supplied ``ebunch``
of node pairs, or over all non-edges by default. None had a dedicated
test file.

This locks fnx against the real upstream networkx with:

* differential parity (including *exact* iteration order) for every
  function, over random graphs, with both the default ebunch and an
  explicit one,
* hand-computed score goldens on a small fixed graph,
* the lazy-iterator contract, and
* the directed / multigraph ``NetworkXNotImplemented`` contract.

br-r37-c1-swpt8
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx

import franken_networkx as fnx


_FUNCS = [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
    "preferential_attachment",
]


def _pair(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng, n


def _materialize(it):
    # Preserve order; round scores so float reps compare cleanly.
    return [(u, v, round(s, 9)) for u, v, s in it]


# ---------------------------------------------------------------------------
# Differential parity (exact iteration order).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize("seed", range(40))
def test_link_prediction_default_ebunch_matches_networkx(fn, seed):
    fg, ng, _ = _pair(seed)
    fr = _materialize(getattr(fnx, fn)(fg))
    nr = _materialize(getattr(nx, fn)(ng))
    assert fr == nr, f"{fn} seed={seed}: order/value mismatch"


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize("seed", range(40))
def test_link_prediction_explicit_ebunch_matches_networkx(fn, seed):
    fg, ng, n = _pair(seed)
    rng = random.Random(seed * 13 + 1)
    all_pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    rng.shuffle(all_pairs)
    ebunch = all_pairs[: min(6, len(all_pairs))]
    fr = _materialize(getattr(fnx, fn)(fg, ebunch))
    nr = _materialize(getattr(nx, fn)(ng, ebunch))
    assert fr == nr, f"{fn} seed={seed} ebunch={ebunch}: mismatch"


# ---------------------------------------------------------------------------
# Hand-computed goldens on a fixed graph: triangle 0-1-2 with tail 2-3.
# ---------------------------------------------------------------------------


def _golden_graph():
    return fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3)])


def test_jaccard_golden():
    # pair (0, 3): common neighbors = {2}; union of neighbors = {1, 2} → 1/2.
    [(u, v, score)] = list(fnx.jaccard_coefficient(_golden_graph(), [(0, 3)]))
    assert (u, v) == (0, 3)
    assert score == pytest.approx(0.5)


def test_resource_allocation_golden():
    # pair (0, 3): common neighbor 2 with degree 3 → 1/3.
    [(_, _, score)] = list(fnx.resource_allocation_index(_golden_graph(), [(0, 3)]))
    assert score == pytest.approx(1 / 3)


def test_adamic_adar_golden():
    # pair (0, 3): common neighbor 2 with degree 3 → 1/log(3).
    [(_, _, score)] = list(fnx.adamic_adar_index(_golden_graph(), [(0, 3)]))
    assert score == pytest.approx(1 / math.log(3))


def test_preferential_attachment_golden():
    # pair (0, 3): deg(0) = 2, deg(3) = 1 → 2.
    [(_, _, score)] = list(fnx.preferential_attachment(_golden_graph(), [(0, 3)]))
    assert score == 2


# ---------------------------------------------------------------------------
# Iterator contract and error contracts.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", _FUNCS)
def test_link_prediction_returns_lazy_iterator(fn):
    it = getattr(fnx, fn)(_golden_graph())
    assert iter(it) is iter(it)
    assert not isinstance(it, list)


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.DiGraph, nx.DiGraph), (fnx.MultiGraph, nx.MultiGraph)],
)
def test_link_prediction_rejects_directed_and_multigraph(fn, fnx_cls, nx_cls):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        list(getattr(fnx, fn)(fg))
    with pytest.raises(nx.NetworkXNotImplemented):
        list(getattr(nx, fn)(ng))


_LIVE_ROUTES = ["native", "networkx-input", "submodule", "backend", "warm-backend"]
_COMMUNITY_FUNCS = [
    "cn_soundarajan_hopcroft", "ra_index_soundarajan_hopcroft", "within_inter_cluster",
]
_LIVE_FUNCS = _FUNCS + _COMMUNITY_FUNCS + ["common_neighbor_centrality"]


def _live_graph(module):
    graph = module.Graph()
    graph.add_nodes_from(range(6), community=0)
    graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])
    return graph


def _live_input_module(route):
    return fnx if route in ("native", "submodule") else nx


def _live_prediction(route, name, graph, pairs, **kwargs):
    if route == "warm-backend":
        nx.relabel_nodes(graph, {}, backend="franken_networkx")
        assert graph.__networkx_cache__["backends"]["franken_networkx"]
    if route in ("backend", "warm-backend"):
        return getattr(nx, name)(graph, pairs, backend="franken_networkx", **kwargs)
    if route == "submodule":
        return getattr(fnx.link_prediction, name)(graph, pairs, **kwargs)
    return getattr(fnx, name)(graph, pairs, **kwargs)


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
@pytest.mark.parametrize("before_first", [False, True])
def test_link_prediction_observes_topology_at_each_score(
    name, route, before_first, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 2)]
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = [] if before_first else [next(scores)]
        graph.add_edges_from([(0, 5), (2, 5)])
        return first + list(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
@pytest.mark.parametrize("change", ["replace", "append", "remove", "reverse", "inner"])
def test_link_prediction_retains_the_callers_pair_list(name, route, change, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 3), (0, 5)]
        if change == "inner":
            pairs = [list(pair) for pair in pairs]
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = next(scores)
        if change == "replace":
            pairs[1] = (1, 4)
        elif change == "append":
            pairs.append((1, 4))
        elif change == "remove":
            pairs.pop(0)
        elif change == "inner":
            pairs[1][:] = [1, 4]
        else:
            pairs.reverse()
        return [first] + list(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_link_prediction_one_shot_pairs_remain_consumed(name, route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = _live_graph(_live_input_module(route))
    pairs = iter([(0, 2), (0, 3)])
    assert list(_live_prediction(route, name, graph, pairs)) == []
    assert list(getattr(nx, name)(_live_graph(nx), iter([(0, 2), (0, 3)]))) == []


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_link_prediction_pair_provider_keeps_validation_and_score_timing(
    name, route, monkeypatch
):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        events = []

        class Pairs:
            passes = 0

            def __iter__(self):
                self.passes += 1
                generation = self.passes
                events.append(("iter", generation))

                def walk():
                    for index in range(2):
                        events.append(("pair", generation, index))
                        if generation == 1 and index == 1:
                            # Mutation during eager endpoint validation must
                            # reach the first score, even after a warm cache.
                            graph.add_edge(0, 5)
                        if generation == 2 and index == 1:
                            graph.add_edge(2, 5)
                        yield (0, 2)

                return walk()

        pairs = Pairs()
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        observations = [("call", list(events))]
        for score in scores:
            observations.append((score, list(events)))
        return observations

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", ["native", "networkx-input", "warm-backend"])
def test_link_prediction_reads_dynamic_view_filters(name, route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        base = _live_graph(module)
        visible = set(base)
        graph = module.subgraph_view(base, filter_node=lambda node: node in visible)
        pairs = [(0, 2), (0, 2)]
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = next(scores)
        visible.remove(1)
        return first, next(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_link_prediction_removed_endpoint_raises_at_its_score(name, route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 5)]
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = next(scores)
        graph.remove_node(5)
        try:
            next(scores)
        except Exception as error:
            return first, type(error), error.args
        pytest.fail("removed endpoint did not raise")

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _LIVE_FUNCS)
def test_link_prediction_backend_closing_discards_callback_conversions(name, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = _live_graph(nx)
    scores = _live_prediction("backend", name, graph, [(0, 2), (0, 2)])
    next(scores)
    nx.dijkstra_path_length(graph, 0, 2, backend="franken_networkx")
    assert graph.__networkx_cache__["backends"]["franken_networkx"]
    scores.close()
    assert not graph.__networkx_cache__.get("backends")


@pytest.mark.parametrize("name", _LIVE_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
@pytest.mark.parametrize("before_first", [False, True])
def test_link_prediction_default_pairs_remain_live(name, route, before_first, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        # Populate the ordinary non-edge cache before creating a live scorer.
        list(module.non_edges(graph))
        scores = (
            getattr(nx, name)(graph, backend="networkx")
            if reference else _live_prediction(route, name, graph, None)
        )
        first = [] if before_first else [next(scores)]
        graph.add_edges_from([(0, 5), (2, 5)])
        return first + list(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _COMMUNITY_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
@pytest.mark.parametrize("node", [0, 1])
def test_link_prediction_community_changes_between_scores(name, route, node, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 2)]
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = next(scores)
        graph.nodes[node]["community"] = 7
        return first, next(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _COMMUNITY_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_link_prediction_missing_community_raises_at_its_score(name, route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = _live_graph(_live_input_module(route))
    scores = _live_prediction(route, name, graph, [(0, 2), (0, 2)])
    next(scores)
    del graph.nodes[1]["community"]
    with pytest.raises(
        nx.NetworkXAlgorithmError, match="No community information available for Node 1"
    ):
        next(scores)


@pytest.mark.parametrize("name", _COMMUNITY_FUNCS)
@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_link_prediction_community_endpoints_are_validated_eagerly(name, route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = _live_graph(_live_input_module(route))
    with pytest.raises(nx.NodeNotFound, match="Node 99 not in G"):
        _live_prediction(route, name, graph, [(0, 99)])


@pytest.mark.parametrize("name", _COMMUNITY_FUNCS)
@pytest.mark.parametrize("route", ["native", "networkx-input", "submodule"])
def test_link_prediction_invalid_community_key_preserves_type_error(name, route):
    graph = _live_graph(_live_input_module(route))
    scores = _live_prediction(route, name, graph, [(0, 2)], community=[])
    with pytest.raises(TypeError, match="unhashable type"):
        next(scores)


@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_common_neighbor_community_bonus_sums_equality_results(route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    class NumericEquality:
        def __eq__(self, other):
            return 2

    def run(module, reference):
        graph = _live_graph(module)
        for node in graph:
            graph.nodes[node]["community"] = NumericEquality()
        name = "cn_soundarajan_hopcroft"
        scores = (
            getattr(nx, name)(graph, [(0, 2)], backend="networkx")
            if reference else _live_prediction(route, name, graph, [(0, 2)])
        )
        return list(scores)

    assert run(_live_input_module(route), False) == run(nx, True) == [(0, 2, 3)]


@pytest.mark.parametrize("route", _LIVE_ROUTES)
@pytest.mark.parametrize("before_first", [False, True])
def test_common_neighbor_centrality_reads_live_graph_size(route, before_first, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 2)]
        name = "common_neighbor_centrality"
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = [] if before_first else [next(scores)]
        graph.add_node(6)
        return first + list(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_common_neighbor_centrality_preserves_call_time_distances(route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 2)]
        name = "common_neighbor_centrality"
        scores = (
            getattr(nx, name)(graph, pairs, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs)
        )
        first = next(scores)
        graph.add_edge(0, 2)
        return first, next(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("route", _LIVE_ROUTES)
def test_common_neighbor_centrality_alpha_one_remains_live(route, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(module, reference):
        graph = _live_graph(module)
        pairs = [(0, 2), (0, 2)]
        name = "common_neighbor_centrality"
        scores = (
            getattr(nx, name)(graph, pairs, alpha=1, backend="networkx")
            if reference else _live_prediction(route, name, graph, pairs, alpha=1)
        )
        first = next(scores)
        graph.add_edges_from([(0, 5), (2, 5)])
        return first, next(scores)

    assert run(_live_input_module(route), False) == run(nx, True)


@pytest.mark.parametrize("name", _FUNCS)
def test_explicit_link_prediction_admission_visits_only_queried_rows(name, monkeypatch):
    graph = fnx.Graph()
    graph.add_nodes_from(range(10000))
    graph.add_edges_from([(0, 1), (1, 2), (1, 3)])
    reference = nx.Graph()
    reference.add_nodes_from(range(10000))
    reference.add_edges_from([(0, 1), (1, 2), (1, 3)])
    if name == "preferential_attachment":
        graph.add_edges_from((0, node) for node in range(4, 10000))
        reference.add_edges_from((0, node) for node in range(4, 10000))
    pairs = [(0, 2), (0, 3)]

    def forbidden_node_scan(self):
        raise AssertionError("a small explicit query scanned all graph nodes")

    monkeypatch.setattr(fnx.Graph, "_native_node_keys", forbidden_node_scan)
    scope = fnx._link_prediction_native_scores.__globals__
    raw_neighbors = scope["_GRAPH_NEIGHBORS"]
    visited = []

    def read_row(owner, node):
        visited.append(node)
        return raw_neighbors(owner, node)

    monkeypatch.setitem(scope, "_GRAPH_NEIGHBORS", read_row)
    raw_name = {
        "jaccard_coefficient": "_raw_link_pred_jaccard_counts",
        "preferential_attachment": "_raw_preferential_attachment",
        "resource_allocation_index": "_raw_link_pred_common_neighbor_degrees",
        "adamic_adar_index": "_raw_link_pred_common_neighbor_degrees",
    }[name]
    raw_scores = scope[raw_name]
    batches = []

    def score_batch(owner, values):
        batches.append(tuple(values))
        return raw_scores(owner, values)

    monkeypatch.setitem(scope, raw_name, score_batch)
    assert list(getattr(fnx, name)(graph, pairs)) == list(getattr(nx, name)(reference, pairs))
    assert visited == ([] if name == "preferential_attachment" else [0, 2, 3])
    assert batches == [tuple(pairs)]


@pytest.mark.parametrize("name", _FUNCS)
def test_link_prediction_does_not_hash_a_later_pairs_custom_neighbors(name):
    events = []

    class Neighbor:
        def __hash__(self):
            events.append("hash")
            return 1234567

    neighbor = Neighbor()
    graph = fnx.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (3, neighbor), (4, neighbor)])
    scores = getattr(fnx, name)(graph, [(0, 2), (3, 4)])
    events.clear()
    next(scores)
    assert events == []
    next(scores)
    if name != "preferential_attachment":
        assert events
