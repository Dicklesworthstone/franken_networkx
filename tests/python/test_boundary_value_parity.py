"""Differential + golden parity for boundary VALUES.

``test_boundary_module_parity.py`` only checks submodule import parity.
This adds value-level coverage for ``node_boundary(G, nbunch1,
nbunch2=None)`` and ``edge_boundary(G, nbunch1, nbunch2=None, data=...,
default=...)``.

Locks fnx to upstream networkx across random undirected and directed
graphs (S-only and S,T forms, and ``edge_boundary``'s ``data`` /
``default`` parameters), hand-computed goldens, and degenerate inputs.

br-r37-c1-dhi0m
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, directed=False, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(6, 12)
    fnx_cls, nx_cls = (fnx.DiGraph, nx.DiGraph) if directed else (fnx.Graph, nx.Graph)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng, n


def _edge_key(edge):
    return (edge[0], edge[1])


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(50))
def test_node_boundary_matches_networkx(directed, seed):
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 13 + 1)
    s = set(rng.sample(range(n), rng.randint(1, n - 1)))
    assert set(fnx.node_boundary(fg, s)) == set(nx.node_boundary(ng, s))
    t = set(rng.sample(range(n), rng.randint(1, n - 1)))
    assert set(fnx.node_boundary(fg, s, t)) == set(nx.node_boundary(ng, s, t))


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(50))
def test_edge_boundary_matches_networkx(directed, seed):
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 17 + 5)
    s = set(rng.sample(range(n), rng.randint(1, n - 1)))
    assert {_edge_key(e) for e in fnx.edge_boundary(fg, s)} == {
        _edge_key(e) for e in nx.edge_boundary(ng, s)
    }
    t = set(rng.sample(range(n), rng.randint(1, n - 1)))
    assert {_edge_key(e) for e in fnx.edge_boundary(fg, s, t)} == {
        _edge_key(e) for e in nx.edge_boundary(ng, s, t)
    }


def test_edge_boundary_with_data_matches_networkx():
    fg = fnx.Graph()
    ng = nx.Graph()
    for g in (fg, ng):
        g.add_edge(0, 1, weight=5)
        g.add_edge(1, 2, weight=3)
        g.add_edge(2, 3)
    assert sorted(fnx.edge_boundary(fg, {0, 1}, data="weight", default=0)) == sorted(
        nx.edge_boundary(ng, {0, 1}, data="weight", default=0)
    )


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", range(40))
def test_edge_boundary_overlapping_sets_matches_networkx(directed, seed):
    # Regression for br-r37-c1-dhi0m: the native kernel computed the strict
    # boundary then filtered by nbunch2, dropping edges inside the s∩t overlap.
    fg, ng, n = _pair(seed, directed=directed)
    rng = random.Random(seed * 101 + 9)
    s = set(rng.sample(range(n), rng.randint(2, n - 1)))
    # Build t to deliberately overlap s.
    t = set(rng.sample(range(n), rng.randint(2, n - 1))) | set(
        rng.sample(sorted(s), rng.randint(1, len(s)))
    )
    assert not s.isdisjoint(t)
    assert {_edge_key(e) for e in fnx.edge_boundary(fg, s, t)} == {
        _edge_key(e) for e in nx.edge_boundary(ng, s, t)
    }


def test_edge_boundary_overlap_golden():
    # Path 0-1-2-3; s={0,1,2}, t={1,2,3} overlap on {1,2}.
    # nx counts (0,1),(1,2),(2,3) (one end in s, other in t). The strict-
    # boundary approach would wrongly drop (0,1) and (1,2).
    g = fnx.path_graph(4)
    ng = nx.path_graph(4)
    got = {(u, v) for u, v in fnx.edge_boundary(g, {0, 1, 2}, {1, 2, 3})}
    assert got == {(u, v) for u, v in nx.edge_boundary(ng, {0, 1, 2}, {1, 2, 3})}
    assert (0, 1) in got and (1, 2) in got


@pytest.mark.parametrize("directed", [False, True])
def test_edge_boundary_target_native_route_preserves_networkx_order(
    directed, monkeypatch
):
    fg, ng, _ = _pair(313, directed=directed, p=0.65)
    source = [0, 2, 4, 6, 8]
    target = [1, 3, 5, 7, 9, 11]
    calls = 0
    raw_edge_boundary = fnx._raw_edge_boundary

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return raw_edge_boundary(*args, **kwargs)

    monkeypatch.setattr(fnx, "_raw_edge_boundary", spy)

    assert list(fnx.edge_boundary(fg, source, target)) == list(
        nx.edge_boundary(ng, source, target)
    )
    assert calls == 1


def test_boundary_goldens():
    g = fnx.path_graph(4)  # 0-1-2-3
    assert set(fnx.node_boundary(g, {0, 1})) == {2}
    assert {(u, v) for u, v in fnx.edge_boundary(g, {0, 1})} == {(1, 2)}
    # restricting the target set away from the boundary yields nothing.
    assert list(fnx.node_boundary(g, {0}, {2, 3})) == []


def test_empty_set_boundary_matches_networkx():
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    assert list(fnx.node_boundary(fg, set())) == list(nx.node_boundary(ng, set()))
    assert list(fnx.edge_boundary(fg, set())) == list(nx.edge_boundary(ng, set()))
