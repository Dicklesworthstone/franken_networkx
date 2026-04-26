"""Parity for Graph class method parameter names.

Bead br-r37-c1-lb47c. fnx's Graph / DiGraph / MultiGraph / MultiDiGraph
class methods used the wrong parameter names:

- ``has_node(node)`` vs nx's ``has_node(n)``
- ``neighbors(node)`` vs ``neighbors(n)``
- ``remove_node(node)`` vs ``remove_node(n)``
- ``remove_edges_from(bunch)`` vs ``remove_edges_from(ebunch)``
- ``Graph.has_edge(u, v, key=None)`` had an extra ``key`` slot that
  only belongs on ``MultiGraph.has_edge`` per nx's contract

Drop-in callers using the kwarg form (``G.has_node(n=x)``) hit
TypeError. Fixed by renaming the wrappers and splitting
_private_aware_has_edge into ``_simple`` (Graph/DiGraph: u, v) and
``_multi`` (MG/MDG: u, v, key=None) variants.
"""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


# ---------------------------------------------------------------------------
# has_node / neighbors / remove_node — all four classes
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
    ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"],
)
def test_has_node_signature_uses_n(fnx_cls, nx_cls):
    g = fnx_cls()
    nx_g = nx_cls()
    assert (
        list(inspect.signature(g.has_node).parameters.keys())
        == list(inspect.signature(nx_g.has_node).parameters.keys())
        == ["n"]
    )


@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ],
    ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"],
)
def test_neighbors_signature_uses_n(fnx_cls, nx_cls):
    g = fnx_cls()
    nx_g = nx_cls()
    assert (
        list(inspect.signature(g.neighbors).parameters.keys())
        == list(inspect.signature(nx_g.neighbors).parameters.keys())
        == ["n"]
    )


# ---------------------------------------------------------------------------
# has_edge: simple Graph/DiGraph (u, v) vs MG/MDG (u, v, key=None)
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
    ids=["Graph", "DiGraph"],
)
def test_has_edge_simple_signature_is_u_v_only(fnx_cls, nx_cls):
    g = fnx_cls()
    nx_g = nx_cls()
    fnx_params = list(inspect.signature(g.has_edge).parameters.keys())
    nx_params = list(inspect.signature(nx_g.has_edge).parameters.keys())
    assert fnx_params == nx_params == ["u", "v"]


@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.MultiGraph, nx.MultiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)],
    ids=["MultiGraph", "MultiDiGraph"],
)
def test_has_edge_multi_signature_includes_key(fnx_cls, nx_cls):
    g = fnx_cls()
    nx_g = nx_cls()
    fnx_params = list(inspect.signature(g.has_edge).parameters.keys())
    nx_params = list(inspect.signature(nx_g.has_edge).parameters.keys())
    assert fnx_params == nx_params == ["u", "v", "key"]


# ---------------------------------------------------------------------------
# Behavioural: kwarg-form calls work
# ---------------------------------------------------------------------------

@needs_nx
def test_has_node_n_kwarg_works():
    G = fnx.Graph()
    G.add_node(0)
    assert G.has_node(n=0) is True
    assert G.has_node(n=99) is False


@needs_nx
def test_neighbors_n_kwarg_works():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2)])
    nbrs = list(G.neighbors(n=1))
    assert sorted(nbrs) == [0, 2]


@needs_nx
def test_simple_graph_has_edge_rejects_third_positional():
    """Graph.has_edge should reject a 3rd positional argument."""
    G = fnx.Graph()
    G.add_edge(0, 1)
    with pytest.raises(TypeError):
        G.has_edge(0, 1, "extra-arg")


@needs_nx
def test_multigraph_has_edge_with_key_works():
    MG = fnx.MultiGraph()
    MG.add_edge(0, 1, key="a")
    assert MG.has_edge(0, 1) is True
    assert MG.has_edge(0, 1, key="a") is True
    assert MG.has_edge(0, 1, key="b") is False


@needs_nx
def test_get_edge_data_still_works_on_simple_graph():
    """Internal call site updated to skip key on Graph/DiGraph; the
    overall surface shouldn't regress."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    assert G.get_edge_data(0, 1) == {"weight": 2.5}
    assert G.get_edge_data(99, 100, default="missing") == "missing"
