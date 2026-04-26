"""Parity for ``cycle_graph`` / ``wheel_graph`` adj-iteration order.

Bead br-r37-c1-o97vk. The Rust-backed _rust_cycle_graph and
_rust_wheel_graph fast paths produced graphs whose adj of the
"closing" node (where the cycle/rim wraps back to node 0) drifted
from nx.

Repro:
  cycle_graph(4):
    fnx adj[3] = [0, 2]
    nx  adj[3] = [2, 0]   (closing edge 3->0 appends 0 after 2)
  wheel_graph(5):
    fnx adj[4] = [0, 1, 3]
    nx  adj[4] = [0, 3, 1]   (rim's closing edge 4->1 appends 1 after 3)

The same graphs constructed via add_edge in the Python path already
match nx exactly, so the fix routes both generators through the
Python path always.

Drop-in code that iterated adj[node] of a generator-built graph
(BFS/DFS-strategy tie-breaking, edge-traversal order, visualisations)
silently broke.
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


def _adj_dict(G):
    return {n: list(G.adj[n]) for n in G.nodes()}


@needs_nx
@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 10])
def test_cycle_graph_adj_matches_nx(n):
    g = fnx.cycle_graph(n)
    gx = nx.cycle_graph(n)
    assert _adj_dict(g) == _adj_dict(gx)
    assert list(g.nodes()) == list(gx.nodes())
    assert list(g.edges()) == list(gx.edges())


@needs_nx
@pytest.mark.parametrize("n", [3, 4, 5, 7, 10])
def test_wheel_graph_adj_matches_nx(n):
    g = fnx.wheel_graph(n)
    gx = nx.wheel_graph(n)
    assert _adj_dict(g) == _adj_dict(gx)
    assert list(g.nodes()) == list(gx.nodes())
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_cycle_graph_repro_4_adj_3_matches_nx():
    """Repro from the bead description."""
    g = fnx.cycle_graph(4)
    gx = nx.cycle_graph(4)
    assert list(g.adj[3]) == list(gx.adj[3]) == [2, 0]


@needs_nx
def test_wheel_graph_repro_5_adj_4_matches_nx():
    """Repro from the bead description."""
    g = fnx.wheel_graph(5)
    gx = nx.wheel_graph(5)
    assert list(g.adj[4]) == list(gx.adj[4]) == [0, 3, 1]


@needs_nx
def test_cycle_graph_zero_nodes_matches_nx():
    g = fnx.cycle_graph(0)
    gx = nx.cycle_graph(0)
    assert g.number_of_nodes() == gx.number_of_nodes() == 0
    assert g.number_of_edges() == gx.number_of_edges() == 0


@needs_nx
def test_cycle_graph_single_node_matches_nx():
    g = fnx.cycle_graph(1)
    gx = nx.cycle_graph(1)
    assert list(g.nodes()) == list(gx.nodes())
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_cycle_graph_two_nodes_matches_nx():
    """Special case: cycle(2) is just one edge (0,1)."""
    g = fnx.cycle_graph(2)
    gx = nx.cycle_graph(2)
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_cycle_graph_with_create_using_digraph_matches_nx():
    g = fnx.cycle_graph(4, create_using=fnx.DiGraph)
    gx = nx.cycle_graph(4, create_using=nx.DiGraph)
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_cycle_graph_node_list_arg_matches_nx():
    """The nodes-as-list arg form should also produce matching adj."""
    g = fnx.cycle_graph(["x", "y", "z", "w"])
    gx = nx.cycle_graph(["x", "y", "z", "w"])
    assert _adj_dict(g) == _adj_dict(gx)


@needs_nx
def test_wheel_graph_zero_nodes_matches_nx():
    g = fnx.wheel_graph(0)
    gx = nx.wheel_graph(0)
    assert g.number_of_nodes() == gx.number_of_nodes() == 0


@needs_nx
def test_wheel_graph_single_node_matches_nx():
    g = fnx.wheel_graph(1)
    gx = nx.wheel_graph(1)
    assert list(g.nodes()) == list(gx.nodes())
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_wheel_graph_two_nodes_matches_nx():
    """wheel(2) is just hub + 1 spoke."""
    g = fnx.wheel_graph(2)
    gx = nx.wheel_graph(2)
    assert list(g.edges()) == list(gx.edges())


@needs_nx
def test_cycle_graph_bfs_order_now_matches_nx():
    """Concrete consequence: BFS from node 0 must match nx after the
    adj fix (BFS visits neighbors in adj-iteration order)."""
    g = fnx.cycle_graph(6)
    gx = nx.cycle_graph(6)
    assert list(fnx.bfs_edges(g, 0)) == list(nx.bfs_edges(gx, 0))


@needs_nx
def test_wheel_graph_bfs_order_now_matches_nx():
    """Same BFS-order consequence for wheel_graph."""
    g = fnx.wheel_graph(6)
    gx = nx.wheel_graph(6)
    assert list(fnx.bfs_edges(g, 0)) == list(nx.bfs_edges(gx, 0))
