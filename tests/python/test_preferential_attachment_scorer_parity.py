"""Parity lock for the explicit-ebunch `preferential_attachment` scorer.

Bead br-r37-c1-z00k8. `preferential_attachment` was the one member of the
four-metric link-prediction family with no dedicated explicit-ebunch scorer:
`jaccard_coefficient`, `adamic_adar_index` and `resource_allocation_index` each
short-circuit into one, while `preferential_attachment` fell through to the
generic `_link_prediction_compute`. On the class1-frontier workload it measured
0.8635x against live NetworkX while `jaccard_coefficient` — same graph, same 300
pairs, same validator — measured 3.2523x.

`_pa_native_scores` is that missing sibling. These tests pin the behaviour the
generic path had, because the fast path may only change how long it takes:

  * int scores, never floats (NetworkX returns `deg(u) * deg(v)`);
  * ebunch order preserved, duplicates and self-pairs included;
  * generator semantics, so nothing is computed before first iteration while
    the NodeNotFound / NetworkXNotImplemented raises stay eager;
  * the default (ebunch=None) non_edges path untouched;
  * subclasses keep the generic path, so an overridden accessor still runs.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _pair(n=120, m=400, seed=7):
    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((str(u), str(v)))
    gnx, gfx = nx.Graph(), fnx.Graph()
    gnx.add_nodes_from(str(i) for i in range(n))
    gfx.add_nodes_from(str(i) for i in range(n))
    gnx.add_edges_from(stream)
    gfx.add_edges_from(stream)
    return gnx, gfx


def test_explicit_ebunch_matches_networkx_exactly():
    gnx, gfx = _pair()
    pairs = [(str(i), str(i + 3)) for i in range(0, 100, 2)]
    assert list(fnx.preferential_attachment(gfx, pairs)) == list(
        nx.preferential_attachment(gnx, pairs)
    )


def test_scores_are_ints_not_floats():
    """NetworkX yields deg(u)*deg(v); a float here would be a silent type drift."""
    _, gfx = _pair()
    pairs = [(str(i), str(i + 3)) for i in range(0, 40, 2)]
    for _u, _v, score in fnx.preferential_attachment(gfx, pairs):
        # `bool` is excluded explicitly: it passes isinstance(x, int) and would
        # hide a degenerate scorer that returned a truth value.
        assert isinstance(score, int) and not isinstance(score, bool)
        assert not isinstance(score, float)


def test_matches_the_generic_scorer_it_replaced():
    gnx, gfx = _pair()
    pairs = [(str(i), str(i + 5)) for i in range(0, 80, 3)]
    fast = list(fnx.preferential_attachment(gfx, pairs))
    generic = list(
        fnx._link_prediction_compute(gfx, list(pairs), "preferential_attachment")
    )
    assert fast == generic
    assert fast == list(nx.preferential_attachment(gnx, pairs))


@pytest.mark.parametrize(
    "pairs",
    [
        [],                                          # empty ebunch
        [("0", "1")],                                # single pair
        [("0", "1"), ("0", "1"), ("0", "1")],        # duplicates keep their slots
        [("3", "3")],                                # self-pair
        [("5", "4"), ("4", "5")],                    # both orientations
        [("2", "9"), ("0", "1"), ("2", "9")],        # unsorted with a repeat
    ],
)
def test_degenerate_ebunches_match_networkx(pairs):
    gnx, gfx = _pair()
    assert list(fnx.preferential_attachment(gfx, pairs)) == list(
        nx.preferential_attachment(gnx, pairs)
    )


def test_large_ebunch_crosses_the_whole_graph_degree_branch():
    """An ebunch at least as large as the node set takes the other branch."""
    gnx, gfx = _pair(n=40, m=120, seed=11)
    pairs = [
        (str(u), str(v)) for u in range(40) for v in range(40) if u != v
    ][:200]
    assert len(pairs) >= gfx.number_of_nodes()
    assert list(fnx.preferential_attachment(gfx, pairs)) == list(
        nx.preferential_attachment(gnx, pairs)
    )


def test_isolated_and_zero_degree_endpoints():
    gnx, gfx = nx.Graph(), fnx.Graph()
    for graph in (gnx, gfx):
        graph.add_nodes_from(["lonely", "a", "b", "c"])
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
    pairs = [("lonely", "a"), ("lonely", "lonely"), ("a", "c")]
    got = list(fnx.preferential_attachment(gfx, pairs))
    assert got == list(nx.preferential_attachment(gnx, pairs))
    assert got[0][2] == 0  # 0 * 1
    assert got[1][2] == 0


def test_default_ebunch_path_is_untouched():
    gnx, gfx = _pair(n=30, m=60, seed=5)
    assert list(fnx.preferential_attachment(gfx)) == list(
        nx.preferential_attachment(gnx)
    )


def test_returns_a_lazy_generator_and_computes_nothing_early():
    _, gfx = _pair()
    pairs = [(str(i), str(i + 3)) for i in range(0, 20, 2)]
    result = fnx.preferential_attachment(gfx, pairs)
    assert iter(result) is result  # a generator, as nx's _apply_prediction returns

    # Mutating between call and first iteration must be visible, which proves
    # the degree batch had not already fired.
    gfx.add_edge(pairs[0][0], "sentinel-node")
    first = next(iter(result))
    assert first[2] == gfx.degree(pairs[0][0]) * gfx.degree(pairs[0][1])


def test_missing_endpoints_still_raise_eagerly():
    """The raise must happen on the call, not on first iteration (scceager)."""
    _, gfx = _pair()
    with pytest.raises(fnx.NodeNotFound):
        fnx.preferential_attachment(gfx, [("0", "not-a-node")])
    with pytest.raises(fnx.NodeNotFound):
        fnx.preferential_attachment(gfx, [("not-a-node", "0")])


def test_directed_and_multigraph_inputs_still_rejected():
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.preferential_attachment(fnx.DiGraph([("a", "b")]), [("a", "b")])
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx.preferential_attachment(fnx.MultiGraph([("a", "b")]), [("a", "b")])


def test_graph_subclass_keeps_the_generic_path_and_same_answers():
    """The fast path gates on `type(G) is Graph`; a subclass must still work."""

    class MyGraph(fnx.Graph):
        pass

    gnx, gfx = _pair(n=30, m=60, seed=3)
    sub = MyGraph()
    sub.add_nodes_from(gfx.nodes)
    sub.add_edges_from(gfx.edges)
    pairs = [(str(i), str(i + 3)) for i in range(0, 20, 2)]
    assert list(fnx.preferential_attachment(sub, pairs)) == list(
        nx.preferential_attachment(gnx, pairs)
    )


def test_sibling_metrics_are_unaffected():
    """The edit must not perturb the three metrics that already had a scorer."""
    gnx, gfx = _pair(n=60, m=180, seed=13)
    pairs = [(str(i), str(i + 3)) for i in range(0, 40, 2)]
    for fnx_fn, nx_fn in (
        (fnx.jaccard_coefficient, nx.jaccard_coefficient),
        (fnx.adamic_adar_index, nx.adamic_adar_index),
        (fnx.resource_allocation_index, nx.resource_allocation_index),
    ):
        assert list(fnx_fn(gfx, pairs)) == list(nx_fn(gnx, pairs))
