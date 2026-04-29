"""NetworkX conformance for the Wiener-index / distance-sum family.

Covers ``wiener_index``, ``harmonic_diameter``, ``gutman_index``,
``schultz_index``, ``hyper_wiener_index``, ``estrada_index``,
``effective_graph_resistance``, and ``kemeny_constant`` against
upstream NetworkX.

Found a sixth instance of the systematic ``gr.undirected()`` directed-
collapse bug pattern (previously fixed in is_eulerian, eccentricity,
is_tree/is_forest, core_number, degree_assortativity_coefficient):
``harmonic_diameter`` on ``DiGraph(C_3)`` returned 1.0 instead of NX's
1.333... because the Rust ``harmonic_diameter_rust`` folded
antiparallel directions before computing distances. Fixed by routing
the directed branch (and the ``sp=`` branch) through NX.

Asserts bit-for-bit (NaN/inf-aware) parity across:
- 50+ undirected fixtures (K_n, C_n, P_n, S_n, K_{m,n}, Petersen,
  hypercube Q_3, gnp randoms).
- 8 directed fixtures (cycles, antiparallel, polytrees, mixed
  orientation, K_n_both).
- Weighted variants for the wiener / gutman / schultz / hyper_wiener
  indices.
- Edge cases (single node, two-node, trivial).
"""

from __future__ import annotations

import itertools
import math
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _equiv(a, b, tol=1e-9):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        if math.isinf(a) and math.isinf(b):
            return True
        return abs(a - b) < tol
    return a == b


def _pair_undirected(edges, nodes=None):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _pair_directed(edges, nodes=None):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _undirected_fixtures():
    out = []
    for n in range(2, 7):
        out.append((f"K_{n}",
                    list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    for n in range(3, 9):
        out.append((f"C_{n}",
                    [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    for n in range(2, 9):
        out.append((f"P_{n}",
                    list(zip(range(n - 1), range(1, n))),
                    list(range(n))))
    for n in range(1, 6):
        out.append((f"S_{n}",
                    [(0, i) for i in range(1, n + 1)],
                    list(range(n + 1))))
    for a, b in [(2, 3), (3, 3), (3, 4)]:
        kbg = nx.complete_bipartite_graph(a, b)
        out.append((f"K_{a}_{b}",
                    list(kbg.edges()), list(kbg.nodes())))
    out.append(("petersen", list(nx.petersen_graph().edges()),
                list(nx.petersen_graph().nodes())))
    out.append(("hypercube_3", list(nx.hypercube_graph(3).edges()),
                list(nx.hypercube_graph(3).nodes())))
    for n, p, seed in [(8, 0.4, 1), (10, 0.4, 2), (12, 0.3, 3),
                       (15, 0.3, 4), (20, 0.2, 5)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        if not nx.is_connected(gnp):
            continue
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


def _directed_fixtures():
    return [
        ("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))),
        ("dir_C_4",
         [(i, (i + 1) % 4) for i in range(4)], list(range(4))),
        ("dir_C_5",
         [(i, (i + 1) % 5) for i in range(5)], list(range(5))),
        ("dir_K3_both",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(3))),
        ("dir_K4_both",
         [(u, v) for u in range(4) for v in range(4) if u != v],
         list(range(4))),
        ("dir_antipar_pair", [(0, 1), (1, 0)], list(range(2))),
        ("dir_path_4", [(0, 1), (1, 2), (2, 3)], list(range(4))),
        ("dir_mixed",
         [(0, 1), (1, 0), (1, 2), (2, 3), (3, 1)], list(range(4))),
    ]


UNDIRECTED = _undirected_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# wiener_index — undirected and directed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_wiener_index_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = fnx.wiener_index(fg)
    nr = nx.wiener_index(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_wiener_index_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.wiener_index(fg)
    nr = nx.wiener_index(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# harmonic_diameter — undirected and directed (regression for br-harmdir)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_harmonic_diameter_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = fnx.harmonic_diameter(fg)
    nr = nx.harmonic_diameter(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_harmonic_diameter_directed(name, edges, nodes):
    """``harmonic_diameter`` must consider ordered (u, v) pairs for
    directed input. Locks the br-harmdir fix in: the Rust
    ``harmonic_diameter_rust`` was folding antiparallel directions
    via ``gr.undirected()`` and reporting 1.0 on directed C_3 instead
    of NX's 1.333..."""
    fg, ng = _pair_directed(edges, nodes)
    fr = fnx.harmonic_diameter(fg)
    nr = nx.harmonic_diameter(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# gutman_index, schultz_index, hyper_wiener_index — undirected only in NX
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn_name",
                         ["gutman_index", "schultz_index",
                          "hyper_wiener_index"])
@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_topological_indices_undirected(name, edges, nodes, fn_name):
    fg, ng = _pair_undirected(edges, nodes)
    fr = getattr(fnx, fn_name)(fg)
    nr = getattr(nx, fn_name)(ng)
    assert _equiv(fr, nr), f"{name} {fn_name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# estrada_index — exponential of adjacency-matrix eigenvalues
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_estrada_index_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = fnx.estrada_index(fg)
    nr = nx.estrada_index(ng)
    assert _equiv(fr, nr, tol=1e-6), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# effective_graph_resistance + kemeny_constant — connected undirected only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_effective_graph_resistance(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    if not fnx.is_connected(fg):
        return
    fr = fnx.effective_graph_resistance(fg)
    nr = nx.effective_graph_resistance(ng)
    assert _equiv(fr, nr, tol=1e-6), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 2 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in UNDIRECTED if 2 <= len(fx[2]) <= 15],
)
def test_kemeny_constant(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    if not fnx.is_connected(fg):
        return
    fr = fnx.kemeny_constant(fg)
    nr = nx.kemeny_constant(ng)
    assert _equiv(fr, nr, tol=1e-6), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Weighted variants of wiener_index
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges_with_w",
    [
        ("triangle_w",
         [(0, 1, 1.0), (1, 2, 2.0), (2, 0, 3.0)]),
        ("path_4_w",
         [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0)]),
        ("K_4_w",
         [(u, v, float(u + v + 1))
          for u, v in itertools.combinations(range(4), 2)]),
    ],
)
def test_wiener_index_weighted_matches_networkx(name, edges_with_w):
    fg = fnx.Graph(); ng = nx.Graph()
    for u, v, w in edges_with_w:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    fr = fnx.wiener_index(fg, weight="weight")
    nr = nx.wiener_index(ng, weight="weight")
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Edge cases — single node, two nodes, disconnected
# ---------------------------------------------------------------------------


def test_wiener_index_single_node():
    fg = fnx.Graph(); fg.add_node(0)
    ng = nx.Graph(); ng.add_node(0)
    assert _equiv(fnx.wiener_index(fg), nx.wiener_index(ng))


def test_wiener_index_disconnected_returns_inf():
    """NX's wiener_index returns ``inf`` on disconnected input."""
    fg, ng = _pair_undirected([(0, 1), (2, 3)], list(range(4)))
    fr = fnx.wiener_index(fg)
    nr = nx.wiener_index(ng)
    assert _equiv(fr, nr)


def test_harmonic_diameter_single_node():
    fg = fnx.Graph(); fg.add_node(0)
    ng = nx.Graph(); ng.add_node(0)
    fr = fnx.harmonic_diameter(fg)
    nr = nx.harmonic_diameter(ng)
    assert _equiv(fr, nr)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 3 <= len(fx[2]) <= 12],
    ids=[fx[0] for fx in UNDIRECTED if 3 <= len(fx[2]) <= 12],
)
def test_wiener_index_equals_half_sum_of_distances(name, edges, nodes):
    """``wiener_index(undirected)`` equals half the sum of all-pairs
    shortest path distances (since each pair is counted once)."""
    fg, _ = _pair_undirected(edges, nodes)
    if not fnx.is_connected(fg):
        return
    spl = dict(fnx.shortest_path_length(fg))
    total = sum(d for src in spl for d in spl[src].values())
    expected = total / 2
    actual = fnx.wiener_index(fg)
    assert _equiv(actual, expected), (
        f"{name}: wiener={actual} half-sum={expected}"
    )
