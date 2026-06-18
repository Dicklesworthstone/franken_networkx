"""Lazy-materialization stress guard for DIRECTED fully-lazy folds.

Companion to test_lazy_materialization_stress_guard.py (which covers Graph).
CrimsonRiver is folding the DiGraph/MultiDiGraph construction family (copy,
reverse, subgraph, to_undirected) in digraph.rs toward the fully-lazy pattern
(drop the Rust AttrMap, materialize from the Python mirror on demand,
br-r37-c1-n7gxs #1). The directed types have extra Rust-AttrMap consumers
(in_degree/out_degree(weight), reverse's arc-flipped attrs) that a fold could
leave empty. This forces materialization through every access path after a
directed lazy-fold construction and checks each vs networkx.

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

np = pytest.importorskip("numpy")

_TYPES = [(fnx.DiGraph, nx.DiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)]
_BUILDERS = ["copy", "reverse", "to_undirected", "subgraph"]


def _build(fcls, ncls, seed):
    r = random.Random(seed)
    n = r.randint(5, 9)
    fg, ng = fcls(), ncls()
    for node in range(n):
        fg.add_node(node, tag=f"t{node}")
        ng.add_node(node, tag=f"t{node}")
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.3:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    return fg, ng, n


def _apply(builder, g, n, seed):
    if builder == "copy":
        return g.copy()
    if builder == "reverse":
        return g.reverse()
    if builder == "to_undirected":
        return g.to_undirected()
    if builder == "subgraph":
        keep = sorted(random.Random(seed).sample(range(n), max(2, n - 1)))
        return g.subgraph(keep).copy()
    raise AssertionError(builder)


def _edge_attrs(g):
    if g.is_multigraph():
        return sorted(((u, v), k, tuple(sorted(d.items())))
                      for u, v, k, d in g.edges(keys=True, data=True))
    return sorted(((u, v), tuple(sorted(d.items()))) for u, v, d in g.edges(data=True))


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("builder", _BUILDERS)
@pytest.mark.parametrize("seed", range(10))
def test_directed_attr_access_paths_agree_after_lazy_build(fcls, ncls, builder, seed):
    fg, ng, n = _build(fcls, ncls, seed)
    fb = _apply(builder, fg, n, seed)
    nb = _apply(builder, ng, n, seed)

    # get_edge_data must materialize identical weights.
    for u, v in nb.edges():
        assert fb.get_edge_data(u, v) == nb.get_edge_data(u, v)
    assert _edge_attrs(fb) == _edge_attrs(nb)
    assert {x: dict(d) for x, d in fb.nodes(data=True)} == {
        x: dict(d) for x, d in nb.nodes(data=True)
    }
    # NATIVE consumers reading the Rust AttrMap (directed-specific where applicable).
    assert fb.size(weight="weight") == nb.size(weight="weight")
    if fb.is_directed() and nb.is_directed():
        assert dict(fb.in_degree(weight="weight")) == dict(nb.in_degree(weight="weight"))
        assert dict(fb.out_degree(weight="weight")) == dict(nb.out_degree(weight="weight"))
    fnodes, nnodes = sorted(fb.nodes()), sorted(nb.nodes())
    assert fnodes == nnodes
    fa = fnx.to_numpy_array(fb, nodelist=fnodes, weight="weight")
    na = nx.to_numpy_array(nb, nodelist=nnodes, weight="weight")
    assert np.array_equal(fa, na)
