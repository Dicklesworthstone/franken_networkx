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
        shell = set(fnx.k_shell(g, k).nodes())
        expected = set(fnx.k_core(g, k).nodes()) - set(fnx.k_core(g, k + 1).nodes())
        assert shell == expected
