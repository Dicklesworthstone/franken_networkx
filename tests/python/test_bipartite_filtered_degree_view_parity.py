"""Parity for ``bipartite.degrees`` _FilteredDegreeView class repr.

Bead br-r37-c1-wu9dv. fnx.bipartite.degrees(G, top) returned a tuple
of (_FilteredDegreeView, _FilteredDegreeView). nx returns
(DegreeView({1: 2, 3: 2}), DegreeView({0: 1, 2: 2, 4: 1})). Two
issues:

- class name '_FilteredDegreeView' differed from nx's 'DegreeView'.
- repr showed just node-keys list ('_FilteredDegreeView([1, 3])')
  instead of nx's full dict repr ('DegreeView({1: 2, 3: 2})').

Drop-in code that printed these or compared reprs broke.
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
def test_filtered_degree_view_class_name_is_DegreeView():
    g = fnx.path_graph(5)
    top, bot = fnx.bipartite.degrees(g, [0, 2, 4])
    assert type(top).__name__ == "DegreeView"
    assert type(bot).__name__ == "DegreeView"


@needs_nx
def test_filtered_degree_view_repr_matches_networkx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    top, bot = fnx.bipartite.degrees(g, [0, 2, 4])
    ntop, nbot = nx.bipartite.degrees(gx, [0, 2, 4])
    assert repr(top) == repr(ntop)
    assert repr(bot) == repr(nbot)


@needs_nx
def test_filtered_degree_view_str_matches_networkx():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    top, _ = fnx.bipartite.degrees(g, [0, 2, 4])
    ntop, _ = nx.bipartite.degrees(gx, [0, 2, 4])
    assert str(top) == str(ntop)


@needs_nx
def test_filtered_degree_view_dict_conversion_unchanged():
    """Sanity: dict(view) values still match."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    top, bot = fnx.bipartite.degrees(g, [0, 2, 4])
    ntop, nbot = nx.bipartite.degrees(gx, [0, 2, 4])
    assert dict(top) == dict(ntop)
    assert dict(bot) == dict(nbot)


@needs_nx
def test_filtered_degree_view_no_underscore_class_name():
    """Regression: '_FilteredDegreeView' wording must not leak."""
    g = fnx.path_graph(5)
    top, _ = fnx.bipartite.degrees(g, [0, 2, 4])
    assert "_Filtered" not in type(top).__name__
    assert "_Filtered" not in repr(top)
    assert "_Filtered" not in str(top)


@needs_nx
def test_filtered_degree_view_iteration_unchanged():
    """Iteration still yields (node, degree) tuples."""
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    top, _ = fnx.bipartite.degrees(g, [0, 2, 4])
    ntop, _ = nx.bipartite.degrees(gx, [0, 2, 4])
    assert list(top) == list(ntop)


@needs_nx
def test_filtered_degree_view_indexing_unchanged():
    g = fnx.path_graph(5)
    gx = nx.path_graph(5)
    top, _ = fnx.bipartite.degrees(g, [0, 2, 4])
    ntop, _ = nx.bipartite.degrees(gx, [0, 2, 4])
    for n in [1, 3]:
        assert top[n] == ntop[n]
