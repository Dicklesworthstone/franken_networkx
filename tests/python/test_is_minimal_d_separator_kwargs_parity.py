"""Parity for ``is_minimal_d_separator`` keyword-only kwargs.

Bead br-r37-c1-0zdk4. fnx had ``is_minimal_d_separator(G, x, y, z)``
while nx accepts keyword-only ``included=None`` and ``restricted=None``
constraints. Drop-in callers passing those kwargs got TypeError on fnx.

Aligned: when either constraint is supplied, delegate to networkx so
behaviour matches; the simple no-constraint path keeps the fnx native
O(|z|) implementation.
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


def _build_pair():
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4)]
    f_g = fnx.DiGraph()
    nx_g = nx.DiGraph()
    for g in (f_g, nx_g):
        g.add_edges_from(edges)
    return f_g, nx_g


@needs_nx
def test_is_minimal_d_separator_signature_includes_kwargs():
    fnx_p = set(inspect.signature(fnx.is_minimal_d_separator).parameters.keys())
    nx_p = set(inspect.signature(nx.is_minimal_d_separator).parameters.keys())
    nx_p -= {"backend", "backend_kwargs"}
    assert nx_p <= fnx_p
    # Both must be keyword-only
    fnx_sig = inspect.signature(fnx.is_minimal_d_separator)
    for name in ("included", "restricted"):
        assert (
            fnx_sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        ), f"{name} should be KEYWORD_ONLY"


@needs_nx
def test_is_minimal_d_separator_default_matches_networkx():
    f_g, nx_g = _build_pair()
    actual = fnx.is_minimal_d_separator(f_g, {0}, {4}, {3})
    expected = nx.is_minimal_d_separator(nx_g, {0}, {4}, {3})
    assert actual == expected


@needs_nx
def test_is_minimal_d_separator_with_restricted_matches_networkx():
    f_g, nx_g = _build_pair()
    actual = fnx.is_minimal_d_separator(
        f_g, {0}, {4}, {3}, restricted={0, 1, 2, 3, 4}
    )
    expected = nx.is_minimal_d_separator(
        nx_g, {0}, {4}, {3}, restricted={0, 1, 2, 3, 4}
    )
    assert actual == expected


@needs_nx
def test_is_minimal_d_separator_with_included_matches_networkx():
    f_g, nx_g = _build_pair()
    actual = fnx.is_minimal_d_separator(f_g, {0}, {4}, {3}, included={3})
    expected = nx.is_minimal_d_separator(nx_g, {0}, {4}, {3}, included={3})
    assert actual == expected


@needs_nx
def test_is_minimal_d_separator_with_both_constraints_matches_networkx():
    f_g, nx_g = _build_pair()
    actual = fnx.is_minimal_d_separator(
        f_g, {0}, {4}, {3}, included={3}, restricted={0, 1, 2, 3, 4}
    )
    expected = nx.is_minimal_d_separator(
        nx_g, {0}, {4}, {3}, included={3}, restricted={0, 1, 2, 3, 4}
    )
    assert actual == expected


@needs_nx
def test_is_minimal_d_separator_rejects_extra_positional():
    """included/restricted are keyword-only — positional must raise."""
    f_g, _ = _build_pair()
    with pytest.raises(TypeError):
        fnx.is_minimal_d_separator(f_g, {0}, {4}, {3}, {3})  # extra positional
