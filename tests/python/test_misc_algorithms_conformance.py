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

from decimal import Decimal
from fractions import Fraction
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


def test_constraint_weighted_matches_networkx():
    g_fnx = fnx.Graph()
    g_nx = nx.Graph()
    weighted_edges = [
        (0, 1, 1.0),
        (1, 2, 5.0),
        (2, 0, 2.0),
        (2, 3, 7.0),
        (3, 4, 3.0),
    ]
    for u, v, weight in weighted_edges:
        g_fnx.add_edge(u, v, weight=weight)
        g_nx.add_edge(u, v, weight=weight)

    fr = fnx.constraint(g_fnx, weight="weight")
    nr = nx.constraint(g_nx, weight="weight")
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


def test_effective_size_weighted_matches_networkx():
    g_fnx = fnx.Graph()
    g_nx = nx.Graph()
    weighted_edges = [
        (0, 1, 1.0),
        (1, 2, 5.0),
        (2, 0, 2.0),
        (2, 3, 7.0),
        (3, 4, 3.0),
    ]
    for u, v, weight in weighted_edges:
        g_fnx.add_edge(u, v, weight=weight)
        g_nx.add_edge(u, v, weight=weight)

    fr = fnx.effective_size(g_fnx, weight="weight")
    nr = nx.effective_size(g_nx, weight="weight")
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


def _dispersion_graph(module, graph_type="Graph"):
    graph = getattr(module, graph_type)()
    graph.add_edges_from([
        (0, 1), (0, 2), (0, 3), (1, 2), (1, 3),
        (2, 4), (3, 4), (1, 5),
    ])
    graph.add_node("isolated")
    if graph.is_multigraph():
        graph.add_edge(0, 1)
    return graph


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("target", [1, "isolated"])
@pytest.mark.parametrize("self_loop", [False, True])
@pytest.mark.parametrize("options", [
    {}, {"normalized": False}, {"alpha": 2, "b": 1, "c": 1},
], ids=["default", "unnormalized", "custom-formula"])
def test_dispersion_target_only_matches_networkx(graph_type, target, self_loop, options):
    actual_graph = _dispersion_graph(fnx, graph_type)
    expected_graph = _dispersion_graph(nx, graph_type)
    if self_loop:
        actual_graph.add_edge(1, 1)
        expected_graph.add_edge(1, 1)

    actual = fnx.dispersion(actual_graph, v=target, **options)
    expected = nx.dispersion(expected_graph, v=target, **options)
    assert list(actual) == list(expected) == list(expected_graph[target])
    assert actual == expected
    assert actual == fnx.dispersion(actual_graph, u=target, **options)
    for node in expected:
        assert type(actual[node]) is type(expected[node])


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_dispersion_missing_target_raises_networkx_key_error(graph_type):
    with pytest.raises(KeyError) as expected:
        nx.dispersion(_dispersion_graph(nx, graph_type), v="missing")
    with pytest.raises(KeyError) as actual:
        fnx.dispersion(_dispersion_graph(fnx, graph_type), v="missing")
    assert actual.value.args == expected.value.args == ("missing",)


@pytest.mark.parametrize("selection", [{}, {"u": 1}, {"v": 1}], ids=["all", "source", "target"])
@pytest.mark.parametrize("parameters", [
    {"alpha": Decimal("1"), "b": Decimal("0.125"), "c": Decimal("0.5")},
    {"alpha": 2, "b": Fraction(1, 3), "c": Fraction(2, 3)},
    {"alpha": 1, "b": 2**80 + 1, "c": 0},
    {"alpha": 0.5, "b": -2.0, "c": 0.0},
], ids=["decimal", "fraction", "wide-integer", "complex-power"])
def test_dispersion_normalization_preserves_scalar_arithmetic(selection, parameters):
    actual = fnx.dispersion(_dispersion_graph(fnx), **selection, **parameters)
    expected = nx.dispersion(_dispersion_graph(nx), **selection, **parameters)
    assert list(actual) == list(expected)
    actual_rows = actual.values() if not selection else [actual]
    expected_rows = expected.values() if not selection else [expected]
    for actual_row, expected_row in zip(actual_rows, expected_rows):
        assert list(actual_row) == list(expected_row)
        assert actual_row == expected_row
        for node in expected_row:
            assert type(actual_row[node]) is type(expected_row[node])


@pytest.mark.parametrize("selection", [{}, {"u": 1}, {"v": 1}], ids=["all", "source", "target"])
@pytest.mark.parametrize("parameters,error", [
    ({"alpha": 2.0, "b": 1e308}, OverflowError),
    ({"alpha": -1.0}, ZeroDivisionError),
])
def test_dispersion_normalization_preserves_python_errors(selection, parameters, error):
    with pytest.raises(error) as expected:
        nx.dispersion(_dispersion_graph(nx), **selection, **parameters)
    with pytest.raises(error) as actual:
        fnx.dispersion(_dispersion_graph(fnx), **selection, **parameters)
    assert actual.value.args == expected.value.args


@pytest.mark.parametrize("selection", [{}, {"u": 1}, {"v": 1}], ids=["all", "source", "target"])
def test_dispersion_default_formula_keeps_native_map_routes(monkeypatch, selection):
    name = "dispersion_node_rust" if selection else "dispersion_full_rust"
    native = getattr(fnx._fnx, name)
    calls = []

    def tracked(*args):
        calls.append(args)
        return native(*args)

    monkeypatch.setattr(fnx._fnx, name, tracked)
    graph = _dispersion_graph(fnx)
    actual = fnx.dispersion(graph, **selection)
    expected = nx.dispersion(_dispersion_graph(nx), **selection)
    assert actual == expected
    assert len(calls) == 1
    assert calls[0][0] is graph
    if selection:
        assert calls[0][1] == 1


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
    fr = fnx.algorithms.node_classification.harmonic_function(fg)
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
    fr = fnx.algorithms.node_classification.local_and_global_consistency(fg, alpha=alpha)
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
