"""Closeness / harmonic centrality identities (centrality <-> distances).

On a connected graph these centralities are defined directly from the shortest-
path distances, so they cross-check all_pairs_shortest_path_length:
  - closeness(v) = (n - 1) / sum_u d(v, u);
  - harmonic(v) = sum_{u != v} 1 / d(v, u);
  - closeness(v) <= 1 (maximised when v is adjacent to every other node).
Oracle-free, independent of networkx.

"On a connected graph" is the interesting part of that sentence: the sweep below
skips 10 of its 40 draws for being disconnected, and disconnectedness is exactly
where these two functions stop agreeing with the simple formulas. Closeness then
uses only the nodes REACHABLE from v, and by default scales by the fraction of
the graph that is reachable (the Wasserman-Faust correction, wf_improved=True) —
a parameter that makes no difference on a connected graph and so was never
exercised. Harmonic needs no correction, since an unreachable node contributes
1/inf = 0. All three are pinned below, still oracle-free.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    g = fnx.Graph(); g.add_nodes_from(range(n)); g.add_edges_from(edges)
    return g, n


@pytest.mark.parametrize("seed", range(40))
def test_closeness_and_harmonic_from_distances(seed):
    g, n = _connected(seed)
    if not fnx.is_connected(g) or g.number_of_edges() == 0:
        pytest.skip("disconnected / empty")
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    clo = fnx.closeness_centrality(g)
    har = fnx.harmonic_centrality(g)
    for v in g:
        distsum = sum(apsp[v][u] for u in g if u != v)
        assert distsum > 0
        assert abs(clo[v] - (n - 1) / distsum) < 1e-6
        expected_har = sum(1 / apsp[v][u] for u in g if u != v)
        assert abs(har[v] - expected_har) < 1e-6
        assert clo[v] <= 1 + 1e-9


def _disconnected_seeds(limit=200):
    """Seeds whose draw is disconnected, so the sweep below skips nothing.

    Parametrising over range(limit) and skipping would report ~150 skips and
    bury the 47 cases that actually run.
    """
    out = []
    for seed in range(limit):
        g, _ = _connected(seed)
        if g.number_of_edges() and not fnx.is_connected(g):
            out.append(seed)
    return out


DISCONNECTED_SEEDS = _disconnected_seeds()


@pytest.mark.parametrize("seed", DISCONNECTED_SEEDS)
def test_disconnected_uses_only_reachable_nodes(seed):
    """The case the sweep above skips: closeness over the reachable set only.

    closeness(v)     = (R / sum_reachable d) * (R / (n - 1))   [wf_improved=True]
    closeness(v)     =  R / sum_reachable d                    [wf_improved=False]
    harmonic(v)      = sum over REACHABLE of 1 / d             [unreachable -> 0]

    where R is the number of nodes reachable from v, excluding v itself.
    """
    g, n = _connected(seed)
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    scaled = fnx.closeness_centrality(g)
    unscaled = fnx.closeness_centrality(g, wf_improved=False)
    har = fnx.harmonic_centrality(g)

    for v in g:
        reachable = {u: d for u, d in apsp[v].items() if u != v}
        count = len(reachable)
        if count == 0:                       # isolated node: nothing to be close to
            assert scaled[v] == 0 and unscaled[v] == 0 and har[v] == 0
            continue
        total = sum(reachable.values())
        assert abs(unscaled[v] - count / total) < 1e-9
        assert abs(scaled[v] - (count / total) * (count / (n - 1))) < 1e-9
        assert abs(har[v] - sum(1 / d for d in reachable.values())) < 1e-9
        # The correction only ever shrinks the value, and matches when connected.
        assert scaled[v] <= unscaled[v] + 1e-12


def test_wf_correction_is_the_identity_on_connected_graphs():
    """Guards the parameter's meaning: it is a no-op exactly when R == n-1."""
    g = fnx.path_graph(6)
    assert fnx.is_connected(g)
    scaled = fnx.closeness_centrality(g)
    unscaled = fnx.closeness_centrality(g, wf_improved=False)
    assert all(abs(scaled[v] - unscaled[v]) < 1e-12 for v in g)

    # ...and genuinely differs once the graph splits, so the guard is not vacuous.
    h = fnx.Graph(); h.add_edges_from([(0, 1), (1, 2), (3, 4)])
    assert fnx.closeness_centrality(h) != fnx.closeness_centrality(h, wf_improved=False)


def test_star_center_has_maximal_closeness():
    # In a star, the center is distance 1 from all leaves -> closeness 1;
    # a leaf is distance 1 to center and 2 to other leaves.
    g = fnx.star_graph(5)  # center 0, leaves 1..5
    clo = fnx.closeness_centrality(g)
    assert abs(clo[0] - 1.0) < 1e-9
    assert clo[0] == max(clo.values())
    # Harmonic of the center = number of leaves (all at distance 1).
    har = fnx.harmonic_centrality(g)
    assert abs(har[0] - 5) < 1e-9


def test_complete_graph_all_closeness_one():
    for n in (3, 4, 5):
        clo = fnx.closeness_centrality(fnx.complete_graph(n))
        assert all(abs(c - 1.0) < 1e-9 for c in clo.values())
