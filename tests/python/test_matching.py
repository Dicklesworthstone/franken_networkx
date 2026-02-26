"""Conformance tests: matching algorithms — fnx vs nx oracle."""

import pytest


@pytest.mark.conformance
class TestMatching:
    def test_maximal_matching_is_valid(self, fnx, path_graph):
        G_fnx, _ = path_graph
        mm = fnx.maximal_matching(G_fnx)
        # Verify it's a valid matching: no node appears twice
        nodes_used = set()
        for u, v in mm:
            assert str(u) not in nodes_used
            assert str(v) not in nodes_used
            nodes_used.add(str(u))
            nodes_used.add(str(v))

    def test_maximal_matching_is_maximal(self, fnx, path_graph):
        G_fnx, _ = path_graph
        mm = fnx.maximal_matching(G_fnx)
        matched = set()
        for u, v in mm:
            matched.add(str(u))
            matched.add(str(v))
        # Every edge has at least one matched endpoint (maximality)
        for u, v in G_fnx.edges:
            assert str(u) in matched or str(v) in matched

    def test_min_edge_cover(self, fnx, nx, path_graph):
        G_fnx, G_nx = path_graph
        fnx_ec = fnx.min_edge_cover(G_fnx)
        nx_ec = nx.min_edge_cover(G_nx)
        # Edge cover sizes should match
        assert len(fnx_ec) == len(nx_ec)

    def test_min_edge_cover_covers_all(self, fnx, path_graph):
        G_fnx, _ = path_graph
        ec = fnx.min_edge_cover(G_fnx)
        covered = set()
        for u, v in ec:
            covered.add(str(u))
            covered.add(str(v))
        # Every node must be covered
        for n in G_fnx.nodes:
            assert str(n) in covered
