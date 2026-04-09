"""Parity tests for trophic_levels and related functions (bead wj9)."""
import franken_networkx as fnx
import networkx as nx


class TestTrophicLevels:
    """Verify trophic_levels matches NetworkX."""

    def test_chain_dag(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 3)])
        nD = nx.DiGraph(D.edges())
        tl = fnx.trophic_levels(D)
        ntl = nx.trophic_levels(nD)
        for n in tl:
            assert abs(tl[n] - ntl[n]) < 1e-10, f"node {n}: fnx={tl[n]} nx={ntl[n]}"

    def test_diamond_dag(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        nD = nx.DiGraph(D.edges())
        tl = fnx.trophic_levels(D)
        ntl = nx.trophic_levels(nD)
        for n in tl:
            assert abs(tl[n] - ntl[n]) < 1e-10, f"node {n}: fnx={tl[n]} nx={ntl[n]}"

    def test_empty_graph(self):
        assert fnx.trophic_levels(fnx.DiGraph()) == {}

    def test_single_node(self):
        D = fnx.DiGraph()
        D.add_node(0)
        tl = fnx.trophic_levels(D)
        assert 0 in tl
        # Single node with no incoming edges is basal: level 1
        assert abs(tl[0] - 1.0) < 1e-10

    def test_basal_species_level_1(self):
        """Nodes with no incoming edges should have trophic level 1."""
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3)])
        tl = fnx.trophic_levels(D)
        assert abs(tl[0] - 1.0) < 1e-10, "Basal species should be level 1"

    def test_weighted(self):
        D = fnx.DiGraph()
        D.add_edge(0, 1, weight=2.0)
        D.add_edge(0, 2, weight=1.0)
        D.add_edge(1, 3, weight=1.0)
        D.add_edge(2, 3, weight=3.0)
        nD = nx.DiGraph()
        nD.add_edge(0, 1, weight=2.0)
        nD.add_edge(0, 2, weight=1.0)
        nD.add_edge(1, 3, weight=1.0)
        nD.add_edge(2, 3, weight=3.0)
        tl = fnx.trophic_levels(D, weight="weight")
        ntl = nx.trophic_levels(nD, weight="weight")
        for n in tl:
            assert abs(tl[n] - ntl[n]) < 1e-10, f"node {n}: fnx={tl[n]} nx={ntl[n]}"


class TestTrophicDifferences:
    """Verify trophic_differences matches NetworkX."""

    def test_chain_dag(self):
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (1, 2), (2, 3)])
        nD = nx.DiGraph(D.edges())
        td = fnx.trophic_differences(D)
        ntd = nx.trophic_differences(nD)
        for e in td:
            assert abs(td[e] - ntd[e]) < 1e-10, f"edge {e}: fnx={td[e]} nx={ntd[e]}"

    def test_all_differences_positive_in_dag(self):
        """In a DAG, all trophic differences should be >= 0."""
        D = fnx.DiGraph()
        D.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3)])
        td = fnx.trophic_differences(D)
        for e, diff in td.items():
            assert diff >= -1e-10, f"edge {e}: negative difference {diff}"
