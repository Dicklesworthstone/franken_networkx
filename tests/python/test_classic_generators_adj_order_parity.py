"""Parity for 12 classic graph generators' adj-iteration order.

Bead br-r37-c1-iw2hz. Same family pattern as br-r37-c1-o97vk
(cycle_graph/wheel_graph): the _rust_* fast paths for these
generators produced adj orderings that didn't match nx. The
pure-Python construction path for each was already correct
(used in the create_using path), so the fix routes through
the Python path always.

Generators covered:
  Named (no args): dodecahedral_graph, heawood_graph, frucht_graph,
    sedgewick_maze_graph, truncated_cube_graph,
    truncated_tetrahedron_graph, house_x_graph
  Parameterised: ladder_graph, circular_ladder_graph,
    circulant_graph, lollipop_graph, barbell_graph

Drop-in code that iterated adj[node] of any of these
generator-built graphs silently broke.
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


def _assert_full_parity(g, gx):
    """Assert nodes, edges, and per-node adj iteration all match."""
    assert list(g.nodes()) == list(gx.nodes())
    assert list(g.edges()) == list(gx.edges())
    assert _adj_dict(g) == _adj_dict(gx)


# ----- named graphs (no args) -----

@needs_nx
def test_dodecahedral_graph_matches_nx():
    _assert_full_parity(fnx.dodecahedral_graph(), nx.dodecahedral_graph())


@needs_nx
def test_heawood_graph_matches_nx():
    _assert_full_parity(fnx.heawood_graph(), nx.heawood_graph())


@needs_nx
def test_frucht_graph_matches_nx():
    _assert_full_parity(fnx.frucht_graph(), nx.frucht_graph())


@needs_nx
def test_sedgewick_maze_graph_matches_nx():
    _assert_full_parity(fnx.sedgewick_maze_graph(), nx.sedgewick_maze_graph())


@needs_nx
def test_truncated_cube_graph_matches_nx():
    _assert_full_parity(fnx.truncated_cube_graph(), nx.truncated_cube_graph())


@needs_nx
def test_truncated_tetrahedron_graph_matches_nx():
    _assert_full_parity(fnx.truncated_tetrahedron_graph(), nx.truncated_tetrahedron_graph())


@needs_nx
def test_house_x_graph_matches_nx():
    _assert_full_parity(fnx.house_x_graph(), nx.house_x_graph())


# ----- parameterised generators -----

@needs_nx
@pytest.mark.parametrize("n", [2, 3, 4, 5, 8])
def test_ladder_graph_matches_nx(n):
    _assert_full_parity(fnx.ladder_graph(n), nx.ladder_graph(n))


@needs_nx
@pytest.mark.parametrize("n", [3, 4, 5, 8])
def test_circular_ladder_graph_matches_nx(n):
    _assert_full_parity(fnx.circular_ladder_graph(n), nx.circular_ladder_graph(n))


@needs_nx
@pytest.mark.parametrize(
    ("n", "offsets"),
    [(7, [1, 2]), (5, [1]), (8, [1, 3]), (6, [2])],
)
def test_circulant_graph_matches_nx(n, offsets):
    _assert_full_parity(
        fnx.circulant_graph(n, offsets), nx.circulant_graph(n, offsets)
    )


@needs_nx
@pytest.mark.parametrize(
    ("m", "n"),
    [(2, 0), (3, 0), (3, 4), (5, 2), (4, 6)],
)
def test_lollipop_graph_matches_nx(m, n):
    _assert_full_parity(fnx.lollipop_graph(m, n), nx.lollipop_graph(m, n))


@needs_nx
@pytest.mark.parametrize(
    ("m1", "m2"),
    [(2, 0), (3, 4), (4, 2), (3, 0), (5, 1)],
)
def test_barbell_graph_matches_nx(m1, m2):
    _assert_full_parity(fnx.barbell_graph(m1, m2), nx.barbell_graph(m1, m2))


# ----- specific repro asserts (regressions for the bead description) -----

@needs_nx
def test_repro_lollipop_3_4_adj_3_matches_nx():
    g = fnx.lollipop_graph(3, 4)
    gx = nx.lollipop_graph(3, 4)
    assert list(g.adj[3]) == list(gx.adj[3]) == [4, 2]


@needs_nx
def test_repro_barbell_3_4_adj_3_matches_nx():
    g = fnx.barbell_graph(3, 4)
    gx = nx.barbell_graph(3, 4)
    assert list(g.adj[3]) == list(gx.adj[3]) == [4, 2]


@needs_nx
def test_repro_circulant_7_1_2_adj_0_matches_nx():
    g = fnx.circulant_graph(7, [1, 2])
    gx = nx.circulant_graph(7, [1, 2])
    assert list(g.adj[0]) == list(gx.adj[0]) == [6, 5, 1, 2]


@needs_nx
def test_repro_ladder_4_adj_4_matches_nx():
    g = fnx.ladder_graph(4)
    gx = nx.ladder_graph(4)
    assert list(g.adj[4]) == list(gx.adj[4]) == [5, 0]


@needs_nx
def test_repro_dodecahedral_adj_0_matches_nx():
    g = fnx.dodecahedral_graph()
    gx = nx.dodecahedral_graph()
    assert list(g.adj[0]) == list(gx.adj[0]) == [1, 19, 10]


# ----- downstream consequence: BFS order now matches -----

@needs_nx
def test_bfs_from_0_lollipop_matches_nx():
    """BFS visits neighbors in adj-iteration order — verify the
    fix propagates downstream."""
    g = fnx.lollipop_graph(3, 4)
    gx = nx.lollipop_graph(3, 4)
    assert list(fnx.bfs_edges(g, 0)) == list(nx.bfs_edges(gx, 0))


@needs_nx
def test_bfs_from_0_circulant_matches_nx():
    g = fnx.circulant_graph(7, [1, 2])
    gx = nx.circulant_graph(7, [1, 2])
    assert list(fnx.bfs_edges(g, 0)) == list(nx.bfs_edges(gx, 0))


@needs_nx
def test_bfs_from_0_ladder_matches_nx():
    g = fnx.ladder_graph(4)
    gx = nx.ladder_graph(4)
    assert list(fnx.bfs_edges(g, 0)) == list(nx.bfs_edges(gx, 0))
