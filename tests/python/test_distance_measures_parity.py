"""Differential + golden parity for the distance-measures family.

Covers ``eccentricity``, ``diameter``, ``radius``, ``center``,
``periphery`` and ``barycenter`` — the eccentricity-derived graph
invariants. None had a dedicated test file.

This locks fnx against the real upstream networkx with:

* differential parity across random connected graphs — undirected and
  (strongly-connected) directed, unweighted and weighted,
* hand-computed goldens (path, cycle, star, complete graphs), and
* the disconnected-graph ``NetworkXError`` contract.

Set-valued results (``center``, ``periphery``, ``barycenter``) are
compared as sets; the scalar/dict results are compared exactly (with a
float tolerance for the weighted cases).

br-r37-c1-8k1rt
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_pair(seed, directed=False, weighted=False, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fnx_cls, nx_cls = (
        (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    )
    for _ in range(300):
        fg = fnx_cls()
        ng = nx_cls()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u == v:
                    continue
                if (directed or u < v) and rng.random() < p:
                    if weighted:
                        w = round(rng.uniform(1, 5), 2)
                        fg.add_edge(u, v, weight=w)
                        ng.add_edge(u, v, weight=w)
                    else:
                        fg.add_edge(u, v)
                        ng.add_edge(u, v)
        connected = (
            nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
        )
        if connected:
            return fg, ng, n
        p = min(0.95, p + 0.03)
    return None


# ---------------------------------------------------------------------------
# Differential parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_distance_measures_match_networkx(directed, weighted, seed):
    pair = _connected_pair(seed, directed=directed, weighted=weighted)
    if pair is None:
        pytest.skip("could not sample a connected graph")
    fg, ng, _ = pair
    kwargs = {"weight": "weight"} if weighted else {}

    fecc = fnx.eccentricity(fg, **kwargs)
    necc = nx.eccentricity(ng, **kwargs)
    assert set(fecc) == set(necc)
    for k in necc:
        assert fecc[k] == pytest.approx(necc[k], abs=1e-9)

    assert fnx.diameter(fg, **kwargs) == pytest.approx(nx.diameter(ng, **kwargs), abs=1e-9)
    assert fnx.radius(fg, **kwargs) == pytest.approx(nx.radius(ng, **kwargs), abs=1e-9)
    assert set(fnx.center(fg, **kwargs)) == set(nx.center(ng, **kwargs))
    assert set(fnx.periphery(fg, **kwargs)) == set(nx.periphery(ng, **kwargs))


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_barycenter_matches_networkx(weighted, seed):
    pair = _connected_pair(seed, directed=False, weighted=weighted)
    if pair is None:
        pytest.skip("could not sample a connected graph")
    fg, ng, _ = pair
    kwargs = {"weight": "weight"} if weighted else {}
    assert set(fnx.barycenter(fg, **kwargs)) == set(nx.barycenter(ng, **kwargs))


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_path_graph_goldens():
    p5 = fnx.path_graph(5)
    assert fnx.diameter(p5) == 4
    assert fnx.radius(p5) == 2
    assert set(fnx.center(p5)) == {2}
    assert set(fnx.periphery(p5)) == {0, 4}


def test_cycle_and_complete_goldens():
    assert fnx.diameter(fnx.cycle_graph(6)) == 3
    assert fnx.diameter(fnx.complete_graph(5)) == 1
    assert fnx.radius(fnx.complete_graph(5)) == 1


def test_star_graph_goldens():
    s4 = fnx.star_graph(4)  # center 0 with 4 leaves
    assert fnx.diameter(s4) == 2
    assert fnx.radius(s4) == 1
    assert set(fnx.center(s4)) == {0}


# ---------------------------------------------------------------------------
# Disconnected error contract.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", ["diameter", "radius"])
def test_distance_measures_reject_disconnected_like_networkx(fn):
    fg = fnx.Graph([(0, 1)])
    fg.add_node(2)
    ng = nx.Graph([(0, 1)])
    ng.add_node(2)
    with pytest.raises(nx.NetworkXError):
        getattr(fnx, fn)(fg)
    with pytest.raises(nx.NetworkXError):
        getattr(nx, fn)(ng)


@pytest.mark.parametrize("fn", ["eccentricity", "diameter", "radius", "center", "periphery"])
def test_unreachable_negative_cycle_reports_the_first_sources_error(fn):
    """networkx checks each source as it computes it: node 0 cannot reach the
    other component, so "not strongly connected" is raised before any Dijkstra
    meets the negative cycle there. Draining all pairs first raised that
    cycle's ValueError instead."""
    outcomes = {}
    for name, lib in (("nx", nx), ("fnx", fnx)):
        graph = lib.DiGraph()
        for i in range(12):
            graph.add_edge(i, (i + 1) % 12, weight=1.5)
        graph.add_edge(30, 31, weight=-7.0)
        graph.add_edge(31, 30, weight=3.0)
        try:
            getattr(lib, fn)(graph, weight="weight")
            outcomes[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - which error is the contract
            outcomes[name] = (type(exc).__name__, str(exc))
    assert outcomes["fnx"] == outcomes["nx"]
    assert outcomes["nx"][0] == "NetworkXError"


@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("n", [0, 1, 3], ids=["null", "singleton", "nonempty"])
@pytest.mark.parametrize("v", [None, 0, 99, "missing", [], [0, "missing"], [[0]]],
                         ids=["all", "node", "missing-integer", "missing", "empty-bunch", "mixed-bunch", "unhashable"])
@pytest.mark.parametrize("sp_kind", ["none", "valid", "invalid"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_eccentricity_actual_oracle_exception_precedence(class_name, n, v, sp_kind, mode):
    """hhj5p.6: 3.7 rejects null graphs before examining either v or sp."""
    graphs = []
    for lib in (fnx, nx):
        graph = getattr(lib, class_name)()
        graph.add_nodes_from(range(n))
        if n > 1:
            graph.add_edges_from((i, (i + 1) % n) for i in range(n))
        graphs.append(graph)
    sp = None
    if sp_kind == "valid":
        sp = dict(nx.all_pairs_shortest_path_length(graphs[1]))
    elif sp_kind == "invalid":
        sp = {0: None}
    outcomes = []
    with fnx.compatibility_mode(mode):
        for lib, graph in zip((fnx, nx), graphs):
            try:
                value = lib.eccentricity(graph, v=v, sp=sp)
            except Exception as exc:
                outcomes.append(("error", type(exc).__name__, str(exc)))
            else:
                outcomes.append(("return", type(value).__name__, value))
    assert outcomes[0] == outcomes[1], (nx.__version__, class_name, n, v, sp_kind, mode, outcomes)


# br-r37-c1-mub4s: warm subset/scalar queries must reuse the topology-bound
# snapshot without losing nbunch validation, ordering, or cache invalidation.
def _eccentricity_cache_pair(class_name):
    labels = [0, "leaf", (2, "tuple"), b"end", frozenset({4})]
    graphs = [getattr(lib, class_name)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_nodes_from(labels)
        graph.add_edges_from(zip(labels, labels[1:]), weight=5)
    return (*graphs, labels)


def _profile_eccentricity(graph, **kwargs):
    """Observe real calls; do not replace either the public or native route."""
    import cProfile
    import pstats

    profiler = cProfile.Profile()
    result = profiler.runcall(fnx.eccentricity, graph, **kwargs)
    calls = sum(record[1] for key, record in pstats.Stats(profiler).stats.items()
                if key[2] == "shortest_path_length")
    return result, calls


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("selection", ["integer", "tuple", "subset", "iterator", "empty", "all"])
def test_eccentricity_warm_selection_reuses_snapshot(class_name, mode, selection):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    with fnx.compatibility_mode(mode):
        assert fnx.eccentricity(fg) == nx.eccentricity(ng)

        def choose():
            if selection == "integer":
                return labels[0]
            if selection == "tuple":
                return labels[2]
            if selection in ("subset", "iterator"):
                nodes = [labels[-1], labels[0], labels[-1], "missing"]
                return iter(nodes) if selection == "iterator" else nodes
            return [] if selection == "empty" else None

        actual, calls = _profile_eccentricity(fg, v=choose())
        expected = nx.eccentricity(ng, v=choose())
        assert type(actual) is type(expected)
        assert actual == expected
        if isinstance(actual, dict):
            assert list(actual.items()) == list(expected.items())
            actual["caller-only"] = -999
            fresh = fnx.eccentricity(fg, v=choose())
            assert list(fresh.items()) == list(expected.items())
            assert "caller-only" not in fnx.eccentricity(fg)
        assert calls == 0, "warm eccentricity recomputed shortest paths"


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("bad_v", [99, "missing", [[0]]])
def test_eccentricity_warm_selection_keeps_validation(class_name, mode, bad_v):
    fg, ng, _ = _eccentricity_cache_pair(class_name)
    fnx.eccentricity(fg)
    outcomes = []
    with fnx.compatibility_mode(mode):
        for lib, graph in ((fnx, fg), (nx, ng)):
            try:
                result = lib.eccentricity(graph, v=bad_v)
            except Exception as exc:
                outcomes.append((type(exc).__name__, exc.args, str(exc)))
            else:
                outcomes.append((type(result).__name__, result))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_eccentricity_warm_selection_invalidates_and_rewarms(class_name, mode):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    selected = [labels[-1], labels[0]]
    with fnx.compatibility_mode(mode):
        fnx.eccentricity(fg)
        for operation in ("add-edge", "remove-edge", "add-node", "remove-node"):
            for graph in (fg, ng):
                if operation == "add-edge":
                    graph.add_edge(labels[0], labels[-1])
                elif operation == "remove-edge":
                    graph.remove_edge(labels[0], labels[-1])
                elif operation == "add-node":
                    graph.add_edge(labels[-1], "new-node")
                else:
                    graph.remove_node("new-node")
            actual, calls = _profile_eccentricity(fg, v=selected)
            assert list(actual.items()) == list(nx.eccentricity(ng, v=selected).items())
            assert calls == len(selected), "stale snapshot survived a topology mutation"
            assert fnx.eccentricity(fg) == nx.eccentricity(ng)
            actual, calls = _profile_eccentricity(fg, v=selected)
            assert list(actual.items()) == list(nx.eccentricity(ng, v=selected).items())
            assert calls == 0, "rewarmed snapshot was ignored"


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
def test_eccentricity_selection_mutates_before_snapshot_validation(class_name):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    fnx.eccentricity(fg)

    def changing_bunch(graph):
        graph.add_edge(labels[0], labels[-1])
        yield labels[-1]
        yield labels[0]

    actual, calls = _profile_eccentricity(fg, v=changing_bunch(fg))
    expected = nx.eccentricity(ng, v=changing_bunch(ng))
    assert list(actual.items()) == list(expected.items())
    assert calls == 2, "nbunch mutation reused a stale snapshot"


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("route", ["cold", "weighted", "supplied", "invalid-supplied"])
def test_eccentricity_selection_preserves_noncache_routes(class_name, route):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    if route != "cold":
        assert fnx.eccentricity(fg) == nx.eccentricity(ng)
    kwargs = {"v": [labels[-1], labels[0]]}
    if route == "weighted":
        kwargs["weight"] = "weight"
    elif route == "supplied":
        kwargs["sp"] = {node: {other: 17 for other in labels} for node in labels}
    elif route == "invalid-supplied":
        kwargs["sp"] = {labels[-1]: None}
        for lib, graph in ((fnx, fg), (nx, ng)):
            with pytest.raises(nx.NetworkXError, match='Format of "sp" is invalid.'):
                lib.eccentricity(graph, **kwargs)
        return
    actual, calls = _profile_eccentricity(fg, **kwargs)
    expected = nx.eccentricity(ng, **kwargs)
    assert list(actual.items()) == list(expected.items())
    assert calls == (0 if route == "supplied" else 2)
    if route in ("weighted", "supplied"):
        assert actual != {node: 4 for node in kwargs["v"]}
    if route == "cold":
        # A point query must not pay the cost of populating every node's cache.
        _, calls = _profile_eccentricity(fg, **kwargs)
        assert calls == 2


@pytest.mark.parametrize("class_name", ["DiGraph", "MultiDiGraph"])
def test_eccentricity_warm_directed_selection_keeps_directed_distances(class_name):
    graphs = [getattr(lib, class_name)() for lib in (fnx, nx)]
    for graph in graphs:
        graph.add_edges_from((node, (node + 1) % 5) for node in range(5))
    fg, ng = graphs
    assert fnx.eccentricity(fg) == nx.eccentricity(ng)
    actual, calls = _profile_eccentricity(fg, v=[3, 0])
    assert list(actual.items()) == list(nx.eccentricity(ng, v=[3, 0]).items())
    assert actual == {3: 4, 0: 4}
    assert calls == 2


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("scalar", [False, True])
def test_eccentricity_selection_disconnected_after_warming(class_name, scalar):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    fnx.eccentricity(fg)
    for graph in (fg, ng):
        graph.remove_edge(labels[1], labels[2])
    outcomes = []
    for lib, graph in ((fnx, fg), (nx, ng)):
        with pytest.raises(nx.NetworkXError) as caught:
            lib.eccentricity(graph, v=labels[0] if scalar else [labels[0]])
        outcomes.append((type(caught.value).__name__, caught.value.args, str(caught.value)))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("prime", ["diameter", "radius", "center", "periphery"])
def test_eccentricity_warm_selection_reuses_sibling_snapshot(class_name, prime):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    # Default diameter/radius and tree center intentionally avoid a full
    # eccentricity sweep. On this path, bounding resolves every node exactly
    # and can retain the same complete snapshot without extra searches.
    kwargs = {} if prime == "periphery" else {"usebounds": True}
    assert getattr(fnx, prime)(fg, **kwargs) == getattr(nx, prime)(ng, **kwargs)
    actual, calls = _profile_eccentricity(fg, v=[labels[-1], labels[0]])
    assert list(actual.items()) == list(nx.eccentricity(ng, v=[labels[-1], labels[0]]).items())
    assert calls == 0


@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("prime", ["diameter", "radius", "center"])
def test_eccentricity_selection_after_shortcut_sibling_stays_cold(class_name, prime):
    fg, ng, labels = _eccentricity_cache_pair(class_name)
    assert getattr(fnx, prime)(fg) == getattr(nx, prime)(ng)
    actual, calls = _profile_eccentricity(fg, v=[labels[-1], labels[0]])
    assert list(actual.items()) == list(nx.eccentricity(ng, v=[labels[-1], labels[0]]).items())
    assert calls == 2, "a sibling shortcut started an unnecessary all-node sweep"


_LIVE_DISTANCE_CASES = [
    (class_name, view)
    for class_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")
    for view in ("graph", "subgraph")
] + [("DiGraph", "reverse"), ("MultiDiGraph", "reverse")]


def _live_distance_graph(module, class_name, view):
    base = getattr(module, class_name)()
    base.add_nodes_from((0, 1, 2))
    edges = [(0, 1, 1), (1, 2, 10), (2, 0, 20)]
    if view == "reverse":
        edges = [(v, u, cost) for u, v, cost in edges]
    for u, v, cost in edges:
        if base.is_multigraph():
            base.add_edge(u, v, key="route", weight=cost)
            base.add_edge(u, v, key="parallel", weight=100)
        else:
            base.add_edge(u, v, weight=cost)
    if view == "subgraph":
        base.add_edge(1, "hidden", weight=0)
        base.add_edge("hidden", 2, weight=0)
        graph = base.subgraph([0, 1, 2])
    elif view == "reverse":
        graph = base.reverse(copy=False)
    else:
        graph = base
    for node in base:
        base.nodes[node]["label"] = str(node)
    return graph, base


def _live_distance_weight(graph, calls):
    def weight(u, v, data):
        original = graph.get_edge_data(u, v)
        if graph.is_multigraph():
            assert list(data) == list(original)
            assert all(attrs is original[key] for key, attrs in data.items())
        else:
            assert data is original
        calls.append((u, v, tuple(graph.nodes[n].get("score") for n in graph)))
        if (u, v) == (0, 1):
            edge = graph.get_edge_data(1, 2)
            if graph.is_multigraph():
                edge = edge["route"]
            edge["weight"] = 1
        if graph.is_multigraph():
            return min(attrs["weight"] for attrs in data.values())
        return data["weight"]

    return weight


@pytest.mark.parametrize("class_name, view", _LIVE_DISTANCE_CASES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize(
    "name", ["eccentricity", "diameter", "radius", "center", "periphery", "barycenter"]
)
def test_distance_measures_use_live_weight_callbacks(name, input_module, class_name, view):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph, base = _live_distance_graph(module, class_name, view)
        calls = []
        kwargs = {"weight": _live_distance_weight(graph, calls)}
        if name == "barycenter":
            kwargs["attr"] = "score"
        value = getattr(api, name)(graph, **kwargs)
        if isinstance(value, dict):
            value = list(value.items())
        outcomes.append((value, calls, list(base.nodes(data=True))))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("class_name, view", _LIVE_DISTANCE_CASES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("selection", [0, [2, 0, 2]], ids=["scalar", "repeated-subset"])
def test_eccentricity_selected_sources_use_live_callbacks(
    input_module, class_name, view, selection
):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph, _ = _live_distance_graph(module, class_name, view)
        calls = []
        value = api.eccentricity(
            graph, v=selection, weight=_live_distance_weight(graph, calls)
        )
        if isinstance(value, dict):
            value = list(value.items())
        outcomes.append((value, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("class_name, view", _LIVE_DISTANCE_CASES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("distances", ["unweighted", "weighted", "supplied"])
def test_barycenter_attr_updates_original_graph(input_module, class_name, view, distances):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph, base = _live_distance_graph(module, class_name, view)
        held_attrs = {node: base.nodes[node] for node in base}
        for attrs in held_attrs.values():
            attrs["score"] = "old score"
        graph.__networkx_cache__ = {"stale": "converted graph"}
        kwargs = {"attr": "score"}
        if distances == "weighted":
            kwargs["weight"] = "weight"
        elif distances == "supplied":
            kwargs["sp"] = {
                2: {0: 7, 1: 2, 2: 0},
                0: {0: 0, 1: 4, 2: 6},
                1: {0: 3, 1: 0, 2: 5},
            }
        value = api.barycenter(graph, **kwargs)
        assert all(held_attrs[node] is base.nodes[node] for node in base)
        assert graph.__networkx_cache__ == {}
        outcomes.append((value, list(base.nodes(data=True)), held_attrs))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("class_name, view", _LIVE_DISTANCE_CASES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("failure", ["supplied-distances", "weight-callback"])
def test_barycenter_keeps_completed_attr_writes_on_error(
    input_module, class_name, view, failure
):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph, base = _live_distance_graph(module, class_name, view)
        graph.__networkx_cache__ = {"existing": "conversion"}
        kwargs = {"attr": "score"}
        if failure == "supplied-distances":
            kwargs["sp"] = {0: {0: 0, 1: 2, 2: 3}, 1: {1: 0}}
            error = nx.NetworkXNoPath
        else:
            def weight(u, v, data):
                if "score" in graph.nodes[0]:
                    raise RuntimeError("stop after the first source")
                if graph.is_multigraph():
                    return min(attrs["weight"] for attrs in data.values())
                return data["weight"]

            kwargs["weight"] = weight
            error = RuntimeError
        with pytest.raises(error) as caught:
            api.barycenter(graph, **kwargs)
        assert "score" in base.nodes[0]
        assert "score" not in base.nodes[1]
        assert graph.__networkx_cache__ == {"existing": "conversion"}
        outcomes.append((str(caught.value), list(base.nodes(data=True))))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("name", ["eccentricity", "diameter", "radius", "center", "periphery"])
def test_distance_measures_supplied_values_do_not_call_weight(input_module, name):
    def unused_weight(u, v, data):
        raise AssertionError("precomputed distances must not evaluate weight")

    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph, _ = _live_distance_graph(module, "DiGraph", "subgraph")
        if name == "eccentricity":
            value = api.eccentricity(
                graph,
                v=[2, 0, 2],
                sp={2: {0: 7, 1: 2, 2: 0}, 0: {0: 0, 1: 4, 2: 6}},
                weight=unused_weight,
            )
            value = list(value.items())
        else:
            value = getattr(api, name)(
                graph, e={2: 7, 0: 6, 1: 7}, usebounds=True, weight=unused_weight
            )
        outcomes.append(value)
    assert outcomes[0] == outcomes[1]


_BOUNDED_DISTANCE_MEASURES = ["diameter", "radius", "center", "periphery"]


def _bounds_work_graph(module, family):
    if family == "path":
        template = nx.path_graph(129)
    elif family == "star":
        template = nx.star_graph(128)
    elif family == "binary-tree":
        template = nx.balanced_tree(2, 6)
    elif family == "grid":
        template = nx.grid_2d_graph(10, 10)
    elif family == "small-world":
        template = nx.watts_strogatz_graph(128, 4, 0.1, seed=7)
    elif family == "cycle":
        template = nx.cycle_graph(64)
    else:
        template = nx.complete_graph(24)
    graph = module.Graph()
    graph.add_nodes_from(template)
    graph.add_edges_from(template.edges())
    return graph


@pytest.mark.parametrize("name", _BOUNDED_DISTANCE_MEASURES)
@pytest.mark.parametrize(
    "family", ["path", "star", "binary-tree", "grid", "small-world", "cycle", "complete"]
)
def test_distance_bounds_match_oracle_search_counts(name, family):
    """Measure real searches in both libraries, including worst-case controls."""
    import cProfile
    import pstats

    outcomes = []
    for api in (nx, fnx):
        graph = _bounds_work_graph(api, family)
        calls = 0

        def weight(u, v, data):
            nonlocal calls
            calls += 1
            return 1

        profiler = cProfile.Profile()
        value = profiler.runcall(getattr(api, name), graph, usebounds=True, weight=weight)
        searches = sum(
            record[1] for key, record in pstats.Stats(profiler).stats.items()
            if key[2] in {"_dijkstra_multisource", "_dijkstra_multisource_inproc"}
        )
        assert calls == searches * 2 * graph.number_of_edges()
        assert 0 < searches <= len(graph)
        if family in {"cycle", "complete"}:
            assert searches == len(graph)
        else:
            assert searches < len(graph)
        outcomes.append((value, searches))
    assert outcomes[0] == outcomes[1]


def _bounds_typed_graph(module, class_name, kind):
    graph = getattr(module, class_name)()
    labels = [0, "a", (2,), b"b", frozenset({4}), 5]
    graph.add_nodes_from(labels)
    edges = [(0, 1, 1), (1, 2, 2), (2, 3, 3), (3, 4, 4),
             (4, 5, 2), (5, 0, 1), (1, 5, 1), (2, 4, 1)]
    for u, v, value in edges:
        if kind == "float":
            cost = value / 4
        elif kind == "fraction":
            cost = Fraction(value, 3)
        elif kind == "decimal":
            cost = Decimal(value) / 4
        elif kind == "large-integer":
            cost = 2**60 + value
        elif kind == "zero":
            cost = 0
        else:
            cost = value
        if graph.is_multigraph():
            graph.add_edge(labels[u], labels[v], key="route", distance=cost)
            graph.add_edge(labels[u], labels[v], key="parallel", distance=cost * 3)
        else:
            graph.add_edge(labels[u], labels[v], distance=cost)
    return graph


@pytest.mark.parametrize("name", _BOUNDED_DISTANCE_MEASURES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize(
    "kind", ["unweighted", "integer", "float", "fraction", "decimal", "large-integer", "zero"]
)
def test_distance_bounds_preserve_weight_values(name, input_module, class_name, kind):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph = _bounds_typed_graph(module, class_name, kind)
        value = getattr(api, name)(
            graph, usebounds=True, weight=None if kind == "unweighted" else "distance"
        )
        outcomes.append((type(value), value))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _BOUNDED_DISTANCE_MEASURES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("view", ["graph", "subgraph"])
def test_distance_bounds_preserve_live_callback_order(name, input_module, class_name, view):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph, _ = _live_distance_graph(module, class_name, view)
        calls = []
        value = getattr(api, name)(
            graph, usebounds=True, weight=_live_distance_weight(graph, calls)
        )
        outcomes.append((value, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _BOUNDED_DISTANCE_MEASURES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("case", ["directed", "precomputed", "truthy-flag"])
def test_distance_bounds_respect_bypass_arguments(name, input_module, case):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        class_name = "DiGraph" if case == "directed" else "Graph"
        graph, _ = _live_distance_graph(module, class_name, "graph")
        calls = []
        kwargs = {"usebounds": 1 if case == "truthy-flag" else True}
        if case == "precomputed":
            kwargs["e"] = {2: 7, 0: 6, 1: 7}

            def weight(u, v, data):
                raise AssertionError("a supplied eccentricity must bypass bounding")

        else:
            weight = _live_distance_weight(graph, calls)
        value = getattr(api, name)(graph, weight=weight, **kwargs)
        outcomes.append((value, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _BOUNDED_DISTANCE_MEASURES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
@pytest.mark.parametrize("case", ["empty", "disconnected", "hidden-by-weight"])
def test_distance_bounds_match_errors(name, input_module, class_name, case):
    outcomes = []
    for api, module in ((nx, nx), (fnx, input_module)):
        graph = getattr(module, class_name)()
        kwargs = {"usebounds": True}
        if case == "disconnected":
            graph.add_edge(0, 1)
            graph.add_node(2)
        elif case == "hidden-by-weight":
            graph.add_edges_from([(0, 1), (1, 2), (2, 0)])
            kwargs["weight"] = lambda u, v, data: None
        try:
            value = getattr(api, name)(graph, **kwargs)
        except Exception as exc:
            outcomes.append(("error", type(exc).__name__, exc.args))
        else:
            outcomes.append(("return", value))
    assert outcomes[0][0] == "error"
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _BOUNDED_DISTANCE_MEASURES)
@pytest.mark.parametrize("class_name", ["Graph", "MultiGraph"])
def test_distance_bounds_never_cache_partial_eccentricities(name, class_name):
    template = nx.gnm_random_graph(24, 48, seed=19)
    template.add_edges_from(zip(range(24), range(1, 24)))
    graphs = []
    for module in (nx, fnx):
        graph = getattr(module, class_name)()
        graph.add_nodes_from(template)
        graph.add_edges_from(template.edges())
        graphs.append(graph)
    reference, actual = graphs
    assert getattr(fnx, name)(actual, usebounds=True) == getattr(nx, name)(reference, usebounds=True)
    expected = nx.eccentricity(reference)
    snapshot = fnx._cached_distance_measures_snapshot(actual)
    if snapshot is not None:
        assert dict(snapshot[3]) == expected
    assert fnx.eccentricity(actual) == expected


_WEIGHTED_DISTANCE_MEASURES = ["eccentricity", "diameter", "radius", "center", "periphery"]


def _asymmetric_distance_view(module, class_name, view, numeric):
    graph = getattr(module, class_name)()
    weight = ("cost", 1) if numeric == "decimal" else "cost"
    convert = {
        "integer": int,
        "fraction": lambda value: Fraction(value, 3),
        "decimal": lambda value: Decimal(value) / 4,
        "wide-integer": lambda value: 2**60 * value + 1,
    }[numeric]
    graph.add_nodes_from([0, 1, 2])
    for u, v, value in [(0, 1, 1), (1, 0, 10), (1, 2, 1), (2, 1, 10)]:
        attributes = {weight: convert(value)}
        if graph.is_multigraph():
            graph.add_edges_from([(u, v, "route", attributes),
                                  (u, v, "parallel", {weight: convert(value + 20)})])
        else:
            graph.add_edges_from([(u, v, attributes)])
    if view == "reverse":
        graph = graph.reverse(copy=False)
    result = graph.to_undirected(as_view=True)
    if view == "filtered":
        result = module.subgraph_view(result, filter_node=lambda node: node in {0, 1, 2})
        result = result.copy(as_view=True)
    return result, weight


def _distance_value_and_types(value):
    if isinstance(value, dict):
        return [(node, type(distance), distance) for node, distance in value.items()]
    return type(value), value


@pytest.mark.parametrize("name", _WEIGHTED_DISTANCE_MEASURES)
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("class_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view", ["direct", "reverse", "filtered"])
@pytest.mark.parametrize("numeric", ["integer", "fraction", "decimal", "wide-integer"])
def test_distance_measures_preserve_asymmetric_named_weight_rows(
    name, input_module, class_name, view, numeric
):
    reference, weight = _asymmetric_distance_view(nx, class_name, view, numeric)
    graph, _ = _asymmetric_distance_view(input_module, class_name, view, numeric)
    expected = getattr(nx, name)(reference, weight=weight, backend="networkx")
    actual = getattr(fnx, name)(graph, weight=weight)
    assert _distance_value_and_types(actual) == _distance_value_and_types(expected)


@pytest.mark.parametrize("name", ["diameter", "radius", "center", "periphery"])
@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("class_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view", ["direct", "reverse", "filtered"])
@pytest.mark.parametrize("numeric", ["integer", "decimal"])
def test_distance_bounds_preserve_asymmetric_named_weight_rows(
    name, input_module, class_name, view, numeric
):
    reference, weight = _asymmetric_distance_view(nx, class_name, view, numeric)
    graph, _ = _asymmetric_distance_view(input_module, class_name, view, numeric)
    expected = getattr(nx, name)(reference, weight=weight, usebounds=True, backend="networkx")
    actual = getattr(fnx, name)(graph, weight=weight, usebounds=True)
    assert _distance_value_and_types(actual) == _distance_value_and_types(expected)


@pytest.mark.parametrize("input_module", [nx, fnx], ids=["networkx-input", "fnx-input"])
@pytest.mark.parametrize("class_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("selection", [0, [2, 0, 2]], ids=["scalar", "repeated-subset"])
def test_eccentricity_selected_sources_keep_asymmetric_rows(input_module, class_name, selection):
    graph, weight = _asymmetric_distance_view(input_module, class_name, "filtered", "fraction")
    reference, _ = _asymmetric_distance_view(nx, class_name, "filtered", "fraction")
    expected = nx.eccentricity(reference, v=selection, weight=weight, backend="networkx")
    actual = fnx.eccentricity(graph, v=selection, weight=weight)
    assert _distance_value_and_types(actual) == _distance_value_and_types(expected)


@pytest.mark.parametrize("name", _WEIGHTED_DISTANCE_MEASURES)
@pytest.mark.parametrize("namespace", ["distance_measures", "algorithms"])
def test_distance_namespaces_keep_asymmetric_rows(name, namespace):
    graph, weight = _asymmetric_distance_view(nx, "DiGraph", "direct", "integer")
    expected = getattr(nx, name)(graph, weight=weight, backend="networkx")
    actual = getattr(getattr(fnx, namespace), name)(graph, weight=weight)
    assert _distance_value_and_types(actual) == _distance_value_and_types(expected)


@pytest.mark.parametrize("name", _WEIGHTED_DISTANCE_MEASURES)
@pytest.mark.parametrize("class_name", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("numeric", ["integer", "decimal"])
@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm-conversion"])
def test_distance_backend_recovers_asymmetric_source(name, class_name, numeric, warm):
    graph, weight = _asymmetric_distance_view(nx, class_name, "filtered", numeric)
    expected = getattr(nx, name)(graph, weight=weight, backend="networkx")
    if warm:
        # Prime the same attribute conversion through an eager algorithm.
        nx.dijkstra_path_length(graph, 0, 2, weight=weight, backend="franken_networkx")
        assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
    actual = getattr(nx, name)(graph, weight=weight, backend="franken_networkx")
    assert _distance_value_and_types(actual) == _distance_value_and_types(expected)


@pytest.mark.parametrize("name", _WEIGHTED_DISTANCE_MEASURES)
@pytest.mark.parametrize("class_name", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_distance_measures_named_weight_reads_private_attribute_providers(name, class_name):
    outcomes = []
    for api in (nx, fnx):
        rows, _ = _live_distance_graph(nx, class_name, "graph")
        calls = []

        class WeightAttributes(dict):
            def get(self, key, default=None):
                if key == "weight":
                    calls.append(dict.__getitem__(self, key))
                    target = rows[1][2]
                    if rows.is_multigraph():
                        target = target["route"]
                    target["weight"] = 1
                return super().get(key, default)

        edges = list(rows.edges(keys=True, data=True) if rows.is_multigraph() else rows.edges(data=True))
        for edge in edges:
            u, v = edge[:2]
            attributes = WeightAttributes(edge[-1])
            if rows.is_multigraph():
                rows._adj[u][v][edge[2]] = attributes
                if rows.is_directed():
                    rows._pred[v][u][edge[2]] = attributes
                else:
                    rows._adj[v][u][edge[2]] = attributes
            else:
                rows._adj[u][v] = attributes
                if rows.is_directed():
                    rows._pred[v][u] = attributes
                else:
                    rows._adj[v][u] = attributes
        graph = getattr(api, class_name)()
        graph.add_nodes_from(rows)
        graph.add_edge(0, 2, weight=99)
        graph._adj = rows._adj
        if graph.is_directed():
            graph._pred = rows._pred
        value = getattr(api, name)(graph, weight="weight")
        outcomes.append((_distance_value_and_types(value), calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("entrypoint", ["top-level", "namespace", "backend-cold", "backend-warm"])
@pytest.mark.parametrize("selection", [None, [0, 1, 2], 0], ids=["all", "bunch", "scalar"])
@pytest.mark.parametrize("mutation", ["remove-node", "change-distance"])
def test_eccentricity_consumes_supplied_distances_with_live_nbunch(entrypoint, selection, mutation):
    outcomes = []
    for reference in (True, False):
        graph = nx.path_graph(3)
        calls = []

        class Distances(dict):
            def __getitem__(self, node):
                calls.append(node)
                if node == 0:
                    if mutation == "remove-node":
                        graph.remove_node(2)
                    else:
                        dict.__getitem__(self, 1)[2] = 17
                return super().__getitem__(node)

        distances = Distances({0: {0: 0, 1: 1, 2: 2},
                               1: {0: 1, 1: 0, 2: 1},
                               2: {0: 2, 1: 1, 2: 0}})
        if not reference and entrypoint == "backend-warm":
            nx.degree_centrality(graph, backend="franken_networkx")
            assert graph.__networkx_cache__.get("backends", {}).get("franken_networkx")
        api = nx.eccentricity if reference else fnx.eccentricity
        options = {"backend": "networkx"} if reference else {}
        if not reference and entrypoint == "namespace":
            api = fnx.distance_measures.eccentricity
        elif not reference and entrypoint.startswith("backend-"):
            api, options = nx.eccentricity, {"backend": "franken_networkx"}
        try:
            value = api(graph, v=selection, sp=distances, **options)
        except Exception as exc:
            result = ("error", type(exc).__name__, exc.args)
        else:
            result = ("return", _distance_value_and_types(value))
        outcomes.append((result, calls, list(graph)))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", _WEIGHTED_DISTANCE_MEASURES)
@pytest.mark.parametrize("weight", [[], {"cost": 1}], ids=["unhashable-list", "unhashable-dict"])
@pytest.mark.parametrize("entrypoint", ["direct", "backend"])
def test_distance_live_rows_preserve_invalid_weight_errors(name, weight, entrypoint):
    outcomes = []
    for reference in (True, False):
        graph, _ = _asymmetric_distance_view(nx, "DiGraph", "direct", "integer")
        api = getattr(nx, name) if reference or entrypoint == "backend" else getattr(fnx, name)
        options = {"backend": "networkx"} if reference else (
            {"backend": "franken_networkx"} if entrypoint == "backend" else {}
        )
        with pytest.raises(TypeError) as caught:
            api(graph, weight=weight, **options)
        outcomes.append(caught.value.args)
    assert outcomes[0] == outcomes[1]
