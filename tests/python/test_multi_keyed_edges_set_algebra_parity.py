"""Parity coverage for Multi* keyed edge view set algebra.

Bead franken_networkx-y14y: G.edges(keys=True) on MultiGraph /
MultiDiGraph must support set operators (&, |, -, ^) matching upstream
NetworkX, not raise TypeError about list-vs-set operand types.
"""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize(
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_keyed_edges_support_set_algebra(fnx_ctor, nx_ctor):
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1")
    fg.add_edge("b", "c", key="k2")
    ng = nx_ctor()
    ng.add_edge("a", "b", key="k1")
    ng.add_edge("b", "c", key="k2")

    other = {("a", "b", "k1"), ("z", "z", "z")}

    assert fg.edges(keys=True) & other == ng.edges(keys=True) & other
    assert fg.edges(keys=True) | other == ng.edges(keys=True) | other
    assert fg.edges(keys=True) - other == ng.edges(keys=True) - other
    assert fg.edges(keys=True) ^ other == ng.edges(keys=True) ^ other

    # Reflected
    assert other & fg.edges(keys=True) == other & ng.edges(keys=True)
    assert other | fg.edges(keys=True) == other | ng.edges(keys=True)


@pytest.mark.parametrize(
    "fnx_ctor",
    [fnx.MultiGraph, fnx.MultiDiGraph],
)
def test_keyed_edges_still_behave_as_list(fnx_ctor):
    """The returned object supports both list operations AND set algebra —
    existing callers iterating as a list must keep working.
    """
    fg = fnx_ctor()
    fg.add_edge("a", "b", key="k1")
    fg.add_edge("b", "c", key="k2")
    # Iterable + indexable like a list.
    edges = fg.edges(keys=True)
    assert len(edges) == 2
    assert edges[0] in [("a", "b", "k1"), ("b", "c", "k2")]
    # list(...) roundtrip works.
    assert list(edges) == list(edges)
