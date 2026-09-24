"""Differential + golden parity for covering / dominating predicates.

Covers ``min_edge_cover`` (a minimum-cardinality set of edges incident to
every node), ``is_edge_cover`` and ``is_dominating_set``. None had a
dedicated test file.

A minimum edge cover is not unique, so ``min_edge_cover`` is checked by
*cardinality* parity plus cross-validation (fnx's cover is a valid cover
according to upstream nx and covers every non-isolated node). The
deterministic boolean predicates ``is_edge_cover`` / ``is_dominating_set``
are checked for exact parity on random ``(graph, subset)`` inputs.

br-r37-c1-8mtqp
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.4, no_isolated=False):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    while True:
        fg = fnx.Graph()
        ng = nx.Graph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
        fg.add_edges_from(edges)
        ng.add_edges_from(edges)
        if not no_isolated or (ng.number_of_nodes() and min(dict(ng.degree()).values()) > 0):
            return fg, ng, n, edges
        p = min(0.9, p + 0.05)


def _norm_edges(edges):
    return {tuple(sorted(e)) for e in edges}


# ---------------------------------------------------------------------------
# min_edge_cover: cardinality parity + cross-validation.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_min_edge_cover_parity_and_validity(seed):
    fg, ng, _, _ = _pair(seed, no_isolated=True)
    fcover = _norm_edges(fnx.min_edge_cover(fg))
    ncover = _norm_edges(nx.min_edge_cover(ng))
    # Minimum edge covers are not unique: match cardinality, ...
    assert len(fcover) == len(ncover), f"seed={seed}: cover size differs"
    # ...and fnx's cover must be a valid edge cover per upstream nx.
    assert nx.is_edge_cover(ng, fcover), f"seed={seed}: fnx cover invalid per nx"
    # Every node is incident to some covered edge.
    covered = {x for e in fcover for x in e}
    assert covered == set(ng.nodes()), f"seed={seed}: a node is uncovered"


# ---------------------------------------------------------------------------
# is_edge_cover differential.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_is_edge_cover_matches_networkx(seed):
    fg, ng, _, edges = _pair(seed)
    if not edges:
        pytest.skip("no edges")
    rng = random.Random(seed * 7 + 1)
    subset = {tuple(sorted(e)) for e in edges if rng.random() < 0.6}
    assert fnx.is_edge_cover(fg, subset) == nx.is_edge_cover(ng, subset)


# ---------------------------------------------------------------------------
# is_dominating_set differential.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_is_dominating_set_matches_networkx(seed):
    fg, ng, n, _ = _pair(seed)
    rng = random.Random(seed * 11 + 3)
    subset = set(rng.sample(range(n), rng.randint(1, n)))
    assert fnx.is_dominating_set(fg, subset) == nx.is_dominating_set(ng, subset)


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_is_dominating_set_goldens():
    p4 = fnx.path_graph(4)  # 0-1-2-3
    assert fnx.is_dominating_set(p4, {1, 2})       # 1 dominates 0,2; 2 dominates 3
    assert fnx.is_dominating_set(p4, {0, 2})       # 0 dominates 1; 2 dominates 3
    assert not fnx.is_dominating_set(p4, {0})      # node 3 undominated
    # Center of a star dominates everything.
    star = fnx.star_graph(5)
    assert fnx.is_dominating_set(star, {0})


def test_is_edge_cover_goldens():
    p4 = fnx.path_graph(4)
    assert fnx.is_edge_cover(p4, {(0, 1), (2, 3)})       # covers all 4 nodes
    assert not fnx.is_edge_cover(p4, {(0, 1)})           # nodes 2,3 uncovered
    assert fnx.is_edge_cover(p4, {(0, 1), (1, 2), (2, 3)})


@pytest.mark.parametrize(
    "cover",
    [{(0, 0), (1, 1)}, {(0, 1), (1, 0)}, {(0, 1)}, {(0, 0)}, {(1, 0, 9)}, set()],
)
def test_is_edge_cover_is_node_coverage_like_networkx(cover):
    # nro4w.7: networkx checks only that every node is an endpoint of some
    # pair in the cover (``set(G) <= set(chain(*cover))``); the pairs need not
    # be edges of G. The native check also required them to be edges, so the
    # self-loop cover of networkx's test_graph_single_edge read False.
    G = fnx.Graph([(0, 1)])
    H = nx.Graph([(0, 1)])
    assert fnx.is_edge_cover(G, cover) == nx.is_edge_cover(H, cover)


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_is_edge_cover_rejects_directed_graphs_like_networkx(cls_name):
    # networkx decorates is_edge_cover with @not_implemented_for("directed").
    with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for directed type"):
        nx.is_edge_cover(getattr(nx, cls_name)([(0, 1)]), {(0, 1)})
    with pytest.raises(nx.NetworkXNotImplemented, match="not implemented for directed type"):
        fnx.is_edge_cover(getattr(fnx, cls_name)([(0, 1)]), {(0, 1)})


def test_is_edge_cover_accepts_multigraphs_like_networkx():
    G = fnx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    H = nx.MultiGraph([(0, 1), (0, 1), (1, 2)])
    for cover in ({(0, 1), (1, 2)}, {(0, 1)}, {(2, 0), (1, 1)}):
        assert fnx.is_edge_cover(G, cover) == nx.is_edge_cover(H, cover)
