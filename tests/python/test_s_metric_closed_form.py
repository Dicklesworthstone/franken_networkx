"""s-metric against its DEFINING formula, not against networkx.

br-r37-c1-znwmd. The existing s_metric tests cover parity with the incumbent and
degenerate inputs. Neither pins the definition, so a change that alters the
formula consistently in both places, or a normalisation that quietly returns to
the historical `normalized=True` behaviour, would pass them.

    s(G) = sum over edges (u, v) of deg(u) * deg(v)

with two closed forms that follow:

    complete   s(K_n) = C(n, 2) * (n - 1)^2   every vertex has degree n-1
    star       s(S_n) = n^2                   n edges, each joining the degree-n
                                              centre to a degree-1 leaf

As in the Wiener oracle, `star_graph(n)` has n+1 nodes and n leaves; reading n
as the node count shifts every expectation.
"""

import math

import pytest

import franken_networkx as fnx

SIZES = [2, 3, 4, 5, 6, 7, 8, 10, 12]


def _defining_sum(graph):
    """s(G) computed straight from the definition, independent of s_metric."""
    degree = dict(graph.degree())
    return sum(degree[u] * degree[v] for u, v in graph.edges())


@pytest.mark.parametrize("n", SIZES)
def test_complete_graph_s_metric_closed_form(n):
    expected = math.comb(n, 2) * (n - 1) ** 2
    assert fnx.s_metric(fnx.complete_graph(n)) == pytest.approx(expected)


@pytest.mark.parametrize("leaves", [1, 2, 3, 4, 5, 6, 8, 10])
def test_star_graph_s_metric_is_leaves_squared(leaves):
    assert fnx.s_metric(fnx.star_graph(leaves)) == pytest.approx(leaves**2)


@pytest.mark.parametrize("n", SIZES)
def test_path_graph_s_metric_matches_the_defining_sum(n):
    graph = fnx.path_graph(n)
    assert fnx.s_metric(graph) == pytest.approx(_defining_sum(graph))


@pytest.mark.parametrize("n", [3, 4, 5, 6, 7, 8, 10])
def test_cycle_graph_s_metric_is_four_n(n):
    """Every vertex of C_n has degree 2 and there are n edges, so s = 4n."""
    graph = fnx.cycle_graph(n)
    assert fnx.s_metric(graph) == pytest.approx(4 * n)
    assert fnx.s_metric(graph) == pytest.approx(_defining_sum(graph))


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6, 7, 8])
def test_random_graphs_s_metric_matches_the_defining_sum(seed):
    """The general case: arbitrary degree sequences, not just regular families.

    The closed forms above are all on graphs where every edge contributes the
    same product, so they cannot distinguish `sum of products` from
    `product of sums` style errors. These cannot be satisfied that way.
    """
    graph = fnx.erdos_renyi_graph(18, 0.3, seed=seed)
    assert fnx.s_metric(graph) == pytest.approx(_defining_sum(graph))


def test_graph_with_no_edges_is_zero():
    graph = fnx.Graph()
    graph.add_nodes_from(range(5))
    assert fnx.s_metric(graph) == 0


def test_self_loop_contributes_its_own_degree_product():
    """A self-loop is the case where `deg` and `edges` disagree most.

    Pinned as a characterisation: whatever the convention, it must equal the
    defining sum computed the same way, so this fails if s_metric and `degree`
    ever stop agreeing about self-loops.
    """
    graph = fnx.Graph()
    graph.add_edge(0, 1)
    graph.add_edge(1, 1)
    assert fnx.s_metric(graph) == pytest.approx(_defining_sum(graph))


@pytest.mark.parametrize("n", [4, 5, 6, 8])
def test_complete_graph_maximises_s_metric_over_spanning_subgraphs(n):
    """Structural invariant independent of the closed forms.

    Removing an edge can only lower degrees and drop a term, so K_n must have a
    strictly larger s-metric than any graph obtained by deleting one of its
    edges.
    """
    complete = fnx.complete_graph(n)
    baseline = fnx.s_metric(complete)
    for u, v in list(complete.edges()):
        reduced = complete.copy()
        reduced.remove_edge(u, v)
        assert fnx.s_metric(reduced) < baseline
