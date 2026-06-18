"""Algebraic connectivity (Fiedler value) closed forms.

The algebraic connectivity is the second-smallest Laplacian eigenvalue, which
has exact closed forms for several named graph families — a ground-truth oracle
independent of networkx (existing tests cover nx parity / the sparse-solver
path):
  - complete K_n:            lambda_2 = n;
  - path P_n:                lambda_2 = 2(1 - cos(pi / n));
  - cycle C_n:               lambda_2 = 2(1 - cos(2*pi / n));
  - complete bipartite K_mn: lambda_2 = min(m, n).
Independent of networkx.

No mocks: real fnx against spectral-graph-theory formulas.
"""

from __future__ import annotations

import math

import pytest
import franken_networkx as fnx


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_complete_graph_algebraic_connectivity_is_n(n):
    assert fnx.algebraic_connectivity(fnx.complete_graph(n)) == pytest.approx(n, abs=1e-4)


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7])
def test_path_algebraic_connectivity(n):
    expected = 2 * (1 - math.cos(math.pi / n))
    assert fnx.algebraic_connectivity(fnx.path_graph(n)) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("n", [4, 5, 6, 7, 8])
def test_cycle_algebraic_connectivity(n):
    expected = 2 * (1 - math.cos(2 * math.pi / n))
    assert fnx.algebraic_connectivity(fnx.cycle_graph(n)) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("m,n", [(2, 3), (3, 3), (2, 4), (3, 5), (4, 4)])
def test_complete_bipartite_algebraic_connectivity_is_min(m, n):
    assert fnx.algebraic_connectivity(
        fnx.complete_bipartite_graph(m, n)
    ) == pytest.approx(min(m, n), abs=1e-4)
