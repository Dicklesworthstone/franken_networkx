"""Whitney's inequality: node connectivity <= edge connectivity <= min degree.

Whitney's theorem bounds the connectivity measures: for any graph,
  kappa(G) <= lambda(G) <= delta(G),
where kappa is node connectivity, lambda is edge connectivity, and delta is the
minimum degree. This cross-checks node_connectivity, edge_connectivity, and the
degree sequence against each other, plus closed forms (K_n: all equal n-1;
cycle: all equal 2). Oracle-free, independent of networkx.

An inequality chain is a weak instrument on its own: kappa = lambda = 0 satisfies
0 <= 0 <= delta for every graph. The closed forms pin exact values only on named
graphs, so on the random family the values themselves are pinned here by their
definitions (minimum local connectivity over pairs) and by the bridge and
articulation-point characterisations of the value 1.

No mocks: real fnx.
"""

from __future__ import annotations

import itertools
import random

import pytest
import franken_networkx as fnx
import franken_networkx.algorithms.connectivity as fc


def _random_graph(seed):
    """The generator used by the chain test, shared so coverage stays comparable."""
    r = random.Random(seed)
    n = r.randint(4, 10)
    p = r.choice([0.3, 0.5, 0.7])
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < p]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g


@pytest.mark.parametrize("seed", range(50))
def test_whitney_chain(seed):
    r = random.Random(seed)
    n = r.randint(4, 10)
    p = r.choice([0.3, 0.5, 0.7])
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < p]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    if not fnx.is_connected(g):
        pytest.skip("disconnected")

    kappa = fnx.node_connectivity(g)
    lam = fnx.edge_connectivity(g)
    delta = min(d for _, d in g.degree())
    # Whitney: kappa <= lambda <= delta.
    assert kappa <= lam <= delta


@pytest.mark.parametrize("seed", range(50))
def test_definitions_pin_the_connectivity_values(seed):
    """kappa and lambda are minima of local connectivity — this fixes the values.

    The chain alone admits kappa = lambda = 0 on every graph; these equalities do
    not.
    """
    g = _random_graph(seed)
    if not fnx.is_connected(g):
        pytest.skip("disconnected")

    pairs = list(itertools.combinations(g.nodes(), 2))
    assert fnx.edge_connectivity(g) == min(fc.local_edge_connectivity(g, u, v) for u, v in pairs)

    non_adjacent = [(u, v) for u, v in pairs if not g.has_edge(u, v)]
    if non_adjacent:      # K_n has none; its kappa is n-1 by convention, covered below
        assert fnx.node_connectivity(g) == min(
            fc.local_node_connectivity(g, u, v) for u, v in non_adjacent
        )


@pytest.mark.parametrize("seed", range(50))
def test_value_one_is_characterised_by_bridges_and_cut_vertices(seed):
    """lambda == 1 exactly when a bridge exists; kappa == 1 exactly when a cut vertex does."""
    g = _random_graph(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected or edgeless")

    assert (fnx.edge_connectivity(g) == 1) == fnx.has_bridges(g)
    if g.number_of_nodes() >= 3:
        has_cut_vertex = len(list(fnx.articulation_points(g))) > 0
        assert (fnx.node_connectivity(g) == 1) == has_cut_vertex


@pytest.mark.parametrize("seed", range(50))
def test_disconnected_graphs_have_zero_connectivity(seed):
    """The chain test skips these 12 seeds outright, leaving the case untested."""
    g = _random_graph(seed)
    if fnx.is_connected(g):
        pytest.skip("connected")
    assert fnx.node_connectivity(g) == 0
    assert fnx.edge_connectivity(g) == 0


@pytest.mark.parametrize("seed", range(50))
def test_chartrand_bound_forces_equality(seed):
    """Chartrand: min degree >= floor(n/2) forces lambda == delta, not merely <=."""
    g = _random_graph(seed)
    if not fnx.is_connected(g):
        pytest.skip("disconnected")
    delta = min(d for _, d in g.degree())
    if delta < g.number_of_nodes() // 2:
        pytest.skip("bound does not apply")
    assert fnx.edge_connectivity(g) == delta


def test_random_family_reaches_all_three_regimes():
    """Guards the sweeps above: they go vacuous if the family stops being varied."""
    connected = [_random_graph(s) for s in range(50)]
    disconnected = [g for g in connected if not fnx.is_connected(g)]
    conn = [g for g in connected if fnx.is_connected(g)]
    assert len(disconnected) >= 5 and len(conn) >= 20
    lambdas = {fnx.edge_connectivity(g) for g in conn}
    assert len(lambdas) >= 3, f"edge connectivity never varies: {lambdas}"


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_complete_graph_connectivity_closed_form(n):
    k = fnx.complete_graph(n)
    # K_n is (n-1)-node-connected and (n-1)-edge-connected; min degree n-1.
    assert fnx.node_connectivity(k) == n - 1
    assert fnx.edge_connectivity(k) == n - 1
    assert min(d for _, d in k.degree()) == n - 1


@pytest.mark.parametrize("n", [4, 5, 6, 7])
def test_cycle_connectivity_closed_form(n):
    c = fnx.cycle_graph(n)
    # A cycle is 2-node-connected and 2-edge-connected.
    assert fnx.node_connectivity(c) == 2
    assert fnx.edge_connectivity(c) == 2


def test_tree_connectivity_is_one():
    # A tree (with >= 2 nodes) has node and edge connectivity 1 (every edge is a bridge).
    t = fnx.path_graph(6)
    assert fnx.node_connectivity(t) == 1
    assert fnx.edge_connectivity(t) == 1
