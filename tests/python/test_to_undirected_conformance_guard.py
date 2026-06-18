"""Byte-exact conformance guard for to_undirected (DiGraph/MultiDiGraph -> undirected).

This LOCKS the observable semantics of to_undirected so the planned lazy-AttrMap
optimization (drop the eager per-node/per-edge ``py_dict_to_attr_map`` crossing in
crates/fnx-python/src/digraph.rs::to_undirected, ~O(V+E) redundant PyO3 work — see
the filed perf bead) can be applied later WITHOUT changing behavior. The subtle
part nx specifies and fnx must preserve:

  * node and edge attributes survive the round (values + identity-independence);
  * for a reciprocal pair a<->b the LATER-processed direction's edge attrs win
    (dict.update semantics in canonical node->successor order);
  * graph-level attrs are carried over;
  * mutating the result does not mutate the source (deep enough copy).

Differential against networkx 3.x: same node/edge/attr structure both ways.

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _both(directed_cls_f, directed_cls_n, seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    fg = directed_cls_f()
    ng = directed_cls_n()
    for node in range(n):
        fg.add_node(node, color=f"c{node}", size=node)
        ng.add_node(node, color=f"c{node}", size=node)
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.35:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w, dir=f"{u}->{v}")
                ng.add_edge(u, v, weight=w, dir=f"{u}->{v}")
    fg.graph["meta"] = "g"
    ng.graph["meta"] = "g"
    return fg, ng


def _edge_attr_map(g):
    return {tuple(sorted((u, v))): dict(d) for u, v, d in g.edges(data=True)}


@pytest.mark.parametrize("seed", range(40))
def test_digraph_to_undirected_matches_networkx(seed):
    fg, ng = _both(fnx.DiGraph, nx.DiGraph, seed)
    fu = fg.to_undirected()
    nu = ng.to_undirected()

    assert sorted(fu.nodes()) == sorted(nu.nodes())
    assert {n: dict(d) for n, d in fu.nodes(data=True)} == {
        n: dict(d) for n, d in nu.nodes(data=True)
    }
    assert sorted(map(tuple, map(sorted, fu.edges()))) == sorted(
        map(tuple, map(sorted, nu.edges()))
    )
    # Reciprocal-merge winner must match nx (later direction wins).
    assert _edge_attr_map(fu) == _edge_attr_map(nu)
    assert dict(fu.graph) == dict(nu.graph)


@pytest.mark.parametrize("seed", range(20))
def test_to_undirected_result_is_independent_of_source(seed):
    fg, _ = _both(fnx.DiGraph, nx.DiGraph, seed)
    fu = fg.to_undirected()
    # Mutate the source after the round; the result must not change.
    before = _edge_attr_map(fu)
    for u, v in list(fg.edges()):
        fg[u][v]["weight"] = -999
    fg.add_edge(100, 101)
    assert _edge_attr_map(fu) == before
    assert (100, 101) not in set(map(tuple, map(sorted, fu.edges())))


def test_reciprocal_edge_later_direction_wins():
    # a<->b with conflicting attrs: nx keeps the later-processed direction.
    fg = fnx.DiGraph()
    fg.add_edge(0, 1, label="forward")
    fg.add_edge(1, 0, label="backward")
    ng = nx.DiGraph()
    ng.add_edge(0, 1, label="forward")
    ng.add_edge(1, 0, label="backward")
    assert fg.to_undirected()[0][1]["label"] == ng.to_undirected()[0][1]["label"]
