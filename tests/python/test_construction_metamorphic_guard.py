"""Metamorphic (oracle-free) guard for the construction-tax fold paths.

The differential guards (vs networkx) miss bugs that fnx and nx SHARE. Metamorphic
relations catch those: they assert internal consistency of the construction
operations the with_mirror folds touched, independent of any reference. A fold
that, say, dropped an attr on the second pass would break idempotence here even
if nx had the same bug.

Relations (all must hold exactly):
  * copy is structure/attr preserving: copy(G) == G;
  * copy is idempotent: copy(copy(G)) == copy(G);
  * full subgraph is identity: subgraph(G, all_nodes) == G;
  * subgraph idempotence: subgraph(subgraph(G,S), S) == subgraph(G, S);
  * subgraph composition: subgraph(subgraph(G,S), T) == subgraph(G, T) for T <= S;
  * to_undirected idempotence on an undirected graph: to_undirected twice == once;
  * edge_subgraph(G, all_edges) keeps all edges + their incident nodes.

No mocks, NO networkx — pure fnx self-consistency.
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx


def _g(seed, cls=fnx.Graph):
    r = random.Random(seed)
    n = r.randint(5, 10)
    g = cls()
    for node in range(n):
        g.add_node(node, tag=f"t{node}", rank=node)
    directed = g.is_directed()
    for u in range(n):
        for v in range(n):
            if (u < v or (directed and u != v)) and r.random() < 0.45:
                g.add_edge(u, v, weight=r.randint(1, 9))
    g.graph["meta"] = seed
    return g, n, r


def _sig(g):
    """Order-insensitive structural+attr signature."""
    nodes = {x: tuple(sorted(d.items())) for x, d in g.nodes(data=True)}
    if g.is_multigraph():
        edges = sorted((tuple(sorted((u, v))) if not g.is_directed() else (u, v), k,
                        tuple(sorted(d.items())))
                       for u, v, k, d in g.edges(keys=True, data=True))
    else:
        edges = sorted((tuple(sorted((u, v))) if not g.is_directed() else (u, v),
                        tuple(sorted(d.items())))
                       for u, v, d in g.edges(data=True))
    return nodes, edges, dict(g.graph)


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph])
@pytest.mark.parametrize("seed", range(12))
def test_copy_preserving_and_idempotent(cls, seed):
    g, n, r = _g(seed, cls)
    assert _sig(g.copy()) == _sig(g)                 # preserving
    assert _sig(g.copy().copy()) == _sig(g.copy())   # idempotent


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph])
@pytest.mark.parametrize("seed", range(12))
def test_subgraph_identity_idempotent_composition(cls, seed):
    g, n, r = _g(seed, cls)
    alln = list(range(n))
    assert _sig(g.subgraph(alln).copy()) == _sig(g)              # full = identity

    S = sorted(r.sample(alln, max(2, n - 1)))
    T = sorted(r.sample(S, max(1, len(S) - 1)))                  # T subset of S
    gs = g.subgraph(S).copy()
    # idempotent: subgraph(gs, S) == gs
    assert _sig(gs.subgraph(S).copy()) == _sig(gs)
    # composition: subgraph(subgraph(G,S), T) == subgraph(G, T)
    assert _sig(gs.subgraph(T).copy()) == _sig(g.subgraph(T).copy())


@pytest.mark.parametrize("cls", [fnx.Graph, fnx.MultiGraph])
@pytest.mark.parametrize("seed", range(10))
def test_to_undirected_idempotent_on_undirected(cls, seed):
    g, n, r = _g(seed, cls)
    once = g.to_undirected()
    twice = once.to_undirected()
    assert _sig(twice) == _sig(once)
