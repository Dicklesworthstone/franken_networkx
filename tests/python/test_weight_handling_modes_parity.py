"""Weight-argument handling parity across modes.

networkx accepts the ``weight`` argument in several forms — a string key, a
callable ``f(u, v, data)``, ``None`` (unit weights), a missing key (defaults to
1), and graphs where only some edges carry the attribute. Each is a distinct
code path that fnx must reproduce. This pins fnx == networkx across all of them.

No mocks: real fnx and real networkx on identically-built graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _weighted(seed, attr="weight"):
    r = random.Random(seed)
    n = r.randint(6, 9)
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, **{attr: w}, cost=w * 2)
                ng.add_edge(u, v, **{attr: w}, cost=w * 2)
    return fg, ng, n


@pytest.mark.parametrize("seed", range(30))
def test_callable_weight(seed):
    fg, ng, n = _weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    wf = lambda u, v, d: d.get("cost", 1)  # noqa: E731
    assert fnx.betweenness_centrality(fg, weight=wf) == (
        nx.betweenness_centrality(ng, weight=wf)
    )
    assert sorted(fnx.minimum_spanning_tree(fg, weight=wf).edges()) == (
        sorted(nx.minimum_spanning_tree(ng, weight=wf).edges())
    )
    r = random.Random(seed + 1)
    s, t = r.sample(range(n), 2)
    assert fnx.dijkstra_path_length(fg, s, t, weight=wf) == (
        nx.dijkstra_path_length(ng, s, t, weight=wf)
    )


@pytest.mark.parametrize("seed", range(30))
def test_weight_none_and_missing_key(seed):
    fg, ng, n = _weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    r = random.Random(seed + 2)
    s, t = r.sample(range(n), 2)
    # weight=None → unit weights (hop count).
    assert fnx.shortest_path_length(fg, s, t, weight=None) == (
        nx.shortest_path_length(ng, s, t, weight=None)
    )
    # Missing key → networkx defaults to 1 for every edge.
    assert fnx.dijkstra_path_length(fg, s, t, weight="absent") == (
        nx.dijkstra_path_length(ng, s, t, weight="absent")
    )


@pytest.mark.parametrize("seed", range(30))
def test_partial_weight_attribute(seed):
    """Only some edges carry 'weight'; networkx defaults the rest to 1."""
    r = random.Random(seed + 100)
    n = r.randint(6, 9)
    fg = fnx.Graph(); fg.add_nodes_from(range(n))
    ng = nx.Graph(); ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if r.random() < 0.5:
                if r.random() < 0.5:
                    w = r.randint(1, 9)
                    fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
                else:
                    fg.add_edge(u, v); ng.add_edge(u, v)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    assert dict(fnx.all_pairs_dijkstra_path_length(fg, weight="weight")) == (
        dict(nx.all_pairs_dijkstra_path_length(ng, weight="weight"))
    )
    assert dict(fg.degree(weight="weight")) == dict(ng.degree(weight="weight"))


# br-r37-c1-upxos: `weight=None` was only exercised on shortest_path_length.
# It is networkx's DEFAULT for the whole dijkstra and betweenness family, and
# the None branch is a distinct code path (a non-str weight argument routes
# differently — cf. br-r37-c1-nonstr-kwarg-delegation), so it needs covering on
# each consumer rather than once. Verified equal across all 30 seeds first.
@pytest.mark.parametrize("seed", range(30))
def test_weight_none_across_the_family(seed):
    fg, ng, n = _weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    r = random.Random(seed + 3)
    s, t = r.sample(range(n), 2)
    assert fnx.dijkstra_path_length(fg, s, t, weight=None) == (
        nx.dijkstra_path_length(ng, s, t, weight=None)
    )
    assert fnx.dijkstra_path(fg, s, t, weight=None) == (
        nx.dijkstra_path(ng, s, t, weight=None)
    )
    assert list(fnx.minimum_spanning_tree(fg, weight=None).edges()) == (
        list(nx.minimum_spanning_tree(ng, weight=None).edges())
    )
    # betweenness is compared with a tolerance, matching the convention in
    # test_centrality_conformance_matrix._assert_centrality_close: the Brandes
    # accumulation is a float sum whose ORDER differs, so exact equality fails
    # by one ULP (2.776e-17) on 3 of these 30 seeds. That is summation order,
    # not a semantic divergence — but it is why the exact `==` used for the
    # callable-weight case above is fragile rather than strict.
    got = fnx.betweenness_centrality(fg, weight=None)
    want = nx.betweenness_centrality(ng, weight=None)
    assert list(got.keys()) == list(want.keys())
    for key in want:
        assert got[key] == pytest.approx(want[key], rel=1e-6, abs=1e-9)


# br-r37-c1-upxos: the bead names shortest_path and all_pairs, and only their
# LENGTHS were checked. A path's SEQUENCE is where a weight-mode tie-break
# divergence would actually show — two routes of equal total weight make the
# length agree while the chosen path differs.
@pytest.mark.parametrize("seed", range(30))
def test_weight_mode_path_sequences(seed):
    fg, ng, n = _weighted(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    r = random.Random(seed + 4)
    s, t = r.sample(range(n), 2)
    wf = lambda u, v, d: d.get("cost", 1)  # noqa: E731
    assert fnx.dijkstra_path(fg, s, t, weight=wf) == nx.dijkstra_path(ng, s, t, weight=wf)
    assert fnx.dijkstra_path(fg, s, t, weight="absent") == (
        nx.dijkstra_path(ng, s, t, weight="absent")
    )
    assert fnx.shortest_path(fg, s, t, weight="weight") == (
        nx.shortest_path(ng, s, t, weight="weight")
    )
    # MST edge ORDER, not just the sorted edge set the callable test compares.
    assert list(fnx.minimum_spanning_tree(fg, weight=wf).edges()) == (
        list(nx.minimum_spanning_tree(ng, weight=wf).edges())
    )
    # Key order of the weighted maps.
    assert list(dict(fg.degree(weight="weight")).keys()) == (
        list(dict(ng.degree(weight="weight")).keys())
    )
