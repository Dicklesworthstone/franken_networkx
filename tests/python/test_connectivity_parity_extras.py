"""Parity coverage for the connectivity submodule extras.

Beads:
- br-r37-c1-lz7u6 — bridge_components
- br-r37-c1-hq5pq — minimum_st_edge_cut
- br-r37-c1-vw7p2 — is_locally_k_edge_connected

The bead descriptions claimed these were missing from franken_networkx.
Inspection shows they are already exposed at the top level (and on
``fnx.connectivity``) and they already match networkx's behaviour. The
tests below freeze that contract so a future regression is caught.
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


def _build_pair(builder):
    nx_graph = builder()
    f_graph = type(_fnx_class(nx_graph))()
    f_graph.add_nodes_from(nx_graph.nodes(data=True))
    f_graph.add_edges_from(nx_graph.edges(data=True))
    return f_graph, nx_graph


def _fnx_class(nx_graph):
    if nx_graph.is_directed():
        return fnx.MultiDiGraph() if nx_graph.is_multigraph() else fnx.DiGraph()
    return fnx.MultiGraph() if nx_graph.is_multigraph() else fnx.Graph()


# ---------------------------------------------------------------------------
# bridge_components
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("two-triangles-via-bridge", lambda: nx.Graph(
            [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
        )),
        ("path", lambda: nx.path_graph(5)),
        ("cycle", lambda: nx.cycle_graph(6)),
        ("complete", lambda: nx.complete_graph(5)),
        ("karate", lambda: nx.karate_club_graph()),
        ("disjoint", lambda: nx.disjoint_union(
            nx.cycle_graph(3), nx.cycle_graph(4)
        )),
        ("single-node", lambda: nx.empty_graph(1)),
    ],
)
def test_bridge_components_matches_networkx(name, builder):
    f_graph, nx_graph = _build_pair(builder)
    actual = sorted(frozenset(c) for c in fnx.bridge_components(f_graph))
    expected = sorted(frozenset(c) for c in nx.connectivity.bridge_components(nx_graph))
    assert actual == expected
    # Each component should be a frozenset / set
    for component in fnx.bridge_components(f_graph):
        assert isinstance(component, (set, frozenset))


# ---------------------------------------------------------------------------
# minimum_st_edge_cut
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "s", "t"),
    [
        ("path", lambda: nx.path_graph(6), 0, 5),
        ("cycle", lambda: nx.cycle_graph(6), 0, 3),
        ("karate", lambda: nx.karate_club_graph(), 0, 33),
        ("complete", lambda: nx.complete_graph(5), 0, 4),
    ],
)
def test_minimum_st_edge_cut_matches_networkx(name, builder, s, t):
    f_graph, nx_graph = _build_pair(builder)
    actual = fnx.minimum_st_edge_cut(f_graph, s, t)
    expected = nx.connectivity.minimum_st_edge_cut(nx_graph, s, t)
    # Both return sets of edge tuples; cardinalities must match exactly
    # because the value is the min-cut size. The actual edges may differ
    # when multiple min-cuts exist, but the cardinality is canonical.
    assert isinstance(actual, set)
    assert len(actual) == len(expected)
    # Verify the cut actually disconnects s from t in a copy
    h = nx_graph.copy()
    h.remove_edges_from(actual)
    assert not nx.has_path(h, s, t)


@needs_nx
def test_minimum_st_edge_cut_directed_matches_networkx():
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from([(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (1, 2)])
    f_graph = fnx.DiGraph()
    f_graph.add_edges_from(nx_graph.edges(data=True))

    actual = fnx.minimum_st_edge_cut(f_graph, 0, 4)
    expected = nx.connectivity.minimum_st_edge_cut(nx_graph, 0, 4)
    assert isinstance(actual, set)
    assert len(actual) == len(expected)


# ---------------------------------------------------------------------------
# is_locally_k_edge_connected
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    ("name", "builder", "s", "t"),
    [
        ("path-far", lambda: nx.path_graph(6), 0, 5),
        ("cycle-half", lambda: nx.cycle_graph(8), 0, 4),
        ("karate-edge", lambda: nx.karate_club_graph(), 0, 33),
        ("complete-pair", lambda: nx.complete_graph(5), 0, 4),
    ],
)
@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 10])
def test_is_locally_k_edge_connected_matches_networkx(name, builder, s, t, k):
    f_graph, nx_graph = _build_pair(builder)
    actual = fnx.is_locally_k_edge_connected(f_graph, s, t, k)
    expected = nx.connectivity.is_locally_k_edge_connected(nx_graph, s, t, k)
    assert actual == expected
    assert isinstance(actual, bool)


@needs_nx
def test_is_locally_k_edge_connected_disconnected_components():
    """When s and t are in different components, the answer is False
    for every k >= 1 (no path exists)."""
    nx_graph = nx.disjoint_union(nx.path_graph(3), nx.path_graph(3))
    f_graph = fnx.Graph()
    f_graph.add_edges_from(nx_graph.edges())

    # 0..2 in one component, 3..5 in the other
    for k in [1, 2, 3]:
        actual = fnx.is_locally_k_edge_connected(f_graph, 0, 5, k)
        expected = nx.connectivity.is_locally_k_edge_connected(nx_graph, 0, 5, k)
        assert actual == expected
        assert actual is False
