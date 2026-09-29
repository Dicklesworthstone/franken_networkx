"""Regression: community.modularity must use the directed (Leicht-Newman)
formula on DiGraphs, matching networkx.

For directed graphs nx computes
``Q = (1/m) * sum_ij [A_ij - gamma * k_i^out * k_j^in / m] delta(c_i, c_j)``
(in/out degrees, divisor m). fnx's unweighted path called a Rust kernel that
used the *undirected* formula (``k_i*k_j / 2m``, divisor 2m) even for DiGraphs,
so directed modularity disagreed with nx. (br-r37-c1-moddir)

br-r37-c1-q9uy6: directed graphs no longer convert to a networkx graph for
this; networkx's own expression is evaluated on the fnx graph, so the answer
must be networkx's float to the last bit - the tests at the bottom compare
repr(), not within a tolerance.
"""

import networkx as nx
import franken_networkx as fnx

import pytest


def _digraph(mod, edges):
    g = mod.DiGraph()
    for e in edges:
        g.add_edge(*e)
    return g


_EDGES = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (2, 3), (0, 3), (4, 1)]
_PART = [{0, 1, 2}, {3, 4, 5}]


def test_directed_modularity_matches_networkx():
    gn, gf = _digraph(nx, _EDGES), _digraph(fnx, _EDGES)
    assert abs(fnx.community.modularity(gf, _PART) - nx.community.modularity(gn, _PART)) <= 1e-9


def test_directed_modularity_differs_from_undirected_formula():
    # Guard the actual semantics: directed modularity here is NOT equal to the
    # undirected modularity of the same edge set (the old buggy value).
    gn, gf = _digraph(nx, _EDGES), _digraph(fnx, _EDGES)
    directed_q = fnx.community.modularity(gf, _PART)
    undirected_q = nx.community.modularity(gn.to_undirected(), _PART)
    assert abs(directed_q - undirected_q) > 1e-6
    assert abs(directed_q - nx.community.modularity(gn, _PART)) <= 1e-9


@pytest.mark.parametrize("resolution", [0.5, 1.0, 1.5, 2.0])
def test_directed_modularity_resolution_matches_networkx(resolution):
    gn, gf = _digraph(nx, _EDGES), _digraph(fnx, _EDGES)
    assert abs(
        fnx.community.modularity(gf, _PART, resolution=resolution)
        - nx.community.modularity(gn, _PART, resolution=resolution)
    ) <= 1e-9


def test_weighted_directed_modularity_matches_networkx():
    def build(mod):
        g = mod.DiGraph()
        for i, (u, v) in enumerate([(0, 1), (1, 2), (2, 0), (3, 4), (4, 3), (2, 3)]):
            g.add_edge(u, v, weight=float(i + 1))
        return g
    part = [{0, 1, 2}, {3, 4}]
    assert abs(
        fnx.community.modularity(build(fnx), part, weight="weight")
        - nx.community.modularity(build(nx), part, weight="weight")
    ) <= 1e-9


def test_multidigraph_modularity_matches_networkx():
    edges = [(0, 1), (0, 1), (1, 2), (2, 0), (3, 4), (4, 3)]
    gn = nx.MultiDiGraph(edges)
    gf = fnx.MultiDiGraph(edges)
    part = [{0, 1, 2}, {3, 4}]
    assert abs(fnx.community.modularity(gf, part) - nx.community.modularity(gn, part)) <= 1e-9


def _outcome(call):
    try:
        return ("ok", repr(call()))
    except Exception as exc:  # noqa: BLE001 - the exception IS the parity subject
        return (type(exc).__name__, str(exc))


def _random_directed(lib, cls, seed, kind):
    import random

    rng = random.Random(seed)
    n = rng.randint(2, 30)
    edges = []
    for _ in range(rng.randint(1, 4 * n)):
        u, v = rng.randrange(n), rng.randrange(n)
        attrs = {}
        if kind == "int":
            attrs["weight"] = rng.randint(0, 9)
        elif kind == "float":
            attrs["weight"] = rng.random() * 10
        elif kind == "mixed":
            attrs["weight"] = rng.choice([rng.randint(1, 5), rng.random()])
        elif kind == "some" and rng.random() < 0.5:
            attrs["weight"] = rng.random()
        edges.append((u, v, attrs))
    graph = getattr(lib, cls)()
    graph.add_nodes_from(range(n))
    graph.add_edges_from(edges)
    nodes = list(range(n))
    rng.shuffle(nodes)
    k = rng.randint(1, min(5, n))
    return graph, [set(nodes[i::k]) for i in range(k)]


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("kind", ["int", "float", "mixed", "none", "some"])
def test_directed_modularity_is_networkx_to_the_last_bit(cls, kind):
    for seed in range(12):
        ours, parts = _random_directed(fnx, cls, seed, kind)
        theirs, _ = _random_directed(nx, cls, seed, kind)
        for weight in ("weight", None, "other"):
            for resolution in (1, 0.5, 2):
                assert _outcome(
                    lambda: fnx.community.modularity(
                        ours, parts, weight=weight, resolution=resolution
                    )
                ) == _outcome(
                    lambda: nx.community.modularity(
                        theirs, parts, weight=weight, resolution=resolution
                    )
                ), (seed, weight, resolution)


_DIRECTED_EDGE_CASES = {
    "not a partition": ([(0, 1), (1, 2)], [{0, 1}]),
    "overlapping communities": ([(0, 1), (1, 2)], [{0, 1}, {1, 2}]),
    "zero weight": ([(0, 1, {"weight": 0})], [{0}, {1}]),
    "zero float weight": ([(0, 1, {"weight": 0.0})], [{0}, {1}]),
    "self-loops": ([(0, 0, {"weight": 2}), (0, 1), (1, 1)], [{0}, {1}]),
}


@pytest.mark.parametrize("cls", ["DiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("case", sorted(_DIRECTED_EDGE_CASES))
def test_directed_modularity_edge_cases_match_networkx(cls, case):
    edges, parts = _DIRECTED_EDGE_CASES[case]
    ours, theirs = getattr(fnx, cls)(edges), getattr(nx, cls)(edges)
    assert _outcome(lambda: fnx.community.modularity(ours, parts)) == _outcome(
        lambda: nx.community.modularity(theirs, parts)
    )


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_undirected_modularity_unchanged(seed):
    gn = nx.gnp_random_graph(9, 0.45, seed=seed)
    gf = fnx.gnp_random_graph(9, 0.45, seed=seed)
    part = [set(range(4)), set(range(4, 9))]
    assert abs(fnx.community.modularity(gf, part) - nx.community.modularity(gn, part)) <= 1e-9
