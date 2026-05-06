"""Pickle / deepcopy parity locks for the public view classes.

br-r37-c1-viewpkl: ``AtlasView`` / ``AdjacencyView`` /
``MultiAdjacencyView`` stored a ``_atlas_getter`` lambda closure that
captured a graph descriptor reference. Pickle cannot serialize lambdas
or local functions, so ``pickle.dumps(M.adj[0])`` and
``pickle.dumps(M.adj)`` raised ``AttributeError: Can't get local
object 'MultiAdjacencyView.__getitem__.<locals>.<lambda>'``.

nx's matching views snapshot to a plain dict (live-tracking is lost,
since the graph descriptor can't survive pickling anyway) but
preserve the wrapping view TYPE on the restored side. Match that
contract exactly so users serializing graphs through caching layers
(joblib, dask, multiprocessing) don't crash on adjacency-view access.

Companion to br-r37-c1-cip5m which fixed the same defect class on
``_LiveMultiEdgeDataView``.
"""

from __future__ import annotations

import copy
import pickle

import franken_networkx as fnx
import networkx as nx
import pytest


GRAPH_BUILDERS = [
    ("Graph", lambda m: m.Graph([(0, 1, {"w": 1}), (1, 2, {"w": 2})])),
    ("DiGraph", lambda m: m.DiGraph([(0, 1, {"w": 1}), (1, 2, {"w": 2})])),
    ("MultiGraph", lambda m: m.MultiGraph(
        [(0, 1, {"w": 1}), (0, 1, {"w": 2}), (1, 2, {"w": 3})])),
    ("MultiDiGraph", lambda m: m.MultiDiGraph(
        [(0, 1, {"w": 1}), (0, 1, {"w": 2}), (1, 2, {"w": 3})])),
]


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_view_pickle_roundtrips(name, builder):
    """``G.adj`` (AdjacencyView or MultiAdjacencyView) must round-trip
    pickle. Snapshot semantics (no live-tracking after restore) match
    nx; the view type is preserved across the roundtrip."""
    G = builder(fnx)
    G_n = builder(nx)
    restored = pickle.loads(pickle.dumps(G.adj))
    restored_n = pickle.loads(pickle.dumps(G_n.adj))
    assert type(restored).__name__ == type(restored_n).__name__
    # Compare via nested dict equality.
    def _flat(view):
        return {u: dict(view[u]) for u in view}
    assert _flat(restored) == _flat(restored_n)


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_node_view_pickle_roundtrips(name, builder):
    """``G.adj[node]`` (AtlasView for simple graphs, AdjacencyView for
    multigraphs) must round-trip pickle."""
    G = builder(fnx)
    G_n = builder(nx)
    av_f = G.adj[0]
    av_n = G_n.adj[0]
    restored = pickle.loads(pickle.dumps(av_f))
    restored_n = pickle.loads(pickle.dumps(av_n))
    assert type(restored).__name__ == type(restored_n).__name__
    assert dict(restored) == dict(restored_n) or {
        k: dict(v) for k, v in dict(restored).items()
    } == {k: dict(v) for k, v in dict(restored_n).items()}


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_view_deepcopy_roundtrips(name, builder):
    """``copy.deepcopy`` uses the same protocol surface as pickle; lock
    parity here so a future change to ``__reduce__`` doesn't break
    deepcopy on adjacency views."""
    G = builder(fnx)
    av = G.adj[0]
    deepc = copy.deepcopy(av)
    assert type(deepc).__name__ == type(av).__name__
    assert dict(deepc) == dict(av) or {
        k: dict(v) for k, v in dict(deepc).items()
    } == {k: dict(v) for k, v in dict(av).items()}


@pytest.mark.parametrize("name,builder", GRAPH_BUILDERS, ids=[b[0] for b in GRAPH_BUILDERS])
def test_adj_view_pickle_loses_live_tracking_like_nx(name, builder):
    """Restored views are snapshots — mutating the original graph after
    pickle does NOT propagate to the restored view. nx behaves the same
    way; the live graph descriptor reference can't survive pickling."""
    G = builder(fnx)
    av = G.adj[0]
    restored = pickle.loads(pickle.dumps(av))
    initial_keys = set(restored)
    if G.is_multigraph():
        G.add_edge(0, 1, key="newkey", w=99)
    else:
        G.add_edge(0, 99, w=99)
    # Restored view's keys should NOT include the new edge target.
    assert set(restored) == initial_keys


def test_adj_view_repickle_roundtrips():
    """A restored view must itself be re-picklable. Originally the
    fix could regress here if the reconstructor produced a view that
    again held an unpicklable closure."""
    M = fnx.MultiGraph([(0, 1, {"w": 1}), (0, 1, {"w": 2})])
    av = M.adj[0]
    once = pickle.loads(pickle.dumps(av))
    twice = pickle.loads(pickle.dumps(once))
    assert dict(twice) == dict(once)
