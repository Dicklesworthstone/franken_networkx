"""Lock for br-r37-c1-w2zqe — edge_subgraph/restricted_view read only their rows.

The NON-default-edge-filter branch of the filtered view's ``_edges`` built the
whole parent adjacency (``dict(_native_adjacency_keys())``) and then indexed a
handful of rows out of it. networkx is O(rows asked for), so the ratio degraded
without bound as the parent grew: 0.2078x at N=500 down to 0.0004x at N=32000,
where fnx spent 28.9 ms against networkx's 11 us.

br-r37-c1-thssf fixed the DEFAULT-edge-filter branch of the same routine, used by
``subgraph()``. This is its sibling, used by ``edge_subgraph()`` and
``restricted_view()``. Fixing one branch and not the other is the
partially-applied-fix trap that bead was written about, so the lock below takes
PARENT SIZE as a parameter: at a single size an O(V+E) read and an O(rows) read
return exactly the same answer, which is why no correctness test caught either.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
SIZES = [60, 400, 2000]


_EDGE_SUBGRAPH_ORDER_PROGRAM = """
import json
import networkx as nx
import franken_networkx as fnx

edges = [
    ('n165', 'n274'),
    ('n24', 'n202'),
    ('n77', 'n165'),
    ('n77', 'n274'),
    ('n37', 'n24'),
]
out = []
for graph_type in (nx.DiGraph, fnx.DiGraph):
    graph = graph_type()
    graph.add_edges_from(edges)
    graph.add_nodes_from(f'n{i}' for i in range(500))
    out.append(list(graph.edge_subgraph(edges).edges()))
print(json.dumps(out))
"""


def _canon(edges, graph):
    """Unordered, orientation-normalised edge comparison.

    SEQUENCE is deliberately not compared. networkx's own edge_subgraph order is
    a function of PYTHONHASHSEED -- pinning the seed makes fnx and networkx agree
    exactly, and 3 of 4 unpinned seeds make them differ -- so a sequence
    assertion here would be flaky for a reason that has nothing to do with this
    fix. That order difference is pre-existing (reproduced on HEAD without this
    change) and is filed separately; pinning it here would only hide it behind a
    red test that fails at random.
    """
    out = []
    for edge in edges:
        u, v = str(edge[0]), str(edge[1])
        out.append((u, v) if graph.is_directed() else tuple(sorted((u, v))))
    return sorted(out)


def _build(lib, cls_name, n, seed=11):
    rng = random.Random(seed)
    graph = getattr(lib, cls_name)()
    names = [f"n{i}" for i in range(n)]
    graph.add_nodes_from(names)
    for _ in range(n * 3):
        graph.add_edge(names[rng.randrange(n)], names[rng.randrange(n)], w=1)
    graph.add_edge(names[0], names[0], w=2)  # self-loop
    if graph.is_multigraph():
        graph.add_edge(names[1], names[2], w=3)  # parallel edge
        graph.add_edge(names[1], names[2], w=4)
    return graph, names


def _edge_seed(graph, names, count=6):
    """A deterministic edge list, taken from the graph itself.

    Multigraph ``edge_subgraph`` selects by (u, v, KEY) -- handing it bare
    (u, v) pairs silently selects something else, which is a bug in the test
    rather than in the code and cost me two rounds here.
    """
    edges = graph.edges(keys=True) if graph.is_multigraph() else graph.edges()
    out = []
    for edge in edges:
        out.append(tuple(edge))
        if len(out) >= count:
            break
    return out


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("n", SIZES)
def test_edge_subgraph_edges_match_networkx_at_every_parent_size(cls_name, n):
    gnx, names = _build(nx, cls_name, n)
    gfx, _ = _build(fnx, cls_name, n)
    seed_edges = _edge_seed(gnx, names)
    a = _canon(gnx.edge_subgraph(seed_edges).edges(), gnx)
    b = _canon(gfx.edge_subgraph(seed_edges).edges(), gfx)
    assert b == a


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("n", SIZES)
def test_edge_subgraph_edges_data_match_networkx(cls_name, n):
    gnx, names = _build(nx, cls_name, n)
    gfx, _ = _build(fnx, cls_name, n)
    seed_edges = _edge_seed(gnx, names)
    def shape(graph):
        out = []
        for u, v, d in graph.edge_subgraph(seed_edges).edges(data=True):
            ends = (str(u), str(v)) if graph.is_directed() else tuple(
                sorted((str(u), str(v)))
            )
            out.append(ends + (tuple(sorted(d.items())),))
        return sorted(out)

    assert shape(gfx) == shape(gnx)


@pytest.mark.parametrize("hashseed", ["0", "1", "7", "42"])
def test_directed_edge_subgraph_edge_sequence_matches_networkx_across_hash_seeds(
    hashseed,
):
    """The selected-node set must be built in NetworkX's two-set sequence.

    The sparse FilterAtlas path iterates that set directly.  A single seed is
    insufficient because the old one-set construction agreed at 0/1 yet
    diverged at 7/42.
    """
    run = subprocess.run(
        [sys.executable, "-c", _EDGE_SUBGRAPH_ORDER_PROGRAM],
        env={**os.environ, "PYTHONHASHSEED": hashseed},
        capture_output=True,
        check=False,
        text=True,
    )
    assert run.returncode == 0, run.stderr
    expected, actual = json.loads(run.stdout)
    assert actual == expected, f"edge sequence diverged at PYTHONHASHSEED={hashseed}"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("n", SIZES)
def test_restricted_view_edges_match_networkx(cls_name, n):
    """restricted_view shares the same branch."""
    gnx, names = _build(nx, cls_name, n)
    gfx, _ = _build(fnx, cls_name, n)
    hidden = names[:3]
    a = _canon(nx.restricted_view(gnx, hidden, []).edges(), gnx)
    b = _canon(fnx.restricted_view(gfx, hidden, []).edges(), gfx)
    assert b == a


@pytest.mark.parametrize("cls_name", CLASSES)
def test_edge_attribute_dicts_are_the_live_ones(cls_name):
    """data=True used to merge a live row over a snapshot; it now reads the row.

    The values must still be the parent's LIVE attr dicts, not copies, or a
    write through the view would stop reaching the graph.
    """
    gfx, names = _build(fnx, cls_name, 60)
    seed_edges = _edge_seed(gfx, names)
    view = gfx.edge_subgraph(seed_edges)
    marked = 0
    for edge in list(view.edges(data=True))[:3]:
        u, v, data = edge[0], edge[1], edge[-1]
        data["marker"] = 99
        if gfx.is_multigraph():
            assert any(d.get("marker") == 99 for d in gfx[u][v].values()), (u, v)
        else:
            assert gfx[u][v].get("marker") == 99, (u, v)
        marked += 1
    assert marked, "no edges to check"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_view_is_live_after_parent_mutation(cls_name):
    gnx, names = _build(nx, cls_name, 60)
    gfx, _ = _build(fnx, cls_name, 60)
    seed_edges = _edge_seed(gnx, names)
    vnx, vfx = gnx.edge_subgraph(seed_edges), gfx.edge_subgraph(seed_edges)
    first = seed_edges[0]
    for graph in (gnx, gfx):
        graph.remove_edge(*first)  # (u, v) or (u, v, key) for a multigraph
    assert _canon(vfx.edges(), gfx) == _canon(vnx.edges(), gnx)


@pytest.mark.parametrize("n", SIZES)
def test_the_row_accessor_equals_the_whole_graph_snapshot(n):
    """The assumption the substitution rests on, pinned directly.

    ``_native_successor_row_dict(u)`` replaced ``dict(_native_adjacency_keys())[u]``
    and ``_native_adjacency_dict()[u]``. If those ever disagree on key ORDER or
    VALUES this must fail loudly here rather than silently through edges().
    """
    graph, _ = _build(fnx, "DiGraph", n)
    whole_keys = dict(graph._native_adjacency_keys())
    whole_adj = graph._native_adjacency_dict()
    for node in graph:
        row = graph._native_successor_row_dict(node)
        assert list(row) == list(whole_keys[node]), node
        assert list(row) == list(whole_adj[node]), node
        for target in row:
            assert dict(row[target]) == dict(whole_adj[node][target]), (node, target)
