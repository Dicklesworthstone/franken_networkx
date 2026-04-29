"""NetworkX conformance for the tree-family predicates.

Covers ``is_tree``, ``is_forest``, ``is_arborescence``, ``is_branching``
against upstream NetworkX. Exercises:

- Standard tree-shaped fixtures (paths, stars, balanced binary trees,
  random trees by seed).
- Negative fixtures (cycles, multi-edge graphs, disconnected pairs).
- Multigraph parallel-edge cases (br-zzcm9 — parallels create cycles).
- Directed graphs: rooted arborescences, branchings, polytrees,
  ``0<->1`` antiparallel edges, multi-parent DAGs (br-treedir — Rust
  binding collapsed antiparallel edges to a single undirected edge).
- Empty graph dispatch (``NetworkXPointlessConcept``).
- Single-node graphs.

Each fixture builds matched ``fnx`` and ``nx`` instances and asserts
bit-for-bit parity.
"""

from __future__ import annotations

import itertools

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


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


def _pair_directed(edges, nodes=None, multi=False):
    fg = fnx.MultiDiGraph() if multi else fnx.DiGraph()
    ng = nx.MultiDiGraph() if multi else nx.DiGraph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


# ---------------------------------------------------------------------------
# Undirected simple-graph fixtures
# ---------------------------------------------------------------------------


def _undirected_simple_fixtures():
    out = []
    # paths P_n (always trees for n >= 1)
    for n in range(1, 10):
        edges = list(zip(range(n - 1), range(1, n)))
        out.append((f"P_{n}", edges, list(range(n))))
    # stars S_n (always trees)
    for n in range(1, 7):
        edges = [(0, i) for i in range(1, n + 1)]
        out.append((f"S_{n}", edges, list(range(n + 1))))
    # cycles C_n (n >= 3 — never trees, never forests)
    for n in range(3, 8):
        edges = [(i, (i + 1) % n) for i in range(n)]
        out.append((f"C_{n}", edges, list(range(n))))
    # complete graphs K_n (trees iff n <= 2)
    for n in range(1, 6):
        edges = list(itertools.combinations(range(n), 2))
        out.append((f"K_{n}", edges, list(range(n))))
    # balanced binary tree
    for h in (2, 3, 4):
        bt = nx.balanced_tree(2, h)
        out.append((
            f"balanced_tree_2_{h}",
            list(bt.edges()),
            list(bt.nodes()),
        ))
    # random trees of various sizes
    for n, seed in [(6, 1), (10, 2), (15, 3), (20, 4)]:
        rt = nx.random_labeled_tree(n, seed=seed)
        out.append((
            f"random_tree_n{n}_s{seed}",
            list(rt.edges()),
            list(range(n)),
        ))
    # disjoint pair of trees → forest, not tree
    out.append((
        "two_paths_disjoint",
        [(0, 1), (1, 2), (3, 4), (4, 5)],
        list(range(6)),
    ))
    # tree + isolated node → forest
    out.append((
        "P_3_plus_isolated",
        [(0, 1), (1, 2)],
        [0, 1, 2, 3],
    ))
    # gnp random — may or may not be tree
    for n, p, seed in [(8, 0.3, 1), (10, 0.25, 2), (15, 0.15, 3)]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((
            f"gnp_n{n}_p{p}_s{seed}",
            list(gnp.edges()),
            list(range(n)),
        ))
    return out


def _undirected_multi_fixtures():
    """MultiGraph fixtures — parallel edges create cycles."""
    return [
        ("multi_double_edge_two_nodes",
         [(0, 1), (0, 1)], [0, 1]),
        ("multi_path_with_parallel",
         [(0, 1), (1, 2), (1, 2)], list(range(3))),
        ("multi_star_with_one_parallel",
         [(0, 1), (0, 2), (0, 3), (0, 1)], list(range(4))),
        ("multi_tree_no_parallels",
         [(0, 1), (1, 2), (1, 3)], list(range(4))),
    ]


# ---------------------------------------------------------------------------
# Directed fixtures
# ---------------------------------------------------------------------------


def _directed_fixtures():
    return [
        # rooted arborescences (directed trees pointing away from root)
        ("dir_rooted_tree_5",
         [(0, 1), (0, 2), (1, 3), (1, 4)], list(range(5))),
        ("dir_chain_4",
         [(0, 1), (1, 2), (2, 3)], list(range(4))),
        # branchings (multiple roots)
        ("dir_two_chains_disjoint",
         [(0, 1), (2, 3)], list(range(4))),
        ("dir_two_arborescences",
         [(0, 1), (0, 2), (3, 4), (3, 5)], list(range(6))),
        # polytrees (underlying undirected is a tree, directed has
        # mixed orientation)
        ("dir_polytree_v_shape",
         [(0, 2), (1, 2)], list(range(3))),
        ("dir_polytree_anti_arborescence",
         [(1, 0), (2, 0), (3, 0)], list(range(4))),
        # directed cycles — neither tree nor forest
        ("dir_C_3", [(0, 1), (1, 2), (2, 0)], list(range(3))),
        ("dir_C_4", [(0, 1), (1, 2), (2, 3), (3, 0)], list(range(4))),
        # antiparallel edges — the directed-edge-collapse bug case
        ("dir_antiparallel_pair",
         [(0, 1), (1, 0)], [0, 1]),
        ("dir_antiparallel_in_path",
         [(0, 1), (1, 2), (2, 1)], list(range(3))),
        # multi-parent DAG (forest=True via underlying tree, even
        # though directed convergence at node 1)
        ("dir_multi_parent_dag",
         [(0, 1), (0, 2), (1, 3), (4, 1)], list(range(5))),
        # single isolated node
        ("dir_single_node", [], [0]),
        # two isolated nodes
        ("dir_two_isolated", [], [0, 1]),
    ]


UNDIRECTED_SIMPLE = _undirected_simple_fixtures()
UNDIRECTED_MULTI = _undirected_multi_fixtures()
DIRECTED = _directed_fixtures()


# ---------------------------------------------------------------------------
# is_tree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_is_tree_undirected_simple(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.is_tree(fg) == nx.is_tree(ng)


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_MULTI,
                         ids=[fx[0] for fx in UNDIRECTED_MULTI])
def test_is_tree_multigraph(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes, multi=True)
    assert fnx.is_tree(fg) == nx.is_tree(ng)


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_is_tree_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    assert fnx.is_tree(fg) == nx.is_tree(ng)


# ---------------------------------------------------------------------------
# is_forest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_SIMPLE,
                         ids=[fx[0] for fx in UNDIRECTED_SIMPLE])
def test_is_forest_undirected_simple(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes)
    assert fnx.is_forest(fg) == nx.is_forest(ng)


@pytest.mark.parametrize("name,edges,nodes", UNDIRECTED_MULTI,
                         ids=[fx[0] for fx in UNDIRECTED_MULTI])
def test_is_forest_multigraph(name, edges, nodes):
    fg, ng = _pair_undirected(edges, nodes, multi=True)
    assert fnx.is_forest(fg) == nx.is_forest(ng)


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_is_forest_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    assert fnx.is_forest(fg) == nx.is_forest(ng)


# ---------------------------------------------------------------------------
# is_arborescence (directed-only)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_is_arborescence_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    if not nodes:
        with pytest.raises((nx.NetworkXPointlessConcept, nx.NetworkXException)):
            nx.is_arborescence(ng)
        with pytest.raises((fnx.NetworkXPointlessConcept, fnx.NetworkXException)):
            fnx.is_arborescence(fg)
        return
    assert fnx.is_arborescence(fg) == nx.is_arborescence(ng)


# ---------------------------------------------------------------------------
# is_branching (directed-only)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,edges,nodes", DIRECTED,
                         ids=[fx[0] for fx in DIRECTED])
def test_is_branching_directed(name, edges, nodes):
    fg, ng = _pair_directed(edges, nodes)
    if not nodes:
        with pytest.raises((nx.NetworkXPointlessConcept, nx.NetworkXException)):
            nx.is_branching(ng)
        with pytest.raises((fnx.NetworkXPointlessConcept, fnx.NetworkXException)):
            fnx.is_branching(fg)
        return
    assert fnx.is_branching(fg) == nx.is_branching(ng)


# ---------------------------------------------------------------------------
# Empty graph dispatch
# ---------------------------------------------------------------------------


def test_is_tree_empty_undirected_raises_pointless_concept():
    with pytest.raises(nx.NetworkXPointlessConcept) as nx_exc:
        nx.is_tree(nx.Graph())
    with pytest.raises(fnx.NetworkXPointlessConcept) as fnx_exc:
        fnx.is_tree(fnx.Graph())
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_is_tree_empty_directed_raises_pointless_concept():
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.is_tree(nx.DiGraph())
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.is_tree(fnx.DiGraph())


def test_is_forest_empty_undirected_raises_pointless_concept():
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.is_forest(nx.Graph())
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.is_forest(fnx.Graph())


def test_is_forest_empty_directed_raises_pointless_concept():
    with pytest.raises(nx.NetworkXPointlessConcept):
        nx.is_forest(nx.DiGraph())
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.is_forest(fnx.DiGraph())


# ---------------------------------------------------------------------------
# Single-node graphs (vacuously a tree and a forest)
# ---------------------------------------------------------------------------


def test_single_node_is_tree_and_forest():
    fg = fnx.Graph(); fg.add_node(0)
    ng = nx.Graph(); ng.add_node(0)
    assert fnx.is_tree(fg) == nx.is_tree(ng) is True
    assert fnx.is_forest(fg) == nx.is_forest(ng) is True


def test_single_node_directed_is_tree_and_forest():
    fg = fnx.DiGraph(); fg.add_node(0)
    ng = nx.DiGraph(); ng.add_node(0)
    assert fnx.is_tree(fg) == nx.is_tree(ng) is True
    assert fnx.is_forest(fg) == nx.is_forest(ng) is True


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in UNDIRECTED_SIMPLE if len(fx[2]) > 0]
    + [fx for fx in DIRECTED if len(fx[2]) > 0],
    ids=[fx[0] for fx in UNDIRECTED_SIMPLE if len(fx[2]) > 0]
       + [fx[0] for fx in DIRECTED if len(fx[2]) > 0],
)
def test_tree_implies_forest(name, edges, nodes):
    """Every tree is a forest (single-component forest)."""
    if any(name.startswith(p) for p in ("dir_",)):
        fg, _ = _pair_directed(edges, nodes)
    else:
        fg, _ = _pair_undirected(edges, nodes)
    if fnx.is_tree(fg):
        assert fnx.is_forest(fg), f"{name}: tree should be forest"


@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in DIRECTED if len(fx[2]) > 0],
    ids=[fx[0] for fx in DIRECTED if len(fx[2]) > 0],
)
def test_arborescence_implies_branching(name, edges, nodes):
    """Every arborescence is a branching (single-root branching)."""
    fg, _ = _pair_directed(edges, nodes)
    if fnx.is_arborescence(fg):
        assert fnx.is_branching(fg), f"{name}: arborescence should be branching"
