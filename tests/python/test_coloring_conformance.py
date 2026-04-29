"""NetworkX conformance for the graph coloring algorithm family.

Covers ``greedy_color`` across all 7 strategies, ``equitable_color``,
and the stateless supporting strategy callables
``strategy_largest_first``, ``strategy_smallest_last``,
``strategy_independent_set``, ``strategy_connected_sequential_bfs``,
and ``strategy_connected_sequential_dfs``.

Each test asserts:

1. The color dict matches NetworkX bit-for-bit (key iteration order
   AND color values).
2. The proper-coloring invariant holds: no edge connects two
   nodes with the same color.
3. ``interchange=True`` parity (which switches to a different code
   path that interchanges colors when beneficial).
4. ``equitable_color`` parity (constraint: color-class sizes differ
   by at most 1).
5. Stateless strategy-callables called directly produce identical
   permutation orderings.

Existing ``test_greedy_color_order_parity.py`` only checked dict
iteration order on a single 5-node fixture; this suite exercises
every strategy across structured fixtures plus 12+ ``gnp_random_graph``
instances so any silent divergence in a strategy's heuristic surfaces
immediately.
"""

from __future__ import annotations

import itertools

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


DETERMINISTIC_STRATEGIES = [
    "largest_first",
    "smallest_last",
    "independent_set",
    "connected_sequential_bfs",
    "connected_sequential_dfs",
    "saturation_largest_first",
]


# Strategies that NX rejects with NetworkXPointlessConcept when paired
# with interchange=True.
INTERCHANGE_INCOMPATIBLE = {"independent_set", "saturation_largest_first"}


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _pair(edges, nodes=None):
    fg = fnx.Graph()
    ng = nx.Graph()
    if nodes is not None:
        fg.add_nodes_from(nodes)
        ng.add_nodes_from(nodes)
    for u, v in edges:
        fg.add_edge(u, v)
        ng.add_edge(u, v)
    return fg, ng


def _structured_fixtures():
    out = []
    # K_n
    for n in range(2, 7):
        out.append((f"K_{n}", list(itertools.combinations(range(n), 2)),
                    list(range(n))))
    # cycles C_n
    for n in range(3, 9):
        out.append((f"C_{n}", [(i, (i + 1) % n) for i in range(n)],
                    list(range(n))))
    # paths P_n
    for n in range(2, 9):
        out.append((f"P_{n}",
                    list(zip(range(n - 1), range(1, n))),
                    list(range(n))))
    # stars S_n
    for n in range(1, 7):
        out.append((f"S_{n}",
                    [(0, i) for i in range(1, n + 1)],
                    list(range(n + 1))))
    # complete bipartite
    for a, b in [(2, 3), (3, 3), (3, 4)]:
        kbg = nx.complete_bipartite_graph(a, b)
        out.append((f"K_{a}_{b}",
                    list(kbg.edges()), list(kbg.nodes())))
    # Petersen
    pg = nx.petersen_graph()
    out.append(("petersen", list(pg.edges()), list(pg.nodes())))
    # Disconnected
    out.append(("disjoint_K3_K3",
                [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
                list(range(6))))
    out.append(("isolate_plus_K3",
                [(0, 1), (1, 2), (2, 0)], [0, 1, 2, 99]))
    return out


def _random_fixtures():
    out = []
    for n, p, seed in [
        (6, 0.4, 1), (8, 0.3, 2), (8, 0.5, 3), (10, 0.3, 4), (10, 0.5, 5),
        (12, 0.3, 6), (12, 0.5, 7), (15, 0.25, 8), (15, 0.4, 9),
        (20, 0.2, 10), (20, 0.3, 11), (25, 0.2, 12),
    ]:
        gnp = nx.gnp_random_graph(n, p, seed=seed)
        out.append((f"gnp_n{n}_p{p}_s{seed}",
                    list(gnp.edges()), list(range(n))))
    return out


STRUCTURED = _structured_fixtures()
RANDOM = _random_fixtures()
ALL_FIXTURES = STRUCTURED + RANDOM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_proper_coloring(graph, coloring):
    """No edge connects same-colored endpoints."""
    for u, v in graph.edges():
        if u == v:
            continue
        assert coloring[u] != coloring[v], (
            f"improper coloring: edge ({u}, {v}) has color {coloring[u]}"
        )


# ---------------------------------------------------------------------------
# greedy_color across deterministic strategies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", DETERMINISTIC_STRATEGIES)
@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_greedy_color_deterministic_matches_networkx(name, edges, nodes, strategy):
    fg, ng = _pair(edges, nodes)
    fr = fnx.greedy_color(fg, strategy=strategy)
    nr = nx.greedy_color(ng, strategy=strategy)
    assert fr == nr, f"{name} {strategy}: dicts differ"
    # Iteration order matters per NX contract
    assert list(fr.items()) == list(nr.items()), (
        f"{name} {strategy}: iteration order differs"
    )
    _assert_proper_coloring(fg, fr)


@pytest.mark.parametrize(
    "strategy",
    [s for s in DETERMINISTIC_STRATEGIES if s not in INTERCHANGE_INCOMPATIBLE],
)
@pytest.mark.parametrize("name,edges,nodes", ALL_FIXTURES,
                         ids=[fx[0] for fx in ALL_FIXTURES])
def test_greedy_color_with_interchange_matches_networkx(name, edges, nodes, strategy):
    fg, ng = _pair(edges, nodes)
    fr = fnx.greedy_color(fg, strategy=strategy, interchange=True)
    nr = nx.greedy_color(ng, strategy=strategy, interchange=True)
    assert fr == nr, f"{name} {strategy} +interchange: dicts differ"
    _assert_proper_coloring(fg, fr)


# ---------------------------------------------------------------------------
# Strategies that error with interchange=True
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", sorted(INTERCHANGE_INCOMPATIBLE))
def test_interchange_incompatible_strategies_error_matching_networkx(strategy):
    fg, ng = _pair(list(itertools.combinations(range(4), 2)), list(range(4)))
    with pytest.raises(nx.NetworkXPointlessConcept) as nx_exc:
        nx.greedy_color(ng, strategy=strategy, interchange=True)
    with pytest.raises(fnx.NetworkXPointlessConcept) as fnx_exc:
        fnx.greedy_color(fg, strategy=strategy, interchange=True)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# random_sequential — must accept seeded callable strategy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 7, 42, 1000])
@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 4 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 4 <= len(fx[2]) <= 15],
)
def test_random_sequential_with_seeded_callable_matches_networkx(name, edges, nodes, seed):
    """``random_sequential`` is non-deterministic without a seed; both
    libraries support the callable form
    ``lambda G, colors: nx.coloring.strategy_random_sequential(G, colors, seed=...)``
    which is the canonical way to seed it. Asserts both libs converge
    on the same coloring."""
    fg, ng = _pair(edges, nodes)

    def strat(G, colors):
        return nx.coloring.strategy_random_sequential(G, colors, seed=seed)

    fr = fnx.greedy_color(fg, strategy=strat)
    nr = nx.greedy_color(ng, strategy=strat)
    assert fr == nr, f"{name} seed={seed}: dicts differ"
    _assert_proper_coloring(fg, fr)


# ---------------------------------------------------------------------------
# Strategy callables — exercise the standalone functions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn_name",
    [
        # ``strategy_saturation_largest_first`` is excluded — it's a
        # stateful generator that expects ``colors`` to be updated
        # between yields, so calling ``list(...)`` on it with a static
        # empty dict deadlocks (each yield re-selects the same uncoloured
        # node forever). It's still exercised end-to-end via
        # ``greedy_color(strategy='saturation_largest_first')`` above.
        "strategy_largest_first",
        "strategy_smallest_last",
        "strategy_independent_set",
        "strategy_connected_sequential_bfs",
        "strategy_connected_sequential_dfs",
    ],
)
@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in STRUCTURED if 3 <= len(fx[2]) <= 12],
    ids=[fx[0] for fx in STRUCTURED if 3 <= len(fx[2]) <= 12],
)
def test_strategy_callable_node_order_matches_networkx(name, edges, nodes, fn_name):
    """Each strategy is itself an iterator/generator over node ordering.
    Asserts both libraries produce the same node ordering — so the
    greedy_color output dict matches by construction."""
    fg, ng = _pair(edges, nodes)
    fnx_strat = getattr(fnx, fn_name)
    nx_strat = getattr(nx.coloring, fn_name)
    fr_order = list(fnx_strat(fg, {}))
    nr_order = list(nx_strat(ng, {}))
    assert fr_order == nr_order, (
        f"{name} {fn_name}: order diverged fnx={fr_order} nx={nr_order}"
    )


# ---------------------------------------------------------------------------
# equitable_color
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,edges,nodes,k",
    [
        ("K_3_color_3", list(itertools.combinations(range(3), 2)), list(range(3)), 3),
        ("K_4_color_4", list(itertools.combinations(range(4), 2)), list(range(4)), 4),
        ("K_5_color_5", list(itertools.combinations(range(5), 2)), list(range(5)), 5),
        ("C_6_color_3", [(i, (i + 1) % 6) for i in range(6)], list(range(6)), 3),
        ("C_8_color_3", [(i, (i + 1) % 8) for i in range(8)], list(range(8)), 3),
        ("petersen_color_4", list(nx.petersen_graph().edges()),
         list(nx.petersen_graph().nodes()), 4),
        ("K_3_3_color_4", list(nx.complete_bipartite_graph(3, 3).edges()),
         list(nx.complete_bipartite_graph(3, 3).nodes()), 4),
        ("S_5_color_6", [(0, i) for i in range(1, 6)], list(range(6)), 6),
    ],
)
def test_equitable_color_matches_networkx(name, edges, nodes, k):
    fg, ng = _pair(edges, nodes)
    fr = fnx.equitable_color(fg, k)
    nr = nx.equitable_color(ng, k)
    assert fr == nr, f"{name}: dicts differ"
    _assert_proper_coloring(fg, fr)
    # Equitable: color-class sizes differ by at most 1
    sizes = {}
    for v in fr.values():
        sizes[v] = sizes.get(v, 0) + 1
    if sizes:
        assert max(sizes.values()) - min(sizes.values()) <= 1


def test_equitable_color_with_too_few_colors_raises_matching_networkx():
    """K_{3,3} has max-degree 3 → equitable_color needs k≥4. Both
    libraries must raise the same NetworkXAlgorithmError for k=2."""
    fg, ng = _pair(list(nx.complete_bipartite_graph(3, 3).edges()),
                    list(nx.complete_bipartite_graph(3, 3).nodes()))
    with pytest.raises(nx.NetworkXAlgorithmError) as nx_exc:
        nx.equitable_color(ng, 2)
    with pytest.raises(fnx.NetworkXAlgorithmError) as fnx_exc:
        fnx.equitable_color(fg, 2)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# Empty / single-node / disconnected dispatch
# ---------------------------------------------------------------------------


def test_greedy_color_empty_graph_returns_empty_dict():
    assert fnx.greedy_color(fnx.Graph()) == nx.greedy_color(nx.Graph()) == {}


def test_greedy_color_single_node_returns_zero():
    fg = fnx.Graph()
    fg.add_node(0)
    ng = nx.Graph()
    ng.add_node(0)
    assert fnx.greedy_color(fg) == nx.greedy_color(ng)


@pytest.mark.parametrize("strategy", DETERMINISTIC_STRATEGIES)
def test_greedy_color_disconnected_matches_networkx(strategy):
    fg, ng = _pair(
        [(0, 1), (1, 2), (3, 4), (4, 5), (6, 7)],
        [0, 1, 2, 3, 4, 5, 6, 7, 99],  # 99 is isolated
    )
    fr = fnx.greedy_color(fg, strategy=strategy)
    nr = nx.greedy_color(ng, strategy=strategy)
    assert fr == nr
    _assert_proper_coloring(fg, fr)


# ---------------------------------------------------------------------------
# Chromatic number invariant: greedy gives ≤ Δ + 1 colors (Brooks' bound)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", DETERMINISTIC_STRATEGIES)
@pytest.mark.parametrize(
    "name,edges,nodes",
    [fx for fx in ALL_FIXTURES if 3 <= len(fx[2]) <= 15],
    ids=[fx[0] for fx in ALL_FIXTURES if 3 <= len(fx[2]) <= 15],
)
def test_greedy_color_uses_at_most_max_degree_plus_one_colors(
    name, edges, nodes, strategy,
):
    fg, _ = _pair(edges, nodes)
    coloring = fnx.greedy_color(fg, strategy=strategy)
    if not coloring:
        return
    n_colors = max(coloring.values()) + 1
    max_degree = max((d for _, d in fg.degree()), default=0)
    assert n_colors <= max_degree + 1, (
        f"{name} {strategy}: used {n_colors} colors but Δ+1 = "
        f"{max_degree + 1}"
    )
