"""NetworkX conformance for the cycle algorithm family.

Existing tests scattered across ``test_cycle_algorithms.py``,
``test_paths_cycles.py``, and several focused single-bug-fix files
cover specific functions on a handful of hand-built fixtures. Add a
broad differential test that exercises the full family across
structured + random fixtures so any divergence in cycle order, cycle
membership, generator contract, or orientation handling surfaces
immediately.

Covered functions:

- ``cycle_basis(G, root=...)`` — undirected cycle basis (Paton-style).
- ``find_cycle(G, source=..., orientation=...)`` — single cycle.
- ``simple_cycles(G, length_bound=...)`` — directed Johnson + bounded.
- ``recursive_simple_cycles(G)`` — recursive variant for digraphs.
- ``minimum_cycle_basis(G, weight=...)`` — weighted minimum cycle basis.
- ``chordless_cycles(G, length_bound=...)`` — chordless directed cycles.
- ``girth(G)`` — length of the shortest cycle (∞ if acyclic).
- ``find_negative_cycle(G, source, weight=...)`` — Bellman-Ford
  negative cycle detection.
"""

from __future__ import annotations

import itertools
import math
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


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
    out.append(("triangle", [(0, 1), (1, 2), (2, 0)], [0, 1, 2]))
    out.append(("square", [(0, 1), (1, 2), (2, 3), (3, 0)], [0, 1, 2, 3]))
    out.append(("K_4", list(itertools.combinations(range(4), 2)),
                list(range(4))))
    out.append(("K_5", list(itertools.combinations(range(5), 2)),
                list(range(5))))
    out.append(("K_6", list(itertools.combinations(range(6), 2)),
                list(range(6))))
    out.append(("two_triangles_share_edge",
                [(0, 1), (1, 2), (2, 0), (1, 3), (3, 2)], list(range(4))))
    out.append(("bowtie",
                [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
                list(range(5))))
    out.append(("petersen", list(nx.petersen_graph().edges()),
                list(nx.petersen_graph().nodes())))
    out.append(("path_5", [(0, 1), (1, 2), (2, 3), (3, 4)], list(range(5))))
    out.append(("tree_5", [(0, 1), (1, 2), (1, 3), (3, 4)], list(range(5))))
    out.append(("hypercube_3", list(nx.hypercube_graph(3).edges()),
                list(nx.hypercube_graph(3).nodes())))
    for n, p, seed in [(8, 0.4, 1), (10, 0.3, 2), (12, 0.3, 3),
                       (15, 0.25, 4)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


def _directed_fixtures():
    out = []
    out.append(("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))))
    out.append(("dir_C_5",
                [(i, (i + 1) % 5) for i in range(5)], list(range(5))))
    out.append(("dir_DAG",
                [(0, 1), (1, 2), (2, 3), (0, 3)], list(range(4))))
    out.append(("dir_K3_both",
                [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
                list(range(3))))
    out.append(("dir_two_cycles_share_node",
                [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
                list(range(5))))
    out.append(("dir_antipar_pair", [(0, 1), (1, 0)], list(range(2))))
    out.append(("dir_path_4", [(0, 1), (1, 2), (2, 3)], list(range(4))))
    out.append(("dir_tree", [(0, 1), (0, 2), (1, 3), (1, 4)], list(range(5))))
    out.append(("dir_self_loop", [(0, 0)], [0]))
    return out


UNDIRECTED = _undirected_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# cycle_basis (undirected)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_cycle_basis_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = list(fnx.cycle_basis(fg))
    nr = list(nx.cycle_basis(ng))
    # NX returns a list of cycles in DFS-traversal order; both libs
    # promise the same ordering on identical inputs (br-r37-cyclebasis).
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes,root",
    [
        ("triangle_root_0", [(0, 1), (1, 2), (2, 0)], list(range(3)), 0),
        ("triangle_root_1", [(0, 1), (1, 2), (2, 0)], list(range(3)), 1),
        ("K_4_root_0", list(itertools.combinations(range(4), 2)),
         list(range(4)), 0),
        ("two_triangles_root_3",
         [(0, 1), (1, 2), (2, 0), (1, 3), (3, 2)], list(range(4)), 3),
    ],
)
def test_cycle_basis_with_explicit_root_matches_networkx(
    name, edges, nodes, root,
):
    fg, ng = _pair_undirected(edges, nodes)
    fr = list(fnx.cycle_basis(fg, root=root))
    nr = list(nx.cycle_basis(ng, root=root))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# girth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_girth_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = fnx.girth(fg)
    nr = nx.girth(ng)
    if math.isinf(fr) and math.isinf(nr):
        return
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# find_cycle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_find_cycle_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    try:
        nr = list(nx.find_cycle(ng))
    except nx.NetworkXNoCycle:
        with pytest.raises(fnx.NetworkXNoCycle):
            list(fnx.find_cycle(fg))
        return
    fr = list(fnx.find_cycle(fg))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED,
                         ids=[fx[0] for fx in UNDIRECTED])
def test_find_cycle_undirected_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    try:
        nr = list(nx.find_cycle(ng))
    except nx.NetworkXNoCycle:
        with pytest.raises(fnx.NetworkXNoCycle):
            list(fnx.find_cycle(fg))
        return
    fr = list(fnx.find_cycle(fg))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes,source",
    [
        ("dir_C_3_src_0", [(0, 1), (1, 2), (2, 0)], list(range(3)), 0),
        ("dir_C_3_src_1", [(0, 1), (1, 2), (2, 0)], list(range(3)), 1),
        ("dir_C_5_src_2",
         [(i, (i + 1) % 5) for i in range(5)], list(range(5)), 2),
    ],
)
def test_find_cycle_directed_with_source_matches_networkx(
    name, edges, nodes, source,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = list(fnx.find_cycle(fg, source=source))
    nr = list(nx.find_cycle(ng, source=source))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# simple_cycles (directed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_simple_cycles_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = list(fnx.simple_cycles(fg))
    nr = list(nx.simple_cycles(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,nodes,length_bound",
    [
        ("dir_K3_bound_2",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(3)), 2),
        ("dir_K3_bound_3",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(3)), 3),
        ("dir_two_C3_share_node_bound_3",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
         list(range(5)), 3),
    ],
)
def test_simple_cycles_with_length_bound_matches_networkx(
    name, edges, nodes, length_bound,
):
    fg, ng = _pair_directed(edges, nodes)
    fr = list(fnx.simple_cycles(fg, length_bound=length_bound))
    nr = list(nx.simple_cycles(ng, length_bound=length_bound))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# recursive_simple_cycles (directed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_recursive_simple_cycles_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = sorted(tuple(c) for c in fnx.recursive_simple_cycles(fg))
    nr = sorted(tuple(c) for c in nx.recursive_simple_cycles(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# minimum_cycle_basis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 3 <= len(fx[2]) <= 12],
    ids=[fx[0] for fx in UNDIRECTED if 3 <= len(fx[2]) <= 12],
)
def test_minimum_cycle_basis_matches_networkx(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    fr = sorted(sorted(c) for c in fnx.minimum_cycle_basis(fg))
    nr = sorted(sorted(c) for c in nx.minimum_cycle_basis(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# chordless_cycles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [
        ("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))),
        ("dir_K3_both",
         [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)],
         list(range(3))),
        ("dir_two_cycles",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
         list(range(5))),
    ],
)
def test_chordless_cycles_directed_matches_networkx(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    fr = sorted(tuple(c) for c in fnx.chordless_cycles(fg))
    nr = sorted(tuple(c) for c in nx.chordless_cycles(ng))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# find_negative_cycle (Bellman-Ford detection)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges_with_w,source",
    [
        ("dir_neg_cycle",
         [(0, 1, 1.0), (1, 2, -3.0), (2, 0, 1.0)], 0),
        ("dir_pos_cycle",
         [(0, 1, 1.0), (1, 2, 2.0), (2, 0, 3.0)], 0),
        ("dir_DAG_no_cycle",
         [(0, 1, 1.0), (1, 2, 2.0), (2, 3, 3.0)], 0),
    ],
)
def test_find_negative_cycle_matches_networkx(name, edges_with_w, source):
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    for u, v, w in edges_with_w:
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    try:
        nr = list(nx.find_negative_cycle(ng, source, weight="weight"))
    except nx.NetworkXError:
        with pytest.raises(fnx.NetworkXError):
            list(fnx.find_negative_cycle(fg, source, weight="weight"))
        return
    fr = list(fnx.find_negative_cycle(fg, source, weight="weight"))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Generator contract — simple_cycles / chordless_cycles return lazy generators
# ---------------------------------------------------------------------------


def test_simple_cycles_returns_iterator():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.simple_cycles(fg)
    assert iter(it) is it


def test_chordless_cycles_returns_iterator():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.chordless_cycles(fg)
    assert iter(it) is it


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 3 <= len(fx[2]) <= 10],
    ids=[fx[0] for fx in UNDIRECTED if 3 <= len(fx[2]) <= 10],
)
def test_girth_equals_minimum_cycle_basis_min_length(name, edges, nodes):
    """``girth(G)`` is the shortest cycle length; if the graph has a
    cycle then ``min(len(c) for c in minimum_cycle_basis(G))`` equals
    the girth."""
    fg, _ = _pair_undirected(edges, nodes)
    g = fnx.girth(fg)
    if math.isinf(g):
        # No cycle → minimum_cycle_basis is empty
        assert list(fnx.minimum_cycle_basis(fg)) == []
        return
    cycles = list(fnx.minimum_cycle_basis(fg))
    assert cycles, f"{name}: girth is finite but minimum_cycle_basis empty"
    assert min(len(c) for c in cycles) == g


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED if 3 <= len(fx[2]) <= 10],
    ids=[fx[0] for fx in UNDIRECTED if 3 <= len(fx[2]) <= 10],
)
def test_cycle_basis_size_equals_circuit_rank(name, edges, nodes):
    """Circuit rank ``|E| - |V| + components(G)``. The number of cycles
    in cycle_basis equals the circuit rank."""
    fg, _ = _pair_undirected(edges, nodes)
    cb = list(fnx.cycle_basis(fg))
    e = fg.number_of_edges()
    v = fg.number_of_nodes()
    c = fnx.number_connected_components(fg)
    assert len(cb) == e - v + c, (
        f"{name}: cycle_basis size {len(cb)} != circuit rank "
        f"{e}-{v}+{c} = {e-v+c}"
    )
