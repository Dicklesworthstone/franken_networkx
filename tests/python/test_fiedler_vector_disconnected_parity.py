"""Parity for fiedler_vector on disconnected and small graphs.

Bead br-r37-c1-s22qo. ``fnx.fiedler_vector`` silently returned a
numerically-meaningless eigenvector for the second-smallest
eigenvalue when the input was disconnected. nx raises
``NetworkXError('graph is not connected.')``.

Sister spectral functions ``algebraic_connectivity`` and
``spectral_ordering`` already raised correctly on the same inputs;
``fiedler_vector`` was the outlier.
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
def test_disconnected_two_components_raises():
    G = fnx.Graph([(1, 2), (3, 4)])
    GX = nx.Graph([(1, 2), (3, 4)])
    with pytest.raises(fnx.NetworkXError, match=r"^graph is not connected\.$"):
        fnx.fiedler_vector(G)
    with pytest.raises(nx.NetworkXError, match=r"^graph is not connected\.$"):
        nx.fiedler_vector(GX)


@needs_nx
def test_disconnected_only_self_loops_raises():
    G = fnx.Graph([(1, 1), (2, 2)])
    GX = nx.Graph([(1, 1), (2, 2)])
    with pytest.raises(fnx.NetworkXError, match=r"^graph is not connected\.$"):
        fnx.fiedler_vector(G)
    with pytest.raises(nx.NetworkXError, match=r"^graph is not connected\.$"):
        nx.fiedler_vector(GX)


@needs_nx
def test_single_node_raises_less_than_two_nodes():
    G = fnx.Graph()
    G.add_node(0)
    GX = nx.Graph()
    GX.add_node(0)
    with pytest.raises(fnx.NetworkXError, match=r"less than two nodes"):
        fnx.fiedler_vector(G)
    with pytest.raises(nx.NetworkXError, match=r"less than two nodes"):
        nx.fiedler_vector(GX)


@needs_nx
def test_empty_graph_raises_less_than_two_nodes():
    with pytest.raises(fnx.NetworkXError, match=r"less than two nodes"):
        fnx.fiedler_vector(fnx.Graph())
    with pytest.raises(nx.NetworkXError, match=r"less than two nodes"):
        nx.fiedler_vector(nx.Graph())


@needs_nx
def test_connected_path_graph_unchanged_after_fix():
    """Regression guard — the connected-graph happy path must continue
    to yield the same Fiedler vector (up to sign and small numerical
    noise) as nx."""
    import numpy as np

    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    f = fnx.fiedler_vector(G)
    n = nx.fiedler_vector(GX)
    # Sign of an eigenvector is arbitrary; compare absolute values.
    # nx uses an iterative solver (tracemin_pcg) so its output has
    # ~1e-8 noise relative to fnx's dense eigh.
    assert np.allclose(np.abs(f), np.abs(n), atol=1e-6)


@needs_nx
def test_connected_complete_graph_unchanged_after_fix():
    import numpy as np

    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    f = fnx.fiedler_vector(G)
    n = nx.fiedler_vector(GX)
    assert f.shape == n.shape == (4,)


@needs_nx
def test_disconnected_caught_by_nx_class():
    """Drop-in: fnx-raised NetworkXError must be catchable via
    ``except nx.NetworkXError`` since fnx's exception hierarchy is
    registered as a subclass of nx's."""
    G = fnx.Graph([(1, 2), (3, 4)])
    try:
        fnx.fiedler_vector(G)
    except nx.NetworkXError:
        return
    pytest.fail("fnx.fiedler_vector should raise NetworkXError on disconnected input")


@needs_nx
@pytest.mark.parametrize("normalized", [False, True])
def test_disconnected_raises_for_both_normalized_modes(normalized):
    """Both the regular and normalized-Laplacian paths must raise on
    disconnected inputs."""
    G = fnx.Graph([(1, 2), (3, 4)])
    GX = nx.Graph([(1, 2), (3, 4)])
    with pytest.raises(fnx.NetworkXError, match=r"^graph is not connected\.$"):
        fnx.fiedler_vector(G, normalized=normalized)
    with pytest.raises(nx.NetworkXError, match=r"^graph is not connected\.$"):
        nx.fiedler_vector(GX, normalized=normalized)
