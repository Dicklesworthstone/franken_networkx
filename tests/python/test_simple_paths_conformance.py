"""NetworkX conformance for the simple-paths algorithm family.

Existing ``test_shortest_simple_paths_msg_parity.py`` checks one
specific error message; there's no broad differential test for this
family. Add 200+ parametrised cases covering every supported
parameter shape across structured + random fixtures.

Covered functions:

- ``all_simple_paths(G, source, target, cutoff=...)`` — generator of
  simple paths (or paths up to length ``cutoff``).
- ``all_simple_edge_paths(G, source, target, cutoff=...)`` — same
  but yields edge tuples instead of node lists.
- ``shortest_simple_paths(G, source, target, weight=...)`` — Yen's
  algorithm; yields paths in non-decreasing length order.
- ``has_path(G, source, target)`` — connectivity predicate.

Edge cases locked in:

- Iterable ``target`` — NX yields paths whose endpoint is *any* node
  in the iterable.
- ``source == target`` — NX yields ``[[source]]``.
- ``source`` / ``target`` not in graph — NX raises
  ``NodeNotFound`` with specific wording; lock it in.
- Cutoff bounds: 0, 1, 2, ..., diameter.
- Multigraph parallel-edge handling — ``all_simple_paths`` collapses
  parallels (each parallel produces a separate path) and
  ``all_simple_edge_paths`` yields ``(u, v, key)`` triples.
- Directed graphs — DAG vs cyclic.
"""

from __future__ import annotations

import itertools
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


def _pair_undirected(edges, nodes=None, multi=False):
    cls_fnx = fnx.MultiGraph if multi else fnx.Graph
    cls_nx = nx.MultiGraph if multi else nx.Graph
    fg = cls_fnx()
    ng = cls_nx()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _pair_directed(edges, nodes=None, multi=False):
    cls_fnx = fnx.MultiDiGraph if multi else fnx.DiGraph
    cls_nx = nx.MultiDiGraph if multi else nx.DiGraph
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
# Fixtures
# ---------------------------------------------------------------------------


def _undirected_fixtures():
    """Return (name, edges, nodes, source, target)."""
    out = []
    out.append(("K_3_diag", list(itertools.combinations(range(3), 2)),
                list(range(3)), 0, 2))
    out.append(("K_4_diag", list(itertools.combinations(range(4), 2)),
                list(range(4)), 0, 3))
    out.append(("K_5_diag", list(itertools.combinations(range(5), 2)),
                list(range(5)), 0, 4))
    out.append(("C_4_opp",
                [(i, (i + 1) % 4) for i in range(4)], list(range(4)), 0, 2))
    out.append(("C_6_opp",
                [(i, (i + 1) % 6) for i in range(6)], list(range(6)), 0, 3))
    out.append(("P_5_endpoints",
                [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)), 0, 4))
    out.append(("S_4_leaf_to_leaf",
                [(0, i) for i in range(1, 5)], list(range(5)), 1, 4))
    out.append(("two_triangles_share_edge",
                [(0, 1), (1, 2), (2, 0), (1, 3), (3, 2)],
                list(range(4)), 0, 3))
    out.append(("bowtie",
                [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
                list(range(5)), 0, 4))
    out.append(("petersen",
                list(nx.petersen_graph().edges()),
                list(nx.petersen_graph().nodes()), 0, 5))
    out.append(("disjoint_K3_K3",
                [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
                list(range(6)), 0, 4))
    for n, p, seed in [(7, 0.4, 1), (8, 0.4, 2), (10, 0.3, 3)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        if not nx.is_connected(gnp):
            continue
        nodes = list(range(n))
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), nodes, 0, n - 1))
    return out


def _directed_fixtures():
    out = []
    out.append(("dir_DAG_diamond",
                [(0, 1), (0, 2), (1, 3), (2, 3)],
                list(range(4)), 0, 3))
    out.append(("dir_DAG_path_plus_chord",
                [(0, 1), (1, 2), (2, 3), (0, 3)],
                list(range(4)), 0, 3))
    out.append(("dir_C_4",
                [(0, 1), (1, 2), (2, 3), (3, 0)],
                list(range(4)), 0, 2))
    out.append(("dir_K3_both",
                [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
                list(range(3)), 0, 2))
    out.append(("dir_chain_5",
                [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)), 0, 4))
    return out


UNDIRECTED = _undirected_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# all_simple_paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes,source,target", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_all_simple_paths_undirected_matches_networkx(
    name, edges, nodes, source, target,
):
    fg, ng = _pair_undirected(edges, nodes)
    fr = sorted(tuple(p) for p in fnx.all_simple_paths(fg, source, target))
    nr = sorted(tuple(p) for p in nx.all_simple_paths(ng, source, target))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes,source,target", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_all_simple_paths_directed_matches_networkx(
    name, edges, nodes, source, target,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = sorted(tuple(p) for p in fnx.all_simple_paths(fg, source, target))
    nr = sorted(tuple(p) for p in nx.all_simple_paths(ng, source, target))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("cutoff", [0, 1, 2, 3, 4, 5])
@pytest.mark.parametrize(
    "name,edges,nodes,source,target",
    [fx for fx in UNDIRECTED if 4 <= len(fx[2]) <= 8],
    ids=[fx[0] for fx in UNDIRECTED if 4 <= len(fx[2]) <= 8],
)
def test_all_simple_paths_with_cutoff_matches_networkx(
    name, edges, nodes, source, target, cutoff,
):
    fg, ng = _pair_undirected(edges, nodes)
    fr = sorted(
        tuple(p)
        for p in fnx.all_simple_paths(fg, source, target, cutoff=cutoff)
    )
    nr = sorted(
        tuple(p)
        for p in nx.all_simple_paths(ng, source, target, cutoff=cutoff)
    )
    assert fr == nr, f"{name} cutoff={cutoff}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes,source,targets",
    [
        ("K_4_iter_targets",
         list(itertools.combinations(range(4), 2)),
         list(range(4)), 0, [2, 3]),
        ("P_5_iter_targets",
         [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5)), 0, [3, 4]),
        ("petersen_iter_targets",
         list(nx.petersen_graph().edges()),
         list(nx.petersen_graph().nodes()), 0, [3, 5, 7]),
    ],
)
def test_all_simple_paths_iterable_target_matches_networkx(
    name, edges, nodes, source, targets,
):
    """NX yields paths whose endpoint is *any* node in the iterable."""
    fg, ng = _pair_undirected(edges, nodes)
    fr = sorted(tuple(p) for p in fnx.all_simple_paths(fg, source, targets))
    nr = sorted(tuple(p) for p in nx.all_simple_paths(ng, source, targets))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# all_simple_edge_paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes,source,target", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_all_simple_edge_paths_undirected_matches_networkx(
    name, edges, nodes, source, target,
):
    fg, ng = _pair_undirected(edges, nodes)
    fr = sorted(
        tuple(p) for p in fnx.all_simple_edge_paths(fg, source, target)
    )
    nr = sorted(
        tuple(p) for p in nx.all_simple_edge_paths(ng, source, target)
    )
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes,source,target", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_all_simple_edge_paths_directed_matches_networkx(
    name, edges, nodes, source, target,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = sorted(
        tuple(p) for p in fnx.all_simple_edge_paths(fg, source, target)
    )
    nr = sorted(
        tuple(p) for p in nx.all_simple_edge_paths(ng, source, target)
    )
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# shortest_simple_paths (Yen's algorithm)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges_with_w,source,target",
    [
        ("triangle_w",
         [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 3.0)], 0, 2),
        ("diamond_w",
         [(0, 1, 1.0), (1, 2, 1.0), (0, 2, 3.0),
          (2, 3, 1.0), (1, 3, 4.0), (0, 3, 10.0)], 0, 3),
        ("K_4_w",
         [(u, v, float(u + v + 1))
          for u, v in itertools.combinations(range(4), 2)], 0, 3),
        ("path_5_w",
         [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0), (3, 4, 4.0)], 0, 4),
    ],
)
def test_shortest_simple_paths_weighted_matches_networkx(
    name, edges_with_w, source, target,
):
    fg = fnx.Graph(); ng = nx.Graph()
    for u, v, w in edges_with_w:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    fr = list(fnx.shortest_simple_paths(fg, source, target, weight="weight"))
    nr = list(nx.shortest_simple_paths(ng, source, target, weight="weight"))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes,source,target", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_shortest_simple_paths_unweighted_matches_networkx(
    name, edges, nodes, source, target,
):
    """Yen's algorithm yields paths in non-decreasing length order, but
    *within* each length group the tie-break order is implementation-
    defined. Compare paths grouped by length so the harness doesn't
    fail on different (but equally valid) orderings inside a group."""
    fg, ng = _pair_undirected(edges, nodes)
    if not fnx.is_connected(fg):
        return  # NX raises on disconnected
    fr = list(fnx.shortest_simple_paths(fg, source, target))
    nr = list(nx.shortest_simple_paths(ng, source, target))

    def _group_by_length(paths):
        out = {}
        for p in paths:
            out.setdefault(len(p), set()).add(tuple(p))
        return out

    assert _group_by_length(fr) == _group_by_length(nr), (
        f"{name}: path multiset diverged"
    )
    # Length sequence must be non-decreasing in both libraries.
    assert [len(p) for p in fr] == sorted(len(p) for p in fr)
    assert [len(p) for p in nr] == sorted(len(p) for p in nr)


# ---------------------------------------------------------------------------
# has_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes,source,target", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_has_path_undirected_matches_networkx(
    name, edges, nodes, source, target,
):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.has_path(fg, source, target) == nx.has_path(ng, source, target)


@pytest.mark.parametrize("name,edges,nodes,source,target", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_has_path_directed_matches_networkx(
    name, edges, nodes, source, target,
):
    fg, ng = _pair_directed(edges, nodes)
    assert fnx.has_path(fg, source, target) == nx.has_path(ng, source, target)


# ---------------------------------------------------------------------------
# Multigraph dispatch — parallel edges multiply path count
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,parallel_edges,source,target,expected_count",
    [
        ("two_parallel_edges_then_one",
         [(0, 1), (0, 1), (1, 2)], 0, 2, 2),
        ("three_parallel_edges_then_one",
         [(0, 1), (0, 1), (0, 1), (1, 2)], 0, 2, 3),
    ],
)
def test_all_simple_paths_multigraph_matches_networkx(
    name, parallel_edges, source, target, expected_count,
):
    fg, ng = _pair_undirected(parallel_edges, multi=True)
    fr = list(fnx.all_simple_paths(fg, source, target))
    nr = list(nx.all_simple_paths(ng, source, target))
    assert fr == nr == [[0, 1, 2]] * expected_count


def test_all_simple_edge_paths_multigraph_yields_keyed_tuples():
    """``all_simple_edge_paths`` on a MultiGraph yields ``(u, v, key)``
    triples per edge — distinguishing parallel copies."""
    fg, ng = _pair_undirected(
        [(0, 1), (0, 1), (1, 2)], multi=True,
    )
    fr = sorted(tuple(p) for p in fnx.all_simple_edge_paths(fg, 0, 2))
    nr = sorted(tuple(p) for p in nx.all_simple_edge_paths(ng, 0, 2))
    assert fr == nr


# ---------------------------------------------------------------------------
# Edge cases — source == target, missing nodes
# ---------------------------------------------------------------------------


def test_all_simple_paths_source_equals_target_yields_singleton():
    fg, ng = _pair_undirected(list(itertools.combinations(range(4), 2)),
                               list(range(4)))
    assert list(fnx.all_simple_paths(fg, 0, 0)) == list(
        nx.all_simple_paths(ng, 0, 0)
    ) == [[0]]


def test_all_simple_paths_missing_source_raises_matching_networkx():
    fg, ng = _pair_undirected([(0, 1), (1, 2)], list(range(3)))
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        list(nx.all_simple_paths(ng, 99, 0))
    with pytest.raises(fnx.NodeNotFound) as fnx_exc:
        list(fnx.all_simple_paths(fg, 99, 0))
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_all_simple_paths_missing_target_raises_matching_networkx():
    fg, ng = _pair_undirected([(0, 1), (1, 2)], list(range(3)))
    with pytest.raises(nx.NodeNotFound) as nx_exc:
        list(nx.all_simple_paths(ng, 0, 99))
    with pytest.raises(fnx.NodeNotFound) as fnx_exc:
        list(fnx.all_simple_paths(fg, 0, 99))
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_all_simple_paths_disconnected_yields_no_paths():
    fg, ng = _pair_undirected([(0, 1), (2, 3)], list(range(4)))
    assert list(fnx.all_simple_paths(fg, 0, 3)) == list(
        nx.all_simple_paths(ng, 0, 3)
    ) == []


# ---------------------------------------------------------------------------
# Generator contract
# ---------------------------------------------------------------------------


def test_all_simple_paths_returns_generator():
    fg = fnx.complete_graph(4)
    it = fnx.all_simple_paths(fg, 0, 2)
    assert iter(it) is it


def test_all_simple_edge_paths_returns_generator():
    fg = fnx.complete_graph(4)
    it = fnx.all_simple_edge_paths(fg, 0, 2)
    assert iter(it) is it


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,source,target",
    [fx for fx in UNDIRECTED if 4 <= len(fx[2]) <= 7],
    ids=[fx[0] for fx in UNDIRECTED if 4 <= len(fx[2]) <= 7],
)
def test_all_simple_paths_count_equals_all_simple_edge_paths_count(
    name, edges, nodes, source, target,
):
    """``all_simple_paths`` and ``all_simple_edge_paths`` enumerate the
    same set of simple paths, just yielded in different shapes — the
    count must match."""
    fg, _ = _pair_undirected(edges, nodes)
    n_paths = sum(1 for _ in fnx.all_simple_paths(fg, source, target))
    n_edge_paths = sum(1 for _ in fnx.all_simple_edge_paths(fg, source, target))
    assert n_paths == n_edge_paths
