"""Byte-exact seeded RNG parity for native random generators vs networkx.

franken_networkx implements many random graph generators natively in
Rust, reproducing networkx's MT19937 ``PythonRandom`` draw sequence so
that a given ``seed`` yields the *exact same* graph. The existing
generator tests check structural shape and that the native path does not
fall back to networkx (they monkeypatch ``nx`` to fail), but none assert
the produced edges equal those of the **real** upstream library.

This test closes that gap: for each generator and seed it asserts that
fnx and the real networkx produce identical node lists *and* identical
edge lists *in the same order*. It is a tripwire for any future drift in
the native RNG / draw-order reproduction.

br-r37-c1-0seyw
"""

from __future__ import annotations

import pytest
import networkx as nx

import franken_networkx as fnx


def _fingerprint(G):
    """Exact, order-sensitive fingerprint: nodes, edges, and graph kind."""
    return (
        [str(n) for n in G.nodes()],
        [tuple(str(x) for x in e) for e in G.edges()],
        G.is_directed(),
        G.is_multigraph(),
    )


# Each entry: (id, callable(lib, seed) -> graph). The callable must build
# the same graph from `lib` (fnx or nx) given the seed.
_GENERATORS = [
    ("gnp_random_graph",
     lambda lib, s: lib.gnp_random_graph(25, 0.2, seed=s)),
    ("gnp_random_graph_directed",
     lambda lib, s: lib.gnp_random_graph(20, 0.2, seed=s, directed=True)),
    ("fast_gnp_random_graph",
     lambda lib, s: lib.fast_gnp_random_graph(25, 0.2, seed=s)),
    ("gnm_random_graph",
     lambda lib, s: lib.gnm_random_graph(25, 40, seed=s)),
    ("erdos_renyi_graph",
     lambda lib, s: lib.erdos_renyi_graph(22, 0.25, seed=s)),
    ("barabasi_albert_graph",
     lambda lib, s: lib.barabasi_albert_graph(25, 3, seed=s)),
    ("dual_barabasi_albert_graph",
     lambda lib, s: lib.dual_barabasi_albert_graph(25, 1, 3, 0.5, seed=s)),
    ("extended_barabasi_albert_graph",
     lambda lib, s: lib.extended_barabasi_albert_graph(22, 2, 0.2, 0.2, seed=s)),
    ("watts_strogatz_graph",
     lambda lib, s: lib.watts_strogatz_graph(25, 4, 0.3, seed=s)),
    ("newman_watts_strogatz_graph",
     lambda lib, s: lib.newman_watts_strogatz_graph(25, 4, 0.3, seed=s)),
    ("connected_watts_strogatz_graph",
     lambda lib, s: lib.connected_watts_strogatz_graph(25, 4, 0.3, seed=s)),
    ("random_regular_graph",
     lambda lib, s: lib.random_regular_graph(4, 20, seed=s)),
    ("powerlaw_cluster_graph",
     lambda lib, s: lib.powerlaw_cluster_graph(30, 3, 0.4, seed=s)),
    ("random_lobster",
     lambda lib, s: lib.random_lobster(15, 0.4, 0.4, seed=s)),
    ("random_powerlaw_tree",
     lambda lib, s: lib.random_powerlaw_tree(15, seed=s, tries=1_000_000)),
    ("duplication_divergence_graph",
     lambda lib, s: lib.duplication_divergence_graph(20, 0.4, seed=s)),
]


@pytest.mark.parametrize("name,builder", _GENERATORS, ids=[g[0] for g in _GENERATORS])
@pytest.mark.parametrize("seed", range(20))
def test_seeded_generator_matches_networkx_byte_exact(name, builder, seed):
    fg = builder(fnx, seed)
    ng = builder(nx, seed)
    assert _fingerprint(fg) == _fingerprint(ng), (
        f"{name} seed={seed}: fnx graph diverges from networkx"
    )


@pytest.mark.parametrize("name,builder", _GENERATORS, ids=[g[0] for g in _GENERATORS])
def test_seeded_generator_is_reproducible(name, builder):
    """Same seed twice → identical graph (determinism)."""
    a = builder(fnx, 12345)
    b = builder(fnx, 12345)
    assert _fingerprint(a) == _fingerprint(b), f"{name}: not reproducible for fixed seed"


@pytest.mark.parametrize("name,builder", _GENERATORS, ids=[g[0] for g in _GENERATORS])
def test_distinct_seeds_usually_differ(name, builder):
    """A handful of distinct seeds should not all collapse to one graph.

    Guards against a broken RNG that ignores the seed entirely. Tiny
    deterministic generators may coincide for some pairs, so we only
    require that not *all* sampled seeds yield the same signature.
    """
    sigs = {repr(_fingerprint(builder(fnx, s))) for s in range(6)}
    assert len(sigs) > 1, f"{name}: every seed produced an identical graph"


# br-r37-c1-cdf1v: networkx's @py_random_state accepts a random.Random, a numpy
# RandomState or Generator (wrapped), and None - which means the GLOBAL random
# module state, so random.seed(k) makes networkx reproducible. These generators
# built random.Random(seed) themselves (TypeError on an instance, fresh entropy
# for None), or ran another algorithm (random_unlabeled_tree, the labeled rooted
# forest), or dropped graph attributes networkx sets (root, name).
_SEED_KIND_GENERATORS = [
    ("random_labeled_tree", lambda lib, s: lib.random_labeled_tree(9, seed=s)),
    ("random_labeled_rooted_tree", lambda lib, s: lib.random_labeled_rooted_tree(9, seed=s)),
    ("random_labeled_rooted_forest", lambda lib, s: lib.random_labeled_rooted_forest(9, seed=s)),
    ("random_unlabeled_tree", lambda lib, s: lib.random_unlabeled_tree(9, seed=s)),
    ("random_unlabeled_tree_many", lambda lib, s: lib.random_unlabeled_tree(8, number_of_trees=3, seed=s)),
    ("relaxed_caveman_graph", lambda lib, s: lib.relaxed_caveman_graph(3, 4, 0.3, seed=s)),
    ("soft_random_geometric_graph", lambda lib, s: lib.soft_random_geometric_graph(10, 0.4, seed=s)),
    ("thresholded_random_geometric_graph", lambda lib, s: lib.thresholded_random_geometric_graph(10, 0.4, 0.2, seed=s)),
    ("geographical_threshold_graph", lambda lib, s: lib.geographical_threshold_graph(10, 0.5, seed=s)),
    ("waxman_graph", lambda lib, s: lib.waxman_graph(10, seed=s)),
    ("navigable_small_world_graph", lambda lib, s: lib.navigable_small_world_graph(3, seed=s)),
    ("k_random_intersection_graph", lambda lib, s: lib.k_random_intersection_graph(8, 4, 2, seed=s)),
    ("k_random_intersection_k_over_m", lambda lib, s: lib.k_random_intersection_graph(5, 2, 3, seed=s)),
    ("dual_barabasi_albert_graph", lambda lib, s: lib.dual_barabasi_albert_graph(12, 1, 2, 0.5, seed=s)),
    ("uniform_random_intersection_graph", lambda lib, s: lib.uniform_random_intersection_graph(8, 4, 0.3, seed=s)),
    ("general_random_intersection_graph", lambda lib, s: lib.general_random_intersection_graph(9, 4, [0.1, 0.4, 0.6, 0.3], seed=s)),
    ("partial_duplication_graph", lambda lib, s: lib.partial_duplication_graph(10, 3, 0.5, 0.3, seed=s)),
    ("random_partition_graph", lambda lib, s: lib.random_partition_graph([4, 5], 0.5, 0.1, seed=s)),
    ("planted_partition_graph", lambda lib, s: lib.planted_partition_graph(2, 4, 0.5, 0.1, seed=s)),
    ("gnm_random_graph", lambda lib, s: lib.gnm_random_graph(8, 10, seed=s)),
]
# gnm_random_graph's seed=None call still takes the native kernel (fresh entropy,
# not the global state) - the MT-state bead, br-r37-c1-ols3t.
_NATIVE_WHEN_NONE = {"gnm_random_graph"}


def _seeded(kind):
    import random

    import numpy as np

    if kind == "int":
        return 11
    if kind == "random.Random":
        return random.Random(11)
    if kind == "RandomState":
        return np.random.RandomState(11)
    if kind == "Generator":
        return np.random.default_rng(11)
    random.seed(11)
    np.random.seed(11)
    return None


def _outcome(builder, lib, kind):
    """The graphs built - order, data and graph attributes - or the exception."""
    try:
        result = builder(lib, _seeded(kind))
    except Exception as exc:  # noqa: BLE001 - the exception is the outcome
        return ("raise", type(exc).__name__, str(exc))
    graphs = result if isinstance(result, list) else [result]
    return [
        (
            _fingerprint(g),
            [repr(d) for _, d in g.nodes(data=True)],
            [repr(d) for *_, d in g.edges(data=True)],
            [list(g.adj[u]) for u in g],
            dict(g.graph),
        )
        for g in graphs
    ]


@pytest.mark.parametrize("kind", ["int", "random.Random", "RandomState", "Generator", "global None"])
@pytest.mark.parametrize("name,builder", _SEED_KIND_GENERATORS, ids=[g[0] for g in _SEED_KIND_GENERATORS])
def test_every_seed_kind_draws_networkx_graph(name, builder, kind):
    if kind == "global None" and name in _NATIVE_WHEN_NONE:
        pytest.skip("seed=None takes the native kernel - br-r37-c1-ols3t")
    assert _outcome(builder, fnx, kind) == _outcome(builder, nx, kind)
