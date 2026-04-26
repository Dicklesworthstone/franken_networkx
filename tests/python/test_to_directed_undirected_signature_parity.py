"""Parity for ``to_directed`` / ``to_undirected`` introspectable signatures.

Bead br-r37-c1-5npb6. The Python wrappers in __init__.py used
``@wraps(rust_impl)`` to copy the docstring from the underlying Rust
binding, but the Rust impl has signature ``()`` — so functools.wraps
poisoned ``inspect.signature(g.to_directed)`` via the ``__wrapped__``
attribute, hiding the Python wrapper's actual ``(self, as_view=False)``
surface.

Drop-in code calling ``inspect.signature(g.to_directed)`` saw a useless
no-arg signature on fnx where nx exposes ``(as_view=False)``. Fix:
stop using ``@wraps``; copy the docstring manually so introspection
reads the wrapper's own def.
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
def test_to_directed_signature_matches_networkx(fnx_cls, nx_cls):
    g = fnx_cls()
    nx_g = nx_cls()
    fnx_params = list(inspect.signature(g.to_directed).parameters.keys())
    nx_params = list(inspect.signature(nx_g.to_directed).parameters.keys())
    assert fnx_params == nx_params == ["as_view"]


@needs_nx
@pytest.mark.parametrize(
    "fnx_cls,nx_cls,expected",
    [
        (fnx.Graph, nx.Graph, ["as_view"]),
        (fnx.DiGraph, nx.DiGraph, ["reciprocal", "as_view"]),
        (fnx.MultiGraph, nx.MultiGraph, ["as_view"]),
        (fnx.MultiDiGraph, nx.MultiDiGraph, ["reciprocal", "as_view"]),
    ],
    ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"],
)
def test_to_undirected_signature_matches_networkx(fnx_cls, nx_cls, expected):
    g = fnx_cls()
    nx_g = nx_cls()
    fnx_params = list(inspect.signature(g.to_undirected).parameters.keys())
    nx_params = list(inspect.signature(nx_g.to_undirected).parameters.keys())
    assert fnx_params == nx_params == expected


@needs_nx
def test_to_directed_as_view_kwarg_works():
    """Behavioural: kwarg-form ``as_view=True`` returns a view."""
    G = fnx.path_graph(4)
    H = G.to_directed(as_view=True)
    assert H.is_directed()
    # Default (no kwarg) returns a copy.
    H2 = G.to_directed()
    assert H2.is_directed()


@needs_nx
def test_to_undirected_as_view_kwarg_works():
    G = fnx.DiGraph()
    G.add_edges_from([(0, 1), (1, 2)])
    H = G.to_undirected(as_view=True)
    assert not H.is_directed()


@needs_nx
def test_digraph_to_undirected_reciprocal_kwarg_works():
    """reciprocal+as_view both reachable on DiGraph."""
    G = fnx.DiGraph()
    G.add_edges_from([(0, 1), (1, 0), (1, 2)])
    H_recip = G.to_undirected(reciprocal=True)
    H_all = G.to_undirected(reciprocal=False)
    assert sorted(H_recip.edges()) == [(0, 1)]
    assert sorted(H_all.edges()) == [(0, 1), (1, 2)]
