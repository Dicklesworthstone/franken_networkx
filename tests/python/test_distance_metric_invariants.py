"""Distance-metric cross-function invariants on connected graphs.

The distance functions are mutually constrained by definition, so they
cross-check each other:
  - radius <= diameter <= 2 * radius;
  - radius = min eccentricity, diameter = max eccentricity;
  - center = {v : ecc(v) = radius}, periphery = {v : ecc(v) = diameter};
  - eccentricity(v) = max over u of dist(v, u);
  - wiener_index = (sum of all-pairs distances) / 2.
A bug in any one of eccentricity/radius/diameter/center/periphery/
all_pairs_shortest_path_length/wiener_index breaks at least one identity.
networkx parity on eccentricity is also checked.

No mocks: real fnx and real networkx on connected graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected(seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if r.random() < 0.4]
    fg = fnx.Graph(); fg.add_nodes_from(range(n)); fg.add_edges_from(edges)
    ng = nx.Graph(); ng.add_nodes_from(range(n)); ng.add_edges_from(edges)
    return fg, ng


@pytest.mark.parametrize("seed", range(40))
def test_eccentricity_radius_diameter_center_periphery(seed):
    fg, ng = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    ecc = fnx.eccentricity(fg)
    radius = fnx.radius(fg)
    diameter = fnx.diameter(fg)

    assert radius <= diameter <= 2 * radius
    assert radius == min(ecc.values())
    assert diameter == max(ecc.values())
    assert set(fnx.center(fg)) == {v for v, e in ecc.items() if e == radius}
    assert set(fnx.periphery(fg)) == {v for v, e in ecc.items() if e == diameter}
    assert ecc == nx.eccentricity(ng)


@pytest.mark.parametrize("seed", range(40))
def test_eccentricity_equals_max_distance_and_wiener(seed):
    fg, ng = _connected(seed)
    if not fnx.is_connected(fg):
        pytest.skip("disconnected")
    ecc = fnx.eccentricity(fg)
    apsp = dict(fnx.all_pairs_shortest_path_length(fg))

    # eccentricity(v) is the greatest distance from v to any node.
    for v in fg:
        assert ecc[v] == max(apsp[v].values())

    # Wiener index is half the sum of all ordered-pair distances.
    total = sum(d for v in apsp for d in apsp[v].values())
    assert fnx.wiener_index(fg) == total / 2


def test_triangle_inequality_on_distance_matrix():
    # The shortest-path distance is a metric: d(a,c) <= d(a,b) + d(b,c).
    g = fnx.cycle_graph(8)
    apsp = dict(fnx.all_pairs_shortest_path_length(g))
    nodes = list(g)
    for a in nodes:
        for b in nodes:
            for c in nodes:
                assert apsp[a][c] <= apsp[a][b] + apsp[b][c]
