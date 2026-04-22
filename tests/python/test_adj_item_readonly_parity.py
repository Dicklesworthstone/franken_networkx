"""Parity coverage for Graph/DiGraph adj item-access read-only contract.

Bead franken_networkx-fsft: G.adj[node] and G[node] must return
read-only AtlasView wrappers that reject __setitem__ with TypeError,
matching upstream NetworkX. Previously fnx returned raw mutable dicts.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_adj_item_access_is_readonly(fnx_ctor, nx_ctor):
    from collections.abc import Mapping

    fg = fnx_ctor()
    fg.add_edge(0, 1, weight=3)
    ng = nx_ctor()
    ng.add_edge(0, 1, weight=3)

    for accessor in (lambda g, n: g[n], lambda g, n: g.adj[n]):
        fnbrs = accessor(fg, 0)
        nnbrs = accessor(ng, 0)
        assert isinstance(fnbrs, Mapping)
        with pytest.raises(TypeError):
            fnbrs["x"] = {}
        with pytest.raises(TypeError):
            nnbrs["x"] = {}
        # Attempted mutation didn't change the graph.
        assert not fg.has_edge(0, "x")
        # Deep content matches upstream.
        assert dict(fnbrs) == dict(nnbrs)


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
    ],
)
def test_adj_item_access_type_is_atlas_view_like(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge(0, 1)
    ng = nx_ctor()
    ng.add_edge(0, 1)

    # Same class name (AtlasView) on both sides is part of the contract.
    assert type(fg.adj[0]).__name__ == type(ng.adj[0]).__name__
    assert type(fg[0]).__name__ == type(ng[0]).__name__
