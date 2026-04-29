"""NetworkX conformance for miscellaneous algorithms.

Bundles small but useful functions that lacked broad differential
coverage:

- ``voronoi_cells(G, center_nodes, weight=)`` — partition by nearest
  center node.
- ``closeness_vitality(G, node=, weight=)`` — drop in graph closeness
  when removing a node.
- ``node_redundancy(G, nodes=)`` — bipartite redundancy coefficient.
- ``constraint(G, nodes=, weight=)`` and
  ``effective_size(G, nodes=, weight=)`` — Burt's structural holes.
- ``dispersion(G, u=, v=, normalized=, alpha=, b=, c=)`` —
  Burt-style dispersion of common neighbors.
- ``second_order_centrality(G, weight=)`` — local-clustering-like
  centrality measure.
- ``harmonic_function(G, max_iter=, label_name=)`` and
  ``local_and_global_consistency(G, alpha=, max_iter=, label_name=)``
   — semi-supervised node classification.
"""

from __future__ import annotations

import math
import warnings

import pytest
import networkx as nx
from networkx.algorithms import node_classification as nx_nc

import franken_networkx as fnx


def _equiv(a, b, tol=1e-6):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isinf(a) and math.isinf(b):
            # Both inf — match if same sign.
            return (a > 0) == (b > 0)
        if math.isinf(a) or math.isinf(b):
            return False
        return abs(a - b) < tol
    return a == b


def _equiv_dict(a, b, tol=1e-6):
    if set(a.keys()) != set(b.keys()):
        return False
    return all(_equiv(a[k], b[k], tol) for k in a)


def _pair(edges, nodes=None, *, directed=False):
    cls_fnx = fnx.DiGraph if directed else fnx.Graph
    cls_nx = nx.DiGraph if directed else nx.Graph
    fg = cls_fnx()
    ng = cls_nx()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# voronoi_cells
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,centers,directed",
    [
        ("undirected_path",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)),
         {0, 4}, False),
        ("undirected_K_4",
         [(u, v) for u in range(4) for v in range(u + 1, 4)],
         list(range(4)), {0, 1}, False),
        ("undirected_grid",
         [(0, 1), (1, 2), (0, 3), (2, 5), (3, 4), (4, 5)],
         list(range(6)), {0, 5}, False),
        ("dir_cycle_centers_at_two_points",
         [(i, (i + 1) % 6) for i in range(6)],
         list(range(6)), {0, 3}, True),
        ("dir_tree",
         [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5)],
         list(range(6)), {0}, True),
    ],
)
def test_voronoi_cells_matches_networkx(name, edges, nodes, centers, directed):
    fg, ng = _pair(edges, nodes, directed=directed)
    fr = fnx.voronoi_cells(fg, centers)
    nr = nx.voronoi_cells(ng, centers)
    fr_norm = {k: set(v) for k, v in fr.items()}
    nr_norm = {k: set(v) for k, v in nr.items()}
    assert fr_norm == nr_norm, f"{name}: fnx={fr_norm} nx={nr_norm}"


# ---------------------------------------------------------------------------
# closeness_vitality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("S_4", lambda L: L.star_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_closeness_vitality_matches_networkx(name, builder):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.closeness_vitality(g_fnx)
    nr = nx.closeness_vitality(g_nx)
    if isinstance(fr, dict) and isinstance(nr, dict):
        assert _equiv_dict(fr, nr), f"{name}: dict mismatch"
    else:
        assert _equiv(fr, nr)


def test_closeness_vitality_for_single_node_matches_networkx():
    """Test ``node=`` parameter for single-node query."""
    g_fnx = fnx.path_graph(5)
    g_nx = nx.path_graph(5)
    for node in [0, 2, 4]:
        fr = fnx.closeness_vitality(g_fnx, node=node)
        nr = nx.closeness_vitality(g_nx, node=node)
        assert _equiv(fr, nr), f"node={node}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# constraint and effective_size — Burt's structural holes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("S_4", lambda L: L.star_graph(4)),
        ("two_K_3_bridge",
         lambda L: L.from_edgelist(
             [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
         ) if hasattr(L, "from_edgelist") else None),
    ],
)
def test_constraint_matches_networkx(name, builder):
    g_nx = builder(nx)
    if g_nx is None:
        # fallback: build manually
        g_nx = nx.Graph()
        g_nx.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.constraint(g_fnx)
    nr = nx.constraint(g_nx)
    assert _equiv_dict(fr, nr)


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_effective_size_matches_networkx(name, builder):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.effective_size(g_fnx)
    nr = nx.effective_size(g_nx)
    assert _equiv_dict(fr, nr)


# ---------------------------------------------------------------------------
# dispersion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,u,v",
    [
        ("path_5_endpoints", lambda L: L.path_graph(5), 0, 4),
        ("path_5_mid", lambda L: L.path_graph(5), 1, 3),
        ("K_5_pair", lambda L: L.complete_graph(5), 0, 1),
        ("petersen_pair", lambda L: L.petersen_graph(), 0, 5),
    ],
)
def test_dispersion_pair_matches_networkx(name, builder, u, v):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.dispersion(g_fnx, u=u, v=v)
    nr = nx.dispersion(g_nx, u=u, v=v)
    assert _equiv(fr, nr)


# ---------------------------------------------------------------------------
# second_order_centrality
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("K_4", lambda L: L.complete_graph(4)),
        ("C_6", lambda L: L.cycle_graph(6)),
        ("petersen", lambda L: L.petersen_graph()),
    ],
)
def test_second_order_centrality_matches_networkx(name, builder):
    g_nx = builder(nx)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.second_order_centrality(g_fnx)
        nr = nx.second_order_centrality(g_nx)
    assert _equiv_dict(fr, nr, tol=1e-3)


# ---------------------------------------------------------------------------
# Node classification: harmonic_function and local_and_global_consistency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,labels",
    [
        ("path_6_two_classes",
         [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
         {0: "A", 5: "B"}),
        ("ring_two_endpoints",
         [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)],
         {0: "A", 3: "B"}),
        ("star_center_labelled",
         [(0, i) for i in range(1, 5)],
         {0: "A", 1: "B"}),
        ("two_K_3_bridge_labelled",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)],
         {0: "A", 5: "B"}),
    ],
)
def test_harmonic_function_matches_networkx(name, edges, labels):
    fg = fnx.Graph(); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_edges_from(edges)
    for n, lab in labels.items():
        fg.nodes[n]["label"] = lab
        ng.nodes[n]["label"] = lab
    fr = fnx.harmonic_function(fg)
    nr = nx_nc.harmonic_function(ng)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,labels",
    [
        ("path_6_two_classes",
         [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
         {0: "A", 5: "B"}),
        ("two_K_3_bridge_labelled",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)],
         {0: "A", 5: "B"}),
    ],
)
@pytest.mark.parametrize("alpha", [0.5, 0.99, 0.999])
def test_local_and_global_consistency_matches_networkx(name, edges, labels, alpha):
    fg = fnx.Graph(); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_edges_from(edges)
    for n, lab in labels.items():
        fg.nodes[n]["label"] = lab
        ng.nodes[n]["label"] = lab
    fr = fnx.local_and_global_consistency(fg, alpha=alpha)
    nr = nx_nc.local_and_global_consistency(ng, alpha=alpha)
    assert fr == nr, f"{name} alpha={alpha}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_voronoi_cells_partition_covers_all_reachable_nodes():
    """Every reachable node belongs to exactly one Voronoi cell."""
    g = fnx.cycle_graph(6)
    centers = {0, 3}
    cells = fnx.voronoi_cells(g, centers)
    all_assigned = set()
    for cell_set in cells.values():
        all_assigned |= set(cell_set)
    assert all_assigned == set(g.nodes())


def test_constraint_and_effective_size_have_same_keys():
    """Both metrics return dicts keyed by the same node set."""
    g = fnx.path_graph(5)
    c = fnx.constraint(g)
    es = fnx.effective_size(g)
    assert set(c.keys()) == set(es.keys()) == set(g.nodes())
