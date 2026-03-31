"""Tests for previously untested algorithm functions.

Covers graph operators, community detection, dominating sets,
planarity, transitive operations, and remaining shortest path variants.
"""

import math

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Graph operators
# ---------------------------------------------------------------------------


class TestGraphOperators:
    def test_union(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G2 = fnx.Graph()
        G2.add_edge(2, 3)
        result = fnx.union(G1, G2)
        assert result.number_of_nodes() == 4
        assert result.number_of_edges() == 2

    def test_intersection(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_edge(0, 1)
        G2.add_edge(2, 3)
        result = fnx.intersection(G1, G2)
        assert result.has_edge(0, 1)
        assert not result.has_edge(1, 2)

    def test_compose(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G2 = fnx.Graph()
        G2.add_edge(1, 2)
        result = fnx.compose(G1, G2)
        assert result.number_of_nodes() == 3
        assert result.number_of_edges() == 2

    def test_difference(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_edge(0, 1)
        result = fnx.difference(G1, G2)
        assert not result.has_edge(0, 1)
        assert result.has_edge(1, 2)

    def test_symmetric_difference(self):
        G1 = fnx.Graph()
        G1.add_edge(0, 1)
        G1.add_edge(1, 2)
        G2 = fnx.Graph()
        G2.add_edge(0, 1)
        G2.add_edge(2, 3)
        result = fnx.symmetric_difference(G1, G2)
        assert not result.has_edge(0, 1)
        assert result.has_edge(1, 2)
        assert result.has_edge(2, 3)


# ---------------------------------------------------------------------------
# Community detection
# ---------------------------------------------------------------------------


class TestCommunityDetection:
    def test_louvain_communities(self):
        G = fnx.Graph()
        # Two cliques connected by a bridge
        for i in range(4):
            for j in range(i + 1, 4):
                G.add_edge(i, j)
        for i in range(4, 8):
            for j in range(i + 1, 8):
                G.add_edge(i, j)
        G.add_edge(3, 4)  # bridge
        comms = fnx.louvain_communities(G)
        assert len(comms) >= 2

    def test_label_propagation_communities(self):
        G = fnx.path_graph(10)
        comms = fnx.label_propagation_communities(G)
        assert len(comms) >= 1
        # All nodes should be in some community
        all_nodes = set()
        for c in comms:
            all_nodes.update(c)
        assert len(all_nodes) == 10

    def test_greedy_modularity_communities(self):
        G = fnx.complete_graph(6)
        comms = fnx.greedy_modularity_communities(G)
        assert len(comms) >= 1

    def test_modularity(self):
        G = fnx.complete_graph(4)
        # modularity expects lists of node labels
        comms = [[0, 1], [2, 3]]
        m = fnx.modularity(G, comms)
        assert isinstance(m, float)
        assert -0.5 <= m <= 1.0


# ---------------------------------------------------------------------------
# Dominating sets
# ---------------------------------------------------------------------------


class TestDominatingSets:
    def test_dominating_set(self):
        G = fnx.star_graph(4)
        ds = fnx.dominating_set(G)
        assert isinstance(ds, (list, set))
        assert len(ds) >= 1

    def test_is_dominating_set(self):
        G = fnx.star_graph(4)
        # Center node (0) dominates all
        assert fnx.is_dominating_set(G, [0])
        # A leaf alone doesn't dominate all
        assert not fnx.is_dominating_set(G, [1])


# ---------------------------------------------------------------------------
# Planarity
# ---------------------------------------------------------------------------


class TestPlanarity:
    def test_planar_graph(self):
        # K4 is planar
        G = fnx.complete_graph(4)
        assert fnx.is_planar(G)

    def test_non_planar_graph(self):
        # K5 is not planar (Kuratowski's theorem)
        G = fnx.complete_graph(5)
        assert not fnx.is_planar(G)


# ---------------------------------------------------------------------------
# Graph predicates
# ---------------------------------------------------------------------------


class TestGraphPredicates:
    def test_is_empty_true(self):
        G = fnx.Graph()
        G.add_node(0)
        G.add_node(1)
        assert fnx.is_empty(G)

    def test_is_empty_false(self):
        G = fnx.Graph()
        G.add_edge(0, 1)
        assert not fnx.is_empty(G)

    def test_degree_histogram(self):
        G = fnx.path_graph(5)
        hist = fnx.degree_histogram(G)
        assert isinstance(hist, list)
        # Path: two nodes of degree 1, three of degree 2
        assert hist[1] == 2
        assert hist[2] == 3


# ---------------------------------------------------------------------------
# Shortest path variants
# ---------------------------------------------------------------------------


class TestShortestPathVariants:
    def test_all_pairs_shortest_path(self):
        G = fnx.path_graph(4)
        result = fnx.all_pairs_shortest_path(G)
        assert len(result) == 4
        assert result[0][3] == [0, 1, 2, 3]

    def test_all_pairs_shortest_path_length(self):
        G = fnx.path_graph(4)
        result = fnx.all_pairs_shortest_path_length(G)
        assert len(result) == 4
        assert result[0][3] == 3

    def test_single_source_shortest_path(self):
        G = fnx.path_graph(4)
        paths = fnx.single_source_shortest_path(G, 0)
        assert len(paths) == 4
        assert paths[3] == [0, 1, 2, 3]

    def test_single_source_shortest_path_length(self):
        G = fnx.path_graph(4)
        lengths = fnx.single_source_shortest_path_length(G, 0)
        assert lengths[0] == 0
        assert lengths[3] == 3

    def test_multi_source_dijkstra(self):
        G = fnx.path_graph(5)
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(1, 2, weight=1.0)
        G.add_edge(2, 3, weight=1.0)
        G.add_edge(3, 4, weight=1.0)
        result = fnx.multi_source_dijkstra(G, [0, 4], weight="weight")
        assert isinstance(result, (dict, tuple, list))

    def test_barycenter(self):
        G = fnx.path_graph(5)
        bc = fnx.barycenter(G)
        # Center of a path is the middle node(s)
        assert 2 in bc


# ---------------------------------------------------------------------------
# Transitive operations
# ---------------------------------------------------------------------------


class TestTransitiveOperations:
    def test_transitive_closure(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        tc = fnx.transitive_closure(D)
        assert tc.has_edge(0, 2)  # transitively reachable
        assert tc.has_edge(0, 1)

    def test_transitive_reduction(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 2)
        D.add_edge(0, 2)  # redundant
        tr = fnx.transitive_reduction(D)
        assert tr.has_edge(0, 1)
        assert tr.has_edge(1, 2)
        assert not tr.has_edge(0, 2)  # removed as redundant


# ---------------------------------------------------------------------------
# Directed component counts
# ---------------------------------------------------------------------------


class TestDirectedComponentCounts:
    def test_number_strongly_connected_components(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_edge(1, 0)
        D.add_node(2)
        assert fnx.number_strongly_connected_components(D) == 2

    def test_number_weakly_connected_components(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_node(2)
        assert fnx.number_weakly_connected_components(D) == 2

    def test_weakly_connected_components(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1)
        D.add_node(2)
        wcc = fnx.weakly_connected_components(D)
        assert len(wcc) == 2


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


class TestGenerators:
    def test_barabasi_albert(self):
        G = fnx.barabasi_albert_graph(20, 2, seed=42)
        assert G.number_of_nodes() == 20

    def test_watts_strogatz(self):
        G = fnx.watts_strogatz_graph(20, 4, 0.3, seed=42)
        assert G.number_of_nodes() == 20
        assert fnx.is_connected(G)

    @needs_nx
    def test_watts_strogatz_accepts_odd_k_like_networkx(self):
        fnx_graph = fnx.watts_strogatz_graph(7, 3, 0.0, seed=42)
        nx_graph = nx.watts_strogatz_graph(7, 3, 0.0, seed=42)
        assert fnx_graph.number_of_nodes() == nx_graph.number_of_nodes()
        assert fnx_graph.number_of_edges() == nx_graph.number_of_edges() == 7
        assert sorted(dict(fnx_graph.degree).values()) == sorted(
            dict(nx_graph.degree()).values()
        )

    @needs_nx
    def test_newman_watts_strogatz_accepts_odd_k_like_networkx(self):
        fnx_graph = fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42)
        nx_graph = nx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42)
        assert fnx_graph.number_of_nodes() == nx_graph.number_of_nodes()
        assert fnx_graph.number_of_edges() == nx_graph.number_of_edges() == 7
        assert sorted(dict(fnx_graph.degree).values()) == sorted(
            dict(nx_graph.degree()).values()
        )

    @needs_nx
    def test_connected_watts_strogatz_accepts_tries_keyword(self):
        fnx_graph = fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42)
        nx_graph = nx.connected_watts_strogatz_graph(12, 4, 0.2, tries=5, seed=42)
        assert fnx_graph.number_of_nodes() == nx_graph.number_of_nodes() == 12
        assert fnx.is_connected(fnx_graph)
        assert nx.is_connected(nx_graph)

    def test_connected_watts_strogatz_zero_tries_raises(self):
        with pytest.raises(ValueError, match="Maximum number of tries exceeded"):
            fnx.connected_watts_strogatz_graph(12, 4, 0.2, tries=0, seed=42)

    def test_random_generators_support_create_using_via_networkx_fallback(self):
        balanced = fnx.balanced_tree(2, 2, create_using=fnx.Graph())
        barbell = fnx.barbell_graph(3, 2, create_using=fnx.Graph())
        bull = fnx.bull_graph(create_using=fnx.Graph())
        chordal_cycle = fnx.chordal_cycle_graph(5, create_using=fnx.MultiGraph())
        chvatal = fnx.chvatal_graph(create_using=fnx.Graph())
        circulant = fnx.circulant_graph(6, [1, 2], create_using=fnx.Graph())
        complete = fnx.complete_graph(4, create_using=fnx.Graph())
        cubical = fnx.cubical_graph(create_using=fnx.Graph())
        cycle = fnx.cycle_graph(4, create_using=fnx.Graph())
        desargues = fnx.desargues_graph(create_using=fnx.Graph())
        diamond = fnx.diamond_graph(create_using=fnx.Graph())
        dodecahedral = fnx.dodecahedral_graph(create_using=fnx.Graph())
        empty = fnx.empty_graph(4, create_using=fnx.Graph())
        frucht = fnx.frucht_graph(create_using=fnx.Graph())
        full = fnx.full_rary_tree(2, 7, create_using=fnx.Graph())
        generalized_petersen = fnx.generalized_petersen_graph(5, 2, create_using=fnx.Graph())
        binomial = fnx.binomial_tree(3, create_using=fnx.Graph())
        bipartite = fnx.complete_bipartite_graph(2, 3, create_using=fnx.Graph())
        dense = fnx.dense_gnm_random_graph(5, 4, seed=1, create_using=fnx.Graph())
        dgm = fnx.dorogovtsev_goltsev_mendes_graph(2, create_using=fnx.Graph())
        hakimi = fnx.havel_hakimi_graph([2, 2, 2, 2], create_using=fnx.Graph())
        hkn = fnx.hkn_harary_graph(2, 5, create_using=fnx.Graph())
        hnm = fnx.hnm_harary_graph(5, 5, create_using=fnx.Graph())
        house = fnx.house_graph(create_using=fnx.Graph())
        house_x = fnx.house_x_graph(create_using=fnx.Graph())
        heawood = fnx.heawood_graph(create_using=fnx.Graph())
        icosahedral = fnx.icosahedral_graph(create_using=fnx.Graph())
        circular = fnx.circular_ladder_graph(4, create_using=fnx.Graph())
        krackhardt = fnx.krackhardt_kite_graph(create_using=fnx.Graph())
        ladder = fnx.ladder_graph(4, create_using=fnx.Graph())
        lollipop = fnx.lollipop_graph(4, 3, create_using=fnx.Graph())
        moebius = fnx.moebius_kantor_graph(create_using=fnx.Graph())
        null = fnx.null_graph(create_using=fnx.Graph())
        octahedral = fnx.octahedral_graph(create_using=fnx.Graph())
        paley = fnx.paley_graph(5, create_using=fnx.DiGraph())
        path = fnx.path_graph(4, create_using=fnx.Graph())
        petersen = fnx.petersen_graph(create_using=fnx.Graph())
        random_clustered = fnx.random_clustered_graph(
            [(1, 0), (1, 0)],
            seed=1,
            create_using=fnx.MultiGraph(),
        )
        random_lobster = fnx.random_lobster_graph(8, 0.4, 0.3, seed=1, create_using=fnx.Graph())
        star = fnx.star_graph(3, create_using=fnx.Graph())
        tadpole = fnx.tadpole_graph(4, 3, create_using=fnx.Graph())
        tetrahedral = fnx.tetrahedral_graph(create_using=fnx.Graph())
        trivial = fnx.trivial_graph(create_using=fnx.Graph())
        truncated_cube = fnx.truncated_cube_graph(create_using=fnx.Graph())
        truncated_tetrahedron = fnx.truncated_tetrahedron_graph(create_using=fnx.Graph())
        tutte = fnx.tutte_graph(create_using=fnx.Graph())
        wheel = fnx.wheel_graph(6, create_using=fnx.Graph())
        periodic_grid = fnx.grid_2d_graph(2, 3, periodic=True, create_using=fnx.Graph())
        ws = fnx.watts_strogatz_graph(7, 3, 0.0, seed=42, create_using=fnx.Graph())
        ba = fnx.barabasi_albert_graph(8, 2, seed=42, create_using=fnx.Graph())
        gnp = fnx.gnp_random_graph(7, 0.2, seed=42, create_using=fnx.Graph())
        er = fnx.erdos_renyi_graph(7, 0.2, seed=42, create_using=fnx.Graph())
        fast = fnx.fast_gnp_random_graph(7, 0.2, seed=42, create_using=fnx.Graph())
        graph = fnx.newman_watts_strogatz_graph(7, 3, 0.0, seed=42, create_using=fnx.Graph())
        regular = fnx.random_regular_graph(2, 6, seed=42, create_using=fnx.Graph())
        cluster = fnx.powerlaw_cluster_graph(10, 2, 0.5, seed=42, create_using=fnx.Graph())

        assert isinstance(balanced, fnx.Graph)
        assert isinstance(barbell, fnx.Graph)
        assert isinstance(bull, fnx.Graph)
        assert isinstance(chordal_cycle, fnx.MultiGraph)
        assert isinstance(chvatal, fnx.Graph)
        assert isinstance(circulant, fnx.Graph)
        assert isinstance(complete, fnx.Graph)
        assert isinstance(cubical, fnx.Graph)
        assert isinstance(cycle, fnx.Graph)
        assert isinstance(desargues, fnx.Graph)
        assert isinstance(diamond, fnx.Graph)
        assert isinstance(dense, fnx.Graph)
        assert isinstance(dgm, fnx.Graph)
        assert isinstance(dodecahedral, fnx.Graph)
        assert isinstance(empty, fnx.Graph)
        assert isinstance(frucht, fnx.Graph)
        assert isinstance(full, fnx.Graph)
        assert isinstance(generalized_petersen, fnx.Graph)
        assert isinstance(hakimi, fnx.Graph)
        assert isinstance(hkn, fnx.Graph)
        assert isinstance(hnm, fnx.Graph)
        assert isinstance(binomial, fnx.Graph)
        assert isinstance(bipartite, fnx.Graph)
        assert isinstance(house, fnx.Graph)
        assert isinstance(house_x, fnx.Graph)
        assert isinstance(heawood, fnx.Graph)
        assert isinstance(icosahedral, fnx.Graph)
        assert isinstance(circular, fnx.Graph)
        assert isinstance(krackhardt, fnx.Graph)
        assert isinstance(ladder, fnx.Graph)
        assert isinstance(lollipop, fnx.Graph)
        assert isinstance(moebius, fnx.Graph)
        assert isinstance(null, fnx.Graph)
        assert isinstance(octahedral, fnx.Graph)
        assert isinstance(paley, fnx.DiGraph)
        assert isinstance(path, fnx.Graph)
        assert isinstance(petersen, fnx.Graph)
        assert isinstance(random_clustered, fnx.MultiGraph)
        assert isinstance(random_lobster, fnx.Graph)
        assert isinstance(star, fnx.Graph)
        assert isinstance(tadpole, fnx.Graph)
        assert isinstance(tetrahedral, fnx.Graph)
        assert isinstance(trivial, fnx.Graph)
        assert isinstance(truncated_cube, fnx.Graph)
        assert isinstance(truncated_tetrahedron, fnx.Graph)
        assert isinstance(tutte, fnx.Graph)
        assert isinstance(wheel, fnx.Graph)
        assert isinstance(periodic_grid, fnx.Graph)
        assert isinstance(ws, fnx.Graph)
        assert isinstance(ba, fnx.Graph)
        assert isinstance(gnp, fnx.Graph)
        assert isinstance(er, fnx.Graph)
        assert isinstance(fast, fnx.Graph)
        assert isinstance(graph, fnx.Graph)
        assert isinstance(regular, fnx.Graph)
        assert isinstance(cluster, fnx.Graph)

    def test_complete_multipartite_and_windmill_match_networkx_contract(self):
        multipartite = fnx.complete_multipartite_graph(2, 3, 1)
        expected_multipartite = nx.complete_multipartite_graph(2, 3, 1)
        windmill = fnx.windmill_graph(3, 4)
        expected_windmill = nx.windmill_graph(3, 4)

        assert sorted(multipartite.edges()) == sorted(expected_multipartite.edges())
        assert sorted(windmill.edges()) == sorted(expected_windmill.edges())

    def test_empty_graph_respects_default_graph_class(self):
        graph = fnx.empty_graph(3, default=fnx.DiGraph)

        assert isinstance(graph, fnx.DiGraph)
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 0

    @needs_nx
    def test_serialization_graph_builders_match_networkx_contract(self):
        def normalize_adjacency_payload(payload):
            normalized = dict(payload)
            normalized["nodes"] = sorted(payload["nodes"], key=lambda item: tuple(sorted(item.items())))
            normalized["adjacency"] = [
                sorted(neighbors, key=lambda item: tuple(sorted(item.items())))
                for neighbors in payload["adjacency"]
            ]
            return normalized

        adjacency_payload = {
            "directed": True,
            "multigraph": False,
            "graph": [],
            "nodes": [{"id": 0}, {"id": 1}],
            "adjacency": [[{"id": 1}], []],
        }
        adjacency_graph = fnx.adjacency_graph(adjacency_payload, directed=True, multigraph=False)
        expected_adjacency = nx.adjacency_graph(
            adjacency_payload,
            directed=True,
            multigraph=False,
        )

        node_link_payload = {
            "directed": True,
            "multigraph": False,
            "graph": {},
            "nodes": [{"id": 0}, {"id": 1}],
            "links": [{"source": 0, "target": 1}],
        }
        node_link_graph = fnx.node_link_graph(
            node_link_payload,
            directed=True,
            multigraph=False,
            edges="links",
        )
        expected_node_link = nx.node_link_graph(
            node_link_payload,
            directed=True,
            multigraph=False,
            edges="links",
        )

        tree_payload = {"name": "root", "kids": [{"name": "leaf"}]}
        tree = fnx.tree_graph(tree_payload, ident="name", children="kids")
        expected_tree = nx.tree_graph(tree_payload, ident="name", children="kids")
        tree_export = fnx.tree_data(
            nx.DiGraph([(0, 1)]),
            0,
            ident="name",
            children="kids",
        )
        expected_tree_export = nx.tree_data(
            nx.DiGraph([(0, 1)]),
            0,
            ident="name",
            children="kids",
        )

        adjacency_data = fnx.adjacency_data(
            fnx.path_graph(3),
            attrs={"id": "name", "key": "ekey"},
        )
        expected_adjacency_data = nx.adjacency_data(
            nx.path_graph(3),
            attrs={"id": "name", "key": "ekey"},
        )

        cytoscape_payload = {
            "data": [],
            "directed": False,
            "multigraph": False,
            "elements": {
                "nodes": [
                    {"data": {"value": "a", "label": "A"}},
                    {"data": {"value": "b", "label": "B"}},
                ],
                "edges": [{"data": {"source": "a", "target": "b"}}],
            },
        }
        cytoscape = fnx.cytoscape_graph(cytoscape_payload, name="label", ident="value")
        expected_cytoscape = nx.cytoscape_graph(
            cytoscape_payload,
            name="label",
            ident="value",
        )
        cytoscape_data = fnx.cytoscape_data(
            fnx.path_graph(2),
            name="label",
            ident="value",
        )
        expected_cytoscape_data = nx.cytoscape_data(
            nx.path_graph(2),
            name="label",
            ident="value",
        )
        node_link_export = fnx.node_link_data(
            fnx.path_graph(2),
            edges="links",
            nodes="vertices",
            source="src",
            target="dst",
            name="name",
        )
        expected_node_link_export = nx.node_link_data(
            nx.path_graph(2),
            edges="links",
            nodes="vertices",
            source="src",
            target="dst",
            name="name",
        )

        projected_source = fnx.complete_bipartite_graph(2, 2)
        projected = fnx.projected_graph(projected_source, [0, 1], multigraph=True)
        expected_projected = nx.projected_graph(
            nx.complete_bipartite_graph(2, 2),
            [0, 1],
            multigraph=True,
        )

        multigraph_input = {
            0: {1: {7: {"weight": 3}}},
            1: {0: {7: {"weight": 3}}},
        }
        converted = fnx.to_networkx_graph(multigraph_input, multigraph_input=True)
        expected_converted = nx.to_networkx_graph(multigraph_input, multigraph_input=True)
        converted_multi = fnx.to_networkx_graph(
            multigraph_input,
            create_using=fnx.MultiGraph(),
            multigraph_input=True,
        )
        expected_converted_multi = nx.to_networkx_graph(
            multigraph_input,
            create_using=nx.MultiGraph(),
            multigraph_input=True,
        )

        assert adjacency_graph.is_directed()
        assert sorted(adjacency_graph.edges()) == sorted(expected_adjacency.edges())
        assert node_link_graph.is_directed()
        assert sorted(node_link_graph.edges()) == sorted(expected_node_link.edges())
        assert normalize_adjacency_payload(adjacency_data) == normalize_adjacency_payload(
            expected_adjacency_data
        )
        assert sorted(tree.edges()) == sorted(expected_tree.edges())
        assert tree_export == expected_tree_export
        assert node_link_export == expected_node_link_export
        assert cytoscape_data == expected_cytoscape_data
        assert sorted(cytoscape.edges()) == sorted(expected_cytoscape.edges())
        assert isinstance(projected, fnx.MultiGraph)
        assert sorted(projected.edges(keys=True)) == sorted(expected_projected.edges(keys=True))
        assert isinstance(converted, fnx.Graph)
        assert sorted(converted.edges(data=True)) == sorted(expected_converted.edges(data=True))
        assert isinstance(converted_multi, fnx.MultiGraph)
        assert sorted(converted_multi.edges(keys=True, data=True)) == sorted(
            expected_converted_multi.edges(keys=True, data=True)
        )

    @needs_nx
    def test_graph_transform_helpers_match_networkx_contract(self):
        path = fnx.path_graph(3)
        line = fnx.line_graph(path, create_using=fnx.Graph())
        expected_line = nx.line_graph(nx.path_graph(3), create_using=nx.Graph())

        clique_graph = fnx.make_max_clique_graph(fnx.complete_graph(4), create_using=fnx.Graph())
        expected_clique_graph = nx.make_max_clique_graph(nx.complete_graph(4), create_using=nx.Graph())

        digraph = fnx.DiGraph([(0, 2), (1, 2)])
        stochastic = fnx.stochastic_graph(digraph, copy=True, weight="w")
        expected_stochastic = nx.stochastic_graph(nx.DiGraph([(0, 2), (1, 2)]), copy=True, weight="w")

        moral = fnx.moral_graph(digraph)
        expected_moral = nx.moral_graph(nx.DiGraph([(0, 2), (1, 2)]))

        chordal_graph, alpha = fnx.complete_to_chordal_graph(fnx.cycle_graph(4))
        expected_chordal_graph, expected_alpha = nx.complete_to_chordal_graph(nx.cycle_graph(4))

        assert isinstance(line, fnx.Graph)
        assert sorted(line.edges()) == sorted(expected_line.edges())
        assert isinstance(clique_graph, fnx.Graph)
        assert sorted(clique_graph.edges()) == sorted(expected_clique_graph.edges())
        assert isinstance(stochastic, fnx.DiGraph)
        assert sorted(stochastic.edges(data=True)) == sorted(expected_stochastic.edges(data=True))
        assert {frozenset(edge) for edge in moral.edges()} == {
            frozenset(edge) for edge in expected_moral.edges()
        }
        assert sorted(chordal_graph.edges()) == sorted(expected_chordal_graph.edges())
        assert alpha == expected_alpha

    def test_graph_class_constructors_accept_edge_iterables(self):
        graph = fnx.Graph([(0, 1)])
        multigraph = fnx.MultiGraph([(0, 1)])
        digraph = fnx.DiGraph([(0, 2), (1, 2)])
        multidigraph = fnx.MultiDiGraph([(0, 2), (1, 2)])

        assert sorted(graph.edges()) == [(0, 1)]
        assert sorted(multigraph.edges()) == [(0, 1)]
        assert sorted(digraph.edges()) == [(0, 2), (1, 2)]
        assert sorted(multidigraph.edges()) == [(0, 2), (1, 2)]

    @needs_nx
    def test_ego_graph_and_from_dict_of_dicts_match_networkx_contract(self):
        weighted = fnx.Graph()
        weighted.add_edge(0, 1, weight=1)
        weighted.add_edge(1, 2, weight=1)
        weighted.add_edge(2, 3, weight=5)

        ego = fnx.ego_graph(weighted, 1, radius=1, distance="weight")
        expected_ego = nx.ego_graph(
            nx.Graph(
                [
                    (0, 1, {"weight": 1}),
                    (1, 2, {"weight": 1}),
                    (2, 3, {"weight": 5}),
                ]
            ),
            1,
            radius=1,
            distance="weight",
        )

        multigraph = fnx.from_dict_of_dicts(
            {0: {1: {7: {"w": 1}}}, 1: {0: {7: {"w": 1}}}},
            create_using=fnx.MultiGraph(),
            multigraph_input=True,
        )
        expected_multigraph = nx.from_dict_of_dicts(
            {0: {1: {7: {"w": 1}}}, 1: {0: {7: {"w": 1}}}},
            create_using=nx.MultiGraph(),
            multigraph_input=True,
        )

        assert sorted(ego.edges(data=True)) == sorted(expected_ego.edges(data=True))
        assert isinstance(multigraph, fnx.MultiGraph)
        assert sorted(multigraph.edges(keys=True, data=True)) == sorted(
            expected_multigraph.edges(keys=True, data=True)
        )

    @needs_nx
    def test_tabular_and_matrix_importers_preserve_networkx_contract(self):
        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")
        scipy_sparse = pytest.importorskip("scipy.sparse")

        frame = pd.DataFrame(
            [
                {"src": "a", "dst": "b", "ek": 7, "weight": 3},
                {"src": "a", "dst": "b", "ek": 8, "weight": 4},
            ]
        )
        pandas_graph = fnx.from_pandas_edgelist(
            frame,
            source="src",
            target="dst",
            edge_attr="weight",
            create_using=fnx.MultiGraph(),
            edge_key="ek",
        )
        expected_pandas_graph = nx.from_pandas_edgelist(
            frame,
            source="src",
            target="dst",
            edge_attr="weight",
            create_using=nx.MultiGraph(),
            edge_key="ek",
        )

        matrix = np.array([[0, 2], [2, 0]], dtype=int)
        numpy_graph = fnx.from_numpy_array(
            matrix,
            parallel_edges=True,
            create_using=fnx.MultiGraph(),
        )
        expected_numpy_graph = nx.from_numpy_array(
            matrix,
            parallel_edges=True,
            create_using=nx.MultiGraph(),
        )

        sparse_graph = fnx.from_scipy_sparse_array(
            scipy_sparse.csr_array(matrix),
            parallel_edges=True,
            create_using=fnx.MultiGraph(),
        )
        expected_sparse_graph = nx.from_scipy_sparse_array(
            scipy_sparse.csr_array(matrix),
            parallel_edges=True,
            create_using=nx.MultiGraph(),
        )

        assert sorted(pandas_graph.edges(keys=True, data=True)) == sorted(
            expected_pandas_graph.edges(keys=True, data=True)
        )
        assert sorted(numpy_graph.edges(keys=True, data=True)) == sorted(
            expected_numpy_graph.edges(keys=True, data=True)
        )
        assert sorted(sparse_graph.edges(keys=True, data=True)) == sorted(
            expected_sparse_graph.edges(keys=True, data=True)
        )

    @needs_nx
    def test_tabular_and_matrix_exporters_preserve_networkx_contract(self):
        np = pytest.importorskip("numpy")
        pytest.importorskip("pandas")

        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)
        graph.add_edge("a", "b", key=8, weight=4)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)
        expected_graph.add_edge("a", "b", key=8, weight=4)

        frame = fnx.to_pandas_edgelist(graph, source="src", target="dst", edge_key="ek")
        expected_frame = nx.to_pandas_edgelist(
            expected_graph,
            source="src",
            target="dst",
            edge_key="ek",
        )

        matrix = fnx.to_numpy_array(
            graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            weight="weight",
        )
        expected_matrix = nx.to_numpy_array(
            expected_graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            weight="weight",
        )
        pandas_adjacency = fnx.to_pandas_adjacency(
            graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            nonedge=-1.0,
        )
        expected_pandas_adjacency = nx.to_pandas_adjacency(
            expected_graph,
            nodelist=["a", "b"],
            multigraph_weight=max,
            nonedge=-1.0,
        )
        sparse = fnx.to_scipy_sparse_array(graph, nodelist=["a", "b"], format="csr")
        expected_sparse = nx.to_scipy_sparse_array(
            expected_graph,
            nodelist=["a", "b"],
            format="csr",
        )

        assert frame.sort_values(["ek"]).reset_index(drop=True).equals(
            expected_frame.sort_values(["ek"]).reset_index(drop=True)
        )
        assert np.array_equal(matrix, expected_matrix)
        assert pandas_adjacency.equals(expected_pandas_adjacency)
        assert np.array_equal(sparse.toarray(), expected_sparse.toarray())

    @needs_nx
    def test_attribute_accessors_preserve_defaults_and_multigraph_keys(self):
        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)
        graph.add_edge("a", "b", key=8)
        graph.add_node("a", color="red")
        graph.add_node("b")

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)
        expected_graph.add_edge("a", "b", key=8)
        expected_graph.add_node("a", color="red")
        expected_graph.add_node("b")

        assert fnx.get_node_attributes(graph, "color", default=None) == nx.get_node_attributes(
            expected_graph,
            "color",
            default=None,
        )
        assert fnx.get_edge_attributes(graph, "weight", default=0) == nx.get_edge_attributes(
            expected_graph,
            "weight",
            default=0,
        )

    @needs_nx
    def test_attribute_mutators_preserve_networkx_multigraph_contract(self):
        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7)
        graph.add_edge("a", "b", key=8)
        graph.add_node("a")
        graph.add_node("b")

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7)
        expected_graph.add_edge("a", "b", key=8)
        expected_graph.add_node("a")
        expected_graph.add_node("b")

        fnx.set_edge_attributes(graph, {("a", "b", 7): 5}, "weight")
        nx.set_edge_attributes(expected_graph, {("a", "b", 7): 5}, "weight")

        fnx.set_node_attributes(graph, "blue", "color")
        nx.set_node_attributes(expected_graph, "blue", "color")

        assert sorted(graph.edges(keys=True, data=True)) == sorted(
            expected_graph.edges(keys=True, data=True)
        )
        assert dict(graph.nodes(data=True)) == dict(expected_graph.nodes(data=True))

    @needs_nx
    def test_top_level_nodes_edges_and_degree_match_networkx(self):
        graph = fnx.Graph()
        graph.add_edge(0, 1, weight=2)
        graph.add_edge(1, 2, weight=3)
        graph.add_edge(2, 3, weight=4)

        expected_graph = nx.Graph()
        expected_graph.add_edge(0, 1, weight=2)
        expected_graph.add_edge(1, 2, weight=3)
        expected_graph.add_edge(2, 3, weight=4)

        assert list(fnx.nodes(graph)) == list(nx.nodes(expected_graph))
        assert sorted(fnx.edges(graph, [1, 2])) == sorted(nx.edges(expected_graph, [1, 2]))
        assert dict(fnx.degree(graph, weight="weight")) == dict(
            nx.degree(expected_graph, weight="weight")
        )

    @needs_nx
    def test_default_node_link_serialization_matches_networkx(self):
        graph = fnx.MultiGraph()
        graph.add_edge("a", "b", key=7, weight=3)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge("a", "b", key=7, weight=3)

        payload = fnx.node_link_data(graph)
        expected_payload = nx.node_link_data(expected_graph)
        roundtrip = fnx.node_link_graph(expected_payload)

        assert payload == expected_payload
        assert isinstance(roundtrip, fnx.MultiGraph)
        assert sorted(roundtrip.edges(keys=True, data=True)) == sorted(
            expected_graph.edges(keys=True, data=True)
        )

    @needs_nx
    def test_attribute_mixing_helpers_match_networkx_on_missing_attributes(self):
        np = pytest.importorskip("numpy")
        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)

        assert fnx.attribute_mixing_dict(graph, "missing", normalized=False) == nx.attribute_mixing_dict(
            expected_graph,
            "missing",
            normalized=False,
        )
        assert np.array_equal(
            fnx.attribute_mixing_matrix(graph, "missing", normalized=True),
            nx.attribute_mixing_matrix(expected_graph, "missing", normalized=True),
        )

    @needs_nx
    def test_attribute_assortativity_matches_networkx_nan_contract(self):
        graph = fnx.Graph()
        graph.add_edge("a", "b")
        graph.nodes["a"]["color"] = "red"
        graph.nodes["b"]["color"] = "red"

        expected_graph = nx.Graph()
        expected_graph.add_edge("a", "b")
        expected_graph.nodes["a"]["color"] = "red"
        expected_graph.nodes["b"]["color"] = "red"

        expected = nx.attribute_assortativity_coefficient(expected_graph, "color")
        actual = fnx.attribute_assortativity_coefficient(graph, "color")

        assert math.isnan(expected)
        assert math.isnan(actual)

    @needs_nx
    def test_numeric_assortativity_missing_attribute_matches_networkx_error(self):
        graph = fnx.path_graph(3)
        expected_graph = nx.path_graph(3)

        with pytest.raises(KeyError):
            nx.numeric_assortativity_coefficient(expected_graph, "missing")
        with pytest.raises(KeyError):
            fnx.numeric_assortativity_coefficient(graph, "missing")

    @needs_nx
    def test_all_pairs_node_connectivity_matches_networkx(self):
        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)

        assert fnx.all_pairs_node_connectivity(graph) == nx.all_pairs_node_connectivity(
            expected_graph
        )

    @needs_nx
    def test_degree_pearson_and_generalized_degree_match_networkx(self):
        math = pytest.importorskip("math")
        digraph = fnx.DiGraph()
        digraph.add_edge(0, 1)
        digraph.add_edge(2, 1)
        digraph.add_edge(2, 3)

        expected_digraph = nx.DiGraph()
        expected_digraph.add_edge(0, 1)
        expected_digraph.add_edge(2, 1)
        expected_digraph.add_edge(2, 3)

        graph = fnx.Graph()
        graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

        expected_graph = nx.Graph()
        expected_graph.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3)])

        actual_corr = fnx.degree_pearson_correlation_coefficient(
            digraph,
            x="in",
            y="out",
        )
        expected_corr = nx.degree_pearson_correlation_coefficient(
            expected_digraph,
            x="in",
            y="out",
        )
        if math.isnan(expected_corr):
            assert math.isnan(actual_corr)
        else:
            assert actual_corr == expected_corr
        assert fnx.generalized_degree(graph) == nx.generalized_degree(expected_graph)

    @needs_nx
    def test_load_centrality_matches_networkx_weighted_contract(self):
        graph = fnx.MultiGraph()
        graph.add_edge(0, 1, key=7, weight=2)
        graph.add_edge(2, 1, key=8, weight=3)
        graph.add_edge(2, 3, key=9, weight=4)

        expected_graph = nx.MultiGraph()
        expected_graph.add_edge(0, 1, key=7, weight=2)
        expected_graph.add_edge(2, 1, key=8, weight=3)
        expected_graph.add_edge(2, 3, key=9, weight=4)

        assert fnx.load_centrality(graph, normalized=False, weight="weight") == nx.load_centrality(
            expected_graph,
            normalized=False,
            weight="weight",
        )

    def test_backend_can_run_rejects_incompatible_signatures(self):
        from franken_networkx.backend import BackendInterface

        graph = fnx.path_graph(4)

        assert BackendInterface.can_run("shortest_path", (graph,), {})
        assert not BackendInterface.can_run("shortest_path", (), {})
        assert not BackendInterface.can_run("node_connectivity", (graph, 0, 3), {})
        assert (
            not BackendInterface.can_run(
                "average_shortest_path_length",
                (graph,),
                {"method": "dijkstra"},
            )
        )
        assert BackendInterface.should_run("shortest_path", (graph,), {})
        assert not BackendInterface.should_run("shortest_path", (), {})
        assert not BackendInterface.should_run("node_connectivity", (graph, 0, 3), {})
        assert (
            not BackendInterface.should_run(
                "average_shortest_path_length",
                (graph,),
                {"method": "dijkstra"},
            )
        )

    @needs_nx
    def test_harary_and_havel_hakimi_wrappers_match_networkx(self):
        hakimi = fnx.havel_hakimi_graph([3, 3, 2, 2, 2], create_using=fnx.Graph())
        expected_hakimi = nx.havel_hakimi_graph([3, 3, 2, 2, 2], create_using=nx.Graph())
        hkn = fnx.hkn_harary_graph(2, 6, create_using=fnx.Graph())
        expected_hkn = nx.hkn_harary_graph(2, 6, create_using=nx.Graph())
        hnm = fnx.hnm_harary_graph(6, 6, create_using=fnx.Graph())
        expected_hnm = nx.hnm_harary_graph(6, 6, create_using=nx.Graph())

        assert sorted(hakimi.edges()) == sorted(expected_hakimi.edges())
        assert sorted(hkn.edges()) == sorted(expected_hkn.edges())
        assert sorted(hnm.edges()) == sorted(expected_hnm.edges())

    @needs_nx
    def test_barabasi_albert_supports_initial_graph_fallback(self):
        initial = fnx.path_graph(3)
        expected_initial = nx.path_graph(3)

        graph = fnx.barabasi_albert_graph(6, 1, seed=42, initial_graph=initial)
        expected = nx.barabasi_albert_graph(6, 1, seed=42, initial_graph=expected_initial)

        assert sorted(graph.edges()) == sorted(expected.edges())

    @needs_nx
    def test_grid_2d_graph_supports_periodic_fallback(self):
        graph = fnx.grid_2d_graph(2, 3, periodic=True)
        expected = nx.grid_2d_graph(2, 3, periodic=True)

        assert sorted(graph.edges()) == sorted(expected.edges())

    def test_gnp_random_graph_supports_directed_fallback(self):
        directed = fnx.gnp_random_graph(8, 0.2, seed=42, directed=True)
        er_directed = fnx.erdos_renyi_graph(8, 0.2, seed=42, directed=True)
        fast_directed = fnx.fast_gnp_random_graph(8, 0.2, seed=42, directed=True)

        assert directed.is_directed()
        assert er_directed.is_directed()
        assert fast_directed.is_directed()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class TestMisc:
    def test_non_neighbors(self):
        G = fnx.path_graph(4)
        nn = list(fnx.non_neighbors(G, 0))
        assert 2 in nn
        assert 3 in nn
        assert 1 not in nn  # 1 IS a neighbor

    def test_number_of_cliques(self):
        G = fnx.complete_graph(4)
        nc = fnx.number_of_cliques(G)
        assert isinstance(nc, (dict, int))

    @needs_nx
    def test_maximum_spanning_tree(self):
        G = fnx.Graph()
        G.add_edge(0, 1, weight=1.0)
        G.add_edge(1, 2, weight=3.0)
        G.add_edge(0, 2, weight=2.0)
        mst = fnx.maximum_spanning_tree(G)
        assert mst.number_of_edges() == 2


class TestDelegateFixes:
    @needs_nx
    def test_graph_operator_batches_delegate(self):
        empty_cases = [
            ("compose_all", fnx.compose_all, nx.compose_all),
            ("union_all", fnx.union_all, nx.union_all),
            ("intersection_all", fnx.intersection_all, nx.intersection_all),
            ("disjoint_union_all", fnx.disjoint_union_all, nx.disjoint_union_all),
        ]
        for _, fnx_func, nx_func in empty_cases:
            with pytest.raises(ValueError):
                nx_func([])
            with pytest.raises(ValueError):
                fnx_func([])

        left = fnx.MultiGraph()
        left.graph["left"] = 1
        left.add_node("a", color="red")
        left.add_edge("a", "b", key=7, weight=2)

        right = fnx.MultiGraph()
        right.graph["right"] = 2
        right.add_node("c", color="blue")
        right.add_edge("c", "d", key=3, cost=4)

        left_nx = nx.MultiGraph()
        left_nx.graph["left"] = 1
        left_nx.add_node("a", color="red")
        left_nx.add_edge("a", "b", key=7, weight=2)

        right_nx = nx.MultiGraph()
        right_nx.graph["right"] = 2
        right_nx.add_node("c", color="blue")
        right_nx.add_edge("c", "d", key=3, cost=4)

        composed = fnx.compose_all([left, right])
        composed_nx = nx.compose_all([left_nx, right_nx])
        assert composed.is_multigraph()
        assert dict(composed.graph) == composed_nx.graph
        assert sorted(composed.edges(keys=True, data=True)) == sorted(
            composed_nx.edges(keys=True, data=True)
        )

        unioned = fnx.union_all([left, right], rename=("L-", "R-"))
        unioned_nx = nx.union_all([left_nx, right_nx], rename=("L-", "R-"))
        assert unioned.is_multigraph()
        assert dict(unioned.graph) == unioned_nx.graph
        assert sorted(unioned.edges(keys=True, data=True)) == sorted(
            unioned_nx.edges(keys=True, data=True)
        )

        disjoint = fnx.disjoint_union_all([left, right])
        disjoint_nx = nx.disjoint_union_all([left_nx, right_nx])
        assert disjoint.is_multigraph()
        assert dict(disjoint.graph) == disjoint_nx.graph
        assert sorted(disjoint.edges(keys=True, data=True)) == sorted(
            disjoint_nx.edges(keys=True, data=True)
        )

    @needs_nx
    def test_conversion_helpers_preserve_multigraph_keys_and_graph_attrs(self):
        graph_nx = nx.MultiGraph()
        graph_nx.graph["name"] = "demo"
        graph_nx.add_edge("a", "b", key=9, weight=4)

        converted = fnx.readwrite._from_nx_graph(graph_nx)
        assert dict(converted.graph) == graph_nx.graph
        assert sorted(converted["a"]["b"].keys()) == [9]

        roundtrip = fnx.drawing.layout._to_nx(converted)
        assert roundtrip.graph == graph_nx.graph
        assert sorted(roundtrip["a"]["b"].keys()) == [9]

    @needs_nx
    def test_disjoint_union_and_relabel_helpers_delegate(self):
        left = fnx.MultiGraph()
        left.graph["left"] = 1
        left.add_edge("a", "b", key=7, weight=2)

        right = fnx.MultiGraph()
        right.graph["right"] = 2
        right.add_edge("c", "d", key=3, cost=4)

        left_nx = nx.MultiGraph()
        left_nx.graph["left"] = 1
        left_nx.add_edge("a", "b", key=7, weight=2)

        right_nx = nx.MultiGraph()
        right_nx.graph["right"] = 2
        right_nx.add_edge("c", "d", key=3, cost=4)

        disjoint = fnx.disjoint_union(left, right)
        disjoint_nx = nx.disjoint_union(left_nx, right_nx)
        assert disjoint.is_multigraph()
        assert dict(disjoint.graph) == disjoint_nx.graph
        assert sorted(disjoint.edges(keys=True, data=True)) == sorted(
            disjoint_nx.edges(keys=True, data=True)
        )

        graph = fnx.Graph()
        graph.graph["name"] = "base"
        graph.add_edge("a", "b", weight=1)

        relabeled = fnx.relabel_nodes(graph, {"a": "x"})
        relabeled_nx = nx.relabel_nodes(nx.Graph([("a", "b", {"weight": 1})]), {"a": "x"})
        relabeled_nx.graph["name"] = "base"
        assert dict(relabeled.graph) == dict(graph.graph)
        assert sorted((frozenset((u, v)), data) for u, v, data in relabeled.edges(data=True)) == sorted(
            (frozenset((u, v)), data) for u, v, data in relabeled_nx.edges(data=True)
        )

        converted = fnx.convert_node_labels_to_integers(graph, label_attribute="old")
        converted_nx = nx.convert_node_labels_to_integers(
            nx.Graph([("a", "b", {"weight": 1})]),
            label_attribute="old",
        )
        converted_nx.graph["name"] = "base"
        assert dict(converted.graph) == dict(graph.graph)
        assert sorted(converted.edges(data=True)) == sorted(converted_nx.edges(data=True))
        assert sorted(converted.nodes(data=True)) == sorted(converted_nx.nodes(data=True))

    @needs_nx
    def test_line_graph_reverse_and_empty_copy_delegate(self):
        graph = fnx.MultiGraph()
        graph.graph["name"] = "multi"
        graph.add_edge("a", "b", key=5, weight=2)

        graph_nx = nx.MultiGraph()
        graph_nx.graph["name"] = "multi"
        graph_nx.add_edge("a", "b", key=5, weight=2)

        line = fnx.line_graph(graph)
        line_nx = nx.line_graph(graph_nx)
        assert type(line).__name__ == type(line_nx).__name__
        assert sorted(line.nodes(data=True)) == sorted(line_nx.nodes(data=True))
        assert sorted(line.edges(data=True)) == sorted(line_nx.edges(data=True))

        empty = fnx.create_empty_copy(graph)
        empty_nx = nx.create_empty_copy(graph_nx)
        assert dict(empty.graph) == empty_nx.graph
        assert sorted(empty.nodes(data=True)) == sorted(empty_nx.nodes(data=True))
        assert empty.number_of_edges() == empty_nx.number_of_edges()

        digraph = fnx.MultiDiGraph()
        digraph.graph["kind"] = "digraph"
        digraph.add_edge("u", "v", key=9, capacity=4)

        digraph_nx = nx.MultiDiGraph()
        digraph_nx.graph["kind"] = "digraph"
        digraph_nx.add_edge("u", "v", key=9, capacity=4)

        reversed_graph = fnx.reverse(digraph)
        reversed_nx = nx.reverse(digraph_nx)
        assert dict(reversed_graph.graph) == reversed_nx.graph
        assert sorted(reversed_graph.edges(keys=True, data=True)) == sorted(
            reversed_nx.edges(keys=True, data=True)
        )

    @needs_nx
    def test_directed_undirected_conversion_and_freeze_delegate(self):
        graph = fnx.MultiGraph()
        graph.graph["name"] = "base"
        graph.add_node("a", color="red")
        graph.add_edge("a", "b", key=4, weight=2)

        graph_nx = nx.MultiGraph()
        graph_nx.graph["name"] = "base"
        graph_nx.add_node("a", color="red")
        graph_nx.add_edge("a", "b", key=4, weight=2)

        directed = fnx.to_directed(graph)
        directed_nx = nx.to_directed(graph_nx)
        assert directed.is_directed()
        assert directed.is_multigraph()
        assert dict(directed.graph) == directed_nx.graph
        assert sorted(directed.nodes(data=True)) == sorted(directed_nx.nodes(data=True))
        assert sorted(directed.edges(keys=True, data=True)) == sorted(
            directed_nx.edges(keys=True, data=True)
        )

        undirected = fnx.to_undirected(directed)
        undirected_nx = nx.to_undirected(directed_nx)
        assert not undirected.is_directed()
        assert undirected.is_multigraph()
        assert dict(undirected.graph) == undirected_nx.graph
        assert sorted(undirected.nodes(data=True)) == sorted(undirected_nx.nodes(data=True))
        assert sorted(undirected.edges(keys=True, data=True)) == sorted(
            undirected_nx.edges(keys=True, data=True)
        )

        frozen = fnx.freeze(fnx.Graph())
        assert frozen is not None
        assert fnx.is_frozen(frozen)
        with pytest.raises(fnx.NetworkXError, match="Frozen graph can't be modified"):
            frozen.add_edge(1, 2)

    @needs_nx
    def test_graph_products_delegate_for_multigraph_attrs(self):
        left = fnx.MultiGraph()
        left.add_node(0, a1=True)
        left.add_edge(0, 1, key=7, w=2)

        right = fnx.MultiGraph()
        right.add_node("a", a2="Spam")
        right.add_edge("a", "b", key=3, c=4)

        left_nx = nx.MultiGraph()
        left_nx.add_node(0, a1=True)
        left_nx.add_edge(0, 1, key=7, w=2)

        right_nx = nx.MultiGraph()
        right_nx.add_node("a", a2="Spam")
        right_nx.add_edge("a", "b", key=3, c=4)

        for name in (
            "cartesian_product",
            "tensor_product",
            "strong_product",
            "lexicographic_product",
        ):
            graph = getattr(fnx, name)(left, right)
            expected = getattr(nx, name)(left_nx, right_nx)

            assert graph.is_multigraph()
            assert sorted(graph.nodes(data=True)) == sorted(expected.nodes(data=True))
            assert sorted((u, v, data) for u, v, _, data in graph.edges(keys=True, data=True)) == sorted(
                (u, v, data) for u, v, _, data in expected.edges(keys=True, data=True)
            )

    @needs_nx
    def test_corona_rooted_and_modular_products_delegate(self):
        def canonical_nodes(graph):
            return sorted(
                ((repr(node), node_data) for node, node_data in graph.nodes(data=True)),
                key=lambda item: item[0],
            )

        def canonical_edges(graph):
            return sorted(
                (
                    tuple(sorted((repr(u), repr(v)))),
                    edge_data,
                )
                for u, v, edge_data in graph.edges(data=True)
            )

        left = fnx.Graph()
        left.add_node(0, color="red")
        left.add_edge(0, 1, weight=2)

        right = fnx.Graph()
        right.add_node("a", label="A")
        right.add_edge("a", "b", cost=3)

        left_nx = nx.Graph()
        left_nx.add_node(0, color="red")
        left_nx.add_edge(0, 1, weight=2)

        right_nx = nx.Graph()
        right_nx.add_node("a", label="A")
        right_nx.add_edge("a", "b", cost=3)

        corona = fnx.corona_product(left, right)
        corona_nx = nx.corona_product(left_nx, right_nx)
        assert canonical_nodes(corona) == canonical_nodes(corona_nx)
        assert canonical_edges(corona) == canonical_edges(corona_nx)

        rooted = fnx.rooted_product(left, right, "a")
        rooted_nx = nx.rooted_product(left_nx, right_nx, "a")
        assert canonical_nodes(rooted) == canonical_nodes(rooted_nx)
        assert canonical_edges(rooted) == canonical_edges(rooted_nx)

        modular = fnx.modular_product(left, right)
        modular_nx = nx.modular_product(left_nx, right_nx)
        assert canonical_nodes(modular) == canonical_nodes(modular_nx)
        assert canonical_edges(modular) == canonical_edges(modular_nx)

    @needs_nx
    def test_from_nx_graph_handles_non_integer_multigraph_keys(self):
        graph_nx = nx.MultiGraph()
        graph_nx.add_edge("a", "b", key=("left", "right"), weight=7)

        converted = fnx.readwrite._from_nx_graph(graph_nx)

        assert converted.is_multigraph()
        assert converted.number_of_edges("a", "b") == 1
        assert next(iter(converted["a"]["b"].values()))["weight"] == 7

    @needs_nx
    def test_graph_atlas_helpers_match_networkx(self):
        atlas = fnx.graph_atlas(6)
        atlas_nx = nx.graph_atlas(6)

        assert sorted(atlas.edges()) == sorted(atlas_nx.edges())
        assert len(fnx.graph_atlas_g()) == len(nx.graph_atlas_g())

    @needs_nx
    def test_random_shell_and_clustered_generators_delegate(self):
        shell = fnx.random_shell_graph([(4, 8, 0.8)], seed=1)
        shell_nx = nx.random_shell_graph([(4, 8, 0.8)], seed=1)
        clustered_sequence = [(1, 0), (1, 0), (1, 0), (1, 0)]
        clustered = fnx.random_clustered_graph(clustered_sequence, seed=1)
        clustered_nx = nx.random_clustered_graph(clustered_sequence, seed=1)

        assert sorted(shell.edges()) == sorted(shell_nx.edges())
        assert clustered.number_of_nodes() == clustered_nx.number_of_nodes()
        assert clustered.number_of_edges() == clustered_nx.number_of_edges()

    @needs_nx
    def test_spectral_graph_forge_and_edit_distance_delegate(self):
        graph = fnx.path_graph(5)
        forged = fnx.spectral_graph_forge(graph, alpha=0.5, seed=1)
        forged_nx = nx.spectral_graph_forge(nx.path_graph(5), alpha=0.5, seed=1)

        assert forged.number_of_nodes() == forged_nx.number_of_nodes()
        assert fnx.graph_edit_distance(fnx.path_graph(3), fnx.path_graph(4)) == nx.graph_edit_distance(
            nx.path_graph(3), nx.path_graph(4)
        )
        assert fnx.optimal_edit_paths(fnx.path_graph(3), fnx.path_graph(3))[1] == 0
        assert next(fnx.optimize_edit_paths(fnx.path_graph(3), fnx.path_graph(3)))[2] == 0

    @needs_nx
    def test_embedding_and_matplotlib_color_helpers_delegate(self):
        embedding = nx.PlanarEmbedding()
        embedding.add_half_edge_cw(0, 1, None)
        embedding.add_half_edge_cw(1, 0, None)
        embedding.add_half_edge_cw(1, 2, 0)
        embedding.add_half_edge_cw(2, 1, None)
        embedding.check_structure()

        pos = fnx.combinatorial_embedding_to_pos(embedding)
        assert set(pos) == {0, 1, 2}

        mpl = pytest.importorskip("matplotlib")
        graph = fnx.path_graph(3)
        for node, value in enumerate([0.0, 0.5, 1.0]):
            graph.nodes[node]["score"] = value
        fnx.apply_matplotlib_colors(graph, "score", "rgba", mpl.cm.viridis)
        assert "rgba" in graph.nodes[0]

    @needs_nx
    def test_equitable_coloring_and_goldberg_radzik_delegate(self):
        coloring = fnx.equitable_color(fnx.cycle_graph(4), 3)
        expected_coloring = nx.equitable_color(nx.cycle_graph(4), 3)

        assert coloring == expected_coloring

        graph = fnx.DiGraph()
        graph.add_weighted_edges_from([(0, 1, 1), (1, 2, -2), (0, 2, 4)])
        expected_graph = nx.DiGraph()
        expected_graph.add_weighted_edges_from([(0, 1, 1), (1, 2, -2), (0, 2, 4)])
        expected = nx.goldberg_radzik(expected_graph, 0)

        assert fnx.goldberg_radzik(graph, 0) == expected

    @needs_nx
    def test_random_degree_sequence_and_edit_distance_iter_delegate(self):
        sequence = [2, 2, 2, 2]
        graph = fnx.random_degree_sequence_graph(sequence, seed=1)
        expected = nx.random_degree_sequence_graph(sequence, seed=1)

        assert sorted(graph.degree[node] for node in graph.nodes()) == sorted(
            degree for _, degree in expected.degree()
        )
        assert list(fnx.optimize_graph_edit_distance(fnx.path_graph(3), fnx.path_graph(3))) == list(
            nx.optimize_graph_edit_distance(nx.path_graph(3), nx.path_graph(3))
        )

    @needs_nx
    def test_neighbors_and_describe_delegate(self, capsys):
        graph = fnx.path_graph(3)
        expected_graph = nx.path_graph(3)

        neighbors = fnx.neighbors(graph, 1)
        assert iter(neighbors) is neighbors
        assert tuple(neighbors) == tuple(nx.neighbors(expected_graph, 1))
        assert fnx.describe(graph) is None

        out = capsys.readouterr().out
        nx.describe(expected_graph)
        expected_out = capsys.readouterr().out
        assert out == expected_out

    @needs_nx
    def test_mixing_panther_and_resistance_helpers_delegate(self):
        assert fnx.mixing_dict([(1, 2), (1, 2), (2, 3)], normalized=True) == nx.mixing_dict(
            [(1, 2), (1, 2), (2, 3)],
            normalized=True,
        )

        graph = fnx.path_graph(4)
        expected_graph = nx.path_graph(4)
        assert fnx.communicability_exp(graph) == nx.communicability_exp(expected_graph)
        assert fnx.effective_graph_resistance(graph) == nx.effective_graph_resistance(expected_graph)
        assert fnx.panther_similarity(graph, 0, k=3, seed=1) == nx.panther_similarity(
            expected_graph,
            0,
            k=3,
            seed=1,
        )

        with pytest.raises(nx.NetworkXUnfeasible):
            fnx.panther_vector_similarity(graph, 0, k=5, seed=1)

        assert fnx.panther_vector_similarity(graph, 0, D=3, k=3, seed=1) == nx.panther_vector_similarity(
            expected_graph,
            0,
            D=3,
            k=3,
            seed=1,
        )
