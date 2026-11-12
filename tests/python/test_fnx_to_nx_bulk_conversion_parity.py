"""Isomorphism for the bulk-native _fnx_to_nx parity conversion.

Bead br-r37-c1-xykjs (perf).

_fnx_to_nx now pulls the whole (node, [(neighbor, attrs)]) structure from a
single native fnx_to_nx_adjacency crossing (reading the fresh edge_py_attrs)
and feeds the unchanged Python topo-emit algorithm, instead of two per-edge
AtlasView passes. The converted nx graph must be byte-identical to one built
from the same add_node/add_edge sequence — same node order, per-node adjacency
order (critical for greedy_color BFS / ego_graph / traversal delegations),
node attrs, edge attrs, graph attrs, and directedness — including after
post-creation edge-attribute mutation.
"""

from __future__ import annotations

import random

import pytest

import franken_networkx as fnx
from franken_networkx.backend import _fnx_to_nx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _build_pair(directed, kind, seed):
    rng = random.Random(seed)
    n = rng.randint(0, 25)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg = fnx.DiGraph() if directed else fnx.Graph()
    gt = nx.DiGraph() if directed else nx.Graph()  # ground truth, same calls
    for u in nodes:
        if kind in ("nattr", "both"):
            fg.add_node(u, color=u % 3, tag=f"n{u}")
            gt.add_node(u, color=u % 3, tag=f"n{u}")
        else:
            fg.add_node(u)
            gt.add_node(u)
    seen = set()
    ecalls = []
    for _ in range(rng.randint(0, n * 2)):
        if not nodes:
            break
        a, b = rng.choice(nodes), rng.choice(nodes)
        if a == b:
            continue
        key = (a, b) if directed else tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        if kind in ("eattr", "both"):
            w = rng.choice([1, 2.5, 3])
            fg.add_edge(a, b, weight=w, lab=f"e{a}{b}")
            gt.add_edge(a, b, weight=w, lab=f"e{a}{b}")
        else:
            fg.add_edge(a, b)
            gt.add_edge(a, b)
        ecalls.append((a, b))
    if kind == "mutated":
        for a, b in ecalls:
            w = rng.choice([5, 7.5])
            fg[a][b]["weight"] = w
            gt[a][b]["weight"] = w
    if kind == "gattr":
        fg.graph["name"] = "X"
        fg.graph["k"] = 3
        gt.graph["name"] = "X"
        gt.graph["k"] = 3
    return fg, gt


def _assert_same(h, g):
    assert h.is_directed() == g.is_directed()
    assert list(h) == list(g)
    assert dict(h.graph) == dict(g.graph)
    for u in g:
        assert list(h.adj[u]) == list(g.adj[u]), f"adj order @ {u}"
        assert dict(h.nodes[u]) == dict(g.nodes[u])
        for v in g.adj[u]:
            assert dict(h[u][v]) == dict(g[u][v])


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize(
    "kind", ["plain", "eattr", "nattr", "both", "mutated", "gattr"]
)
@pytest.mark.parametrize("seed", list(range(25)))
def test_conversion_byte_identical(directed, kind, seed):
    fg, gt = _build_pair(directed, kind, seed * 131 + 5)
    _assert_same(_fnx_to_nx(fg), gt)


@needs_nx
@pytest.mark.parametrize("seed", list(range(20)))
def test_greedy_color_order_sensitive_delegation(seed):
    # greedy_color BFS strategies depend on the converted graph's adj order;
    # this exercises the delegation path end-to-end.
    rng = random.Random(seed * 17 + 1)
    n = rng.randint(3, 20)
    nodes = list(range(n))
    rng.shuffle(nodes)
    fg, gt = fnx.Graph(), nx.Graph()
    for u in nodes:
        fg.add_node(u)
        gt.add_node(u)
    seen = set()
    for _ in range(rng.randint(n, n * 2)):
        a, b = rng.sample(nodes, 2)
        k = tuple(sorted((a, b)))
        if k in seen:
            continue
        seen.add(k)
        fg.add_edge(a, b)
        gt.add_edge(a, b)
    for strat in ("largest_first", "connected_sequential_bfs",
                  "connected_sequential_dfs", "smallest_last"):
        assert fnx.greedy_color(fg, strategy=strat) == nx.greedy_color(gt, strategy=strat)


@needs_nx
@pytest.mark.parametrize("directed", [False, True])
def test_subgraph_view_conversion_honours_filter(directed):
    # SubgraphView (type is not the concrete Graph) must route to the Python
    # fallback so the view's node/edge filtering is honoured, not bypassed.
    fg = fnx.DiGraph() if directed else fnx.Graph()
    gt = nx.DiGraph() if directed else nx.Graph()
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (4, 1)]:
        fg.add_edge(a, b, weight=a + b)
        gt.add_edge(a, b, weight=a + b)
    keep = [0, 1, 2, 3]
    h = _fnx_to_nx(fg.subgraph(keep))
    g = gt.subgraph(keep)
    assert list(h) == list(g)
    for u in g:
        assert set(h.adj[u]) == set(g.adj[u])
        for v in g.adj[u]:
            assert dict(h[u][v]) == dict(g[u][v])
    assert 4 not in h


@needs_nx
def test_onion_layers_matches_networkx():
    rng = random.Random(99)
    fg, gt = fnx.Graph(), nx.Graph()
    for u, v in [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 0), (1, 4)]:
        fg.add_edge(u, v)
        gt.add_edge(u, v)
    assert fnx.onion_layers(fg) == nx.onion_layers(gt)
