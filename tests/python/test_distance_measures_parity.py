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
    # eccentricity sweep. Their usebounds route does populate the snapshot.
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
