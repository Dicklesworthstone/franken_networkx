"""Differential lock for br-r37-c1-native-relabel-attr-roundtrip-u3vvm.

`relabel_nodes(G, mapping, copy=True)` on an exact simple ``Graph`` with a dict
mapping now routes to `PyGraph::_native_relabel_copy`, which clones the store
`AttrMap` Rust-to-Rust and copies the Python mirror with `PyDict_Copy` instead
of materializing every attr dict out of the graph and re-ingesting it.

Everything here compares against the live networkx in the environment, because
the kernel's whole job is to be indistinguishable from the path it replaces.
The cases that matter are the ones where it must NOT take over:

* a MERGING mapping (two nodes onto one) — order-sensitive attr merge, stays on
  the Python path,
* a mapping target of ``None`` — not a legal node; `read_gexf(relabel=True)`
  depends on the ValueError, and an earlier version of the kernel swallowed it,
  which is why that case is pinned here explicitly,
* non-scalar attr values (tuples, lists, None), which live only in the Python
  mirror and would be silently dropped by a store-only clone.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx

SCALARS = {"w": 2, "f": 1.5, "s": "x", "b": True}
NONSCALARS = {"pos": (1, 2), "tags": ["a", "b"], "none": None}


def _build(lib, *, nattrs=3, nonscalar=False, n=30, e=70, seed=11, graph_attr=True):
    rng = random.Random(seed)
    graph = lib.Graph()
    attrs = {f"a{i}": i for i in range(nattrs)}
    if nonscalar:
        attrs = {**attrs, **NONSCALARS}
    graph.add_nodes_from((f"n{i}", dict(attrs)) for i in range(n))
    seen: set[tuple[int, int]] = set()
    while len(seen) < e:
        a, b = rng.randrange(n), rng.randrange(n)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(f"n{pair[0]}", f"n{pair[1]}", **attrs)
    if graph_attr:
        graph.graph["level"] = "top"
    return graph


def _pair(**kwargs):
    return _build(nx, **kwargs), _build(fnx, **kwargs)


def _shape(graph):
    return (
        list(graph.nodes()),
        list(graph.edges()),
        [dict(d) for _, d in graph.nodes(data=True)],
        [dict(d) for _, _, d in graph.edges(data=True)],
        dict(graph.graph),
    )


MAPPINGS = {
    "offset": lambda n: {f"n{i}": f"n{i + 500}" for i in range(n)},
    "prefix": lambda n: {f"n{i}": f"z{i}" for i in range(n)},
    "to-int": lambda n: {f"n{i}": i * 3 for i in range(n)},
    "to-tuple": lambda n: {f"n{i}": (i, "t") for i in range(n)},
    "partial": lambda n: {f"n{i}": f"p{i}" for i in range(0, n, 2)},
    "swap-two": lambda n: {"n0": "n1", "n1": "n0"},
    "empty": lambda n: {},
    "merging": lambda n: {f"n{i}": "ALL" for i in range(n)},
    "collide-unmapped": lambda n: {"n0": "n1"},
}


@pytest.mark.parametrize("mapping_name", list(MAPPINGS))
@pytest.mark.parametrize("nattrs", [0, 1, 5])
@pytest.mark.parametrize("nonscalar", [False, True], ids=["scalar", "nonscalar"])
def test_relabel_copy_matches_networkx(mapping_name, nattrs, nonscalar):
    gnx, gfx = _pair(nattrs=nattrs, nonscalar=nonscalar)
    mapping = MAPPINGS[mapping_name](30)
    assert _shape(fnx.relabel_nodes(gfx, mapping, copy=True)) == _shape(
        nx.relabel_nodes(gnx, mapping, copy=True)
    )


@pytest.mark.parametrize("seed", range(5))
def test_relabel_copy_matches_networkx_across_seeds(seed):
    gnx, gfx = _build(nx, seed=seed, nonscalar=True), _build(fnx, seed=seed, nonscalar=True)
    mapping = {f"n{i}": f"r{i}" for i in range(30)}
    assert _shape(fnx.relabel_nodes(gfx, mapping, copy=True)) == _shape(
        nx.relabel_nodes(gnx, mapping, copy=True)
    )


def test_relabel_to_none_raises_like_networkx():
    """`None` is not a legal node — `read_gexf(relabel=True)` relies on this.

    An earlier version of the kernel canonicalized the target instead of
    letting the established path reject it, which silently turned this
    ValueError into a graph containing a ``None`` node.
    """
    gnx, gfx = _pair(nattrs=1)
    mapping = {"n0": None}
    with pytest.raises(ValueError, match="None"):
        nx.relabel_nodes(gnx, mapping, copy=True)
    with pytest.raises(ValueError, match="None"):
        fnx.relabel_nodes(gfx, mapping, copy=True)


def test_relabel_result_does_not_alias_the_source():
    """The store clone and the mirror copy must both be independent."""
    _, gfx = _pair(nattrs=2, nonscalar=True)
    relabeled = fnx.relabel_nodes(gfx, {f"n{i}": f"r{i}" for i in range(30)}, copy=True)

    relabeled.nodes["r0"]["injected"] = 1
    relabeled.edges[list(relabeled.edges())[0]]["injected"] = 1
    relabeled.graph["injected"] = 1

    assert "injected" not in gfx.nodes["n0"]
    assert "injected" not in gfx.graph
    assert all("injected" not in d for _, _, d in gfx.edges(data=True))
    # And the source's own attrs are still intact and unrenamed.
    assert "n0" in gfx and "r0" not in gfx


def test_relabel_result_is_live_and_mutable():
    """The result is an ordinary graph, not a frozen snapshot."""
    gnx, gfx = _pair(nattrs=1)
    mapping = {f"n{i}": f"r{i}" for i in range(30)}
    hnx = nx.relabel_nodes(gnx, mapping, copy=True)
    hfx = fnx.relabel_nodes(gfx, mapping, copy=True)
    for graph in (hnx, hfx):
        graph.add_edge("brand", "new", weight=9)
        graph.nodes["r0"]["late"] = 2
    assert _shape(hfx) == _shape(hnx)


def test_relabel_after_attribute_mutation_sees_the_write():
    """A write through the live mirror must survive the relabel.

    Node-attr writes are not tracked by `edges_dirty`, so the kernel refreshes
    node attrs from the mirror where one exists. This is the case that would
    break if it cloned the store blindly.
    """
    gnx, gfx = _pair(nattrs=1)
    for graph in (gnx, gfx):
        graph.nodes["n0"]["mutated"] = "yes"
        graph.edges["n0", list(graph["n0"])[0]]["mutated"] = "yes"
    mapping = {f"n{i}": f"r{i}" for i in range(30)}
    assert _shape(fnx.relabel_nodes(gfx, mapping, copy=True)) == _shape(
        nx.relabel_nodes(gnx, mapping, copy=True)
    )


def test_relabel_copy_false_is_untouched():
    """The kernel is copy=True only."""
    gnx, gfx = _pair(nattrs=2)
    mapping = {f"n{i}": f"r{i}" for i in range(30)}
    rnx = nx.relabel_nodes(gnx, mapping, copy=False)
    rfx = fnx.relabel_nodes(gfx, mapping, copy=False)
    assert rfx is gfx
    assert _shape(rfx) == _shape(rnx)


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_other_graph_classes_still_match(cls_name):
    """The kernel is gated to exact simple Graph; siblings keep the old path."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_nodes_from((f"n{i}", {"w": i}) for i in range(8))
        for i in range(7):
            graph.add_edge(f"n{i}", f"n{i + 1}", w=i)
    mapping = {f"n{i}": f"r{i}" for i in range(8)}
    assert _shape(fnx.relabel_nodes(gfx, mapping, copy=True)) == _shape(
        nx.relabel_nodes(gnx, mapping, copy=True)
    )


def test_callable_mapping_matches_networkx():
    """A callable is pre-resolved to a dict before the kernel sees it."""
    gnx, gfx = _pair(nattrs=2)
    assert _shape(fnx.relabel_nodes(gfx, lambda n: f"c_{n}", copy=True)) == _shape(
        nx.relabel_nodes(gnx, lambda n: f"c_{n}", copy=True)
    )
