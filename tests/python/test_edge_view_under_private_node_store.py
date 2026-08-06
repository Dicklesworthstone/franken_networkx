"""`G.edges()` must read the adjacency, not the node view.

br-r37-c1-ka7fd. Assigning ``G._node = {...}`` makes the node view report the
assigned mapping while ``_adj`` keeps the native rows. networkx's ``EdgeView``
iterates ``_adj`` and never consults ``_node``, so the edges held in ``_adj``
come back regardless. fnx iterated the NODE list and then indexed the adjacency
with each node, which raised ``KeyError`` for a node that exists only in the
assigned mapping:

    fnx  list(g.edges())  -> KeyError: 'private'
    nx   list(g.edges())  -> [('a', 'b')]

Two separate defects produced that, and the multigraph one hid behind the first:
the edge view's node-sourced iteration, and ``MultiAdjacencyView.__getitem__``
gating membership on the NODE view so ``adj['a']`` raised for a node with a real
adjacency row.

Every expectation is taken from live networkx on the same input.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

_CLASS_PAIRS = [
    pytest.param(nx.Graph, fnx.Graph, id="Graph"),
    pytest.param(nx.DiGraph, fnx.DiGraph, id="DiGraph"),
    pytest.param(nx.MultiGraph, fnx.MultiGraph, id="MultiGraph"),
    pytest.param(nx.MultiDiGraph, fnx.MultiDiGraph, id="MultiDiGraph"),
]


def _build(cls):
    graph = cls()
    graph.add_edge("a", "b")
    graph.add_node("native")
    graph._node = {"private": {"tag": 1}}
    return graph


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_edges_match_networkx_under_an_assigned_node_store(nx_cls, fnx_cls):
    expected = sorted(map(str, _build(nx_cls).edges()))
    actual = sorted(map(str, _build(fnx_cls).edges()))
    assert actual == expected


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_edges_with_data_match_networkx_under_an_assigned_node_store(nx_cls, fnx_cls):
    expected = list(_build(nx_cls).edges(data=True))
    actual = list(_build(fnx_cls).edges(data=True))
    assert len(actual) == len(expected)
    assert sorted((u, v) for u, v, _ in actual) == sorted(
        (u, v) for u, v, _ in expected
    )


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_node_view_still_reports_the_assigned_mapping(nx_cls, fnx_cls):
    """The node half must NOT change — only the edge half was wrong."""
    assert list(_build(fnx_cls)) == list(_build(nx_cls)) == ["private"]
    assert len(_build(fnx_cls)) == len(_build(nx_cls)) == 1


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_adjacency_lookup_of_a_real_row_does_not_raise(nx_cls, fnx_cls):
    """The multigraph half: `adj['a']` must work for a node with a real row.

    `MultiAdjacencyView.__getitem__` gated on node-view membership, so it raised
    for 'a' — which has an adjacency row — merely because 'a' was absent from
    the assigned mapping. That turned `edges()` silently empty once the outer
    KeyError was guarded, which is worse than the crash.
    """
    fnx_graph = _build(fnx_cls)
    nx_graph = _build(nx_cls)

    assert sorted(fnx_graph.adj) == sorted(nx_graph.adj)
    assert sorted(fnx_graph.adj["a"]) == sorted(nx_graph.adj["a"])


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_adjacency_lookup_of_an_absent_node_still_raises(nx_cls, fnx_cls):
    """Loosening the gate must not stop `G.adj[missing]` raising."""
    for graph in (_build(nx_cls), _build(fnx_cls)):
        with pytest.raises(KeyError):
            graph.adj["definitely-not-a-node"]


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
def test_ordinary_graphs_are_untouched(nx_cls, fnx_cls):
    """No override: edge content and ORDER must match nx exactly.

    The fix changed which mapping the edge view iterates, so the thing most at
    risk is edge order on a normal graph. Asserted as an ordered sequence, not
    a set.
    """
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    nx_graph, fnx_graph = nx_cls(), fnx_cls()
    nx_graph.add_edges_from(edges)
    fnx_graph.add_edges_from(edges)

    assert list(fnx_graph.edges()) == list(nx_graph.edges())
    assert list(fnx_graph.nodes()) == list(nx_graph.nodes())
    assert [sorted(map(str, e)) for e in fnx_graph.edges(data=True)] == [
        sorted(map(str, e)) for e in nx_graph.edges(data=True)
    ]


_NBUNCH_SHAPES = [
    pytest.param("a", id="scalar-with-row"),
    pytest.param("private", id="scalar-without-row"),
    pytest.param("ghost", id="scalar-unknown"),
    pytest.param(["a", "private"], id="list-mixed"),
    pytest.param(["a", "b"], id="list-both-with-rows"),
]


@pytest.mark.parametrize("nx_cls, fnx_cls", _CLASS_PAIRS)
@pytest.mark.parametrize("nbunch", _NBUNCH_SHAPES)
def test_edges_nbunch_matches_networkx(nx_cls, fnx_cls, nbunch):
    """br-r37-c1-wzypa: the explicit-nbunch path, including its ASYMMETRY.

    This test previously asserted only that the path "still runs", as a
    placeholder while the divergence was tracked separately. That bead is fixed,
    so it now asserts real parity rather than a contract that has moved.

    networkx's nbunch handling is deliberately asymmetric and all of it is
    pinned here — a scalar is matched against the NODE view and returned
    unfiltered (so a node with no adjacency row RAISES), while an iterable is
    filtered against the ADJACENCY (so the same node is silently skipped):

        edges('a')             -> [('a','b')]
        edges('private')       -> KeyError
        edges('ghost')         -> []            (nx iterates the string)
        edges(['a','private']) -> [('a','b')]
    """

    def run(cls):
        graph = _build(cls)
        try:
            return sorted(map(str, graph.edges(nbunch)))
        except Exception as exc:  # noqa: BLE001 - the exception TYPE is the contract
            return type(exc).__name__

    assert run(fnx_cls) == run(nx_cls)
