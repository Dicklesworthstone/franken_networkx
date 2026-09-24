"""Strict mode builds every generator size networkx builds.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.8. fnx-generators kept
MAX_N_GENERIC=100k, MAX_N_GNP=20k and MAX_N_COMPLETE=2000 size budgets and
enforced them in strict mode, so the default fnx raised
``ValueError(FailClosed {...})`` on legal inputs: complete_graph(2500),
gnp_random_graph(25000), path_graph(150000), watts_strogatz_graph(150000),
circulant_graph, ladder_graph and more. networkx has no size caps. The budgets
are a hardened-mode defence; strict mode now builds exactly what nx builds.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

# Each size sits just past the Rust budget that refused it (MAX_N_GENERIC=100k,
# MAX_N_GNP=20k, MAX_N_COMPLETE=2000, dense edges 1,999,000).
EXACT_CASES = {
    "empty_graph": lambda m: m.empty_graph(100_001),
    "path_graph": lambda m: m.path_graph(100_001),
    "cycle_graph": lambda m: m.cycle_graph(100_001),
    "ladder_graph": lambda m: m.ladder_graph(50_001),
    "circular_ladder_graph": lambda m: m.circular_ladder_graph(50_001),
    "circulant_graph": lambda m: m.circulant_graph(100_001, [1, 7]),
    "full_rary_tree": lambda m: m.full_rary_tree(3, 100_001),
    "balanced_tree": lambda m: m.balanced_tree(2, 17),
    "fast_gnp_random_graph": lambda m: m.fast_gnp_random_graph(150_000, 1e-5, seed=11),
    "watts_strogatz_graph": lambda m: m.watts_strogatz_graph(20_001, 4, 0.1, seed=11),
    "gnp_random_graph": lambda m: m.gnp_random_graph(20_001, 1e-5, seed=11),
}


def _shape(G):
    return list(G.nodes), list(G.edges)


@pytest.mark.parametrize("name", sorted(EXACT_CASES))
def test_strict_builds_past_the_budget_exactly_like_networkx(name):
    build = EXACT_CASES[name]
    expected = build(nx)
    actual = build(fnx)
    assert actual.number_of_nodes() == expected.number_of_nodes()
    assert _shape(actual) == _shape(expected)


def test_complete_graph_past_the_dense_budget():
    # K_2001 has 2,001,000 edges, one row past the 1,999,000 dense budget.
    expected = nx.complete_graph(2001)
    actual = fnx.complete_graph(2001)
    assert actual.number_of_nodes() == 2001
    assert actual.number_of_edges() == expected.number_of_edges() == 2_001_000
    for node in (0, 1000, 2000):
        assert list(actual.adj[node]) == list(expected.adj[node])


def test_erdos_renyi_alias_builds_past_the_gnp_budget():
    # nx.erdos_renyi_graph is gnp_random_graph; the gnp case above already pays
    # for the O(n^2) networkx arm, so compare the alias against fnx's gnp.
    G = fnx.erdos_renyi_graph(20_001, 1e-5, seed=11)
    assert G.number_of_nodes() == 20_001
    assert _shape(G) == _shape(fnx.gnp_random_graph(20_001, 1e-5, seed=11))


@pytest.mark.parametrize(
    ("build", "clamped_nodes"),
    [
        (lambda: fnx.empty_graph(100_001), 100_000),
        (lambda: fnx.path_graph(100_001), 100_000),
        (lambda: fnx.gnp_random_graph(20_001, 1e-5, seed=3), 20_000),
    ],
)
def test_hardened_mode_clamps_the_budget_and_says_so(build, clamped_nodes):
    """The budgets did not disappear: hardened mode keeps its defence (a fix
    that deleted the caps fails the node count), and the clamp is VISIBLE.
    nro4w.9: the clamp warning never left Rust, so a hardened caller got a
    smaller graph than requested with nothing to say so."""
    with fnx.compatibility_mode("hardened"):
        with pytest.warns(RuntimeWarning, match="clamped to"):
            G = build()
    assert G.number_of_nodes() == clamped_nodes


def test_strict_mode_generators_emit_no_recovery_warnings():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert fnx.path_graph(100_001).number_of_nodes() == 100_001
        assert fnx.gnp_random_graph(50, 0.1, seed=1).number_of_nodes() == 50
