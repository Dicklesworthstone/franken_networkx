"""Differential parity for pagerank's parameter combinations.

Default pagerank is covered elsewhere; this pins the complex knobs whose
semantics are easy to get subtly wrong: ``personalization``, ``dangling``,
``nstart``, ``weight``/``alpha`` and their combination.

br-r37-c1-ktky5
"""

from __future__ import annotations

import random

import franken_networkx as fnx
import networkx as nx
import pytest


def _weighted_digraph(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(5, 9)
    fg = fnx.DiGraph()
    ng = nx.DiGraph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                w = rng.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    vec = {i: rng.random() + 0.1 for i in range(n)}
    return fg, ng, n, vec


def _close(a, b, tol=1e-6):
    assert set(a) == set(b)
    for k in b:
        assert a[k] == pytest.approx(b[k], abs=tol)


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_personalization(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, personalization=vec),
           nx.pagerank(ng, personalization=vec))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_dangling(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, dangling=vec), nx.pagerank(ng, dangling=vec))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_nstart(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, nstart=vec), nx.pagerank(ng, nstart=vec))


@pytest.mark.parametrize("alpha", [0.5, 0.7, 0.95])
@pytest.mark.parametrize("seed", range(15))
def test_pagerank_weight_and_alpha(alpha, seed):
    fg, ng, _, _ = _weighted_digraph(seed)
    _close(fnx.pagerank(fg, weight="weight", alpha=alpha),
           nx.pagerank(ng, weight="weight", alpha=alpha))


@pytest.mark.parametrize("seed", range(40))
def test_pagerank_combined_personalization_dangling_weight(seed):
    fg, ng, _, vec = _weighted_digraph(seed)
    dangling = {k: v + 0.05 for k, v in vec.items()}
    _close(
        fnx.pagerank(fg, personalization=vec, dangling=dangling, weight="weight"),
        nx.pagerank(ng, personalization=vec, dangling=dangling, weight="weight"),
    )


@pytest.mark.parametrize("workers", [None, 1, 4])
@pytest.mark.parametrize("weight", [None, "weight"])
def test_pagerank_many_is_byte_identical_to_separate_networkx_calls(
    workers, weight
):
    fg, ng, n, _ = _weighted_digraph(917, p=0.55)
    rng = random.Random(1229)
    personalizations = [
        {node: rng.random() + 0.01 for node in rng.sample(range(n), 3)}
        for _ in range(8)
    ]

    actual = fnx.pagerank_many(
        fg,
        personalizations,
        alpha=0.9,
        max_iter=250,
        tol=1.0e-9,
        weight=weight,
        workers=workers,
    )
    expected = [
        nx.pagerank(
            ng,
            personalization=personalization,
            alpha=0.9,
            max_iter=250,
            tol=1.0e-9,
            weight=weight,
        )
        for personalization in personalizations
    ]
    assert actual == expected


def test_pagerank_many_preserves_query_order_and_degenerate_shapes():
    fg, ng, n, _ = _weighted_digraph(41)
    personalizations = [{node: 1.0} for node in range(n)]
    actual = fnx.pagerank_many(fg, personalizations, weight=None, workers=3)
    expected = [
        nx.pagerank(ng, personalization=p, weight=None)
        for p in personalizations
    ]
    assert actual == expected
    assert fnx.pagerank_many(fg, [], workers=3) == []
    assert fnx.pagerank_many(fnx.DiGraph(), [None, {}], workers=2) == [{}, {}]


def test_pagerank_many_rejects_zero_sum_personalization_and_bad_workers():
    graph = fnx.path_graph(4, create_using=fnx.DiGraph)
    with pytest.raises(ZeroDivisionError):
        fnx.pagerank_many(graph, [{0: 0.0}], workers=1)
    with pytest.raises(ValueError, match="workers must be greater than 0"):
        fnx.pagerank_many(graph, [{0: 1.0}], workers=0)


# br-r37-c1-mub4s: optional vectors must consume the existing native matrix
# builder/cache, without changing NetworkX's floating-point association order.
def _matrix_pair(graph_name):
    nodes = [("root", 2), "sink", 7, "leaf", ("isolated",), "second"]
    edges = [
        (nodes[0], nodes[1], {"weight": 1.5, "other": 4.0}),
        (nodes[0], nodes[2], {"weight": 2.25}),
        (nodes[2], nodes[1], {"weight": 0.75, "other": 2.0}),
        (nodes[1], nodes[3], {"weight": 2.0}),
        (nodes[3], nodes[0], {"weight": 1.0, "other": 0.5}),
        (nodes[3], nodes[3], {"weight": 1.125}),
    ]
    fg = getattr(fnx, graph_name)()
    ng = getattr(nx, graph_name)()
    for graph in (fg, ng):
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
    return fg, ng


def _matrix_kwargs(variant="combined"):
    vectors = {
        "personalization": {"sink": 0.75, 7: 1.5, ("isolated",): 2.0, "outside": 99},
        "nstart": {("root", 2): 1.0, "leaf": 2.5, "outside": 7.0},
        "dangling": {"leaf": 2.0, "second": 1.0, "outside": 9.0},
    }
    chosen = vectors if variant == "combined" else {variant: vectors[variant]}
    return dict(chosen, tol=1.0e-10, max_iter=250)


def _assert_matrix_rank_exact(actual, expected):
    assert list(actual) == list(expected)
    assert actual == expected
    assert all(type(value) is float for value in actual.values())
    assert {node: value.hex() for node, value in actual.items()} == {
        node: value.hex() for node, value in expected.items()
    }


def _profile_matrix_rank(graph, **kwargs):
    import cProfile

    profiler = cProfile.Profile()
    actual = profiler.runcall(fnx.pagerank, graph, **kwargs)
    names = [
        entry.code if isinstance(entry.code, str) else entry.code.co_name
        for entry in profiler.getstats()
    ]
    return actual, names


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("variant", ["personalization", "dangling", "nstart", "combined"])
def test_optional_vectors_build_native_matrix_and_match_exact_oracle(
    graph_name, weight, variant
):
    fg, ng = _matrix_pair(graph_name)
    kwargs = _matrix_kwargs(variant)
    actual, names = _profile_matrix_rank(fg, weight=weight, **kwargs)
    _assert_matrix_rank_exact(actual, nx.pagerank(ng, weight=weight, **kwargs))
    assert "to_scipy_sparse_array" not in names
    cache = vars(fg).get("_fnx_pagerank_scipy_matrix_cache")
    assert cache is not None
    assert cache[1][0] == list(ng)


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("prime", ["default", "personalized"])
def test_optional_vectors_share_matrix_with_default_and_other_vectors(
    graph_name, weight, prime
):
    fg, ng = _matrix_pair(graph_name)
    kwargs = {} if prime == "default" else _matrix_kwargs("personalization")
    fnx.pagerank(fg, weight=weight, **kwargs)
    cache = vars(fg).get("_fnx_pagerank_scipy_matrix_cache")
    assert cache is not None
    for variant in ("dangling", "nstart", "combined"):
        kwargs = _matrix_kwargs(variant)
        actual, names = _profile_matrix_rank(fg, weight=weight, **kwargs)
        _assert_matrix_rank_exact(actual, nx.pagerank(ng, weight=weight, **kwargs))
        assert vars(fg)["_fnx_pagerank_scipy_matrix_cache"] is cache
        assert "to_scipy_sparse_array" not in names
        assert not any("adjacency_csr_bytes" in name for name in names)
        assert not any("adjacency_default_order_arrays" in name for name in names)
    fnx.pagerank(fg, weight=weight)
    assert vars(fg)["_fnx_pagerank_scipy_matrix_cache"] is cache


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("mutation", ["add_edge", "remove_edge", "add_node", "remove_node"])
def test_optional_vector_matrix_invalidates_on_topology_changes(
    graph_name, weight, mutation
):
    fg, ng = _matrix_pair(graph_name)
    kwargs = _matrix_kwargs()
    fnx.pagerank(fg, weight=weight, **kwargs)
    cache = vars(fg).get("_fnx_pagerank_scipy_matrix_cache")
    assert cache is not None
    for graph in (fg, ng):
        if mutation == "add_edge":
            graph.add_edge("second", 7, weight=3.5)
        elif mutation == "remove_edge":
            graph.remove_edge("sink", "leaf")
        elif mutation == "add_node":
            graph.add_node(("new", 31))
        else:
            graph.remove_node(7)
    actual = fnx.pagerank(fg, weight=weight, **kwargs)
    _assert_matrix_rank_exact(actual, nx.pagerank(ng, weight=weight, **kwargs))
    assert vars(fg)["_fnx_pagerank_scipy_matrix_cache"] is not cache


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
def test_optional_vector_matrix_tracks_repeated_writes_through_held_edge_dict(graph_name):
    fg, ng = _matrix_pair(graph_name)
    kwargs = _matrix_kwargs()
    held_f = fg[("root", 2)]["sink"]
    held_n = ng[("root", 2)]["sink"]
    for value in (1.5, 11.25, 0.125, 4.0):
        held_f["weight"] = value
        held_n["weight"] = value
        _assert_matrix_rank_exact(
            fnx.pagerank(fg, weight="weight", **kwargs),
            nx.pagerank(ng, weight="weight", **kwargs),
        )
    del held_f["weight"]
    del held_n["weight"]
    _assert_matrix_rank_exact(
        fnx.pagerank(fg, weight="weight", **kwargs),
        nx.pagerank(ng, weight="weight", **kwargs),
    )


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
def test_optional_vector_matrix_keys_weight_and_returns_independent_results(graph_name):
    fg, ng = _matrix_pair(graph_name)
    kwargs = _matrix_kwargs()
    seen = []
    for weight in ("weight", None, "other", "missing", "weight"):
        actual = fnx.pagerank(fg, weight=weight, **kwargs)
        _assert_matrix_rank_exact(actual, nx.pagerank(ng, weight=weight, **kwargs))
        cache = vars(fg).get("_fnx_pagerank_scipy_matrix_cache")
        assert cache is not None
        actual.clear()
        repeated = fnx.pagerank(fg, weight=weight, **kwargs)
        _assert_matrix_rank_exact(repeated, nx.pagerank(ng, weight=weight, **kwargs))
        assert vars(fg)["_fnx_pagerank_scipy_matrix_cache"] is cache
        seen.append(repeated)
    assert seen[0] == seen[-1]
    assert seen[0] != seen[1]


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("view_kind", ["subgraph", "converted", "reverse", "subclass"])
def test_optional_vector_matrix_excludes_nonexact_graph_cache_types(graph_name, view_kind):
    fg, ng = _matrix_pair(graph_name)
    parent_f, parent_n = fg, ng
    if view_kind == "subgraph":
        selected = [node for node in fg if node != 7]
        fg = fg.subgraph(selected)
        ng = ng.subgraph(selected)
    elif view_kind == "converted":
        if graph_name == "Graph":
            fg, ng = fg.to_directed(as_view=True), ng.to_directed(as_view=True)
        else:
            fg, ng = fg.to_undirected(as_view=True), ng.to_undirected(as_view=True)
    elif view_kind == "reverse":
        if graph_name == "Graph":
            fg, ng = fg.to_directed(as_view=True), ng.to_directed(as_view=True)
        fg, ng = fg.reverse(copy=False), ng.reverse(copy=False)
    else:
        class GraphSubclass(getattr(fnx, graph_name)):
            pass

        fg = GraphSubclass(fg)
    kwargs = _matrix_kwargs()
    for round_index in range(2):
        if round_index and view_kind != "subclass":
            for graph in (parent_f, parent_n):
                graph[("root", 2)]["sink"]["weight"] = 4.0
        for weight in (None, "weight"):
            _assert_matrix_rank_exact(
                fnx.pagerank(fg, weight=weight, **kwargs),
                nx.pagerank(ng, weight=weight, **kwargs),
            )
            assert "_fnx_pagerank_scipy_matrix_cache" not in vars(fg)


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("variant", ["personalization", "dangling", "nstart", "combined"])
def test_optional_vectors_random_matrix_values_are_bit_exact(seed, weight, variant):
    fg, ng, n, vec = _weighted_digraph(seed)
    vectors = {
        "personalization": vec,
        "dangling": {node: value + 0.125 for node, value in vec.items()},
        "nstart": {node: float(n - node) for node in range(n)},
    }
    kwargs = vectors if variant == "combined" else {variant: vectors[variant]}
    kwargs = dict(kwargs, max_iter=250, tol=1.0e-10, weight=weight)
    for _ in range(2):
        _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))


def _matrix_outcome(library, graph, kwargs):
    try:
        return ("return", library.pagerank(graph, **kwargs))
    except Exception as exc:
        return ("raise", type(exc).__name__, str(exc))


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("variant", ["personalization", "dangling", "nstart"])
@pytest.mark.parametrize("vector", [{}, {"outside": 1.0}, {"sink": 0.0}, {"sink": -1.0}])
def test_optional_vectors_degenerate_vector_outcomes_remain_unchanged(
    graph_name, variant, vector
):
    fg, ng = _matrix_pair(graph_name)
    # Prime the shared matrix so validation cannot be skipped by warm reuse.
    fnx.pagerank(fg, weight="weight")
    kwargs = dict(_matrix_kwargs(), **{variant: vector})
    assert _matrix_outcome(fnx, fg, kwargs) == _matrix_outcome(nx, ng, kwargs)


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("edge_weight", [0.0, -1.0, float("inf"), "2.5", "heavy"])
def test_optional_vectors_unusual_edge_weights_keep_oracle_outcome(graph_name, edge_weight):
    fg, ng = _matrix_pair(graph_name)
    for graph in (fg, ng):
        graph[("root", 2)]["sink"]["weight"] = edge_weight
    kwargs = _matrix_kwargs()
    assert _matrix_outcome(fnx, fg, kwargs) == _matrix_outcome(nx, ng, kwargs)


@pytest.mark.parametrize("graph_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("node_count", [0, 1, 3])
def test_optional_vectors_empty_and_edgeless_graphs_match_exactly(graph_name, node_count):
    fg = getattr(fnx, graph_name)()
    ng = getattr(nx, graph_name)()
    for graph in (fg, ng):
        graph.add_nodes_from(range(node_count))
    kwargs = dict(personalization={0: 1.0}, nstart={0: 2.0}, dangling={0: 3.0})
    _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))


# br-r37-c1-mub4s: the multigraph vector route must join the existing sparse
# producer, not copy to a directed graph and reassociate sums in Python.
def _multigraph_optional_pair(graph_name, seed=0):
    fg, ng = _matrix_pair(graph_name)
    for graph in (fg, ng):
        graph.add_edge(("root", 2), "sink", key="parallel", weight=0.75)
        graph.add_edge("leaf", "leaf", key="second-loop", weight=2.25)
        graph.add_edge("second", "sink", key=("key", seed), weight=1.125)
        graph.add_node(0)
        graph.add_edge(0.0, "second", key="alias", weight=0.875)
    return fg, ng


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "weight", "other", "missing"])
@pytest.mark.parametrize("variant", ["personalization", "nstart", "dangling", "combined"])
def test_multigraph_optional_vectors_use_sparse_producer_bit_exact(
    graph_name, weight, variant
):
    fg, ng = _multigraph_optional_pair(graph_name)
    kwargs = _matrix_kwargs(variant)
    for _ in range(2):
        actual, names = _profile_matrix_rank(fg, weight=weight, **kwargs)
        _assert_matrix_rank_exact(actual, nx.pagerank(ng, weight=weight, **kwargs))
        assert names.count("_pagerank_scipy_personalized") == 1
        assert names.count("_pagerank_scipy_matrix") == 1
        assert any("adjacency_arrays_multigraph" in name for name in names)
        assert not any("to_directed" in name for name in names)
        # MultiGraph has no rewrite token; caching a mutable weighted matrix
        # would turn subsequent held-dictionary writes into stale results.
        assert "_fnx_pagerank_scipy_matrix_cache" not in vars(fg)
        actual.clear()


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("variant", ["personalization", "nstart", "dangling", "combined"])
def test_multigraph_optional_random_parallel_rows_match_bit_exact(
    graph_name, weight, seed, variant
):
    directed = graph_name == "MultiDiGraph"
    ng = getattr(nx, graph_name)(nx.gnp_random_graph(13, 0.25, seed=seed, directed=directed))
    ng.add_edges_from((u, (u + 3) % 13, {"weight": (u % 5 + 1) / 8}) for u in range(13))
    for u, v, attrs in ng.edges(data=True):
        attrs.setdefault("weight", (u + v + 1) / 16)
    fg = getattr(fnx, graph_name)(ng)
    vectors = {
        "personalization": {u: (u % 5 + 1) / 8 for u in ng},
        "nstart": {u: (u % 7 + 1) / 16 for u in ng},
        "dangling": {u: (u % 3 + 1) / 4 for u in ng},
    }
    kwargs = vectors if variant == "combined" else {variant: vectors[variant]}
    kwargs = dict(kwargs, weight=weight, max_iter=250, tol=1.0e-10)
    _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("weight", [None, "weight"])
@pytest.mark.parametrize("mutation", ["held_weight", "remove_key", "add_parallel", "add_node", "remove_node"])
def test_multigraph_optional_vectors_read_live_mutations(graph_name, weight, mutation):
    fg, ng = _multigraph_optional_pair(graph_name)
    kwargs = dict(_matrix_kwargs(), weight=weight)
    _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))
    if mutation == "held_weight":
        held_f = fg[("root", 2)]["sink"]["parallel"]
        held_n = ng[("root", 2)]["sink"]["parallel"]
        for value in (11.25, 0.125, 4.0):
            held_f["weight"] = held_n["weight"] = value
            _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))
    else:
        for graph in (fg, ng):
            if mutation == "remove_key":
                graph.remove_edge(("root", 2), "sink", "parallel")
            elif mutation == "add_parallel":
                graph.add_edge("second", "sink", key="extra", weight=3.5)
            elif mutation == "add_node":
                graph.add_node(("new", 31))
            else:
                graph.remove_node(7)
        _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("variant", ["personalization", "nstart", "dangling"])
@pytest.mark.parametrize("vector", [{}, {"outside": 1.0}, {"sink": 0.0}, {"sink": -1.0}])
def test_multigraph_optional_degenerate_vectors_match_exact_outcome(graph_name, variant, vector):
    fg, ng = _multigraph_optional_pair(graph_name)
    kwargs = dict(_matrix_kwargs(), **{variant: vector})
    assert _matrix_outcome(fnx, fg, kwargs) == _matrix_outcome(nx, ng, kwargs)


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("edge_weight", [0.0, -1.0, float("inf"), float("nan"), "2.5", "heavy"])
def test_multigraph_optional_invalid_weights_keep_oracle_outcome(graph_name, edge_weight):
    fg, ng = _multigraph_optional_pair(graph_name)
    for graph in (fg, ng):
        graph[("root", 2)]["sink"]["parallel"]["weight"] = edge_weight
    kwargs = _matrix_kwargs()
    assert _matrix_outcome(fnx, fg, kwargs) == _matrix_outcome(nx, ng, kwargs)


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("node_count", [0, 1, 3])
def test_multigraph_optional_edgeless_graphs_match_bit_exact(graph_name, node_count):
    fg = getattr(fnx, graph_name)()
    ng = getattr(nx, graph_name)()
    for graph in (fg, ng):
        graph.add_nodes_from(range(node_count))
    kwargs = dict(personalization={0: 1.0}, nstart={0: 2.0}, dangling={0: 3.0})
    _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("max_iter", [0, -1, 1, 1.5])
def test_multigraph_optional_nonconvergence_matches_exact_error(graph_name, max_iter):
    fg, ng = _multigraph_optional_pair(graph_name)
    kwargs = dict(_matrix_kwargs(), max_iter=max_iter, tol=0.0)
    assert _matrix_outcome(fnx, fg, kwargs) == _matrix_outcome(nx, ng, kwargs)


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_optional_public_namespaces_consume_same_producer(graph_name):
    import cProfile

    from franken_networkx import algorithms
    from franken_networkx.algorithms import link_analysis
    from franken_networkx.algorithms.link_analysis import pagerank_alg

    fg, ng = _multigraph_optional_pair(graph_name)
    kwargs = _matrix_kwargs()
    expected = nx.pagerank(ng, **kwargs)
    for namespace in (fnx, algorithms, link_analysis, pagerank_alg):
        profiler = cProfile.Profile()
        actual = profiler.runcall(namespace.pagerank, fg, **kwargs)
        names = [
            entry.code if isinstance(entry.code, str) else entry.code.co_name
            for entry in profiler.getstats()
        ]
        _assert_matrix_rank_exact(actual, expected)
        assert names.count("_pagerank_scipy_personalized") == 1
        assert any("adjacency_arrays_multigraph_live_finite_checked" in name for name in names)


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("guard", ["subclass", "private", "mapping", "weight_key"])
def test_multigraph_optional_guarded_inputs_retain_existing_route(graph_name, guard):
    from types import MappingProxyType

    fg, ng = _multigraph_optional_pair(graph_name)
    kwargs = _matrix_kwargs()
    if guard == "subclass":
        class GraphSubclass(getattr(fnx, graph_name)):
            pass

        fg = GraphSubclass(fg)
    elif guard == "private":
        # Assign a real matching mapping; this probe checks route exclusion,
        # not an assertion that other private-PageRank bug classes are fixed.
        fg._adj = ng._adj
        if fg.is_directed():
            fg._succ = ng._succ
            fg._pred = ng._pred
    elif guard == "mapping":
        kwargs["personalization"] = MappingProxyType(kwargs["personalization"])
    else:
        kwargs["weight"] = 17
    actual, names = _profile_matrix_rank(fg, **kwargs)
    _close(actual, nx.pagerank(ng, **kwargs))
    assert "_pagerank_scipy_personalized" not in names


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("view_kind", ["subgraph", "converted", "reverse"])
def test_multigraph_optional_views_keep_filtered_oracle_values(graph_name, view_kind):
    fg, ng = _multigraph_optional_pair(graph_name)
    if view_kind == "subgraph":
        selected = [node for node in ng if node != 7]
        fg, ng = fg.subgraph(selected), ng.subgraph(selected)
    elif view_kind == "converted":
        if fg.is_directed():
            fg, ng = fg.to_undirected(as_view=True), ng.to_undirected(as_view=True)
        else:
            fg, ng = fg.to_directed(as_view=True), ng.to_directed(as_view=True)
    else:
        if not fg.is_directed():
            fg, ng = fg.to_directed(as_view=True), ng.to_directed(as_view=True)
        fg, ng = fg.reverse(copy=False), ng.reverse(copy=False)
    kwargs = _matrix_kwargs()
    _close(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))


@pytest.mark.parametrize("graph_name", ["MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("variant", ["personalization", "nstart", "dangling", "combined"])
def test_multigraph_optional_loop_association_matches_float_bits(graph_name, seed, variant):
    import numpy as np
    import scipy.sparse as sp

    rng = random.Random(9021 + seed)
    ng = getattr(nx, graph_name)()
    ng.add_nodes_from(["z", "a", "d", "c"])
    for node in ng:
        for _ in range(3):
            ng.add_edge(node, node, weight=rng.random() / 10)
        for other in ng:
            if other != node:
                ng.add_edge(node, other, weight=rng.random() + 0.1)
                ng.add_edge(node, other, weight=rng.random() + 0.1)
    fg = getattr(fnx, graph_name)(ng)
    _, actual_matrix, _ = fnx._pagerank_scipy_matrix(fg, "weight")
    expected_matrix = nx.to_scipy_sparse_array(ng, dtype=float, weight="weight")
    row_sums = np.asarray(expected_matrix.sum(axis=1)).flatten()
    row_sums[row_sums != 0] = 1.0 / row_sums[row_sums != 0]
    expected_matrix = sp.dia_array((row_sums, 0), shape=expected_matrix.shape).tocsr() @ expected_matrix
    assert np.array_equal(actual_matrix.toarray(), expected_matrix.toarray())
    vectors = {
        "personalization": {"a": 0.1, "c": 0.3},
        "nstart": {"z": 0.2, "d": 0.7},
        "dangling": {"a": 0.3, "c": 0.1},
    }
    kwargs = vectors if variant == "combined" else {variant: vectors[variant]}
    kwargs = dict(kwargs, max_iter=250, tol=1.0e-10)
    _assert_matrix_rank_exact(fnx.pagerank(fg, **kwargs), nx.pagerank(ng, **kwargs))
