"""Value-parity harness for the algorithmically heavy flow / cut / matching /
optimum-tree families.

These functions can return *non-unique* witnesses (a particular max-flow
distribution, min-cut partition, or maximum-weight matching edge set) that are
allowed to differ from networkx — see
``test_max_flow_default_algorithm_divergence.py``. What must NOT differ is the
optimum *value*: the max-flow value, min-cut value, min-cost-flow cost,
Stoer-Wagner cut value, matching total weight, and spanning-tree/arborescence
weight. This harness locks those scalar contracts against live networkx across
several weighted graphs, complementing the per-feature tests with a broad
numeric-correctness net.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


# ---- shared weighted graph specs (built identically on each library) -------

_FLOW_SPECS = [
    [(0, 1, 3), (0, 2, 2), (1, 2, 1), (1, 3, 2), (2, 3, 3), (2, 1, 1), (3, 4, 4), (0, 4, 1)],
    [(0, 1, 5), (0, 2, 3), (1, 3, 4), (2, 3, 6), (1, 2, 2), (3, 4, 7), (2, 4, 1)],
    [(0, 1, 10), (1, 2, 10), (0, 2, 1), (2, 3, 10), (1, 3, 1)],
]

_UNDIRECTED_W = [
    [(0, 1, 3), (1, 2, 2), (2, 3, 4), (3, 0, 1), (0, 2, 2), (1, 3, 3), (2, 4, 2), (4, 5, 3), (5, 3, 1)],
    [(0, 1, 1), (1, 2, 2), (2, 3, 1), (3, 0, 3), (0, 2, 2), (2, 4, 1), (4, 5, 2), (5, 3, 1), (1, 4, 3)],
]


def _digraph(mod, spec, attr="capacity"):
    g = mod.DiGraph()
    for u, v, c in spec:
        g.add_edge(u, v, **{attr: c, "weight": c})
    return g


def _graph(mod, spec):
    g = mod.Graph()
    for u, v, w in spec:
        g.add_edge(u, v, weight=w)
    return g


@pytest.mark.parametrize("spec", _FLOW_SPECS)
def test_max_flow_and_min_cut_value(spec):
    t = max(v for _, v, _ in spec)
    assert fnx.maximum_flow_value(_digraph(fnx, spec), 0, t) == nx.maximum_flow_value(_digraph(nx, spec), 0, t)
    assert fnx.minimum_cut_value(_digraph(fnx, spec), 0, t) == nx.minimum_cut_value(_digraph(nx, spec), 0, t)


def test_min_cost_flow_cost_and_network_simplex():
    def build(mod):
        g = mod.DiGraph()
        g.add_node(0, demand=-4)
        g.add_node(4, demand=4)
        for u, v, c, w in [(0, 1, 3, 1), (0, 2, 3, 2), (1, 3, 2, 1), (2, 3, 3, 1),
                           (3, 4, 4, 2), (1, 2, 2, 1), (2, 4, 2, 3)]:
            g.add_edge(u, v, capacity=c, weight=w)
        return g
    assert fnx.min_cost_flow_cost(build(fnx)) == nx.min_cost_flow_cost(build(nx))
    assert fnx.network_simplex(build(fnx))[0] == nx.network_simplex(build(nx))[0]


@pytest.mark.parametrize("spec", _UNDIRECTED_W)
def test_stoer_wagner_and_cut_size(spec):
    assert fnx.stoer_wagner(_graph(fnx, spec))[0] == nx.stoer_wagner(_graph(nx, spec))[0]
    assert (
        fnx.cut_size(_graph(fnx, spec), {0, 1}, weight="weight")
        == nx.cut_size(_graph(nx, spec), {0, 1}, weight="weight")
    )


@pytest.mark.parametrize("spec", _UNDIRECTED_W)
def test_matching_total_weight(spec):
    def weight(mod, edges, g):
        return sum(g[u][v]["weight"] for u, v in edges)
    gf, gn = _graph(fnx, spec), _graph(nx, spec)
    for maxcard in (False, True):
        mf = fnx.max_weight_matching(gf, maxcardinality=maxcard)
        mn = nx.max_weight_matching(gn, maxcardinality=maxcard)
        # edge set may differ on ties; total weight must match
        assert weight(fnx, mf, gf) == weight(nx, mn, gn)
        # both are valid matchings of equal cardinality-vs-weight tradeoff
        assert fnx.is_matching(gf, mf) and nx.is_matching(gn, mn)


@pytest.mark.parametrize("spec", _UNDIRECTED_W)
def test_spanning_tree_weight(spec):
    def tw(g):
        return sum(d["weight"] for _, _, d in g.edges(data=True))
    assert tw(fnx.minimum_spanning_tree(_graph(fnx, spec))) == tw(nx.minimum_spanning_tree(_graph(nx, spec)))
    assert tw(fnx.maximum_spanning_tree(_graph(fnx, spec))) == tw(nx.maximum_spanning_tree(_graph(nx, spec)))


def test_arborescence_and_branching_weight():
    def dt(mod):
        g = mod.DiGraph()
        for u, v, w in [(0, 1, 3), (0, 2, 2), (1, 2, 1), (2, 3, 4), (1, 3, 2), (0, 3, 5)]:
            g.add_edge(u, v, weight=w)
        return g

    def tw(g):
        return sum(d["weight"] for _, _, d in g.edges(data=True))

    assert tw(fnx.minimum_spanning_arborescence(dt(fnx))) == tw(nx.minimum_spanning_arborescence(dt(nx)))
    assert tw(fnx.maximum_branching(dt(fnx))) == tw(nx.maximum_branching(dt(nx)))


@pytest.mark.parametrize("spec", _UNDIRECTED_W)
def test_steiner_tree_weight(spec):
    terminals = [0, 3, 5]

    def tw(g):
        return sum(d["weight"] for _, _, d in g.edges(data=True))

    assert tw(fnx.approximation.steiner_tree(_graph(fnx, spec), terminals)) == tw(
        nx.approximation.steiner_tree(_graph(nx, spec), terminals)
    )
