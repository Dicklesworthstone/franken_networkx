"""More parity for directed-only function error wording.

Bead br-r37-c1-1ewpw — continuation of br-r37-c1-yf4tf and
br-r37-c1-4elbw. Four more drifts:

- ``weakly_connected_components`` /
  ``number_weakly_connected_components`` raised
  ``'<name> is not defined for undirected graphs. ...'`` on undirected
  inputs; nx raises ``'not implemented for undirected type'``.
- ``topological_generations`` raised ``'Topological generations not
  defined on undirected graphs.'``; nx uses ``'Topological sort not
  defined on undirected graphs.'`` (same as ``topological_sort``).
- ``transitive_closure_dag`` silently ran on undirected input; nx
  raises ``NetworkXNotImplemented('not implemented for undirected
  type')``.
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
# weakly_connected_components family
# ---------------------------------------------------------------------------

@needs_nx
def test_weakly_connected_components_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        list(fnx.weakly_connected_components(G))
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        list(nx.weakly_connected_components(GX))
    assert str(fnx_exc.value) == str(nx_exc.value) == "not implemented for undirected type"


@needs_nx
def test_number_weakly_connected_components_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.number_weakly_connected_components(G)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.number_weakly_connected_components(GX)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# topological_generations
# ---------------------------------------------------------------------------

@needs_nx
def test_topological_generations_undirected_uses_topological_sort_wording():
    """nx says 'Topological sort not defined' even for the
    generations function — fnx should match."""
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        list(fnx.topological_generations(G))
    with pytest.raises(nx.NetworkXError) as nx_exc:
        list(nx.topological_generations(GX))
    assert str(fnx_exc.value) == str(nx_exc.value)
    assert "Topological sort not defined" in str(fnx_exc.value)


# ---------------------------------------------------------------------------
# transitive_closure_dag
# ---------------------------------------------------------------------------

@needs_nx
def test_transitive_closure_dag_undirected_raises_not_implemented():
    """Previously fnx silently returned a result on undirected input."""
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        fnx.transitive_closure_dag(G)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.transitive_closure_dag(GX)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Regression: directed-happy paths must still work
# ---------------------------------------------------------------------------

@needs_nx
def test_weakly_connected_components_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    f = sorted(frozenset(c) for c in fnx.weakly_connected_components(DG))
    n = sorted(frozenset(c) for c in nx.weakly_connected_components(DGX))
    assert f == n


@needs_nx
def test_number_weakly_connected_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (2, 3)])
    DGX = nx.DiGraph([(0, 1), (2, 3)])
    assert fnx.number_weakly_connected_components(DG) == nx.number_weakly_connected_components(DGX) == 2


@needs_nx
def test_topological_generations_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    DGX = nx.DiGraph([(0, 1), (0, 2), (1, 3), (2, 3)])
    f = [sorted(g) for g in fnx.topological_generations(DG)]
    n = [sorted(g) for g in nx.topological_generations(DGX)]
    assert f == n


@needs_nx
def test_transitive_closure_dag_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert sorted(fnx.transitive_closure_dag(DG).edges) == sorted(nx.transitive_closure_dag(DGX).edges)
