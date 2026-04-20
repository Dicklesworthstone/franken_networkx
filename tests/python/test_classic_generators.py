"""Tests for classic graph generator bindings.

Tests cover node/edge counts for all named and parametric generators.
"""

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Named graphs
# ---------------------------------------------------------------------------

class TestNamedGraphs:
    def test_bull_graph(self):
        g = fnx.bull_graph()
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 5

    def test_chvatal_graph(self):
        g = fnx.chvatal_graph()
        assert g.number_of_nodes() == 12
        assert g.number_of_edges() == 24

    def test_cubical_graph(self):
        g = fnx.cubical_graph()
        assert g.number_of_nodes() == 8
        assert g.number_of_edges() == 12

    def test_desargues_graph(self):
        g = fnx.desargues_graph()
        assert g.number_of_nodes() == 20
        assert g.number_of_edges() == 30

    def test_diamond_graph(self):
        g = fnx.diamond_graph()
        assert g.number_of_nodes() == 4
        assert g.number_of_edges() == 5

    def test_dodecahedral_graph(self):
        g = fnx.dodecahedral_graph()
        assert g.number_of_nodes() == 20
        assert g.number_of_edges() == 30

    def test_frucht_graph(self):
        g = fnx.frucht_graph()
        assert g.number_of_nodes() == 12
        assert g.number_of_edges() == 18

    def test_heawood_graph(self):
        g = fnx.heawood_graph()
        assert g.number_of_nodes() == 14
        assert g.number_of_edges() == 21

    def test_house_graph(self):
        g = fnx.house_graph()
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 6

    def test_house_x_graph(self):
        g = fnx.house_x_graph()
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 8

    def test_icosahedral_graph(self):
        g = fnx.icosahedral_graph()
        assert g.number_of_nodes() == 12
        assert g.number_of_edges() == 30

    def test_krackhardt_kite_graph(self):
        g = fnx.krackhardt_kite_graph()
        assert g.number_of_nodes() == 10
        assert g.number_of_edges() == 18

    def test_moebius_kantor_graph(self):
        g = fnx.moebius_kantor_graph()
        assert g.number_of_nodes() == 16
        assert g.number_of_edges() == 24

    def test_octahedral_graph(self):
        g = fnx.octahedral_graph()
        assert g.number_of_nodes() == 6
        assert g.number_of_edges() == 12

    def test_pappus_graph(self):
        g = fnx.pappus_graph()
        assert g.number_of_nodes() == 18
        assert g.number_of_edges() == 27

    def test_petersen_graph(self):
        g = fnx.petersen_graph()
        assert g.number_of_nodes() == 10
        assert g.number_of_edges() == 15

    def test_sedgewick_maze_graph(self):
        g = fnx.sedgewick_maze_graph()
        assert g.number_of_nodes() == 8
        assert g.number_of_edges() == 10

    def test_tetrahedral_graph(self):
        g = fnx.tetrahedral_graph()
        assert g.number_of_nodes() == 4
        assert g.number_of_edges() == 6

    def test_truncated_cube_graph(self):
        g = fnx.truncated_cube_graph()
        assert g.number_of_nodes() == 24
        assert g.number_of_edges() == 36

    def test_truncated_tetrahedron_graph(self):
        g = fnx.truncated_tetrahedron_graph()
        assert g.number_of_nodes() == 12
        assert g.number_of_edges() == 18

    def test_tutte_graph(self):
        g = fnx.tutte_graph()
        assert g.number_of_nodes() == 46
        assert g.number_of_edges() == 69

    def test_hoffman_singleton_graph(self):
        g = fnx.hoffman_singleton_graph()
        assert g.number_of_nodes() == 50
        assert g.number_of_edges() == 175


# ---------------------------------------------------------------------------
# Parametric generators
# ---------------------------------------------------------------------------

class TestParametricGenerators:
    def test_balanced_tree(self):
        g = fnx.balanced_tree(2, 3)
        assert g.number_of_nodes() == 15
        assert g.number_of_edges() == 14

    def test_barbell_graph(self):
        g = fnx.barbell_graph(3, 2)
        assert g.number_of_nodes() == 8

    def test_generalized_petersen_graph(self):
        g = fnx.generalized_petersen_graph(5, 2)
        assert g.number_of_nodes() == 10
        assert g.number_of_edges() == 15

    def test_wheel_graph(self):
        g = fnx.wheel_graph(5)
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 8

    def test_ladder_graph(self):
        g = fnx.ladder_graph(4)
        assert g.number_of_nodes() == 8
        assert g.number_of_edges() == 10

    def test_circular_ladder_graph(self):
        g = fnx.circular_ladder_graph(4)
        assert g.number_of_nodes() == 8
        assert g.number_of_edges() == 12

    def test_lollipop_graph(self):
        g = fnx.lollipop_graph(4, 3)
        assert g.number_of_nodes() == 7
        assert g.number_of_edges() == 9

    def test_tadpole_graph(self):
        g = fnx.tadpole_graph(4, 3)
        assert g.number_of_nodes() == 7
        assert g.number_of_edges() == 7

    def test_turan_graph(self):
        g = fnx.turan_graph(6, 3)
        assert g.number_of_nodes() == 6
        assert g.number_of_edges() == 12

    def test_windmill_graph(self):
        g = fnx.windmill_graph(3, 4)
        assert g.number_of_nodes() == 10

    def test_hypercube_graph(self):
        g = fnx.hypercube_graph(3)
        assert g.number_of_nodes() == 8
        assert g.number_of_edges() == 12

    def test_complete_bipartite_graph(self):
        g = fnx.complete_bipartite_graph(3, 4)
        assert g.number_of_nodes() == 7
        assert g.number_of_edges() == 12

    def test_complete_multipartite_graph(self):
        # Each positional arg is one partition (matching NetworkX). Pass
        # sizes as separate ints, not a single list of ints.
        g = fnx.complete_multipartite_graph(2, 2, 2)
        assert g.number_of_nodes() == 6
        assert g.number_of_edges() == 12
        assert sorted(g.nodes[n]["subset"] for n in g.nodes()) == [0, 0, 1, 1, 2, 2]

    def test_grid_2d_graph(self):
        g = fnx.grid_2d_graph(3, 4)
        assert g.number_of_nodes() == 12
        assert g.number_of_edges() == 17

    def test_null_graph(self):
        g = fnx.null_graph()
        assert g.number_of_nodes() == 0

    def test_trivial_graph(self):
        g = fnx.trivial_graph()
        assert g.number_of_nodes() == 1
        assert g.number_of_edges() == 0

    def test_binomial_tree(self):
        g = fnx.binomial_tree(3)
        assert g.number_of_nodes() == 8
        assert g.number_of_edges() == 7

    def test_full_rary_tree(self):
        g = fnx.full_rary_tree(2, 7)
        assert g.number_of_nodes() == 7
        assert g.number_of_edges() == 6

    def test_circulant_graph(self):
        g = fnx.circulant_graph(6, [1, 2])
        assert g.number_of_nodes() == 6
        assert g.number_of_edges() == 12

    def test_kneser_graph_petersen(self):
        g = fnx.kneser_graph(5, 2)
        assert g.number_of_nodes() == 10
        assert g.number_of_edges() == 15

    def test_paley_graph(self):
        g = fnx.paley_graph(5)
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 5

    def test_chordal_cycle_graph(self):
        g = fnx.chordal_cycle_graph(6)
        assert g.number_of_nodes() == 6
        assert g.number_of_edges() == 12

    def test_petersen_is_connected(self):
        g = fnx.petersen_graph()
        assert fnx.is_connected(g)

    def test_wheel_is_connected(self):
        g = fnx.wheel_graph(6)
        assert fnx.is_connected(g)


try:
    import networkx as _nx_import

    _HAS_NX = True
except ImportError:  # pragma: no cover - nx is an optional oracle here
    _HAS_NX = False


import pytest


@pytest.mark.skipif(not _HAS_NX, reason="networkx not installed")
class TestCompleteMultipartiteGraphParity:
    @pytest.mark.parametrize(
        "sizes",
        [(2, 2), (3, 2, 1), (4,), (1, 1, 1, 1), (0, 2, 3), (), (0, 0, 0)],
    )
    def test_sizes_only_matches_networkx(self, sizes):
        import networkx as nx

        expected = nx.complete_multipartite_graph(*sizes)
        actual = fnx.complete_multipartite_graph(*sizes)
        assert actual.number_of_nodes() == expected.number_of_nodes()
        assert actual.number_of_edges() == expected.number_of_edges()
        expected_attrs = {n: expected.nodes[n].get("subset") for n in expected.nodes()}
        actual_attrs = {n: actual.nodes[n].get("subset") for n in actual.nodes()}
        assert actual_attrs == expected_attrs

    def test_iterable_partitions_label_nodes_and_set_subset(self):
        import networkx as nx

        expected = nx.complete_multipartite_graph(["a", "b"], ["c", "d", "e"])
        actual = fnx.complete_multipartite_graph(["a", "b"], ["c", "d", "e"])
        assert set(actual.nodes()) == set(expected.nodes())
        for node in expected.nodes():
            assert actual.nodes[node]["subset"] == expected.nodes[node]["subset"]
        assert actual.number_of_edges() == expected.number_of_edges()

    def test_strings_are_treated_as_node_iterables(self):
        import networkx as nx

        expected = nx.complete_multipartite_graph("a", "bc", "def")
        actual = fnx.complete_multipartite_graph("a", "bc", "def")
        assert set(actual.nodes()) == set(expected.nodes())
        assert actual.number_of_edges() == expected.number_of_edges()

    def test_single_iterable_arg_is_one_partition_not_unpacked(self):
        import networkx as nx

        expected = nx.complete_multipartite_graph([1, 2, 3])
        actual = fnx.complete_multipartite_graph([1, 2, 3])
        assert set(actual.nodes()) == set(expected.nodes()) == {1, 2, 3}
        assert actual.number_of_edges() == 0
        assert [actual.nodes[n]["subset"] for n in sorted(actual.nodes())] == [0, 0, 0]

    @pytest.mark.parametrize("args", [(2, ["a", "b"]), (["x"], 3), (1, "ab")])
    def test_mixed_int_and_iterable_rejected(self, args):
        with pytest.raises(fnx.NetworkXError):
            fnx.complete_multipartite_graph(*args)

    def test_negative_size_rejected(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.complete_multipartite_graph(2, -1, 3)

    def test_subset_attribute_is_present_for_every_node(self):
        g = fnx.complete_multipartite_graph(3, 2, 1)
        assert all("subset" in g.nodes[n] for n in g.nodes())
