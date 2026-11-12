"""k-core nesting, degeneracy, and core_number / k_shell consistency.

The k-core decomposition obeys structural laws cross-checking k_core,
core_number, and k_shell:
  - nesting: k_core(k+1) is a subgraph of k_core(k);
  - k_core(k) is exactly {v : core_number(v) >= k};
  - every node in k_core(k) has degree >= k WITHIN that core;
  - the degeneracy is max(core_number); k_core(degeneracy) is non-empty and
    k_core(degeneracy+1) is empty;
  - k_shell(k) = k_core(k) minus k_core(k+1).
Oracle-free structural invariants, independent of networkx.

The laws above constrain which NODES come back. They do not pin the returned
subgraph's EDGES: a core carrying extra edges still satisfies every degree bound
(extra edges only raise degrees), and a core returned as a live view of the
parent has identical nodes and degrees to one returned as a copy. Both of those
are pinned here — k_core is the induced subgraph on its nodes, and it is a copy,
so mutating it leaves the parent alone.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(6, 12)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


def _edge_set(g):
    return {frozenset((u, v)) for u, v in g.edges()}


def _induced_edges(g, nodes):
    """The edges of g with both endpoints inside `nodes`."""
    return {frozenset((u, v)) for u, v in g.edges() if u in nodes and v in nodes}


@pytest.mark.parametrize("seed", range(40))
def test_kcore_nesting_and_corenumber_consistency(seed):
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("empty")
    cn = fnx.core_number(g)
    max_core = max(cn.values())

    for k in range(0, max_core + 1):
        ck = set(fnx.k_core(g, k).nodes())
        ck1 = set(fnx.k_core(g, k + 1).nodes())
        assert ck1 <= ck                                # nesting
        if k >= 1:
            assert ck == {v for v, c in cn.items() if c >= k}   # core = corenum>=k


@pytest.mark.parametrize("seed", range(40))
def test_kcore_min_degree_and_degeneracy(seed):
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("empty")
    cn = fnx.core_number(g)
    max_core = max(cn.values())

    for k in range(1, max_core + 1):
        kcg = fnx.k_core(g, k)
        # Every node in the k-core has internal degree >= k.
        assert all(d >= k for _, d in kcg.degree())

    # Degeneracy boundary.
    assert fnx.k_core(g, max_core).number_of_nodes() > 0
    assert fnx.k_core(g, max_core + 1).number_of_nodes() == 0


@pytest.mark.parametrize("seed", range(40))
def test_kshell_is_core_difference(seed):
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("empty")
    max_core = max(fnx.core_number(g).values())
    for k in range(0, max_core + 1):
        shell = fnx.k_shell(g, k)
        expected = set(fnx.k_core(g, k).nodes()) - set(fnx.k_core(g, k + 1).nodes())
        assert set(shell.nodes()) == expected
        # The shell is likewise induced, not merely a node bag.
        assert _edge_set(shell) == _induced_edges(g, expected)


@pytest.mark.parametrize("seed", range(40))
def test_kcore_is_the_induced_subgraph_on_its_nodes(seed):
    """Degree bounds cannot pin the edge set — extra edges only raise degrees."""
    g = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("empty")
    max_core = max(fnx.core_number(g).values())

    for k in range(0, max_core + 2):
        core = fnx.k_core(g, k)
        nodes = set(core.nodes())
        assert _edge_set(core) == _induced_edges(g, nodes)
        # The O(1) count and the iterated edges must agree — a core that counts
        # its edges off a different path than it yields them is broken either way.
        assert core.number_of_edges() == len(list(core.edges()))


def test_kcore_is_a_copy_not_a_live_view():
    """k_core returns an independent graph: mutating it must not touch the parent."""
    g = fnx.gnm_random_graph(14, 40, seed=5)
    parent_nodes, parent_edges = set(g.nodes()), _edge_set(g)

    core = fnx.k_core(g, 2)
    assert core.number_of_nodes() > 0, "fixture must produce a non-empty 2-core"
    victim = next(iter(core.nodes()))
    core.remove_node(victim)

    assert set(g.nodes()) == parent_nodes            # parent untouched by the removal
    assert _edge_set(g) == parent_edges
    assert victim not in core                         # ...and the core really changed


def test_default_k_is_the_degeneracy_core():
    g = fnx.gnm_random_graph(16, 50, seed=9)
    degeneracy = max(fnx.core_number(g).values())
    default_core, explicit = fnx.k_core(g), fnx.k_core(g, degeneracy)
    assert set(default_core.nodes()) == set(explicit.nodes())
    assert _edge_set(default_core) == _edge_set(explicit)
