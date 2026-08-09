"""Directed-graph reverse: involution + degree-swap invariants.

Reversing a digraph flips every arc. Its defining properties cross-check
reverse against the degree views and the SCC decomposition:
  - reverse swaps each arc (u, v) -> (v, u);
  - reverse is an involution: reverse(reverse(G)) == G;
  - reverse swaps in-degree and out-degree (in_degree of reverse == out_degree of G);
  - node and edge counts are unchanged;
  - the strongly connected components are preserved (reachability is symmetric
    under arc reversal).
Oracle-free, independent of networkx.

No mocks: real fnx.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _digraph(seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    edges = [(u, v) for u in range(n) for v in range(n) if u != v and r.random() < 0.35]
    g = fnx.DiGraph(edges)
    g.add_nodes_from(range(n))
    return g


def _edges(g):
    return sorted((u, v) for u, v in g.edges())


@pytest.mark.parametrize("seed", range(40))
def test_reverse_swaps_arcs_and_is_involution(seed):
    g = _digraph(seed)
    rev = fnx.reverse(g)
    # Each arc is flipped.
    assert _edges(rev) == sorted((v, u) for u, v in g.edges())
    # Reversing twice recovers the original.
    assert _edges(fnx.reverse(rev)) == _edges(g)
    # Counts unchanged.
    assert rev.number_of_nodes() == g.number_of_nodes()
    assert rev.number_of_edges() == g.number_of_edges()


@pytest.mark.parametrize("seed", range(40))
def test_reverse_swaps_degrees_and_preserves_sccs(seed):
    g = _digraph(seed)
    rev = fnx.reverse(g)
    # in-degree of the reverse equals out-degree of the original (and vice-versa).
    assert dict(rev.in_degree()) == dict(g.out_degree())
    assert dict(rev.out_degree()) == dict(g.in_degree())
    # Strongly connected components are invariant under reversal.
    scc_g = sorted(sorted(c) for c in fnx.strongly_connected_components(g))
    scc_r = sorted(sorted(c) for c in fnx.strongly_connected_components(rev))
    assert scc_g == scc_r


def test_reverse_carries_the_attributes_across():
    """The arc set is pinned above; what rides on the arcs was not."""
    g = fnx.DiGraph()
    g.add_node(0, colour="red")
    g.add_node(1, colour="blue")
    g.add_edge(0, 1, weight=5, label="a")
    g.add_edge(1, 2, weight=2)
    g.graph["name"] = "probe"

    rev = fnx.reverse(g)
    assert dict(rev.nodes(data=True)) == dict(g.nodes(data=True))
    assert rev.graph == g.graph
    # The attributes follow the arc to its flipped position.
    assert rev.edges[1, 0] == g.edges[0, 1]
    assert rev.edges[2, 1] == g.edges[1, 2]

    # The attribute dicts are independent, so writing through one does not
    # reach the other (networkx behaves the same way).
    rev.edges[1, 0]["weight"] = 99
    assert g.edges[0, 1]["weight"] == 5


def test_reverse_copy_false_is_a_live_view():
    """copy=False and copy=True differ in kind, not just in cost."""
    g = fnx.DiGraph([(0, 1), (1, 2)])

    view = g.reverse(copy=False)
    assert view.has_edge(1, 0) and view.has_edge(2, 1)
    # A view reflects later changes to its parent...
    g.add_edge(2, 3)
    assert view.has_edge(3, 2)
    # ...and refuses to be edited directly.
    with pytest.raises(fnx.NetworkXError):
        view.add_edge(9, 8)

    # A copy is a snapshot: later parent edits do not reach it.
    snapshot = g.reverse(copy=True)
    g.add_edge(3, 4)
    assert not snapshot.has_edge(4, 3)


def test_self_loops_survive_reversal():
    """The random generator excludes u == v, so loops were never exercised."""
    g = fnx.DiGraph([(0, 0), (0, 1)])
    rev = fnx.reverse(g)
    assert rev.has_edge(0, 0)                 # a loop reversed is itself
    assert _edges(rev) == [(0, 0), (1, 0)]
    assert rev.in_degree(0) == g.out_degree(0)


def test_multidigraph_reverse_preserves_keys_and_attributes():
    """Parallel arcs keep their identity through the flip."""
    m = fnx.MultiDiGraph()
    m.add_edge(0, 1, key="k1", weight=3)
    m.add_edge(0, 1, key="k2")
    m.add_edge(1, 2)

    rev = fnx.reverse(m)
    assert rev.number_of_edges() == m.number_of_edges()
    assert sorted((u, v, str(k)) for u, v, k in rev.edges(keys=True)) == [
        (1, 0, "k1"), (1, 0, "k2"), (2, 1, "0"),
    ]
    assert rev.edges[1, 0, "k1"] == m.edges[0, 1, "k1"]
    # Still an involution once keys are in play.
    assert sorted((u, v, str(k)) for u, v, k in fnx.reverse(rev).edges(keys=True)) == sorted(
        (u, v, str(k)) for u, v, k in m.edges(keys=True)
    )
