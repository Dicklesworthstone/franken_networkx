"""Parity for inner-dict order on all_pairs_dijkstra/bellman_ford*.

Bead br-r37-c1-6rphu — continuation of br-r37-c1-3dxfn (outer keys)
and br-r37-c1-5ur50 (BFS inner). Five all_pairs_* dijkstra/bellman-
ford functions yielded inner per-source dicts in arbitrary Rust
internal order; nx returns them in (distance, BFS-tiebreak) order
from each source.
"""

from __future__ import annotations

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
@pytest.mark.parametrize("name", [
    "all_pairs_dijkstra_path",
    "all_pairs_dijkstra_path_length",
    "all_pairs_bellman_ford_path",
    "all_pairs_bellman_ford_path_length",
])
def test_inner_keys_match_networkx(name):
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(getattr(fnx, name)(g))
    n = dict(getattr(nx, name)(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys()), (
            f"{name}[{source}]: fnx={list(f[source].keys())} "
            f"nx={list(n[source].keys())}"
        )


@needs_nx
def test_all_pairs_dijkstra_tuple_inner_keys_match():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra(g))
    n = dict(nx.all_pairs_dijkstra(gx))
    for source in n:
        fdist, fpaths = f[source]
        ndist, npaths = n[source]
        assert list(fdist.keys()) == list(ndist.keys())
        assert list(fpaths.keys()) == list(npaths.keys())


@needs_nx
def test_weighted_dijkstra_inner_uses_distance_order():
    """For weighted graphs the BFS order and distance order differ;
    nx uses distance order — fnx must too."""
    g = fnx.Graph()
    gx = nx.Graph()
    for u, v, w in [("c", "a", 10), ("c", "b", 1), ("b", "d", 1)]:
        g.add_edge(u, v, weight=w)
        gx.add_edge(u, v, weight=w)
    f = dict(fnx.all_pairs_dijkstra_path(g, weight="weight"))
    n = dict(nx.all_pairs_dijkstra_path(gx, weight="weight"))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_path_graph_inner_unchanged():
    """Regression: simple int graphs that already worked must continue."""
    g = fnx.path_graph(4)
    gx = nx.path_graph(4)
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


@needs_nx
def test_inner_values_unchanged():
    g = _make_str_graph(fnx)
    gx = _make_str_graph(nx)
    f = dict(fnx.all_pairs_dijkstra_path_length(g))
    n = dict(nx.all_pairs_dijkstra_path_length(gx))
    for source in n:
        for target in n[source]:
            assert f[source][target] == n[source][target]


@needs_nx
def test_disconnected_components_inner_keys_match():
    g = fnx.Graph([("a", "b"), ("c", "d")])
    gx = nx.Graph([("a", "b"), ("c", "d")])
    f = dict(fnx.all_pairs_dijkstra_path(g))
    n = dict(nx.all_pairs_dijkstra_path(gx))
    for source in n:
        assert list(f[source].keys()) == list(n[source].keys())


# br-r37-c1-9bnpj: over int weights (or none - networkx's default is the int
# 1) networkx's distances are ints; the multigraph arm of fnx's native
# all_pairs_dijkstra wrote every distance as a float. == cannot see it
# (1 == 1.0), so compare (value, type). Float weights stay floats in both.
_TYPED_BUNCHES = {
    "unweighted": [(0, 1, {}), (1, 2, {}), (0, 1, {}), (2, 3, {})],
    "int": [(0, 1, {"weight": 4}), (1, 2, {"weight": 2}), (0, 1, {"weight": 1}), (2, 3, {"weight": 3})],
    "lightest_is_int": [(0, 1, {"weight": 2.5}), (0, 1, {"weight": 1}), (1, 2, {"weight": 2})],
    "float": [(0, 1, {"weight": 1.5}), (1, 2, {"weight": 2.0}), (0, 1, {"weight": 0.5}), (2, 3, {"weight": 1.0})],
}


def _typed(d):
    return {k: (v, type(v).__name__) for k, v in d.items()}


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("bunch", sorted(_TYPED_BUNCHES))
def test_all_pairs_dijkstra_distance_types_match_networkx(cls, bunch):
    g = getattr(fnx, cls)()
    g.add_edges_from(_TYPED_BUNCHES[bunch])
    gx = getattr(nx, cls)()
    gx.add_edges_from(_TYPED_BUNCHES[bunch])

    f = dict(fnx.all_pairs_dijkstra(g))
    n = dict(nx.all_pairs_dijkstra(gx))

    assert list(f) == list(n)
    for source, (n_dist, n_paths) in n.items():
        f_dist, f_paths = f[source]
        assert _typed(f_dist) == _typed(n_dist), (source, f_dist, n_dist)
        assert f_paths == n_paths


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("domain", ["integer", "wide_integer", "fraction", "decimal"])
def test_backend_all_pairs_dijkstra_preserves_numeric_domain_and_cutoff(cls, domain):
    from decimal import Decimal
    from fractions import Fraction

    unit = {
        "integer": 2,
        "wide_integer": 2**80 + 1,
        "fraction": Fraction(1, 3),
        "decimal": Decimal("0.1"),
    }[domain]
    graph = getattr(nx, cls)()
    graph.add_nodes_from(["source", "far", "near", "isolated"])
    graph.add_edge("source", "far", cost=4 * unit)
    graph.add_edge("source", "near", cost=unit)
    graph.add_edge("near", "far", cost=unit)
    if graph.is_multigraph():
        graph.add_edge("source", "near", key="parallel", cost=3 * unit)
    kwargs = {"weight": "cost", "cutoff": 2 * unit}
    actual = list(nx.all_pairs_dijkstra(graph, **kwargs, backend="franken_networkx"))
    expected = list(nx.all_pairs_dijkstra(graph, **kwargs, backend="networkx"))
    assert [source for source, _ in actual] == [source for source, _ in expected]
    for (source, (distances, paths)), (_, (wanted_distances, wanted_paths)) in zip(actual, expected):
        assert list(distances.items()) == list(wanted_distances.items()), source
        assert list(paths.items()) == list(wanted_paths.items()), source
        assert _typed(distances) == _typed(wanted_distances), source


def test_backend_all_pairs_dijkstra_supports_automatic_dispatch(monkeypatch):
    import franken_networkx.backend as backend_module

    graph = nx.path_graph(4)
    expected = list(nx.all_pairs_dijkstra(graph, backend="networkx"))
    calls = []
    implementation = backend_module._SUPPORTED_ALGORITHMS["all_pairs_dijkstra"]

    def observed(G, cutoff=None, weight="weight"):
        calls.append(G)
        return implementation(G, cutoff=cutoff, weight=weight)

    monkeypatch.setitem(backend_module._SUPPORTED_ALGORITHMS, "all_pairs_dijkstra", observed)
    monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
    assert list(nx.all_pairs_dijkstra(graph)) == expected
    assert calls == [graph]


@pytest.mark.parametrize("exit_kind", ["yield", "close", "error"])
def test_backend_all_pairs_dijkstra_invalidates_reentrant_callback_caches(exit_kind, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.DiGraph()
    graph.add_weighted_edges_from([(0, 1, 1), (1, 2, 9)])

    def weight(u, v, data):
        assert data is graph._adj[u][v]
        if (u, v) == (0, 1):
            # A nested backend call may cache the old graph during the callback.
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            assert graph.__networkx_cache__["backends"]["franken_networkx"]
            graph[1][2]["weight"] = 2
            if exit_kind == "error":
                raise RuntimeError("weight callback stopped")
        return data["weight"]

    iterator = nx.all_pairs_dijkstra(graph, weight=weight, backend="franken_networkx")
    if exit_kind == "error":
        with pytest.raises(RuntimeError, match="weight callback stopped"):
            next(iterator)
    else:
        assert next(iterator)[1][0] == {0: 0, 1: 1, 2: 3}
        if exit_kind == "close":
            nx.relabel_nodes(graph, {}, backend="franken_networkx")
            graph[1][2]["weight"] = 4
            iterator.close()
    assert not graph.__networkx_cache__.get("backends")
    iterator.close()
