"""Parity for ``florentine_families_graph``.

Bead br-r37-c1-dgicx. fnx built the graph from a canonical/
alphabetical edge list, but nx adds edges in a specific narrative
order (Castellani's edges before Medici's middle edges, etc.).
This produced different node-insertion order, edge iteration
order, and per-node adj order. Drop-in code that iterated the
classic Florentine families dataset in nx's order broke.
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


@needs_nx
def test_node_order_matches_nx():
    f = fnx.florentine_families_graph()
    n = nx.florentine_families_graph()
    assert list(f.nodes()) == list(n.nodes())


@needs_nx
def test_edge_order_matches_nx():
    f = fnx.florentine_families_graph()
    n = nx.florentine_families_graph()
    assert list(f.edges()) == list(n.edges())


@needs_nx
def test_adj_order_matches_nx():
    f = fnx.florentine_families_graph()
    n = nx.florentine_families_graph()
    for node in n.nodes():
        assert list(f.adj[node]) == list(n.adj[node]), (
            f"adj[{node}]: fnx={list(f.adj[node])} nx={list(n.adj[node])}"
        )


@needs_nx
def test_15_nodes_20_edges():
    """Sanity: classic dataset shape preserved."""
    f = fnx.florentine_families_graph()
    assert f.number_of_nodes() == 15
    assert f.number_of_edges() == 20


@needs_nx
def test_returns_undirected_graph():
    f = fnx.florentine_families_graph()
    assert isinstance(f, fnx.Graph)
    assert not f.is_directed()


@needs_nx
def test_medici_adjacency_repro_matches_nx():
    """Specific regression: 'Medici' adj order in nx is
    [Acciaiuoli, Barbadori, Ridolfi, Tornabuoni, Albizzi, Salviati]."""
    f = fnx.florentine_families_graph()
    expected = ["Acciaiuoli", "Barbadori", "Ridolfi", "Tornabuoni", "Albizzi", "Salviati"]
    assert list(f.adj["Medici"]) == expected


@needs_nx
def test_first_5_nodes_match_nx():
    """Specific regression: first 5 nodes in nx insertion order are
    [Acciaiuoli, Medici, Castellani, Peruzzi, Strozzi]."""
    f = fnx.florentine_families_graph()
    assert list(f.nodes())[:5] == ["Acciaiuoli", "Medici", "Castellani", "Peruzzi", "Strozzi"]


@needs_nx
def test_bfs_from_medici_matches_nx():
    """Downstream consequence: BFS from Medici visits in adj order,
    so the sequence must match after the adj-order fix."""
    f = fnx.florentine_families_graph()
    n = nx.florentine_families_graph()
    assert list(fnx.bfs_edges(f, "Medici")) == list(nx.bfs_edges(n, "Medici"))
