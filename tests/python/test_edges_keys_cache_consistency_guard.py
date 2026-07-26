"""Cache-consistency guard for the edges(keys=True) read optimization (multigraphs).

MultiGraph/MultiDiGraph edges(keys=True) is served from edges_with_keys_cache,
keyed by (nodes_seq, edges_seq). It must invalidate on edge mutation or the keyed
view returns stale parallel-edge structure. This locks consistency without
depending on exact key VALUES (which need not survive a rebuild):

  * the keyed view's endpoint multiset == the plain edges() endpoint multiset;
  * len(edges(keys=True)) == number_of_edges();
  these hold after add-parallel-edge / second-parallel / remove / add-node+edge.

Completes the read-cache invalidation quartet (node_data_mirror, adjacency,
edges_with_data, edges_with_keys). No mocks: pure fnx self-consistency.
"""

from __future__ import annotations

import copy
import io
import pickle
import random

import pytest
import franken_networkx as fnx

_TYPES = [fnx.MultiGraph, fnx.MultiDiGraph]


def _build(cls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    g = cls()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and (g.is_directed() or u < v) and r.random() < 0.4:
                g.add_edge(u, v, weight=r.randint(1, 9))
    return g, n


def _endpoints(edge_iter, directed):
    def ep(u, v):
        return (u, v) if directed else tuple(sorted((u, v), key=str))
    return sorted(ep(e[0], e[1]) for e in edge_iter)


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_edges_keys_cache_reflects_mutations(cls, seed):
    g, n = _build(cls, seed)
    directed = g.is_directed()

    def check():
        keyed = _endpoints(g.edges(keys=True), directed)
        plain = _endpoints(g.edges(), directed)
        assert keyed == plain                               # keyed view consistent
        assert len(list(g.edges(keys=True))) == g.number_of_edges()

    _ = list(g.edges(keys=True))   # warm the cache
    check()

    g.add_edge(0, 1, weight=1)     # parallel edge
    check()
    g.add_edge(0, 1, weight=2)     # second parallel
    check()
    g.remove_edge(0, 1)            # drop one parallel
    check()
    g.add_node(n + 100)
    g.add_edge(n + 100, 0, weight=3)
    check()


@pytest.mark.parametrize("cls", _TYPES)
def test_direct_edge_view_reuses_private_keyed_materialization(cls):
    """br-r37-c1-c5zn8: warm direct iteration must not clone the edge list."""
    g = cls()
    g.add_edges_from(
        [
            ("u0", "v0", "k0"),
            ("u0", "v0", "k1"),
            ("u1", "v1", "k0"),
        ]
    )
    view = g.edges
    expected = list(g.edges(keys=True))

    assert list(view) == expected
    cache = vars(g)["_fnx_direct_multi_edge_iter_cache"]
    assert cache[0] == (g.nodes_seq, g.edges_seq)
    assert list(cache[1]) == expected

    # The direct view reuses its private list, but the callable public API
    # remains a fresh result that users may mutate without poisoning the cache.
    assert list(view) == expected
    assert vars(g)["_fnx_direct_multi_edge_iter_cache"] is cache
    public_result = g.edges(keys=True)
    assert public_result is not cache[1]
    public_result.clear()
    assert list(view) == expected


@pytest.mark.parametrize("cls", _TYPES)
def test_direct_edge_view_cache_invalidates_and_iterator_stays_fail_fast(cls):
    g = cls()
    g.add_edges_from(
        [
            ("u0", "v0", "k0"),
            ("u1", "v1", "k0"),
        ]
    )
    view = g.edges
    stale = iter(view)
    next(stale)
    old_cache = vars(g)["_fnx_direct_multi_edge_iter_cache"]

    g.add_edge("u0", "v0", key="k1")
    with pytest.raises(
        RuntimeError, match="dictionary changed size during iteration"
    ):
        next(stale)

    expected = list(g.edges(keys=True))
    assert list(view) == expected
    new_cache = vars(g)["_fnx_direct_multi_edge_iter_cache"]
    assert new_cache is not old_cache
    assert new_cache[0] == (g.nodes_seq, g.edges_seq)

    g.remove_edge("u0", "v0", key="k1")
    assert list(view) == list(g.edges(keys=True))
    assert vars(g)["_fnx_direct_multi_edge_iter_cache"] is not new_cache


@pytest.mark.parametrize("cls", _TYPES)
def test_direct_edge_view_cache_is_not_copied_or_used_for_private_storage(cls):
    g = cls()
    g.add_edge("u0", "v0", key="k0")
    view = g.edges
    expected = list(g.edges(keys=True))
    assert list(view) == expected
    assert "_fnx_direct_multi_edge_iter_cache" in vars(g)

    for other in (
        copy.copy(g),
        copy.deepcopy(g),
        pickle.Unpickler(io.BytesIO(pickle.dumps(g))).load(),
    ):
        assert "_fnx_direct_multi_edge_iter_cache" not in vars(other)
        assert list(other.edges) == list(g.edges)

    # Installing any NetworkX-private store after capturing the view must route
    # through the established generic path rather than the native-only cache.
    vars(g).pop("_fnx_direct_multi_edge_iter_cache")
    g._node = {"private": {}}
    if cls is fnx.MultiGraph:
        g._adj = {"private": {}}
    else:
        g._succ = {"private": {}}
        g._pred = {"private": {}}
    # Preserve the established captured-view result; this test is about
    # declining the native-only cache, not redefining private edge-view policy.
    assert list(view) == expected
    assert "_fnx_direct_multi_edge_iter_cache" not in vars(g)


@pytest.mark.parametrize("cls", _TYPES)
def test_direct_edge_view_subclasses_retain_generic_path(cls):
    class GraphSubclass(cls):
        pass

    g = GraphSubclass()
    g.add_edge("u0", "v0", key="k0")
    assert list(g.edges) == list(g.edges(keys=True))
    assert "_fnx_direct_multi_edge_iter_cache" not in vars(g)
