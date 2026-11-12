"""NetworkX conformance for traversal, tree-coding, dominance, LCA,
moral, and minors algorithm families.

Bundles six widely-used but currently uncovered families:

- ``traversal`` — ``bfs_edges``, ``bfs_tree``, ``bfs_predecessors``,
  ``bfs_successors``, ``bfs_layers``, ``descendants_at_distance``,
  ``dfs_edges``, ``dfs_tree``, ``dfs_predecessors``, ``dfs_successors``,
  ``dfs_preorder_nodes``, ``dfs_postorder_nodes``,
  ``dfs_labeled_edges``, ``edge_bfs``, ``edge_dfs``.
- ``tree.coding`` — ``to_prufer_sequence`` and
  ``from_prufer_sequence`` with the round-trip identity.
- ``dominance`` — ``immediate_dominators``, ``dominance_frontiers``.
- ``lowest_common_ancestors`` — ``lowest_common_ancestor``,
  ``tree_all_pairs_lowest_common_ancestor``.
- ``moral`` — ``moral_graph`` (DAG → undirected moralized graph).
- ``minors`` — ``contracted_nodes``, ``contracted_edge``.

For traversals, we assert structural equality (sorted edge tuples,
visited sets, ordered preorder/postorder lists) on small fixtures
so we don't depend on tie-broken iteration order in the BFS/DFS
queue. ``edge_bfs`` and ``edge_dfs`` are compared as canonical
edge sets / sorted edge sequences.
"""

from __future__ import annotations

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _build_pair(edges, *, directed=False, nodes=None):
    cls_fnx = fnx.DiGraph if directed else fnx.Graph
    cls_nx = nx.DiGraph if directed else nx.Graph
    fg = cls_fnx()
    ng = cls_nx()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng


def _build_tree_pair(L, branching, depth):
    return L.balanced_tree(branching, depth)


# ---------------------------------------------------------------------------
# bfs_edges / bfs_tree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,source",
    [
        ("path_5", [(0, 1), (1, 2), (2, 3), (3, 4)], 0),
        ("cycle_6", [(i, (i + 1) % 6) for i in range(6)], 0),
        ("complete_5", [(u, v) for u in range(5) for v in range(u + 1, 5)], 2),
        ("star_5", [(0, i) for i in range(1, 6)], 0),
        ("two_triangles_bridge",
         [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)], 0),
    ],
)
def test_bfs_edges_matches_networkx(name, edges, source):
    fg, ng = _build_pair(edges)
    fr = list(fnx.bfs_edges(fg, source))
    nr = list(nx.bfs_edges(ng, source))
    # BFS edge sequences match exactly when the underlying neighbor
    # iteration order is canonical (which fnx provides for sorted node
    # ids 0..n-1 — fixtures use those).
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,source",
    [
        ("path_5", [(0, 1), (1, 2), (2, 3), (3, 4)], 0),
        ("cycle_6", [(i, (i + 1) % 6) for i in range(6)], 0),
        ("balanced_tree_2_3_root_0",
         [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6),
          (3, 7), (3, 8), (4, 9), (4, 10), (5, 11), (5, 12),
          (6, 13), (6, 14)], 0),
    ],
)
def test_bfs_tree_matches_networkx(name, edges, source):
    fg, ng = _build_pair(edges)
    fr = sorted(fnx.bfs_tree(fg, source).edges())
    nr = sorted(nx.bfs_tree(ng, source).edges())
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_bfs_predecessors_matches_networkx():
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)
    assert list(fnx.bfs_predecessors(fg, 0)) == list(nx.bfs_predecessors(ng, 0))


def test_bfs_successors_matches_networkx():
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)
    assert list(fnx.bfs_successors(fg, 0)) == list(nx.bfs_successors(ng, 0))


def test_bfs_layers_matches_networkx():
    fg, ng = _build_pair([(0, 1), (0, 2), (1, 3), (2, 4), (3, 5)])
    assert list(fnx.bfs_layers(fg, 0)) == list(nx.bfs_layers(ng, 0))


@pytest.mark.parametrize("k", [0, 1, 2, 3, 4])
def test_descendants_at_distance_matches_networkx(k):
    fg = fnx.path_graph(6)
    ng = nx.path_graph(6)
    assert fnx.descendants_at_distance(fg, 0, k) == nx.descendants_at_distance(ng, 0, k)


# ---------------------------------------------------------------------------
# dfs_edges / dfs_tree / dfs_pre/postorder
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,source",
    [
        ("path_5", [(0, 1), (1, 2), (2, 3), (3, 4)], 0),
        ("cycle_6", [(i, (i + 1) % 6) for i in range(6)], 0),
        ("complete_5", [(u, v) for u in range(5) for v in range(u + 1, 5)], 0),
        ("star_5", [(0, i) for i in range(1, 6)], 0),
    ],
)
def test_dfs_edges_matches_networkx(name, edges, source):
    fg, ng = _build_pair(edges)
    fr = list(fnx.dfs_edges(fg, source))
    nr = list(nx.dfs_edges(ng, source))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_dfs_tree_path_5_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert sorted(fnx.dfs_tree(fg, 0).edges()) == sorted(nx.dfs_tree(ng, 0).edges())


def test_dfs_preorder_postorder_path_5_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert list(fnx.dfs_preorder_nodes(fg, 0)) == list(nx.dfs_preorder_nodes(ng, 0))
    assert list(fnx.dfs_postorder_nodes(fg, 0)) == list(nx.dfs_postorder_nodes(ng, 0))


def test_dfs_predecessors_successors_match_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert fnx.dfs_predecessors(fg, 0) == nx.dfs_predecessors(ng, 0)
    assert fnx.dfs_successors(fg, 0) == nx.dfs_successors(ng, 0)


def test_dfs_labeled_edges_path_5_matches_networkx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    assert list(fnx.dfs_labeled_edges(fg, 0)) == list(nx.dfs_labeled_edges(ng, 0))


# ---------------------------------------------------------------------------
# edge_bfs / edge_dfs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,source",
    [
        ("path_5_mid", [(0, 1), (1, 2), (2, 3), (3, 4)], 2),
        ("cycle_4", [(0, 1), (1, 2), (2, 3), (3, 0)], 0),
        ("complete_4", [(u, v) for u in range(4) for v in range(u + 1, 4)], 0),
    ],
)
def test_edge_bfs_matches_networkx(name, edges, source):
    fg, ng = _build_pair(edges)
    fr = list(fnx.edge_bfs(fg, source))
    nr = list(nx.edge_bfs(ng, source))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,source",
    [
        ("path_5_mid", [(0, 1), (1, 2), (2, 3), (3, 4)], 2),
        ("cycle_4", [(0, 1), (1, 2), (2, 3), (3, 0)], 0),
    ],
)
def test_edge_dfs_matches_networkx(name, edges, source):
    fg, ng = _build_pair(edges)
    fr = list(fnx.edge_dfs(fg, source))
    nr = list(nx.edge_dfs(ng, source))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Tree coding — Prufer round trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("balanced_tree_2_2", lambda L: L.balanced_tree(2, 2)),
        ("balanced_tree_2_3", lambda L: L.balanced_tree(2, 3)),
        ("balanced_tree_3_2", lambda L: L.balanced_tree(3, 2)),
        ("path_8", lambda L: L.path_graph(8)),
        ("star_5", lambda L: L.star_graph(5)),
    ],
)
def test_to_prufer_sequence_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = fnx.to_prufer_sequence(fg)
    nr = nx.to_prufer_sequence(ng)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,seq",
    [
        ("seq_3_2_1_0", [3, 2, 1, 0]),
        ("seq_0_1_2_3", [0, 1, 2, 3]),
        ("seq_2_2_2", [2, 2, 2]),
        ("seq_empty_n2", []),
    ],
)
def test_from_prufer_sequence_matches_networkx(name, seq):
    fr = fnx.from_prufer_sequence(seq)
    nr = nx.from_prufer_sequence(seq)
    assert sorted(fr.edges()) == sorted(nr.edges()), (
        f"{name}: fnx={sorted(fr.edges())} nx={sorted(nr.edges())}"
    )


@pytest.mark.parametrize(
    "name,builder",
    [
        ("balanced_tree_2_2", lambda L: L.balanced_tree(2, 2)),
        ("balanced_tree_3_2", lambda L: L.balanced_tree(3, 2)),
        ("path_6", lambda L: L.path_graph(6)),
    ],
)
def test_prufer_round_trip_identity(name, builder):
    """``from_prufer_sequence(to_prufer_sequence(T)) == T`` for any
    labelled tree on the canonical node set 0..n-1."""
    g = builder(fnx)
    seq = fnx.to_prufer_sequence(g)
    rebuilt = fnx.from_prufer_sequence(seq)
    orig_edges = {tuple(sorted(e)) for e in g.edges()}
    rebuilt_edges = {tuple(sorted(e)) for e in rebuilt.edges()}
    assert orig_edges == rebuilt_edges, (
        f"{name}: orig={orig_edges} rebuilt={rebuilt_edges}"
    )


# ---------------------------------------------------------------------------
# Dominance — immediate_dominators / dominance_frontiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,start",
    [
        ("dag_diamond", [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)], 0),
        ("dag_chain", [(0, 1), (1, 2), (2, 3), (3, 4)], 0),
        ("dag_branch", [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4)], 0),
        ("dag_long_diamond",
         [(0, 1), (0, 2), (1, 3), (2, 3), (1, 4), (3, 5), (4, 5)], 0),
    ],
)
def test_immediate_dominators_matches_networkx(name, edges, start):
    fg, ng = _build_pair(edges, directed=True)
    fr = fnx.immediate_dominators(fg, start)
    nr = nx.immediate_dominators(ng, start)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,edges,start",
    [
        ("dag_diamond", [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)], 0),
        ("dag_branch", [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4)], 0),
    ],
)
def test_dominance_frontiers_matches_networkx(name, edges, start):
    fg, ng = _build_pair(edges, directed=True)
    fr = fnx.dominance_frontiers(fg, start)
    nr = nx.dominance_frontiers(ng, start)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Lowest common ancestor
# ---------------------------------------------------------------------------


def _balanced_tree_directed(L, b, h):
    """A balanced tree rooted at 0 as a DiGraph (edges parent→child)."""
    g = L.DiGraph()
    g.add_edges_from(L.balanced_tree(b, h).edges())
    return g


@pytest.mark.parametrize(
    "name,builder,u,v",
    [
        ("tree_2_3_leaves_7_12", lambda L: _balanced_tree_directed(L, 2, 3),
         7, 12),
        ("tree_2_3_leaves_3_5", lambda L: _balanced_tree_directed(L, 2, 3),
         3, 5),
        ("tree_2_3_leaf_root", lambda L: _balanced_tree_directed(L, 2, 3),
         3, 0),
    ],
)
def test_lowest_common_ancestor_matches_networkx(name, builder, u, v):
    fg = builder(fnx)
    ng = builder(nx)
    fr = fnx.lowest_common_ancestor(fg, u, v)
    nr = nx.lowest_common_ancestor(ng, u, v)
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_tree_all_pairs_lowest_common_ancestor_matches_networkx():
    """Every-pair LCA on a small balanced binary tree."""
    fg = _balanced_tree_directed(fnx, 2, 3)
    ng = _balanced_tree_directed(nx, 2, 3)
    fr = dict(fnx.tree_all_pairs_lowest_common_ancestor(fg, root=0))
    nr = dict(nx.tree_all_pairs_lowest_common_ancestor(ng, root=0))
    assert fr == nr


# ---------------------------------------------------------------------------
# moral_graph
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges",
    [
        ("collider", [(0, 2), (1, 2)]),  # 0,1 share child 2 ⇒ 0—1
        ("chain", [(0, 1), (1, 2)]),
        ("v_structure", [(0, 1), (2, 1), (3, 1)]),
        ("dag_4nodes", [(0, 1), (0, 2), (1, 3), (2, 3)]),  # collider at 3
    ],
)
def test_moral_graph_matches_networkx(name, edges):
    fg, ng = _build_pair(edges, directed=True)
    fr = fnx.moral_graph(fg)
    nr = nx.moral_graph(ng)
    fr_edges = sorted(tuple(sorted(e)) for e in fr.edges())
    nr_edges = sorted(tuple(sorted(e)) for e in nr.edges())
    assert fr_edges == nr_edges, f"{name}: fnx={fr_edges} nx={nr_edges}"


def test_moral_graph_is_undirected():
    fg = fnx.DiGraph()
    fg.add_edges_from([(0, 2), (1, 2)])
    m = fnx.moral_graph(fg)
    assert not m.is_directed()


# ---------------------------------------------------------------------------
# Minors — contracted_nodes / contracted_edge
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,u,v,self_loops",
    [
        ("path_5_contract_1_2", [(0, 1), (1, 2), (2, 3), (3, 4)], 1, 2, True),
        ("cycle_5_contract_0_2",
         [(i, (i + 1) % 5) for i in range(5)], 0, 2, True),
        ("path_5_no_loops", [(0, 1), (1, 2), (2, 3), (3, 4)], 1, 2, False),
    ],
)
def test_contracted_nodes_matches_networkx(name, edges, u, v, self_loops):
    fg, ng = _build_pair(edges)
    fr = fnx.contracted_nodes(fg, u, v, self_loops=self_loops)
    nr = nx.contracted_nodes(ng, u, v, self_loops=self_loops)
    fr_edges = sorted(tuple(sorted(e)) for e in fr.edges())
    nr_edges = sorted(tuple(sorted(e)) for e in nr.edges())
    assert fr_edges == nr_edges, f"{name}: fnx={fr_edges} nx={nr_edges}"
    assert sorted(fr.nodes()) == sorted(ng.nodes() - {v} | set())  # noqa: E501


@pytest.mark.parametrize(
    "name,edges,edge_to_contract",
    [
        ("path_5_contract_1_2", [(0, 1), (1, 2), (2, 3), (3, 4)], (1, 2)),
        ("cycle_5_contract_0_1",
         [(i, (i + 1) % 5) for i in range(5)], (0, 1)),
    ],
)
def test_contracted_edge_matches_networkx(name, edges, edge_to_contract):
    fg, ng = _build_pair(edges)
    fr = fnx.contracted_edge(fg, edge_to_contract, self_loops=False)
    nr = nx.contracted_edge(ng, edge_to_contract, self_loops=False)
    fr_edges = sorted(tuple(sorted(e)) for e in fr.edges())
    nr_edges = sorted(tuple(sorted(e)) for e in nr.edges())
    assert fr_edges == nr_edges, f"{name}: fnx={fr_edges} nx={nr_edges}"


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_bfs_layers_partitions_reachable_nodes():
    """Every node reachable from the source belongs to exactly one
    BFS layer; layer index equals the BFS distance."""
    g = fnx.path_graph(8)
    layers = list(fnx.bfs_layers(g, 0))
    seen = set()
    for layer in layers:
        for v in layer:
            assert v not in seen, f"node {v} appears in multiple layers"
            seen.add(v)
    assert seen == set(g.nodes())


def test_bfs_tree_is_spanning_tree_when_graph_is_connected():
    """``bfs_tree(G, s)`` rooted at ``s`` has exactly N nodes and N-1
    edges when G is connected."""
    g = fnx.cycle_graph(6)
    t = fnx.bfs_tree(g, 0)
    assert t.number_of_nodes() == g.number_of_nodes()
    assert t.number_of_edges() == g.number_of_nodes() - 1


def test_dfs_preorder_postorder_visit_every_reachable_node():
    g = fnx.path_graph(7)
    pre = list(fnx.dfs_preorder_nodes(g, 0))
    post = list(fnx.dfs_postorder_nodes(g, 0))
    assert set(pre) == set(post) == set(g.nodes())


def test_descendants_at_distance_zero_is_singleton_source():
    g = fnx.cycle_graph(8)
    assert fnx.descendants_at_distance(g, 3, 0) == {3}


def test_immediate_dominators_source_dominates_itself_or_omitted():
    """nx maps the start node to itself in the dom dict on some
    versions, omits it on others. fnx must agree with nx exactly."""
    g_fnx = fnx.DiGraph()
    g_nx = nx.DiGraph()
    edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    g_fnx.add_edges_from(edges)
    g_nx.add_edges_from(edges)
    assert fnx.immediate_dominators(g_fnx, 0) == nx.immediate_dominators(g_nx, 0)


def test_moral_graph_strict_supersets_skeleton():
    """The moralized graph contains every edge of the underlying
    skeleton plus the marrying edges between co-parents."""
    g = fnx.DiGraph()
    g.add_edges_from([(0, 2), (1, 2)])  # collider 0,1 -> 2
    skel = {tuple(sorted(e)) for e in g.edges()}
    moral = {tuple(sorted(e)) for e in fnx.moral_graph(g).edges()}
    assert skel.issubset(moral)
    # Co-parents 0 and 1 must be connected.
    assert (0, 1) in moral


def test_contract_then_count_drops_one_node():
    g = fnx.path_graph(5)
    n_before = g.number_of_nodes()
    contracted = fnx.contracted_nodes(g, 1, 2, self_loops=False)
    assert contracted.number_of_nodes() == n_before - 1
