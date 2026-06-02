"""Value parity for tournament functions and min-cost-flow variants.

Tournament algorithms (is_tournament, hamiltonian_path, score_sequence,
is_strongly_connected) and the min-cost-flow family (min_cost_flow_cost,
network_simplex, capacity_scaling, max_flow_min_cost/cost_of_flow) run intricate
native kernels that the existing value nets don't cover. This pins their
scalar/structural outputs to networkx's at small and medium scale.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _tournament(mod, n):
    g = mod.DiGraph()
    for i in range(n):
        for j in range(i + 1, n):
            if (i + j) % 2 == 0:
                g.add_edge(i, j)
            else:
                g.add_edge(j, i)
    return g


@pytest.mark.parametrize("n", [5, 9, 30])
def test_is_tournament_matches_networkx(n):
    assert fnx.tournament.is_tournament(_tournament(fnx, n)) == nx.tournament.is_tournament(_tournament(nx, n)) is True


@pytest.mark.parametrize("n", [5, 9, 30])
def test_hamiltonian_path_length_matches_networkx(n):
    # Every tournament has a Hamiltonian path visiting all n nodes.
    pf = fnx.tournament.hamiltonian_path(_tournament(fnx, n))
    pn = nx.tournament.hamiltonian_path(_tournament(nx, n))
    assert len(pf) == len(pn) == n
    # the returned path must be a valid directed path in the tournament
    g = _tournament(fnx, n)
    assert all(g.has_edge(pf[i], pf[i + 1]) for i in range(len(pf) - 1))


def test_tournament_score_sequence_matches_networkx():
    if not (hasattr(nx.tournament, "score_sequence") and hasattr(fnx.tournament, "score_sequence")):
        pytest.skip("score_sequence unavailable")
    for n in (5, 9):
        assert sorted(fnx.tournament.score_sequence(_tournament(fnx, n))) == sorted(
            nx.tournament.score_sequence(_tournament(nx, n))
        )


def _mcf(mod, n):
    g = mod.DiGraph()
    g.add_node(0, demand=-10)
    g.add_node(n - 1, demand=10)
    for i in range(n):
        j = (i + 1) % n
        g.add_edge(i, j, capacity=15, weight=1 + (i % 5))
        k = (i * 2 + 3) % n
        if k != i:
            g.add_edge(i, k, capacity=8, weight=2 + (i % 4))
    return g


@pytest.mark.parametrize("n", [6, 80])
def test_min_cost_flow_cost_matches_networkx(n):
    assert fnx.min_cost_flow_cost(_mcf(fnx, n)) == nx.min_cost_flow_cost(_mcf(nx, n))


@pytest.mark.parametrize("n", [6, 80])
def test_network_simplex_cost_matches_networkx(n):
    assert fnx.network_simplex(_mcf(fnx, n))[0] == nx.network_simplex(_mcf(nx, n))[0]


@pytest.mark.parametrize("n", [6, 40])
def test_capacity_scaling_cost_matches_networkx(n):
    if not (hasattr(nx, "capacity_scaling") and hasattr(fnx, "capacity_scaling")):
        pytest.skip("capacity_scaling unavailable")
    assert fnx.capacity_scaling(_mcf(fnx, n))[0] == nx.capacity_scaling(_mcf(nx, n))[0]


def test_max_flow_min_cost_cost_matches_networkx():
    if not (hasattr(nx, "cost_of_flow") and hasattr(fnx, "cost_of_flow")):
        pytest.skip("cost_of_flow unavailable")
    def build(mod):
        g = mod.DiGraph()
        for u, v, c, w in [(0, 1, 4, 2), (0, 2, 3, 1), (1, 3, 3, 1), (2, 3, 4, 3), (1, 2, 2, 1), (3, 4, 5, 1)]:
            g.add_edge(u, v, capacity=c, weight=w)
        return g
    cn = nx.cost_of_flow(build(nx), nx.max_flow_min_cost(build(nx), 0, 4))
    cf = fnx.cost_of_flow(build(fnx), fnx.max_flow_min_cost(build(fnx), 0, 4))
    assert cf == cn
