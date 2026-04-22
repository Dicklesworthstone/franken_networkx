"""Parity coverage for `to_undirected(as_view=..., reciprocal=...)`.

Bead franken_networkx-5vyu: the core graph classes must accept
NetworkX's conversion keyword surface — as_view on all four families
and reciprocal on the directed pair.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_as_view_returns_frozen_view(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(0, 1), (1, 2)])
    ng = nx_ctor()
    ng.add_edges_from([(0, 1), (1, 2)])

    fv = fg.to_undirected(as_view=True)
    nv = ng.to_undirected(as_view=True)

    # View must be frozen on both sides.
    assert fnx.is_frozen(fv)
    assert nx.is_frozen(nv)

    # Same edge set (sorted by endpoint pair for undirected comparison).
    f_edges = sorted(sorted(e) for e in fv.edges())
    n_edges = sorted(sorted(e) for e in nv.edges())
    assert f_edges == n_edges


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_reciprocal_keeps_only_bidirectional_edges(fnx_ctor, nx_ctor):
    """reciprocal=True: keep an undirected edge only when the original
    had edges in both directions.
    """
    fg = fnx_ctor()
    fg.add_edge(0, 1)   # single direction
    fg.add_edge(1, 0)   # reverse — pair
    fg.add_edge(2, 3)   # single direction only
    ng = nx_ctor()
    ng.add_edge(0, 1)
    ng.add_edge(1, 0)
    ng.add_edge(2, 3)

    fu = fg.to_undirected(reciprocal=True)
    nu = ng.to_undirected(reciprocal=True)

    # Both should have the bidirectional pair but not the single edge.
    assert sorted(sorted(e) for e in fu.edges()) == sorted(
        sorted(e) for e in nu.edges()
    )
    # Specifically: (0, 1) retained, (2, 3) dropped.
    fu_edges = {frozenset(e) for e in fu.edges()}
    assert frozenset((0, 1)) in fu_edges
    assert frozenset((2, 3)) not in fu_edges


@pytest.mark.parametrize(
    ("direction", "fnx_ctor", "nx_ctor"),
    [
        ("to_directed", fnx.Graph, nx.Graph),
        ("to_undirected", fnx.DiGraph, nx.DiGraph),
    ],
)
def test_conversion_live_view_exposes_dict_factory_attributes(direction, fnx_ctor, nx_ctor):
    """Bead franken_networkx-i4b8: top-level to_undirected / to_directed
    conversion live views must expose NetworkX's dict-factory attribute
    surface — each materialising an empty dict by default.
    """
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    ng = nx_ctor()
    ng.add_edge(0, 1)

    fv = getattr(fg, direction)(as_view=True)
    nv = getattr(ng, direction)(as_view=True)

    factories = (
        "adjlist_inner_dict_factory",
        "adjlist_outer_dict_factory",
        "edge_attr_dict_factory",
        "graph_attr_dict_factory",
        "node_attr_dict_factory",
        "node_dict_factory",
    )
    for attr in factories:
        assert hasattr(fv, attr), f"fnx view missing {attr}"
        assert hasattr(nv, attr), f"nx view missing {attr}"
        f_factory = getattr(fv, attr)
        assert callable(f_factory)
        assert f_factory() == {}


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_to_undirected_reciprocal_false_matches_default(fnx_ctor, nx_ctor):
    """reciprocal=False keeps all undirected edges, matching the
    default behaviour.
    """
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    fg.add_edge(2, 3)
    ng = nx_ctor()
    ng.add_edge(0, 1)
    ng.add_edge(2, 3)

    fu = fg.to_undirected(reciprocal=False)
    nu = ng.to_undirected(reciprocal=False)
    assert sorted(sorted(e) for e in fu.edges()) == sorted(
        sorted(e) for e in nu.edges()
    )
