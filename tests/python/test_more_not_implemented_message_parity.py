"""More parity for ``NetworkXNotImplemented`` / ``NetworkXError`` messages.

Bead br-r37-c1-4elbw — continuation of br-r37-c1-yf4tf. Seven more
functions diverged from nx's exact error wording:

- ``strongly_connected_components`` / ``number_strongly_connected_components``
  / ``kosaraju_strongly_connected_components`` / ``condensation`` raised
  ``'<name> is not defined for undirected graphs. ...'``;
  nx raises ``'not implemented for undirected type'``.
- ``in_degree_centrality`` / ``out_degree_centrality`` raised similar
  custom text.
- ``flow_hierarchy`` raised ``NetworkXError('flow_hierarchy requires a
  DiGraph')``; nx raises ``NetworkXError('G must be a digraph in
  flow_hierarchy')``.
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


# Functions that should raise NetworkXNotImplemented with nx's standard
# 'not implemented for undirected type' message when given an undirected
# graph.
NOT_IMPL_UNDIRECTED = [
    "strongly_connected_components",
    "number_strongly_connected_components",
    "kosaraju_strongly_connected_components",
    "condensation",
    "in_degree_centrality",
    "out_degree_centrality",
]


@needs_nx
@pytest.mark.parametrize("name", NOT_IMPL_UNDIRECTED)
def test_undirected_message_matches_networkx(name):
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)

    def _consume(result):
        # iterate generators; ignore non-iterable results
        if hasattr(result, "__iter__") and not isinstance(result, dict):
            list(result)

    with pytest.raises(fnx.NetworkXNotImplemented) as fnx_exc:
        _consume(getattr(fnx, name)(G))
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        _consume(getattr(nx, name)(GX))
    assert str(fnx_exc.value) == str(nx_exc.value) == "not implemented for undirected type"


@needs_nx
def test_flow_hierarchy_undirected_message_matches_networkx():
    G = fnx.path_graph(3)
    GX = nx.path_graph(3)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.flow_hierarchy(G)
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.flow_hierarchy(GX)
    assert str(fnx_exc.value) == str(nx_exc.value) == "G must be a digraph in flow_hierarchy"


# ---------------------------------------------------------------------------
# Regression: directed-happy-path must still work
# ---------------------------------------------------------------------------

@needs_nx
def test_strongly_connected_components_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    f = sorted(frozenset(c) for c in fnx.strongly_connected_components(DG))
    n = sorted(frozenset(c) for c in nx.strongly_connected_components(DGX))
    assert f == n


@needs_nx
def test_number_strongly_connected_components_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.number_strongly_connected_components(DG) == nx.number_strongly_connected_components(DGX) == 3


@needs_nx
def test_in_out_degree_centrality_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    DGX = nx.DiGraph([(0, 1), (1, 2)])
    assert fnx.in_degree_centrality(DG) == nx.in_degree_centrality(DGX)
    assert fnx.out_degree_centrality(DG) == nx.out_degree_centrality(DGX)


@needs_nx
def test_flow_hierarchy_directed_unchanged():
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    DGX = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert fnx.flow_hierarchy(DG) == nx.flow_hierarchy(DGX)


# ---------------------------------------------------------------------------
# 'is not defined for' phrasing must not leak through
# ---------------------------------------------------------------------------

@needs_nx
@pytest.mark.parametrize("name", NOT_IMPL_UNDIRECTED)
def test_no_leftover_is_not_defined_message(name):
    G = fnx.path_graph(3)

    def _consume(result):
        if hasattr(result, "__iter__") and not isinstance(result, dict):
            list(result)

    with pytest.raises(fnx.NetworkXNotImplemented) as exc:
        _consume(getattr(fnx, name)(G))
    assert "is not defined for" not in str(exc.value)
