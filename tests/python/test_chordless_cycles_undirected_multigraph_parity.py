"""Differential parity for ``chordless_cycles`` on undirected graphs.

``test_cycle_conformance.py`` exercises ``chordless_cycles`` only on
``DiGraph`` fixtures, but networkx 3.x also defines ``chordless_cycles``
for undirected ``Graph``/``MultiGraph`` (where parallel edges form
length-2 chordless cycles).

This test locks fnx against the real upstream library across the
undirected and multigraph classes — structured fixtures plus a
randomized differential sweep. Comparison is by canonical multiset:
a chordless cycle is defined by its (undirected) node sequence, and the
*emission order* of distinct cycles is not part of nx's contract for
undirected graphs (e.g. nx and fnx may list the parallel-edge 2-cycles
of a multigraph in either order). The multiset of canonicalized cycles
is the invariant both libraries must agree on.

br-r37-c1-bckdt
"""

from __future__ import annotations

import cProfile
import random
import warnings
from collections import Counter

import pytest
import networkx as nx

import franken_networkx as fnx


def _canonical_undirected_cycle(cycle):
    """Rotate+reflect an undirected cycle's node list to a canonical key."""
    nodes = [str(x) for x in cycle]
    if len(nodes) <= 1:
        return ("self", *nodes)

    def _rot_min(seq):
        i = min(range(len(seq)), key=lambda k: seq[k])
        return tuple(seq[i:] + seq[:i])

    return min(_rot_min(nodes), _rot_min(list(reversed(nodes))))


def _multiset(cycles):
    return Counter(_canonical_undirected_cycle(c) for c in cycles)


def _build(fnx_cls, nx_cls, edges):
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng


# ---------------------------------------------------------------------------
# Structured fixtures.
# ---------------------------------------------------------------------------

# (name, fnx_cls, nx_cls, edges, length_bound)
_STRUCTURED = [
    # Triangle is chordless; the square-with-chord splits into two triangles.
    ("graph_square_with_chord", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)], None),
    # A 5-cycle is chordless; K4 has only triangles.
    ("graph_c5", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], None),
    ("graph_k4", fnx.Graph, nx.Graph,
     [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], None),
    # Two triangles joined at a node.
    ("graph_bowtie", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)], None),
    # Bounded length filters out the long chordless cycle.
    ("graph_c5_bound_4", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], 4),
    ("graph_c5_bound_5", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], 5),
    # MultiGraph: parallel edges => length-2 chordless cycles.
    ("multigraph_parallel_pair", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (1, 2), (2, 0)], None),
    ("multigraph_triple_parallel", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (0, 1), (1, 2), (2, 0)], None),
    ("multigraph_parallel_and_triangle", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (1, 2), (2, 3), (3, 1)], None),
    ("multigraph_parallel_bound_2", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (1, 2), (2, 3), (3, 4), (4, 2)], 2),
]


@pytest.mark.parametrize(
    "name,fnx_cls,nx_cls,edges,length_bound",
    _STRUCTURED,
    ids=[fx[0] for fx in _STRUCTURED],
)
def test_chordless_cycles_structured_matches_networkx(
    name, fnx_cls, nx_cls, edges, length_bound
):
    fg, ng = _build(fnx_cls, nx_cls, edges)
    kwargs = {} if length_bound is None else {"length_bound": length_bound}
    fr = list(fnx.chordless_cycles(fg, **kwargs))
    nr = list(nx.chordless_cycles(ng, **kwargs))
    assert _multiset(fr) == _multiset(nr), f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Randomized differential sweep.
# ---------------------------------------------------------------------------

_CLASSES = [
    (fnx.Graph, nx.Graph),
    (fnx.MultiGraph, nx.MultiGraph),
]


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    _CLASSES,
    ids=[fx[0].__name__ for fx in _CLASSES],
)
@pytest.mark.parametrize("length_bound", [None, 4])
def test_chordless_cycles_random_matches_networkx(
    seed, fnx_cls, nx_cls, length_bound
):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for _ in range(rng.randint(n, n * 2)):
        u = rng.randint(0, n - 1)
        v = rng.randint(0, n - 1)
        fg.add_edge(u, v)
        ng.add_edge(u, v)

    kwargs = {} if length_bound is None else {"length_bound": length_bound}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fr = list(fnx.chordless_cycles(fg, **kwargs))
        nr = list(nx.chordless_cycles(ng, **kwargs))
    assert _multiset(fr) == _multiset(nr), (
        f"{fnx_cls.__name__} seed={seed} length_bound={length_bound}: "
        f"fnx={fr} nx={nr}"
    )


def test_chordless_cycles_undirected_returns_lazy_generator():
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.chordless_cycles(fg)
    assert iter(it) is iter(it)
    assert not isinstance(it, list)
    assert _multiset(it) == Counter({("0", "1", "2"): 1})


# br-r37-c1-56s29: the adapter is a structural snapshot, not an attributed
# graph conversion. Check the real consumer's exact sequence, not a sorted
# multiset that could hide changed insertion order or cycle rotations.
_ALL_CLASSES = [
    (fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
def test_chordless_cycles_bulk_structure_adapter_avoids_edge_rebuild(fnx_cls, nx_cls):
    fg, ng = _build(fnx_cls, nx_cls, [("a", "b"), ("b", "c"), ("c", "a")])
    fg.add_node("isolated")
    ng.add_node("isolated")
    profile = cProfile.Profile()
    converted = profile.runcall(fnx._networkx_graph_for_traversal_parity, fg)
    assert list(converted) == list(ng)
    assert list(nx.chordless_cycles(converted)) == list(nx.chordless_cycles(ng))
    edge_rebuilds = [
        entry for entry in profile.getstats()
        if hasattr(entry.code, "co_name")
        and entry.code.co_name in ("add_node", "add_edge", "add_edges_from")
        and "networkx/classes" in entry.code.co_filename.replace("\\", "/")
    ]
    assert not edge_rebuilds


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
def test_chordless_cycles_bulk_structure_ignores_nonstring_attributes(fnx_cls, nx_cls):
    fg, ng = _build(fnx_cls, nx_cls, [("a", "b"), ("b", "c"), ("c", "a")])
    for graph in (fg, ng):
        graph.graph[0] = object()
        graph.nodes["a"][1] = object()
        attrs = graph["a"]["b"]
        if graph.is_multigraph():
            attrs = attrs[0]
        attrs[2] = object()
    assert list(fnx.chordless_cycles(fg)) == list(nx.chordless_cycles(ng))
    # Attribute payloads are not consumed by chordless_cycles and must not be
    # passed as **kwargs (which rejects non-string keys).
    assert 1 in fg.nodes["a"]
    attrs = fg["a"]["b"][0] if fg.is_multigraph() else fg["a"]["b"]
    assert 2 in attrs


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("length_bound", [None, 0, 1, 2, 4])
def test_chordless_cycles_exact_order_after_shuffled_mutations(fnx_cls, nx_cls, seed, length_bound):
    rng = random.Random(seed)
    labels = ["alpha", 3, ("tuple", 1), "beta", -7, "gamma", (2, 3)]
    rng.shuffle(labels)
    fg, ng = fnx_cls(), nx_cls()
    for graph in (fg, ng):
        graph.add_nodes_from(labels)
        graph.add_edges_from(zip(labels[:6], labels[1:6] + labels[:1]))
        graph.add_edge(labels[6], labels[6])
    for _ in range(18):
        u, v = rng.sample(labels[:6], 2)
        weight = rng.random()
        for graph in (fg, ng):
            graph.add_edge(u, v, weight=weight)
    # Remove/reinsert changes adjacency order. Use the same node objects on
    # both arms so CPython set order sees exactly the same labels.
    for graph in (fg, ng):
        if graph.has_edge(labels[0], labels[1]):
            graph.remove_edge(labels[0], labels[1])
        graph.add_edge(labels[0], labels[1])
    assert list(fnx.chordless_cycles(fg, length_bound=length_bound)) == list(
        nx.chordless_cycles(ng, length_bound=length_bound)
    )


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
@pytest.mark.parametrize("kind", ["subgraph", "conversion", "reverse", "assigned"])
def test_chordless_cycles_view_and_private_storage_match_networkx(fnx_cls, nx_cls, kind):
    fg, ng = _build(fnx_cls, nx_cls, [(0, 1), (1, 2), (2, 0), (2, 3), (3, 1), (4, 4)])
    if kind == "subgraph":
        fg, ng = fg.subgraph([0, 1, 2]), ng.subgraph([0, 1, 2])
    elif kind == "conversion":
        conversion = "to_undirected" if fg.is_directed() else "to_directed"
        fg = getattr(fg, conversion)(as_view=True)
        ng = getattr(ng, conversion)(as_view=True)
    elif kind == "reverse" and fg.is_directed():
        fg, ng = fg.reverse(copy=False), ng.reverse(copy=False)
    elif kind == "assigned":
        replacement = nx_cls()
        replacement.add_edges_from([(8, 9), (9, 10), (10, 8), (11, 11)])
        for graph in (fg, ng):
            graph._node = replacement._node
            if graph.is_directed():
                graph._succ = replacement._succ
                graph._pred = replacement._pred
            else:
                graph._adj = replacement._adj
    assert list(fnx.chordless_cycles(fg)) == list(nx.chordless_cycles(ng))


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
def test_chordless_cycles_snapshot_is_lazy_and_does_not_mutate_source(fnx_cls, nx_cls):
    fg, ng = _build(fnx_cls, nx_cls, [(0, 1), (1, 2), (2, 0), (3, 3)])
    it = fnx.chordless_cycles(fg)
    expected = nx.chordless_cycles(ng)
    # The adapter must not run until the first next().
    for graph in (fg, ng):
        graph.add_edge(4, 4)
    before_nodes = list(fg)
    before_edges = list(fg.edges(keys=True)) if fg.is_multigraph() else list(fg.edges)
    assert list(it) == list(expected)
    assert list(fg) == before_nodes
    after_edges = list(fg.edges(keys=True)) if fg.is_multigraph() else list(fg.edges)
    assert after_edges == before_edges


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
def test_chordless_cycles_negative_bound_matches_networkx(fnx_cls, nx_cls):
    fg, ng = _build(fnx_cls, nx_cls, [(0, 1), (1, 2), (2, 0)])
    for library, graph in ((fnx, fg), (nx, ng)):
        with pytest.raises(ValueError, match="^length bound must be non-negative$"):
            list(library.chordless_cycles(graph, length_bound=-1))


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
def test_chordless_cycles_adapter_topology_survives_source_mutation(fnx_cls, nx_cls):
    fg, ng = _build(fnx_cls, nx_cls, [(0, 1), (1, 2), (2, 0)])
    if fg.is_multigraph():
        for graph in (fg, ng):
            graph.add_edge(0, 1)
    converted = fnx._networkx_graph_for_traversal_parity(fg)
    expected = list(nx.chordless_cycles(ng))
    fg.remove_edge(0, 1)
    fg.add_edge(3, 3)
    fg.add_node("new")
    assert list(nx.chordless_cycles(converted)) == expected
    assert list(converted) == list(ng)
    assert 3 not in converted


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
@pytest.mark.parametrize("isolated", [False, True])
def test_chordless_cycles_empty_and_edgeless_match_networkx(fnx_cls, nx_cls, isolated):
    fg, ng = fnx_cls(), nx_cls()
    if isolated:
        fg.add_node("alone")
        ng.add_node("alone")
    assert list(fnx.chordless_cycles(fg)) == list(nx.chordless_cycles(ng)) == []


@pytest.mark.parametrize("fnx_cls,nx_cls", _ALL_CLASSES)
def test_chordless_cycles_subclass_rows_match_networkx(fnx_cls, nx_cls):
    class Derived(fnx_cls):
        pass

    fg, ng = _build(Derived, nx_cls, [(0, 1), (1, 2), (2, 0)])
    assert type(fg) is Derived
    assert list(fnx.chordless_cycles(fg)) == list(nx.chordless_cycles(ng))
