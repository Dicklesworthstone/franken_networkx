"""Parity for ``get_edge_data`` signatures and kwarg behaviour.

Bead br-r37-c1-gyn8z. fnx's _private_aware_get_edge_data used a
generic ``(self, u, v, *args, **kwargs)`` shape on all four Graph
classes. nx exposes:

- ``(u, v, default=None)`` on Graph / DiGraph
- ``(u, v, key=None, default=None)`` on MultiGraph / MultiDiGraph

Drop-in introspection (IDE autocomplete, inspect.signature) returned
the catch-all instead of the documented per-arg surface. Fix splits
the wrapper into ``_simple`` and ``_multi`` variants mirroring the
has_edge split (br-r37-c1-lb47c).
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


def _params(f):
    return [k for k in inspect.signature(f).parameters.keys()
            if k not in ("backend", "backend_kwargs")]


@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.Graph, nx.Graph), (fnx.DiGraph, nx.DiGraph)],
    ids=["Graph", "DiGraph"],
)
def test_simple_get_edge_data_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.get_edge_data) == _params(ng.get_edge_data) == ["u", "v", "default"]


@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.MultiGraph, nx.MultiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)],
    ids=["MultiGraph", "MultiDiGraph"],
)
def test_multi_get_edge_data_signature(fnx_cls, nx_cls):
    g, ng = fnx_cls(), nx_cls()
    assert _params(g.get_edge_data) == _params(ng.get_edge_data) == ["u", "v", "key", "default"]


@needs_nx
def test_simple_default_kwarg_returned_for_missing_edge():
    G = fnx.Graph()
    G.add_edge(0, 1, weight=2.5)
    assert G.get_edge_data(0, 1, default="X") == {"weight": 2.5}
    assert G.get_edge_data(99, 100, default="MISSING") == "MISSING"


@needs_nx
def test_simple_default_positional_returned_for_missing_edge():
    G = fnx.Graph()
    assert G.get_edge_data(0, 1, "MISSING") == "MISSING"


@needs_nx
def test_simple_rejects_third_positional_beyond_default():
    G = fnx.Graph()
    G.add_edge(0, 1)
    with pytest.raises(TypeError):
        G.get_edge_data(0, 1, "default", "extra")


@needs_nx
def test_multi_key_kwarg_returned():
    MG = fnx.MultiGraph()
    MG.add_edge(0, 1, key="a", weight=1)
    MG.add_edge(0, 1, key="b", weight=2)
    assert MG.get_edge_data(0, 1, key="a") == {"weight": 1}
    assert MG.get_edge_data(0, 1, key="b") == {"weight": 2}


@needs_nx
def test_multi_default_kwarg_for_missing_key():
    MG = fnx.MultiGraph()
    MG.add_edge(0, 1, key="a")
    assert MG.get_edge_data(0, 1, key="z", default="NONE") == "NONE"


@needs_nx
def test_multi_default_positional_returned_for_missing_edge():
    MG = fnx.MultiGraph()
    assert MG.get_edge_data(99, 100, None, "MISSING") == "MISSING"


@needs_nx
def test_simple_no_args_returns_all_keys_dict():
    """Without key=, get_edge_data returns the full attr dict, not None."""
    G = fnx.Graph()
    G.add_edge(0, 1, weight=1, color="red")
    assert G.get_edge_data(0, 1) == {"weight": 1, "color": "red"}


@needs_nx
def test_multi_no_key_returns_full_attr_dict():
    """nx contract: without key=, multigraph get_edge_data returns the
    {key: attrs} dict for that pair."""
    MG = fnx.MultiGraph()
    MG.add_edge(0, 1, key="a", w=1)
    MG.add_edge(0, 1, key="b", w=2)
    result = MG.get_edge_data(0, 1)
    nx_g = nx.MultiGraph()
    nx_g.add_edge(0, 1, key="a", w=1)
    nx_g.add_edge(0, 1, key="b", w=2)
    expected = nx_g.get_edge_data(0, 1)
    assert dict(result) == dict(expected)
