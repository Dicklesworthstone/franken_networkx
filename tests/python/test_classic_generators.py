"""Tests for classic graph generator bindings.

Tests cover node/edge counts for all named and parametric generators.
"""

import pytest

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
        # br-paleydir: paley_graph default return type is DiGraph (per nx).
        # For p=5 (≡1 mod 4): each node has 2 out-neighbors via {1, 4},
        # giving 10 directed edges total.
        g = fnx.paley_graph(5)
        assert g.is_directed()
        assert g.number_of_nodes() == 5
        assert g.number_of_edges() == 10

    def test_chordal_cycle_graph(self):
        # br-chordalmg: chordal_cycle_graph default return type is
        # MultiGraph (per nx). 6 nodes × 3 edges per node (left, right,
        # chord) = 18 total edge additions.
        g = fnx.chordal_cycle_graph(6)
        assert g.is_multigraph()
        assert g.number_of_nodes() == 6
        assert g.number_of_edges() == 18

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


@pytest.mark.skipif(not _HAS_NX, reason="networkx not installed")
class TestRandomGeometricGraphParity:
    @pytest.mark.parametrize("p", [1, 2, 3, float("inf")])
    def test_minkowski_p_matches_networkx(self, p):
        import networkx as nx

        pos = {i: (i * 0.1, (i * 0.17) % 1.0) for i in range(25)}
        expected = nx.random_geometric_graph(25, 0.25, pos=pos, p=p)
        actual = fnx.random_geometric_graph(25, 0.25, pos=pos, p=p)
        assert {tuple(sorted(e)) for e in expected.edges()} == {
            tuple(sorted(e)) for e in actual.edges()
        }

    def test_positions_stored_under_custom_pos_name(self):
        g = fnx.random_geometric_graph(10, 0.2, seed=7, pos_name="xy")
        assert all("xy" in g.nodes[n] for n in g.nodes())
        assert all("pos" not in g.nodes[n] for n in g.nodes())

    def test_chebyshev_distance_inf(self):
        # Square corners — all pairs are within chebyshev radius 1.
        import networkx as nx

        pos = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}
        expected = nx.random_geometric_graph(4, 1.0, pos=pos, p=float("inf"))
        actual = fnx.random_geometric_graph(4, 1.0, pos=pos, p=float("inf"))
        assert {tuple(sorted(e)) for e in actual.edges()} == {
            tuple(sorted(e)) for e in expected.edges()
        }
        assert actual.number_of_edges() == 6  # complete graph on 4 nodes


@pytest.mark.skipif(not _HAS_NX, reason="networkx not installed")
class TestGeometricEdgesParity:
    @pytest.fixture
    def square(self):
        points = [(0, 0), (1, 0), (1, 1), (0, 1)]
        G = fnx.Graph()
        for i, xy in enumerate(points):
            G.add_node(i, pos=xy)
        return G

    def test_returns_list_and_does_not_mutate_graph(self, square):
        before = square.number_of_edges()
        result = fnx.geometric_edges(square, radius=1.5)
        assert isinstance(result, list)
        assert square.number_of_edges() == before  # caller controls mutation

    def test_matches_networkx_edge_list(self):
        import networkx as nx

        points = [(0, 0), (3, 0), (8, 0)]
        G_fn = fnx.Graph()
        G_nx = nx.Graph()
        for i, xy in enumerate(points):
            G_fn.add_node(i, pos=xy)
            G_nx.add_node(i, pos=xy)
        for r in (1, 4, 6, 9):
            assert sorted(fnx.geometric_edges(G_fn, radius=r)) == sorted(
                nx.geometric_edges(G_nx, radius=r)
            )

    def test_missing_pos_raises_networkx_error(self):
        G = fnx.Graph()
        G.add_nodes_from([0, 1])  # no pos attribute
        with pytest.raises(fnx.NetworkXError):
            fnx.geometric_edges(G, radius=1.0)

    def test_pos_name_kwarg_is_honored(self):
        import networkx as nx

        G_fn = fnx.Graph()
        G_nx = nx.Graph()
        G_fn.add_nodes_from([(0, {"xy": (0, 0)}), (1, {"xy": (1, 0)})])
        G_nx.add_nodes_from([(0, {"xy": (0, 0)}), (1, {"xy": (1, 0)})])
        assert fnx.geometric_edges(G_fn, radius=1.5, pos_name="xy") == (
            nx.geometric_edges(G_nx, radius=1.5, pos_name="xy")
        )

    @pytest.mark.parametrize("p", [1, 2, float("inf")])
    def test_minkowski_p_matches_networkx(self, p, square):
        import networkx as nx

        G_nx = nx.Graph()
        for n in square.nodes():
            G_nx.add_node(n, pos=square.nodes[n]["pos"])
        assert sorted(fnx.geometric_edges(square, radius=1.1, p=p)) == sorted(
            nx.geometric_edges(G_nx, radius=1.1, p=p)
        )


# ---------------------------------------------------------------------------
# Watts-Strogatz backend keyword surface (franken_networkx-h1bp)
# ---------------------------------------------------------------------------


class TestWattsStrogatzBackendKeyword:
    """watts_strogatz_graph and newman_watts_strogatz_graph must accept
    NetworkX's backend dispatch keyword surface (backend, **backend_kwargs)
    and raise ImportError on unknown backends matching upstream behaviour.
    """

    def test_default_backend_runs_in_tree(self):
        g = fnx.watts_strogatz_graph(10, 4, 0.1)
        assert g.number_of_nodes() == 10
        g = fnx.newman_watts_strogatz_graph(10, 4, 0.1)
        assert g.number_of_nodes() == 10

    @pytest.mark.parametrize("backend", [None, "networkx"])
    def test_explicit_supported_backend_runs_in_tree(self, backend):
        g = fnx.watts_strogatz_graph(10, 4, 0.1, backend=backend)
        assert g.number_of_nodes() == 10
        g = fnx.newman_watts_strogatz_graph(10, 4, 0.1, backend=backend)
        assert g.number_of_nodes() == 10

    def test_unknown_backend_raises_import_error(self):
        with pytest.raises(ImportError):
            fnx.watts_strogatz_graph(10, 4, 0.1, backend="nonexistent")
        with pytest.raises(ImportError):
            fnx.newman_watts_strogatz_graph(10, 4, 0.1, backend="nonexistent")

    def test_arbitrary_backend_kwargs_accepted(self):
        # **backend_kwargs must absorb trailing kwargs without TypeError.
        fnx.watts_strogatz_graph(10, 4, 0.1, foo="bar", spam=1)
        fnx.newman_watts_strogatz_graph(10, 4, 0.1, foo="bar", spam=1)


# ---------------------------------------------------------------------------
# Attachment generator backend keyword surface (franken_networkx-k4mg)
# ---------------------------------------------------------------------------


class TestAttachmentGeneratorBackendKeyword:
    """barabasi_albert_graph and powerlaw_cluster_graph must match the
    NetworkX backend keyword contract just like the Watts-Strogatz family.
    """

    def test_default_backend_runs_in_tree(self):
        assert fnx.barabasi_albert_graph(10, 2).number_of_nodes() == 10
        assert fnx.powerlaw_cluster_graph(10, 2, 0.3).number_of_nodes() == 10

    @pytest.mark.parametrize("backend", [None, "networkx"])
    def test_explicit_supported_backend(self, backend):
        fnx.barabasi_albert_graph(10, 2, backend=backend)
        fnx.powerlaw_cluster_graph(10, 2, 0.3, backend=backend)

    def test_unknown_backend_raises_import_error(self):
        with pytest.raises(ImportError):
            fnx.barabasi_albert_graph(10, 2, backend="nonexistent")
        with pytest.raises(ImportError):
            fnx.powerlaw_cluster_graph(10, 2, 0.3, backend="nonexistent")

    def test_arbitrary_backend_kwargs_accepted(self):
        fnx.barabasi_albert_graph(10, 2, foo="bar", spam=1)
        fnx.powerlaw_cluster_graph(10, 2, 0.3, foo="bar", spam=1)


class TestGnpFamilyBackendKeyword:
    """Bead franken_networkx-g8w2: every member of the G(n,p) family
    (gnp_random_graph, fast_gnp_random_graph, erdos_renyi_graph,
    binomial_graph) accepts the backend keyword surface and routes
    unknown-backend / unknown-kwargs errors the same way upstream does.
    """

    FAMILY = [
        "gnp_random_graph",
        "fast_gnp_random_graph",
        "erdos_renyi_graph",
        "binomial_graph",
    ]

    @pytest.mark.parametrize("name", FAMILY)
    def test_default_and_explicit_supported_backend(self, name):
        fn = getattr(fnx, name)
        assert fn(8, 0.3, seed=42).number_of_nodes() == 8
        assert fn(8, 0.3, seed=42, backend=None).number_of_nodes() == 8
        assert fn(8, 0.3, seed=42, backend="networkx").number_of_nodes() == 8

    @pytest.mark.parametrize("name", FAMILY)
    def test_unknown_backend_raises_import_error(self, name):
        fn = getattr(fnx, name)
        with pytest.raises(ImportError):
            fn(8, 0.3, seed=42, backend="nonexistent")

    @pytest.mark.parametrize("name", FAMILY)
    def test_unknown_kwargs_rejected_matching_networkx(self, name):
        import networkx as nx

        fn = getattr(fnx, name)
        nxfn = getattr(nx, name)
        with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
            fn(8, 0.3, seed=42, foo="bar")
        with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
            nxfn(8, 0.3, seed=42, foo="bar")


# ---------------------------------------------------------------------------
# Tree / shell random generator keyword surface (franken_networkx-p2rq)
# ---------------------------------------------------------------------------


class TestTreeShellRandomGeneratorsKeywordSurface:
    """random_lobster, random_shell_graph, and random_powerlaw_tree must
    expose NetworkX's full public keyword surface: create_using +
    backend / **backend_kwargs. random_lobster previously lacked
    create_using entirely; all three were missing the backend dispatch.
    """

    def test_random_lobster_accepts_create_using(self):
        g = fnx.random_lobster(10, 0.3, 0.3, seed=42)
        assert isinstance(g, fnx.Graph)
        # Same constructor returns the requested class.
        g = fnx.random_lobster(10, 0.3, 0.3, seed=42, create_using=fnx.Graph)
        assert isinstance(g, fnx.Graph)
        # Directed / multi rejected with NetworkXError just like upstream.
        with pytest.raises(fnx.NetworkXError):
            fnx.random_lobster(10, 0.3, 0.3, seed=42, create_using=fnx.DiGraph)
        with pytest.raises(fnx.NetworkXError):
            fnx.random_lobster(10, 0.3, 0.3, seed=42, create_using=fnx.MultiGraph)

    def test_random_lobster_backend_dispatch(self):
        fnx.random_lobster(10, 0.3, 0.3, seed=42, backend=None)
        fnx.random_lobster(10, 0.3, 0.3, seed=42, backend="networkx")
        with pytest.raises(ImportError):
            fnx.random_lobster(10, 0.3, 0.3, seed=42, backend="nonexistent")
        # Arbitrary trailing kwargs absorbed by **backend_kwargs.
        fnx.random_lobster(10, 0.3, 0.3, seed=42, foo="bar", spam=1)

    def test_random_shell_graph_backend_dispatch(self):
        constructor = [(2, 4, 0.4), (3, 8, 0.5)]
        fnx.random_shell_graph(constructor, seed=42, backend=None)
        fnx.random_shell_graph(constructor, seed=42, backend="networkx")
        with pytest.raises(ImportError):
            fnx.random_shell_graph(constructor, seed=42, backend="nonexistent")
        fnx.random_shell_graph(constructor, seed=42, foo="bar")

    def test_random_powerlaw_tree_backend_dispatch(self):
        fnx.random_powerlaw_tree(10, seed=42, tries=1000, backend=None)
        fnx.random_powerlaw_tree(10, seed=42, tries=1000, backend="networkx")
        with pytest.raises(ImportError):
            fnx.random_powerlaw_tree(10, seed=42, tries=1000, backend="nonexistent")
        fnx.random_powerlaw_tree(10, seed=42, tries=1000, foo="bar")


# ---------------------------------------------------------------------------
# random_kernel_graph signature parity (franken_networkx-g77j)
# ---------------------------------------------------------------------------


class TestRandomKernelGraphSignatureParity:
    """random_kernel_graph must match upstream's public signature
    (n, kernel_integral, kernel_root=None, seed=None, *, create_using,
    backend, **backend_kwargs) and forward backend dispatch to networkx.
    """

    @staticmethod
    def _kernel_integral(u, v, w):
        return (v - u) * w

    def test_keyword_kernel_integral_accepted(self):
        g = fnx.random_kernel_graph(6, kernel_integral=self._kernel_integral, seed=42)
        assert g.number_of_nodes() == 6

    def test_kernel_root_keyword_accepted(self):
        g = fnx.random_kernel_graph(
            6, kernel_integral=self._kernel_integral, kernel_root=None, seed=42
        )
        assert g.number_of_nodes() == 6

    def test_unknown_backend_raises_import_error(self):
        with pytest.raises(ImportError):
            fnx.random_kernel_graph(
                6, kernel_integral=self._kernel_integral, backend="nonexistent"
            )

    def test_create_using_keyword_accepted(self):
        # Upstream nx expects an *instance* (or None) rather than a class
        # for create_using in this generator; pass an instance to mirror
        # their convention.
        g = fnx.random_kernel_graph(
            6,
            kernel_integral=self._kernel_integral,
            seed=42,
            create_using=fnx.Graph(),
        )
        assert isinstance(g, fnx.Graph)

    def test_create_using_accepts_fnx_class(self):
        """Bead franken_networkx-clre: passing the fnx.Graph *class* as
        create_using must work without leaking descriptor TypeError from
        nx's internals (which call G.is_directed(None) on class inputs).
        """
        g = fnx.random_kernel_graph(
            6, kernel_integral=self._kernel_integral, seed=42, create_using=fnx.Graph
        )
        assert isinstance(g, fnx.Graph)

    def test_create_using_directed_rejected_matching_networkx(self):
        """Passing a directed class routes through the same
        'create_using must not be directed' NetworkXError as upstream.
        """
        import networkx as nx

        with pytest.raises((fnx.NetworkXError, nx.NetworkXError), match="directed"):
            fnx.random_kernel_graph(
                6,
                kernel_integral=self._kernel_integral,
                seed=42,
                create_using=fnx.DiGraph,
            )
        with pytest.raises(nx.NetworkXError, match="directed"):
            nx.random_kernel_graph(
                6,
                kernel_integral=self._kernel_integral,
                seed=42,
                create_using=nx.DiGraph,
            )


class TestRandomKernelGraphDifferentialConformance:
    """Table-driven differential conformance for random_kernel_graph
    against upstream NetworkX: covers create_using None/constructor/instance
    in both nx and fnx flavours, and exception parity for the error paths.

    Bead franken_networkx-2v9o.
    """

    @staticmethod
    def _kernel_integral(u, v, w):
        return (v - u) * w

    @staticmethod
    def _graph_signature(g):
        # Canonical structure snapshot — node set, edge set, and class name.
        return (
            type(g).__name__,
            sorted(g.nodes()),
            sorted(sorted(edge) for edge in g.edges()),
        )

    def test_create_using_none_matches_networkx_signature(self):
        import networkx as nx

        fg = fnx.random_kernel_graph(6, kernel_integral=self._kernel_integral, seed=42)
        ng = nx.random_kernel_graph(6, kernel_integral=self._kernel_integral, seed=42)
        # Same node set and edge set; class name equal after the nx→fnx rehydrate.
        assert sorted(fg.nodes()) == sorted(ng.nodes())
        assert sorted(sorted(e) for e in fg.edges()) == sorted(
            sorted(e) for e in ng.edges()
        )

    @pytest.mark.parametrize(
        "fnx_input, nx_input",
        [
            pytest.param(None, None, id="None"),
            pytest.param(lambda: fnx.Graph, lambda: __import__("networkx").Graph, id="class-fnx-vs-nx"),
            pytest.param(lambda: fnx.Graph(), lambda: __import__("networkx").Graph(), id="instance-fnx-vs-nx"),
        ],
    )
    def test_create_using_variants_succeed(self, fnx_input, nx_input):
        """All three create_using shapes (None, class, instance) must
        produce a fnx.Graph with the same edge set as upstream.
        """
        import networkx as nx

        fnx_cu = fnx_input() if callable(fnx_input) else fnx_input
        nx_cu = nx_input() if callable(nx_input) else nx_input
        fg = fnx.random_kernel_graph(
            6, kernel_integral=self._kernel_integral, seed=42, create_using=fnx_cu
        )
        ng = nx.random_kernel_graph(
            6, kernel_integral=self._kernel_integral, seed=42, create_using=nx_cu
        )
        assert isinstance(fg, fnx.Graph)
        assert sorted(sorted(e) for e in fg.edges()) == sorted(
            sorted(e) for e in ng.edges()
        )

    def test_directed_create_using_raises_networkx_error(self):
        import networkx as nx

        for fnx_cu, nx_cu in [(fnx.DiGraph, nx.DiGraph), (fnx.DiGraph(), nx.DiGraph())]:
            with pytest.raises(
                (fnx.NetworkXError, nx.NetworkXError), match="directed"
            ):
                fnx.random_kernel_graph(
                    6,
                    kernel_integral=self._kernel_integral,
                    seed=42,
                    create_using=fnx_cu,
                )
            with pytest.raises(nx.NetworkXError, match="directed"):
                nx.random_kernel_graph(
                    6,
                    kernel_integral=self._kernel_integral,
                    seed=42,
                    create_using=nx_cu,
                )

    def test_kernel_root_custom_function_accepted(self):
        """A custom kernel_root callable matching the upstream signature
        runs through the wrapper and produces a fnx.Graph.
        """
        import networkx as nx

        def kernel_root(y, a, r):
            # Inverse of (v - a) * 1 = r when w=1; matches _kernel_integral.
            return r + a

        fg = fnx.random_kernel_graph(
            5, kernel_integral=self._kernel_integral, kernel_root=kernel_root, seed=42
        )
        ng = nx.random_kernel_graph(
            5, kernel_integral=self._kernel_integral, kernel_root=kernel_root, seed=42
        )
        assert sorted(fg.nodes()) == sorted(ng.nodes())
        assert sorted(sorted(e) for e in fg.edges()) == sorted(
            sorted(e) for e in ng.edges()
        )

    def test_bad_kernel_integral_signature_surfaces_type_error(self):
        """A kernel_integral with the wrong arity must surface TypeError
        on both sides — matches upstream argmap+dispatch behaviour.
        """
        import networkx as nx

        def bad_integral(u, v):  # wrong arity (needs u, v, w)
            return v - u

        for probe in (fnx, nx):
            with pytest.raises(TypeError):
                probe.random_kernel_graph(5, kernel_integral=bad_integral, seed=42)


# ---------------------------------------------------------------------------
# Signature conformance audit (franken_networkx-vrx8)
# ---------------------------------------------------------------------------


class TestGeneratorSignatureParityWithNetworkX:
    """After the backend-keyword rollout, verify the touched public
    generators expose byte-identical signatures to upstream NetworkX.
    Catches regressions like literal backend_kwargs=None parameters
    instead of **backend_kwargs, and keyword-only create_using drift.
    """

    SIGNATURE_TARGETS = [
        "forceatlas2_layout",
        "gnp_random_graph",
        "watts_strogatz_graph",
        "newman_watts_strogatz_graph",
        "fast_gnp_random_graph",
        "powerlaw_cluster_graph",
        "barabasi_albert_graph",
        "dual_barabasi_albert_graph",
        "extended_barabasi_albert_graph",
        "random_regular_graph",
        "random_shell_graph",
        "random_kernel_graph",
        "erdos_renyi_graph",
        "binomial_graph",
    ]

    @pytest.mark.parametrize("fn_name", SIGNATURE_TARGETS)
    def test_signature_matches_networkx(self, fn_name):
        import inspect

        import networkx as nx

        fnx_fn = getattr(fnx, fn_name)
        nx_fn = getattr(nx, fn_name)
        assert str(inspect.signature(fnx_fn)) == str(inspect.signature(nx_fn)), (
            f"{fn_name} signature drifted from upstream "
            f"(fnx={inspect.signature(fnx_fn)!r}, nx={inspect.signature(nx_fn)!r})"
        )


# br-rrgval: random_regular_graph invalid-arg errors must be NetworkXError
# with nx wording (not the Rust ValueError(FailClosed{...}) surface).
# Note: fnx.NetworkXError is _fnx.NetworkXError and is NOT a subclass of
# nx.NetworkXError (see queued bead nxexcbases). We match fnx's hierarchy
# here and gate the cross-library `isinstance nx.NetworkXError` parity in
# test_exception_hierarchy_parity where the queued bead lives.
class TestRandomRegularInvalidArgs:
    def test_d_ge_n_raises_networkx_error_matching_nx(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"the 0 <= d < n inequality must be satisfied",
        ):
            fnx.random_regular_graph(3, 0, seed=0)

    def test_d_zero_n_zero_raises_networkx_error(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"the 0 <= d < n inequality must be satisfied",
        ):
            fnx.random_regular_graph(0, 0, seed=0)

    def test_odd_n_times_d_raises_networkx_error(self):
        # 0 <= 3 < 5 passes the first check; 3*5=15 is odd -> second.
        with pytest.raises(fnx.NetworkXError, match=r"n \* d must be even"):
            fnx.random_regular_graph(3, 5, seed=0)


# br-badiacritic: nx uses Unicode "Barabási–Albert" in its error messages
# for barabasi_albert_graph and dual_barabasi_albert_graph (but ASCII
# "Barabasi-Albert" for extended_barabasi_albert_graph). fnx matches
# character-for-character so `pytest.raises(..., match=...)` regex patterns
# written against upstream work unchanged.
class TestBarabasiAlbertErrorDiacritics:
    def test_ba_m_ge_n_uses_diacritics(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Barabási–Albert network must have m >= 1",
        ):
            fnx.barabasi_albert_graph(1, 1, seed=0)

    def test_dual_ba_m1_uses_diacritics(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Dual Barabási–Albert must have m1 >= 1",
        ):
            fnx.dual_barabasi_albert_graph(1, 1, 1, 0.5, seed=0)

    def test_dual_ba_p_out_of_range_uses_diacritics(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Dual Barabási–Albert network must have 0 <= p <= 1",
        ):
            fnx.dual_barabasi_albert_graph(5, 2, 3, 1.5, seed=0)

    def test_extended_ba_stays_ascii(self):
        # upstream keeps ASCII for extended_barabasi_albert_graph; ensure
        # fnx mirrors that exact string (a common copy/paste trap).
        with pytest.raises(
            fnx.NetworkXError,
            match=r"Extended Barabasi-Albert network needs m>=1",
        ):
            fnx.extended_barabasi_albert_graph(1, 1, 0.1, 0.1, seed=0)


# br-gnrempty: gnc_graph(0) and gnr_graph(0) must match nx's "single seed
# node" output instead of returning the empty digraph from the Rust
# fast-path.
class TestGrowingDigraphEmpty:
    def test_gnc_graph_zero_returns_one_node_matching_nx(self):
        import networkx as nx

        fg = fnx.gnc_graph(0, seed=42)
        ng = nx.gnc_graph(0, seed=42)
        assert sorted(fg.nodes()) == sorted(ng.nodes()) == [0]
        assert list(fg.edges()) == list(ng.edges()) == []

    def test_gnr_graph_zero_returns_one_node_matching_nx(self):
        import networkx as nx

        fg = fnx.gnr_graph(0, 0.5, seed=42)
        ng = nx.gnr_graph(0, 0.5, seed=42)
        assert sorted(fg.nodes()) == sorted(ng.nodes()) == [0]
        assert list(fg.edges()) == list(ng.edges()) == []


# br-powerlawexc: powerlaw_cluster_graph invalid-arg errors must match
# nx's (unusual) "NetworkXError must have..." wording exactly instead of
# leaking the Rust ValueError(FailClosed{...}) surface.
class TestPowerlawClusterInvalidArgs:
    def test_m_out_of_range_uses_nx_wording(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"NetworkXError must have m>1 and m<n, m=0,n=0",
        ):
            fnx.powerlaw_cluster_graph(0, 0, 0.0, seed=0)

    def test_p_out_of_range_uses_nx_wording_high(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"NetworkXError p must be in \[0,1\], p=1.5",
        ):
            fnx.powerlaw_cluster_graph(3, 1, 1.5, seed=0)

    def test_p_out_of_range_uses_nx_wording_low(self):
        with pytest.raises(
            fnx.NetworkXError,
            match=r"NetworkXError p must be in \[0,1\], p=-0.1",
        ):
            fnx.powerlaw_cluster_graph(3, 1, -0.1, seed=0)
