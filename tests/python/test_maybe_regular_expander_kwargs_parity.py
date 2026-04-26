"""Parity for ``maybe_regular_expander`` keyword-only kwargs.

Self-review found that ``fnx.maybe_regular_expander(n, d, seed=None)``
was missing nx's keyword-only ``create_using=None`` and
``max_tries=100``. The longer-form ``maybe_regular_expander_graph``
had them; the public alias did not. Drop-in callers passing either
kwarg hit ``TypeError``. Aligned the alias signature.
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
def test_signature_matches_networkx():
    fnx_sig = inspect.signature(fnx.maybe_regular_expander)
    nx_sig = inspect.signature(nx.maybe_regular_expander)
    fnx_params = list(fnx_sig.parameters.keys())
    nx_params = [k for k in nx_sig.parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params

    # Confirm KEYWORD_ONLY for the three after n, d
    for name in ("create_using", "max_tries", "seed"):
        assert (
            fnx_sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        ), f"{name} should be KEYWORD_ONLY"


@needs_nx
def test_default_path_returns_simple_graph():
    G = fnx.maybe_regular_expander(12, 4, seed=42)
    assert G.number_of_nodes() == 12
    assert all(G.degree[n] == 4 for n in G.nodes())
    assert not G.is_multigraph()
    assert not G.is_directed()


@needs_nx
def test_create_using_multigraph():
    G = fnx.maybe_regular_expander(12, 4, create_using=fnx.MultiGraph, seed=42)
    assert G.is_multigraph()
    assert not G.is_directed()
    assert G.number_of_nodes() == 12


@needs_nx
def test_max_tries_kwarg_accepted():
    """max_tries shouldn't change the structure for an easy case but
    must not raise."""
    G = fnx.maybe_regular_expander(12, 4, max_tries=500, seed=42)
    assert G.number_of_nodes() == 12
    assert all(G.degree[n] == 4 for n in G.nodes())


@needs_nx
def test_kwargs_are_keyword_only():
    """create_using/max_tries/seed must be keyword-only — positional
    must raise."""
    with pytest.raises(TypeError):
        fnx.maybe_regular_expander(12, 4, fnx.MultiGraph)  # 3rd positional
