"""Parity for Dijkstra shortest-path dict KEY ORDER under equal-distance ties.

Bead br-r37-c1-k9q6q.

networkx yields the per-source dicts from ``single_source_dijkstra*`` and
``all_pairs_dijkstra*`` in **finalize (heap-pop) order** — i.e. sorted by
``(distance, heap-push-seq)``. fnx previously reconstructed this order in the
Python layer using a **BFS-from-source hop order** as the tie-break, which
diverges from nx whenever several nodes share a distance but were pushed onto
the Dijkstra heap in a different order than plain BFS would visit them.

Example: a weighted graph where three nodes sit at distance 3. BFS hop order
and Dijkstra finalize order disagree, so the old fnx returned e.g. ``[3, 1, 5]``
where nx returns ``[3, 5, 1]``.

The fix has the Rust kernel emit entries in finalize order and the Python
wrappers trust that order (stable sort by distance preserves the push-seq
tie-break). These tests pin the *key order* — not merely the values — to nx
across directed and undirected graphs. Graphs are built from an identical edge
sequence so adjacency-insertion order (which drives the tie-break) matches.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _witness(lib):
    """A graph where BFS-hop order != Dijkstra finalize order at distance 3."""
    g = lib.Graph()
    edges = [
        (5, 0, 1), (0, 1, 1), (4, 7, 1), (7, 1, 2), (1, 5, 2), (3, 1, 1),
        (5, 2, 1), (7, 0, 2), (4, 1, 3), (3, 6, 3), (7, 2, 1), (0, 6, 2),
    ]
    for u, v, w in edges:
        g.add_edge(u, v, weight=float(w))
    return g


@needs_nx
def test_witness_single_source_key_order():
    f, n = _witness(fnx), _witness(nx)
    fo = list(fnx.single_source_dijkstra_path_length(f, 6, weight="weight").keys())
    no = list(nx.single_source_dijkstra_path_length(n, 6, weight="weight").keys())
    assert fo == no, f"fnx={fo} nx={no}"


@needs_nx
def test_witness_path_key_order():
    f, n = _witness(fnx), _witness(nx)
    fo = list(fnx.single_source_dijkstra_path(f, 6, weight="weight").keys())
    no = list(nx.single_source_dijkstra_path(n, 6, weight="weight").keys())
    assert fo == no


def _build(lib, edges, directed):
    g = lib.DiGraph() if directed else lib.Graph()
    for u, v, w in edges:
        g.add_edge(u, v, weight=w)
    return g


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(40)))
def test_random_single_source_key_order(directed, seed):
    rng = random.Random(seed * 17 + (5 if directed else 2))
    n = rng.randint(3, 10)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg = fnx.DiGraph() if directed else fnx.Graph()
    ng = nx.DiGraph() if directed else nx.Graph()
    for u in nodes:
        fg.add_node(u)
        ng.add_node(u)
    seen = set()
    target = rng.randint(0, n * (n - 1) // (1 if directed else 2))
    tries = 0
    while ng.number_of_edges() < target and tries < target * 5 + 10:
        tries += 1
        u, v = rng.sample(nodes, 2)
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        w = float(rng.choice([1, 1, 2, 2, 3]))
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    for s in nodes:
        fp = fnx.single_source_dijkstra_path(fg, s, weight="weight")
        npp = nx.single_source_dijkstra_path(ng, s, weight="weight")
        assert list(fp.keys()) == list(npp.keys()), f"d={directed} seed={seed} s={s}"
        assert dict(fp) == dict(npp)
        fl = fnx.single_source_dijkstra_path_length(fg, s, weight="weight")
        nl = nx.single_source_dijkstra_path_length(ng, s, weight="weight")
        assert list(fl.keys()) == list(nl.keys())


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("seed", list(range(25)))
def test_random_all_pairs_key_order(directed, seed):
    rng = random.Random(seed * 13 + (9 if directed else 4))
    n = rng.randint(3, 9)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg = fnx.DiGraph() if directed else fnx.Graph()
    ng = nx.DiGraph() if directed else nx.Graph()
    for u in nodes:
        fg.add_node(u)
        ng.add_node(u)
    seen = set()
    target = rng.randint(0, n * 2)
    tries = 0
    while ng.number_of_edges() < target and tries < target * 5 + 10:
        tries += 1
        u, v = rng.sample(nodes, 2)
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            continue
        seen.add(key)
        w = float(rng.choice([1, 1, 2, 3]))
        fg.add_edge(u, v, weight=w)
        ng.add_edge(u, v, weight=w)
    # all_pairs_dijkstra_path
    fap = dict(fnx.all_pairs_dijkstra_path(fg, weight="weight"))
    nap = dict(nx.all_pairs_dijkstra_path(ng, weight="weight"))
    assert list(fap.keys()) == list(nap.keys())
    for s in nap:
        assert list(fap[s].keys()) == list(nap[s].keys()), f"path d={directed} seed={seed} s={s}"
        assert dict(fap[s]) == dict(nap[s])
    # all_pairs_dijkstra_path_length
    fal = dict(fnx.all_pairs_dijkstra_path_length(fg, weight="weight"))
    nal = dict(nx.all_pairs_dijkstra_path_length(ng, weight="weight"))
    assert list(fal.keys()) == list(nal.keys())
    for s in nal:
        assert list(fal[s].keys()) == list(nal[s].keys()), f"len d={directed} seed={seed} s={s}"
    # all_pairs_dijkstra (tuple)
    fat = dict(fnx.all_pairs_dijkstra(fg, weight="weight"))
    nat = dict(nx.all_pairs_dijkstra(ng, weight="weight"))
    assert list(fat.keys()) == list(nat.keys())
    for s in nat:
        assert list(fat[s][0].keys()) == list(nat[s][0].keys())
        assert list(fat[s][1].keys()) == list(nat[s][1].keys())
