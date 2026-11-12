"""Cache-consistency guard for the node_data_mirror read optimization.

nodes(data=...) is served from a seq-keyed node_data_mirror cache (the read-side
perf win that closed the ~3.8x nodes(data) gap for all four graph types). A bug in
the seq-keyed invalidation would silently serve STALE node data after a mutation.
This locks cache consistency: after every mutation kind, nodes(data=True) must
reflect the current state (and match a fresh graph built to that state).

Mutations exercised between cache reads:
  * add a node with attrs;
  * set/overwrite a node attr (g.nodes[n][k] = v);
  * remove a node;
  * add a node then remove it (seq churn).

No mocks: pure fnx self-consistency (the cache vs the live graph).
"""

from __future__ import annotations

import random

import pytest
import franken_networkx as fnx

_TYPES = [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph]


def _build(cls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    g = cls()
    for node in range(n):
        g.add_node(node, tag=f"t{node}", v=node)
    return g, n


def _snapshot(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


@pytest.mark.parametrize("cls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_nodes_data_reflects_mutations(cls, seed):
    g, n = _build(cls, seed)

    # Warm the cache.
    first = _snapshot(g)
    assert first == {i: {"tag": f"t{i}", "v": i} for i in range(n)}

    # 1) add a node with attrs -> cache must invalidate.
    g.add_node("X", tag="tx", v=-1)
    s = _snapshot(g)
    assert s["X"] == {"tag": "tx", "v": -1}
    assert len(s) == n + 1

    # 2) overwrite a node attr -> reflected.
    g.nodes[0]["v"] = 999
    assert _snapshot(g)[0]["v"] == 999

    # 3) remove a node -> gone from nodes(data).
    g.remove_node(1)
    s = _snapshot(g)
    assert 1 not in s
    assert len(s) == n  # added X, removed 1

    # 4) add+remove churn -> final state consistent.
    g.add_node("Y", tag="ty")
    g.remove_node("Y")
    s = _snapshot(g)
    assert "Y" not in s
    # Cross-check: a freshly built graph at the same node/attr state agrees.
    fresh = cls()
    for node, d in s.items():
        fresh.add_node(node, **d)
    assert _snapshot(fresh) == s
