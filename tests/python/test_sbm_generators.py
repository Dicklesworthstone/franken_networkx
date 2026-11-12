"""Tests for stochastic-block-model generator wrappers."""

import pytest

import franken_networkx as fnx


def test_stochastic_block_model_reproducibility():
    sizes = [3, 2]
    probs = [[0.8, 0.1], [0.1, 0.7]]

    left = fnx.stochastic_block_model(sizes, probs, seed=3)
    right = fnx.stochastic_block_model(sizes, probs, seed=3)

    assert left.number_of_nodes() == 5
    assert sorted(left.edges()) == sorted(right.edges())


def test_planted_partition_and_random_partition_graph_sizes():
    planted = fnx.planted_partition_graph(2, 3, 0.9, 0.1, seed=2)
    partition = fnx.random_partition_graph([3, 2], 0.8, 0.2, seed=2)

    assert planted.number_of_nodes() == 6
    assert partition.number_of_nodes() == 5


def test_gaussian_random_partition_graph_is_directed_when_requested():
    graph = fnx.gaussian_random_partition_graph(10, 3, 1, 0.8, 0.1, directed=True, seed=4)

    assert graph.is_directed()
    assert graph.number_of_nodes() == 10


def test_relaxed_caveman_graph_size():
    graph = fnx.relaxed_caveman_graph(3, 4, 0.25, seed=5)

    assert graph.number_of_nodes() == 12
    assert graph.number_of_edges() > 0


def test_stochastic_block_model_default_delegates_to_networkx_for_parity(monkeypatch):
    """br-r37-c1-kilv4: br-sbmrng made stochastic_block_model
    delegate to nx for exact-output parity (the Rust native path
    produced ~25% of nx's edge count for symmetric block matrices).
    Verify the delegation is in effect — _rust_stochastic_block_model
    must NOT be called.
    """
    def fail(*args, **kwargs):
        raise AssertionError(
            "_rust_stochastic_block_model should not be used: "
            "br-sbmrng routes through nx for parity"
        )

    monkeypatch.setattr(fnx, "_rust_stochastic_block_model", fail)

    graph = fnx.stochastic_block_model([2, 1], [[0.0, 1.0], [1.0, 0.0]], seed=7)

    # The result still carries the standard SBM metadata regardless
    # of which backend produced it.
    assert graph.graph["partition"] == [{0, 1}, {2}]
    assert graph.graph["name"] == "stochastic_block_model"
    assert graph.nodes[0]["block"] == 0
    assert graph.nodes[2]["block"] == 1


def test_stochastic_block_model_fallback_preserves_nodelist_and_attrs(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("native fast path should not be used")

    monkeypatch.setattr(fnx, "_rust_stochastic_block_model", fail)

    graph = fnx.stochastic_block_model(
        [2, 1],
        [[0.0, 0.0], [0.0, 0.0]],
        nodelist=["left", "right", "solo"],
        seed=11,
    )

    assert list(graph.nodes()) == ["left", "right", "solo"]
    assert graph.graph["partition"] == [{"left", "right"}, {"solo"}]
    assert graph.graph["name"] == "stochastic_block_model"
    assert graph.nodes["left"]["block"] == 0
    assert graph.nodes["solo"]["block"] == 1


def test_stochastic_block_model_validates_probability_matrix():
    with pytest.raises(fnx.NetworkXError, match="'p' must be symmetric."):
        fnx.stochastic_block_model([1, 1], [[0.0, 1.0], [0.0, 0.0]])


def _sbm_seed(kind):
    import random

    import numpy as np

    if kind == "int":
        return 11
    if kind == "random.Random":
        return random.Random(3)
    if kind == "RandomState":
        return np.random.RandomState(4)
    if kind == "Generator":
        return np.random.default_rng(4)
    if kind in ("RandomState adapter", "Generator adapter"):
        from networkx.utils import create_py_random_state

        raw = np.random.RandomState(4) if kind == "RandomState adapter" else np.random.default_rng(4)
        return create_py_random_state(raw)
    if kind in ("float", "str"):
        return 1.5 if kind == "float" else "x"
    random.seed(7)
    np.random.seed(7)
    if kind == "random module":
        return random
    if kind == "numpy.random module":
        return np.random
    if kind == "numpy global RandomState":
        return np.random.mtrand._rand
    return None


# br-r37-c1-cdf1v: networkx's @py_random_state resolves the seed before the
# body - a bad seed with a bad p is ValueError, not fnx's TypeError from len(p)
# - and seed=None is the global random state, which the native kernel drew as
# fresh entropy.
@pytest.mark.parametrize(
    "kind", ["int", "random.Random", "RandomState", "Generator", "float", "str", "global None"]
)
@pytest.mark.parametrize(
    "sizes, p, kwargs",
    [
        ([4, 5], [[0.5, 0.1], [0.1, 0.5]], {}),
        ([4, 5], [[0.5, 0.1], [0.3, 0.5]], {"directed": True, "selfloops": True}),
        ([3, 3], [[0.6, 0.2], [0.2, 0.6]], {"sparse": False}),
        ([2, 2], [[0.9, 0.3], [0.3, 0.9]], {"nodelist": ["a", "b", "c", "d"]}),
        ([4, 3], 0.3, {}),
    ],
    ids=["undirected", "directed_selfloops", "dense", "nodelist", "bad_p"],
)
def test_stochastic_block_model_takes_networkx_seeds(sizes, p, kwargs, kind):
    import networkx as nx

    def outcome(lib):
        try:
            g = lib.stochastic_block_model(sizes, p, seed=_sbm_seed(kind), **kwargs)
        except Exception as exc:  # noqa: BLE001 - the exception is the outcome
            return type(exc).__name__, str(exc)
        # An undirected edge compares without orientation: with a nodelist fnx
        # lists nodes in nodelist order (br-r37-c1-hkbd8), networkx in its
        # blocks' set order, so G.edges() may orient an edge the other way.
        return (
            sorted(map(repr, g.nodes(data=True))),
            sorted(repr(e if g.is_directed() else sorted(map(repr, e))) for e in g.edges()),
            g.graph["name"],
            [sorted(map(repr, block)) for block in g.graph["partition"]],
        )

    assert outcome(fnx) == outcome(nx)


@pytest.mark.parametrize(
    "kind",
    [
        "random.Random", "RandomState", "Generator", "global None", "random module",
        "numpy.random module", "numpy global RandomState", "RandomState adapter",
        "Generator adapter",
    ],
)
@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("sparse", [False, True])
def test_partition_pipeline_preserves_shared_rng_state(kind, directed, sparse):
    """Composite generators reuse one stream across their normalization boundaries."""
    import random

    import networkx as nx
    import numpy as np

    def outcome(lib):
        random.seed(7)
        np.random.seed(7)
        seed = _sbm_seed(kind)
        graphs = []
        for _ in range(2):
            graphs.extend([
                lib.stochastic_block_model(
                    [3, 4], [[0.55, 0.2], [0.2, 0.7]], seed=seed,
                    directed=directed, selfloops=True, sparse=sparse,
                ),
                lib.random_partition_graph([4, 5], 0.6, 0.2, seed=seed, directed=directed),
                lib.planted_partition_graph(3, 4, 0.55, 0.15, seed=seed, directed=directed),
                lib.gaussian_random_partition_graph(
                    18, 4, 2, 0.55, 0.15, directed=directed, seed=seed,
                ),
            ])
        fingerprints = [
            (
                graph.is_directed(), graph.is_multigraph(),
                list(graph.nodes(data=True)), list(graph.edges(data=True)),
                dict(graph.graph), [list(graph.adj[node]) for node in graph],
            )
            for graph in graphs
        ]
        raw = getattr(seed, "_rng", seed)
        if isinstance(raw, random.Random):
            instance_state = raw.getstate()
        elif isinstance(raw, np.random.RandomState):
            instance_state = raw.get_state()
        elif isinstance(raw, np.random.Generator):
            instance_state = raw.bit_generator.state
        else:
            instance_state = None
        return fingerprints, instance_state, random.getstate(), np.random.get_state()

    saved_python = random.getstate()
    saved_numpy = np.random.get_state()
    try:
        actual = outcome(fnx)
        expected = outcome(nx)
    finally:
        random.setstate(saved_python)
        np.random.set_state(saved_numpy)
    assert actual[0] == expected[0]
    np.testing.assert_equal(actual[1:], expected[1:])
