"""Wiener index against TEXTBOOK closed forms, not against networkx.

br-r37-c1-jjslo. The existing wiener tests are parity/conformance: they assert
fnx agrees with networkx. That cannot catch an error both libraries share, and
it cannot catch a fixture that silently stopped covering anything. These
assertions come from the mathematics instead, so they hold independently of the
incumbent.

Closed forms used (standard results for the Wiener index, the sum of shortest
path lengths over all unordered vertex pairs):

    path      W(P_n) = n(n^2 - 1) / 6
    complete  W(K_n) = C(n, 2)                     every pair is at distance 1
    cycle     W(C_n) = n^3 / 8            (n even)
              W(C_n) = n(n^2 - 1) / 8     (n odd)
    star      W(S_n) = n^2               for `star_graph(n)`, i.e. n LEAVES plus
                                         a centre: n pairs at distance 1 and
                                         C(n,2) pairs at distance 2, and
                                         n + 2*C(n,2) = n^2.

The star identity is the one worth stating explicitly, because `star_graph(n)`
has n+1 nodes; reading n as the node count silently shifts every expected value.
"""

import itertools
import math

import pytest

import franken_networkx as fnx

SIZES = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15]


@pytest.mark.parametrize("n", SIZES)
def test_path_graph_wiener_index_closed_form(n):
    assert fnx.wiener_index(fnx.path_graph(n)) == pytest.approx(n * (n * n - 1) / 6)


@pytest.mark.parametrize("n", SIZES)
def test_complete_graph_wiener_index_is_the_pair_count(n):
    """Every pair is at distance 1, so W(K_n) is exactly the number of pairs."""
    assert fnx.wiener_index(fnx.complete_graph(n)) == pytest.approx(math.comb(n, 2))


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
def test_cycle_graph_wiener_index_closed_form(n):
    expected = (n**3) / 8 if n % 2 == 0 else n * (n * n - 1) / 8
    assert fnx.wiener_index(fnx.cycle_graph(n)) == pytest.approx(expected)


@pytest.mark.parametrize("leaves", [1, 2, 3, 4, 5, 6, 8, 10])
def test_star_graph_wiener_index_is_leaves_squared(leaves):
    assert fnx.wiener_index(fnx.star_graph(leaves)) == pytest.approx(leaves**2)


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 8])
def test_wiener_index_equals_the_defining_double_sum(n):
    """Cross-check against the DEFINITION, summed independently.

    The closed forms above could all be wrong in the same way if the family were
    misidentified; this recomputes from all-pairs shortest path lengths, so it
    pins the definition rather than a formula.
    """
    for graph in (fnx.path_graph(n), fnx.cycle_graph(n), fnx.complete_graph(n)):
        lengths = dict(fnx.all_pairs_shortest_path_length(graph))
        total = sum(
            lengths[u][v] for u, v in itertools.combinations(graph, 2)
        )
        assert fnx.wiener_index(graph) == pytest.approx(total)


def test_disconnected_graph_wiener_index_is_infinite():
    """The negative case: a disconnected graph has an infinite Wiener index.

    An implementation that silently skips unreachable pairs returns a finite
    number here and passes every connected-graph assertion above.
    """
    graph = fnx.Graph()
    graph.add_edge(0, 1)
    graph.add_edge(2, 3)
    assert fnx.wiener_index(graph) == math.inf


def test_single_node_and_empty_edge_cases():
    single = fnx.Graph()
    single.add_node(0)
    assert fnx.wiener_index(single) == 0

    two_isolated = fnx.Graph()
    two_isolated.add_nodes_from([0, 1])
    assert fnx.wiener_index(two_isolated) == math.inf


@pytest.mark.parametrize("n", [4, 6, 8])
def test_path_wiener_exceeds_cycle_wiener(n):
    """A structural invariant, independent of both closed forms.

    Closing a path into a cycle can only shorten distances, so W(C_n) < W(P_n)
    for n >= 4. If both formulas were transcribed wrong in a correlated way this
    ordering would still catch it.
    """
    assert fnx.wiener_index(fnx.cycle_graph(n)) < fnx.wiener_index(fnx.path_graph(n))
