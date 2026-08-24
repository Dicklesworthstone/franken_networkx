"""Phase B certification: bipartite module — projections, matching,
vertex cover, centralities, clustering, redundancy, spectral
bipartivity. Identical fixed bipartite graphs. Zero divergences.
"""
import importlib
import importlib.util
import inspect
import io
import random
import sys
from functools import lru_cache
from pathlib import Path

import networkx as nx
import networkx.algorithms.bipartite as nxb
import pytest

import franken_networkx as fnx


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_bipartite_surface"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _mk(mod):
    # Dense, connected, every node degree >= 2 so node_redundancy and
    # bipartite_sets/matching are well-defined (a sparse random graph
    # yields isolated/degree-1 nodes -> both impls raise identically,
    # which is an nx contract, not a divergence).
    g = mod.Graph()
    for i in range(6):
        g.add_node(i, bipartite=0)
    for i in range(6, 12):
        g.add_node(i, bipartite=1)
    R = random.Random(53)
    # ring backbone guarantees connectivity + min degree 2
    for i in range(6):
        g.add_edge(i, 6 + i)
        g.add_edge(i, 6 + ((i + 1) % 6))
    for _ in range(10):
        g.add_edge(R.randrange(6), 6 + R.randrange(6))
    return g


_TOP = set(range(6))


def _D(d):
    return sorted((repr(k), round(float(v), 6)) for k, v in d.items())


def _EW(g, weighted=True):
    if weighted:
        return sorted(
            (min(repr(u), repr(v)), max(repr(u), repr(v)), round(d.get("weight"), 6))
            for u, v, d in g.edges(data=True)
        )
    return sorted((min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v in g.edges())


def test_bipartite_basics_and_projection():
    bf, bn = _mk(fnx), _mk(nx)
    assert nx.is_bipartite(bf) == nx.is_bipartite(bn) is True
    assert round(nxb.density(bf, _TOP), 9) == round(nxb.density(bn, _TOP), 9)
    assert _EW(nxb.projected_graph(bf, _TOP), weighted=False) == _EW(
        nxb.projected_graph(bn, _TOP), weighted=False
    )
    assert _EW(nxb.weighted_projected_graph(bf, _TOP)) == _EW(nxb.weighted_projected_graph(bn, _TOP))
    assert _EW(nxb.overlap_weighted_projected_graph(bf, _TOP)) == _EW(
        nxb.overlap_weighted_projected_graph(bn, _TOP)
    )


def test_bipartite_projection_module_paths_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    assert round(module.density(fnx_graph, _TOP), 9) == round(
        nxb.density(nx_graph, _TOP), 9
    )
    assert round(via_algorithms.density(fnx_graph, _TOP), 9) == round(
        nxb.density(nx_graph, _TOP), 9
    )
    for route in (module, via_algorithms):
        assert _EW(route.projected_graph(fnx_graph, _TOP), weighted=False) == _EW(
            nxb.projected_graph(nx_graph, _TOP), weighted=False
        )
        assert _EW(route.weighted_projected_graph(fnx_graph, _TOP)) == _EW(
            nxb.weighted_projected_graph(nx_graph, _TOP)
        )
        assert _EW(route.overlap_weighted_projected_graph(fnx_graph, _TOP)) == _EW(
            nxb.overlap_weighted_projected_graph(nx_graph, _TOP)
        )


def test_bipartite_matching_and_cover():
    bf, bn = _mk(fnx), _mk(nx)
    assert sorted((repr(k), repr(v)) for k, v in nxb.hopcroft_karp_matching(bf, top_nodes=_TOP).items()) == sorted(
        (repr(k), repr(v)) for k, v in nxb.hopcroft_karp_matching(bn, top_nodes=_TOP).items()
    )
    assert sorted(repr(x) for x in nxb.to_vertex_cover(bf, nxb.maximum_matching(bf, top_nodes=_TOP), _TOP)) == sorted(
        repr(x) for x in nxb.to_vertex_cover(bn, nxb.maximum_matching(bn, top_nodes=_TOP), _TOP)
    )


def test_bipartite_matching_module_paths_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    def matching_items(matching):
        return sorted((repr(k), repr(v)) for k, v in matching.items())

    expected_hk = nxb.hopcroft_karp_matching(nx_graph, top_nodes=_TOP)
    assert matching_items(module.hopcroft_karp_matching(fnx_graph, top_nodes=_TOP)) == matching_items(
        expected_hk
    )
    assert matching_items(
        via_algorithms.hopcroft_karp_matching(fnx_graph, top_nodes=_TOP)
    ) == matching_items(expected_hk)

    expected_max = nxb.maximum_matching(nx_graph, top_nodes=_TOP)
    module_max = module.maximum_matching(fnx_graph, top_nodes=_TOP)
    algorithms_max = via_algorithms.maximum_matching(fnx_graph, top_nodes=_TOP)
    assert matching_items(module_max) == matching_items(expected_max)
    assert matching_items(algorithms_max) == matching_items(expected_max)

    expected_cover = sorted(
        repr(node) for node in nxb.to_vertex_cover(nx_graph, expected_max, _TOP)
    )
    assert sorted(
        repr(node) for node in module.to_vertex_cover(fnx_graph, module_max, _TOP)
    ) == expected_cover
    assert sorted(
        repr(node)
        for node in via_algorithms.to_vertex_cover(fnx_graph, algorithms_max, _TOP)
    ) == expected_cover


def test_bipartite_partition_matching_backend_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    for name, args in (
        ("color", ()),
        ("sets", (_TOP,)),
        ("is_bipartite_node_set", (_TOP,)),
        ("hopcroft_karp_matching", (_TOP,)),
        ("maximum_matching", (_TOP,)),
        ("eppstein_matching", (_TOP,)),
    ):
        actual = getattr(module, name)(fnx_graph, *args, backend="networkx")
        expected = getattr(nxb, name)(nx_graph, *args, backend="networkx")
        if name.endswith("matching"):
            assert sorted((repr(k), repr(v)) for k, v in actual.items()) == sorted(
                (repr(k), repr(v)) for k, v in expected.items()
            )
        elif isinstance(actual, dict):
            assert _D(actual) == _D(expected)
        elif isinstance(actual, tuple):
            assert tuple(map(set, actual)) == tuple(map(set, expected))
        else:
            assert actual == expected

    with pytest.raises(ImportError):
        module.color(fnx_graph, backend="missing")
    with pytest.raises(TypeError):
        module.sets(fnx_graph, unexpected=True)


def test_bipartite_basic_metrics_backend_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    assert module.density(fnx_graph, _TOP, backend="networkx") == nxb.density(
        nx_graph, _TOP, backend="networkx"
    )
    assert _D(module.degree_centrality(fnx_graph, _TOP, backend="networkx")) == _D(
        nxb.degree_centrality(nx_graph, _TOP, backend="networkx")
    )
    actual_top, actual_bottom = module.degrees(
        fnx_graph, _TOP, weight=None, backend="networkx"
    )
    expected_top, expected_bottom = nxb.degrees(
        nx_graph, _TOP, weight=None, backend="networkx"
    )
    assert list(actual_top) == list(expected_top)
    assert list(actual_bottom) == list(expected_bottom)


def test_bipartite_clustering_backend_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    for name in (
        "latapy_clustering",
        "clustering",
        "average_clustering",
        "robins_alexander_clustering",
    ):
        actual = getattr(module, name)(fnx_graph, backend="networkx")
        expected = getattr(nxb, name)(nx_graph, backend="networkx")
        if isinstance(actual, dict):
            assert _D(actual) == _D(expected)
        else:
            assert actual == pytest.approx(expected)

    with pytest.raises(ImportError):
        module.clustering(fnx_graph, backend="missing")


def test_bipartite_centrality_backend_signatures_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    for name in ("betweenness_centrality", "closeness_centrality", "node_redundancy"):
        actual = getattr(module, name)(fnx_graph, _TOP, backend="networkx")
        expected = getattr(nxb, name)(nx_graph, _TOP, backend="networkx")
        assert _D(actual) == _D(expected)

    with pytest.raises(TypeError):
        module.node_redundancy(fnx_graph, unexpected=True)


def test_biadjacency_matrix_backend_signature_matches_legacy_oracle():
    module = importlib.import_module("franken_networkx.bipartite")
    legacy = _legacy_networkx()
    actual_parameters = inspect.signature(module.biadjacency_matrix).parameters
    expected_parameters = inspect.signature(
        legacy.algorithms.bipartite.biadjacency_matrix
    ).parameters
    assert actual_parameters == expected_parameters
    graph, legacy_graph = _mk(fnx), _mk(legacy)
    graph[0][6]["weight"] = 3
    legacy_graph[0][6]["weight"] = 3

    actual = module.biadjacency_matrix(
        graph, sorted(_TOP), weight="weight", format="csc", backend="networkx"
    )
    expected = legacy.algorithms.bipartite.biadjacency_matrix(
        legacy_graph,
        sorted(_TOP),
        weight="weight",
        format="csc",
        backend="networkx",
    )
    assert actual.format == expected.format
    assert actual.dtype == expected.dtype
    assert actual.toarray().tolist() == expected.toarray().tolist()

    with pytest.raises(ImportError):
        module.biadjacency_matrix(graph, sorted(_TOP), backend="missing")
    with pytest.raises(TypeError):
        module.biadjacency_matrix(graph, sorted(_TOP), unexpected=True)


def test_bipartite_min_edge_cover_routes_through_fnx(monkeypatch):
    module = importlib.import_module("franken_networkx.bipartite")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.bipartite")
    graph = fnx.path_graph(4)
    calls = []

    def fake_hopcroft_karp_matching(G):
        calls.append(G)
        return {0: 1, 1: 0, 2: 3, 3: 2}

    monkeypatch.setattr(module, "hopcroft_karp_matching", fake_hopcroft_karp_matching)

    assert module.min_edge_cover(graph) == {(0, 1), (1, 0), (2, 3), (3, 2)}
    assert via_algorithms.min_edge_cover(graph) == {
        (0, 1),
        (1, 0),
        (2, 3),
        (3, 2),
    }
    assert calls == [graph, graph]


def test_bipartite_min_edge_cover_matches_networkx_value():
    module = importlib.import_module("franken_networkx.bipartite")
    graph = fnx.path_graph(4)
    expected_graph = nx.path_graph(4)

    assert module.min_edge_cover(graph) == nxb.min_edge_cover(expected_graph)


def test_bipartite_edgelist_helpers_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)
    fnx_graph[0][6]["weight"] = 3
    nx_graph[0][6]["weight"] = 3
    fnx_graph[1][7]["capacity"] = 12
    nx_graph[1][7]["capacity"] = 12

    assert module.generate_edgelist is not nxb.generate_edgelist
    assert module.write_edgelist is not nxb.write_edgelist
    for data in (False, True, ["weight", "capacity"]):
        assert list(module.generate_edgelist(fnx_graph, data=data)) == list(
            nxb.generate_edgelist(nx_graph, data=data)
        )
        assert list(via_algorithms.generate_edgelist(fnx_graph, data=data)) == list(
            nxb.generate_edgelist(nx_graph, data=data)
        )

    actual = io.BytesIO()
    expected = io.BytesIO()
    module.write_edgelist(fnx_graph, actual, data=["weight", "capacity"])
    nxb.write_edgelist(nx_graph, expected, data=["weight", "capacity"])
    assert actual.getvalue() == expected.getvalue()


def test_bipartite_clustering_module_paths_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    for mode in ("dot", "min", "max"):
        assert _D(module.clustering(fnx_graph, mode=mode)) == _D(
            nxb.clustering(nx_graph, mode=mode)
        )
        assert _D(via_algorithms.clustering(fnx_graph, nodes=_TOP, mode=mode)) == _D(
            nxb.clustering(nx_graph, nodes=_TOP, mode=mode)
        )
        for nodes in (None, sorted(_TOP), [6, 7, 8]):
            assert round(
                module.average_clustering(fnx_graph, nodes=nodes, mode=mode), 12
            ) == round(nxb.average_clustering(nx_graph, nodes=nodes, mode=mode), 12)
            assert round(
                via_algorithms.average_clustering(
                    fnx_graph, nodes=nodes, mode=mode
                ),
                12,
            ) == round(nxb.average_clustering(nx_graph, nodes=nodes, mode=mode), 12)


def test_bipartite_centrality_module_paths_match_networkx():
    module = importlib.import_module("franken_networkx.bipartite")
    via_algorithms = importlib.import_module("franken_networkx.algorithms.bipartite")
    fnx_graph, nx_graph = _mk(fnx), _mk(nx)

    for route in (module, via_algorithms):
        assert _D(route.degree_centrality(fnx_graph, _TOP)) == _D(
            nxb.degree_centrality(nx_graph, _TOP)
        )
        assert _D(route.betweenness_centrality(fnx_graph, _TOP)) == _D(
            nxb.betweenness_centrality(nx_graph, _TOP)
        )
        assert _D(route.closeness_centrality(fnx_graph, _TOP)) == _D(
            nxb.closeness_centrality(nx_graph, _TOP)
        )
        assert _D(route.node_redundancy(fnx_graph)) == _D(
            nxb.node_redundancy(nx_graph)
        )
        assert round(route.spectral_bipartivity(fnx_graph), 6) == round(
            nxb.spectral_bipartivity(nx_graph), 6
        )


def test_bipartite_centrality_clustering_redundancy():
    bf, bn = _mk(fnx), _mk(nx)
    assert _D(nxb.degree_centrality(bf, _TOP)) == _D(nxb.degree_centrality(bn, _TOP))
    assert _D(nxb.betweenness_centrality(bf, _TOP)) == _D(nxb.betweenness_centrality(bn, _TOP))
    assert _D(nxb.closeness_centrality(bf, _TOP)) == _D(nxb.closeness_centrality(bn, _TOP))
    assert _D(nxb.clustering(bf)) == _D(nxb.clustering(bn))
    assert round(nxb.robins_alexander_clustering(bf), 9) == round(nxb.robins_alexander_clustering(bn), 9)
    assert _D(nxb.node_redundancy(bf)) == _D(nxb.node_redundancy(bn))
    assert round(nxb.spectral_bipartivity(bf), 6) == round(nxb.spectral_bipartivity(bn), 6)
