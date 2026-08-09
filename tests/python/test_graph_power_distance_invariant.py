"""Graph power G^k distance invariant (power <-> shortest paths).

The k-th power of a graph has an edge (u, v) exactly when u and v are within
distance k in the original graph. This is the DEFINING property, cross-checking
power against all_pairs_shortest_path_length (the existing power test covers
nx parity, not this invariant):
  - G^k has edge (u, v) iff 1 <= dist(u, v) <= k;
  - G^1 == G;
  - for a connected graph, G^diameter is the complete graph.
Oracle-free, independent of networkx.

Every assertion above compares EDGE sets, which says nothing about the node set:
a power that silently dropped isolated nodes would satisfy all of them, and 16 of
the 40 draws have an isolated node. And "for a connected graph" costs the
diameter test 18 of its 40 draws — a disconnected graph still has the invariant,
one component at a time. Both are covered below, together with the k <= 0 and
directed contracts.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _graph(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.35]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


def _edge_set(g):
    return {tuple(sorted((u, v))) for u, v in g.edges()}


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_power_edge_iff_within_distance_k(seed, k):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    gk_edges = _edge_set(fnx.power(g, k))
    expected = {
        (u, v)
        for u in g for v in apsp[u]
        if u < v and 1 <= apsp[u][v] <= k
    }
    assert gk_edges == expected


@pytest.mark.parametrize("seed", range(40))
def test_power_one_is_identity(seed):
    g, n = _graph(seed)
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    assert _edge_set(fnx.power(g, 1)) == _edge_set(g)


@pytest.mark.parametrize("seed", range(40))
def test_power_diameter_is_complete(seed):
    g, n = _graph(seed)
    if not fnx.is_connected(g) or n < 2:
        pytest.skip("disconnected / trivial")
    d = fnx.diameter(g)
    gd = fnx.power(g, d)
    # Every pair is within the diameter, so G^diameter is complete.
    assert gd.number_of_edges() == n * (n - 1) // 2


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_power_preserves_the_node_set(seed, k):
    """Edge-set assertions cannot see a dropped isolated node."""
    g, n = _graph(seed)
    gk = fnx.power(g, k)
    assert set(gk.nodes()) == set(g.nodes())
    assert gk.number_of_nodes() == n


def test_isolated_nodes_are_present_to_be_dropped():
    """Guards the test above: without isolated nodes it proves little."""
    with_isolated = 0
    for seed in range(40):
        g, _ = _graph(seed)
        if g.number_of_edges() and any(g.degree(v) == 0 for v in g):
            with_isolated += 1
    assert with_isolated >= 10, f"only {with_isolated} of 40 draws have an isolated node"


@pytest.mark.parametrize("seed", range(40))
def test_power_is_monotone_in_k(seed):
    """Distance <= k implies distance <= k+1, so the powers nest."""
    g, _ = _graph(seed)
    previous = _edge_set(fnx.power(g, 1))
    for k in (2, 3, 4):
        current = _edge_set(fnx.power(g, k))
        assert previous <= current
        previous = current


@pytest.mark.parametrize("seed", range(40))
def test_disconnected_power_is_complete_per_component(seed):
    """The invariant the connectivity skip discards: it holds componentwise."""
    g, _ = _graph(seed)
    if fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("connected or edgeless")

    components = [set(c) for c in fnx.connected_components(g)]
    for component in components:
        if len(component) < 2:
            continue
        diameter = fnx.diameter(g.subgraph(component).copy())
        powered = fnx.power(g, diameter)
        # Complete inside the component...
        for u in component:
            for v in component:
                if u != v:
                    assert powered.has_edge(u, v)
        # ...and no walk of any length leaves it.
        for other in components:
            if other is component:
                continue
            for u in component:
                for v in other:
                    assert not powered.has_edge(u, v)


@pytest.mark.parametrize("k", [0, -1, -5])
def test_nonpositive_k_is_rejected(k):
    g, _ = _graph(1)
    with pytest.raises(ValueError):
        fnx.power(g, k)


def test_directed_power_is_not_supported():
    d = fnx.DiGraph(); d.add_edges_from([(0, 1), (1, 2)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.power(d, 2)
