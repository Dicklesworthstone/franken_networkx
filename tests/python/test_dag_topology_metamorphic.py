"""Metamorphic tests for DAG-specific topological algebraic invariants.

Eleventh metamorphic-equivalence module pairing with the ten already
in place. Asserts the algebraic properties that follow from the DAG
acyclicity contract — every textbook identity that must hold on every
DAG.

DAG topology invariants:

1. **Topological-order consistency**: for every edge ``u → v`` of a
   DAG, the topological position of u is strictly less than v.
2. **Topological generations are antichains**: within each generation
   produced by ``topological_generations``, no two members are
   connected by an edge (each generation is an independent set in
   the DAG).
3. **Generations partition the DAG node set**: every node appears in
   exactly one generation; the union covers V.
4. **All-topological-sorts validity**: every order in
   ``all_topological_sorts(G)`` satisfies the edge-precedence rule.
5. **Ancestors / descendants**:
   * ``v ∈ descendants(u) iff u ∈ ancestors(v)`` (symmetry).
   * ``descendants(v) ∪ {v} ∪ ancestors(v)`` partitions reachable
     nodes for a connected DAG-tree, but on general DAGs only
     captures the comparable pairs.
6. **DAG longest path bounded**: the simple-path longest path on a
   DAG has at most |V| nodes (no repeats).
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


DAG_FIXTURES = [
    (
        "linear_chain_5",
        lambda: fnx.DiGraph(
            [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
        ),
    ),
    (
        "shortcut_chain_5",
        lambda: fnx.DiGraph(
            [
                ("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"),
                ("a", "c"), ("a", "d"), ("a", "e"),
                ("b", "d"), ("b", "e"),
                ("c", "e"),
            ]
        ),
    ),
    (
        "diamond",
        lambda: fnx.DiGraph(
            [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "d")]
        ),
    ),
    (
        "balanced_tree_2_3",
        lambda: fnx.balanced_tree(2, 3, create_using=fnx.DiGraph),
    ),
    (
        "balanced_tree_3_2",
        lambda: fnx.balanced_tree(3, 2, create_using=fnx.DiGraph),
    ),
]


# -----------------------------------------------------------------------------
# Topological-order consistency
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_topological_order_consistent_with_edges(name, builder):
    g = builder()
    order = list(fnx.topological_sort(g))
    position = {n: i for i, n in enumerate(order)}
    assert set(position) == set(g.nodes()), (
        f"{name}: topological_sort emitted {set(position)} but G has "
        f"{set(g.nodes())}"
    )
    for u, v in g.edges():
        assert position[u] < position[v], (
            f"{name}: edge {u} → {v} violates topological order "
            f"(pos[{u}]={position[u]} >= pos[{v}]={position[v]})"
        )


# -----------------------------------------------------------------------------
# Topological generations
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_topological_generations_are_antichains(name, builder):
    g = builder()
    generations = list(fnx.topological_generations(g))
    for gen in generations:
        for i, u in enumerate(gen):
            for v in gen[i + 1:]:
                assert not g.has_edge(u, v), (
                    f"{name}: generation contains edge {u} → {v} "
                    f"(generations must be antichains)"
                )
                assert not g.has_edge(v, u), (
                    f"{name}: generation contains edge {v} → {u} "
                    f"(generations must be antichains)"
                )


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_topological_generations_partition_nodes(name, builder):
    g = builder()
    generations = list(fnx.topological_generations(g))
    seen = set()
    for gen in generations:
        for n in gen:
            assert g.has_node(n), (
                f"{name}: generation contains foreign node {n}"
            )
            assert n not in seen, (
                f"{name}: node {n} appears in multiple generations"
            )
            seen.add(n)
    assert seen == set(g.nodes()), (
        f"{name}: generations don't cover the DAG node set"
    )


# -----------------------------------------------------------------------------
# all_topological_sorts validity
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_all_topological_sorts_validity(name, builder):
    g = builder()
    sorts = fnx.all_topological_sorts(g)
    # Bound iteration to keep tests fast on graphs with many sorts.
    for i, order in enumerate(sorts):
        if i >= 50:
            break
        position = {n: idx for idx, n in enumerate(order)}
        for u, v in g.edges():
            assert position[u] < position[v], (
                f"{name}: all_topological_sorts emitted order {order} "
                f"that violates edge {u} → {v}"
            )


# -----------------------------------------------------------------------------
# Ancestors / descendants symmetry
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_ancestors_descendants_symmetry(name, builder):
    g = builder()
    nodes = list(g.nodes())
    if len(nodes) < 2:
        return
    for u in nodes:
        descendants = fnx.descendants(g, u)
        for d in descendants:
            ancestors_of_d = fnx.ancestors(g, d)
            assert u in ancestors_of_d, (
                f"{name}: {d} ∈ descendants({u}) but {u} ∉ ancestors({d}) "
                f"(symmetry violated)"
            )


# -----------------------------------------------------------------------------
# Ancestors / descendants exclude self
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_ancestors_descendants_exclude_self(name, builder):
    g = builder()
    for v in g.nodes():
        anc = fnx.ancestors(g, v)
        desc = fnx.descendants(g, v)
        assert v not in anc, (
            f"{name}: ancestors({v}) contains v itself"
        )
        assert v not in desc, (
            f"{name}: descendants({v}) contains v itself"
        )


# -----------------------------------------------------------------------------
# DAG longest path bounded by node count
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_dag_longest_path_bounded_by_node_count(name, builder):
    g = builder()
    path = fnx.dag_longest_path(g)
    if path is None:
        return
    assert len(path) <= g.number_of_nodes(), (
        f"{name}: dag_longest_path has {len(path)} nodes > |V| = "
        f"{g.number_of_nodes()} (must be a simple path)"
    )
    # Path must have no repeated nodes.
    assert len(set(path)) == len(path), (
        f"{name}: dag_longest_path has repeated nodes — not simple"
    )


@pytest.mark.parametrize(("name", "builder"), DAG_FIXTURES)
def test_dag_longest_path_consecutive_pairs_are_edges(name, builder):
    g = builder()
    path = fnx.dag_longest_path(g)
    if not path or len(path) < 2:
        return
    for u, v in zip(path[:-1], path[1:]):
        assert g.has_edge(u, v), (
            f"{name}: dag_longest_path step {u} → {v} is not an edge of G"
        )
