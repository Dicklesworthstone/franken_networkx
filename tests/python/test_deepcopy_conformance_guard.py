"""Byte-exact + deep-semantics conformance guard for graph __deepcopy__.

The remaining construction-tax lever (br-r37-c1-n7gxs #2) would fold the deepcopy
paths (__deepcopy__, _native_to_directed_deepcopy) with a single-pass
deepcopy+AttrMap helper. That fold is NOT correct-by-construction — per-value
deepcopy differs from whole-dict deepcopy in memo sharing of nested objects — so
it needs this guard to land safely. This locks the deep semantics vs networkx:

  * deepcopy(G) reproduces node/edge/graph attrs exactly (values match nx);
  * source-independence: mutating the source after deepcopy leaves the copy
    unchanged (top-level);
  * DEEP independence: mutating a NESTED mutable attr (a list/dict inside an
    attr) in the source does NOT change the copy — this is what distinguishes
    deepcopy from a shallow copy, and what the fold must preserve.

No mocks: real fnx vs real networkx (copy.deepcopy).
"""

from __future__ import annotations

import copy
import random

import pytest
import networkx as nx
import franken_networkx as fnx

_TYPES = [
    (fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


def _build(fcls, ncls, seed):
    r = random.Random(seed)
    n = r.randint(4, 8)
    fg, ng = fcls(), ncls()
    for node in range(n):
        # Include a NESTED mutable attr to exercise deep semantics.
        fg.add_node(node, tag=f"t{node}", items=[node, node + 1])
        ng.add_node(node, tag=f"t{node}", items=[node, node + 1])
    directed = fg.is_directed()
    for u in range(n):
        for v in range(n):
            if (u < v or (directed and u != v)) and r.random() < 0.4:
                w = r.randint(1, 9)  # local: G[u][v]["weight"] is invalid on MultiGraph
                fg.add_edge(u, v, weight=w, meta={"k": u})
                ng.add_edge(u, v, weight=w, meta={"k": u})
    fg.graph["info"] = {"name": "g"}
    ng.graph["info"] = {"name": "g"}
    return fg, ng, n


def _node_attrs(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_deepcopy_attrs_match_networkx(fcls, ncls, seed):
    fg, ng, n = _build(fcls, ncls, seed)
    fc, nc = copy.deepcopy(fg), copy.deepcopy(ng)
    assert _node_attrs(fc) == _node_attrs(nc)
    assert dict(fc.graph) == dict(nc.graph)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_deepcopy_is_deeply_independent(fcls, ncls, seed):
    fg, ng, n = _build(fcls, ncls, seed)
    fc = copy.deepcopy(fg)
    before = _node_attrs(fc)
    # Mutate a NESTED attr in the source; a true deepcopy is unaffected.
    for node in list(fg.nodes()):
        fg.nodes[node]["items"].append(999)
        fg.nodes[node]["tag"] = "MUT"
        break
    fg.graph["info"]["name"] = "MUT"
    assert _node_attrs(fc) == before          # nested list + tag unchanged
    assert fc.graph["info"]["name"] == "g"     # nested graph attr unchanged
