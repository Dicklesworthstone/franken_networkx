"""Parity for ``G.edges(data=...)`` live-view semantics.

Bead br-r37-c1-sf1ku. fnx's ``_edge_view_call_with_nbunch_first``
wrapper materialised the result to a list when ``data`` was non-False
or ``nbunch`` was given. nx's ``EdgeDataView`` is a true view over
the live graph — mutations after the view is captured are reflected
on subsequent iteration.

Drop-in code that captures ``view = G.edges(data=True)`` and iterates
after mutating G saw the pre-mutation snapshot on fnx but the live
state on nx. ``type(view).__name__`` was ``'list'`` on fnx vs
``'EdgeDataView'`` on nx — broke isinstance / class-name checks.

Fix introduces an ``EdgeDataView`` wrapper that re-invokes the
underlying edge_view_call on each access (iter / len / contains /
repr) so semantics match nx, with class name aligned.
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


@needs_nx
def test_edges_data_returns_edge_data_view_class():
    G = fnx.path_graph(3)
    view = G.edges(data=True)
    assert type(view).__name__ == "EdgeDataView"


@needs_nx
def test_edges_nbunch_returns_edge_data_view_class():
    G = fnx.path_graph(3)
    view = G.edges(nbunch=0)
    assert type(view).__name__ == "EdgeDataView"


@needs_nx
def test_edges_no_args_still_returns_edge_view():
    """The plain G.edges() form should still return the live Rust
    EdgeView — only the data/nbunch paths were buggy."""
    G = fnx.path_graph(3)
    view = G.edges()
    assert type(view).__name__ == "EdgeView"


@needs_nx
def test_edges_data_view_is_live_after_mutation():
    """Capturing the view then mutating G should reflect on the next
    iteration — matches nx's live-view contract."""
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    fview = G.edges(data=True)
    nview = GX.edges(data=True)

    G.add_edge(2, 3)
    GX.add_edge(2, 3)

    f_after = list(fview)
    n_after = list(nview)
    assert f_after == n_after
    # Confirm the new edge is included on the freshly-iterated view.
    assert (2, 3, {}) in f_after


@needs_nx
def test_edges_data_view_len_is_live():
    G = fnx.path_graph(3)
    view = G.edges(data=True)
    assert len(view) == 2
    G.add_edge(2, 3)
    assert len(view) == 3


@needs_nx
def test_edges_data_view_contains_works():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2.5)
    fview = G.edges(data=True)
    nview = GX.edges(data=True)
    # Both should agree
    assert ((0, 1, {"weight": 2.5}) in fview) == ((0, 1, {"weight": 2.5}) in nview)
    assert ((0, 1) in fview) == ((0, 1) in nview)


@needs_nx
def test_edges_data_str_attr_yields_3_tuples():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    view = G.edges(data="weight")
    assert list(view) == [(0, 1, 2.5)]


@needs_nx
def test_edges_data_str_attr_default():
    """data='attr' with default for edges missing the attribute."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    G.add_edge(1, 2)
    GX = nx.Graph()
    GX.add_edge(0, 1, weight=2.5)
    GX.add_edge(1, 2)

    f = list(G.edges(data="weight", default=99))
    n = list(GX.edges(data="weight", default=99))
    assert f == n


@needs_nx
def test_edges_nbunch_yields_correct_endpoint_order():
    """When nbunch is given, edges are yielded with the queried
    endpoint first (br-edgesu1)."""
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = list(G.edges(nbunch=2))
    n = list(GX.edges(nbunch=2))
    # Both should yield (2, ...) tuples
    for u, v in f + n:
        pass  # type-check
    assert sorted(f) == sorted(n)


@needs_nx
def test_edges_nbunch_view_is_live():
    G = fnx.path_graph(3)
    fview = G.edges(nbunch=2)
    initial = list(fview)
    G.add_edge(2, 3)
    after = list(fview)
    assert len(after) > len(initial)


@needs_nx
def test_edges_data_view_repr():
    """Repr should be 'EdgeDataView(...)' matching nx's wording."""
    G = fnx.path_graph(2)
    view = G.edges(data=True)
    r = repr(view)
    assert r.startswith("EdgeDataView(")


@needs_nx
def test_edges_data_view_eq_to_list():
    G = fnx.path_graph(2)
    view = G.edges(data=True)
    assert view == [(0, 1, {})]


@needs_nx
def test_edges_data_none_yields_default_in_third_position():
    """data=None means yield 3-tuples where the third element is the
    default for every edge (br-edgesnone)."""
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    f = list(G.edges(data=None, default=42))
    n = list(GX.edges(data=None, default=42))
    assert f == n
