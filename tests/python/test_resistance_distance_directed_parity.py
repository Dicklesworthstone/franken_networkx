"""Parity for resistance_distance on directed inputs.

Bead br-r37-c1-b7huh. ``fnx.resistance_distance`` silently computed
a numerically-meaningless asymmetric matrix on DiGraph and
MultiDiGraph inputs. nx is decorated with
``@not_implemented_for('directed')`` and raises
NetworkXNotImplemented.

Resistance distance is mathematically defined for undirected
(electrical network) graphs only. Applying it to a digraph treats
each directed edge as a resistor in one direction, producing an
asymmetric pseudo-inverse-of-Laplacian computation that doesn't
correspond to any meaningful physical quantity.

This was the only function found in an audit of all 106 nx
functions decorated with ``@not_implemented_for('directed')`` that
had a fnx parity gap.
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
@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_directed_input_raises_not_implemented(cls_name):
    G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 3)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        fnx.resistance_distance(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"^not implemented for directed type$",
    ):
        nx.resistance_distance(GX)


@needs_nx
def test_directed_with_node_args_also_raises():
    """The pair-form (nodeA / nodeB given) must also raise; the
    type guard fires before any pair-specific dispatch."""
    G = fnx.DiGraph([(1, 2), (2, 3)])
    GX = nx.DiGraph([(1, 2), (2, 3)])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.resistance_distance(G, 1, 2)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.resistance_distance(GX, 1, 2)


@needs_nx
def test_directed_caught_by_nx_class():
    """Drop-in: fnx-raised exception catchable via
    ``except nx.NetworkXNotImplemented``."""
    G = fnx.DiGraph([(1, 2)])
    try:
        fnx.resistance_distance(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        "fnx.resistance_distance should raise NetworkXNotImplemented on directed input"
    )


@needs_nx
def test_undirected_unchanged():
    """Regression guard — the happy path on undirected Graph
    continues to compute the same resistance distances as nx."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 1)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 1)])
    f = fnx.resistance_distance(G)
    n = nx.resistance_distance(GX)
    # dict-of-dicts; check keys and a sample pairwise value.
    assert set(f.keys()) == set(n.keys())
    for u in f:
        for v in f[u]:
            assert abs(f[u][v] - n[u][v]) < 1e-9, (u, v, f[u][v], n[u][v])


@needs_nx
def test_undirected_pair_form_unchanged():
    """The (nodeA, nodeB) pair form continues to work on undirected."""
    G = fnx.Graph([(1, 2), (2, 3), (3, 1)])
    GX = nx.Graph([(1, 2), (2, 3), (3, 1)])
    assert abs(
        fnx.resistance_distance(G, 1, 3) - nx.resistance_distance(GX, 1, 3)
    ) < 1e-9


@needs_nx
def test_undirected_multigraph_unchanged():
    """MultiGraph (undirected + multi) continues to work — nx allows
    it for resistance_distance (only the directed decorator applies)."""
    G = fnx.MultiGraph([(1, 2), (2, 3), (3, 1)])
    GX = nx.MultiGraph([(1, 2), (2, 3), (3, 1)])
    f = fnx.resistance_distance(G)
    n = nx.resistance_distance(GX)
    assert set(f.keys()) == set(n.keys())
