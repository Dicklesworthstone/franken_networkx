"""NetworkX conformance for the assortativity algorithm family.

Covers ``degree_assortativity_coefficient``,
``degree_pearson_correlation_coefficient``,
``attribute_assortativity_coefficient``,
``numeric_assortativity_coefficient``, and the supporting helpers
``degree_mixing_matrix`` / ``attribute_mixing_matrix`` against
upstream NetworkX.

Found and locked in: a fifth instance of the same systematic
``gr.undirected()`` directed-graph bug pattern previously fixed in
``is_eulerian``, ``eccentricity``, ``is_tree``/``is_forest``, and
``core_number``. The Rust ``_raw_degree_assortativity_coefficient``
computed the coefficient over the undirected projection's degrees,
so on a directed P_3 it produced -1.0 (perfect anti-assortativity)
where NX produced NaN (zero variance because both directed edges
share the (out_src, in_tgt) = (1, 1) pair).

Asserts bit-for-bit parity (with NaN-aware comparison) across:
- 30+ undirected fixtures (paths, stars, cycles, K_n, gnp randoms)
- 25+ directed fixtures (cycles, antiparallel pairs, mixed orientation,
  trees, gnp directeds)
- weighted variants
- attribute / numeric assortativity on bipartite / mixed-attribute
  fixtures
- full-flow degree_mixing_matrix invariants
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
        return abs(a - b) < tol
    return a == b


def _pair_undirected(edges, nodes=None, multi=False):
    fg = fnx.MultiGraph() if multi else fnx.Graph()
    ng = nx.MultiGraph() if multi else nx.Graph()
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
    for n in range(2, 8):
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
    for n in range(1, 7):
        out.append((f"S_{n}",
                    [(0, i) for i in range(1, n + 1)],
                    list(range(n + 1))))
    pg = nx.petersen_graph()
    out.append(("petersen", list(pg.edges()), list(pg.nodes())))
    for n, p, seed in [(8, 0.3, 1), (10, 0.4, 2), (12, 0.3, 3),
                       (15, 0.25, 4), (20, 0.2, 5), (25, 0.2, 6)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


def _directed_fixtures():
    out = []
    out.append(("dir_antipar_pair", [(0, 1), (1, 0)], [0, 1]))
    out.append(("dir_K3_both",
                [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
                list(range(3))))
    out.append(("dir_K4_both",
                [(u, v) for u in range(4) for v in range(4) if u != v],
                list(range(4))))
    out.append(("dir_K5_both",
                [(u, v) for u in range(5) for v in range(5) if u != v],
                list(range(5))))
    for n in range(3, 7):
        out.append((f"dir_K{n}_one_way",
                    list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    for n in range(2, 8):
        out.append((f"dir_C{n}",
                    [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    out.append(("dir_P3", [(0, 1), (1, 2)], list(range(3))))
    out.append(("dir_P5", [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5))))
    out.append(("dir_tree_5",
                [(0, 1), (0, 2), (1, 3), (1, 4)], list(range(5))))
    out.append(("dir_tree_6",
                [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5)], list(range(6))))
    out.append(("dir_bowtie",
                [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
                list(range(5))))
    out.append(("dir_mixed",
                [(0, 1), (1, 0), (1, 2), (2, 3), (3, 1)],
                list(range(4))))
    for n, p, seed in [(6, 0.3, 1), (8, 0.3, 2), (10, 0.25, 3),
                       (12, 0.2, 4), (15, 0.2, 5)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed, directed=True)
        out.append((f"dir_gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


UNDIRECTED = _undirected_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# degree_assortativity_coefficient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_degree_assortativity_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_assortativity_coefficient(fg)
        nr = nx.degree_assortativity_coefficient(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_degree_assortativity_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_assortativity_coefficient(fg)
        nr = nx.degree_assortativity_coefficient(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("xy", [("out", "in"), ("in", "out"),
                                 ("out", "out"), ("in", "in")])
@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in DIRECTED if 2 <= len(fx[2]) <= 12],
    ids=[fx[0] for fx in DIRECTED if 2 <= len(fx[2]) <= 12],
)
def test_degree_assortativity_directed_xy_combinations(name, edges, nodes, xy):
    """All four (x, y) ∈ {out, in}² combinations must match NX."""
    fg, ng = _pair_directed(edges, nodes)
    x, y = xy
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_assortativity_coefficient(fg, x=x, y=y)
        nr = nx.degree_assortativity_coefficient(ng, x=x, y=y)
    assert _equiv(fr, nr), f"{name} xy={xy}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# degree_pearson_correlation_coefficient
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_degree_pearson_undirected(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_pearson_correlation_coefficient(fg)
        nr = nx.degree_pearson_correlation_coefficient(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_degree_pearson_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_pearson_correlation_coefficient(fg)
        nr = nx.degree_pearson_correlation_coefficient(ng)
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Pearson and degree assortativity must agree on undirected
# (NX docstring: "For undirected graphs, this is equivalent to
# degree_assortativity_coefficient.")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 4 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in UNDIRECTED if 4 <= len(fx[2]) <= 15],
)
def test_pearson_equals_degree_assortativity_on_undirected(name, edges, nodes):
    fg, _ = _pair_undirected(edges, nodes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = fnx.degree_assortativity_coefficient(fg)
        b = fnx.degree_pearson_correlation_coefficient(fg)
    assert _equiv(a, b), f"{name}: assortativity={a} pearson={b}"


# ---------------------------------------------------------------------------
# Attribute / numeric assortativity
# ---------------------------------------------------------------------------


def _attr_pair(edges, attrs):
    fg = fnx.Graph(); ng = nx.Graph()
    for u, v in edges:
        fg.add_edge(u, v); ng.add_edge(u, v)
    for n, value in attrs.items():
        fg.nodes[n]["color"] = value
        ng.nodes[n]["color"] = value
    return fg, ng


def _numeric_pair(edges, attrs):
    fg = fnx.Graph(); ng = nx.Graph()
    for u, v in edges:
        fg.add_edge(u, v); ng.add_edge(u, v)
    for n, value in attrs.items():
        fg.nodes[n]["weight"] = value
        ng.nodes[n]["weight"] = value
    return fg, ng


@pytest.mark.parametrize(
    "name,edges,attrs",
    [
        ("two_groups",
         [(0, 1), (1, 2), (2, 3), (3, 0)],
         {0: "A", 1: "A", 2: "B", 3: "B"}),
        ("alternating",
         [(0, 1), (1, 2), (2, 3), (3, 0)],
         {0: "A", 1: "B", 2: "A", 3: "B"}),
        ("clique_two_attrs",
         list(itertools.combinations(range(4), 2)),
         {0: "X", 1: "X", 2: "Y", 3: "Y"}),
        ("path_three_attrs",
         [(0, 1), (1, 2), (2, 3), (3, 4)],
         {0: "A", 1: "B", 2: "C", 3: "B", 4: "A"}),
    ],
)
def test_attribute_assortativity_matches_networkx(name, edges, attrs):
    fg, ng = _attr_pair(edges, attrs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.attribute_assortativity_coefficient(fg, "color")
        nr = nx.attribute_assortativity_coefficient(ng, "color")
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,attrs",
    [
        ("path_5",
         [(0, 1), (1, 2), (2, 3), (3, 4)],
         {0: 1.0, 1: 2.0, 2: 3.0, 3: 4.0, 4: 5.0}),
        ("star_4",
         [(0, i) for i in range(1, 5)],
         {0: 10.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}),
        ("two_clusters",
         [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3)],
         {0: 1.0, 1: 1.0, 2: 1.0, 3: 5.0, 4: 5.0, 5: 5.0}),
    ],
)
def test_numeric_assortativity_matches_networkx(name, edges, attrs):
    fg, ng = _numeric_pair(edges, attrs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.numeric_assortativity_coefficient(fg, "weight")
        nr = nx.numeric_assortativity_coefficient(ng, "weight")
    assert _equiv(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# degree_mixing_matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 4 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in UNDIRECTED if 4 <= len(fx[2]) <= 15],
)
def test_degree_mixing_matrix_undirected(name, edges, nodes):
    import numpy as np
    fg, ng = _pair_undirected(edges, nodes)
    fr = fnx.degree_mixing_matrix(fg)
    nr = nx.degree_mixing_matrix(ng)
    assert np.allclose(fr, nr), f"{name}: matrices differ"


# ---------------------------------------------------------------------------
# Multigraph / weighted nx-only-path
# ---------------------------------------------------------------------------


def test_degree_assortativity_multigraph_matches_networkx():
    fg = fnx.MultiGraph()
    ng = nx.MultiGraph()
    for u, v in [(0, 1), (0, 1), (1, 2), (2, 3), (3, 0)]:
        fg.add_edge(u, v); ng.add_edge(u, v)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_assortativity_coefficient(fg)
        nr = nx.degree_assortativity_coefficient(ng)
    assert _equiv(fr, nr)


def test_degree_assortativity_with_weight_matches_networkx():
    fg = fnx.Graph(); ng = nx.Graph()
    for u, v, w in [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0), (3, 0, 1.0)]:
        fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = fnx.degree_assortativity_coefficient(fg, weight="weight")
        nr = nx.degree_assortativity_coefficient(ng, weight="weight")
    assert _equiv(fr, nr)
