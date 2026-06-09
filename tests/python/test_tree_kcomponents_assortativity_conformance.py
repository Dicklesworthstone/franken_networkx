"""NetworkX conformance for tree.* + connectivity.kcomponents/cuts +
assortativity (attribute) + gomory_hu_tree families.

Bundles five small uncovered families:

- ``tree.recognition``: ``is_tree``, ``is_forest``,
  ``is_arborescence``, ``is_branching``.
- ``tree.branchings``: ``branching_weight``,
  ``greedy_branching``, ``minimum_branching``,
  ``maximum_branching``, ``minimum_spanning_arborescence``,
  ``maximum_spanning_arborescence``.
- ``tree.decomposition`` / ``tree.operations``:
  ``junction_tree``, ``join_trees``.
- ``connectivity.kcomponents`` / ``cuts``: ``k_components``,
  ``k_edge_components``, ``k_edge_subgraphs``,
  ``minimum_st_edge_cut``, ``minimum_st_node_cut``,
  ``minimum_node_cut``, ``minimum_edge_cut``.
- ``assortativity (attribute)``:
  ``attribute_assortativity_coefficient``,
  ``numeric_assortativity_coefficient``,
  ``average_degree_connectivity``.
- ``gomory_hu_tree``.

For algorithms with multiple valid outputs (e.g. matchings,
branchings, st-cuts), the harness asserts the *value* invariants
(weight, size, etc.) rather than identity, since tie-breaks
differ across implementations.
"""

from __future__ import annotations

import math

import networkx as nx
import pytest

import franken_networkx as fnx


def _close(a, b, *, tol=1e-9):
    if isinstance(a, float) or isinstance(b, float):
        af, bf = float(a), float(b)
        if math.isnan(af) and math.isnan(bf):
            return True
        return abs(af - bf) <= tol * max(1.0, abs(af), abs(bf))
    return a == b


def _build_pair(builder):
    return builder(fnx), builder(nx)


def _graph_with_nodes_edges(library, nodes, edges):
    graph = library.Graph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from(edges)
    return graph


# ---------------------------------------------------------------------------
# tree.recognition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,expected_tree,expected_forest",
    [
        ("path_5", lambda L: L.path_graph(5), True, True),
        ("path_8", lambda L: L.path_graph(8), True, True),
        ("balanced_tree_2_3", lambda L: L.balanced_tree(2, 3), True, True),
        ("star_5", lambda L: L.star_graph(5), True, True),
        ("cycle_5", lambda L: L.cycle_graph(5), False, False),
        ("complete_4", lambda L: L.complete_graph(4), False, False),
    ],
)
def test_is_tree_is_forest_match_networkx(
    name, builder, expected_tree, expected_forest,
):
    fg, ng = _build_pair(builder)
    fr_tree = fnx.is_tree(fg)
    nr_tree = nx.is_tree(ng)
    fr_forest = fnx.is_forest(fg)
    nr_forest = nx.is_forest(ng)
    assert fr_tree == nr_tree == expected_tree, name
    assert fr_forest == nr_forest == expected_forest, name


def test_is_forest_disjoint_paths_is_forest_not_tree():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (2, 3), (4, 5)])
    ng = nx.Graph()
    ng.add_edges_from([(0, 1), (2, 3), (4, 5)])
    assert fnx.is_forest(fg) == nx.is_forest(ng) == True
    assert fnx.is_tree(fg) == nx.is_tree(ng) == False


@pytest.mark.parametrize(
    "name,edges,expected_arb,expected_branch",
    [
        ("rooted_balanced",
         [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)], True, True),
        ("two_roots",
         [(0, 1), (0, 2), (3, 4), (3, 5)], False, True),  # 2 components
        ("with_cycle",
         [(0, 1), (1, 2), (2, 0)], False, False),
        ("multi_parent",
         [(0, 2), (1, 2)], False, False),  # node 2 has 2 parents
    ],
)
def test_is_arborescence_is_branching_match_networkx(
    name, edges, expected_arb, expected_branch,
):
    fg = fnx.DiGraph(); fg.add_edges_from(edges)
    ng = nx.DiGraph(); ng.add_edges_from(edges)
    assert fnx.is_arborescence(fg) == nx.is_arborescence(ng) == expected_arb, name
    assert fnx.is_branching(fg) == nx.is_branching(ng) == expected_branch, name


# ---------------------------------------------------------------------------
# tree.branchings — branching_weight, greedy_branching, min/max
# ---------------------------------------------------------------------------


def _weighted_arborescence(L):
    g = L.DiGraph()
    g.add_weighted_edges_from([
        (0, 1, 2.0), (0, 2, 3.0), (0, 3, 1.0),
        (1, 4, 5.0), (1, 5, 1.5),
        (2, 6, 4.0),
        (3, 7, 2.5),
    ])
    return g


def test_branching_weight_matches_networkx():
    fg = _weighted_arborescence(fnx)
    ng = _weighted_arborescence(nx)
    assert fnx.algorithms.tree.branchings.branching_weight(fg) == nx.algorithms.tree.branching_weight(ng)


@pytest.mark.parametrize(
    "name,builder",
    [
        ("simple_dag", lambda L: _weighted_arborescence(L)),
        ("two_parent_dag",
         lambda L: (L.DiGraph(),
                    L.DiGraph().add_weighted_edges_from(
                        [(0, 2, 5.0), (1, 2, 3.0), (2, 3, 2.0)],
                    ))[0]),
    ],
)
def test_greedy_branching_matches_networkx(name, builder):
    fg = builder(fnx)
    ng = builder(nx)
    fr = sorted(fnx.algorithms.tree.branchings.greedy_branching(fg).edges())
    nr = sorted(nx.algorithms.tree.greedy_branching(ng).edges())
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


def test_minimum_branching_total_weight_matches_networkx():
    fg = _weighted_arborescence(fnx)
    ng = _weighted_arborescence(nx)
    fr = fnx.minimum_branching(fg)
    nr = nx.minimum_branching(ng)
    fr_w = sum(d.get("weight", 1) for _, _, d in fr.edges(data=True))
    nr_w = sum(d.get("weight", 1) for _, _, d in nr.edges(data=True))
    assert _close(fr_w, nr_w)


def test_maximum_branching_total_weight_matches_networkx():
    fg = _weighted_arborescence(fnx)
    ng = _weighted_arborescence(nx)
    fr = fnx.maximum_branching(fg)
    nr = nx.maximum_branching(ng)
    fr_w = sum(d.get("weight", 1) for _, _, d in fr.edges(data=True))
    nr_w = sum(d.get("weight", 1) for _, _, d in nr.edges(data=True))
    assert _close(fr_w, nr_w)


def test_minimum_spanning_arborescence_total_weight_matches_networkx():
    fg = _weighted_arborescence(fnx)
    ng = _weighted_arborescence(nx)
    fr = fnx.minimum_spanning_arborescence(fg)
    nr = nx.minimum_spanning_arborescence(ng)
    fr_w = sum(d.get("weight", 1) for _, _, d in fr.edges(data=True))
    nr_w = sum(d.get("weight", 1) for _, _, d in nr.edges(data=True))
    assert _close(fr_w, nr_w)


# ---------------------------------------------------------------------------
# tree.decomposition / tree.operations
# ---------------------------------------------------------------------------


def test_junction_tree_matches_networkx_on_chordal_graph():
    """br-r37-c1-7hq76: parity restored via delegation to nx so node
    identifiers and sepset nodes match (was previously clique-index
    integers without sepset nodes)."""
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    ng = nx.Graph()
    ng.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
    fr = fnx.junction_tree(fg)
    nr = nx.junction_tree(ng)
    assert sorted(fr.nodes()) == sorted(nr.nodes())
    assert sorted(fr.edges()) == sorted(nr.edges())
    fr_types = sorted((n, d.get("type")) for n, d in fr.nodes(data=True))
    nr_types = sorted((n, d.get("type")) for n, d in nr.nodes(data=True))
    assert fr_types == nr_types


def test_join_trees_matches_networkx():
    t1 = fnx.balanced_tree(2, 2)
    t2 = fnx.path_graph(3)
    t1n = nx.balanced_tree(2, 2)
    t2n = nx.path_graph(3)
    fr = fnx.join_trees([(t1, 0), (t2, 0)])
    nr = nx.join_trees([(t1n, 0), (t2n, 0)])
    assert fr.number_of_nodes() == nr.number_of_nodes()
    assert fr.number_of_edges() == nr.number_of_edges()


# ---------------------------------------------------------------------------
# connectivity.kcomponents
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder",
    [
        ("complete_5", lambda L: L.complete_graph(5)),
        ("petersen", lambda L: L.petersen_graph()),
        ("path_5", lambda L: L.path_graph(5)),
        ("two_triangles_bridge",
         lambda L: L.from_edgelist(
             [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
         ) if hasattr(L, "from_edgelist") else None),
    ],
)
def test_k_components_matches_networkx(name, builder):
    g_nx = builder(nx)
    if g_nx is None:
        g_nx = nx.Graph()
        g_nx.add_edges_from([
            (0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3),
        ])
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(g_nx.nodes())
    g_fnx.add_edges_from(g_nx.edges())
    fr = fnx.k_components(g_fnx)
    nr = nx.k_components(g_nx)
    assert set(fr.keys()) == set(nr.keys())
    for k in fr:
        fr_sets = [frozenset(s) for s in fr[k]]
        nr_sets = [frozenset(s) for s in nr[k]]
        assert sorted(fr_sets, key=lambda x: (len(x), sorted(x))) == \
            sorted(nr_sets, key=lambda x: (len(x), sorted(x))), \
            f"{name}: k={k}"


@pytest.mark.parametrize("n", [0, 1, 2, 5])
def test_k_components_complete_graph_raw_shape_matches_networkx(n):
    fg = fnx.complete_graph(n)
    ng = nx.complete_graph(n)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert {k: type(v).__name__ for k, v in fr.items()} == {
        k: type(v).__name__ for k, v in nr.items()
    }
    assert {k: [type(c).__name__ for c in v] for k, v in fr.items()} == {
        k: [type(c).__name__ for c in v] for k, v in nr.items()
    }
    assert {k: [set(c) for c in v] for k, v in fr.items()} == {
        k: [set(c) for c in v] for k, v in nr.items()
    }


def test_k_components_complete_graph_ignores_flow_func_like_networkx():
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("complete graph should not call flow_func")

    fg = fnx.complete_graph(5)
    ng = nx.complete_graph(5)

    assert fnx.k_components(fg, flow_func=fail_if_called) == nx.k_components(
        ng, flow_func=fail_if_called
    )


def test_k_components_complete_fast_path_rejects_density_one_selfloop_case():
    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        graph.add_nodes_from([0, 1, 2])
        graph.add_edges_from([(0, 1), (1, 2), (0, 0)])

    assert fnx.density(fg) == nx.density(ng) == 1
    assert fnx.k_components(fg) == nx.k_components(ng) == {1: [{0, 1, 2}]}


def test_k_components_directed_guard_still_matches_networkx():
    fg = fnx.complete_graph(3, create_using=fnx.DiGraph)
    ng = nx.complete_graph(3, create_using=nx.DiGraph)

    with pytest.raises(nx.NetworkXNotImplemented):
        fnx.k_components(fg)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.k_components(ng)


@pytest.mark.parametrize("builder", [
    lambda L: L.cycle_graph(5),
    lambda L: L.disjoint_union(L.cycle_graph(4), L.cycle_graph(5)),
])
def test_k_components_cycle_family_raw_shape_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys()) == [2, 1]
    assert {k: [set(c) for c in v] for k, v in fr.items()} == {
        k: [set(c) for c in v] for k, v in nr.items()
    }
    assert {k: [type(c).__name__ for c in v] for k, v in fr.items()} == {
        k: [type(c).__name__ for c in v] for k, v in nr.items()
    }


def test_k_components_cycle_fast_path_rejects_selfloop_degree_two_case():
    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        graph.add_nodes_from([0, 1, 2, 3])
        graph.add_edges_from([(0, 0), (1, 2), (2, 3), (3, 1)])

    assert all(degree == 2 for _, degree in fg.degree())
    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize("builder", [
    lambda L: L.empty_graph(2),
    lambda L: L.path_graph(5),
    lambda L: L.star_graph(7),
    lambda L: L.disjoint_union(L.path_graph(3), L.empty_graph(1)),
    lambda L: L.disjoint_union(L.path_graph(3), L.path_graph(2)),
])
def test_k_components_forest_family_raw_shape_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert {k: [set(c) for c in v] for k, v in fr.items()} == {
        k: [set(c) for c in v] for k, v in nr.items()
    }
    assert {k: [type(c).__name__ for c in v] for k, v in fr.items()} == {
        k: [type(c).__name__ for c in v] for k, v in nr.items()
    }


def test_k_components_forest_fast_path_ignores_flow_func_like_networkx():
    fg = fnx.star_graph(6)
    ng = nx.star_graph(6)

    def fail_flow(*args, **kwargs):
        raise AssertionError("forest k_components should not call flow_func")

    assert fnx.k_components(fg, flow_func=fail_flow) == nx.k_components(
        ng, flow_func=fail_flow
    )


@pytest.mark.parametrize("builder", [
    lambda L: L.Graph([(0, 1), (1, 2), (2, 0), (2, 3)]),
    lambda L: _graph_with_nodes_edges(L, [0, 1, 2], [(0, 1), (1, 2), (0, 0)]),
])
def test_k_components_forest_fast_path_rejects_non_forest_boundaries(builder):
    fg = builder(fnx)
    ng = builder(nx)

    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize("builder", [
    lambda L: L.barbell_graph(4, 1),
    lambda L: _graph_with_nodes_edges(
        L, [], [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]
    ),
    lambda L: _graph_with_nodes_edges(
        L,
        [],
        [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3), (3, 4), (4, 5), (5, 3)],
    ),
])
def test_k_components_block_graph_family_raw_shape_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert {k: [set(c) for c in v] for k, v in fr.items()} == {
        k: [set(c) for c in v] for k, v in nr.items()
    }
    assert {k: [type(c).__name__ for c in v] for k, v in fr.items()} == {
        k: [type(c).__name__ for c in v] for k, v in nr.items()
    }


def test_k_components_block_graph_fast_path_ignores_flow_func_like_networkx():
    fg = fnx.barbell_graph(4, 1)
    ng = nx.barbell_graph(4, 1)

    def fail_flow(*args, **kwargs):
        raise AssertionError("block-graph k_components should not call flow_func")

    assert fnx.k_components(fg, flow_func=fail_flow) == nx.k_components(
        ng, flow_func=fail_flow
    )


def test_k_components_block_graph_fast_path_rejects_non_clique_block():
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    fg = _graph_with_nodes_edges(fnx, [], edges)
    ng = _graph_with_nodes_edges(nx, [], edges)

    assert fnx.k_components(fg) == nx.k_components(ng)


def _complete_multipartite(library, *sizes):
    graph = library.Graph()
    parts = []
    offset = 0
    for size in sizes:
        part = list(range(offset, offset + size))
        graph.add_nodes_from(part)
        parts.append(part)
        offset += size
    for index, left in enumerate(parts):
        for right in parts[index + 1:]:
            graph.add_edges_from((u, v) for u in left for v in right)
    return graph


def _disjoint_complete_multipartite(library, *families):
    graph = library.Graph()
    offset = 0
    for sizes in families:
        component = _complete_multipartite(library, *sizes)
        mapping = {node: node + offset for node in component.nodes()}
        graph.add_nodes_from(mapping.values())
        graph.add_edges_from((mapping[u], mapping[v]) for u, v in component.edges())
        offset += sum(sizes)
    return graph


@pytest.mark.parametrize("sizes", [
    (2, 3),
    (3, 3, 3),
    (2, 4, 5),
])
def test_k_components_complete_multipartite_family_raw_shape_matches_networkx(
    sizes,
):
    fg = _complete_multipartite(fnx, *sizes)
    ng = _complete_multipartite(nx, *sizes)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert {k: [set(c) for c in v] for k, v in fr.items()} == {
        k: [set(c) for c in v] for k, v in nr.items()
    }
    assert {k: [type(c).__name__ for c in v] for k, v in fr.items()} == {
        k: [type(c).__name__ for c in v] for k, v in nr.items()
    }


def test_k_components_complete_multipartite_mixed_connectivity_order_matches_networkx():
    fg = _disjoint_complete_multipartite(fnx, (2, 2, 2), (2, 3), (1, 2, 3))
    ng = _disjoint_complete_multipartite(nx, (2, 2, 2), (2, 3), (1, 2, 3))

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_complete_multipartite_custom_flow_func_delegates_like_networkx():
    fg = _complete_multipartite(fnx, 3, 4, 5)
    ng = _complete_multipartite(nx, 3, 4, 5)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def test_k_components_complete_multipartite_fast_path_rejects_missing_cross_edge():
    fg = _complete_multipartite(fnx, 3, 4)
    ng = _complete_multipartite(nx, 3, 4)
    fg.remove_edge(0, 3)
    ng.remove_edge(0, 3)

    assert fnx.k_components(fg) == nx.k_components(ng)


def _chorded_cycle(library, n):
    graph = library.cycle_graph(n)
    for node in range(0, n, 4):
        graph.add_edge(node, (node + 2) % n)
    return graph


def _disjoint_union_builders(library, *builders):
    graph = library.Graph()
    offset = 0
    for builder in builders:
        component = builder(library)
        mapping = {node: node + offset for node in component.nodes()}
        graph.add_nodes_from(mapping.values())
        graph.add_edges_from((mapping[u], mapping[v]) for u, v in component.edges())
        offset += component.number_of_nodes()
    return graph


@pytest.mark.parametrize("builder", [
    lambda L: _graph_with_nodes_edges(
        L, [], [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    ),
    lambda L: _chorded_cycle(L, 12),
    lambda L: _chorded_cycle(L, 16),
])
def test_k_components_two_degenerate_biconnected_family_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert {k: [set(c) for c in v] for k, v in fr.items()} == {
        k: [set(c) for c in v] for k, v in nr.items()
    }
    assert {k: [type(c).__name__ for c in v] for k, v in fr.items()} == {
        k: [type(c).__name__ for c in v] for k, v in nr.items()
    }


def test_k_components_two_degenerate_disconnected_order_matches_networkx():
    fg = _disjoint_union_builders(
        fnx,
        lambda L: _chorded_cycle(L, 8),
        lambda L: _graph_with_nodes_edges(
            L, [], [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
        ),
    )
    ng = _disjoint_union_builders(
        nx,
        lambda L: _chorded_cycle(L, 8),
        lambda L: _graph_with_nodes_edges(
            L, [], [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
        ),
    )

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_two_degenerate_custom_flow_func_delegates_like_networkx():
    fg = _chorded_cycle(fnx, 12)
    ng = _chorded_cycle(nx, 12)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def test_k_components_two_degenerate_fast_path_rejects_three_core_graph():
    fg = fnx.circular_ladder_graph(6)
    ng = nx.circular_ladder_graph(6)

    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize("size", [3, 4, 6, 10])
def test_k_components_ordered_prism_fast_path_matches_networkx(size):
    fg = fnx.circular_ladder_graph(size)
    ng = nx.circular_ladder_graph(size)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == [3, 2, 1]
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_ordered_prism_custom_flow_func_delegates_like_networkx():
    fg = fnx.circular_ladder_graph(6)
    ng = nx.circular_ladder_graph(6)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def test_k_components_ordered_prism_missing_rung_delegates_and_matches_networkx():
    fg = fnx.circular_ladder_graph(6)
    ng = nx.circular_ladder_graph(6)
    fg.remove_edge(0, 6)
    ng.remove_edge(0, 6)

    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize("size", [5, 8, 12])
def test_k_components_wheel_fast_path_matches_networkx(size):
    fg = fnx.wheel_graph(size)
    ng = nx.wheel_graph(size)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == [3, 2, 1]
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_wheel_custom_flow_func_delegates_like_networkx():
    fg = fnx.wheel_graph(8)
    ng = nx.wheel_graph(8)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def test_k_components_wheel_disconnected_rim_delegates_and_matches_networkx():
    fg = fnx.Graph()
    ng = nx.Graph()
    spokes = [(0, node) for node in range(1, 7)]
    rim_edges = [(1, 2), (2, 3), (3, 1), (4, 5), (5, 6), (6, 4)]
    fg.add_edges_from(spokes + rim_edges)
    ng.add_edges_from(spokes + rim_edges)

    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize("dimension", [3, 4])
def test_k_components_hypercube_fast_path_matches_networkx(dimension):
    fg = fnx.hypercube_graph(dimension)
    ng = nx.hypercube_graph(dimension)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == list(range(dimension, 0, -1))
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_hypercube_custom_flow_func_delegates_like_networkx():
    fg = fnx.hypercube_graph(4)
    ng = nx.hypercube_graph(4)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def test_k_components_hypercube_missing_edge_delegates_and_matches_networkx():
    fg = fnx.hypercube_graph(3)
    ng = nx.hypercube_graph(3)
    edge = ((0, 0, 0), (1, 0, 0))
    fg.remove_edge(*edge)
    ng.remove_edge(*edge)

    assert fnx.k_components(fg) == nx.k_components(ng)


def _paired_clique_barbell(L, size):
    graph = L.Graph()
    left = list(range(size))
    right = list(range(size, 2 * size))
    graph.add_nodes_from(left)
    graph.add_nodes_from(right)
    for group in (left, right):
        for index, source in enumerate(group):
            for target in group[index + 1:]:
                graph.add_edge(source, target)
    graph.add_edge(left[0], right[0])
    graph.add_edge(left[1], right[1])
    return graph


def _near_barbell_bypass(L, size):
    graph = L.barbell_graph(size, 1)
    graph.add_edge(1, size + 2)
    return graph


@pytest.mark.parametrize(
    "name,builder,size",
    [
        ("paired_clique_barbell", _paired_clique_barbell, 5),
        ("paired_clique_barbell", _paired_clique_barbell, 8),
        ("near_barbell_bypass", _near_barbell_bypass, 5),
        ("near_barbell_bypass", _near_barbell_bypass, 8),
    ],
)
def test_k_components_ordered_two_clique_bridge_matches_networkx(
    name,
    builder,
    size,
):
    fg = builder(fnx, size)
    ng = builder(nx, size)
    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)
    assert list(fr.keys()) == list(nr.keys()), name
    assert fr == nr, name


def test_k_components_ordered_two_clique_bridge_custom_flow_delegates_like_networkx():
    fg = _paired_clique_barbell(fnx, 5)
    ng = _paired_clique_barbell(nx, 5)

    def fail_flow(*_args, **_kwargs):
        raise RuntimeError("flow reached")

    with pytest.raises(RuntimeError, match="flow reached"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow reached"):
        nx.k_components(ng, flow_func=fail_flow)


def test_k_components_ordered_two_clique_bridge_shared_endpoint_delegates():
    fg = fnx.Graph()
    ng = nx.Graph()
    for graph in (fg, ng):
        graph.add_nodes_from(range(8))
        for group in (range(4), range(4, 8)):
            group = list(group)
            for index, source in enumerate(group):
                for target in group[index + 1:]:
                    graph.add_edge(source, target)
        graph.add_edge(0, 4)
        graph.add_edge(0, 5)
    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize(
    "builder",
    [
        lambda mod: mod.petersen_graph(),
        lambda mod: mod.generalized_petersen_graph(7, 2),
        lambda mod: mod.generalized_petersen_graph(8, 3),
        lambda mod: mod.generalized_petersen_graph(10, 2),
    ],
)
def test_k_components_cubic_three_connected_family_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == [3, 2, 1]
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_cubic_three_connected_custom_flow_delegates_like_networkx():
    fg = fnx.generalized_petersen_graph(7, 2)
    ng = nx.generalized_petersen_graph(7, 2)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def _cubic_two_cut_graph(mod):
    graph = mod.Graph()
    graph.add_edges_from(
        [
            (0, 1),
            (0, 2),
            (0, 3),
            (1, 2),
            (1, 3),
            (4, 6),
            (4, 7),
            (5, 6),
            (5, 7),
            (6, 7),
            (2, 4),
            (3, 5),
        ]
    )
    return graph


def test_k_components_cubic_two_cut_delegates_and_matches_networkx():
    fg = _cubic_two_cut_graph(fnx)
    ng = _cubic_two_cut_graph(nx)

    assert all(degree == 3 for _, degree in fg.degree())
    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize(
    "builder",
    [
        lambda mod: mod.random_regular_graph(4, 18, seed=3),
        lambda mod: mod.random_regular_graph(4, 24, seed=5),
    ],
)
def test_k_components_four_regular_four_connected_family_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == [4, 3, 2, 1]
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_four_regular_custom_flow_delegates_like_networkx():
    fg = fnx.random_regular_graph(4, 18, seed=3)
    ng = nx.random_regular_graph(4, 18, seed=3)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def _four_regular_two_cut_graph(mod):
    graph = mod.complete_graph(5)
    graph.add_nodes_from(range(5, 10))
    graph.add_edges_from(
        (u, v)
        for u in range(5, 10)
        for v in range(u + 1, 10)
    )
    graph.remove_edge(0, 1)
    graph.remove_edge(5, 6)
    graph.add_edge(0, 5)
    graph.add_edge(1, 6)
    return graph


def test_k_components_four_regular_two_cut_delegates_and_matches_networkx():
    fg = _four_regular_two_cut_graph(fnx)
    ng = _four_regular_two_cut_graph(nx)

    assert all(degree == 4 for _, degree in fg.degree())
    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize(
    "builder",
    [
        lambda mod: mod.random_regular_graph(5, 20, seed=7),
        lambda mod: mod.random_regular_graph(5, 24, seed=11),
    ],
)
def test_k_components_five_regular_five_connected_family_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == [5, 4, 3, 2, 1]
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_five_regular_custom_flow_delegates_like_networkx():
    fg = fnx.random_regular_graph(5, 20, seed=7)
    ng = nx.random_regular_graph(5, 20, seed=7)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def _five_regular_two_cut_graph(mod):
    graph = mod.complete_graph(6)
    graph.add_nodes_from(range(6, 12))
    graph.add_edges_from(
        (u, v)
        for u in range(6, 12)
        for v in range(u + 1, 12)
    )
    graph.remove_edge(0, 1)
    graph.remove_edge(6, 7)
    graph.add_edge(0, 6)
    graph.add_edge(1, 7)
    return graph


def test_k_components_five_regular_two_cut_delegates_and_matches_networkx():
    fg = _five_regular_two_cut_graph(fnx)
    ng = _five_regular_two_cut_graph(nx)

    assert all(degree == 5 for _, degree in fg.degree())
    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize(
    "builder",
    [
        lambda mod: mod.random_regular_graph(6, 20, seed=17),
        lambda mod: mod.random_regular_graph(6, 24, seed=19),
    ],
)
def test_k_components_six_regular_six_connected_family_matches_networkx(builder):
    fg = builder(fnx)
    ng = builder(nx)

    fr = fnx.k_components(fg)
    nr = nx.k_components(ng)

    assert list(fr.keys()) == [6, 5, 4, 3, 2, 1]
    assert list(fr.keys()) == list(nr.keys())
    assert [[set(component) for component in fr[k]] for k in fr] == [
        [set(component) for component in nr[k]] for k in nr
    ]


def test_k_components_six_regular_custom_flow_delegates_like_networkx():
    fg = fnx.random_regular_graph(6, 20, seed=17)
    ng = nx.random_regular_graph(6, 20, seed=17)

    def fail_flow(*args, **kwargs):
        raise RuntimeError("flow called")

    with pytest.raises(RuntimeError, match="flow called"):
        fnx.k_components(fg, flow_func=fail_flow)
    with pytest.raises(RuntimeError, match="flow called"):
        nx.k_components(ng, flow_func=fail_flow)


def _six_regular_two_cut_graph(mod):
    graph = mod.complete_graph(7)
    graph.add_nodes_from(range(7, 14))
    graph.add_edges_from(
        (u, v)
        for u in range(7, 14)
        for v in range(u + 1, 14)
    )
    graph.remove_edge(0, 1)
    graph.remove_edge(7, 8)
    graph.add_edge(0, 7)
    graph.add_edge(1, 8)
    return graph


def test_k_components_six_regular_two_cut_delegates_and_matches_networkx():
    fg = _six_regular_two_cut_graph(fnx)
    ng = _six_regular_two_cut_graph(nx)

    assert all(degree == 6 for _, degree in fg.degree())
    assert fnx.k_components(fg) == nx.k_components(ng)


@pytest.mark.parametrize(
    "name,builder,k",
    [
        ("complete_4_k2", lambda L: L.complete_graph(4), 2),
        ("petersen_k2", lambda L: L.petersen_graph(), 2),
        ("path_5_k1", lambda L: L.path_graph(5), 1),
        ("path_5_k2", lambda L: L.path_graph(5), 2),
    ],
)
def test_k_edge_components_matches_networkx(name, builder, k):
    fg, ng = _build_pair(builder)
    fr = sorted(frozenset(s) for s in fnx.k_edge_components(fg, k))
    nr = sorted(frozenset(s) for s in nx.k_edge_components(ng, k))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder,k",
    [
        ("complete_4_k2", lambda L: L.complete_graph(4), 2),
        ("petersen_k2", lambda L: L.petersen_graph(), 2),
        ("path_5_k1", lambda L: L.path_graph(5), 1),
    ],
)
def test_k_edge_subgraphs_matches_networkx(name, builder, k):
    fg, ng = _build_pair(builder)
    fr = sorted(frozenset(s) for s in fnx.k_edge_subgraphs(fg, k))
    nr = sorted(frozenset(s) for s in nx.k_edge_subgraphs(ng, k))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# connectivity.cuts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,builder,s,t",
    [
        ("path_5_endpoints", lambda L: L.path_graph(5), 0, 4),
        ("petersen_pair", lambda L: L.petersen_graph(), 0, 5),
        ("complete_4_pair", lambda L: L.complete_graph(4), 0, 3),
    ],
)
def test_minimum_st_edge_cut_matches_networkx_size(name, builder, s, t):
    """``minimum_st_edge_cut`` is in ``nx.algorithms.connectivity`` (not
    on the top-level ``nx`` namespace). Cut sizes must agree even when
    the specific cut chosen differs by tie-break."""
    fg, ng = _build_pair(builder)
    fr = fnx.algorithms.connectivity.minimum_st_edge_cut(fg, s, t)
    nr = nx.algorithms.connectivity.minimum_st_edge_cut(ng, s, t)
    assert len(fr) == len(nr), f"{name}: fnx={len(fr)} nx={len(nr)}"


@pytest.mark.parametrize(
    "name,builder,s,t",
    [
        ("path_5_endpoints", lambda L: L.path_graph(5), 0, 4),
        ("petersen_pair", lambda L: L.petersen_graph(), 0, 5),
    ],
)
def test_minimum_st_node_cut_matches_networkx_size(name, builder, s, t):
    fg, ng = _build_pair(builder)
    fr = fnx.algorithms.connectivity.minimum_st_node_cut(fg, s, t)
    nr = nx.algorithms.connectivity.minimum_st_node_cut(ng, s, t)
    assert len(fr) == len(nr)


def test_minimum_node_cut_default_endpoints_matches_size():
    fg = fnx.cycle_graph(6)
    ng = nx.cycle_graph(6)
    fr = fnx.minimum_node_cut(fg)
    nr = nx.minimum_node_cut(ng)
    assert len(fr) == len(nr)


def test_minimum_edge_cut_default_endpoints_matches_size():
    fg = fnx.cycle_graph(6)
    ng = nx.cycle_graph(6)
    fr = fnx.minimum_edge_cut(fg)
    nr = nx.minimum_edge_cut(ng)
    assert len(fr) == len(nr)


# ---------------------------------------------------------------------------
# Assortativity (attribute / numeric / degree-connectivity)
# ---------------------------------------------------------------------------


def _attr_graph(L, color_map):
    g = L.Graph()
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (1, 3)]
    g.add_edges_from(edges)
    for node, color in color_map.items():
        g.nodes[node]["color"] = color
        g.nodes[node]["size"] = node + 1
    return g


@pytest.mark.parametrize(
    "name,color_map",
    [
        ("alternating", {0: "R", 1: "B", 2: "R", 3: "B", 4: "R"}),
        ("two_classes_balanced",
         {0: "R", 1: "R", 2: "B", 3: "B", 4: "B"}),
        ("uniform", {0: "R", 1: "R", 2: "R", 3: "R", 4: "R"}),
    ],
)
def test_attribute_assortativity_coefficient_matches_networkx(
    name, color_map,
):
    fg = _attr_graph(fnx, color_map)
    ng = _attr_graph(nx, color_map)
    fr = fnx.attribute_assortativity_coefficient(fg, "color")
    nr = nx.attribute_assortativity_coefficient(ng, "color")
    assert _close(fr, nr, tol=1e-6), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,color_map",
    [
        ("alternating", {0: "R", 1: "B", 2: "R", 3: "B", 4: "R"}),
        ("two_classes_balanced",
         {0: "R", 1: "R", 2: "B", 3: "B", 4: "B"}),
    ],
)
def test_numeric_assortativity_coefficient_matches_networkx(
    name, color_map,
):
    fg = _attr_graph(fnx, color_map)
    ng = _attr_graph(nx, color_map)
    fr = fnx.numeric_assortativity_coefficient(fg, "size")
    nr = nx.numeric_assortativity_coefficient(ng, "size")
    assert _close(fr, nr, tol=1e-6), f"{name}: fnx={fr} nx={nr}"


@pytest.mark.parametrize(
    "name,builder",
    [
        ("path_5", lambda L: L.path_graph(5)),
        ("petersen", lambda L: L.petersen_graph()),
        ("complete_4", lambda L: L.complete_graph(4)),
    ],
)
def test_average_degree_connectivity_matches_networkx(name, builder):
    fg, ng = _build_pair(builder)
    fr = fnx.average_degree_connectivity(fg)
    nr = nx.average_degree_connectivity(ng)
    assert set(fr.keys()) == set(nr.keys())
    for k in fr:
        assert _close(fr[k], nr[k], tol=1e-9)


# ---------------------------------------------------------------------------
# gomory_hu_tree
# ---------------------------------------------------------------------------


def _capacity_graph(L, edges):
    """Build a graph where every edge has unit capacity so the
    flow-based Gomory-Hu tree algorithm has bounded edge weights."""
    g = L.Graph()
    for (u, v) in edges:
        g.add_edge(u, v, capacity=1)
    return g


@pytest.mark.parametrize(
    "name,edge_set",
    [
        ("cycle_4", [(0, 1), (1, 2), (2, 3), (3, 0)]),
        ("complete_4",
         [(u, v) for u in range(4) for v in range(u + 1, 4)]),
        ("petersen", list(nx.petersen_graph().edges())),
    ],
)
def test_gomory_hu_tree_is_a_tree_matching_networkx(name, edge_set):
    fg = _capacity_graph(fnx, edge_set)
    ng = _capacity_graph(nx, edge_set)
    fr = fnx.gomory_hu_tree(fg)
    nr = nx.gomory_hu_tree(ng)
    # Both must be trees on the same node set
    assert set(fr.nodes()) == set(ng.nodes()) == set(fg.nodes())
    assert fr.number_of_edges() == nr.number_of_edges() == fr.number_of_nodes() - 1
    # Total edge weight matches (Gomory-Hu invariant: |V|-1 unique
    # st-cut values)
    fr_total = sum(d.get("weight", 1) for _, _, d in fr.edges(data=True))
    nr_total = sum(d.get("weight", 1) for _, _, d in nr.edges(data=True))
    assert _close(fr_total, nr_total)


# ---------------------------------------------------------------------------
# Cross-relation invariants
# ---------------------------------------------------------------------------


def test_arborescence_is_branching():
    """Every arborescence is a branching."""
    g = fnx.DiGraph()
    g.add_edges_from([(0, 1), (0, 2), (1, 3)])
    assert fnx.is_arborescence(g)
    assert fnx.is_branching(g)


def test_tree_is_forest():
    """Every tree is a forest."""
    g = fnx.balanced_tree(2, 3)
    assert fnx.is_tree(g)
    assert fnx.is_forest(g)


def test_minimum_branching_weight_le_maximum_branching():
    """Minimum branching weight ≤ Maximum branching weight."""
    g = _weighted_arborescence(fnx)
    min_b = fnx.minimum_branching(g)
    max_b = fnx.maximum_branching(g)
    min_w = sum(d.get("weight", 1) for _, _, d in min_b.edges(data=True))
    max_w = sum(d.get("weight", 1) for _, _, d in max_b.edges(data=True))
    assert min_w <= max_w + 1e-9


def test_attribute_assortativity_uniform_is_nan():
    """When all nodes share the same attribute value, the
    coefficient is NaN (degenerate case — no variance)."""
    g = _attr_graph(fnx, {0: "R", 1: "R", 2: "R", 3: "R", 4: "R"})
    val = fnx.attribute_assortativity_coefficient(g, "color")
    assert math.isnan(val), f"expected NaN, got {val}"


def test_minimum_node_cut_size_equals_node_connectivity():
    """``len(minimum_node_cut)`` equals node_connectivity(G)."""
    g = fnx.cycle_graph(6)
    cut = fnx.minimum_node_cut(g)
    nc = fnx.node_connectivity(g)
    assert len(cut) == nc
