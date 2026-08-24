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

    # The direct view reuses its private list, which stays an implementation
    # detail: the keyed no-argument call is the Mapping view itself.
    assert list(view) == expected
    assert vars(g)["_fnx_direct_multi_edge_iter_cache"] is cache
    public_result = g.edges(keys=True)
    assert public_result is view
    assert public_result is not cache[1]
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


@pytest.mark.parametrize("cls", _TYPES)
def test_captured_multiedge_key_view_cache_is_lazy_and_live(cls):
    """br-r37-c1-u4gjj: cache iteration, never cold len/membership or values."""
    g = cls()
    for index, key in enumerate(("k0", "k3", "k7")):
        g.add_edge("left", "right", key=key, weight=index)

    view = g["left"]["right"]
    assert type(view) is fnx.AtlasView
    assert view._fnx_multi_edge_owner is g
    assert view._fnx_kd_cache is None

    # Preserve the shipped native exact-size and lookup routes until a caller
    # actually requests key iteration.
    assert len(view) == 3
    assert "k3" in view
    assert "missing" not in view
    assert view._fnx_kd_cache is None

    iterator = iter(view)
    assert type(iterator).__name__ == "dict_keyiterator"
    assert list(iterator) == ["k0", "k3", "k7"]
    warm_cache = view._fnx_kd_cache
    assert warm_cache[0] == (g.nodes_seq, g.edges_seq)
    assert list(warm_cache[1]) == ["k0", "k3", "k7"]
    assert list(view) == ["k0", "k3", "k7"]
    assert view._fnx_kd_cache is warm_cache

    # The cached mapping is keys-only. Attribute values remain the canonical
    # live dicts returned by the graph and mutate through either reference.
    attrs = view["k3"]
    assert attrs is g.get_edge_data("left", "right", "k3")
    attrs["color"] = "blue"
    assert view["k3"]["color"] == "blue"

    g.add_edge("left", "right", key="k9", weight=9)
    assert list(view) == ["k0", "k3", "k7", "k9"]
    added_cache = view._fnx_kd_cache
    assert added_cache is not warm_cache
    assert added_cache[0] == (g.nodes_seq, g.edges_seq)

    g.remove_edge("left", "right", key="k3")
    assert list(view) == ["k0", "k7", "k9"]
    assert view._fnx_kd_cache is not added_cache


@pytest.mark.parametrize("cls", _TYPES)
def test_multiedge_key_view_cache_preserves_wrapper_identity_policy(cls):
    """Caching keys must not memoize the public AtlasView wrapper itself."""
    g = cls()
    g.add_edge("left", "right", key="k0")

    first = g["left"]["right"]
    second = g["left"]["right"]
    assert first is not second
    assert type(first) is type(second) is fnx.AtlasView
    assert list(first) == list(second) == ["k0"]


@pytest.mark.parametrize("cls", _TYPES)
def test_multiedge_key_view_private_storage_declines_native_cache(cls):
    g = cls()
    g.add_edge("left", "right", key="k0")
    view = g["left"]["right"]

    g._node = {"private": {}}
    if cls is fnx.MultiGraph:
        g._adj = {"private": {}}
    else:
        g._succ = {"private": {}}
        g._pred = {"private": {}}

    assert list(view) == ["k0"]
    assert view._fnx_kd_cache is None


@pytest.mark.parametrize("cls", _TYPES)
def test_multiedge_key_view_subclasses_retain_generic_iteration(cls):
    class GraphSubclass(cls):
        pass

    g = GraphSubclass()
    g.add_edge("left", "right", key="k0")
    view = g["left"]["right"]

    assert list(view) == ["k0"]
    assert view._fnx_kd_cache is None
