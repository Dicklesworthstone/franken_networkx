"""Phase B certification: bipartite module — projections, matching,
vertex cover, centralities, clustering, redundancy, spectral
bipartivity. Identical fixed bipartite graphs. Zero divergences.
"""
import importlib
import io
import random

import networkx as nx
import networkx.algorithms.bipartite as nxb

import franken_networkx as fnx


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
