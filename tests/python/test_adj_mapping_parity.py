"""Parity coverage for Graph/DiGraph/MultiGraph/MultiDiGraph `.adj` mapping helpers.

Upstream NetworkX exposes `items()`, `keys()`, `values()`, and `get()` on every
`<Graph>.adj` view. FrankenNetworkX must match that contract.
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
def test_adj_exposes_mapping_helpers(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])
    ng = nx_ctor()
    ng.add_edges_from([(1, 2, {"w": 3}), (2, 3, {"w": 5}), (3, 4)])

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(fg.adj, attr), f"{fnx_ctor.__name__}.adj is missing {attr}"

    assert list(fg.adj.keys()) == list(ng.adj.keys())
    assert [(k, dict(v)) for k, v in fg.adj.items()] == [
        (k, dict(v)) for k, v in ng.adj.items()
    ]
    assert [dict(v) for v in fg.adj.values()] == [dict(v) for v in ng.adj.values()]


@pytest.mark.parametrize(
    "fnx_ctor",
    [fnx.Graph, fnx.DiGraph],
)
def test_adj_get_matches_upstream_defaults(fnx_ctor):
    fg = fnx_ctor()
    fg.add_edges_from([(1, 2), (2, 3)])

    assert fg.adj.get(99) is None
    assert fg.adj.get(99, "sentinel") == "sentinel"
    assert dict(fg.adj.get(1)) == {2: {}}


def test_reverse_view_adj_exposes_mapping_helpers():
    fg = fnx.DiGraph()
    fg.add_edges_from([(1, 2), (2, 3), (3, 4)])
    ng = nx.DiGraph()
    ng.add_edges_from([(1, 2), (2, 3), (3, 4)])

    frv = fnx.reverse_view(fg)
    nrv = nx.reverse_view(ng)

    for attr in ("items", "keys", "values", "get"):
        assert hasattr(frv.adj, attr), f"reverse_view.adj is missing {attr}"

    assert list(frv.adj.keys()) == list(nrv.adj.keys())
    assert [(k, dict(v)) for k, v in frv.adj.items()] == [
        (k, dict(v)) for k, v in nrv.adj.items()
    ]
    assert [dict(v) for v in frv.adj.values()] == [dict(v) for v in nrv.adj.values()]
    assert frv.adj.get(99) is None
    assert frv.adj.get(99, "sentinel") == "sentinel"
