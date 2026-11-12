"""Parity for ``fnx.describe(G, describe_hook=...)``.

Bead br-r37-c1-pyx0a. fnx.describe used to accept only ``(G,)``,
shadowing nx's documented ``(G, describe_hook=None)``. Drop-in code
passing a hook callable hit TypeError on fnx but worked on nx.
"""

from __future__ import annotations

import inspect
import io
from contextlib import redirect_stdout

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_describe_signature_matches_networkx():
    fnx_params = list(inspect.signature(fnx.describe).parameters.keys())
    nx_params = [k for k in inspect.signature(nx.describe).parameters.keys()
                 if k not in ("backend", "backend_kwargs")]
    assert fnx_params == nx_params == ["G", "describe_hook"]


@needs_nx
def test_describe_hook_kwarg_merges_extra_properties():
    G = fnx.path_graph(5)

    def extra(graph):
        return {"My custom field": 42}

    buf = io.StringIO()
    with redirect_stdout(buf):
        fnx.describe(G, describe_hook=extra)
    out = buf.getvalue()

    assert "Number of nodes" in out
    assert "My custom field" in out
    assert "42" in out


@needs_nx
def test_describe_hook_none_unchanged():
    """Backwards-compat: no hook still works."""
    G = fnx.path_graph(3)
    buf = io.StringIO()
    with redirect_stdout(buf):
        fnx.describe(G)
    assert "Number of nodes" in buf.getvalue()


@needs_nx
def test_describe_hook_falsy_dict_skipped():
    """An empty hook dict shouldn't add a blank section."""
    G = fnx.path_graph(3)

    def empty_hook(graph):
        return {}

    buf = io.StringIO()
    with redirect_stdout(buf):
        fnx.describe(G, describe_hook=empty_hook)
    assert "Number of nodes" in buf.getvalue()


@needs_nx
def test_describe_hook_positional_call():
    """nx accepts describe_hook positionally; fnx should too."""
    G = fnx.path_graph(3)

    def aug(graph):
        return {"Hook field": "yes"}

    buf = io.StringIO()
    with redirect_stdout(buf):
        fnx.describe(G, aug)
    assert "Hook field" in buf.getvalue()
    assert "yes" in buf.getvalue()
