"""Golden conformance harness for the Rust ``wiener_index`` port.

The Python ``franken_networkx.wiener_index`` previously implemented its
own BFS / Dijkstra loops in pure Python. The native Rust port adds the
weighted-undirected and weighted/unweighted-directed variants alongside
the existing unweighted-undirected one, dispatching all four cases
through ``franken_networkx._fnx.wiener_index(G, weight=)``.

This harness validates 50+ inputs across:

- 4 dispatch combinations: undirected/directed × unweighted/weighted
- Many fixture topologies: paths, cycles, complete, star, petersen,
  random ER, random tree, weighted ladder, disconnected, near-bound
- Multigraph fallback (Python path), to make sure the Rust route does
  not swallow the parallel-edge min-weight semantics

Each input is run through both ``fnx.wiener_index`` and
``networkx.wiener_index`` and the two scalars must match (within float
tolerance for the weighted cases).
"""

from __future__ import annotations

import math

import pytest
import networkx as nx

import franken_networkx as fnx


def _close(a, b, *, tol=1e-9):
    if math.isinf(a) and math.isinf(b):
        return (a > 0) == (b > 0)
    if math.isinf(a) or math.isinf(b):
        return False
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _build_pair_undirected(builder):
    return builder(fnx), builder(nx)


def _build_directed_strongly_connected(L):
    g = L.DiGraph()
    g.add_edges_from(
        [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (2, 0), (1, 3), (3, 1)]
    )
    return g


def _build_directed_disconnected(L):
    g = L.DiGraph()
    g.add_edges_from([(0, 1), (1, 2)])  # not strongly connected
    return g


def _weighted_path_5(L):
    g = L.Graph()
    g.add_weighted_edges_from(
        [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0), (3, 4, 4.0)]
    )
    return g


def _weighted_grid(L):
    g = L.Graph()
    g.add_weighted_edges_from([
        (0, 1, 0.5), (1, 2, 1.5), (2, 3, 2.5),
        (0, 4, 1.0), (1, 5, 1.0), (2, 6, 1.0), (3, 7, 1.0),
        (4, 5, 2.0), (5, 6, 3.0), (6, 7, 1.5),
    ])
    return g


def _weighted_petersen(L):
    """Build the Petersen graph with weighted edges constructed via
    ``add_weighted_edges_from`` — fnx's Python-side
    ``g[u][v]["weight"] = ...`` mutations do not propagate to the
    underlying Rust adjacency storage, so weights set after the
    generator call would be ignored by the Rust port."""
    proto = L.petersen_graph()
    edges = [(u, v, float(u + v + 1)) for u, v in proto.edges()]
    g = L.Graph()
    g.add_weighted_edges_from(edges)
    return g


def _weighted_directed_cycle(L, n=6):
    g = L.DiGraph()
    edges = [(i, (i + 1) % n, float(i + 1)) for i in range(n)]
    g.add_weighted_edges_from(edges)
    return g


def _weighted_directed_complete(L, n=4):
    g = L.DiGraph()
    edges = [
        (u, v, float((u * n + v) % 7 + 1))
        for u in range(n)
        for v in range(n)
        if u != v
    ]
    g.add_weighted_edges_from(edges)
    return g


# ---------------------------------------------------------------------------
# 1. Undirected unweighted: full parity across many topologies
# ---------------------------------------------------------------------------


UNDIRECTED_UNWEIGHTED = [
    ("path_2", lambda L: L.path_graph(2)),
    ("path_3", lambda L: L.path_graph(3)),
    ("path_5", lambda L: L.path_graph(5)),
    ("path_8", lambda L: L.path_graph(8)),
    ("path_12", lambda L: L.path_graph(12)),
    ("cycle_3", lambda L: L.cycle_graph(3)),
    ("cycle_4", lambda L: L.cycle_graph(4)),
    ("cycle_5", lambda L: L.cycle_graph(5)),
    ("cycle_8", lambda L: L.cycle_graph(8)),
    ("cycle_12", lambda L: L.cycle_graph(12)),
    ("complete_3", lambda L: L.complete_graph(3)),
    ("complete_4", lambda L: L.complete_graph(4)),
    ("complete_5", lambda L: L.complete_graph(5)),
    ("complete_8", lambda L: L.complete_graph(8)),
    ("star_4", lambda L: L.star_graph(4)),
    ("star_8", lambda L: L.star_graph(8)),
    ("star_12", lambda L: L.star_graph(12)),
    ("petersen", lambda L: L.petersen_graph()),
    ("krackhardt_kite", lambda L: L.krackhardt_kite_graph()),
    ("bull", lambda L: L.bull_graph()),
    ("diamond", lambda L: L.diamond_graph()),
    ("house", lambda L: L.house_graph()),
    ("balanced_tree_2_2", lambda L: L.balanced_tree(2, 2)),
    ("balanced_tree_3_2", lambda L: L.balanced_tree(3, 2)),
    ("hypercube_3", lambda L: L.hypercube_graph(3)),
    ("hypercube_4", lambda L: L.hypercube_graph(4)),
    ("ladder_4", lambda L: L.ladder_graph(4)),
    ("circular_ladder_4", lambda L: L.circular_ladder_graph(4)),
    ("wheel_5", lambda L: L.wheel_graph(5)),
    ("wheel_8", lambda L: L.wheel_graph(8)),
]


@pytest.mark.parametrize(
    "name,builder", UNDIRECTED_UNWEIGHTED,
    ids=[fx[0] for fx in UNDIRECTED_UNWEIGHTED],
)
def test_undirected_unweighted_matches_networkx(name, builder):
    fg, ng = _build_pair_undirected(builder)
    fr = fnx.wiener_index(fg)
    nr = nx.wiener_index(ng)
    assert _close(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 2. Undirected weighted: parity for several weighted topologies
# ---------------------------------------------------------------------------


UNDIRECTED_WEIGHTED = [
    ("weighted_path_5", _weighted_path_5),
    ("weighted_grid_8", _weighted_grid),
    ("weighted_petersen", _weighted_petersen),
]


@pytest.mark.parametrize(
    "name,builder", UNDIRECTED_WEIGHTED,
    ids=[fx[0] for fx in UNDIRECTED_WEIGHTED],
)
def test_undirected_weighted_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = fnx.wiener_index(fg, weight="weight")
    nr = nx.wiener_index(ng, weight="weight")
    assert _close(fr, nr, tol=1e-9), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 3. Directed unweighted: parity for strongly-connected fixtures
# ---------------------------------------------------------------------------


DIRECTED_UNWEIGHTED = [
    ("dir_cycle_4", lambda L: L.cycle_graph(4, create_using=L.DiGraph)),
    ("dir_cycle_8", lambda L: L.cycle_graph(8, create_using=L.DiGraph)),
    ("dir_complete_4",
     lambda L: L.complete_graph(4, create_using=L.DiGraph)),
    ("dir_complete_5",
     lambda L: L.complete_graph(5, create_using=L.DiGraph)),
    ("dir_strong", _build_directed_strongly_connected),
]


@pytest.mark.parametrize(
    "name,builder", DIRECTED_UNWEIGHTED,
    ids=[fx[0] for fx in DIRECTED_UNWEIGHTED],
)
def test_directed_unweighted_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = fnx.wiener_index(fg)
    nr = nx.wiener_index(ng)
    assert _close(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 4. Directed weighted: parity
# ---------------------------------------------------------------------------


DIRECTED_WEIGHTED = [
    ("wd_cycle_4", lambda L: _weighted_directed_cycle(L, 4)),
    ("wd_cycle_6", lambda L: _weighted_directed_cycle(L, 6)),
    ("wd_complete_4", lambda L: _weighted_directed_complete(L, 4)),
    ("wd_complete_5", lambda L: _weighted_directed_complete(L, 5)),
]


@pytest.mark.parametrize(
    "name,builder", DIRECTED_WEIGHTED,
    ids=[fx[0] for fx in DIRECTED_WEIGHTED],
)
def test_directed_weighted_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = fnx.wiener_index(fg, weight="weight")
    nr = nx.wiener_index(ng, weight="weight")
    assert _close(fr, nr, tol=1e-9), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 5. Disconnected and corner cases — both libs must report inf
# ---------------------------------------------------------------------------


def test_disconnected_undirected_returns_inf():
    fg = fnx.Graph()
    fg.add_nodes_from([0, 1, 2, 3])
    fg.add_edges_from([(0, 1), (2, 3)])  # two components
    ng = nx.Graph()
    ng.add_nodes_from([0, 1, 2, 3])
    ng.add_edges_from([(0, 1), (2, 3)])
    assert math.isinf(fnx.wiener_index(fg))
    assert math.isinf(nx.wiener_index(ng))


def test_not_strongly_connected_directed_returns_inf():
    fg = _build_directed_disconnected(fnx)
    ng = _build_directed_disconnected(nx)
    assert math.isinf(fnx.wiener_index(fg))
    assert math.isinf(nx.wiener_index(ng))


def test_singleton_returns_zero():
    fg = fnx.Graph()
    fg.add_node(0)
    assert fnx.wiener_index(fg) == 0.0


def test_empty_graph_raises_pointless_matching_networkx():
    """nx raises ``NetworkXPointlessConcept`` for an empty graph because
    ``is_connected`` is undefined there. fnx must mirror that contract."""
    fg = fnx.Graph()
    ng = nx.Graph()
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.wiener_index(ng)
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.wiener_index(fg)


# ---------------------------------------------------------------------------
# 6. Multigraph fallback path: stays in Python because the Rust binding
#    sees only the simple-graph collapse
# ---------------------------------------------------------------------------


def test_multigraph_unweighted_matches_networkx():
    fg = fnx.MultiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (1, 3)])
    ng = nx.MultiGraph()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (1, 3)])
    assert _close(fnx.wiener_index(fg), nx.wiener_index(ng))


def test_multigraph_weighted_min_parallel_edge_matches_networkx():
    """nx picks the minimum weight across parallel edges; the Rust
    binding sees only the simple-graph collapse, so fnx falls back to
    the Python loop here."""
    fg = fnx.MultiGraph()
    fg.add_edge(0, 1, weight=5.0)
    fg.add_edge(0, 1, weight=1.0)  # parallel — min weight is 1.0
    fg.add_edge(1, 2, weight=2.0)
    ng = nx.MultiGraph()
    ng.add_edge(0, 1, weight=5.0)
    ng.add_edge(0, 1, weight=1.0)
    ng.add_edge(1, 2, weight=2.0)
    fr = fnx.wiener_index(fg, weight="weight")
    nr = nx.wiener_index(ng, weight="weight")
    assert _close(fr, nr, tol=1e-9), f"fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# 7. Cross-relation invariants
# ---------------------------------------------------------------------------


def test_weighted_with_unit_weights_equals_unweighted():
    """When every edge weight equals 1, weighted result equals unweighted."""
    proto = fnx.cycle_graph(8)
    g = fnx.Graph()
    g.add_weighted_edges_from([(u, v, 1.0) for u, v in proto.edges()])
    assert _close(
        fnx.wiener_index(g, weight="weight"),
        fnx.wiener_index(g),
    )


def test_directed_cycle_weighted_equals_unweighted_with_unit_weights():
    proto = fnx.cycle_graph(6, create_using=fnx.DiGraph)
    g = fnx.DiGraph()
    g.add_weighted_edges_from([(u, v, 1.0) for u, v in proto.edges()])
    assert _close(
        fnx.wiener_index(g, weight="weight"),
        fnx.wiener_index(g),
    )


def test_undirected_value_is_one_half_of_ordered_pair_sum():
    """Undirected wiener index counts each pair once; doubling it should
    equal the directed-style sum-of-ordered-pair-distances."""
    g = fnx.cycle_graph(6)
    w = fnx.wiener_index(g)
    # Sum directly via single-source BFS
    total_ordered = 0.0
    nodes = list(g.nodes())
    for s in nodes:
        d = fnx.single_source_shortest_path_length(g, s)
        for v in nodes:
            if v == s:
                continue
            total_ordered += d[v]
    assert _close(2 * w, total_ordered)
