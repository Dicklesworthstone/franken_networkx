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
