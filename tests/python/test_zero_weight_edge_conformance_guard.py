"""Conformance guard: weight=0 edges are distinct from non-edges.

A weight=0 edge is a real edge (it exists, contributes to connectivity/degree)
but contributes 0 to weighted sums — distinct from a non-edge. This is a tempting
perf shortcut to get wrong (treat weight==0 as "no edge"), so it is pinned vs nx
across the matrix / shortest-path / MST / pagerank paths.

No mocks: real fnx vs real networkx 3.x.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx

np = pytest.importorskip("numpy")

_EDGES = [(0, 1, 0.0), (1, 2, 5.0), (2, 3, 0.0), (3, 4, 2.0), (0, 4, 0.0), (2, 4, 3.0)]


def _build(cls):
    fg = cls()
    ng = getattr(nx, cls.__name__)()
    for u, v, w in _EDGES:
        fg.add_edge(u, v, weight=w); ng.add_edge(u, v, weight=w)
    return fg, ng


def _dclose(a, b, tol=1e-6):
    a, b = dict(a), dict(b)
    return set(a) == set(b) and all(abs(a[k] - b[k]) < tol for k in a)


def test_to_numpy_array_distinguishes_zero_weight_from_nonedge():
    fg, ng = _build(fnx.Graph)
    # nonedge=nan makes the distinction observable: weight-0 edges -> 0, real
    # non-edges -> nan.
    a = fnx.to_numpy_array(fg, nonedge=np.nan)
    b = nx.to_numpy_array(ng, nonedge=np.nan)
    assert a.shape == b.shape and np.allclose(a, b, atol=1e-9, equal_nan=True)
    # zero-weight edge (0,1) is 0.0, not nan; true non-edge (1,3) is nan.
    assert a[0, 1] == 0.0 and np.isnan(a[1, 3])


def test_shortest_path_and_dijkstra_zero_weight():
    fg, ng = _build(fnx.Graph)
    assert (fnx.shortest_path_length(fg, 0, 3, weight="weight")
            == nx.shortest_path_length(ng, 0, 3, weight="weight"))
    fd = dict(fnx.all_pairs_dijkstra_path_length(fg, weight="weight"))
    nd = dict(nx.all_pairs_dijkstra_path_length(ng, weight="weight"))
    assert all(_dclose(fd[s], nd[s]) for s in nd)


def test_mst_zero_weight():
    fg, ng = _build(fnx.Graph)
    fm = {tuple(sorted((u, v))) for u, v in fnx.minimum_spanning_tree(fg, weight="weight").edges()}
    nm = {tuple(sorted((u, v))) for u, v in nx.minimum_spanning_tree(ng, weight="weight").edges()}
    assert fm == nm


def test_pagerank_zero_weight():
    fg, ng = _build(fnx.DiGraph)
    assert _dclose(fnx.pagerank(fg, weight="weight"), nx.pagerank(ng, weight="weight"))
