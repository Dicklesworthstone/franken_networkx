"""Parity for ``voronoi_cells`` empty-centers exception.

Bead br-r37-c1-95ayv. fnx.voronoi_cells(G, set()) raised
``NetworkXError('center_nodes must not be empty')``; nx raises
``ValueError('sources must not be empty')``. Drop-in code catching
``ValueError`` failed on fnx (NetworkXError is not a ValueError
subclass) and the message text mismatched too.
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
def test_voronoi_cells_empty_centers_raises_value_error():
    G = fnx.path_graph(5)
    with pytest.raises(ValueError) as fnx_exc:
        fnx.voronoi_cells(G, set())
    nx_g = nx.path_graph(5)
    with pytest.raises(ValueError) as nx_exc:
        nx.voronoi_cells(nx_g, set())
    assert str(fnx_exc.value) == str(nx_exc.value)
    assert "sources must not be empty" in str(fnx_exc.value)


@needs_nx
def test_voronoi_cells_empty_centers_exception_type_matches_networkx():
    """Exact exception class parity — must be ValueError, not
    NetworkXError, so drop-in code catching ValueError works."""
    G = fnx.path_graph(5)
    nx_g = nx.path_graph(5)
    with pytest.raises(Exception) as fnx_exc:
        fnx.voronoi_cells(G, set())
    with pytest.raises(Exception) as nx_exc:
        nx.voronoi_cells(nx_g, set())
    assert type(fnx_exc.value) is type(nx_exc.value)
    assert type(fnx_exc.value).__name__ == "ValueError"


@needs_nx
def test_voronoi_cells_empty_centers_caught_by_value_error():
    """ValueError catch must trigger; NetworkXError must not be
    sufficient since nx uses ValueError."""
    G = fnx.path_graph(5)
    caught_via_value_error = False
    try:
        fnx.voronoi_cells(G, set())
    except ValueError:
        caught_via_value_error = True
    assert caught_via_value_error


@needs_nx
def test_voronoi_cells_empty_centers_on_null_graph():
    """Empty centers + empty graph still raises ValueError, not some
    earlier null-graph exception."""
    G = fnx.empty_graph(0)
    with pytest.raises(ValueError):
        fnx.voronoi_cells(G, set())


@needs_nx
def test_voronoi_cells_normal_case_unchanged():
    """The fix must not affect the normal path."""
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    assert fnx.voronoi_cells(G, {0, 4}) == nx.voronoi_cells(GX, {0, 4})


@needs_nx
def test_voronoi_cells_empty_list_also_raises_value_error():
    """Lists, sets, generators all collapse to the same empty check."""
    G = fnx.path_graph(5)
    with pytest.raises(ValueError):
        fnx.voronoi_cells(G, [])
    with pytest.raises(ValueError):
        fnx.voronoi_cells(G, iter(()))
