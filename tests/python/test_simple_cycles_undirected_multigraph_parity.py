"""Differential parity for ``simple_cycles`` on non-directed-simple graphs.

``test_cycle_conformance.py`` exercises ``simple_cycles`` only on
``DiGraph`` fixtures, but networkx 3.x generalized ``simple_cycles`` to
every graph class: undirected ``Graph``/``MultiGraph`` (using a distinct
non-Johnson algorithm), with parallel-edge length-2 cycles, self-loops,
and a ``length_bound`` cap on all of them.

This test locks fnx against the real upstream library across all four
graph classes — structured fixtures that target the multigraph-only and
undirected-only emission paths, plus a randomized differential sweep.
fnx is verified to reproduce nx's *exact* emission order (not merely the
same multiset of cycles), so the assertions compare the generator output
list directly.

br-r37-c1-f79v3
"""

from __future__ import annotations

import random
import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Structured fixtures — each targets an emission path the directed-only
# conformance test never reaches.
# ---------------------------------------------------------------------------

# (name, fnx_cls, nx_cls, edges, length_bound)
_STRUCTURED = [
    # Undirected triangle + attached triangle sharing one node.
    ("graph_two_triangles_shared_node", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)], None),
    # Undirected with a chord — several overlapping cycles.
    ("graph_square_with_chord", fnx.Graph, nx.Graph,
     [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)], None),
    # Undirected complete-ish graph, bounded.
    ("graph_k4_bound_3", fnx.Graph, nx.Graph,
     [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], 3),
    ("graph_k4_bound_4", fnx.Graph, nx.Graph,
     [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)], 4),
    # MultiGraph parallel edges => length-2 cycles between the same pair.
    ("multigraph_parallel_pair", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (1, 2), (2, 0)], None),
    # MultiGraph parallel edges + self-loop.
    ("multigraph_parallel_and_selfloop", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (1, 2), (2, 0), (2, 2), (3, 3)], None),
    # MultiGraph triple-parallel edges => several distinct 2-cycles.
    ("multigraph_triple_parallel", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (0, 1), (1, 2), (2, 0)], None),
    # MultiGraph bounded to length 2 — only the parallel-edge cycles.
    ("multigraph_parallel_bound_2", fnx.MultiGraph, nx.MultiGraph,
     [(0, 1), (0, 1), (1, 2), (2, 0), (2, 3), (3, 2)], 2),
    # MultiDiGraph parallel directed edges + antiparallel.
    ("multidigraph_parallel", fnx.MultiDiGraph, nx.MultiDiGraph,
     [(0, 1), (0, 1), (1, 0), (1, 2), (2, 1)], None),
    # MultiDiGraph self-loop is a length-1 cycle.
    ("multidigraph_selfloop", fnx.MultiDiGraph, nx.MultiDiGraph,
     [(0, 0), (0, 1), (1, 0)], None),
]


def _build(fnx_cls, nx_cls, edges):
    fg = fnx_cls()
    ng = nx_cls()
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng


@pytest.mark.parametrize(
    "name,fnx_cls,nx_cls,edges,length_bound",
    _STRUCTURED,
    ids=[fx[0] for fx in _STRUCTURED],
)
def test_simple_cycles_structured_matches_networkx(
    name, fnx_cls, nx_cls, edges, length_bound
):
    fg, ng = _build(fnx_cls, nx_cls, edges)
    kwargs = {} if length_bound is None else {"length_bound": length_bound}
    fr = list(fnx.simple_cycles(fg, **kwargs))
    nr = list(nx.simple_cycles(ng, **kwargs))
    assert fr == nr, f"{name}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Randomized differential sweep across all four graph classes.
# ---------------------------------------------------------------------------

_CLASSES = [
    (fnx.Graph, nx.Graph),
    (fnx.MultiGraph, nx.MultiGraph),
    (fnx.DiGraph, nx.DiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph),
]


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    _CLASSES,
    ids=[fx[0].__name__ for fx in _CLASSES],
)
@pytest.mark.parametrize("length_bound", [None, 3])
def test_simple_cycles_random_matches_networkx(
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
        fr = list(fnx.simple_cycles(fg, **kwargs))
        nr = list(nx.simple_cycles(ng, **kwargs))
    assert fr == nr, (
        f"{fnx_cls.__name__} seed={seed} length_bound={length_bound}: "
        f"fnx={fr} nx={nr}"
    )


def test_simple_cycles_undirected_returns_lazy_generator():
    """``simple_cycles`` is a lazy generator on undirected graphs too."""
    fg = fnx.Graph()
    fg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    it = fnx.simple_cycles(fg)
    assert iter(it) is iter(it)  # an iterator, not a materialized list
    assert not isinstance(it, list)
    assert sorted(map(sorted, it)) == [[0, 1, 2]]
