"""Conformance harness pinning down REVIEW MODE parity fixes.

The 2026-05-03 review pass landed a series of fnx-vs-nx parity fixes
that the value-equality assertions in existing tests would silently
ignore on regression — return-type, exception-type, and generator-
protocol contracts. This file locks those contracts down so a future
edit that reverts (e.g.) ``transitivity`` to float-on-empty or
``all_shortest_paths`` to a bare iterator trips a hard failure.

Each test is keyed to the bead that fixed the contract; deleting a
test would also need a deliberate bead-close decision.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx


# --- transitivity (br-r37-c1-4jnwn) ---------------------------------

def test_transitivity_returns_int_zero_on_triangle_free():
    """nx returns int(0) on a triangle-free graph; fnx must too."""
    G_nx = nx.path_graph(5)
    G_fnx = fnx.path_graph(5)
    nv, fv = nx.transitivity(G_nx), fnx.transitivity(G_fnx)
    assert nv == fv == 0
    assert fv.__class__ is nv.__class__  # both int, not float


def test_transitivity_returns_float_on_graph_with_triangles():
    G_nx = nx.complete_graph(4)
    G_fnx = fnx.complete_graph(4)
    nv, fv = nx.transitivity(G_nx), fnx.transitivity(G_fnx)
    assert nv == fv == 1.0
    assert fv.__class__ is nv.__class__  # both float


# --- wiener_index (br-r37-c1-t26b4) ---------------------------------

def test_wiener_index_directed_returns_int():
    """Directed branch: nx returns ``total`` un-divided (int)."""
    G_nx = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    G_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    nv, fv = nx.wiener_index(G_nx), fnx.wiener_index(G_fnx)
    assert nv == fv
    assert fv.__class__ is nv.__class__ is int


def test_wiener_index_undirected_returns_float():
    """Undirected branch: nx returns ``total / 2`` (float)."""
    G_nx = nx.path_graph(5)
    G_fnx = fnx.path_graph(5)
    nv, fv = nx.wiener_index(G_nx), fnx.wiener_index(G_fnx)
    assert nv == fv
    assert fv.__class__ is nv.__class__ is float


# --- barycenter (br-r37-c1-pooue) -----------------------------------

def test_barycenter_empty_graph_contract_depends_on_directedness():
    """nx returns [] for empty directed classes, but raises for undirected."""
    for nx_cls, fnx_cls in [
        (nx.DiGraph, fnx.DiGraph),
        (nx.MultiDiGraph, fnx.MultiDiGraph),
    ]:
        assert nx.barycenter(nx_cls()) == fnx.barycenter(fnx_cls()) == []

    for nx_cls, fnx_cls in [
        (nx.Graph, fnx.Graph),
        (nx.MultiGraph, fnx.MultiGraph),
    ]:
        with pytest.raises(nx.NetworkXPointlessConcept):
            nx.barycenter(nx_cls())
        with pytest.raises(nx.NetworkXPointlessConcept):
            fnx.barycenter(fnx_cls())


def test_barycenter_directed_disconnected_raises_no_path():
    """Non-strongly-connected DiGraph: NetworkXNoPath in both libs."""
    G_nx = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    G_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    with pytest.raises(nx.NetworkXNoPath):
        nx.barycenter(G_nx)
    with pytest.raises(nx.NetworkXNoPath):
        fnx.barycenter(G_fnx)


# --- degree_centrality (br-r37-c1-pu5q7) ----------------------------

# --- _link_prediction_lazy_delegate generator-protocol lock (br-r37-c1-sybdh) ---

@pytest.mark.parametrize(
    "fn",
    [
        fnx.jaccard_coefficient,
        fnx.adamic_adar_index,
        fnx.preferential_attachment,
        fnx.resource_allocation_index,
    ],
    ids=["jaccard", "adamic_adar", "preferential", "resource_allocation"],
)
def test_link_prediction_lazy_generator_protocol(fn):
    """The lazy-delegate generator (br-r37-c1-8e60l) must implement
    the Python generator protocol cleanly: isinstance is generator,
    next() yields a 3-tuple, close() exhausts the generator (next
    raises StopIteration). A regression that wraps the inner call in
    something catching GeneratorExit would silently leak the inner
    generator across the link-prediction surface."""
    import types

    G = fnx.barabasi_albert_graph(8, 2, seed=3)
    gen = fn(G)
    assert isinstance(gen, types.GeneratorType), (
        f"{fn.__name__} should return a real generator (GeneratorType)"
    )
    # Consume one element — should be a 3-tuple (u, v, score)
    first = next(gen)
    assert isinstance(first, tuple) and len(first) == 3
    # Close the generator mid-iteration; subsequent next() must raise
    # StopIteration.
    gen.close()
    with pytest.raises(StopIteration):
        next(gen)


# --- _raw_neighbors_dispatch helper lock (br-r37-c1-4ar9q) -----------

def test_raw_neighbors_dispatch_plain_graph_returns_graph_neighbors():
    """Plain ``fnx.Graph`` with no private storage → fast Rust binding."""
    from franken_networkx import _raw_neighbors_dispatch, _GRAPH_NEIGHBORS

    G = fnx.complete_graph(5)
    raw = _raw_neighbors_dispatch(G)
    assert raw is _GRAPH_NEIGHBORS
    assert callable(raw)
    nbrs = raw(G, 0)
    # K5: node 0 has 4 neighbors {1, 2, 3, 4}
    assert sorted(nbrs) == [1, 2, 3, 4]


def test_raw_neighbors_dispatch_plain_digraph_returns_digraph_neighbors():
    """Plain ``fnx.DiGraph`` with no private storage → fast Rust binding."""
    from franken_networkx import _raw_neighbors_dispatch, _DIGRAPH_NEIGHBORS

    G = fnx.DiGraph([(0, 1), (0, 2), (1, 2)])
    raw = _raw_neighbors_dispatch(G)
    assert raw is _DIGRAPH_NEIGHBORS
    # successors of 0 (DiGraph.neighbors == successors)
    assert sorted(raw(G, 0)) == [1, 2]


@pytest.mark.parametrize(
    "graph_factory",
    [
        lambda: fnx.MultiGraph([(0, 1), (0, 1), (1, 2)]),
        lambda: fnx.MultiDiGraph([(0, 1), (0, 1)]),
    ],
    ids=["MultiGraph", "MultiDiGraph"],
)
def test_raw_neighbors_dispatch_rejects_multigraph_via_isinstance(graph_factory):
    """MultiGraph and MultiDiGraph have independent MROs (NOT
    Graph/DiGraph subclasses); the isinstance dispatch returns None
    for both, so the bypass is correctly skipped (br-r37-c1-ni9va)."""
    from franken_networkx import _raw_neighbors_dispatch

    G = graph_factory()
    assert _raw_neighbors_dispatch(G) is None


def test_raw_neighbors_dispatch_rejects_private_storage_override():
    """When nx-compatibility private storage is set on a Graph, the
    helper returns None — falls back to the slow path so the override
    is honored. Critical for nx test-suite compatibility."""
    from franken_networkx import (
        _raw_neighbors_dispatch,
        _PRIVATE_ADJ_OVERRIDE,
    )

    G = fnx.complete_graph(3)
    # Before override: dispatch returns the fast binding.
    assert _raw_neighbors_dispatch(G) is not None
    # Set nx-private adjacency override (simulates nx test code that
    # monkey-patches G._adj). After: dispatch falls back to None.
    setattr(G, _PRIVATE_ADJ_OVERRIDE, {"a": {}, "b": {}})
    assert _raw_neighbors_dispatch(G) is None


# --- _reciprocity_value_for_node fast-path lock (br-r37-c1-o4f52) ----

@pytest.mark.parametrize(
    "edges,node,expected",
    [
        # cycle3 directed: each node has 1 in + 1 out, 0 reciprocal → 0/2 = 0
        ([(0, 1), (1, 2), (2, 0)], 0, 0.0),
        # symmetric cycle3 (each pair reciprocal): each node has 2 in + 2 out,
        # 2 mutual neighbors → 2*2/4 = 1.0
        ([(0, 1), (1, 0), (1, 2), (2, 1), (2, 0), (0, 2)], 0, 1.0),
        # mixed: node 0 has out=[1,2], in=[3]; mutual={} → 0/3 = 0
        ([(0, 1), (0, 2), (3, 0), (1, 4), (2, 4)], 0, 0.0),
        # node with 1 mutual edge: out=[1], in=[1,3] → mutual={1}, 2*1/3
        ([(0, 1), (1, 0), (3, 0)], 0, pytest.approx(2 / 3)),
    ],
    ids=[
        "cycle3_no_reciprocal",
        "K3_directed_full_reciprocal",
        "mixed_no_mutual",
        "one_mutual_two_thirds",
    ],
)
def test_per_node_reciprocity_fast_path_known_results(edges, node, expected):
    """Locks br-r37-c1-o4f52's bypass of predecessors/successors
    wrappers. Hand-derived expected values from the formula
    ``2 * |pred ∩ succ| / (|pred| + |succ|)``. Independent of nx —
    catches regressions that swap pred/succ, miscompute overlap,
    or break the multigraph fallback."""
    G = fnx.DiGraph()
    G.add_edges_from(edges)
    assert fnx.reciprocity(G, node) == expected


# --- selfloop_edges/number_of_selfloops fast-path lock (br-r37-c1-61okz) ---

@pytest.mark.parametrize(
    "graph_factory,expected_count,expected_edges",
    [
        (lambda: fnx.complete_graph(5), 0, []),
        (lambda: fnx.path_graph(5), 0, []),
        (lambda: fnx.Graph([(0, 0), (0, 1), (2, 2)]), 2, [(0, 0), (2, 2)]),
        (lambda: fnx.Graph([(0, 0)]), 1, [(0, 0)]),
        (lambda: fnx.DiGraph([(0, 0), (0, 1), (1, 1)]), 2, [(0, 0), (1, 1)]),
        # Multigraph fallback path (parallel self-loops counted)
        (lambda: fnx.MultiGraph([(0, 0), (0, 0), (0, 1)]), 2, [(0, 0), (0, 0)]),
    ],
    ids=["K5_no_selfloops", "P5_no_selfloops", "two_selfloops",
         "single_selfloop", "directed_two_selfloops", "multigraph_parallel_selfloops"],
)
def test_selfloop_fast_path_known_results(graph_factory, expected_count, expected_edges):
    """Locks br-r37-c1-61okz's has_edge-based fast path AND the
    multigraph fallback. Hand-derived expected values catch:
      - off-by-one in the iteration
      - wrong type returned (must be tuples, not other shapes)
      - multigraph parallel-edge counting drift
    Independent of nx — based on graph structure."""
    G = graph_factory()
    assert fnx.number_of_selfloops(G) == expected_count
    actual_edges = sorted(fnx.selfloop_edges(G))
    assert actual_edges == sorted(expected_edges)


# --- volume fast-path lock (br-r37-c1-ay2no) -------------------------

@pytest.mark.parametrize(
    "graph_factory,subset_factory,expected",
    [
        # K_n: every pair is connected; sum of degrees on a subset of size k
        # is k * (n - 1) since every node has degree n-1.
        (lambda: fnx.complete_graph(5), lambda G: [0, 1, 2], 12),       # 3 * 4
        (lambda: fnx.complete_graph(6), lambda G: list(G.nodes())[:4], 20),  # 4 * 5
        # P_n: linear path; endpoints have degree 1, middle have degree 2.
        (lambda: fnx.path_graph(5), lambda G: [0, 4], 2),               # 1 + 1
        (lambda: fnx.path_graph(5), lambda G: [1, 2, 3], 6),            # 2 + 2 + 2
        # Self-loop case: degree counts self-loop twice.
        (lambda: fnx.Graph([(0, 0), (0, 1), (1, 2)]), lambda G: [0], 3),  # self-loop=2 + edge=1
        # All-nodes volume = 2|E| for undirected.
        (lambda: fnx.barabasi_albert_graph(20, 3, seed=7), lambda G: list(G.nodes()),
         2 * fnx.barabasi_albert_graph(20, 3, seed=7).number_of_edges()),
    ],
    ids=["K5_first3", "K6_first4", "P5_endpoints", "P5_middle", "self_loop_node",
         "BA20_all_nodes_eq_2m"],
)
def test_volume_fast_path_known_results(graph_factory, subset_factory, expected):
    """Locks the br-r37-c1-ay2no fast-path correctness (volume on
    undirected simple graphs == sum(deg(v) for v in S)) against
    hand-derived expected values. Independent of nx — catches a future
    regression that reroutes through the slow _adc_weighted_degree
    path or breaks the self-loop *2 semantic."""
    G = graph_factory()
    S = subset_factory(G)
    assert fnx.volume(G, S) == expected


@pytest.mark.parametrize(
    "nx_graph,fnx_graph,kwargs,expected",
    [
        (nx.path_graph(2), fnx.path_graph(2), {}, 1),
        (
            nx.Graph([(0, 1, {"weight": 2})]),
            fnx.Graph([(0, 1, {"weight": 2})]),
            {"weight": "weight"},
            2,
        ),
        (nx.DiGraph([(0, 1)]), fnx.DiGraph([(0, 1)]), {}, 1),
        (nx.MultiGraph([(0, 1)]), fnx.MultiGraph([(0, 1)]), {}, 1),
    ],
    ids=[
        "simple_fast_path",
        "weighted_slow_path",
        "directed_slow_path",
        "multi_slow_path",
    ],
)
def test_volume_ignores_missing_nodes_like_networkx(nx_graph, fnx_graph, kwargs, expected):
    """NetworkX treats missing nodes in S as degree zero."""
    assert nx.volume(nx_graph, [0, 99], **kwargs) == expected
    assert fnx.volume(fnx_graph, [0, 99], **kwargs) == expected
    assert nx.volume(nx_graph, [99], **kwargs) == 0
    assert fnx.volume(fnx_graph, [99], **kwargs) == 0


# --- distance-metric Rust guard lock (br-r37-c1-0xhhq) ---------------

@pytest.mark.parametrize(
    "fn_name,expected",
    [
        ("diameter", 2),       # directed cycle3 has diameter 2
        ("radius", 2),         # same
        ("center", [0, 1, 2]),
        ("periphery", [0, 1, 2]),
        ("barycenter", [0, 1, 2]),  # cycle3 is vertex-transitive
    ],
)
def test_public_fnx_wrappers_handle_directed_via_native_paths(fn_name, expected):
    """The Python wrappers fnx.{diameter, radius, center, periphery,
    barycenter} must handle directed input correctly via native
    fnx.eccentricity / fnx.shortest_path_length paths (br-r37-c1-{
    89n9d, wojl3, ecqmz}). The underlying _fnx.* Rust bindings now
    reject directed input via require_undirected (br-r37-c1-0xhhq /
    p7p7l) — this lock catches a wrapper regression that accidentally
    reroutes through the rejecting raw path or the silent-wrong-
    answer raw path (depending on .so build state)."""
    G = fnx.DiGraph()
    G.add_edges_from([(0, 1), (1, 2), (2, 0)])  # strongly connected cycle3
    func = getattr(fnx, fn_name)
    result = func(G)
    if isinstance(expected, list):
        assert sorted(result) == expected
    else:
        assert result == expected


# --- transitivity directed-collapse wrapper lock (br-r37-c1-b4zwt) ---

@pytest.mark.parametrize(
    "edges,expected_nx_value",
    [
        ([(0, 1), (1, 2), (2, 0)], 0),  # cycle3 — no directed triangle
        ([(i, (i + 1) % 5) for i in range(5)] + [(0, 2)], 0.5),
        ([(u, v) for u in range(4) for v in range(4) if u != v], 1.0),
    ],
    ids=["cycle3_no_directed_triangle", "cycle5_chord", "directed_K4"],
)
def test_transitivity_directed_wrapper_matches_nx(edges, expected_nx_value):
    """fnx.transitivity (the Python wrapper at line 26142) routes
    directed inputs through the Python triangle-iter path because the
    underlying _fnx.transitivity has a gr.undirected() directed-
    collapse defect (returns 1.0 on cycle3 vs nx's 0). Locks the
    wrapper-level contract so a future refactor that re-routes
    through _fnx directly trips immediately."""
    G_nx = nx.DiGraph(edges)
    G_fnx = fnx.DiGraph(edges)
    nv = nx.transitivity(G_nx)
    fv = fnx.transitivity(G_fnx)
    assert nv == fv == expected_nx_value


# --- is_planar Kuratowski-pair lock (br-r37-c1-s2jfv) ----------------

@pytest.mark.parametrize(
    "name,builder",
    [
        ("K33", nx.complete_bipartite_graph),
        ("petersen", lambda: nx.petersen_graph()),
        ("K5", lambda: nx.complete_graph(5)),
    ],
    ids=["K33", "petersen", "K5"],
)
def test_is_planar_rejects_kuratowski_pair_at_public_api(name, builder):
    """fnx.is_planar (the Python wrapper, which delegates to
    nx.check_planarity) MUST return False for K3,3, Petersen, and K5
    regardless of the underlying Rust binary state. Locks the
    public-API contract independently of br-r37-c1-xdjpt's Rust-level
    fix, so a future regression that re-routes through the (binary-
    lagging) ``_fnx.is_planar`` directly trips this test immediately.
    """
    if name == "K33":
        G_nx = nx.complete_bipartite_graph(3, 3)
        G_fnx = fnx.complete_bipartite_graph(3, 3)
    elif name == "petersen":
        G_nx = nx.petersen_graph()
        G_fnx = fnx.petersen_graph()
    else:
        G_nx = nx.complete_graph(5)
        G_fnx = fnx.complete_graph(5)
    assert nx.is_planar(G_nx) is False
    assert fnx.is_planar(G_fnx) is False


# --- predicate-family parity (chordal / planar / eulerian / bipartite / tree) ---

@pytest.mark.parametrize(
    "predicate",
    [
        "is_chordal",
        "is_eulerian",
        "is_semieulerian",
        "is_planar",
        "is_bipartite",
        "is_tree",
        "is_forest",
        "is_connected",
    ],
)
@pytest.mark.parametrize(
    "builder",
    [
        lambda m: m.complete_graph(3),
        lambda m: m.complete_graph(4),
        lambda m: m.complete_graph(5),
        lambda m: m.complete_bipartite_graph(3, 3),
        lambda m: m.path_graph(5),
        lambda m: m.cycle_graph(6),
        lambda m: m.petersen_graph(),
    ],
    ids=["K3", "K4", "K5", "K33", "P5", "C6", "petersen"],
)
def test_graph_predicate_parity_with_nx(predicate, builder):
    """Lock bit-exact parity for boolean graph predicates across a
    fixture spread that includes K_n, complete bipartite, paths,
    cycles, and Petersen (planar test edge case). Surfaced from a
    /reality-check probe — parity holds today; this test pins it."""
    G_nx = builder(nx)
    G_fnx = builder(fnx)
    assert getattr(nx, predicate)(G_nx) == getattr(fnx, predicate)(G_fnx)


# --- harmonic_centrality (br-r37-c1-rsom6) -------------------------

def test_harmonic_centrality_dict_order_matches_nx():
    """nx initializes via ``{u: 0 for u in set(G.nbunch_iter())}`` so
    output dict iteration order is set(G.nodes) order. fnx's Rust path
    emitted insertion order, breaking drop-in code that did
    ``next(iter(harmonic_centrality(G)))``."""
    def build(m):
        G = m.Graph()
        for n in [3, 1, 4, 1, 5, 9, 2, 6]:
            G.add_node(n)
        G.add_edges_from([(3, 1), (1, 4), (4, 5), (5, 9), (9, 2), (2, 6)])
        return G
    nv = nx.harmonic_centrality(build(nx))
    fv = fnx.harmonic_centrality(build(fnx))
    assert list(nv.keys()) == list(fv.keys())
    # Values match within 1 ULP (different summation order is inherent
    # to the Rust vs Python implementations).
    for k in nv:
        assert nv[k] == pytest.approx(fv[k], abs=1e-12)


# --- clustering (br-r37-c1-9ccqe) -----------------------------------

@pytest.mark.parametrize(
    "builder",
    [
        lambda m: m.Graph([(0, 1)]),
        lambda m: m.path_graph(5),
        lambda m: m.Graph([(0, 1), (0, 2), (1, 2), (2, 3), (3, 4)]),
    ],
    ids=["K2", "P5", "mixed"],
)
def test_clustering_emits_int_zero_for_triangle_free_nodes(builder):
    """nx returns int 0 (not 0.0) for triangle-free nodes. Same
    type-drift family as transitivity and degree_centrality."""
    G_nx = builder(nx)
    G_fnx = builder(fnx)
    nv = nx.clustering(G_nx)
    fv = fnx.clustering(G_fnx)
    assert nv == fv
    for k in nv:
        assert type(fv[k]) is type(nv[k]), (
            f"node {k}: nx={type(nv[k]).__name__} fnx={type(fv[k]).__name__}"
        )


@pytest.mark.parametrize(
    "edges",
    [
        [("c", "d"), ("a", "b"), ("b", "c"), ("d", "e"), ("a", "c")],
        [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)],
    ],
    ids=["insertion_ordered", "two_triangles"],
)
def test_average_clustering_exact_float_matches_nx_summation(edges):
    """average_clustering must use nx's public summation order exactly."""
    G_nx = nx.Graph()
    G_fnx = fnx.Graph()
    G_nx.add_edges_from(edges)
    G_fnx.add_edges_from(edges)

    assert fnx.clustering(G_fnx) == nx.clustering(G_nx)
    assert fnx.average_clustering(G_fnx) == nx.average_clustering(G_nx)


@pytest.mark.parametrize(
    "nx_cls,fnx_cls",
    [
        (nx.Graph, fnx.Graph),
        (nx.DiGraph, fnx.DiGraph),
        (nx.MultiGraph, fnx.MultiGraph),
        (nx.MultiDiGraph, fnx.MultiDiGraph),
    ],
    ids=["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"],
)
def test_degree_centrality_singleton_returns_int_one(nx_cls, fnx_cls):
    """nx special-cases ``len(G) <= 1`` and returns {n: 1} (int).
    Previously fnx returned NaN for multigraph singletons and 1.0
    (float) for simple-graph singletons — both diverged from nx."""
    G_nx = nx_cls(); G_nx.add_node(0)
    G_fnx = fnx_cls(); G_fnx.add_node(0)
    nv = nx.degree_centrality(G_nx)
    fv = fnx.degree_centrality(G_fnx)
    assert nv == fv == {0: 1}
    assert type(fv[0]) is int


def test_barycenter_directed_strongly_connected_returns_list():
    G_nx = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    G_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert sorted(nx.barycenter(G_nx)) == sorted(fnx.barycenter(G_fnx))


def test_barycenter_accepts_backend_keyword_contract():
    G_nx = nx.path_graph(3)
    G_fnx = fnx.path_graph(3)
    assert nx.barycenter(G_nx, backend=None) == fnx.barycenter(G_fnx, backend=None)
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        nx.barycenter(G_nx, backend_kwargs={"x": 1})
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        fnx.barycenter(G_fnx, backend_kwargs={"x": 1})


# --- katz_centrality (br-r37-c1-ua4i8) ------------------------------

def test_katz_centrality_non_convergent_raises_power_iteration_failed():
    """Tight max_iter must raise PowerIterationFailedConvergence (not silent)."""
    G_fnx = fnx.complete_graph(50)
    with pytest.raises(nx.PowerIterationFailedConvergence):
        fnx.katz_centrality(G_fnx, alpha=0.5, max_iter=1, tol=1e-12)


def test_katz_centrality_default_nonconvergence_message_matches_networkx():
    G_nx = nx.complete_graph(20)
    G_fnx = fnx.complete_graph(20)
    with pytest.raises(nx.PowerIterationFailedConvergence) as nx_error:
        nx.katz_centrality(G_nx)
    with pytest.raises(nx.PowerIterationFailedConvergence) as fnx_error:
        fnx.katz_centrality(G_fnx)

    assert str(fnx_error.value) == str(nx_error.value)
    assert fnx_error.value.args[1] == nx_error.value.args[1]


# --- all_shortest_paths (br-r37-c1-6atv8) ---------------------------

def test_all_shortest_paths_returns_real_generator():
    """Must be a generator object (supports .send/.throw/.close)."""
    g_nx = nx.all_shortest_paths(nx.complete_graph(4), 0, 3)
    g_fnx = fnx.all_shortest_paths(fnx.complete_graph(4), 0, 3)
    assert inspect.isgenerator(g_nx)
    assert inspect.isgenerator(g_fnx)
    # Generator protocol: .close() returns None and exhausts the gen.
    g_fnx.close()
    with pytest.raises(StopIteration):
        next(g_fnx)


def test_all_shortest_paths_validates_source_and_method_eagerly():
    """nx raises bad method and missing-source errors at call time."""
    G = fnx.complete_graph(4)
    with pytest.raises(nx.NodeNotFound):
        fnx.all_shortest_paths(G, 99, 0)
    with pytest.raises(ValueError):
        fnx.all_shortest_paths(G, 0, 3, weight="weight", method="floyd-warshall")


@pytest.mark.parametrize(
    "source,target,exc",
    [
        (0, 99, nx.NetworkXNoPath),
        (0, [], TypeError),
    ],
    ids=["missing-target", "unhashable-target"],
)
def test_all_shortest_paths_defers_target_errors_until_iteration(source, target, exc):
    """Target-dependent errors live inside nx's generator body."""
    G_nx = nx.path_graph(3)
    G_fnx = fnx.path_graph(3)
    g_nx = nx.all_shortest_paths(G_nx, source, target)
    g_fnx = fnx.all_shortest_paths(G_fnx, source, target)
    assert inspect.isgenerator(g_nx)
    assert inspect.isgenerator(g_fnx)
    with pytest.raises(exc):
        next(g_nx)
    with pytest.raises(exc):
        next(g_fnx)


def test_all_shortest_paths_accepts_backend_keyword_contract():
    G_nx = nx.path_graph(3)
    G_fnx = fnx.path_graph(3)
    assert list(nx.all_shortest_paths(G_nx, 0, 2, backend=None)) == list(
        fnx.all_shortest_paths(G_fnx, 0, 2, backend=None)
    )
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        list(nx.all_shortest_paths(G_nx, 0, 2, backend_kwargs={"x": 1}))
    with pytest.raises(TypeError, match="unexpected keyword argument 'backend_kwargs'"):
        list(fnx.all_shortest_paths(G_fnx, 0, 2, backend_kwargs={"x": 1}))


def test_all_shortest_paths_unweighted_method_ignores_weight_argument():
    """method='unweighted' is accepted with weight=... and ignores weights."""
    G_nx = nx.Graph()
    G_fnx = fnx.Graph()
    for G in (G_nx, G_fnx):
        G.add_edge(0, 1, weight=1)
        G.add_edge(1, 2, weight=1)
        G.add_edge(0, 2, weight=100)

    expected = list(nx.all_shortest_paths(G_nx, 0, 2, weight="weight", method="unweighted"))
    actual = list(fnx.all_shortest_paths(G_fnx, 0, 2, weight="weight", method="unweighted"))
    assert actual == expected == [[0, 2]]


# --- graph_clique_number (br-r37-c1-h964b) --------------------------

def test_graph_clique_number_absent_like_networkx_36():
    """Removed upstream in NetworkX 3.6; fnx should not expose it."""
    assert not hasattr(nx, "graph_clique_number")
    assert not hasattr(fnx, "graph_clique_number")
    assert "graph_clique_number" not in fnx.__all__


def test_private_fnx_stub_tracks_graph_clique_number_runtime_export():
    """The private native module still exports graph_clique_number."""
    from franken_networkx import _fnx

    stub = Path(fnx.__file__).with_name("_fnx.pyi").read_text()
    assert hasattr(_fnx, "graph_clique_number")
    assert "def graph_clique_number(g: Graph) -> int: ..." in stub


# --- connected_components (br-r37-c1-anace) -------------------------

def test_connected_components_yields_sets_not_lists():
    """nx contract: ``yield`` a set per component. Code that does
    ``for comp in connected_components(G): comp.add(x)`` would break
    if fnx returned lists."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (2, 3)])
    comps = list(fnx.connected_components(G))
    for comp in comps:
        assert isinstance(comp, set), f"got {type(comp).__name__}, want set"


# --- cycle_basis ----------------------------------------------------

def test_cycle_basis_matches_nx_canonical_form():
    """Different root-pick strategies are fine but cycle multiset must match."""
    for builder in [
        lambda m: m.cycle_graph(5),
        lambda m: m.Graph([(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)]),
        lambda m: m.grid_2d_graph(3, 3),
    ]:
        nv = nx.cycle_basis(builder(nx))
        fv = fnx.cycle_basis(builder(fnx))
        assert sorted(tuple(sorted(c)) for c in nv) == sorted(
            tuple(sorted(c)) for c in fv
        )


# --- load_centrality (br-r37-c1-3wzcj) ------------------------------

@pytest.mark.parametrize(
    "builder",
    [
        lambda m: m.complete_graph(5),
        lambda m: m.cycle_graph(5),
        lambda m: m.complete_bipartite_graph(3, 3),
        lambda m: m.wheel_graph(6),
        lambda m: m.barabasi_albert_graph(50, 3, seed=42),
    ],
    ids=["K5", "C5", "K3,3", "W6", "BA50"],
)
def test_load_centrality_matches_newman_not_brandes(builder):
    """The previous Rust impl computed Brandes' BETWEENNESS instead of
    Newman's LOAD. The two diverge on graphs with multiple shortest
    paths through a node (K3,3 is a clean diagnostic). Lock parity."""
    G_nx = builder(nx)
    G_fnx = builder(fnx)
    nv = nx.load_centrality(G_nx)
    fv = fnx.load_centrality(G_fnx)
    assert set(nv) == set(fv)
    for k in nv:
        assert nv[k] == pytest.approx(fv[k], abs=1e-9)


def test_load_centrality_surfaces_unexpected_native_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("native boom")

    monkeypatch.setattr(fnx, "_raw_load_centrality", boom)
    with pytest.raises(RuntimeError, match="native boom"):
        fnx.load_centrality(fnx.path_graph(3))


def test_community_all_excludes_private_implementation_names():
    private_exports = [name for name in fnx.community.__all__ if name.startswith("_")]
    assert private_exports == []
    assert "label_propagation_communities" in fnx.community.__all__


# --- exception-type contracts (cross-cutting; 20-case audit) --------

@pytest.mark.parametrize(
    "name,builder,call,exc",
    [
        (
            "shortest_path_disconnected",
            lambda m: m.Graph([(0, 1), (2, 3)]),
            lambda m, G: m.shortest_path(G, 0, 3),
            nx.NetworkXNoPath,
        ),
        (
            "shortest_path_missing_src",
            lambda m: m.Graph([(0, 1)]),
            lambda m, G: m.shortest_path(G, 99, 0),
            nx.NodeNotFound,
        ),
        (
            "find_cycle_on_tree",
            lambda m: m.Graph([(0, 1), (1, 2)]),
            lambda m, G: list(m.find_cycle(G)),
            nx.NetworkXNoCycle,
        ),
        (
            "topological_sort_cyclic",
            lambda m: m.DiGraph([(0, 1), (1, 0)]),
            lambda m, G: list(m.topological_sort(G)),
            nx.NetworkXUnfeasible,
        ),
        (
            "eigenvector_centrality_empty",
            lambda m: m.Graph(),
            lambda m, G: m.eigenvector_centrality(G),
            nx.NetworkXPointlessConcept,
        ),
        (
            "diameter_disconnected",
            lambda m: m.Graph([(0, 1), (2, 3)]),
            lambda m, G: m.diameter(G),
            nx.NetworkXError,
        ),
        (
            "is_strongly_connected_on_undirected",
            lambda m: m.Graph([(0, 1)]),
            lambda m, G: m.is_strongly_connected(G),
            nx.NetworkXNotImplemented,
        ),
        # br-r37-c1-qmzy2: connected_double_edge_swap silently returned
        # 0 on disconnected/<4-node/empty inputs; nx raises. Lock all
        # three precondition cases against future regression.
        (
            "connected_double_edge_swap_disconnected",
            lambda m: m.Graph([(0, 1), (2, 3), (4, 5), (6, 7)]),
            lambda m, G: m.connected_double_edge_swap(G, nswap=1, seed=42),
            nx.NetworkXError,
        ),
        (
            "connected_double_edge_swap_too_small",
            lambda m: m.complete_graph(3),
            lambda m, G: m.connected_double_edge_swap(G, nswap=1, seed=42),
            nx.NetworkXError,
        ),
        (
            "connected_double_edge_swap_empty",
            lambda m: m.Graph(),
            lambda m, G: m.connected_double_edge_swap(G, nswap=1, seed=42),
            nx.NetworkXPointlessConcept,
        ),
        # br-r37-c1-des-validate: double_edge_swap silently returned G
        # unchanged on five precondition violations that nx raises on.
        # Lock all five: directed input, nswap>max_tries, <4 nodes,
        # <2 edges, max_tries exhausted.
        (
            "double_edge_swap_directed",
            lambda m: m.DiGraph([(0, 1), (1, 2), (2, 3)]),
            lambda m, G: m.double_edge_swap(G),
            nx.NetworkXError,
        ),
        (
            "double_edge_swap_nswap_gt_max_tries",
            lambda m: m.complete_graph(5),
            lambda m, G: m.double_edge_swap(G, nswap=200, max_tries=10, seed=42),
            nx.NetworkXError,
        ),
        (
            "double_edge_swap_too_small",
            lambda m: m.complete_graph(3),
            lambda m, G: m.double_edge_swap(G, seed=42),
            nx.NetworkXError,
        ),
        (
            "double_edge_swap_too_few_edges",
            lambda m: (lambda H: (H.add_edges_from([(0, 1)]),
                                  H.add_nodes_from([2, 3]), H)[-1])(m.Graph()),
            lambda m, G: m.double_edge_swap(G, seed=42),
            nx.NetworkXError,
        ),
        (
            "double_edge_swap_max_tries_exhausted",
            lambda m: m.complete_graph(4),
            lambda m, G: m.double_edge_swap(G, nswap=1, max_tries=5, seed=42),
            nx.NetworkXAlgorithmError,
        ),
        # br-r37-c1-tssa-empty: spectrum / matrix builders silently
        # returned 0×0 / [] on empty graphs; nx raises. The check is
        # at the to_scipy_sparse_array boundary so all six callers
        # (adjacency_matrix, laplacian_matrix, normalized_laplacian_matrix,
        # adjacency_spectrum, laplacian_spectrum, normalized_laplacian_spectrum)
        # inherit the parity. Lock all six.
        (
            "to_scipy_sparse_array_empty",
            lambda m: m.Graph(),
            lambda m, G: m.to_scipy_sparse_array(G),
            nx.NetworkXError,
        ),
        (
            "adjacency_matrix_empty",
            lambda m: m.Graph(),
            lambda m, G: m.adjacency_matrix(G),
            nx.NetworkXError,
        ),
        (
            "laplacian_matrix_empty",
            lambda m: m.Graph(),
            lambda m, G: m.laplacian_matrix(G),
            nx.NetworkXError,
        ),
        (
            "normalized_laplacian_matrix_empty",
            lambda m: m.Graph(),
            lambda m, G: m.normalized_laplacian_matrix(G),
            nx.NetworkXError,
        ),
        (
            "adjacency_spectrum_empty",
            lambda m: m.Graph(),
            lambda m, G: m.adjacency_spectrum(G),
            nx.NetworkXError,
        ),
        (
            "laplacian_spectrum_empty",
            lambda m: m.Graph(),
            lambda m, G: m.laplacian_spectrum(G),
            nx.NetworkXError,
        ),
        (
            "normalized_laplacian_spectrum_empty",
            lambda m: m.Graph(),
            lambda m, G: m.normalized_laplacian_spectrum(G),
            nx.NetworkXError,
        ),
        # br-r37-c1-tssa-nlist0: empty user-supplied nodelist on a
        # non-empty graph silently returned a 0×0 sparse matrix; nx
        # raises NetworkXError("nodelist has no nodes"). Lock the
        # raise at the to_scipy_sparse_array boundary AND through
        # the three matrix-builder cascade layers.
        (
            "to_scipy_sparse_array_empty_nodelist",
            lambda m: m.path_graph(3),
            lambda m, G: m.to_scipy_sparse_array(G, nodelist=[]),
            nx.NetworkXError,
        ),
        (
            "adjacency_matrix_empty_nodelist",
            lambda m: m.path_graph(3),
            lambda m, G: m.adjacency_matrix(G, nodelist=[]),
            nx.NetworkXError,
        ),
        (
            "laplacian_matrix_empty_nodelist",
            lambda m: m.path_graph(3),
            lambda m, G: m.laplacian_matrix(G, nodelist=[]),
            nx.NetworkXError,
        ),
        (
            "normalized_laplacian_matrix_empty_nodelist",
            lambda m: m.path_graph(3),
            lambda m, G: m.normalized_laplacian_matrix(G, nodelist=[]),
            nx.NetworkXError,
        ),
        # br-r37-c1-dmm-empty: directed_modularity_matrix routed through
        # to_numpy_array (no empty-G raise) instead of to_scipy_sparse_array
        # like nx; with `if m == 0: return A` short-circuit, callers got
        # an empty 0×0 numpy array on empty DiGraph instead of an
        # exception. The undirected sibling already has the equivalent
        # check at the same boundary.
        (
            "directed_modularity_matrix_empty",
            lambda m: m.DiGraph(),
            lambda m, G: m.directed_modularity_matrix(G),
            nx.NetworkXError,
        ),
        # br-r37-c1-union-disjoint: union(G, H) silently merged
        # overlapping nodes; nx raises with a hint about rename /
        # disjoint_union.
        (
            "union_overlapping_nodes",
            lambda m: m.path_graph(3),
            lambda m, G: m.union(G, m.path_graph(3)),
            nx.NetworkXError,
        ),
        # br-r37-c1-aef-tupshape: add_edges_from raised ValueError
        # on bad-arity tuples; nx raises NetworkXError. Code that
        # catches `nx.NetworkXError` to detect malformed edge inputs
        # missed fnx's ValueError. Lock NetworkXError on (Graph,
        # DiGraph) for 1-tuple and 5-tuple inputs.
        (
            "add_edges_from_1tuple_graph",
            lambda m: m.Graph(),
            lambda m, G: G.add_edges_from([(1,)]),
            nx.NetworkXError,
        ),
        (
            "add_edges_from_empty_tuple_digraph",
            lambda m: m.DiGraph(),
            lambda m, G: G.add_edges_from([()]),
            nx.NetworkXError,
        ),
        (
            "add_edges_from_5tuple_graph",
            lambda m: m.Graph(),
            lambda m, G: G.add_edges_from([(1, 2, 3, 4, 5)]),
            nx.NetworkXError,
        ),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_exception_type_parity(name, builder, call, exc):
    """Drop-in code that catches specific nx.NetworkX* subclasses
    must catch the same class on fnx. ValueError-vs-NetworkXError
    is a real divergence."""
    G_nx = builder(nx)
    G_fnx = builder(fnx)
    with pytest.raises(exc):
        call(nx, G_nx)
    with pytest.raises(exc):
        call(fnx, G_fnx)


def test_betweenness_centrality_subset_bad_source_match_nx():
    """br-r37-c1-bcs-bad-src: betweenness_centrality_subset and
    edge_betweenness_centrality_subset silently treated unknown
    sources as no-op contributions and returned all-zero dicts.
    nx's SSSP raises KeyError when called with a source not in G
    (it tries to index ``predecessors[s]`` before the source is
    initialized).  Lock parity for both unweighted and weighted
    paths.

    Targets are intentionally NOT validated — nx does not raise
    on bad targets (their absence just yields zeros for those
    paths).  Mirror that asymmetry."""
    P5_f = fnx.path_graph(5)
    P5_n = nx.path_graph(5)

    # Bad source: KeyError
    for sources in ([99], [99, 100], [0, 99]):
        with pytest.raises(KeyError):
            fnx.betweenness_centrality_subset(P5_f, sources, [2])
        with pytest.raises(KeyError):
            fnx.edge_betweenness_centrality_subset(P5_f, sources, [2])
        # Weighted path also raises
        with pytest.raises(KeyError):
            fnx.betweenness_centrality_subset(
                P5_f, sources, [2], weight="weight"
            )
    # Bad target: zeros (parity, no raise)
    rf = fnx.betweenness_centrality_subset(P5_f, [0], [99])
    rn = nx.betweenness_centrality_subset(P5_n, [0], [99])
    assert rf == rn
    # Good case: parity
    rf = fnx.betweenness_centrality_subset(P5_f, [0], [4])
    rn = nx.betweenness_centrality_subset(P5_n, [0], [4])
    assert rf == rn


def test_min_cost_flow_negative_capacity_match_nx():
    """br-r37-c1-mcf-negcap: min_cost_flow / min_cost_flow_cost /
    max_flow_min_cost silently treated negative-capacity edges as
    0, masking nx's NetworkXUnfeasible(``edge (u, v)!r has
    negative capacity``) contract.  network_simplex (sibling)
    already validated correctly via _validate_network_simplex_
    inputs; the SSP path was the gap, propagating through the two
    derivative APIs.  Lock parity for all three entry points."""

    def make_neg(lib):
        D = lib.DiGraph()
        D.add_node(0, demand=-5)
        D.add_node(3, demand=5)
        D.add_edge(0, 1, weight=1, capacity=10)
        D.add_edge(1, 2, weight=1, capacity=-3)
        D.add_edge(2, 3, weight=1, capacity=10)
        return D

    match = r"edge \(1, 2\) has negative capacity"
    with pytest.raises(nx.NetworkXUnfeasible, match=match):
        fnx.min_cost_flow(make_neg(fnx))
    with pytest.raises(nx.NetworkXUnfeasible, match=match):
        fnx.min_cost_flow_cost(make_neg(fnx))
    with pytest.raises(nx.NetworkXUnfeasible, match=match):
        fnx.max_flow_min_cost(make_neg(fnx), 0, 3)
    with pytest.raises(nx.NetworkXUnfeasible, match=match):
        fnx.network_simplex(make_neg(fnx))

    # Positive-capacity regression: parity with nx
    def make_good(lib):
        D = lib.DiGraph()
        D.add_node(0, demand=-5)
        D.add_node(3, demand=5)
        D.add_edge(0, 1, weight=1, capacity=10)
        D.add_edge(1, 2, weight=2, capacity=10)
        D.add_edge(2, 3, weight=1, capacity=10)
        return D

    assert fnx.min_cost_flow_cost(make_good(fnx)) == nx.min_cost_flow_cost(
        make_good(nx)
    )


def test_graph6_sparse6_low_byte_input_match_nx():
    """br-r37-c1-g6-low-byte: nx only rejects high bytes (> 126)
    in graph6/sparse6 input — low bytes (< 63) flow through as
    negative values which downstream produce either a 0-node
    graph (sparse6) or the canonical ``Expected N bits but got 0
    in graph6`` error. fnx previously rejected low bytes upfront
    with a leaky ValueError, diverging from nx for inputs like
    ``b'\\x00'`` and ``b':\\x00'``.  Lock parity for the four
    documented cases."""
    # graph6 low-byte: nx raises NetworkXError "Expected N bits"
    Gf = None
    try:
        Gf = fnx.from_graph6_bytes(b"\x00")
    except nx.NetworkXError as e:
        assert "Expected" in str(e) and "bits but got" in str(e)
    else:
        pytest.fail(f"expected NetworkXError, got {Gf!r}")
    try:
        Gf = fnx.from_graph6_bytes(b"\x00\x00")
    except nx.NetworkXError as e:
        assert "Expected" in str(e) and "bits but got" in str(e)
    else:
        pytest.fail(f"expected NetworkXError, got {Gf!r}")
    # sparse6 low-byte: nx silently returns 0-node graph
    for data in (b":\x00", b":\x00\x00"):
        Gf = fnx.from_sparse6_bytes(data)
        Gn = nx.from_sparse6_bytes(data)
        assert Gf.number_of_nodes() == Gn.number_of_nodes() == 0
    # High-byte still rejected (regression check)
    with pytest.raises(ValueError, match="must be in range"):
        fnx.from_graph6_bytes(b"\xFF")
    # Valid input regression
    Gf = fnx.from_graph6_bytes(b"A_")
    Gn = nx.from_graph6_bytes(b"A_")
    assert Gf.number_of_nodes() == Gn.number_of_nodes() == 2
    assert Gf.number_of_edges() == Gn.number_of_edges() == 1


def test_grid_graph_negative_dim_match_nx():
    """br-r37-c1-grid-neg: same defect family as br-r37-c1-{rgg-neg,
    pjf7g, srgg-neg, trgg-neg, 60f9n, waxman-neg, gtg-neg, hszkp,
    48hex, xm9lx, vdaws}.  ``grid_graph`` silently returned an
    empty graph for any negative integral dim element (range(-3)
    yielded nothing → axis empty → early return).  nx routes
    through cartesian_product of path_graph(d), so the first
    negative d raises NetworkXError(``Negative number of nodes
    not valid: {d}``).  Lock parity on first-negative semantics."""
    bad = [
        ([-3, 3], -3), ([3, -3], -3), ([-3, -3], -3),
        ([0, -3], -3), ([-3], -3), ([-1], -1),
    ]
    for dim, neg in bad:
        match = f"Negative number of nodes not valid: {neg}"
        with pytest.raises(nx.NetworkXError, match=match):
            fnx.grid_graph(dim)
    # Positive / zero / empty dims still work
    for dim in ([3], [3, 3], [0, 0], []):
        Gf = fnx.grid_graph(dim)
        Gn = nx.grid_graph(dim)
        assert Gf.number_of_nodes() == Gn.number_of_nodes()
        assert Gf.number_of_edges() == Gn.number_of_edges()


def test_from_prufer_sequence_panic_on_oob_value_match_nx():
    """br-r37-c1-prufer-oob: from_prufer_sequence panicked the Rust
    backend with ``index out of bounds`` when any value in the
    sequence was >= n (where n = len(sequence) + 2), and raised
    OverflowError on negative values.  nx validates and raises
    NetworkXError(``Invalid Prufer sequence: Values must be between
    0 and {n-1}, got {bad}``).  Lock parity + no-panic guarantee.

    [CRITICAL]: a PyO3 PanicException leaking from a public API on
    valid Python input (a list of ints) is far worse than a typed
    error — it's UB-flavored, not handle-able with normal
    try/except contracts."""
    n_seq = 4  # any sequence of length 2 → n=4, valid range [0, 3]
    bad_cases = [([0, 1, -1], 4, -1),    # negative value
                 ([5, 5], 3, 5),          # value > n-1
                 ([4, 4], 3, 4),          # value == n
                 ([0, 99], 3, 99)]        # large value
    for seq, hi, bad in bad_cases:
        match = f"between 0 and {hi}, got {bad}"
        with pytest.raises(nx.NetworkXError, match=match):
            fnx.from_prufer_sequence(seq)
    # Valid sequences still work and produce nx-equivalent trees
    for seq in ([], [0], [3, 3], [0, 0], [0, 1], [1, 2, 3], [0, 1, 2, 3, 4, 5]):
        Gf = fnx.from_prufer_sequence(seq)
        Gn = nx.from_prufer_sequence(seq)
        assert Gf.number_of_nodes() == Gn.number_of_nodes()
        assert Gf.number_of_edges() == Gn.number_of_edges()
        assert sorted(map(tuple, map(sorted, Gf.edges()))) == sorted(
            map(tuple, map(sorted, Gn.edges()))
        )


def test_from_prufer_sequence_rust_no_panic_on_oob_value():
    """br-r37-c1-zs68s defense-in-depth: even if a future caller
    bypasses the Python wrapper validation and invokes the Rust
    binding directly, ``_fnx.from_prufer_sequence_rust`` must NOT
    panic.  The previous Rust impl indexed ``degree[i]`` where
    ``i >= n`` triggers a Rust panic that leaks through PyO3 as
    PanicException.  The hardened Rust now returns a typed
    NetworkXError on the same input."""
    import franken_networkx as _fnx_mod
    rust_fn = _fnx_mod._fnx.from_prufer_sequence_rust
    # Out-of-range values previously panicked; should now raise
    # NetworkXError with nx-matching message.
    for seq, n_minus_1, bad in [([5, 5], 3, 5), ([99], 2, 99),
                                  ([0, 0, 10], 4, 10)]:
        with pytest.raises(nx.NetworkXError,
                           match=f"between 0 and {n_minus_1}, got {bad}"):
            rust_fn(seq)
    # Valid sequences still produce edge lists.
    edges = rust_fn([0, 1])
    assert len(edges) == 3  # n - 1 = 3 edges for n=4 nodes


def test_to_prufer_sequence_sparse_labels_no_rust_panic_match_nx():
    """br-r37-c1-wsz3q: the public wrapper rejected sparse labels,
    but direct calls to the Rust binding could still panic or return
    a silently wrong empty sequence.  Lock typed KeyError behavior on
    both surfaces."""
    bad_edges = [[(0, 2)], [(1, 2)], [(0, 1), (1, 3)]]
    rust_fn = fnx._fnx.to_prufer_sequence_rust
    for edges in bad_edges:
        Gf = fnx.Graph()
        Gf.add_edges_from(edges)
        Gn = nx.Graph()
        Gn.add_edges_from(edges)
        match = r"tree must have node labels \{0, \.\.\., n - 1\}"
        with pytest.raises(KeyError, match=match):
            fnx.to_prufer_sequence(Gf)
        with pytest.raises(KeyError, match=match):
            nx.to_prufer_sequence(Gn)
        with pytest.raises(KeyError, match=match):
            rust_fn(Gf)

    G = fnx.path_graph(4)
    assert rust_fn(G) == fnx.to_prufer_sequence(G) == nx.to_prufer_sequence(nx.path_graph(4))


def test_to_prufer_sequence_rust_non_tree_no_panic_match_nx():
    """br-r37-c1-bs952: direct Rust-binding callers bypassed the
    public wrapper's tree check, so cyclic integer-labelled graphs
    leaked a PyO3 PanicException from the Rust leaf invariant.  Lock
    typed errors on both public and direct surfaces."""
    rust_fn = fnx._fnx.to_prufer_sequence_rust
    for factory in (fnx.Graph, nx.Graph):
        G = factory()
        with pytest.raises(nx.NetworkXPointlessConcept,
                           match="fewer than two nodes"):
            (fnx.to_prufer_sequence if factory is fnx.Graph else nx.to_prufer_sequence)(G)
    empty = fnx.Graph()
    with pytest.raises(nx.NetworkXPointlessConcept,
                       match="fewer than two nodes"):
        rust_fn(empty)

    Gf = fnx.cycle_graph(3)
    Gn = nx.cycle_graph(3)
    with pytest.raises(nx.NotATree, match="provided graph is not a tree"):
        fnx.to_prufer_sequence(Gf)
    with pytest.raises(nx.NotATree, match="provided graph is not a tree"):
        nx.to_prufer_sequence(Gn)
    with pytest.raises(nx.NotATree, match="provided graph is not a tree"):
        rust_fn(Gf)


def test_balanced_tree_negative_r_match_nx_geometric_formula():
    """br-r37-c1-bt-neg-r: balanced_tree(r, h) for negative r used to
    short-circuit blanket-return ``empty_graph(0)``.  nx instead
    routes through the geometric-series formula
    ``n = (1 - r**(h+1)) // (1 - r)`` and dispatches to
    full_rary_tree, yielding either positive-n graphs (when h+1 is
    even) or NetworkXError (when h+1 is odd and yields negative n).
    Lock parity across sign×parity combinations."""
    # h+1 even (n positive): isolated-nodes graph
    for r, h, expected_n in [(-1, 0, 1), (-1, 2, 1), (-2, 0, 1),
                              (-2, 2, 3), (-3, 0, 1), (-3, 2, 7)]:
        Gf = fnx.balanced_tree(r, h)
        Gn = nx.balanced_tree(r, h)
        assert Gf.number_of_nodes() == Gn.number_of_nodes() == expected_n
        assert Gf.number_of_edges() == Gn.number_of_edges() == 0
    # h+1 odd, negative r: nx raises NetworkXError on computed n<0
    for r, h, neg_n in [(-2, 1, -1), (-2, 3, -5), (-3, 1, -2),
                         (-3, 3, -20)]:
        match = f"Negative number of nodes not valid: {neg_n}"
        with pytest.raises(nx.NetworkXError, match=match):
            fnx.balanced_tree(r, h)
    # Positive args still go through Rust fast-path with parity
    Gf = fnx.balanced_tree(3, 2)
    Gn = nx.balanced_tree(3, 2)
    assert Gf.number_of_nodes() == Gn.number_of_nodes() == 13
    assert Gf.number_of_edges() == Gn.number_of_edges() == 12


def test_random_powerlaw_tree_sequence_nonpositive_n_match_nx():
    """br-r37-c1-rpts-neg: same defect family as br-r37-c1-{rgg-neg,
    pjf7g, srgg-neg, trgg-neg, 60f9n, waxman-neg, gtg-neg, hszkp,
    48hex}. random_powerlaw_tree_sequence silently returned ``[]`` for
    n <= 0 (range(n) yielded nothing and the empty-sequence early
    return was reached); nx raises ValueError leaked from internal
    rng.randint/randrange.  Lock parity on the structural-error
    contract."""
    for n in (-5, -1, 0):
        with pytest.raises(ValueError, match=r"empty range in randrange"):
            fnx.random_powerlaw_tree_sequence(n, seed=42)
    # Positive args still work.
    fseq = fnx.random_powerlaw_tree_sequence(5, seed=42)
    nseq = nx.random_powerlaw_tree_sequence(5, seed=42)
    assert fseq == nseq
    # n=1 still raises NetworkXError (existing convergence-failure
    # contract — single-node tree is degenerate).
    with pytest.raises(nx.NetworkXError, match="Exceeded max"):
        fnx.random_powerlaw_tree_sequence(1, seed=42)


def test_gnm_random_graph_negative_n_match_nx():
    """br-r37-c1-gnm-neg: same defect family as br-r37-c1-{rgg-neg,
    pjf7g, srgg-neg, trgg-neg, 60f9n, waxman-neg, gtg-neg, hszkp}.
    gnm_random_graph silently accepted negative n (returning empty
    graph); nx raises NetworkXError. Lock parity on the structural-
    error contract."""
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.gnm_random_graph(-5, 5, seed=42)
    # Negative m is OK (no edges to add).
    G_f = fnx.gnm_random_graph(5, -5, seed=42)
    G_n = nx.gnm_random_graph(5, -5, seed=42)
    assert G_f.number_of_nodes() == G_n.number_of_nodes() == 5
    assert G_f.number_of_edges() == G_n.number_of_edges() == 0
    # Positive args still work.
    G_f = fnx.gnm_random_graph(10, 3, seed=42)
    G_n = nx.gnm_random_graph(10, 3, seed=42)
    assert G_f.number_of_nodes() == G_n.number_of_nodes() == 10
    assert G_f.number_of_edges() == G_n.number_of_edges()


def test_waxman_geographical_threshold_negative_n_match_nx():
    """br-r37-c1-{waxman-neg, gtg-neg}: same defect family as
    br-r37-c1-{rgg-neg, pjf7g, srgg-neg, trgg-neg, 60f9n}.
    waxman_graph and geographical_threshold_graph silently accepted
    negative `n`; nx raises NetworkXError. Lock parity."""
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.waxman_graph(-5, seed=42)
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.geographical_threshold_graph(-5, 0.5, seed=42)
    # Positive n still works.
    G_f = fnx.waxman_graph(10, seed=42)
    G_n = nx.waxman_graph(10, seed=42)
    assert G_f.number_of_nodes() == G_n.number_of_nodes() == 10


def test_soft_thresholded_random_geometric_negative_n_match_nx():
    """br-r37-c1-{srgg-neg, trgg-neg}: same defect family as
    br-r37-c1-{rgg-neg, pjf7g}. soft_random_geometric_graph and
    thresholded_random_geometric_graph silently accepted negative
    `n` (returning empty graph); nx raises NetworkXError. Lock
    parity on the structural-error contract."""
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.soft_random_geometric_graph(-5, 0.5, seed=42)
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.thresholded_random_geometric_graph(-5, 0.5, 0.1, seed=42)
    # Positive n still works.
    G_f = fnx.soft_random_geometric_graph(10, 0.5, seed=42)
    G_n = nx.soft_random_geometric_graph(10, 0.5, seed=42)
    assert G_f.number_of_nodes() == G_n.number_of_nodes() == 10


def test_caveman_random_geometric_negative_args_match_nx():
    """br-r37-c1-cave-neg + br-r37-c1-rgg-neg: caveman_graph,
    connected_caveman_graph, and random_geometric_graph silently
    accepted negative size arguments (returning empty graphs);
    nx raises NetworkXError("Negative number of nodes not valid:
    -X"). Lock parity on all three generators across both arg
    positions."""
    # caveman_graph: l < 0
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.caveman_graph(-1, 5)
    # caveman_graph: k < 0
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.caveman_graph(3, -1)
    # connected_caveman_graph inherits the fix via underlying caveman_graph.
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.connected_caveman_graph(-1, 5)
    # random_geometric_graph: n < 0
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.random_geometric_graph(-5, 0.5)

    # Positive args still work.
    G_f = fnx.caveman_graph(3, 4)
    G_n = nx.caveman_graph(3, 4)
    assert G_f.number_of_nodes() == G_n.number_of_nodes() == 12


def test_full_rary_tree_negative_args_match_nx():
    """br-r37-c1-frt-neg: same defect family as br-r37-c1-{w1smc,
    udsdu, nxj7k, f34fw}. The Rust full_rary_tree binding declared
    both `r` and `n` as unsigned int and raised OverflowError
    uniformly. nx has domain-specific contracts:
      - n < 0 → NetworkXError("Negative number of nodes not valid")
      - r < 0 → empty graph with n isolated nodes (no children)
      - r == 0 → empty graph with n isolated nodes

    Lock parity on all three negative-arg paths."""
    # n < 0 raises NetworkXError
    with pytest.raises(nx.NetworkXError, match="Negative number of nodes"):
        fnx.full_rary_tree(2, -1)

    # r < 0 returns n isolated nodes
    G_f = fnx.full_rary_tree(-1, 5)
    G_n = nx.full_rary_tree(-1, 5)
    assert G_f.number_of_nodes() == G_n.number_of_nodes() == 5
    assert G_f.number_of_edges() == G_n.number_of_edges() == 0

    # r == 0 (also no children → isolated)
    G_f = fnx.full_rary_tree(0, 5)
    G_n = nx.full_rary_tree(0, 5)
    assert G_f.number_of_edges() == G_n.number_of_edges() == 0

    # Positive values still work.
    G_f = fnx.full_rary_tree(2, 7)
    G_n = nx.full_rary_tree(2, 7)
    assert G_f.number_of_edges() == G_n.number_of_edges()


def test_eigenvector_centrality_negative_max_iter_raises_convergence_failure():
    """br-r37-c1-eigvec-maxiter: nx raises
    PowerIterationFailedConvergence on max_iter <= 0 (the power
    iteration exits immediately without converging). The Rust
    binding declared max_iter as unsigned int and raised
    OverflowError on negatives. Code that catches
    PowerIterationFailedConvergence to detect non-convergence
    silently broke on fnx — got the wrong exception class.

    Lock nx's domain-specific exception across negative,
    zero, and small-positive max_iter inputs."""
    G = fnx.path_graph(5)
    for mi in (-1, 0, 1, -5):
        with pytest.raises(nx.PowerIterationFailedConvergence):
            fnx.eigenvector_centrality(G, max_iter=mi)


_NEGATIVE_DEPTH_OR_CUTOFF_FUNCS = [
    ("dfs_edges", "depth_limit", lambda fn, m, G: list(fn(G, 0, depth_limit=-1))),
    ("dfs_predecessors", "depth_limit", lambda fn, m, G: dict(fn(G, 0, depth_limit=-1))),
    ("dfs_successors", "depth_limit", lambda fn, m, G: dict(fn(G, 0, depth_limit=-1))),
    ("dfs_postorder_nodes", "depth_limit", lambda fn, m, G: list(fn(G, 0, depth_limit=-1))),
    ("dfs_preorder_nodes", "depth_limit", lambda fn, m, G: list(fn(G, 0, depth_limit=-1))),
    ("single_source_shortest_path_length", "cutoff",
     lambda fn, m, G: dict(fn(G, 0, cutoff=-1))),
    ("all_pairs_shortest_path", "cutoff",
     lambda fn, m, G: dict(fn(G, cutoff=-1))),
    ("all_pairs_shortest_path_length", "cutoff",
     lambda fn, m, G: dict(fn(G, cutoff=-1))),
]


@pytest.mark.parametrize(
    "name,kwarg,op",
    _NEGATIVE_DEPTH_OR_CUTOFF_FUNCS,
    ids=[t[0] for t in _NEGATIVE_DEPTH_OR_CUTOFF_FUNCS],
)
def test_traversal_negative_depth_bulk_matches_nx(name, kwarg, op):
    """br-r37-c1-trav-depth-bulk: same defect family as br-r37-c1-
    {w1smc, udsdu}. The Rust traversal bindings declare
    depth_limit/cutoff as unsigned int — negative values raised
    OverflowError. nx walks `range(depth)` / while-loop, which
    trivially yields nothing on negatives. The bulk retrofit
    `_bulk_coerce_negative_depth_to_zero` wraps each affected
    function so negative depth/cutoff is coerced to 0
    (nx-equivalent degenerate result) before the Rust binding
    sees it. Lock parity on all 8 sibling functions."""
    G_f = fnx.path_graph(5)
    G_n = nx.path_graph(5)
    f_fn = getattr(fnx, name)
    n_fn = getattr(nx, name)
    f_result = op(f_fn, fnx, G_f)
    n_result = op(n_fn, nx, G_n)
    assert f_result == n_result


def test_traversal_negative_depth_or_cutoff_matches_nx():
    """br-r37-c1-bfs-depth: same defect class as br-r37-c1-w1smc.
    The Rust BFS/DFS bindings declared `depth_limit` / `cutoff` as
    unsigned int — negative values raised OverflowError. nx walks
    `range(depth)` / while-loop which trivially yields nothing on
    negatives. Affected `bfs_edges`, `dfs_tree`,
    `single_source_shortest_path`. Lock parity on negative
    depth/cutoff inputs."""
    G = fnx.path_graph(5)
    G_n = nx.path_graph(5)

    # bfs_edges with depth=-1 → empty iteration (matches nx).
    assert list(fnx.bfs_edges(G, 0, depth_limit=-1)) == []
    assert list(fnx.bfs_edges(G, 0, depth_limit=-1)) == list(
        nx.bfs_edges(G_n, 0, depth_limit=-1)
    )

    # dfs_tree with depth=-1 → matches nx (which produces a 2-node tree).
    f_tree = fnx.dfs_tree(G, 0, depth_limit=-1)
    n_tree = nx.dfs_tree(G_n, 0, depth_limit=-1)
    assert sorted(f_tree.nodes()) == sorted(n_tree.nodes())

    # single_source_shortest_path with cutoff=-1 → just {source: [source]}.
    assert fnx.single_source_shortest_path(G, 0, cutoff=-1) == {0: [0]}
    assert fnx.single_source_shortest_path(G, 0, cutoff=-1) == \
        nx.single_source_shortest_path(G_n, 0, cutoff=-1)


def test_descendants_at_distance_degenerate_distance_returns_empty():
    """br-r37-c1-dad-distance: nx returns set() for any non-positive
    int distance AND for non-int distances (its BFS / range loop
    degenerates trivially). The Rust binding raised OverflowError
    on negative ints (Rust can't convert negative to unsigned) and
    TypeError on non-int distances. Defensive code that treats
    'no nodes at distance' as a valid empty result silently broke
    on fnx.

    Lock nx-shape parity:
      - distance < 0       → set()   (was OverflowError)
      - distance non-int   → set()   (was TypeError)
      - missing source     → NetworkXError  (preserved)
      - unhashable source  → NetworkXError  (preserved)
    """
    G = fnx.path_graph(5)
    G_n = nx.path_graph(5)

    # Negative distance — both libs return empty set.
    assert fnx.descendants_at_distance(G, 0, -1) == set()
    assert fnx.descendants_at_distance(G, 0, -10) == nx.descendants_at_distance(G_n, 0, -10)

    # Non-int distance — both libs return empty set.
    assert fnx.descendants_at_distance(G, 0, "foo") == set()
    assert fnx.descendants_at_distance(G, 0, "foo") == nx.descendants_at_distance(G_n, 0, "foo")

    # Valid positive distance still works.
    assert fnx.descendants_at_distance(G, 0, 2) == {2}

    # Missing source still raises NetworkXError.
    with pytest.raises(nx.NetworkXError):
        fnx.descendants_at_distance(G, 99, 1)


def test_backend_kwarg_accepted_on_bulk_dispatchable_functions():
    """br-r37-c1-spbk-bulk: br-r37-c1-0z6fh fixed 4 functions
    missing the `backend=None, **backend_kwargs` dispatch surface;
    a sweep identified ~20 more (the same defect class). The bulk
    `_bulk_add_backend_dispatch_kwargs` retrofit at module-load
    time wraps each with the standard validator. Lock that all 20
    accept `backend='networkx'` AND that their `inspect.signature`
    includes `backend` + `backend_kwargs` parameters."""
    import inspect

    target_fns = (
        "find_cycle", "simple_cycles", "diameter", "radius",
        "eccentricity", "average_shortest_path_length", "cycle_basis",
        "topological_sort", "descendants", "ancestors",
        "single_source_shortest_path", "has_path",
        "is_directed_acyclic_graph", "is_simple_path",
        "minimum_spanning_tree", "maximum_spanning_tree",
        "is_strongly_connected", "strongly_connected_components",
        "weakly_connected_components", "is_weakly_connected",
    )
    for name in target_fns:
        f_sig = inspect.signature(getattr(fnx, name))
        params = set(f_sig.parameters)
        assert "backend" in params, f"{name} missing backend kwarg"
        # var-keyword present (inspect represents **kwargs as a single param)
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in f_sig.parameters.values()
        )
        assert has_var_kw, f"{name} missing **backend_kwargs"
    # Garbage kwargs still raise (not silently accepted).
    G = fnx.path_graph(3)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        fnx.diameter(G, totally_made_up_kwarg=42)


def test_backend_kwarg_accepted_on_dispatchable_functions():
    """br-r37-c1-spbk: nx adds `backend=None, **backend_kwargs` to
    all dispatchable functions via the @_dispatchable decorator.
    Drop-in code that does `fn(G, ..., backend='networkx')` crashed
    on fnx with `TypeError: got an unexpected keyword argument
    'backend'`. Lock the dispatch surface on a sample of frequently-
    used functions: shortest_path, is_connected, connected_components,
    number_connected_components."""
    G = fnx.path_graph(5)
    # All four accept backend=...
    fnx.shortest_path(G, 0, 4, backend="networkx")
    fnx.is_connected(G, backend="networkx")
    list(fnx.connected_components(G, backend="networkx"))
    fnx.number_connected_components(G, backend="networkx")
    # Match nx's signature exactly via inspect
    import inspect
    for name in ("shortest_path", "is_connected", "connected_components",
                 "number_connected_components"):
        f_params = set(inspect.signature(getattr(fnx, name)).parameters)
        n_params = set(inspect.signature(getattr(nx, name)).parameters)
        assert f_params == n_params, f"{name} signature diverges: fnx={f_params}, nx={n_params}"


def test_write_gexf_byte_parity_with_nx():
    """br-r37-c1-wgexf-parity: the prior Rust-native write_gexf
    fast path's XML declaration diverged from nx's lxml-based
    output: fnx wrote `"1.0" encoding="UTF-8"` (double quotes,
    uppercase), nx writes `'1.0' encoding='utf-8'` (single quotes,
    lowercase). Now `write_gexf` always delegates to nx for
    byte-exact output. Lock byte parity (timestamps stripped since
    nx's <meta lastmodifieddate=...> includes the current date)."""
    import io, re
    G_f = fnx.path_graph(3)
    G_n = nx.path_graph(3)

    buf_f = io.BytesIO()
    buf_n = io.BytesIO()
    fnx.write_gexf(G_f, buf_f)
    nx.write_gexf(G_n, buf_n)

    def strip_timestamps(b):
        return re.sub(rb'lastmodifieddate="[^"]*"', b'lastmodifieddate=""', b)

    assert strip_timestamps(buf_f.getvalue()) == strip_timestamps(buf_n.getvalue())
    # XML decl uses single quotes + lowercase encoding (matches nx)
    assert buf_f.getvalue().startswith(b"<?xml version='1.0' encoding='utf-8'?>")


def test_write_multiline_adjlist_byte_parity_with_nx():
    """br-r37-c1-wmadj-header: nx prepends a 3-line timestamped
    comment header to the multiline-adjlist body; fnx previously
    omitted it. Byte-level snapshot diffs across libraries failed.
    Lock the comment-stripped equality + header-presence."""
    import io
    G_f = fnx.path_graph(3)
    G_n = nx.path_graph(3)

    buf_f = io.BytesIO()
    buf_n = io.BytesIO()
    fnx.write_multiline_adjlist(G_f, buf_f)
    nx.write_multiline_adjlist(G_n, buf_n)

    def strip_comments(b):
        return b"".join(
            line for line in b.splitlines(keepends=True) if not line.startswith(b"#")
        )

    assert strip_comments(buf_f.getvalue()) == strip_comments(buf_n.getvalue())
    # Timestamped header present (3 comment lines)
    header_lines = [
        line for line in buf_f.getvalue().splitlines() if line.startswith(b"#")
    ]
    assert len(header_lines) == 3


def test_write_graphml_byte_parity_with_nx():
    """br-r37-c1-wgml-parity: the prior Rust-native write_graphml fast
    path diverged byte-wise from nx in three observable places:
    XML decl quoting (`"1.0"` vs `'1.0'`), `<graph id="G">` (extra
    attribute), and self-closing tags (`<node id="0"/>` vs
    `<node id="0" />`). The public `write_graphml` now delegates
    to nx unconditionally for byte-exact output."""
    import io
    G_f = fnx.path_graph(3)
    G_n = nx.path_graph(3)

    buf_f = io.BytesIO()
    buf_n = io.BytesIO()
    fnx.write_graphml(G_f, buf_f)
    nx.write_graphml(G_n, buf_n)

    assert buf_f.getvalue() == buf_n.getvalue()


def test_write_adjlist_byte_parity_with_nx():
    """br-r37-c1-wadj-parity: the Rust-native write_adjlist fast
    path omitted the timestamped comment header and the trailing
    newline that nx writes. Tooling that snapshot-diffs adjlist
    output across libraries saw spurious differences. The public
    `write_adjlist` now delegates to nx unconditionally for
    byte-exact output."""
    import io
    G_f = fnx.path_graph(5)
    G_n = nx.path_graph(5)

    buf_f = io.BytesIO()
    buf_n = io.BytesIO()
    fnx.write_adjlist(G_f, buf_f)
    nx.write_adjlist(G_n, buf_n)

    # Strip timestamp comments — they include date/time which won't
    # be exactly equal to the millisecond.
    def strip_comments(b):
        return b"".join(
            line for line in b.splitlines(keepends=True) if not line.startswith(b"#")
        )

    assert strip_comments(buf_f.getvalue()) == strip_comments(buf_n.getvalue())
    # Trailing newline preserved (was missing in the prior Rust path)
    assert buf_f.getvalue().endswith(b"\n")


# --- View pickle / iter / equality regression locks
# (br-r37-c1-{z42ez, 7gej0, oww5k, k1xn4}) -----------------------------
import pickle


def test_z42ez_edge_and_degree_views_pickle():
    """br-r37-c1-z42ez: G.edges and G.degree on Graph/DiGraph
    crashed pickle because the underlying Rust EdgeView /
    DegreeView / DiDegreeView lacked __reduce__.  Snapshot semantics
    (restore as ``list``) match nx's pickle round-trip behavior."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3)])
    DG = fnx.DiGraph()
    DG.add_edges_from([(0, 1), (1, 2), (2, 3)])

    # Each of these used to raise TypeError("cannot pickle ...")
    for view in (G.edges, G.degree, DG.degree, DG.edges):
        b = pickle.dumps(view)
        r = pickle.loads(b)
        # Round-trip preserves the materialized contents
        assert sorted(map(tuple, map(sorted, r))) == sorted(
            map(tuple, map(sorted, view))
        )


def test_7gej0_digraph_in_out_edges_iterable():
    """br-r37-c1-7gej0: DG.in_edges / DG.out_edges on DiGraph were
    bound methods rather than iterable views.  ``for u, v in
    G.in_edges:`` used to raise TypeError on the `for`.  Lock that
    both attributes are usable as iterables (matching nx's
    InEdgeView / OutEdgeView contract)."""
    DG = fnx.DiGraph()
    DG.add_edges_from([(0, 1), (1, 2), (2, 3)])
    in_pairs = sorted(tuple(uv) for uv in DG.in_edges)
    out_pairs = sorted(tuple(uv) for uv in DG.out_edges)
    assert in_pairs == [(0, 1), (1, 2), (2, 3)]
    assert out_pairs == [(0, 1), (1, 2), (2, 3)]
    # len() works
    assert len(DG.in_edges) == 3
    assert len(DG.out_edges) == 3


def test_oww5k_di_edge_method_view_eq_and_data():
    """br-r37-c1-oww5k: _DiEdgeMethodView (returned from
    DG.in_edges / DG.out_edges per the br-r37-c1-7gej0 fix)
    initially missed __eq__ + .data() — partial nx.InEdgeView
    contract.  Lock both."""
    DG = fnx.DiGraph()
    DG.add_edges_from([(0, 1, {"w": 5}), (1, 2, {"w": 7})])
    # __eq__ (Set-like)
    assert DG.in_edges == DG.in_edges
    assert DG.out_edges == DG.out_edges
    # .data() returns 3-tuples (u, v, data_dict)
    in_data = list(DG.in_edges.data())
    assert all(len(t) == 3 for t in in_data)
    assert {tuple((u, v, frozenset(d.items()))) for u, v, d in in_data} == {
        (0, 1, frozenset({("w", 5)})),
        (1, 2, frozenset({("w", 7)})),
    }


def test_k1xn4_edge_views_eq_across_graph_types():
    """br-r37-c1-k1xn4: G.edges on DiGraph / MultiGraph /
    MultiDiGraph used object.__eq__ — view == view returned False
    for distinct view objects pointing at the same graph.  Lock
    Set-like __eq__ semantics across all three classes."""
    for cls in (fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edges_from([(0, 1), (1, 2)])
        # Self-equality on freshly-fetched view objects
        assert G.edges == G.edges, f"edges == edges failed for {cls.__name__}"


def test_bnydo_multidigraph_in_out_edges_yield_3_tuples():
    """br-r37-c1-bnydo: MultiDiGraph.in_edges / out_edges previously
    iterated 2-tuples, diverging from nx where these views default
    to ``keys=True`` (3-tuples).  Asymmetric defaults silently
    broke unpacking-loops in caller code."""
    MDG = fnx.MultiDiGraph()
    MDG.add_edges_from([(0, 1), (1, 2), (2, 3)])
    in_pairs = list(MDG.in_edges)
    out_pairs = list(MDG.out_edges)
    # Each tuple is (u, v, key) — 3 elements, not 2
    for tup in in_pairs + out_pairs:
        assert len(tup) == 3, f"expected 3-tuple, got {tup!r}"
    # Parity with nx for the same construction
    nMDG = nx.MultiDiGraph()
    nMDG.add_edges_from([(0, 1), (1, 2), (2, 3)])
    assert sorted(in_pairs) == sorted(nMDG.in_edges)
    assert sorted(out_pairs) == sorted(nMDG.out_edges)


def test_7krwv_node_view_eq_across_all_four_graph_classes():
    """br-r37-c1-7krwv: G.nodes used object.__eq__ (identity) so
    ``view == view`` returned False on freshly-fetched view objects.
    nx's NodeView is Mapping-equal.  Lock across all 4 classes."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edges_from([(0, 1), (1, 2)])
        assert G.nodes == G.nodes, f"NodeView __eq__ broken on {cls.__name__}"
        # Also: equal to the nx-style dict view of itself
        assert dict(G.nodes) == dict(G.nodes)


def test_86151_degree_view_family_eq_across_classes():
    """br-r37-c1-86151: G.degree, G.in_degree, G.out_degree views
    all used object.__eq__.  Lock Set/Mapping equality on every
    DegreeView variant."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edges_from([(0, 1), (1, 2)])
        assert G.degree == G.degree, f"degree __eq__ broken on {cls.__name__}"
    for cls in (fnx.DiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edges_from([(0, 1)])
        assert G.in_degree == G.in_degree, f"in_degree __eq__ broken on {cls.__name__}"
        assert G.out_degree == G.out_degree, f"out_degree __eq__ broken on {cls.__name__}"


def test_fbtk0_edge_view_set_protocol_complete():
    """br-r37-c1-fbtk0: edge views previously implemented only
    __eq__ — missed Set comparison (<=, <, >=, >, isdisjoint) and
    Set algebra (&, |, -, ^).  Lock the full Set protocol."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3)])
    G2 = fnx.Graph()
    G2.add_edges_from([(1, 2)])
    # Set comparison
    assert G2.edges <= G.edges
    assert G2.edges < G.edges
    assert G.edges >= G2.edges
    assert G.edges > G2.edges
    assert G.edges.isdisjoint(set())
    assert not G.edges.isdisjoint({(1, 2)})
    # Set algebra returns a real set with edge tuples
    inter = G.edges & G2.edges
    assert sorted(map(tuple, map(sorted, inter))) == [(1, 2)]
    diff = G.edges - G2.edges
    assert len(diff) == 2
    union = G.edges | {(99, 100)}
    assert (99, 100) in union or (100, 99) in union
    sym = G.edges ^ G2.edges
    assert (1, 2) not in sym and (0, 1) in {tuple(sorted(e)) for e in sym}


def test_s89yr_subgraph_filtered_edge_view_set_protocol():
    """br-r37-c1-s89yr: subgraph views' edges (_FilteredEdgeView)
    missed __eq__ for self-equality plus the Set comparison
    operators.  Lock both for the filtered-view code path."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2), (2, 3), (0, 3)])
    sg = G.subgraph([0, 1, 2])
    # Self-equality (object identity wasn't enough for view objects
    # constructed afresh on each property access)
    assert sg.edges == sg.edges
    # Subset comparison: filtered view's edges <= parent view's edges
    assert sg.edges <= G.edges
    assert sg.edges < G.edges
    # Intersection and difference behave as set algebra
    inter = sg.edges & G.edges
    assert len(inter) == len(list(sg.edges))
    diff = G.edges - sg.edges
    assert (0, 3) in diff or (3, 0) in diff


def test_ld4oo_reverse_view_edges_set_protocol():
    """br-r37-c1-ld4oo: G.reverse().edges (_ReverseEdgeView) used to
    miss the entire Set protocol — only __iter__/__contains__ — and
    iter shape diverged on multigraphs.  Lock Set comparison + algebra
    on the reversed-view path."""
    DG = fnx.DiGraph()
    DG.add_edges_from([(0, 1), (1, 2), (2, 3)])
    R = DG.reverse()
    # Self-equality
    assert R.edges == R.edges
    # Set comparison vs sets of pairs
    rset = {tuple(sorted(e)) for e in R.edges}
    assert R.edges <= R.edges
    # Set algebra
    inter = R.edges & R.edges
    assert {tuple(sorted(e)) for e in inter} == rset


def test_8crof_node_data_view_pickles():
    """br-r37-c1-8crof: G.nodes(data=True) NodeDataView crashed
    pickle.  Snapshot to list semantics matches nx round-trip."""
    G = fnx.Graph()
    G.add_nodes_from([(0, {"x": 1}), (1, {"y": 2})])
    r = pickle.loads(pickle.dumps(G.nodes(data=True)))
    assert sorted(r) == [(0, {"x": 1}), (1, {"y": 2})]


def test_w97ow_edge_data_view_pickles():
    """br-r37-c1-w97ow: G.edges.data() EdgeDataView crashed pickle
    on Graph (wrapper_descriptor class shadowing).  Lock round-trip."""
    G = fnx.Graph()
    G.add_edges_from([(0, 1, {"w": 5}), (1, 2, {"w": 7})])
    r = pickle.loads(pickle.dumps(G.edges.data()))
    by_uv = {tuple(sorted((u, v))): d for u, v, d in r}
    assert by_uv == {(0, 1): {"w": 5}, (1, 2): {"w": 7}}


def test_qh17m_union_raises_on_overlapping_nodes():
    """br-r37-c1-qh17m: fnx.union(G, H) used to silently merge
    overlapping nodes; nx raises NetworkXError("The node sets of
    the graphs are not disjoint...").  Lock the raise."""
    G = fnx.Graph(); G.add_edges_from([(0, 1), (1, 2)])
    H = fnx.Graph(); H.add_edges_from([(2, 3), (3, 4)])
    with pytest.raises(nx.NetworkXError, match="not disjoint"):
        fnx.union(G, H)
    # Disjoint case still works
    H2 = fnx.Graph(); H2.add_edges_from([(10, 11)])
    U = fnx.union(G, H2)
    assert U.number_of_nodes() == 5


def test_ea7eh_add_edges_from_raises_networkx_error_on_bad_arity():
    """br-r37-c1-ea7eh: G.add_edges_from raised ValueError on
    bad-arity tuples; nx raises NetworkXError.  Lock the type."""
    G = fnx.Graph()
    with pytest.raises(nx.NetworkXError):
        G.add_edges_from([(0, 1, 2, 3)])  # 4-tuple too many
    with pytest.raises(nx.NetworkXError):
        G.add_edges_from([(0,)])  # 1-tuple too few


def test_eeawk_write_adjlist_byte_parity_with_nx():
    """br-r37-c1-eeawk: write_adjlist Rust fast path previously
    omitted the 3-line ``# / # GMT ... / #`` header and trailing
    newline.  Lock byte-equality with nx (timestamp line excluded)."""
    import io
    buf_f = io.BytesIO(); fnx.write_adjlist(fnx.path_graph(3), buf_f)
    buf_n = io.BytesIO(); nx.write_adjlist(nx.path_graph(3), buf_n)
    def strip_ts(b):
        return b'\n'.join(l for l in b.split(b'\n') if not l.startswith(b'# GMT'))
    assert strip_ts(buf_f.getvalue()) == strip_ts(buf_n.getvalue())
    # Header starts with '#' (first line is sys.argv[0] commented)
    assert buf_f.getvalue().startswith(b"#")
    assert buf_f.getvalue().endswith(b"\n")


def test_nlkkm_write_graphml_byte_parity_with_nx():
    """br-r37-c1-nlkkm: write_graphml Rust fast path previously
    diverged in XML decl quoting + graph id + self-closing tag
    spacing.  Lock byte-equality with nx."""
    import io
    buf_f = io.BytesIO(); fnx.write_graphml(fnx.path_graph(3), buf_f)
    buf_n = io.BytesIO(); nx.write_graphml(nx.path_graph(3), buf_n)
    assert buf_f.getvalue() == buf_n.getvalue()


def test_nhgtp_write_multiline_adjlist_byte_parity_with_nx():
    """br-r37-c1-nhgtp: write_multiline_adjlist previously omitted
    the 3-line timestamped header.  Lock byte-equality with nx
    (timestamp line excluded)."""
    import io
    buf_f = io.BytesIO(); fnx.write_multiline_adjlist(fnx.path_graph(3), buf_f)
    buf_n = io.BytesIO(); nx.write_multiline_adjlist(nx.path_graph(3), buf_n)
    def strip_ts(b):
        return b'\n'.join(l for l in b.split(b'\n') if not l.startswith(b'# GMT'))
    assert strip_ts(buf_f.getvalue()) == strip_ts(buf_n.getvalue())
    assert buf_f.getvalue().startswith(b"#")


def test_htvy8_write_gexf_byte_parity_with_nx():
    """br-r37-c1-htvy8: write_gexf Rust fast path previously
    diverged in XML declaration quoting/encoding case.  The fix
    delegates to nx for byte-exact output.  Lock byte-equality."""
    import io
    buf_f = io.BytesIO(); fnx.write_gexf(fnx.path_graph(3), buf_f)
    buf_n = io.BytesIO(); nx.write_gexf(nx.path_graph(3), buf_n)
    # gexf embeds timestamps; strip lastmodifieddate attribute
    import re
    def strip_dates(b):
        return re.sub(rb'lastmodifieddate="[^"]*"', b'lastmodifieddate=""', b)
    assert strip_dates(buf_f.getvalue()) == strip_dates(buf_n.getvalue())


def test_disjoint_union_all_intersection_all_empty_message_match_nx():
    """br-r37-c1-{djuall-msg, iall-msg}: empty-list error messages
    diverged from nx's exact text.

    * disjoint_union_all([]) — nx delegates the empty-list check
      to union_all and leaks "cannot apply union_all to an empty
      list"; fnx previously said "cannot apply disjoint_union_all
      to an empty list" (more accurate but breaks string-match
      callers).
    * intersection_all([]) — fnx previously said "empty sequence"
      where nx says "empty list".

    Lock both for byte-identical message parity."""
    with pytest.raises(ValueError,
                       match=r"^cannot apply union_all to an empty list$"):
        fnx.disjoint_union_all([])
    with pytest.raises(ValueError,
                       match=r"^cannot apply intersection_all to an empty list$"):
        fnx.intersection_all([])
    # Regression: non-empty calls still work
    G = fnx.path_graph(2)
    H = fnx.path_graph(2)
    assert fnx.disjoint_union_all([G, H]).number_of_nodes() == 4
    assert fnx.intersection_all([G, H]).number_of_nodes() == 2


def test_pagerank_personalization_filters_to_graph_keys():
    """br-r37-c1-prnk-perso: pagerank ``personalization`` (and
    ``nstart`` / ``dangling``) vectors with keys not in G silently
    distributed implicit weight to dropped keys, producing scores
    that diverged from nx by a factor proportional to the bad-key
    weight share.

    nx filters these vectors to graph-intersection keys BEFORE
    normalizing.  As a side effect, a vector with NO graph keys
    (e.g. ``{99: 1.0}`` on a 3-node graph) raises ZeroDivisionError
    on the normalization step.

    Lock both the silent-rescaling fix and the
    ZeroDivisionError contract."""
    P = fnx.path_graph(3)

    # Mixed-bad: only key 0 is in G; nx rescales to 1.0 weight on
    # node 0.  fnx previously kept node 0 at 0.5 weight (using
    # full sum 1.0 as denominator), producing scores ~half of
    # nx.  Verify numeric parity now.
    rf = fnx.pagerank(P, personalization={0: 0.5, 99: 0.5})
    rn = nx.pagerank(nx.path_graph(3), personalization={0: 0.5, 99: 0.5})
    for node in rf:
        assert abs(rf[node] - rn[node]) < 1e-9, f"node {node}: {rf[node]} vs {rn[node]}"

    # Only-bad: ZeroDivisionError matches nx
    with pytest.raises(ZeroDivisionError):
        fnx.pagerank(P, personalization={99: 1.0})

    # Sanity: partial-good (key 0 only — nx fills others as 0)
    # produces same scores as mixed-bad above (since 99 is dropped
    # to leave only {0: 0.5} → normalized to {0: 1.0})
    rf2 = fnx.pagerank(P, personalization={0: 1.0})
    for node in rf:
        assert abs(rf[node] - rf2[node]) < 1e-9


def test_pagerank_bad_nstart_dangling_nonconverge_like_nx():
    """br-r37-c1-w3jlh: ``personalization`` raises
    ZeroDivisionError when it has no graph keys, but nx does not
    apply that typed error to ``nstart`` or ``dangling``.  Those
    vectors normalize to NaN and fail the power iteration instead."""
    P_fnx = fnx.path_graph(3)
    P_nx = nx.path_graph(3)

    for kwargs in ({"nstart": {99: 1.0}}, {"dangling": {99: 1.0}}):
        with pytest.raises(nx.PowerIterationFailedConvergence):
            nx.pagerank(P_nx, max_iter=3, **kwargs)
        with pytest.raises(nx.PowerIterationFailedConvergence):
            fnx.pagerank(P_fnx, max_iter=3, **kwargs)


def test_k_edge_augmentation_nonpositive_k_raises_match_nx():
    """br-r37-c1-keaug-k0: k_edge_augmentation silently returned
    ``[]`` for k <= 0, masking caller bugs (typo'd k, off-by-one).
    nx raises ValueError("k must be a positive integer, not {k}").
    Lock parity for k in {0, -1, -5} plus regression checks for
    valid k=1, 2."""
    G = fnx.path_graph(5)
    for k in (0, -1, -5):
        with pytest.raises(ValueError,
                           match=f"k must be a positive integer, not {k}"):
            list(fnx.k_edge_augmentation(G, k))
    # Regression: valid k still works
    assert list(fnx.k_edge_augmentation(G, 1)) == []
    aug = list(fnx.k_edge_augmentation(G, 2))
    assert aug == [(0, 4)]


def test_operator_type_mismatch_message_match_nx():
    """br-r37-c1-opmsg: union / compose / intersection /
    disjoint_union / etc. previously emitted a single
    "operator works only on graphs of the same type" message
    on type mismatch.  nx splits the message along two axes:

      * directedness mismatch → "All graphs must be directed
        or undirected."
      * multigraphness mismatch → "All graphs must be graphs
        or multigraphs."

    Lock both messages exactly so caller-side string checks
    align."""
    import re
    DIRECTED_MSG = re.escape("All graphs must be directed or undirected.")
    MULTI_MSG = re.escape("All graphs must be graphs or multigraphs.")

    # Directedness mismatch on union + compose
    with pytest.raises(nx.NetworkXError, match=DIRECTED_MSG):
        fnx.union(fnx.Graph([(0, 1)]), fnx.DiGraph([(2, 3)]))
    with pytest.raises(nx.NetworkXError, match=DIRECTED_MSG):
        fnx.union(fnx.DiGraph([(0, 1)]), fnx.Graph([(2, 3)]))
    with pytest.raises(nx.NetworkXError, match=DIRECTED_MSG):
        fnx.compose(fnx.Graph([(0, 1)]), fnx.DiGraph([(2, 3)]))

    # Multigraph mismatch
    with pytest.raises(nx.NetworkXError, match=MULTI_MSG):
        fnx.union(fnx.Graph([(0, 1)]), fnx.MultiGraph([(2, 3)]))
    with pytest.raises(nx.NetworkXError, match=MULTI_MSG):
        fnx.compose(fnx.MultiGraph([(0, 1)]), fnx.Graph([(2, 3)]))

    # Same-type regression: still works
    assert fnx.union(fnx.Graph([(0, 1)]),
                     fnx.Graph([(2, 3)])).number_of_nodes() == 4
    assert fnx.compose(fnx.Graph([(0, 1)]),
                       fnx.Graph([(1, 2)])).number_of_nodes() == 3


def test_dag_longest_path_length_preserves_int_type_match_nx():
    """br-r37-c1-daglen-int: dag_longest_path_length always returned
    float because the Rust binding coerces ``default_weight`` to
    float internally.  nx returns int when all contributing weights
    (edge values + default_weight) are int — sum-of-ints stays int.
    Lock the type-preservation contract for callers comparing
    against int literals (``assert dag_longest_path_length(G) == 3``
    pattern)."""

    def make(lib, edges):
        D = lib.DiGraph()
        D.add_weighted_edges_from(edges)
        return D

    # All-int weights → int result
    fr = fnx.dag_longest_path_length(make(fnx, [(0, 1, 5), (1, 2, 3)]),
                                     weight="weight")
    nr = nx.dag_longest_path_length(make(nx, [(0, 1, 5), (1, 2, 3)]),
                                    weight="weight")
    assert type(fr) is type(nr) is int
    assert fr == nr == 8

    # Default weight (no explicit weight attr) → int result
    DG_f = fnx.DiGraph(); DG_f.add_edges_from([(0, 1), (1, 2)])
    DG_n = nx.DiGraph(); DG_n.add_edges_from([(0, 1), (1, 2)])
    fr = fnx.dag_longest_path_length(DG_f)
    nr = nx.dag_longest_path_length(DG_n)
    assert type(fr) is type(nr) is int
    assert fr == nr == 2

    # Float weights → float result
    fr = fnx.dag_longest_path_length(make(fnx, [(0, 1, 5.0), (1, 2, 3.5)]),
                                     weight="weight")
    nr = nx.dag_longest_path_length(make(nx, [(0, 1, 5.0), (1, 2, 3.5)]),
                                    weight="weight")
    assert type(fr) is type(nr) is float
    assert fr == nr == 8.5

    # Mixed int + float → float result (any float promotes)
    fr = fnx.dag_longest_path_length(make(fnx, [(0, 1, 5), (1, 2, 3.5)]),
                                     weight="weight")
    nr = nx.dag_longest_path_length(make(nx, [(0, 1, 5), (1, 2, 3.5)]),
                                    weight="weight")
    assert type(fr) is type(nr) is float
    assert fr == nr == 8.5

    # br-r37-c1-12wfm: unused float edges must not demote an
    # integer-valued longest path to float.  nx's type follows the
    # selected path arithmetic, not every edge in the graph.
    fr = fnx.dag_longest_path_length(
        make(fnx, [(0, 1, 5), (1, 2, 3), (0, 2, 1.5)]),
        weight="weight",
    )
    nr = nx.dag_longest_path_length(
        make(nx, [(0, 1, 5), (1, 2, 3), (0, 2, 1.5)]),
        weight="weight",
    )
    assert type(fr) is type(nr) is int
    assert fr == nr == 8

    # bool edge/default values also accumulate to Python int in nx.
    fr = fnx.dag_longest_path_length(make(fnx, [(0, 1, True), (1, 2, 1)]))
    nr = nx.dag_longest_path_length(make(nx, [(0, 1, True), (1, 2, 1)]))
    assert type(fr) is type(nr) is int
    assert fr == nr == 2

    # Float default_weight → float result even with int edge weights
    fr = fnx.dag_longest_path_length(DG_f, default_weight=1.0)
    nr = nx.dag_longest_path_length(DG_n, default_weight=1.0)
    assert type(fr) is type(nr) is float


def test_dijkstra_bellman_ford_nonnumeric_weight_typeerror_match_nx():
    """br-r37-c1-djk-strw: dijkstra_path / bellman_ford_path with a
    string ``weight`` kwarg silently returned a path when edge values
    at that key were non-numeric (str, list, dict).  The Rust binding
    treated the value as the default 1.0, masking nx's TypeError on
    the natural ``+`` accumulation.

    Lock TypeError parity for dijkstra_path and bellman_ford_path
    across str / list / dict weight values, plus regression checks
    for valid numeric weights and missing-attr default."""
    def make(lib, val):
        G = lib.Graph()
        G.add_edge(0, 1, weight=val)
        G.add_edge(1, 2, weight=val)
        return G

    for fn_name in ("dijkstra_path", "bellman_ford_path"):
        f = getattr(fnx, fn_name)
        # Non-numeric values now propagate TypeError
        for bad in ("abc", "5", [1, 2], {"x": 1}):
            with pytest.raises(TypeError):
                f(make(fnx, bad), 0, 2)
        # Numeric values still work
        G = fnx.Graph()
        G.add_edge(0, 1, weight=5)
        G.add_edge(1, 2, weight=3)
        assert f(G, 0, 2) == [0, 1, 2]
        # Missing weight attr → default unweighted path
        assert f(fnx.path_graph(3), 0, 2) == [0, 1, 2]

    for bad in ("abc", [1, 2]):
        Gf = make(fnx, bad)
        Gn = make(nx, bad)
        with pytest.raises(TypeError):
            nx.shortest_path(
                Gn, 0, 2, weight="weight", method="bellman-ford"
            )
        with pytest.raises(TypeError):
            fnx.shortest_path(
                Gf, 0, 2, weight="weight", method="bellman-ford"
            )


def test_astar_path_nonnumeric_weight_typeerror_match_nx():
    """br-r37-c1-astar-strw: astar_path / astar_path_length silently
    returned a path when ``weight`` referenced edge values of
    non-numeric type (str / list / dict).  Same defect family as
    br-r37-c1-vi0zo (dijkstra/bellman_ford); the astar gate predates
    the _has_nonnumeric_edge_weight helper.

    Lock TypeError parity with nx for both functions across str /
    list / dict, plus None-routes-to-NetworkXNoPath, plus numeric
    regression."""
    def make(lib, val):
        G = lib.Graph()
        G.add_edge(0, 1, weight=val)
        G.add_edge(1, 2, weight=val)
        return G

    for fn_name in ("astar_path", "astar_path_length"):
        f = getattr(fnx, fn_name)
        for bad in ("abc", "5", [1, 2], {"x": 1}):
            with pytest.raises(TypeError):
                f(make(fnx, bad), 0, 2)
        # None weight: nx returns NetworkXNoPath (Node 2 not reachable)
        with pytest.raises(nx.NetworkXNoPath):
            f(make(fnx, None), 0, 2)
        # Numeric regression
        G = fnx.Graph()
        G.add_edge(0, 1, weight=5)
        G.add_edge(1, 2, weight=3)
        result = f(G, 0, 2)
        if fn_name == "astar_path":
            assert result == [0, 1, 2]
        else:
            assert result == 8 or result == 8.0  # type can vary


def test_astar_path_length_preserves_int_type_match_nx():
    """br-r37-c1-astarlen-int: astar_path_length always returned
    float because the Rust binding uses f64 internally.  nx returns
    int when all weights along the chosen path are int (bool counts
    as int — bool is an int subclass and nx accumulates True+True=2).
    Same defect family as br-r37-c1-oqspv on dag_longest_path_length.

    Lock type-preservation across all-int, default-no-weight, bool,
    all-float, and mixed configurations."""
    def make(lib, edges):
        G = lib.Graph()
        G.add_weighted_edges_from(edges)
        return G

    # All-int weights → int result
    fr = fnx.astar_path_length(make(fnx, [(0, 1, 5), (1, 2, 3)]), 0, 2)
    nr = nx.astar_path_length(make(nx, [(0, 1, 5), (1, 2, 3)]), 0, 2)
    assert type(fr) is type(nr) is int
    assert fr == nr == 8

    # Default (no weight attr) → int result
    fr = fnx.astar_path_length(fnx.path_graph(3), 0, 2)
    nr = nx.astar_path_length(nx.path_graph(3), 0, 2)
    assert type(fr) is type(nr) is int
    assert fr == nr == 2

    # Bool weights → int result (bool subclass of int)
    fr = fnx.astar_path_length(make(fnx, [(0, 1, True), (1, 2, True)]),
                               0, 2)
    nr = nx.astar_path_length(make(nx, [(0, 1, True), (1, 2, True)]),
                              0, 2)
    assert type(fr) is type(nr) is int

    # Float weights → float result
    fr = fnx.astar_path_length(make(fnx, [(0, 1, 5.0), (1, 2, 3.5)]),
                               0, 2)
    nr = nx.astar_path_length(make(nx, [(0, 1, 5.0), (1, 2, 3.5)]),
                              0, 2)
    assert type(fr) is type(nr) is float

    # Mixed → float (any float promotes)
    fr = fnx.astar_path_length(make(fnx, [(0, 1, 5), (1, 2, 3.5)]),
                               0, 2)
    nr = nx.astar_path_length(make(nx, [(0, 1, 5), (1, 2, 3.5)]),
                              0, 2)
    assert type(fr) is type(nr) is float


def test_resistance_distance_disconnected_raises_match_nx():
    """br-r37-c1-resd-disc: resistance_distance silently returned
    Laplacian-pseudo-inverse-derived numeric values on disconnected
    graphs (cross-component values are meaningless), masking nx's
    NetworkXError("Graph G must be strongly connected.").  Lock
    parity for 4 disconnected configurations + connected
    regression."""

    def disc_two_comps():
        return fnx.Graph([(0, 1), (2, 3)])

    def disc_bigger():
        return fnx.Graph([(0, 1), (1, 2), (3, 4), (4, 5)])

    # Same-component nodes still raise (graph as a whole disconnected)
    with pytest.raises(nx.NetworkXError, match="strongly connected"):
        fnx.resistance_distance(disc_two_comps(), 0, 1)
    # Cross-component
    with pytest.raises(nx.NetworkXError, match="strongly connected"):
        fnx.resistance_distance(disc_two_comps(), 0, 2)
    # Larger disconnected
    with pytest.raises(nx.NetworkXError, match="strongly connected"):
        fnx.resistance_distance(disc_bigger(), 0, 4)
    # Self-distance with disconnected graph
    with pytest.raises(nx.NetworkXError, match="strongly connected"):
        fnx.resistance_distance(disc_two_comps(), 0, 0)
    # No-node-args dict form on disconnected
    with pytest.raises(nx.NetworkXError, match="strongly connected"):
        fnx.resistance_distance(disc_two_comps())
    # Connected regression
    assert abs(fnx.resistance_distance(fnx.complete_graph(4), 0, 2) - 0.5) < 1e-9
    assert abs(fnx.resistance_distance(fnx.path_graph(5), 0, 4) - 4.0) < 1e-9


def test_graph_edit_distance_with_roots_returns_float_match_nx():
    """br-r37-c1-ged-flt: graph_edit_distance with ``roots=`` set
    returned int 0 for identical graphs because the local Python
    fallback initialized its cost accumulator to int 0.  nx
    consistently returns float.  Same defect family as the
    int-vs-float type-preservation series (br-r37-c1-{oqspv,
    ihfqv}) but inverted — nx returns float, fnx returned int.

    Lock float return type for graph_edit_distance across
    roots / no-roots / identical / different configurations."""
    P3_f = fnx.path_graph(3)
    P3_n = nx.path_graph(3)
    P4_f = fnx.path_graph(4)
    P4_n = nx.path_graph(4)

    cases = [
        # (G1, G2, roots, expected_value)
        (P3_f, P3_f, None, 0.0),
        (P3_f, P3_f, (0, 0), 0.0),
        (P3_f, P3_f, (1, 1), 0.0),
        (P3_f, P4_f, None, 2.0),
        (P3_f, P4_f, (0, 0), 2.0),
        (fnx.complete_graph(3), fnx.complete_graph(3), (0, 0), 0.0),
    ]
    for G1, G2, roots, expected in cases:
        kwargs = {} if roots is None else {"roots": roots}
        result = fnx.graph_edit_distance(G1, G2, **kwargs)
        assert type(result) is float, (
            f"expected float, got {type(result).__name__}: "
            f"G1={G1.number_of_nodes()}n, G2={G2.number_of_nodes()}n, roots={roots}"
        )
        assert result == expected


def test_adjacency_spectrum_returns_complex_match_nx():
    """br-r37-c1-aspec-cmplx: adjacency_spectrum previously returned
    a sorted ``float64`` ndarray (using np.linalg.eigvalsh + np.sort).
    nx uses the general non-Hermitian ``scipy.linalg.eigvals`` so its
    dtype is ``complex128`` and the return is unsorted.  Lock dtype
    parity (callers using ``.dtype`` or general numpy expectations
    break otherwise)."""
    import numpy as np
    cases = [
        fnx.complete_graph(4),
        fnx.path_graph(5),
        fnx.cycle_graph(3),
        fnx.DiGraph([(0, 1), (1, 2), (2, 0)]),
    ]
    nx_cases = [
        nx.complete_graph(4),
        nx.path_graph(5),
        nx.cycle_graph(3),
        nx.DiGraph([(0, 1), (1, 2), (2, 0)]),
    ]
    for G_f, G_n in zip(cases, nx_cases):
        fr = fnx.adjacency_spectrum(G_f)
        nr = nx.adjacency_spectrum(G_n)
        # dtype parity (THE central regression)
        assert fr.dtype == nr.dtype == np.complex128
        # value parity (sort both since solver order is unstable)
        assert np.allclose(np.sort_complex(fr), np.sort_complex(nr))


def test_dispersion_bad_node_raises_keyerror_match_nx():
    """br-r37-c1-disp-keyerr: dispersion raised NetworkXError when
    given a node not in G (because it called ``G.neighbors(u)``
    internally, which has nx's NetworkXError contract).  nx
    accesses ``G[u]`` directly and leaks a raw KeyError.  Lock
    KeyError parity for callers using ``except KeyError:`` to
    detect missing-node-pair cases."""
    K4 = fnx.complete_graph(4)

    # Pair form: bad u, bad v, both bad
    for u, v in [(99, 1), (0, 99), (99, 100)]:
        with pytest.raises(KeyError):
            fnx.dispersion(K4, u, v)

    # Dict form with bad u (v=None)
    with pytest.raises(KeyError):
        fnx.dispersion(K4, 99)

    # Regression: valid args still return float / dict
    assert fnx.dispersion(K4, 0, 1) == nx.dispersion(nx.complete_graph(4), 0, 1)
    assert isinstance(fnx.dispersion(K4), dict)
    assert isinstance(fnx.dispersion(K4, 0), dict)


def test_to_nested_tuple_typed_errors_match_nx():
    """br-r37-c1-tnt-typed-errs: to_nested_tuple raised generic
    NetworkXError on missing root and a Python RecursionError on
    non-tree (cyclic) input.  nx raises typed NodeNotFound / NotATree
    respectively.  RecursionError leaking is particularly bad — it's
    a programmer-error category that callers don't catch with normal
    domain-error handlers.

    Lock typed-error parity for both precondition violations plus
    valid-tree regression."""
    T = fnx.balanced_tree(2, 2)
    C = fnx.cycle_graph(3)

    # Bad root
    with pytest.raises(nx.NodeNotFound,
                       match=r"contains no node 99"):
        fnx.to_nested_tuple(T, 99)

    # Non-tree (cyclic)
    with pytest.raises(nx.NotATree,
                       match=r"provided graph is not a tree"):
        fnx.to_nested_tuple(C, 0)

    # Valid: regression
    assert fnx.to_nested_tuple(T, 0) == nx.to_nested_tuple(nx.balanced_tree(2, 2), 0)
    assert fnx.to_nested_tuple(T, 0, canonical_form=True) == nx.to_nested_tuple(
        nx.balanced_tree(2, 2), 0, canonical_form=True
    )


def test_bfs_layers_nonmember_int_source_typeerror_match_nx():
    """br-r37-c1-bfsl-typeerr: bfs_layers with sources= as a single
    int that's NOT in G raised NodeNotFound where nx raises
    TypeError.  fnx's wrapper had a try/except TypeError fallback
    that routed to the Rust raw binding, which pre-checked
    membership.  Too helpful — masked nx's leaky-but-documented
    contract.

    Lock TypeError parity for non-member single int + None +
    valid sources regression."""
    P5 = fnx.path_graph(5)

    # Non-member single int → TypeError (matching nx's set(sources) raise)
    with pytest.raises(TypeError, match=r"'int' object is not iterable"):
        list(fnx.bfs_layers(P5, sources=99))

    # None → TypeError (NoneType not iterable)
    with pytest.raises(TypeError, match=r"'NoneType' object is not iterable"):
        list(fnx.bfs_layers(P5, sources=None))

    # Member single int → works (wrapped to [n])
    assert list(fnx.bfs_layers(P5, sources=0)) == [[0], [1], [2], [3], [4]]

    # List of bad members → NetworkXError on the bad node
    with pytest.raises(nx.NetworkXError, match=r"The node 99 is not in"):
        list(fnx.bfs_layers(P5, sources=[99]))

    # Valid list source → works
    assert list(fnx.bfs_layers(P5, sources=[0, 1])) == [[0, 1], [2], [3], [4]]

    # Empty source list → empty layers
    assert list(fnx.bfs_layers(P5, sources=[])) == []


def test_vf2pp_empty_graph_returns_falsy_match_nx():
    """br-r37-c1-vf2pp-empty: vf2pp_is_isomorphic / vf2pp_isomorphism /
    vf2pp_all_isomorphisms all silently treated empty/empty as
    trivially isomorphic (returning True / {} / [{}] respectively).
    nx's vf2pp implementation treats empty graphs as a degenerate
    case and returns False / None / [].

    Lock parity for the empty-graph short-circuit across all three
    entry points + valid-graph regression."""
    empty = fnx.Graph()
    one = fnx.Graph(); one.add_node(0)

    # All-empty: False / None / []
    assert fnx.vf2pp_is_isomorphic(empty, empty) is False
    assert fnx.vf2pp_isomorphism(empty, empty) is None
    assert list(fnx.vf2pp_all_isomorphisms(empty, empty)) == []

    # Mixed empty: also False / None / []
    assert fnx.vf2pp_is_isomorphic(empty, one) is False
    assert fnx.vf2pp_is_isomorphic(one, empty) is False
    assert fnx.vf2pp_isomorphism(empty, one) is None
    assert fnx.vf2pp_isomorphism(one, empty) is None
    assert list(fnx.vf2pp_all_isomorphisms(empty, one)) == []

    # Regression: non-empty graphs still work normally
    assert fnx.vf2pp_is_isomorphic(one, one) is True
    K3 = fnx.complete_graph(3)
    assert fnx.vf2pp_is_isomorphic(K3, K3) is True
    assert fnx.vf2pp_is_isomorphic(K3, fnx.path_graph(3)) is False
    assert fnx.vf2pp_isomorphism(K3, K3) is not None


def test_traversal_backend_kwarg_surface_match_nx():
    """br-r37-c1-trav-bk: 11 BFS/DFS/topology entry points missed
    the ``*, backend=None, **backend_kwargs`` dispatch surface that
    nx's ``@_dispatchable`` decorator adds.  Drop-in code that used
    ``fn(G, ..., backend='networkx')`` crashed with TypeError on
    these functions while passing on the rest of the dispatch
    family.

    Same defect family as br-r37-c1-{spbk-bulk, qk425, 0z6fh}.

    Lock both signature parity (``backend`` parameter present) and
    runtime acceptance of ``backend=None`` for all 11 functions."""
    import inspect
    targets = (
        "bfs_labeled_edges", "dfs_labeled_edges", "bfs_layers",
        "descendants_at_distance", "bfs_predecessors", "bfs_successors",
        "bfs_tree", "dfs_tree", "topological_generations",
        "all_topological_sorts", "lexicographical_topological_sort",
    )
    for name in targets:
        f_sig = inspect.signature(getattr(fnx, name))
        assert "backend" in f_sig.parameters, (
            f"fnx.{name} missing backend kwarg"
        )

    # Runtime check: backend=None passes through; bogus raises
    P = fnx.path_graph(5)
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])

    # bfs_layers and a few siblings — confirm they accept backend=None
    list(fnx.bfs_layers(P, [0], backend=None))
    list(fnx.bfs_labeled_edges(P, 0, backend=None))
    list(fnx.dfs_labeled_edges(P, 0, backend=None))
    list(fnx.bfs_predecessors(P, 0, backend=None))
    list(fnx.bfs_successors(P, 0, backend=None))
    fnx.bfs_tree(P, 0, backend=None)
    fnx.dfs_tree(P, 0, backend=None)
    list(fnx.topological_generations(DG, backend=None))
    list(fnx.all_topological_sorts(DG, backend=None))
    list(fnx.lexicographical_topological_sort(DG, backend=None))
    fnx.descendants_at_distance(P, 0, 1, backend=None)

    # Bad backend → ImportError (matching nx's contract)
    with pytest.raises(ImportError):
        list(fnx.bfs_layers(P, [0], backend="bogus_backend"))


def test_bulk2_backend_kwarg_surface_match_nx():
    """br-r37-c1-bulk2-bk: 50 high-traffic dispatchable APIs across
    distance/path, connectivity, DAG, cycles, coloring, clustering,
    matching, and operators families missed the backend dispatch
    surface that nx's @_dispatchable adds.  Drop-in code that used
    ``fn(G, ..., backend='networkx')`` crashed with TypeError.

    Same defect family as br-r37-c1-{spbk-bulk, qk425, 0z6fh, 4gxxz}
    (which fixed earlier batches).  Lock the full surface."""
    import inspect
    targets = [
        # Distance / path
        "shortest_path_length", "dijkstra_path", "dijkstra_path_length",
        "all_pairs_dijkstra", "floyd_warshall", "johnson",
        # Connectivity
        "biconnected_components", "is_biconnected", "bridges",
        "has_bridges", "local_bridges", "articulation_points",
        "node_connectivity", "edge_connectivity", "minimum_edge_cut",
        "all_node_cuts",
        # DAG
        "condensation", "transitive_closure", "transitive_closure_dag",
        "transitive_reduction", "antichains", "dag_to_branching",
        "dag_longest_path", "dag_longest_path_length",
        # Cycles / trees
        "recursive_simple_cycles", "minimum_cycle_basis",
        "is_arborescence", "is_branching",
        # Coloring
        "greedy_color", "equitable_color",
        # Clustering
        "clustering", "average_clustering", "transitivity",
        "triangles", "square_clustering",
        # Matching
        "max_weight_matching", "min_weight_matching", "is_matching",
        "is_perfect_matching", "is_maximal_matching",
        # Operators
        "union", "compose", "intersection", "difference",
        "symmetric_difference", "disjoint_union",
        "cartesian_product", "tensor_product", "lexicographic_product",
        "strong_product",
    ]
    for name in targets:
        f_sig = inspect.signature(getattr(fnx, name))
        assert "backend" in f_sig.parameters, (
            f"fnx.{name} missing backend kwarg"
        )

    # Functional spot-check: a handful accept backend=None
    P = fnx.path_graph(5)
    K3 = fnx.complete_graph(3)
    fnx.shortest_path_length(P, 0, 4, backend=None)
    fnx.dijkstra_path(P, 0, 4, backend=None)
    fnx.clustering(P, backend=None)
    fnx.transitivity(P, backend=None)
    fnx.greedy_color(P, backend=None)
    fnx.node_connectivity(P, backend=None)
    fnx.triangles(K3, backend=None)
    fnx.max_weight_matching(K3, backend=None)
    fnx.is_matching(K3, set(), backend=None)
    fnx.dag_longest_path(fnx.DiGraph([(0, 1)]), backend=None)
    fnx.transitive_closure(fnx.DiGraph([(0, 1)]), backend=None)
