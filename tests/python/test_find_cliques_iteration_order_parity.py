"""Parity for ``find_cliques`` and ``find_cliques_recursive`` ordering.

Bead br-r37-c1-g71v3. The Rust binding's Bron-Kerbosch produced
cliques in a different iteration order from nx, and within each
clique returned nodes in canonical/sorted order rather than nx's
pivot-based discovery order.

Repro:
  edges = [('c','d'),('a','b'),('b','c'),('d','e'),('a','c')]
  fnx -> [['a','b','c'], ['c','d'], ['d','e']]
  nx  -> [['e','d'],     ['c','b','a'], ['c','d']]

Drop-in code that iterated cliques in nx's order (or treated the
first node of each clique as the pivot) broke. ``find_cliques`` now
keeps the nx-order local path for ``nodes=None`` instead of falling
back to NetworkX.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


def _make_graph(lib, edges):
    g = lib.Graph()
    for u, v in edges:
        g.add_edge(u, v)
    return g


def _forbid_networkx_find_cliques(monkeypatch):
    monkeypatch.setattr(
        nx,
        "find_cliques",
        lambda *call_args, **call_kwargs: (_ for _ in ()).throw(
            AssertionError("NetworkX find_cliques fallback should not be used")
        ),
    )


@needs_nx
def test_repro_two_triangles_with_chord_matches_nx(monkeypatch):
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    expected = list(nx.find_cliques(gx))
    _forbid_networkx_find_cliques(monkeypatch)
    assert list(fnx.find_cliques(g)) == expected


@needs_nx
def test_two_triangles_int_nodes_match_nx(monkeypatch):
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    expected = list(nx.find_cliques(gx))
    _forbid_networkx_find_cliques(monkeypatch)
    assert list(fnx.find_cliques(g)) == expected


@needs_nx
def test_k4_with_chords_matches_nx(monkeypatch):
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "c"), ("b", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    expected = list(nx.find_cliques(gx))
    _forbid_networkx_find_cliques(monkeypatch)
    assert list(fnx.find_cliques(g)) == expected


@needs_nx
def test_complete_graph_k4_matches_nx(monkeypatch):
    g = fnx.complete_graph(4)
    gx = nx.complete_graph(4)
    expected = list(nx.find_cliques(gx))
    _forbid_networkx_find_cliques(monkeypatch)
    assert list(fnx.find_cliques(g)) == expected


@needs_nx
def test_path_graph_matches_nx(monkeypatch):
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    expected = list(nx.find_cliques(gx))
    _forbid_networkx_find_cliques(monkeypatch)
    assert list(fnx.find_cliques(g)) == expected


@needs_nx
def test_empty_graph_yields_nothing(monkeypatch):
    g = fnx.Graph()
    gx = nx.Graph()
    expected = list(nx.find_cliques(gx))
    _forbid_networkx_find_cliques(monkeypatch)
    assert list(fnx.find_cliques(g)) == expected == []


@needs_nx
def test_directed_input_raises_not_implemented():
    g = fnx.DiGraph([(0, 1)])
    with pytest.raises(fnx.NetworkXNotImplemented, match="directed"):
        list(fnx.find_cliques(g))


@needs_nx
def test_find_cliques_recursive_matches_nx():
    """Sister function shares the same drift; same delegation fix."""
    edges = [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.find_cliques_recursive(g)) == list(nx.find_cliques_recursive(gx))


@needs_nx
def test_find_cliques_recursive_int_nodes_matches_nx():
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert list(fnx.find_cliques_recursive(g)) == list(nx.find_cliques_recursive(gx))


@needs_nx
def test_nodes_kwarg_path_unchanged():
    """The ``nodes=`` branch is the existing pure-Python implementation
    and is not affected by the delegation fix; sanity-check it still
    returns the expected single clique."""
    g = fnx.complete_graph(5)
    cliques = list(fnx.find_cliques(g, nodes=[0, 1]))
    assert len(cliques) == 1
    assert set(cliques[0]) == {0, 1, 2, 3, 4}


@needs_nx
def test_number_of_cliques_unchanged_after_delegation():
    """number_of_cliques uses find_cliques internally; verify the
    integer counts still match nx after the wrapper change."""
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")]
    g = _make_graph(fnx, edges)
    gx = _make_graph(nx, edges)
    assert fnx.number_of_cliques(g) == nx.number_of_cliques(gx)
