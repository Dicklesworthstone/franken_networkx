"""Metamorphic tests for distance / metric algebraic invariants.

Eighth metamorphic-equivalence module pairing with the seven already
in place. Covers textbook distance-metric identities that catch any
algorithm drift violating them on every input.

1. **Self-distance**: ``d(v, v) == 0`` for every node v.
2. **Symmetry on undirected**: ``d(u, v) == d(v, u)`` on undirected
   graphs.
3. **Triangle inequality**: ``d(u, w) ≤ d(u, v) + d(v, w)`` for every
   reachable triple (u, v, w).
4. **Diameter == max(eccentricity)**.
5. **Radius == min(eccentricity)**.
6. **Radius ≤ diameter ≤ 2·radius** — the standard radius/diameter
   inequality (the diameter is at most twice the radius because the
   center of the graph is within ``radius`` of every node).
7. **Eccentricity ≥ 0**: every node's eccentricity is non-negative.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx


CONNECTED_FIXTURES = [
    ("path_5", lambda: fnx.path_graph(5)),
    ("path_8", lambda: fnx.path_graph(8)),
    ("cycle_6", lambda: fnx.cycle_graph(6)),
    ("complete_4", lambda: fnx.complete_graph(4)),
    ("complete_5", lambda: fnx.complete_graph(5)),
    ("balanced_tree_2_3", lambda: fnx.balanced_tree(2, 3)),
    ("karate", lambda: fnx.karate_club_graph()),
]


def _all_pairs(g):
    """Materialise all-pairs shortest-path lengths into a nested dict."""
    return {src: dict(dists) for src, dists in fnx.all_pairs_shortest_path_length(g)}


# -----------------------------------------------------------------------------
# Distance metric axioms
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_self_distance_is_zero(name, builder):
    g = builder()
    apsl = _all_pairs(g)
    for v in g.nodes():
        d_vv = apsl[v].get(v)
        assert d_vv == 0, (
            f"{name}: d({v}, {v}) == {d_vv}, expected 0"
        )


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_distance_is_symmetric_on_undirected(name, builder):
    g = builder()
    apsl = _all_pairs(g)
    nodes = list(g.nodes())
    for u in nodes:
        for v in nodes:
            d_uv = apsl[u].get(v)
            d_vu = apsl[v].get(u)
            assert d_uv == d_vu, (
                f"{name}: distance asymmetric on undirected — "
                f"d({u}, {v}) = {d_uv} but d({v}, {u}) = {d_vu}"
            )


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_triangle_inequality(name, builder):
    g = builder()
    apsl = _all_pairs(g)
    nodes = list(g.nodes())
    # Sample 32 triples to keep the test fast on large fixtures.
    n = len(nodes)
    if n < 3:
        return
    triples = [
        (nodes[i % n], nodes[(i * 7 + 1) % n], nodes[(i * 13 + 5) % n])
        for i in range(min(n * n, 64))
    ]
    for u, v, w in triples:
        d_uw = apsl[u].get(w)
        d_uv = apsl[u].get(v)
        d_vw = apsl[v].get(w)
        if d_uw is None or d_uv is None or d_vw is None:
            continue
        assert d_uw <= d_uv + d_vw, (
            f"{name}: triangle inequality violated — "
            f"d({u},{w})={d_uw} > d({u},{v}) + d({v},{w}) = {d_uv} + {d_vw}"
        )


# -----------------------------------------------------------------------------
# Diameter / radius / eccentricity relations
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_diameter_equals_max_eccentricity(name, builder):
    g = builder()
    diam = fnx.diameter(g)
    ecc = fnx.eccentricity(g)
    expected = max(ecc.values())
    assert diam == expected, (
        f"{name}: diameter {diam} != max(eccentricity) {expected}"
    )


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_radius_equals_min_eccentricity(name, builder):
    g = builder()
    rad = fnx.radius(g)
    ecc = fnx.eccentricity(g)
    expected = min(ecc.values())
    assert rad == expected, (
        f"{name}: radius {rad} != min(eccentricity) {expected}"
    )


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_radius_diameter_inequality(name, builder):
    """Standard graph-theory bound: ``radius ≤ diameter ≤ 2 * radius``.

    The lower side follows from radius == min(eccentricity) and
    diameter == max(eccentricity). The upper side follows because the
    center of the graph (any node achieving the radius) is within
    ``radius`` of every other node, so the longest geodesic in the
    graph is at most ``2 * radius`` (going through the center).
    """
    g = builder()
    rad = fnx.radius(g)
    diam = fnx.diameter(g)
    assert rad <= diam, (
        f"{name}: radius {rad} > diameter {diam} (impossible)"
    )
    assert diam <= 2 * rad, (
        f"{name}: diameter {diam} > 2 * radius {2 * rad} "
        f"(violates the radius-diameter inequality)"
    )


@pytest.mark.parametrize(("name", "builder"), CONNECTED_FIXTURES)
def test_eccentricity_is_non_negative(name, builder):
    g = builder()
    ecc = fnx.eccentricity(g)
    for v, e in ecc.items():
        assert e >= 0, (
            f"{name}: eccentricity({v}) = {e} is negative"
        )
