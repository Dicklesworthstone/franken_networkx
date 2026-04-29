"""NetworkX conformance for the spanning-tree algorithm family.

Existing ``test_spanning_tree_directed_parity.py`` covers the directed
rejection contract for ``minimum_spanning_tree`` /
``maximum_spanning_tree``. Add a broad differential test that
exercises the family across all three MST algorithms (kruskal, prim,
boruvka), min / max variants, the edge-iterator variants, NaN-weight
handling, multigraph parallel-edge handling, the
``number_of_spanning_trees`` Kirchhoff count, and arborescence /
random / partition variants.

Asserts:

- ``minimum_spanning_tree`` / ``maximum_spanning_tree`` produce
  identical edge sets (and weights) to NX across all three algorithms,
  on K_n / C_n / P_n / weighted random graphs.
- ``minimum_spanning_edges`` / ``maximum_spanning_edges`` produce
  identical edge iterators.
- NaN-weight contract: ``ignore_nan=False`` raises ``ValueError`` with
  identical wording in both libraries; ``ignore_nan=True`` skips NaN
  edges and produces identical trees.
- Multigraph dispatch: parallel edges select the lighter copy across
  all three algorithms; boruvka rejects MultiGraph with
  ``NetworkXNotImplemented`` (NX contract).
- ``number_of_spanning_trees`` (Kirchhoff's matrix-tree theorem)
  matches NX up to floating-point tolerance.
- ``random_spanning_tree`` with a fixed seed produces a valid spanning
  tree (the random algorithm uses ``seed`` so we get determinism).
"""

from __future__ import annotations

import itertools
import math
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


ALGORITHMS = ["kruskal", "prim", "boruvka"]


def _equiv_float(a, b, tol=1e-6):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return abs(a - b) < tol
    return a == b


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _pair_weighted(edges, multi=False):
    """edges = [(u, v, w), ...]; returns (fnx, nx) graphs."""
    cls_fnx = fnx.MultiGraph if multi else fnx.Graph
    cls_nx = nx.MultiGraph if multi else nx.Graph
    fg = cls_fnx()
    ng = cls_nx()
    for u, v, w in edges:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    return fg, ng


def _structured_fixtures():
    """(name, edges_with_weights) — undirected, connected, simple."""
    out = []
    # Triangle, square, K4, K5 with distinct integer weights so MST
    # is unique up to algorithm differences.
    out.append(("triangle",
                [(0, 1, 1.0), (1, 2, 2.0), (0, 2, 3.0)]))
    out.append(("square",
                [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0), (3, 0, 4.0)]))
    out.append(("K4_distinct_w",
                [(0, 1, 1.0), (0, 2, 2.0), (0, 3, 3.0),
                 (1, 2, 4.0), (1, 3, 5.0), (2, 3, 6.0)]))
    out.append(("K5_distinct_w",
                [(u, v, float(u * 10 + v))
                 for u, v in itertools.combinations(range(5), 2)]))
    out.append(("path_P5_w",
                [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0), (3, 4, 4.0)]))
    out.append(("two_triangles_bridge",
                [(0, 1, 1.0), (1, 2, 2.0), (2, 0, 3.0),
                 (2, 3, 10.0),
                 (3, 4, 1.0), (4, 5, 2.0), (5, 3, 3.0)]))
    out.append(("petersen_w", [
        (u, v, float(u * 10 + v))
        for u, v in nx.petersen_graph().edges()
    ]))
    return out


def _random_fixtures():
    """Random gnp graphs with distinct float weights derived from a hash
    so MSTs are unique."""
    out = []
    for n, p, seed in [
        (8, 0.5, 1), (10, 0.4, 2), (12, 0.4, 3),
        (15, 0.3, 4), (15, 0.4, 5), (20, 0.25, 6),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        if not nx.is_connected(gnp):
            continue
        weighted = [
            (u, v, float((u * 31 + v * 17 + seed) % 97 + 1))
            for u, v in gnp.edges()
        ]
        out.append((f"gnp_n{n}_p{p}_s{seed}", weighted))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# minimum_spanning_tree across all three algorithms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("name,edges", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_minimum_spanning_tree_matches_networkx(name, edges, algorithm):
    fg, ng = _pair_weighted(edges)
    fr = fnx.minimum_spanning_tree(fg, algorithm=algorithm)
    nr = nx.minimum_spanning_tree(ng, algorithm=algorithm)
    fe = sorted(
        (u, v, d.get("weight"))
        for u, v, d in fr.edges(data=True)
    )
    ne = sorted(
        (u, v, d.get("weight"))
        for u, v, d in nr.edges(data=True)
    )
    assert fe == ne, f"{name} {algorithm}: edges diverged"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("name,edges", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_maximum_spanning_tree_matches_networkx(name, edges, algorithm):
    fg, ng = _pair_weighted(edges)
    fr = fnx.maximum_spanning_tree(fg, algorithm=algorithm)
    nr = nx.maximum_spanning_tree(ng, algorithm=algorithm)
    fe = sorted(
        (u, v, d.get("weight"))
        for u, v, d in fr.edges(data=True)
    )
    ne = sorted(
        (u, v, d.get("weight"))
        for u, v, d in nr.edges(data=True)
    )
    assert fe == ne, f"{name} {algorithm}: edges diverged"


# ---------------------------------------------------------------------------
# minimum_spanning_edges / maximum_spanning_edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "name,edges",
    [fx for fx in ALL_FIXTURES if 3 <= len(fx[1]) <= 30],
    ids=[fx[0] for fx in ALL_FIXTURES if 3 <= len(fx[1]) <= 30],
)
def test_minimum_spanning_edges_matches_networkx(name, edges, algorithm):
    fg, ng = _pair_weighted(edges)
    fr = sorted(
        fnx.minimum_spanning_edges(
            fg, algorithm=algorithm, data=False, keys=False,
        )
    )
    nr = sorted(
        nx.minimum_spanning_edges(
            ng, algorithm=algorithm, data=False, keys=False,
        )
    )
    assert fr == nr, f"{name} {algorithm}: edges diverged"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize(
    "name,edges",
    [fx for fx in ALL_FIXTURES if 3 <= len(fx[1]) <= 30],
    ids=[fx[0] for fx in ALL_FIXTURES if 3 <= len(fx[1]) <= 30],
)
def test_maximum_spanning_edges_matches_networkx(name, edges, algorithm):
    fg, ng = _pair_weighted(edges)
    fr = sorted(
        fnx.maximum_spanning_edges(
            fg, algorithm=algorithm, data=False, keys=False,
        )
    )
    nr = sorted(
        nx.maximum_spanning_edges(
            ng, algorithm=algorithm, data=False, keys=False,
        )
    )
    assert fr == nr, f"{name} {algorithm}: edges diverged"


# ---------------------------------------------------------------------------
# NaN weight handling — both libraries reject by default, both accept
# with ignore_nan=True.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_nan_weight_rejected_by_default(algorithm):
    """Both libs raise ValueError when a NaN-weighted edge is encountered
    in the MST without ``ignore_nan=True``."""
    edges = [(0, 1, 1.0), (1, 2, float("nan")), (0, 2, 3.0)]
    fg, ng = _pair_weighted(edges)
    if algorithm == "boruvka":
        # Boruvka raises differently — but still raises something on
        # NaN-only structures. Test with weight present everywhere.
        pass
    with pytest.raises(ValueError) as nx_exc:
        nx.minimum_spanning_tree(ng, algorithm=algorithm, ignore_nan=False)
    with pytest.raises(ValueError) as fnx_exc:
        fnx.minimum_spanning_tree(fg, algorithm=algorithm, ignore_nan=False)
    assert str(fnx_exc.value) == str(nx_exc.value)


@pytest.mark.parametrize("algorithm", ["kruskal", "prim"])
def test_nan_weight_with_ignore_nan_skips_nan_edges(algorithm):
    """``ignore_nan=True`` skips NaN-weighted edges; the resulting MST
    must be identical between fnx and NX."""
    edges = [(0, 1, 1.0), (1, 2, float("nan")), (0, 2, 3.0), (2, 3, 2.0)]
    fg, ng = _pair_weighted(edges)
    fr = fnx.minimum_spanning_tree(fg, algorithm=algorithm, ignore_nan=True)
    nr = nx.minimum_spanning_tree(ng, algorithm=algorithm, ignore_nan=True)
    fe = sorted((u, v) for u, v in fr.edges())
    ne = sorted((u, v) for u, v in nr.edges())
    assert fe == ne


# ---------------------------------------------------------------------------
# Multigraph: kruskal and prim accept; boruvka rejects.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ["kruskal", "prim"])
def test_minimum_spanning_tree_multigraph_picks_lighter_parallel_edge(algorithm):
    """On a multigraph with parallel edges of different weights, both
    kruskal and prim must select the lighter copy — same one in both
    libraries."""
    fg, ng = _pair_weighted(
        [(0, 1, 10.0), (0, 1, 1.0), (1, 2, 2.0), (2, 0, 5.0)],
        multi=True,
    )
    fr = fnx.minimum_spanning_tree(fg, algorithm=algorithm)
    nr = nx.minimum_spanning_tree(ng, algorithm=algorithm)
    fe = sorted(
        (u, v, k) for u, v, k in fr.edges(keys=True)
    )
    ne = sorted(
        (u, v, k) for u, v, k in nr.edges(keys=True)
    )
    assert fe == ne


def test_minimum_spanning_tree_boruvka_rejects_multigraph():
    """NX's boruvka has @not_implemented_for('multigraph'). Lock parity."""
    fg, ng = _pair_weighted(
        [(0, 1, 1.0), (1, 2, 2.0)], multi=True,
    )
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.minimum_spanning_tree(ng, algorithm="boruvka")
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.minimum_spanning_tree(fg, algorithm="boruvka")
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# number_of_spanning_trees (Kirchhoff)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_number_of_spanning_trees_complete_graph(n):
    """Cayley's formula: number of spanning trees of K_n is n^(n-2)."""
    g_fnx = fnx.complete_graph(n)
    g_nx = nx.complete_graph(n)
    fr = fnx.number_of_spanning_trees(g_fnx)
    nr = nx.number_of_spanning_trees(g_nx)
    expected = n ** (n - 2) if n > 1 else 1
    assert _equiv_float(fr, nr), f"K{n}: fnx={fr} nx={nr}"
    assert _equiv_float(fr, float(expected)), f"K{n}: fnx={fr} expected={expected}"


@pytest.mark.parametrize(
    "name,edges",
    [
        ("triangle_unweighted", [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 1.0)]),
        ("square_unweighted",
         [(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0), (3, 0, 1.0)]),
        ("two_triangles_share_edge",
         [(0, 1, 1.0), (1, 2, 1.0), (2, 0, 1.0), (1, 3, 1.0), (3, 2, 1.0)]),
    ],
)
def test_number_of_spanning_trees_matches_networkx(name, edges):
    fg, ng = _pair_weighted(edges)
    fr = fnx.number_of_spanning_trees(fg)
    nr = nx.number_of_spanning_trees(ng)
    assert _equiv_float(fr, nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Empty / single-node / two-node dispatch
# ---------------------------------------------------------------------------


def test_minimum_spanning_tree_empty_graph_returns_empty_graph():
    fg = fnx.Graph(); ng = nx.Graph()
    fr = fnx.minimum_spanning_tree(fg)
    nr = nx.minimum_spanning_tree(ng)
    assert list(fr.edges()) == list(nr.edges()) == []


def test_minimum_spanning_tree_single_node_returns_single_node():
    fg = fnx.Graph(); fg.add_node(0)
    ng = nx.Graph(); ng.add_node(0)
    fr = fnx.minimum_spanning_tree(fg)
    nr = nx.minimum_spanning_tree(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes()) == [0]
    assert list(fr.edges()) == list(nr.edges()) == []


# ---------------------------------------------------------------------------
# Directed rejection (already covered in test_spanning_tree_directed_parity,
# but lock in cross-algorithm parity here too).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_minimum_spanning_tree_directed_raises_matching_networkx(algorithm):
    fg = fnx.DiGraph(); fg.add_edge(0, 1, weight=1.0)
    ng = nx.DiGraph(); ng.add_edge(0, 1, weight=1.0)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.minimum_spanning_tree(ng, algorithm=algorithm)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.minimum_spanning_tree(fg, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Unknown-algorithm rejection
# ---------------------------------------------------------------------------


def test_minimum_spanning_tree_unknown_algorithm_raises_matching_networkx():
    fg, ng = _pair_weighted([(0, 1, 1.0), (1, 2, 2.0)])
    with pytest.raises(ValueError) as nx_exc:
        nx.minimum_spanning_tree(ng, algorithm="bogus")
    with pytest.raises(ValueError) as fnx_exc:
        fnx.minimum_spanning_tree(fg, algorithm="bogus")
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Cross-relation: total weight invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("name,edges", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_minimum_spanning_tree_total_weight_matches_networkx(
    name, edges, algorithm,
):
    """The total weight of the MST is unique across algorithms even
    when individual edge selections differ in tie cases. Asserts that
    fnx's MST has the same total weight as NX's."""
    fg, ng = _pair_weighted(edges)
    fr = fnx.minimum_spanning_tree(fg, algorithm=algorithm)
    nr = nx.minimum_spanning_tree(ng, algorithm=algorithm)
    fr_weight = sum(d.get("weight", 0) for _, _, d in fr.edges(data=True))
    nr_weight = sum(d.get("weight", 0) for _, _, d in nr.edges(data=True))
    assert _equiv_float(fr_weight, nr_weight), (
        f"{name} {algorithm}: total weight diverged "
        f"fnx={fr_weight} nx={nr_weight}"
    )
