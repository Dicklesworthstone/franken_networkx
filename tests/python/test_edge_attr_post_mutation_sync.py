"""Regression tests for br-r37-c1-sjf4t.

Edge attribute mutations performed after edge creation — via
``G[u][v]['k'] = v`` or ``for u, v, attrs in G.edges(data=True):
attrs[k] = v`` — used to be invisible to Rust algorithm kernels because
``edge_py_attrs`` (the Python-side persistent dict store) and
``inner.AttrMap`` (Rust-side) are dual stores populated together at
edge creation but not kept in sync on mutation.

The architectural fix exposes a ``_fnx_sync_attrs_to_inner()`` method
on every PyGraph variant; both the Python wrapper layer and raw Rust
weighted bindings call it before invoking native algorithms. This file
verifies:

1. The raw Rust binding sees fresh data without requiring callers to
   remember an explicit sync call.
2. Public wrappers (``single_source_dijkstra_path_length``, etc.)
   produce correct weighted distances even when weights were assigned
   post-creation.
3. The fix works across all four graph types: Graph, DiGraph,
   MultiGraph, MultiDiGraph.
"""

from __future__ import annotations

import math

import pytest

import franken_networkx as fnx
import franken_networkx._fnx as raw

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# Direct sync-method verification
# ---------------------------------------------------------------------------


def test_sync_method_exposed_on_all_graph_types():
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        g = cls()
        assert hasattr(g, "_fnx_sync_attrs_to_inner"), cls.__name__
        # Should be a no-op on an empty graph.
        g._fnx_sync_attrs_to_inner()


def test_sync_propagates_post_creation_edge_mutation_undirected():
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g[0][1]["weight"] = 1.5
    g[1][2]["weight"] = 2.5

    distances = dict(raw.single_source_dijkstra_path_length(g, 0))
    assert distances == {0: 0.0, 1: 1.5, 2: 4.0}


def test_raw_weighted_path_length_sees_add_weighted_edges_from_attrs():
    g = fnx.Graph()
    g.add_weighted_edges_from([(0, 1, 5.5), (1, 2, 7.25)])

    assert raw.dijkstra_path_length(g, 0, 2) == pytest.approx(12.75)
    assert raw.bellman_ford_path_length(g, 0, 2) == pytest.approx(12.75)


def test_raw_dag_longest_path_length_sees_post_creation_attrs():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g[0][1]["weight"] = 3
    g[1][2]["weight"] = 4

    assert raw.dag_longest_path_length(g, "weight") == pytest.approx(7.0)


def test_sync_propagates_post_creation_edge_mutation_directed():
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g[0][1]["weight"] = 3.0
    g[1][2]["weight"] = 4.0

    g._fnx_sync_attrs_to_inner()

    after = dict(raw.single_source_dijkstra_path_length(g, 0))
    assert after == {0: 0.0, 1: 3.0, 2: 7.0}


def test_sync_propagates_post_creation_edge_mutation_multigraph():
    g = fnx.MultiGraph()
    k1 = g.add_edge(0, 1)
    k2 = g.add_edge(1, 2)
    g[0][1][k1]["weight"] = 5.0
    g[1][2][k2]["weight"] = 6.0

    g._fnx_sync_attrs_to_inner()

    after = dict(raw.single_source_dijkstra_path_length(g, 0))
    assert after == {0: 0.0, 1: 5.0, 2: 11.0}


def test_sync_propagates_post_creation_edge_mutation_multidigraph():
    g = fnx.MultiDiGraph()
    k1 = g.add_edge(0, 1)
    k2 = g.add_edge(1, 2)
    g[0][1][k1]["weight"] = 7.0
    g[1][2][k2]["weight"] = 8.0

    g._fnx_sync_attrs_to_inner()

    after = dict(raw.single_source_dijkstra_path_length(g, 0))
    assert after == {0: 0.0, 1: 7.0, 2: 15.0}


def test_sync_propagates_for_loop_mutation():
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    for u, v, attrs in g.edges(data=True):
        attrs["weight"] = 9.0 if (u, v) == ("a", "b") else 10.0

    g._fnx_sync_attrs_to_inner()

    after = dict(raw.single_source_dijkstra_path_length(g, "a"))
    assert after == {"a": 0.0, "b": 9.0, "c": 19.0}


def test_sync_is_idempotent():
    g = fnx.Graph()
    g.add_edge(0, 1, weight=1.5)
    g._fnx_sync_attrs_to_inner()
    g._fnx_sync_attrs_to_inner()
    g._fnx_sync_attrs_to_inner()
    after = dict(raw.single_source_dijkstra_path_length(g, 0))
    assert after == {0: 0.0, 1: 1.5}


def test_sync_handles_node_attr_mutation():
    g = fnx.Graph()
    g.add_node(0)
    g.add_node(1)
    g.nodes[0]["color"] = "red"
    g.nodes[1]["color"] = "blue"
    # Should not raise; node attrs are now visible to Rust kernels.
    g._fnx_sync_attrs_to_inner()
    assert g.nodes[0]["color"] == "red"
    assert g.nodes[1]["color"] == "blue"


# ---------------------------------------------------------------------------
# Public wrapper auto-sync verification
# ---------------------------------------------------------------------------


@needs_nx
def test_public_dijkstra_correct_under_post_mutation():
    """The public wrapper auto-syncs before calling Rust; it must match nx."""
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 3)
    g[0][1]["weight"] = 2.0
    g[1][2]["weight"] = 3.0
    g[2][3]["weight"] = 4.0

    fnx_dist = dict(fnx.single_source_dijkstra_path_length(g, 0))

    gx = nx.Graph()
    gx.add_edge(0, 1, weight=2.0)
    gx.add_edge(1, 2, weight=3.0)
    gx.add_edge(2, 3, weight=4.0)
    nx_dist = dict(nx.single_source_dijkstra_path_length(gx, 0))

    assert fnx_dist == nx_dist


@needs_nx
def test_public_bellman_ford_correct_under_post_mutation():
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g[0][1]["weight"] = 2.5
    g[1][2]["weight"] = 1.5

    fnx_dist = dict(fnx.single_source_bellman_ford_path_length(g, 0))

    gx = nx.Graph()
    gx.add_edge(0, 1, weight=2.5)
    gx.add_edge(1, 2, weight=1.5)
    nx_dist = dict(nx.single_source_bellman_ford_path_length(gx, 0))

    assert fnx_dist == nx_dist


@needs_nx
def test_public_floyd_warshall_correct_under_post_mutation():
    g = fnx.Graph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(0, 2)
    g[0][1]["weight"] = 1.0
    g[1][2]["weight"] = 2.0
    g[0][2]["weight"] = 5.0

    fnx_dist = dict(fnx.floyd_warshall(g))
    fnx_dist = {k: dict(v) for k, v in fnx_dist.items()}

    gx = nx.Graph()
    gx.add_edge(0, 1, weight=1.0)
    gx.add_edge(1, 2, weight=2.0)
    gx.add_edge(0, 2, weight=5.0)
    nx_dist = dict(nx.floyd_warshall(gx))
    nx_dist = {k: dict(v) for k, v in nx_dist.items()}

    for u in fnx_dist:
        for v in fnx_dist[u]:
            assert math.isclose(fnx_dist[u][v], nx_dist[u][v]), (
                f"({u},{v}): fnx={fnx_dist[u][v]} nx={nx_dist[u][v]}"
            )


def test_post_mutation_dijkstra_returns_float_not_hopcount():
    """Specific regression: hop-count was returned (int 1.0/2.0 instead of
    weighted floats) when AttrMap was stale.
    """
    g = fnx.Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g["a"]["b"]["weight"] = 7.7
    g["b"]["c"]["weight"] = 3.3

    dist = dict(fnx.single_source_dijkstra_path_length(g, "a"))
    assert dist["b"] == pytest.approx(7.7)
    assert dist["c"] == pytest.approx(11.0)
