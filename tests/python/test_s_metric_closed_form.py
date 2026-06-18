"""s_metric closed form (s_metric == sum of degree products over edges).

The s-metric is defined as the sum over edges of the product of endpoint
degrees:
  s_metric(G) = sum_{(u,v) in E} deg(u) * deg(v).
This cross-checks s_metric against the degree sequence and the edge set
(existing tests cover nx parity / degenerate inputs, not this defining formula):
  - random graphs: s_metric == sum of deg(u)*deg(v) over edges;
  - K_n: s_metric == C(n,2) * (n-1)^2;
  - star S_n: s_metric == n * n  (n leaf-center edges, each n*1).
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import math
import random

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("seed", range(40))
def test_s_metric_equals_degree_product_sum(seed):
    r = random.Random(seed)
    n = r.randint(4, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.45]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    deg = dict(g.degree())
    expected = sum(deg[u] * deg[v] for u, v in g.edges())
    assert fnx.s_metric(g) == pytest.approx(expected)


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_complete_graph_s_metric(n):
    # Each of C(n,2) edges joins two degree-(n-1) nodes.
    assert fnx.s_metric(fnx.complete_graph(n)) == pytest.approx(
        math.comb(n, 2) * (n - 1) ** 2
    )


@pytest.mark.parametrize("n", [3, 4, 5])
def test_star_s_metric(n):
    # Star with n leaves: n edges, each joining the degree-n center to a degree-1 leaf.
    assert fnx.s_metric(fnx.star_graph(n)) == pytest.approx(n * n)
