"""Differential + golden parity for the distance-measures family.

Covers ``eccentricity``, ``diameter``, ``radius``, ``center``,
``periphery`` and ``barycenter`` — the eccentricity-derived graph
invariants. None had a dedicated test file.

This locks fnx against the real upstream networkx with:

* differential parity across random connected graphs — undirected and
  (strongly-connected) directed, unweighted and weighted,
* hand-computed goldens (path, cycle, star, complete graphs), and
* the disconnected-graph ``NetworkXError`` contract.

Set-valued results (``center``, ``periphery``, ``barycenter``) are
compared as sets; the scalar/dict results are compared exactly (with a
float tolerance for the weighted cases).

br-r37-c1-8k1rt
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _connected_pair(seed, directed=False, weighted=False, p=0.45):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fnx_cls, nx_cls = (
        (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    )
    for _ in range(300):
        fg = fnx_cls()
        ng = nx_cls()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u == v:
                    continue
                if (directed or u < v) and rng.random() < p:
                    if weighted:
                        w = round(rng.uniform(1, 5), 2)
                        fg.add_edge(u, v, weight=w)
                        ng.add_edge(u, v, weight=w)
                    else:
                        fg.add_edge(u, v)
                        ng.add_edge(u, v)
        connected = (
            nx.is_strongly_connected(ng) if directed else nx.is_connected(ng)
        )
        if connected:
            return fg, ng, n
        p = min(0.95, p + 0.03)
    return None


# ---------------------------------------------------------------------------
# Differential parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_distance_measures_match_networkx(directed, weighted, seed):
    pair = _connected_pair(seed, directed=directed, weighted=weighted)
    if pair is None:
        pytest.skip("could not sample a connected graph")
    fg, ng, _ = pair
    kwargs = {"weight": "weight"} if weighted else {}

    fecc = fnx.eccentricity(fg, **kwargs)
    necc = nx.eccentricity(ng, **kwargs)
    assert set(fecc) == set(necc)
    for k in necc:
        assert fecc[k] == pytest.approx(necc[k], abs=1e-9)

    assert fnx.diameter(fg, **kwargs) == pytest.approx(nx.diameter(ng, **kwargs), abs=1e-9)
    assert fnx.radius(fg, **kwargs) == pytest.approx(nx.radius(ng, **kwargs), abs=1e-9)
    assert set(fnx.center(fg, **kwargs)) == set(nx.center(ng, **kwargs))
    assert set(fnx.periphery(fg, **kwargs)) == set(nx.periphery(ng, **kwargs))


@pytest.mark.parametrize("weighted", [False, True])
@pytest.mark.parametrize("seed", range(30))
def test_barycenter_matches_networkx(weighted, seed):
    pair = _connected_pair(seed, directed=False, weighted=weighted)
    if pair is None:
        pytest.skip("could not sample a connected graph")
    fg, ng, _ = pair
    kwargs = {"weight": "weight"} if weighted else {}
    assert set(fnx.barycenter(fg, **kwargs)) == set(nx.barycenter(ng, **kwargs))


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_path_graph_goldens():
    p5 = fnx.path_graph(5)
    assert fnx.diameter(p5) == 4
    assert fnx.radius(p5) == 2
    assert set(fnx.center(p5)) == {2}
    assert set(fnx.periphery(p5)) == {0, 4}


def test_cycle_and_complete_goldens():
    assert fnx.diameter(fnx.cycle_graph(6)) == 3
    assert fnx.diameter(fnx.complete_graph(5)) == 1
    assert fnx.radius(fnx.complete_graph(5)) == 1


def test_star_graph_goldens():
    s4 = fnx.star_graph(4)  # center 0 with 4 leaves
    assert fnx.diameter(s4) == 2
    assert fnx.radius(s4) == 1
    assert set(fnx.center(s4)) == {0}


# ---------------------------------------------------------------------------
# Disconnected error contract.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", ["diameter", "radius"])
def test_distance_measures_reject_disconnected_like_networkx(fn):
    fg = fnx.Graph([(0, 1)])
    fg.add_node(2)
    ng = nx.Graph([(0, 1)])
    ng.add_node(2)
    with pytest.raises(nx.NetworkXError):
        getattr(fnx, fn)(fg)
    with pytest.raises(nx.NetworkXError):
        getattr(nx, fn)(ng)
