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
    ("fnx_ctor", "nx_ctor"),
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
)
def test_node_view_reflected_set_algebra_matches_networkx(fnx_ctor, nx_ctor):
    """networkx's NodeView is a collections.abc.Set, so a plain set on the LEFT
    works too; the native NodeView had only the forward operators until
    2026-09-03. Every result is compared against networkx on the same graph.
    """
    fg, ng = fnx_ctor(), nx_ctor()
    for g in (fg, ng):
        g.add_edges_from([("a", "b"), ("b", "c")])
    other = {"a", "z"}
    assert other & fg.nodes == other & ng.nodes == {"a"}
    assert other | fg.nodes == other | ng.nodes == {"a", "b", "c", "z"}
    assert other - fg.nodes == other - ng.nodes == {"z"}
    assert other ^ fg.nodes == other ^ ng.nodes == {"b", "c", "z"}
    # The forward direction must keep giving the same answers.
    assert fg.nodes - other == ng.nodes - other == {"b", "c"}


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
    # Iterable and sized like a list. Integer indexing is NOT part of the
    # contract: networkx's keyed edge view unpacks the subscript as (u, v, k) and
    # raises TypeError on `edges[0]`, and fnx mirrors that.
    edges = fg.edges(keys=True)
    assert len(edges) == 2
    assert next(iter(edges)) in [("a", "b", "k1"), ("b", "c", "k2")]
    with pytest.raises(TypeError):
        edges[0]
    # list(...) roundtrip works.
    assert list(edges) == list(edges)
