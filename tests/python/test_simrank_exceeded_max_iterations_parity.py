"""Regression + parity for ``simrank_similarity`` non-convergence.

When SimRank fails to converge within ``max_iterations``, networkx raises
``nx.ExceededMaxIterations``. fnx referenced that class without importing
it, so the non-convergence path raised a bare ``NameError`` instead. This
locks fnx to nx's exception type, message, and catchability, and checks
the converged path and a small differential sweep are unaffected.
br-r37-c1-s13m9
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _graph():
    return (
        fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]),
        nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]),
    )


@pytest.mark.parametrize("max_iterations", [1, 3, 5])
def test_non_convergence_raises_exceeded_max_iterations(max_iterations):
    fg, ng = _graph()
    with pytest.raises(nx.ExceededMaxIterations) as fnx_exc:
        fnx.simrank_similarity(fg, max_iterations=max_iterations)
    with pytest.raises(nx.ExceededMaxIterations) as nx_exc:
        nx.simrank_similarity(ng, max_iterations=max_iterations)
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_non_convergence_is_not_a_name_error():
    fg, _ = _graph()
    # Regression: previously raised NameError('ExceededMaxIterations' ...).
    try:
        fnx.simrank_similarity(fg, max_iterations=2)
    except nx.ExceededMaxIterations:
        pass
    except NameError as exc:  # pragma: no cover - the bug we fixed
        pytest.fail(f"simrank leaked a NameError: {exc}")


@pytest.mark.parametrize("seed", range(20))
def test_converged_simrank_matches_networkx(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 8)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < 0.45:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    fr = fnx.simrank_similarity(fg)
    nr = nx.simrank_similarity(ng)
    for a in nr:
        for b in nr[a]:
            assert fr[a][b] == pytest.approx(nr[a][b], abs=1e-9)
