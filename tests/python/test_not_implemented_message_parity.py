"""Parity for ``NetworkXNotImplemented`` message text.

Bead br-r37-c1-yf4tf. Three functions raised NetworkXNotImplemented
with custom helpful messages that diverged from nx's standard
``@not_implemented_for`` decorator format:

- ``is_strongly_connected`` raised
  ``'is_strongly_connected is not defined for undirected graphs.
  Use is_connected instead.'``
- ``is_weakly_connected`` raised similar custom text.
- ``immediate_dominators`` raised
  ``'immediate_dominators is not defined for undirected graphs.'``

nx raises the standard ``'not implemented for undirected type'`` for
all three. Drop-in code that asserts on the exact message text broke.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False

needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_is_strongly_connected_on_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.is_strongly_connected(G)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.is_strongly_connected(GX)
    assert str(fnx_exc.value) == str(nx_exc.value) == "not implemented for undirected type"


@needs_nx
def test_is_weakly_connected_on_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.is_weakly_connected(G)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.is_weakly_connected(GX)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_immediate_dominators_on_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.immediate_dominators(G, 0)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.immediate_dominators(GX, 0)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Regression: the directed (happy) paths must still work
# ---------------------------------------------------------------------------

@needs_nx
def test_is_strongly_connected_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert fnx.is_strongly_connected(DG) == nx.is_strongly_connected(DGX) is True


@needs_nx
def test_is_weakly_connected_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.is_weakly_connected(DG) == nx.is_weakly_connected(DGX) is True


@needs_nx
def test_immediate_dominators_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert fnx.immediate_dominators(DG, 0) == nx.immediate_dominators(DGX, 0)


# ---------------------------------------------------------------------------
# Regression: existing test still passes (drop-in 'not implemented for')
# ---------------------------------------------------------------------------

@needs_nx
def test_message_does_not_say_not_defined():
    """The fnx-specific 'is not defined for undirected' wording must
    not leak through after the fix."""
    G = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as exc:
        fnx.is_strongly_connected(G)
    assert "is not defined for" not in str(exc.value)
    with pytest.raises(fnx.NetworkXNotImplemented) as exc2:
        fnx.is_weakly_connected(G)
    assert "is not defined for" not in str(exc2.value)
    with pytest.raises(fnx.NetworkXNotImplemented) as exc3:
        fnx.immediate_dominators(G, 0)
    assert "is not defined for" not in str(exc3.value)
