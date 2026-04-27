"""Parity for algebraic_connectivity on directed graphs.

Bead br-r37-c1-d8qdy. ``fnx.algebraic_connectivity`` silently
computed a Fiedler value on directed graphs; nx is
``@not_implemented_for('directed')`` and raises
NetworkXNotImplemented.

Repro:
    >>> g = fnx.DiGraph([(1, 2), (2, 1)])
    >>> fnx.algebraic_connectivity(g)
    2.0
    >>> nx.algebraic_connectivity(nx.DiGraph([(1, 2), (2, 1)]))
    NetworkXNotImplemented: not implemented for directed type

Sister functions ``fiedler_vector`` (already raised on directed)
and ``spectral_ordering`` (correctly accepts both per nx's contract)
were already correct — only ``algebraic_connectivity`` was the
remaining outlier.
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
def test_algebraic_connectivity_rejects_directed(cls_name):
    G = getattr(fnx, cls_name)([(1, 2), (2, 1)])
    GX = getattr(nx, cls_name)([(1, 2), (2, 1)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        fnx.algebraic_connectivity(G)
    with pytest.raises(
        nx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        nx.algebraic_connectivity(GX)


@needs_nx
def test_algebraic_connectivity_directed_caught_by_nx_class():
    """Drop-in: fnx-raised NetworkXNotImplemented must be catchable
    via ``except nx.NetworkXNotImplemented``."""
    G = fnx.DiGraph([(1, 2)])
    try:
        fnx.algebraic_connectivity(G)
    except nx.NetworkXNotImplemented:
        return
    pytest.fail(
        "fnx.algebraic_connectivity should raise NetworkXNotImplemented on directed input"
    )


@needs_nx
def test_algebraic_connectivity_undirected_unchanged():
    """Regression guard — undirected inputs must continue to compute
    the algebraic connectivity (Fiedler value)."""
    G = fnx.path_graph(4)
    GX = nx.path_graph(4)
    assert abs(fnx.algebraic_connectivity(G) - nx.algebraic_connectivity(GX)) < 1e-9


@needs_nx
def test_algebraic_connectivity_empty_still_raises_less_than_two_nodes():
    """Pre-existing parity (br-r37-c1-pb97z) preserved: empty/null
    graph raises NetworkXError. The new directed guard fires before
    the size check, but ``fnx.Graph()`` is undirected so the size
    check still applies."""
    with pytest.raises(fnx.NetworkXError, match=r"less than two nodes"):
        fnx.algebraic_connectivity(fnx.Graph())
    with pytest.raises(nx.NetworkXError, match=r"less than two nodes"):
        nx.algebraic_connectivity(nx.Graph())


@needs_nx
def test_algebraic_connectivity_normalized_directed_also_rejects():
    """The normalized=True path must also raise on directed input;
    the type check fires before the dispatch into the normalized
    Laplacian solver."""
    G = fnx.DiGraph([(1, 2), (2, 1)])
    with pytest.raises(
        fnx.NetworkXNotImplemented,
        match=r"not implemented for directed type",
    ):
        fnx.algebraic_connectivity(G, normalized=True)
