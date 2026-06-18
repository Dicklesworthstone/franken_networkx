"""Golden parity for bfs/dfs missing-source error wording.

The native traversal bindings leaked a repr-quoted, always-"graph"
message (``The node 'x' is not in the graph.``) for a missing source.
networkx emits the unquoted ``The node x is not in the graph.`` for
undirected graphs and ``...is not in the digraph.`` for directed ones.

The wrappers re-raise lazily (inside the generator), matching nx's
lazy-raise contract; this test exercises the materialized generator to
trigger the raise. br-r37-c1-i7asy
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

_TRAVERSALS = [
    "dfs_edges",
    "bfs_edges",
    "dfs_tree",
    "dfs_predecessors",
    "dfs_successors",
    "dfs_preorder_nodes",
    "dfs_postorder_nodes",
    "bfs_predecessors",
    "bfs_successors",
]


@pytest.mark.parametrize("fn", _TRAVERSALS)
@pytest.mark.parametrize(
    "fnx_cls,nx_cls", [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
    ids=["undirected", "directed"],
)
def test_traversal_missing_source_matches_networkx(fn, fnx_cls, nx_cls):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXError) as fnx_exc:
        list(getattr(fnx, fn)(fg, "x"))
    with pytest.raises(nx.NetworkXError) as nx_exc:
        list(getattr(nx, fn)(ng, "x"))
    assert str(fnx_exc.value) == str(nx_exc.value)


def test_message_is_unquoted_and_kind_aware():
    with pytest.raises(nx.NetworkXError) as exc_u:
        list(fnx.dfs_edges(fnx.Graph([(0, 1)]), "x"))
    assert str(exc_u.value) == "The node x is not in the graph."
    with pytest.raises(nx.NetworkXError) as exc_d:
        list(fnx.dfs_edges(fnx.DiGraph([(0, 1)]), "x"))
    assert str(exc_d.value) == "The node x is not in the digraph."
    assert "'x'" not in str(exc_u.value)


def test_valid_traversal_unaffected():
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    assert list(fnx.dfs_edges(fg, 0)) == list(nx.dfs_edges(ng, 0))
    assert list(fnx.bfs_edges(fg, 0)) == list(nx.bfs_edges(ng, 0))
