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
    assert _outcome(builder, fnx, kind) == _outcome(builder, nx, kind)


def _native_seed(kind):
    import numpy as np

    return {
        "-1": -1,
        "-12345": -12345,
        "True": True,
        "1.5": 1.5,
        "nan": float("nan"),
        "str": "x",
        "numpy int": np.int64(3),
    }[kind]


def _call_outcome(builder, lib, seed):
    try:
        g = builder(lib, seed)
    except Exception as exc:  # noqa: BLE001 - the exception is the outcome
        return type(exc).__name__, str(exc)
    return _fingerprint(g)


# br-r37-c1-cdf1v: the native kernels seed MT19937 as random.seed(int) does -
# from abs(int) - but _native_random_seed masked a negative int to 2**64 - n
# (another graph), and handed a float / str / numpy int to the binding
# (TypeError, or a graph for a float) where networkx's create_py_random_state
# raises ValueError("... cannot be used to generate a random.Random instance").
@pytest.mark.parametrize("kind", ["-1", "-12345", "True", "1.5", "nan", "str", "numpy int"])
@pytest.mark.parametrize("name,builder", _GENERATORS, ids=[g[0] for g in _GENERATORS])
def test_int_like_and_invalid_seeds_match_networkx(name, builder, kind):
    assert _call_outcome(builder, fnx, _native_seed(kind)) == _call_outcome(builder, nx, _native_seed(kind))


# br-r37-c1-cdf1v: spectral_graph_forge ran its own algorithm (a median threshold
# over a noise blend, relabelled to G's nodes), so no seed drew networkx's graph,
# and np.random.RandomState(seed) raised TypeError on a numpy RNG. It is
# networkx's algorithm on networkx's np_random_state now.
@pytest.mark.parametrize("kind", ["int", "RandomState", "Generator", "global None", "random.Random", "1.5"])
@pytest.mark.parametrize("transformation", ["identity", "modularity", "bogus"])
@pytest.mark.parametrize("alpha", [0.0, 0.4, 1.0, 1.7])
@pytest.mark.parametrize(
    "build",
    [
        lambda lib: lib.karate_club_graph(),
        lambda lib: lib.relabel_nodes(lib.cycle_graph(6), dict(enumerate("abcdef"))),
        lambda lib: lib.Graph([(0, 1, {"weight": 3}), (1, 2, {"weight": 0.5}), (2, 0, {})]),
    ],
    ids=["karate", "str_labels", "weighted"],
)
def test_spectral_graph_forge_is_networkx_for_every_seed_kind(build, alpha, transformation, kind):
    import numpy as np

    def seed():
        if kind == "int":
            return 11
        if kind == "RandomState":
            return np.random.RandomState(4)
        if kind == "Generator":
            return np.random.default_rng(4)
        if kind == "random.Random":
            import random

            return random.Random(3)
        if kind == "1.5":
            return 1.5
        np.random.seed(7)
        return None

    def outcome(lib):
        s = seed()
        try:
            g = lib.spectral_graph_forge(build(lib), alpha, transformation=transformation, seed=s)
        except Exception as exc:  # noqa: BLE001 - the exception is the outcome
            return type(exc).__name__, str(exc).replace(hex(id(s)), "ID")
        return list(g.nodes(data=True)), list(g.edges(data=True)), dict(g.graph)

    assert outcome(fnx) == outcome(nx)


# br-r37-c1-cdf1v: networkx's @py_random_state resolves the seed before
# navigable_small_world_graph's p / q / r checks.
@pytest.mark.parametrize("args", [(3, 0), (3, 1, -1), (3, 1, 1, -1)])
@pytest.mark.parametrize("seed", [1.5, "x"])
def test_navigable_small_world_resolves_the_seed_first(args, seed):
    assert _call_outcome(lambda lib, s: lib.navigable_small_world_graph(*args, seed=s), fnx, seed) == _call_outcome(
        lambda lib, s: lib.navigable_small_world_graph(*args, seed=s), nx, seed
    )


# br-r37-c1-ols3t: the native kernels draw networkx's stream for every seed
# networkx resolves to a random.Random - the instance a caller passes, the
# global random._inst for None (and for the random module), random.Random(seed)
# for an int of 2**64 or more - by running on its getstate() and setstate()ing
# the advanced state back, so the caller's generator ends where networkx leaves
# it. Before, the bridge drew ONE u64 from it (fresh entropy for None): another
# graph, and the generator left elsewhere. A numpy seed runs networkx's body.
_NATIVE_CALLS = [
    ("gnp", lambda lib, s: lib.gnp_random_graph(20, 0.3, seed=s)),
    ("gnp_directed", lambda lib, s: lib.gnp_random_graph(15, 0.3, seed=s, directed=True)),
    ("gnp_p0", lambda lib, s: lib.gnp_random_graph(6, 0, seed=s)),
    ("gnp_p1", lambda lib, s: lib.gnp_random_graph(6, 1, seed=s)),
    ("erdos_renyi_create_using", lambda lib, s: lib.erdos_renyi_graph(8, 0.4, seed=s, create_using=lib.Graph())),
    ("gnm", lambda lib, s: lib.gnm_random_graph(20, 30, seed=s)),
    ("gnm_directed", lambda lib, s: lib.gnm_random_graph(12, 40, seed=s, directed=True)),
    ("gnm_saturated", lambda lib, s: lib.gnm_random_graph(5, 50, seed=s)),
    ("fast_gnp", lambda lib, s: lib.fast_gnp_random_graph(40, 0.1, seed=s)),
    ("fast_gnp_directed", lambda lib, s: lib.fast_gnp_random_graph(30, 0.1, seed=s, directed=True)),
    ("watts_strogatz", lambda lib, s: lib.watts_strogatz_graph(25, 4, 0.3, seed=s)),
    ("newman_watts_strogatz", lambda lib, s: lib.newman_watts_strogatz_graph(25, 4, 0.3, seed=s)),
    ("newman_watts_strogatz_create_using", lambda lib, s: lib.newman_watts_strogatz_graph(9, 4, 0.5, seed=s, create_using=lib.Graph)),
    ("connected_watts_strogatz", lambda lib, s: lib.connected_watts_strogatz_graph(25, 4, 0.3, seed=s)),
    ("connected_watts_strogatz_exhausted", lambda lib, s: lib.connected_watts_strogatz_graph(10, 2, 0.9, tries=3, seed=s)),
    ("powerlaw_cluster", lambda lib, s: lib.powerlaw_cluster_graph(30, 3, 0.4, seed=s)),
    ("random_geometric", lambda lib, s: lib.random_geometric_graph(20, 0.3, seed=s)),
    ("gnc", lambda lib, s: lib.gnc_graph(15, seed=s)),
    ("gnc_multidigraph", lambda lib, s: lib.gnc_graph(6, create_using=lib.MultiDiGraph, seed=s)),
    ("gnr", lambda lib, s: lib.gnr_graph(15, 0.4, seed=s)),
    ("scale_free", lambda lib, s: lib.scale_free_graph(30, seed=s)),
]


def _streamed_seed(kind):
    import random

    import numpy as np

    random.seed(99)
    np.random.seed(99)
    return {
        "random.Random": lambda: random.Random(5),
        "global None": lambda: None,
        "random module": lambda: random,
        "int >= 2**64": lambda: 2**64 + 5,
        "RandomState": lambda: np.random.RandomState(5),
        "Generator": lambda: np.random.default_rng(5),
        "numpy.random module": lambda: np.random,
    }[kind]()


def _outcome_and_rng_state(builder, lib, kind):
    import random

    import numpy as np

    seed = _streamed_seed(kind)
    try:
        g = builder(lib, seed)
    except Exception as exc:  # noqa: BLE001 - the exception is the outcome
        result = (type(exc).__name__, str(exc))
    else:
        kw = {"keys": True} if g.is_multigraph() else {}
        result = (
            type(g).__name__,
            [repr(x) for x in g.nodes(data=True)],
            [repr(e) for e in g.edges(data=True, **kw)],
            [list(map(repr, g.adj[u])) for u in g],
        )
    if isinstance(seed, random.Random):
        instance = seed.getstate()
    elif isinstance(seed, np.random.RandomState):
        instance = repr(seed.get_state(legacy=False))
    elif isinstance(seed, np.random.Generator):
        instance = repr(seed.bit_generator.state)
    else:
        instance = None
    return result, instance, random.getstate(), repr(np.random.get_state(legacy=False))


@pytest.mark.parametrize(
    "kind",
    ["random.Random", "global None", "random module", "int >= 2**64", "RandomState", "Generator",
     "numpy.random module"],
)
@pytest.mark.parametrize("name,builder", _NATIVE_CALLS, ids=[c[0] for c in _NATIVE_CALLS])
def test_native_generators_draw_and_advance_networkx_stream(name, builder, kind):
    assert _outcome_and_rng_state(builder, fnx, kind) == _outcome_and_rng_state(builder, nx, kind)


# br-r37-c1-cdf1v: networkx's decorator resolves the seed before any argument
# check, so an invalid seed raises its ValueError whatever else is wrong.
_BAD_ARGUMENT_CALLS = [
    ("barabasi_albert_graph", (5, 0)), ("dual_barabasi_albert_graph", (5, 0, 1, 0.5)),
    ("extended_barabasi_albert_graph", (5, 0, 0.1, 0.1)), ("duplication_divergence_graph", (5, 1.5)),
    ("gn_graph", (-1,)), ("geographical_threshold_graph", (-1, 0.5)), ("planted_partition_graph", (2, 3, 1.5, 0.1)),
    ("random_partition_graph", ([3, 3], 1.5, 0.1)), ("random_regular_graph", (3, 5)), ("random_labeled_tree", (0,)),
    ("random_labeled_rooted_tree", (0,)), ("random_unlabeled_tree", (0,)), ("random_unlabeled_rooted_tree", (0,)),
    ("soft_random_geometric_graph", (-1, 0.3)), ("thresholded_random_geometric_graph", (-1, 0.3, 0.1)),
    ("waxman_graph", (-1,)), ("random_powerlaw_tree", (0,)), ("random_powerlaw_tree_sequence", (0,)),
    ("gnp_random_graph", (-1, 0.5)), ("fast_gnp_random_graph", (-1, 0.5)), ("gnm_random_graph", (-1, 3)),
    ("watts_strogatz_graph", (5, 7, 0.1)), ("newman_watts_strogatz_graph", (5, 7, 0.1)),
    ("connected_watts_strogatz_graph", (5, 7, 0.1)), ("powerlaw_cluster_graph", (5, 0, 0.1)),
    ("random_geometric_graph", (-1, 0.3)), ("gnc_graph", (-1,)), ("gnr_graph", (5, 1.5)), ("scale_free_graph", (5, -1)),
]


@pytest.mark.parametrize("seed", [1.5, "x"])
@pytest.mark.parametrize("name,args", _BAD_ARGUMENT_CALLS, ids=[c[0] for c in _BAD_ARGUMENT_CALLS])
def test_an_invalid_seed_is_rejected_before_the_arguments(name, args, seed):
    assert _call_outcome(lambda lib, s: getattr(lib, name)(*args, seed=s), fnx, seed) == _call_outcome(
        lambda lib, s: getattr(lib, name)(*args, seed=s), nx, seed
    )
