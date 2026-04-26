"""Parity for ``add_*`` / ``remove_*`` kwarg names on Graph classes.

Bead br-r37-c1-wcdm3. fnx's wrappers used internal positional arg
names that differed from nx's documented names:

- ``Graph.add_edge(u, v, **attr)`` vs nx ``(u_of_edge, v_of_edge)``
- ``MultiGraph.add_edge(u, v, key=None, **attr)`` vs nx
  ``(u_for_edge, v_for_edge, key=None)``
- ``add_node(n, **attr)`` vs nx ``(node_for_adding, **attr)``
- ``add_weighted_edges_from(ebunch, ...)`` vs nx
  ``(ebunch_to_add, ...)``
- ``remove_node(node)`` vs nx ``(n,)``
- ``remove_nodes_from(bunch)`` vs nx ``(nodes,)``
- ``remove_edges_from(bunch)`` vs nx ``(ebunch,)``

Drop-in callers using the documented kwarg form
(``G.add_edge(u_of_edge=0, v_of_edge=1)``) hit TypeError on fnx but
worked on nx. Fix renames the params in each Python wrapper to match
nx exactly. Positional callers continue to work unchanged.
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


SIMPLE_PAIRS = [
    (fnx.Graph, nx.Graph) if HAS_NX else None,
    (fnx.DiGraph, nx.DiGraph) if HAS_NX else None,
]
MULTI_PAIRS = [
    (fnx.MultiGraph, nx.MultiGraph) if HAS_NX else None,
    (fnx.MultiDiGraph, nx.MultiDiGraph) if HAS_NX else None,
]
ALL_PAIRS = (SIMPLE_PAIRS + MULTI_PAIRS) if HAS_NX else []


def _params(f):
    return [k for k in inspect.signature(f).parameters.keys()
            if k not in ("backend", "backend_kwargs")]


# ---------------------------------------------------------------------------
# Signature parity — params match nx for all four classes
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", SIMPLE_PAIRS,
                         ids=["Graph", "DiGraph"])
def test_simple_add_edge_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.add_edge) == _params(ng.add_edge) == ["u_of_edge", "v_of_edge", "attr"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", MULTI_PAIRS,
                         ids=["MultiGraph", "MultiDiGraph"])
def test_multi_add_edge_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.add_edge) == _params(ng.add_edge) == ["u_for_edge", "v_for_edge", "key", "attr"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", ALL_PAIRS,
                         ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_add_node_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.add_node) == _params(ng.add_node) == ["node_for_adding", "attr"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", ALL_PAIRS,
                         ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_add_weighted_edges_from_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.add_weighted_edges_from) == _params(ng.add_weighted_edges_from) == ["ebunch_to_add", "weight", "attr"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", ALL_PAIRS,
                         ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_remove_node_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.remove_node) == _params(ng.remove_node) == ["n"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", ALL_PAIRS,
                         ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_remove_nodes_from_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.remove_nodes_from) == _params(ng.remove_nodes_from) == ["nodes"]


@needs_nx
@pytest.mark.parametrize("fnx_cls,nx_cls", ALL_PAIRS,
                         ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_remove_edges_from_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.remove_edges_from) == _params(ng.remove_edges_from) == ["ebunch"]


# ---------------------------------------------------------------------------
# Behavioural — the documented nx kwarg form actually works
# ---------------------------------------------------------------------------

@needs_nx
def test_add_edge_kwarg_form_simple():
    G = fnx.Graph()
    G.add_edge(u_of_edge=0, v_of_edge=1, weight=3)
    assert G.has_edge(0, 1)
    assert G[0][1] == {"weight": 3}


@needs_nx
def test_add_edge_kwarg_form_multi():
    MG = fnx.MultiGraph()
    MG.add_edge(u_for_edge=0, v_for_edge=1, key="a", weight=2)
    assert MG.has_edge(0, 1, key="a")


@needs_nx
def test_add_node_kwarg_form():
    G = fnx.Graph()
    G.add_node(node_for_adding=42, color="red")
    assert G.has_node(42)
    assert G.nodes[42] == {"color": "red"}


@needs_nx
def test_add_weighted_edges_from_kwarg_form():
    G = fnx.Graph()
    G.add_weighted_edges_from(ebunch_to_add=[(0, 1, 1.5), (1, 2, 2.5)])
    assert G[0][1]["weight"] == 1.5
    assert G[1][2]["weight"] == 2.5


@needs_nx
def test_remove_node_kwarg_form():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2)])
    G.remove_node(n=1)
    assert not G.has_node(1)


@needs_nx
def test_remove_nodes_from_kwarg_form():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3)])
    G.remove_nodes_from(nodes=[1, 2])
    assert sorted(G.nodes()) == [0, 3]


@needs_nx
def test_remove_edges_from_kwarg_form():
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3)])
    G.remove_edges_from(ebunch=[(0, 1), (2, 3)])
    assert sorted(G.edges()) == [(1, 2)]


# ---------------------------------------------------------------------------
# Backwards-compat — positional callers must still work
# ---------------------------------------------------------------------------

@needs_nx
def test_positional_calls_unchanged():
    G = fnx.Graph()
    G.add_node(0)
    G.add_edge(0, 1)
    G.add_weighted_edges_from([(1, 2, 3.0)])
    G.remove_node(2)
    G.remove_edges_from([(0, 1)])
    G.add_edges_from([(3, 4), (4, 5)])
    G.remove_nodes_from([3])
    assert sorted(G.nodes()) == [0, 1, 4, 5]
