"""Parity tests for k_edge_augmentation (bead 049)."""
from unittest import mock

import franken_networkx as fnx
import networkx as nx


class TestKEdgeAugmentation:
    """Verify k_edge_augmentation matches NetworkX behavior."""

    def test_k0_returns_empty(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3)])
        assert fnx.k_edge_augmentation(G, 0) == []

    def test_k1_already_connected(self):
        G = fnx.complete_graph(4)
        assert fnx.k_edge_augmentation(G, 1) == []

    def test_k1_disconnected_components(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (2, 3), (4, 5)])
        aug = fnx.k_edge_augmentation(G, 1)
        assert len(aug) == 2  # need 2 edges to connect 3 components
        H = G.copy()
        for u, v in aug:
            H.add_edge(u, v)
        assert fnx.is_connected(H)

    def test_k2_bridge_graph(self):
        """Graph with a bridge: augmentation should eliminate it."""
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
        aug = fnx.k_edge_augmentation(G, 2)
        # Both should produce valid augmentations
        H = G.copy()
        for u, v in aug:
            H.add_edge(u, v)
        assert fnx.edge_connectivity(H) >= 2.0

    def test_k2_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
        nG = nx.Graph(G.edges())
        aug = fnx.k_edge_augmentation(G, 2)
        naug = list(nx.k_edge_augmentation(nG, 2))
        assert sorted(aug) == sorted(naug)

    def test_k3_cycle_graph(self):
        """C6 has edge connectivity 2; augment to 3."""
        G = fnx.cycle_graph(6)
        nG = nx.cycle_graph(6)
        aug = fnx.k_edge_augmentation(G, 3)
        naug = list(nx.k_edge_augmentation(nG, 3))
        # Verify result achieves k=3
        H = G.copy()
        for u, v in aug:
            H.add_edge(u, v)
        assert fnx.edge_connectivity(H) >= 3.0
        # Same edge set as NX
        assert sorted(aug) == sorted(naug)

    def test_weighted_k1_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = [(1, 5, {"weight": 11}), (2, 5, {"weight": 10})]

        aug = fnx.k_edge_augmentation(G, 1, avail=avail, weight="weight")
        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        naug = list(nx.k_edge_augmentation(nG, 1, avail=avail, weight="weight"))

        assert aug == naug

    def test_weighted_k2_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = [(1, 5, 11), (2, 5, 10), (4, 3, 1), (4, 5, 51)]

        aug = fnx.k_edge_augmentation(G, 2, avail=avail)
        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        naug = list(nx.k_edge_augmentation(nG, 2, avail=avail))

        assert sorted(aug) == sorted(naug)

    def test_partial_k2_matches_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = {(1, 5): 11}

        aug = fnx.k_edge_augmentation(G, 2, avail=avail, partial=True)
        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        naug = list(nx.k_edge_augmentation(nG, 2, avail=avail, partial=True))

        assert sorted(aug) == sorted(naug)

    def test_nontrivial_paths_do_not_call_to_nx(self):
        G = fnx.Graph()
        G.add_edges_from([(1, 2), (2, 3), (3, 4)])
        G.add_node(5)
        avail = [(1, 5, 11), (2, 5, 10), (4, 3, 1), (4, 5, 51)]

        with mock.patch(
            "franken_networkx.drawing.layout._to_nx",
            side_effect=AssertionError("_to_nx fallback should not be used"),
        ), mock.patch(
            "networkx.k_edge_augmentation",
            side_effect=AssertionError("networkx fallback should not be used"),
        ):
            aug = fnx.k_edge_augmentation(G, 2, avail=avail)

        nG = nx.Graph()
        nG.add_edges_from([(1, 2), (2, 3), (3, 4)])
        nG.add_node(5)
        assert sorted(aug) == sorted(nx.k_edge_augmentation(nG, 2, avail=avail))

    def test_k_already_satisfied(self):
        """K5 has edge connectivity 4; k=3 should return empty."""
        G = fnx.complete_graph(5)
        assert fnx.k_edge_augmentation(G, 3) == []

    def test_augmented_graph_is_k_connected(self):
        """Generic verification: after augmentation, connectivity >= k."""
        G = fnx.path_graph(8)
        for k in [1, 2, 3]:
            aug = fnx.k_edge_augmentation(G, k)
            H = G.copy()
            for u, v in aug:
                H.add_edge(u, v)
            conn = fnx.edge_connectivity(H)
            assert conn >= k, f"k={k}: expected conn>={k}, got {conn}"
