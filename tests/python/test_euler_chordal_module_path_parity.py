"""Module-path parity for the two graph-returning wrappers that had none.

br-r37-c1-nlzs7 (``franken_networkx.euler.eulerize``) and br-r37-c1-eubxc
(``franken_networkx.chordal.complete_to_chordal_graph``). Both are covered at
the TOP level by existing conformance suites; neither had any assertion on the
submodule route, which is where a namespace can quietly hand back networkx's
function instead (the br-r37-c1-2qsqf class) or a wrapper can lose the fnx
return type.

Both properties are asserted here: the object is not networkx's, the return type
is the fnx class the module promises, and the value matches live networkx.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx
from franken_networkx import chordal as fnx_chordal, euler as fnx_euler


def _edge_multiset(graph):
    """Multiset of undirected edges — eulerize DUPLICATES edges, so a set loses
    exactly the information under test."""
    return sorted(tuple(sorted(map(str, edge))) for edge in graph.edges())


# --------------------------------------------------------------------------- #
# br-r37-c1-nlzs7: euler.eulerize
# --------------------------------------------------------------------------- #

_EULERIZE_FIXTURES = [
    pytest.param([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)], id="chorded-cycle"),
    pytest.param([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], id="cycle5"),
    pytest.param([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)], id="bowtie"),
    pytest.param([(0, 1), (1, 2), (2, 3)], id="path"),
]


def test_euler_module_eulerize_is_not_networkxs_function():
    assert fnx_euler.eulerize is not nx.eulerize


@pytest.mark.parametrize("edges", _EULERIZE_FIXTURES)
def test_euler_module_eulerize_returns_fnx_multigraph(edges):
    """The bead's named contract: the submodule wrapper returns fnx.MultiGraph."""
    result = fnx_euler.eulerize(fnx.Graph(edges))
    assert isinstance(result, fnx.MultiGraph), type(result)


@pytest.mark.parametrize("edges", _EULERIZE_FIXTURES)
def test_euler_module_eulerize_edge_multiset_matches_networkx(edges):
    """Edge MULTISET, not set — eulerize works by duplicating edges."""
    actual = fnx_euler.eulerize(fnx.Graph(edges))
    expected = nx.eulerize(nx.Graph(edges))
    assert _edge_multiset(actual) == _edge_multiset(expected)
    assert sorted(map(str, actual.nodes())) == sorted(map(str, expected.nodes()))


@pytest.mark.parametrize("edges", _EULERIZE_FIXTURES)
def test_euler_module_eulerize_result_is_actually_eulerian(edges):
    """The property the algorithm exists to establish, checked on both sides."""
    actual = fnx_euler.eulerize(fnx.Graph(edges))
    expected = nx.eulerize(nx.Graph(edges))
    # Two separate assertions on purpose. `a == b is True` chains into
    # `(a == b) and (b is True)`, which is not what it looks like and would keep
    # passing if BOTH sides went false.
    assert fnx.is_eulerian(actual) == nx.is_eulerian(expected)
    assert fnx.is_eulerian(actual), "eulerize did not produce an Eulerian graph"


def test_euler_module_eulerize_matches_networkx_on_an_error_shape():
    """A disconnected graph has no eulerization; both sides must agree."""
    disconnected_fnx = fnx.Graph([(0, 1), (2, 3)])
    disconnected_nx = nx.Graph([(0, 1), (2, 3)])

    with pytest.raises(Exception) as fnx_exc:
        fnx_euler.eulerize(disconnected_fnx)
    with pytest.raises(Exception) as nx_exc:
        nx.eulerize(disconnected_nx)
    assert type(fnx_exc.value).__name__ == type(nx_exc.value).__name__


# --------------------------------------------------------------------------- #
# br-r37-c1-eubxc: chordal.complete_to_chordal_graph
# --------------------------------------------------------------------------- #

_CHORDAL_FIXTURES = [
    pytest.param([(0, 1), (1, 2), (2, 3), (3, 0)], id="cycle4"),
    pytest.param([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], id="cycle5"),
    pytest.param([(0, 1), (1, 2), (2, 0)], id="triangle-already-chordal"),
    pytest.param([(0, 1), (0, 2), (0, 3), (1, 2), (2, 3)], id="mixed"),
]


def test_chordal_module_completion_is_not_networkxs_function():
    assert (
        fnx_chordal.complete_to_chordal_graph is not nx.complete_to_chordal_graph
    )


@pytest.mark.parametrize("edges", _CHORDAL_FIXTURES)
def test_chordal_module_completion_returns_fnx_graph(edges):
    """The bead's named contract: the submodule wrapper returns fnx.Graph."""
    result, _alpha = fnx_chordal.complete_to_chordal_graph(fnx.Graph(edges))
    assert isinstance(result, fnx.Graph), type(result)


@pytest.mark.parametrize("edges", _CHORDAL_FIXTURES)
def test_chordal_module_completion_edges_and_alpha_match_networkx(edges):
    """Both halves of the return: the completed graph AND the alpha mapping."""
    actual_graph, actual_alpha = fnx_chordal.complete_to_chordal_graph(
        fnx.Graph(edges)
    )
    expected_graph, expected_alpha = nx.complete_to_chordal_graph(nx.Graph(edges))

    assert _edge_multiset(actual_graph) == _edge_multiset(expected_graph)
    assert sorted(map(str, actual_graph.nodes())) == sorted(
        map(str, expected_graph.nodes())
    )
    assert {str(k): v for k, v in actual_alpha.items()} == {
        str(k): v for k, v in expected_alpha.items()
    }


@pytest.mark.parametrize("edges", _CHORDAL_FIXTURES)
def test_chordal_module_completion_result_is_chordal(edges):
    """The property the algorithm exists to establish."""
    actual_graph, _ = fnx_chordal.complete_to_chordal_graph(fnx.Graph(edges))
    expected_graph, _ = nx.complete_to_chordal_graph(nx.Graph(edges))
    assert fnx.is_chordal(actual_graph) == nx.is_chordal(expected_graph)
    assert fnx.is_chordal(actual_graph), "completion did not produce a chordal graph"
