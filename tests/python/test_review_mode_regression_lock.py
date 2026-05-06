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
