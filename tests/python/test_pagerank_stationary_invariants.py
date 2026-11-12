"""PageRank stationary-distribution / fixed-point invariants.

PageRank is, by definition, the stationary distribution of the damped random
walk: it must satisfy the fixed-point equation
  pr[i] = (1 - alpha)/n + alpha * sum_{j in N(i)} pr[j] / deg(j)
(undirected form), sum to 1, be strictly positive, and be uniform on a regular
graph. These are oracle-free properties that define PageRank, checked here
independent of networkx.

"(undirected form)" is the load-bearing caveat. On a DIGRAPH the fixed point
grows a term the undirected equation does not have: a node with out-degree 0 is
dangling, its rank cannot flow along any edge, and that mass is redistributed
across the whole graph instead. The directed equation is therefore

  pr[i] = (1-a)/n + a * ( sum_{j -> i} pr[j]/outdeg(j)
                          + sum_{j dangling} pr[j]/n )

and the second sum is not decorative — dropping it breaks the equation on every
draw here that contains a dangling node. Pinned below, along with the alpha = 0
boundary where teleportation is total and the result is exactly uniform.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

_ALPHA = 0.85


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_satisfies_fixed_point(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    pr = fnx.pagerank(g, alpha=_ALPHA)
    deg = dict(g.degree())

    assert abs(sum(pr.values()) - 1.0) < 1e-6      # probability distribution
    assert all(v > 0 for v in pr.values())          # strictly positive

    # The defining fixed-point equation of (undirected) PageRank.
    for i in g:
        expected = (1 - _ALPHA) / n + _ALPHA * sum(
            pr[j] / deg[j] for j in g.neighbors(i)
        )
        assert abs(pr[i] - expected) < 1e-4


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    d = fnx.DiGraph(); d.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.25:
                d.add_edge(u, v)
    return d, n


def _dangling(d):
    out_degree = dict(d.out_degree())
    return [j for j in d if out_degree[j] == 0]


@pytest.mark.parametrize("seed", range(40))
def test_directed_fixed_point_redistributes_dangling_mass(seed):
    """The directed form, which the undirected sweep above never reaches."""
    d, n = _digraph(seed)
    pr = fnx.pagerank(d, alpha=_ALPHA)
    out_degree = dict(d.out_degree())
    dangling_mass = sum(pr[j] for j in _dangling(d))

    assert abs(sum(pr.values()) - 1.0) < 1e-6
    assert all(v > 0 for v in pr.values())
    for i in d:
        inflow = sum(pr[j] / out_degree[j] for j in d.predecessors(i))
        expected = (1 - _ALPHA) / n + _ALPHA * (inflow + dangling_mass / n)
        assert abs(pr[i] - expected) < 1e-4


def test_dangling_term_is_load_bearing():
    """Guards the test above: without dangling nodes it would prove nothing extra."""
    checked = 0
    for seed in range(40):
        d, n = _digraph(seed)
        if not _dangling(d):
            continue
        checked += 1
        pr = fnx.pagerank(d, alpha=_ALPHA)
        out_degree = dict(d.out_degree())
        # Same equation MINUS the redistribution term: it must fail somewhere.
        assert any(
            abs(pr[i] - ((1 - _ALPHA) / n + _ALPHA * sum(
                pr[j] / out_degree[j] for j in d.predecessors(i)))) > 1e-4
            for i in d
        )
    assert checked >= 10, f"only {checked} draws contain a dangling node"


def test_alpha_zero_is_exactly_uniform():
    """No damping means pure teleportation, so structure cannot matter at all."""
    for g in (fnx.path_graph(6), fnx.star_graph(5)):
        pr = fnx.pagerank(g, alpha=0)
        n = g.number_of_nodes()
        assert all(abs(v - 1.0 / n) < 1e-9 for v in pr.values())


@pytest.mark.parametrize("builder", [
    lambda n: fnx.cycle_graph(n),       # 2-regular
    lambda n: fnx.complete_graph(n),    # (n-1)-regular
])
@pytest.mark.parametrize("n", [4, 5, 6])
def test_regular_graph_has_uniform_pagerank(builder, n):
    pr = fnx.pagerank(builder(n))
    # A regular graph's PageRank is uniform (1/n at every node).
    assert max(pr.values()) - min(pr.values()) < 1e-6
    assert all(abs(v - 1.0 / n) < 1e-6 for v in pr.values())


def test_uniform_personalization_equals_default():
    # Uniform personalization is exactly the default PageRank teleportation,
    # so it must reproduce the unpersonalized result.
    g = fnx.path_graph(5)
    uniform = fnx.pagerank(g, personalization={i: 1 for i in range(5)})
    default = fnx.pagerank(g)
    assert all(abs(uniform[k] - default[k]) < 1e-9 for k in g)


def test_personalization_biases_toward_seed():
    # Personalizing on node 0 must give node 0 MORE rank than personalizing on
    # the far node 4 does — a monotone bias toward the seed.
    g = fnx.path_graph(5)
    pr_seed0 = fnx.pagerank(g, personalization={0: 1, 1: 0, 2: 0, 3: 0, 4: 0})
    pr_seed4 = fnx.pagerank(g, personalization={0: 0, 1: 0, 2: 0, 3: 0, 4: 1})
    assert abs(sum(pr_seed0.values()) - 1.0) < 1e-6
    assert pr_seed0[0] > pr_seed4[0]
