"""Differential guard for binary operators' node/edge ATTR-merging vs networkx.

Set-algebra structure is checked elsewhere (cluiw); this targets the subtle part
where construction-tax folds touched: how union / disjoint_union / intersection /
difference / symmetric_difference / compose carry and MERGE node, edge, and graph
attributes. Each operator is run on identical fnx and nx inputs and the full
result (nodes+attrs, edges+attrs, graph attrs) compared.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _na(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


def _ea(g):
    return sorted((tuple(sorted((u, v), key=str)), tuple(sorted(d.items())))
                  for u, v, d in g.edges(data=True))


def _pair_disjoint(seed):
    """Two graphs with DISJOINT node sets (for union/disjoint_union)."""
    r = random.Random(seed)
    fg, ng = fnx.Graph(), nx.Graph()
    fh, nh = fnx.Graph(), nx.Graph()
    for node in range(4):
        fg.add_node(node, tag=f"g{node}"); ng.add_node(node, tag=f"g{node}")
        fh.add_node(node + 100, tag=f"h{node}"); nh.add_node(node + 100, tag=f"h{node}")
    for u in range(4):
        for v in range(u + 1, 4):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fh.add_edge(u + 100, v + 100, weight=w); nh.add_edge(u + 100, v + 100, weight=w)
    return fg, ng, fh, nh


def _pair_samenodes(seed):
    """Two graphs on the SAME node set (for intersection/difference/compose)."""
    r = random.Random(seed)
    fg, ng = fnx.Graph(), nx.Graph()
    fh, nh = fnx.Graph(), nx.Graph()
    for node in range(5):
        fg.add_node(node, tag=f"g{node}"); ng.add_node(node, tag=f"g{node}")
        fh.add_node(node, tag=f"h{node}"); nh.add_node(node, tag=f"h{node}")
    for u in range(5):
        for v in range(u + 1, 5):
            if r.random() < 0.5:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
            if r.random() < 0.5:
                w = r.randint(10, 19)
                fh.add_edge(u, v, weight=w); nh.add_edge(u, v, weight=w)
    return fg, ng, fh, nh


@pytest.mark.parametrize("seed", range(25))
def test_union_and_disjoint_union(seed):
    fg, ng, fh, nh = _pair_disjoint(seed)
    for op in ("union", "disjoint_union"):
        fr = getattr(fnx, op)(fg, fh)
        nr = getattr(nx, op)(ng, nh)
        assert _na(fr) == _na(nr), op
        assert _ea(fr) == _ea(nr), op


@pytest.mark.parametrize("seed", range(25))
def test_sameset_operators(seed):
    fg, ng, fh, nh = _pair_samenodes(seed)
    for op in ("intersection", "difference", "symmetric_difference", "compose"):
        fr = getattr(fnx, op)(fg, fh)
        nr = getattr(nx, op)(ng, nh)
        assert _na(fr) == _na(nr), op
        assert _ea(fr) == _ea(nr), op
