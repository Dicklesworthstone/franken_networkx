"""Phase B certification: greedy-coloring strategies (deterministic ones),
simrank similarity, triadic census, and structural helpers. Zero
divergences. Direct asserts (no try/except masking).
"""
import random

import networkx as nx

import franken_networkx as fnx


def _ue():
    R = random.Random(404)
    return [(u, v) for u, v in ((R.randrange(18), R.randrange(18)) for _ in range(55)) if u != v]


_STRATEGIES = [
    "largest_first",
    "smallest_last",
    "independent_set",
    "connected_sequential_bfs",
    "connected_sequential_dfs",
    "saturation_largest_first",
]


def test_greedy_color_strategies_color_count():
    gf, gn = fnx.Graph(_ue()), nx.Graph(_ue())
    for strat in _STRATEGIES:
        nc_f = 1 + max(nx.greedy_color(gf, strategy=strat).values())
        nc_n = 1 + max(nx.greedy_color(gn, strategy=strat).values())
        assert nc_f == nc_n, strat
    # the produced coloring is proper
    coloring = nx.greedy_color(gf, strategy="largest_first")
    assert all(coloring[u] != coloring[v] for u, v in gf.edges())


def test_simrank():
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    sf, sn = fnx.Graph(edges), nx.Graph(edges)

    def rd(d):
        return {repr(k): {repr(k2): round(v2, 6) for k2, v2 in d2.items()} for k, d2 in d.items()}

    # default max_iterations (1000) converges; small caps raise
    # ExceededMaxIterations on BOTH impls (not a divergence).
    assert rd(nx.simrank_similarity(sf)) == rd(nx.simrank_similarity(sn))


def test_structural_helpers():
    gf, gn = fnx.Graph(_ue()), nx.Graph(_ue())
    assert nx.is_isolate(gf, 0) == nx.is_isolate(gn, 0)
    assert sorted(repr(x) for x in nx.common_neighbors(gf, 0, 1)) == sorted(
        repr(x) for x in nx.common_neighbors(gn, 0, 1)
    )
    assert sorted(repr(x) for x in nx.non_neighbors(gf, 0)) == sorted(
        repr(x) for x in nx.non_neighbors(gn, 0)
    )
    assert round(nx.degree_assortativity_coefficient(gf), 8) == round(
        nx.degree_assortativity_coefficient(gn), 8
    )
    assert round(nx.degree_pearson_correlation_coefficient(gf), 8) == round(
        nx.degree_pearson_correlation_coefficient(gn), 8
    )


def test_triadic_census():
    R = random.Random(404)
    R.randrange(18)  # advance to match probe-era stream is unnecessary; build fresh
    de = [(u, v) for u, v in ((R.randrange(12), R.randrange(12)) for _ in range(40)) if u != v]
    assert nx.triadic_census(fnx.DiGraph(de)) == nx.triadic_census(nx.DiGraph(de))
