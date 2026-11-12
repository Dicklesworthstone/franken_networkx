"""Parity for null-graph exception behaviour.

Bead br-r37-c1-pb97z. Three functions silently returned valid-looking
values on null/single-node graphs where nx raises specific exceptions:

- ``barycenter(empty_graph(0))`` returned ``[]``;
  nx raises ``NetworkXPointlessConcept('G has no nodes.')``.
- ``algebraic_connectivity(empty_graph(0))`` and
  ``algebraic_connectivity(empty_graph(1))`` returned ``0.0``;
  nx raises ``NetworkXError('graph has less than two nodes.')``.
- ``local_efficiency(empty_graph(0))`` returned ``0.0``;
  nx raises ``ZeroDivisionError('division by zero')``.

Drop-in code that catches these specific exceptions to gate empty-graph
paths failed to trigger on fnx — silent values masked the contract
violation.
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
# barycenter
# ---------------------------------------------------------------------------

@needs_nx
def test_barycenter_null_graph_raises_pointless_concept():
    G = fnx.empty_graph(0)
    nx_g = nx.empty_graph(0)
    with pytest.raises(fnx.NetworkXPointlessConcept) as fnx_exc:
        fnx.barycenter(G)
    with pytest.raises(nx.NetworkXPointlessConcept) as nx_exc:
        nx.barycenter(nx_g)
    assert str(fnx_exc.value) == str(nx_exc.value) == "G has no nodes."


@needs_nx
def test_barycenter_normal_case_unchanged():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    assert sorted(fnx.barycenter(G)) == sorted(nx.barycenter(GX))


@needs_nx
def test_barycenter_with_kwargs_on_null_graph_also_raises():
    G = fnx.empty_graph(0)
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx.barycenter(G, weight="weight")


# ---------------------------------------------------------------------------
# algebraic_connectivity
# ---------------------------------------------------------------------------

@needs_nx
def test_algebraic_connectivity_null_graph_raises_networkxerror():
    G = fnx.empty_graph(0)
    nx_g = nx.empty_graph(0)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.algebraic_connectivity(G)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.algebraic_connectivity(nx_g)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_algebraic_connectivity_single_node_raises_networkxerror():
    """nx requires >= 2 nodes; the single-node case must also raise."""
    G = fnx.empty_graph(1)
    nx_g = nx.empty_graph(1)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.algebraic_connectivity(G)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.algebraic_connectivity(nx_g)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_algebraic_connectivity_normal_case_unchanged():
    G = fnx.path_graph(5)
    GX = nx.path_graph(5)
    assert abs(fnx.algebraic_connectivity(G) - nx.algebraic_connectivity(GX)) < 1e-6


# ---------------------------------------------------------------------------
# local_efficiency
# ---------------------------------------------------------------------------

@needs_nx
def test_local_efficiency_null_graph_raises_zero_division():
    G = fnx.empty_graph(0)
    nx_g = nx.empty_graph(0)
    with pytest.raises(ZeroDivisionError) as fnx_exc:
        fnx.local_efficiency(G)
    with pytest.raises(ZeroDivisionError) as nx_exc:
        nx.local_efficiency(nx_g)
    assert str(fnx_exc.value) == str(nx_exc.value)


@needs_nx
def test_local_efficiency_normal_case_unchanged():
    G = fnx.complete_graph(4)
    GX = nx.complete_graph(4)
    assert fnx.local_efficiency(G) == nx.local_efficiency(GX)


@needs_nx
def test_local_efficiency_single_node_zero_unchanged():
    """Single-node graph: 1 node has no neighbours so its local
    efficiency is 0; the average over 1 node is 0.0 — both libs."""
    G = fnx.empty_graph(1)
    GX = nx.empty_graph(1)
    assert fnx.local_efficiency(G) == nx.local_efficiency(GX) == 0.0
