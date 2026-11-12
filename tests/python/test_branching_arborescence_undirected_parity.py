"""Parity for branching/arborescence functions on undirected input.

Bead br-r37-c1-ugod2. Four functions diverged from nx on undirected
input:

- ``maximum_branching`` raised NetworkXNotImplemented; nx returns the
  maximum-weight spanning Graph result.
- ``minimum_branching`` raised NetworkXNotImplemented; nx returns an
  empty Graph (lowest sum is no edges).
- ``maximum_spanning_arborescence`` and ``minimum_spanning_arborescence``
  raised with custom message ``'<name> is only implemented for
  directed graphs.'`` instead of nx's standard ``'not implemented for
  undirected type'``.

Drop-in code that uses these on undirected breaks or fails to match
nx's exact NotImplemented message.
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


# ---------------------------------------------------------------------------
# Branching: should accept undirected (delegate to nx)
# ---------------------------------------------------------------------------

@needs_nx
def test_minimum_branching_undirected_returns_empty_graph():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    f = fnx.minimum_branching(G)
    n = nx.minimum_branching(GX)
    assert sorted(f.edges) == sorted(n.edges) == []


@needs_nx
def test_maximum_branching_undirected_returns_max_spanning():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    f = fnx.maximum_branching(G)
    n = nx.maximum_branching(GX)
    assert sorted(f.edges) == sorted(n.edges)


@needs_nx
def test_branching_undirected_does_not_raise():
    """Regression: must not raise the old custom NotImplemented."""
    G = fnx.path_graph(3)
    fnx.minimum_branching(G)  # must not raise
    fnx.maximum_branching(G)  # must not raise


# ---------------------------------------------------------------------------
# Arborescence: must raise with nx's exact message
# ---------------------------------------------------------------------------

@needs_nx
def test_minimum_spanning_arborescence_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.minimum_spanning_arborescence(G)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.minimum_spanning_arborescence(GX)
    assert str(fnx_exc.value) == str(nx_exc.value) == "not implemented for undirected type"


@needs_nx
def test_maximum_spanning_arborescence_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.maximum_spanning_arborescence(G)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.maximum_spanning_arborescence(GX)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_arborescence_no_leftover_only_implemented_message():
    """The fnx-specific 'is only implemented for directed' wording must
    not leak through the fix."""
    G = fnx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as exc1:
        fnx.minimum_spanning_arborescence(G)
    assert "only implemented for" not in str(exc1.value)
    with pytest.raises(fnx.NetworkXNotImplemented) as exc2:
        fnx.maximum_spanning_arborescence(G)
    assert "only implemented for" not in str(exc2.value)


# ---------------------------------------------------------------------------
# Regression: directed paths still work
# ---------------------------------------------------------------------------

@needs_nx
def test_minimum_branching_directed_unchanged():
    DG = fnx.DiGraph([(0, 1, {"weight": 2}), (0, 2, {"weight": 1})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2}), (0, 2, {"weight": 1})])
    f = sorted(fnx.minimum_branching(DG).edges)
    n = sorted(nx.minimum_branching(DGX).edges)
    assert f == n


@needs_nx
def test_maximum_branching_directed_unchanged():
    DG = fnx.DiGraph([(0, 1, {"weight": 2}), (1, 2, {"weight": 3})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2}), (1, 2, {"weight": 3})])
    assert sorted(fnx.maximum_branching(DG).edges) == sorted(nx.maximum_branching(DGX).edges)


@needs_nx
def test_minimum_spanning_arborescence_directed_unchanged():
    DG = fnx.DiGraph([(0, 1, {"weight": 2}), (0, 2, {"weight": 1}), (1, 2, {"weight": 3})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2}), (0, 2, {"weight": 1}), (1, 2, {"weight": 3})])
    f = sorted(fnx.minimum_spanning_arborescence(DG).edges)
    n = sorted(nx.minimum_spanning_arborescence(DGX).edges)
    assert f == n


@needs_nx
def test_maximum_spanning_arborescence_directed_unchanged():
    DG = fnx.DiGraph([(0, 1, {"weight": 2}), (1, 2, {"weight": 3})])
    DGX = nx.DiGraph([(0, 1, {"weight": 2}), (1, 2, {"weight": 3})])
    f = sorted(fnx.maximum_spanning_arborescence(DG).edges)
    n = sorted(nx.maximum_spanning_arborescence(DGX).edges)
    assert f == n
