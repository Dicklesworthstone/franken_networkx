"""Parity for ``rescale_layout`` default value.

Bead br-r37-c1-wvh8r. fnx.rescale_layout had default ``scale=1.0``
(float) but networkx.drawing.layout.rescale_layout uses ``scale=1``
(int). Functionally equivalent but inspect.signature() defaults
differed in literal repr — trips signature-snapshot tests and any
tooling comparing default-value literals (typer-style CLIs, doc
generators).
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
def test_rescale_layout_default_scale_matches_networkx():
    fnx_sig = inspect.signature(fnx.rescale_layout)
    nx_sig = inspect.signature(nx.rescale_layout)
    fnx_default = fnx_sig.parameters["scale"].default
    nx_default = nx_sig.parameters["scale"].default
    assert fnx_default == nx_default
    assert type(fnx_default) is type(nx_default)
    assert fnx_default == 1
    assert isinstance(fnx_default, int)


@needs_nx
def test_rescale_layout_default_repr_matches_networkx():
    """The signature repr should print 'scale=1' not 'scale=1.0'."""
    fnx_sig = str(inspect.signature(fnx.rescale_layout))
    assert "scale=1.0" not in fnx_sig
    assert "scale=1" in fnx_sig


@needs_nx
def test_rescale_layout_default_call_still_works():
    """Backwards-compat: positional/kwarg calls without scale still
    rescale to [-1, 1]."""
    import numpy as np
    pos = np.array([[0.0, 0.0], [2.0, 0.0], [-3.0, 4.0]])
    rescaled = fnx.rescale_layout(pos)
    # Largest magnitude should be exactly 1 after rescale.
    assert np.max(np.abs(rescaled)) <= 1.0 + 1e-9


@needs_nx
def test_rescale_layout_explicit_scale_still_works():
    import numpy as np
    pos = np.array([[0.0, 0.0], [1.0, 0.0]])
    rescaled = fnx.rescale_layout(pos, scale=5)
    assert np.max(np.abs(rescaled)) <= 5.0 + 1e-9
