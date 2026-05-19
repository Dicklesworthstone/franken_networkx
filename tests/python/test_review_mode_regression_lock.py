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


def test_bulk3_backend_kwarg_surface_match_nx():
    """br-r37-c1-bulk3-bk: 59 more dispatchable APIs across SSSP /
    multi-source variants, branching/MST, Eulerian, k-core,
    chordal, regularity families missed the backend dispatch
    surface.  Continuation of br-r37-c1-{4gxxz, pvapc} sweep —
    the second / final pass reaching ~100% backend kwarg parity.

    Lock signature parity for all 59 functions + functional
    spot-check on representative samples."""
    import inspect
    targets = [
        # Path / SSSP / multi-source variants
        "estrada_index",
        "all_pairs_dijkstra_path", "all_pairs_dijkstra_path_length",
        "all_pairs_bellman_ford_path", "all_pairs_bellman_ford_path_length",
        "single_source_dijkstra", "single_source_dijkstra_path",
        "single_source_dijkstra_path_length",
        "single_source_bellman_ford", "single_source_bellman_ford_path",
        "single_source_bellman_ford_path_length",
        "multi_source_dijkstra", "multi_source_dijkstra_path",
        "multi_source_dijkstra_path_length",
        "bellman_ford_path", "bellman_ford_path_length",
        "bellman_ford_predecessor_and_distance",
        "astar_path", "astar_path_length",
        "shortest_simple_paths",
        # Components / branching
        "attracting_components", "kosaraju_strongly_connected_components",
        "minimum_spanning_edges", "maximum_spanning_edges",
        "maximum_branching", "minimum_branching",
        "maximum_spanning_arborescence", "minimum_spanning_arborescence",
        # Distance measures
        "periphery", "center", "resistance_distance",
        "effective_graph_resistance",
        # Misc
        "flow_hierarchy", "global_efficiency", "local_efficiency",
        "algebraic_connectivity", "fiedler_vector", "spectral_ordering",
        # Eulerian
        "is_eulerian", "has_eulerian_path", "is_semieulerian",
        "eulerian_path", "eulerian_circuit", "eulerize",
        # Domination / k-core
        "is_dominating_set", "dominating_set",
        "core_number", "k_core", "k_shell", "k_crust", "k_corona", "k_truss",
        # Chordal
        "is_chordal", "chordal_graph_cliques", "chordal_graph_treewidth",
        "find_induced_nodes", "complete_to_chordal_graph",
        # Regularity
        "is_strongly_regular", "is_distance_regular",
    ]
    for name in targets:
        f_sig = inspect.signature(getattr(fnx, name))
        assert "backend" in f_sig.parameters, (
            f"fnx.{name} missing backend kwarg"
        )

    # Functional spot-check (representative samples)
    P = fnx.path_graph(5)
    fnx.astar_path(P, 0, 4, backend=None)
    fnx.bellman_ford_path(P, 0, 4, backend=None)
    fnx.center(P, backend=None)
    fnx.periphery(P, backend=None)
    fnx.k_core(P, backend=None)
    list(fnx.eulerian_circuit(fnx.cycle_graph(4), backend=None))
    fnx.global_efficiency(P, backend=None)
    fnx.is_eulerian(fnx.cycle_graph(4), backend=None)
    fnx.is_chordal(fnx.cycle_graph(4), backend=None)
    fnx.is_strongly_regular(fnx.complete_graph(4), backend=None)


def test_bulk4_backend_kwarg_surface_match_nx():
    """br-r37-c1-bulk4-bk: 64 more dispatchable APIs across
    communicability, assortativity, cuts, isolates, link prediction,
    isomorphism, polynomials, flows, and boundary measures missed
    the backend dispatch surface.  Final-sweep continuation of the
    bulk-fix series (bulk2/bulk3); the bulk-wrap also gained two
    fixes:

      * preserves ``**kwargs`` pass-through for functions that
        legitimately forward unknown kwargs (e.g. ``minimum_cut_value``
        forwarding to ``flow_func``); previously the wrapper stripped
        unknown kwargs as backend kwargs and rejected them.
      * re-syncs the ``fnx.isomorphism`` submodule exports after the
        wrap so ``fnx.isomorphism.is_isomorphic is fnx.is_isomorphic``
        — previously stale because the submodule snapshotted globals
        before the wrap ran.

    Lock signature parity for representative APIs + the flow-kwargs
    pass-through + iso submodule resync."""
    import inspect
    targets = [
        "communicability", "communicability_exp",
        "is_aperiodic", "is_isolate", "number_of_isolates", "isolates",
        "voronoi_cells",
        "degree_assortativity_coefficient",
        "attribute_assortativity_coefficient",
        "cut_size", "normalized_cut_size", "volume", "edge_expansion",
        "conductance",
        "edge_dfs", "edge_bfs",
        "compose_all", "union_all", "intersection_all", "disjoint_union_all",
        "jaccard_coefficient", "adamic_adar_index",
        "preferential_attachment", "resource_allocation_index",
        "is_isomorphic", "could_be_isomorphic",
        "fast_could_be_isomorphic", "faster_could_be_isomorphic",
        "simrank_similarity", "panther_similarity",
        "is_edge_cover",
        "to_dict_of_lists", "to_edgelist", "from_dict_of_dicts",
        "edge_boundary", "node_boundary",
        "immediate_dominators", "dominance_frontiers",
        "minimum_cut_value", "maximum_flow_value", "maximum_flow",
        "minimum_cut", "min_cost_flow", "min_cost_flow_cost",
        "max_flow_min_cost", "cost_of_flow", "gomory_hu_tree",
        "capacity_scaling", "network_simplex",
    ]
    for name in targets:
        sig = inspect.signature(getattr(fnx, name))
        assert "backend" in sig.parameters, f"fnx.{name} missing backend"

    # Flow function with **kwargs forwarding still works
    DG = fnx.DiGraph(); DG.add_edge(0, 1, capacity=10); DG.add_edge(1, 2, capacity=10)
    fnx.maximum_flow_value(DG, 0, 2, backend=None)

    # iso submodule resync: identity check
    assert fnx.isomorphism.is_isomorphic is fnx.is_isomorphic
    assert fnx.isomorphism.could_be_isomorphic is fnx.could_be_isomorphic


def test_submodule_backend_kwarg_surface_match_nx():
    """br-r37-c1-bk-submod: 3 fnx-native submodule overrides
    (approximation.treewidth_min_degree, bipartite.collaboration_
    weighted_projected_graph, community.label_propagation_
    communities) had bare signatures without ``*, backend=None,
    **backend_kwargs``.  These weren't reachable by the bulk
    wrapper because they live in submodule namespaces, not the
    main fnx globals.

    Lock signature parity + runtime backend handling for all 3."""
    import inspect

    P = fnx.path_graph(5)
    B = fnx.complete_bipartite_graph(2, 3)

    cases = [
        ("approximation", "treewidth_min_degree", (P,)),
        ("bipartite", "collaboration_weighted_projected_graph",
         (B, [0, 1])),
        ("community", "label_propagation_communities", (P,)),
    ]

    for path, name, args in cases:
        fn = getattr(getattr(fnx, path), name)
        sig = inspect.signature(fn)
        assert "backend" in sig.parameters, (
            f"fnx.{path}.{name} missing backend kwarg"
        )

        # backend=None passes through
        result = fn(*args, backend=None)
        if path == "community":
            list(result)  # consume generator

        # bogus backend → ImportError
        with pytest.raises(ImportError):
            result = fn(*args, backend="bogus_backend")
            if path == "community":
                list(result)


def test_contracted_nodes_v_not_in_graph_raises_match_nx():
    """br-r37-c1-cnodes-vbad: contracted_nodes / identified_nodes
    silently returned the unmodified graph when ``v`` was not in G,
    masking nx's NetworkXError contract.  nx accesses ``H.nodes[v]``
    explicitly and raises ``NetworkXError("Node {v} is not in the
    graph.")``.

    fnx had a defensive ``if v in G else {}`` guard that silently
    used an empty dict when v was missing, then proceeded to skip
    the contraction entirely.

    nx intentionally permits ``u not in G`` (the bad u becomes a
    real node implicitly via ``add_edge`` during remap).  Lock
    the v-bad raise + valid args regression."""
    P = fnx.path_graph(3)

    # v-bad → NetworkXError matching nx
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        fnx.contracted_nodes(P, 0, 99)
    with pytest.raises(nx.NetworkXError, match=r"Node 100 is not in the graph"):
        fnx.contracted_nodes(P, 99, 100)
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        fnx.identified_nodes(P, 0, 99)

    # u-bad with v-good is permitted (the bad u becomes a node
    # implicitly during the remap)
    H = fnx.contracted_nodes(P, 99, 1)
    assert H.number_of_nodes() == 3
    assert 99 in H.nodes()  # bad u became a real node

    # Valid: regression
    H = fnx.contracted_nodes(P, 0, 2)
    assert H.number_of_nodes() == 2


def test_quotient_graph_partition_validation_match_nx():
    """br-r37-c1-quot-validate: quotient_graph silently accepted
    invalid partitions:
      * parts containing nodes not in G — silently created
        quotient nodes from foreign labels
      * overlapping parts (a node-of-G in two blocks) — silently
        merged the parts
      * duplicate parts (same singleton listed twice) — silently
        merged

    nx raises ``NetworkXException("each node must be in exactly
    one part of \`partition\`")`` for all three cases.

    Lock the validation contract while preserving the documented
    asymmetry (missing nodes — in G but not in partition — are
    silently excluded from the quotient)."""
    P = fnx.path_graph(5)
    msg = r"each node must be in exactly one part of"

    # Bad cases: foreign nodes / overlap / duplicate
    bad_cases = [
        [{99}],                    # bad-only
        [{0, 99}],                 # bad-mixed
        [{0, 1}, {1, 2}],          # overlap
        [{0}, {0}],                # duplicate
    ]
    for partition in bad_cases:
        with pytest.raises(nx.NetworkXException, match=msg):
            fnx.quotient_graph(P, partition, relabel=False)

    # OK cases: missing nodes (silently excluded), empty parts
    H = fnx.quotient_graph(P, [{0, 1}, {2}], relabel=False)
    assert H.number_of_nodes() == 2  # nodes 3, 4 silently excluded

    H = fnx.quotient_graph(P, [{0, 1, 2}, set(), {3, 4}], relabel=False)
    assert H.number_of_nodes() == 3  # empty part allowed

    # Valid: regression
    H = fnx.quotient_graph(P, [{0, 1}, {2}, {3, 4}], relabel=False)
    assert H.number_of_nodes() == 3
    assert H.number_of_edges() == 2


def test_reconstruct_path_bad_node_raises_keyerror_match_nx():
    """br-r37-c1-recon-keyerr: reconstruct_path with floyd-warshall-
    style predecessors leaked weird errors on bad source/target:

      * bad source: ``TypeError: unhashable type: 'dict'`` because
        the dijkstra fallback walked through the floyd-warshall
        sub-dicts and used a dict as a key in get()
      * bad target: silently returned ``[]`` instead of raising

    nx raises ``KeyError(node)`` for both cases.  Lock the typed-
    error contract."""
    G = fnx.complete_graph(4)
    preds, _ = fnx.floyd_warshall_predecessor_and_distance(G)

    # Bad source/target → KeyError matching nx
    with pytest.raises(KeyError):
        fnx.reconstruct_path(99, 0, preds)
    with pytest.raises(KeyError):
        fnx.reconstruct_path(0, 99, preds)
    with pytest.raises(KeyError):
        fnx.reconstruct_path(99, 100, preds)

    # Same node still returns empty list (no path needed)
    assert fnx.reconstruct_path(0, 0, preds) == []

    # Valid: regression
    path = fnx.reconstruct_path(0, 2, preds)
    assert path == [0, 2]


def test_average_shortest_path_length_floyd_warshall_methods_match_nx():
    """br-r37-c1-aspl-fw: average_shortest_path_length rejected
    ``method='floyd-warshall'`` and ``method='floyd-warshall-numpy'``
    with ValueError; nx accepts both via its standard dispatch.
    Lock acceptance + value parity for both new methods + the
    existing methods + bogus rejection."""
    P = fnx.path_graph(5)
    nP = nx.path_graph(5)

    # Floyd-Warshall variants now match nx
    for method in ("floyd-warshall", "floyd-warshall-numpy"):
        assert fnx.average_shortest_path_length(P, method=method) == \
               nx.average_shortest_path_length(nP, method=method)

    # Weighted FW path
    Gf = fnx.Graph([(0, 1, {"w": 5}), (1, 2, {"w": 3})])
    Gn = nx.Graph([(0, 1, {"w": 5}), (1, 2, {"w": 3})])
    for method in ("floyd-warshall", "floyd-warshall-numpy"):
        f_val = fnx.average_shortest_path_length(Gf, weight="w", method=method)
        n_val = nx.average_shortest_path_length(Gn, weight="w", method=method)
        assert abs(f_val - n_val) < 1e-9

    # Other methods still work (regression)
    for method in (None, "unweighted", "dijkstra", "bellman-ford"):
        assert fnx.average_shortest_path_length(P, method=method) == 2.0

    # Bogus method still rejected
    with pytest.raises(ValueError, match=r"method not supported: bogus"):
        fnx.average_shortest_path_length(P, method="bogus")


def test_residual_graph_edit_distance_and_reverse_backend_kwarg():
    """br-r37-c1-bk-residue: 2 dispatchable APIs slipped past the
    bulk2/bulk3/bulk4 audits.  Lock signature parity + runtime
    acceptance for the residual cleanup."""
    import inspect

    # graph_edit_distance — has its own internal kwargs but missed
    # the explicit backend / backend_kwargs surface.
    sig = inspect.signature(fnx.graph_edit_distance)
    assert "backend" in sig.parameters
    fnx.graph_edit_distance(fnx.path_graph(3), fnx.path_graph(3), backend=None)

    # reverse — DiGraph reverse operation.
    sig = inspect.signature(fnx.reverse)
    assert "backend" in sig.parameters
    fnx.reverse(fnx.DiGraph([(0, 1)]), backend=None)

    # Bogus backend rejected
    with pytest.raises(ImportError):
        fnx.graph_edit_distance(fnx.path_graph(3), fnx.path_graph(3),
                                backend="bogus_backend")


def test_matrix_family_backend_kwarg_match_nx():
    """br-r37-c1-bk-matrix: 17 matrix / spectrum functions missed
    the backend dispatch surface — first batch of the multi-tick
    br-r37-c1-xc9no epic.  Lock signature parity for all 17."""
    import inspect
    targets = [
        "adjacency_matrix", "adjacency_spectrum",
        "attr_matrix", "attr_sparse_matrix",
        "bethe_hessian_matrix", "bethe_hessian_spectrum",
        "directed_combinatorial_laplacian_matrix",
        "directed_laplacian_matrix", "directed_modularity_matrix",
        "google_matrix", "incidence_matrix",
        "laplacian_matrix", "laplacian_spectrum",
        "modularity_matrix", "modularity_spectrum",
        "normalized_laplacian_matrix", "normalized_laplacian_spectrum",
    ]
    for name in targets:
        sig = inspect.signature(getattr(fnx, name))
        assert "backend" in sig.parameters, f"fnx.{name} missing backend"

    # Functional spot-check on a sample
    P = fnx.path_graph(4)
    fnx.adjacency_matrix(P, backend=None)
    fnx.adjacency_spectrum(P, backend=None)
    fnx.laplacian_matrix(P, backend=None)
    fnx.laplacian_spectrum(P, backend=None)
    fnx.modularity_matrix(P, backend=None)
    fnx.google_matrix(P, backend=None)
    fnx.incidence_matrix(P, backend=None)
    fnx.attr_matrix(P, backend=None)

    # Bogus backend rejected
    with pytest.raises(ImportError):
        fnx.adjacency_matrix(P, backend="bogus_backend")


def test_algo_variant_family_backend_kwarg_match_nx():
    """br-r37-c1-bk-algo: 128 algorithm-variant functions missing
    the backend dispatch surface — batch 2/5 of the
    br-r37-c1-xc9no epic.  Lock signature parity for a
    representative sample."""
    import inspect
    sample = [
        "all_triangles", "bidirectional_dijkstra", "chain_decomposition",
        "contracted_nodes", "contracted_edge", "convert_node_labels_to_integers",
        "dfs_edges", "dfs_predecessors", "dijkstra_predecessor_and_distance",
        "find_cliques", "find_negative_cycle",
        "floyd_warshall_numpy", "floyd_warshall_predecessor_and_distance",
        "from_prufer_sequence", "get_edge_attributes", "get_node_attributes",
        "is_bipartite", "is_empty", "is_k_edge_connected", "is_weighted",
        "k_edge_augmentation", "k_components",
        "max_weight_clique", "maximal_independent_set", "min_edge_cover",
        "node_clique_number", "node_disjoint_paths",
        "number_of_selfloops", "number_strongly_connected_components",
        "optimal_edit_paths", "predecessor", "reconstruct_path",
        "relabel_nodes", "set_edge_attributes", "set_node_attributes",
        "single_source_shortest_path_length",
        "to_prufer_sequence", "triadic_census",
        "vf2pp_is_isomorphic", "weisfeiler_lehman_subgraph_hashes",
    ]
    for name in sample:
        sig = inspect.signature(getattr(fnx, name))
        assert "backend" in sig.parameters, f"fnx.{name} missing backend"

    # Functional spot-check
    P = fnx.path_graph(5)
    K3 = fnx.complete_graph(3)
    fnx.bidirectional_dijkstra(P, 0, 4, backend=None)
    list(fnx.dfs_edges(P, 0, backend=None))
    fnx.is_bipartite(P, backend=None)
    fnx.is_weighted(P, backend=None)
    list(fnx.find_cliques(P, backend=None))
    fnx.contracted_nodes(P, 0, 1, backend=None)
    fnx.relabel_nodes(P, {0: 99}, backend=None)
    fnx.vf2pp_is_isomorphic(K3, K3, backend=None)

    # Bogus backend rejected
    with pytest.raises(ImportError):
        fnx.is_bipartite(P, backend="bogus_backend")


def test_full_dispatch_surface_parity_with_nx():
    """br-r37-c1-bk-final: closes the multi-tick br-r37-c1-xc9no
    epic by adding backend dispatch surface to the remaining 176
    functions across generators, IO, conversions, and predicates.

    Lock that ZERO top-level fnx-vs-nx function signatures diverge
    on the backend kwarg axis.  Any future addition that drops this
    parity will trip this lock."""
    import inspect
    import types

    mismatches = []
    for name in dir(nx):
        if name.startswith("_"):
            continue
        n_obj = getattr(nx, name, None)
        f_obj = getattr(fnx, name, None)
        if n_obj is None or f_obj is None:
            continue
        if not (inspect.isfunction(n_obj)
                or isinstance(n_obj, types.BuiltinFunctionType)):
            continue
        try:
            sn = inspect.signature(n_obj)
            sf = inspect.signature(f_obj)
        except (TypeError, ValueError):
            continue
        if "backend" in sn.parameters and "backend" not in sf.parameters:
            mismatches.append(name)

    assert mismatches == [], (
        f"{len(mismatches)} functions still missing backend kwarg: "
        f"{mismatches[:10]}"
    )


def test_generate_random_paths_empty_graph_raises_match_nx():
    """br-r37-c1-grp-empty: generate_random_paths on an empty graph
    silently returned ``[]`` instead of raising nx's
    ValueError("high <= 0") which leaks from the internal
    ``randint(0, len(nodes)-1)`` call.

    Lock the leaky-but-stable nx contract."""
    with pytest.raises(ValueError, match="high <= 0"):
        list(fnx.generate_random_paths(fnx.Graph(), 5, seed=42))

    # Regression: non-empty graphs work
    result = list(fnx.generate_random_paths(fnx.path_graph(5), 3, 3, seed=42))
    assert len(result) == 3


def test_edge_node_disjoint_paths_input_validation_match_nx():
    """br-r37-c1-edp-validate: edge_disjoint_paths and
    node_disjoint_paths silently yielded an empty generator on bad
    inputs (missing source/target node, or same source-sink for
    edge variant).  nx raises typed NetworkXError.  Lock the
    contract for both functions."""
    P = fnx.path_graph(5)

    # edge_disjoint_paths — full validation
    with pytest.raises(nx.NetworkXError, match=r"source and sink are the same node"):
        list(fnx.edge_disjoint_paths(P, 0, 0))
    with pytest.raises(nx.NetworkXError, match=r"node 99 not in graph"):
        list(fnx.edge_disjoint_paths(P, 99, 0))
    with pytest.raises(nx.NetworkXError, match=r"node 99 not in graph"):
        list(fnx.edge_disjoint_paths(P, 0, 99))
    # Valid: regression
    assert list(fnx.edge_disjoint_paths(P, 0, 4)) == [[0, 1, 2, 3, 4]]

    # node_disjoint_paths — node validation only (same s=t leaves
    # to the underlying flow, which yields a degenerate path)
    with pytest.raises(nx.NetworkXError, match=r"node 99 not in graph"):
        list(fnx.node_disjoint_paths(P, 99, 0))
    with pytest.raises(nx.NetworkXError, match=r"node 99 not in graph"):
        list(fnx.node_disjoint_paths(P, 0, 99))
    # Valid: regression
    assert list(fnx.node_disjoint_paths(P, 0, 4)) == [[0, 1, 2, 3, 4]]


def test_gomory_hu_tree_unbounded_paths_raise_match_nx():
    """br-r37-c1-ght-disc: gomory_hu_tree silently produced
    meaningless trees when:
      * the graph was disconnected (cross-component min-cut is
        mathematically infinite)
      * any edge had infinite (default-missing) capacity (any
        flow path becomes unbounded)

    nx raises ``NetworkXUnbounded("Infinite capacity path, flow
    unbounded above.")`` for both cases.  fnx called the Rust
    min-cut binding directly, which didn't propagate the
    unbounded error.  Lock both contracts."""
    msg = "Infinite capacity path"

    # Disconnected
    with pytest.raises(nx.NetworkXUnbounded, match=msg):
        fnx.gomory_hu_tree(fnx.Graph([(0, 1), (2, 3)]))

    # Connected but no capacity attr (default is infinite)
    with pytest.raises(nx.NetworkXUnbounded, match=msg):
        fnx.gomory_hu_tree(fnx.complete_graph(4))

    # Valid: regression with finite capacities
    G = fnx.Graph([(0, 1, {"capacity": 5}),
                   (1, 2, {"capacity": 3}),
                   (0, 2, {"capacity": 4})])
    T = fnx.gomory_hu_tree(G)
    assert T.number_of_edges() == 2

    # Empty / 1-node still raise their own typed errors
    with pytest.raises(nx.NetworkXError, match="Empty Graph"):
        fnx.gomory_hu_tree(fnx.Graph())


def test_geometric_generators_dim_le_zero_raise_match_nx():
    """br-r37-c1-rgg-dim0: 4 geometric generators silently produced
    complete (n*(n-1)/2-edge) graphs when ``dim <= 0`` because the
    position-sampling loop ran zero iterations and all pairs ended
    up at distance 0.  nx leaks IndexError (3 generators) or
    ZeroDivisionError (geographical_threshold_graph) from internal
    numpy / power operations.

    Lock the leaky-but-stable nx contract for all 4 generators."""
    # IndexError-leaking generators
    for fn_factory, args in [
        (lambda dim: fnx.random_geometric_graph(5, 0.5, dim=dim, seed=42), None),
        (lambda dim: fnx.soft_random_geometric_graph(5, 0.5, dim=dim, seed=42), None),
        (lambda dim: fnx.thresholded_random_geometric_graph(5, 0.5, 0.3, dim=dim, seed=42), None),
    ]:
        with pytest.raises(IndexError, match="Out of bounds"):
            fn_factory(0)
        with pytest.raises(IndexError, match="Out of bounds"):
            fn_factory(-1)

    # ZeroDivisionError-leaking generator
    with pytest.raises(ZeroDivisionError):
        fnx.geographical_threshold_graph(5, 0.3, dim=0, seed=42)
    with pytest.raises(ZeroDivisionError):
        fnx.geographical_threshold_graph(5, 0.3, dim=-1, seed=42)

    # Valid dim still works (regression)
    assert fnx.random_geometric_graph(5, 0.5, dim=2, seed=42).number_of_nodes() == 5
    assert fnx.geographical_threshold_graph(5, 0.3, dim=2, seed=42).number_of_nodes() == 5


def test_connected_watts_strogatz_bad_tries_match_nx():
    """br-r37-c1-cws-tries: connected_watts_strogatz_graph leaked
    Rust internal error formats on bad ``tries`` values:
      * tries=0: ``ValueError(FailClosed { operation: ..., reason:
        ... })`` — the Rust FailClosed wrapper format
      * tries<0: ``OverflowError("can't convert negative int to
        unsigned")`` — from the unsigned PyO3 signature

    nx raises ``NetworkXError("Maximum number of tries exceeded")``
    for both.  Lock parity."""
    msg = "Maximum number of tries exceeded"

    with pytest.raises(nx.NetworkXError, match=msg):
        fnx.connected_watts_strogatz_graph(5, 2, 0.1, tries=0, seed=42)
    with pytest.raises(nx.NetworkXError, match=msg):
        fnx.connected_watts_strogatz_graph(5, 2, 0.1, tries=-1, seed=42)
    with pytest.raises(nx.NetworkXError, match=msg):
        fnx.connected_watts_strogatz_graph(5, 2, 0.1, tries=-100, seed=42)

    # Valid tries still work
    G = fnx.connected_watts_strogatz_graph(5, 2, 0.1, tries=100, seed=42)
    assert G.number_of_nodes() == 5
    G = fnx.connected_watts_strogatz_graph(5, 2, 0.1, tries=1, seed=42)
    assert G.number_of_nodes() == 5


def test_newman_watts_strogatz_pathological_p_match_nx():
    """br-r37-c1-nws-pnan: newman_watts_strogatz_graph leaked Rust
    ``ValueError(FailClosed { ... })`` for p values nx silently
    accepts: NaN, inf, p<0, p>1.  nx's natural ``random() < p``
    flip handles all of these as graceful extremes (NaN → no
    rewiring, inf → full rewiring, etc.).  Lock parity for the
    pathological-p edge cases."""
    cases = [
        (float("nan"), 5),    # NaN → no rewiring (5 edges from base ring)
        (float("inf"), 10),   # inf → full rewiring (all edges added)
        (-1.0, 5),            # p<0 → no rewiring
        (2.0, 10),            # p>1 → full rewiring
        (0.0, 5),              # p=0 → no rewiring
        (1.0, 10),             # p=1 → full rewiring
    ]
    for p, expected_edges in cases:
        G = fnx.newman_watts_strogatz_graph(5, 2, p, seed=42)
        assert G.number_of_edges() == expected_edges, (
            f"p={p}: expected {expected_edges} edges, got {G.number_of_edges()}"
        )

    # Valid in-range still works
    G = fnx.newman_watts_strogatz_graph(5, 2, 0.5, seed=42)
    assert G.number_of_edges() == 8


def test_fast_gnp_random_graph_nan_p_raises_match_nx():
    """br-r37-c1-fgnp-pnan: fast_gnp_random_graph silently returned
    0 edges on p=NaN; nx leaks
    ``ValueError("cannot convert float NaN to integer")`` from its
    internal ``int(log(1-p)/...)`` computation.

    Note: the asymmetry with gnp_random_graph is intentional —
    gnp's slower Erdős-Rényi path accepts NaN silently
    (random.random() < NaN evaluates False → no edges).  Only the
    fast O(n+m) Batagelj-Brandes path's int conversion raises."""
    msg = "cannot convert float NaN to integer"
    with pytest.raises(ValueError, match=msg):
        fnx.fast_gnp_random_graph(5, float("nan"), seed=42)
    with pytest.raises(ValueError, match=msg):
        fnx.fast_gnp_random_graph(5, float("nan"), seed=42, directed=True)

    # Other pathological p values still pass through to silent
    # extremes (matching nx)
    assert fnx.fast_gnp_random_graph(5, float("inf"), seed=42).number_of_edges() == 10
    assert fnx.fast_gnp_random_graph(5, -1.0, seed=42).number_of_edges() == 0
    assert fnx.fast_gnp_random_graph(5, 2.0, seed=42).number_of_edges() == 10

    # Valid: regression
    assert fnx.fast_gnp_random_graph(5, 0.5, seed=42).number_of_edges() == 6


def test_random_planted_partition_p_validation_match_nx():
    """br-r37-c1-rpg-validate: random_partition_graph and
    planted_partition_graph routed straight to stochastic_block_
    model whose matrix-level validation produced a generic
    "Entries of 'p' not in [0,1]." message.  AND silently accepted
    NaN by short-circuiting on the matrix construction.

    nx validates p_in / p_out separately with axis-specific
    messages ("p_in must be in [0,1]" / "p_out must be in [0,1]")
    BEFORE building the matrix.  Lock the per-axis validation."""
    bad_p_cases = [
        (float("nan"), 0.1, "p_in"),
        (0.5, float("nan"), "p_out"),
        (-1, 0.1, "p_in"),
        (0.5, 2.0, "p_out"),
        (2.0, 0.1, "p_in"),
    ]
    for p_in, p_out, axis in bad_p_cases:
        match = f"{axis} must be in"
        with pytest.raises(nx.NetworkXError, match=match):
            fnx.random_partition_graph([3, 2], p_in, p_out, seed=42)
        with pytest.raises(nx.NetworkXError, match=match):
            fnx.planted_partition_graph(2, 3, p_in, p_out, seed=42)

    # Valid: regression
    G = fnx.random_partition_graph([3, 2], 0.5, 0.1, seed=42)
    assert G.number_of_nodes() == 5
    G = fnx.planted_partition_graph(2, 3, 0.5, 0.1, seed=42)
    assert G.number_of_nodes() == 6


def test_powerlaw_cluster_graph_nan_p_match_nx():
    """br-r37-c1-pcg-pnan: powerlaw_cluster_graph leaked Rust
    ``ValueError(FailClosed { ..., reason: "p is NaN" })`` for
    p=NaN.  nx accepts NaN silently — its weighted flip
    ``random.random() < p`` evaluates False, so triangle-closure
    never fires and the base preferential-attachment graph is
    returned.  Same defect family as br-r37-c1-r3ct1
    (newman_watts_strogatz NaN).  Lock parity."""
    G = fnx.powerlaw_cluster_graph(5, 2, float("nan"), seed=42)
    nG = nx.powerlaw_cluster_graph(5, 2, float("nan"), seed=42)
    assert G.number_of_edges() == nG.number_of_edges() == 6

    # Out-of-range p still raises with nx's exact message
    for bad_p in (float("inf"), -1.0, 2.0):
        with pytest.raises(nx.NetworkXError, match=r"p must be in \[0,1\]"):
            fnx.powerlaw_cluster_graph(5, 2, bad_p, seed=42)

    # Valid p regression
    assert fnx.powerlaw_cluster_graph(5, 2, 0.5, seed=42).number_of_edges() == 6


def test_random_tree_n_zero_raises_pointless_match_nx():
    """br-r37-c1-rut-zero: random_unlabeled_tree(n=0) and
    random_labeled_rooted_tree(n=0) silently returned an empty
    Graph by delegating to random_tree's defensive ``n <= 0:
    return Graph()`` short-circuit.  nx raises
    ``NetworkXPointlessConcept("the null graph is not a tree")``.

    Lock parity for both functions; preserve the existing
    correct behavior of random_labeled_tree (which already
    validates n=0) and random_unlabeled_rooted_tree."""
    msg = "the null graph is not a tree"

    # Now-fixed functions
    with pytest.raises(nx.NetworkXPointlessConcept, match=msg):
        fnx.random_unlabeled_tree(0, seed=42)
    with pytest.raises(nx.NetworkXPointlessConcept, match=msg):
        fnx.random_labeled_rooted_tree(0, seed=42)

    # Already-correct (regression check)
    with pytest.raises(nx.NetworkXPointlessConcept, match=msg):
        fnx.random_labeled_tree(0, seed=42)
    with pytest.raises(nx.NetworkXPointlessConcept, match=msg):
        fnx.random_unlabeled_rooted_tree(0, seed=42)

    # Valid n still produces correct trees
    assert fnx.random_unlabeled_tree(5, seed=42).number_of_nodes() == 5
    assert fnx.random_labeled_rooted_tree(5, seed=42).number_of_nodes() == 5
    assert len(fnx.random_unlabeled_tree(5, number_of_trees=3, seed=42)) == 3


def test_spanner_input_validation_match_nx():
    """br-r37-c1-spnr-validate: spanner had two silent-no-op
    failure modes:
      * empty graph: silently returned empty Graph; nx raises
        ValueError("math domain error") from internal log(0)
      * multigraph: silently produced a regular Graph; nx raises
        NetworkXNotImplemented

    nx validates stretch FIRST regardless of graph contents
    (returns "stretch must be at least 1" even on empty graph
    with stretch=0).  Lock validation order + parity."""
    # Stretch validation fires first
    with pytest.raises(ValueError, match=r"stretch must be at least 1"):
        fnx.spanner(fnx.Graph(), 0)
    with pytest.raises(ValueError, match=r"stretch must be at least 1"):
        fnx.spanner(fnx.path_graph(5), -1)

    # Multigraph rejected with nx-matching error
    with pytest.raises(nx.NetworkXNotImplemented,
                       match=r"not implemented for multigraph type"):
        fnx.spanner(fnx.MultiGraph([(0, 1), (0, 1)]), 2)

    # Empty graph + valid stretch → math domain error
    with pytest.raises(ValueError, match=r"math domain error"):
        fnx.spanner(fnx.Graph(), 2)

    # Valid: regression
    G = fnx.spanner(fnx.path_graph(5), 2)
    assert G.number_of_edges() == 4


def test_lfr_benchmark_graph_raises_exceeded_max_iterations_match_nx():
    """br-r37-c1-lfr-emi: LFR_benchmark_graph raised
    ``NetworkXError`` on convergence failure; nx raises
    ``ExceededMaxIterations`` (a sibling of NetworkXError under
    NetworkXException, NOT a subclass).  Callers using
    ``except ExceededMaxIterations:`` to specifically catch
    convergence failures couldn't catch fnx's NetworkXError.

    Lock the typed-error contract."""
    # ExceededMaxIterations is NOT a subclass of NetworkXError
    assert not issubclass(nx.ExceededMaxIterations, nx.NetworkXError)
    assert issubclass(nx.ExceededMaxIterations, nx.NetworkXException)

    # Hard-convergence config (n=20 small + average_degree=5 forces
    # the community-assignment loop to fail)
    with pytest.raises(nx.ExceededMaxIterations,
                       match=r"Could not assign communities"):
        fnx.LFR_benchmark_graph(20, 3.0, 1.5, 0.1, average_degree=5, seed=42)

    # Valid-config regression
    G = fnx.LFR_benchmark_graph(50, 3.0, 1.5, 0.1, average_degree=5, seed=42)
    assert G.number_of_nodes() == 50


def test_eulerian_path_bad_source_match_nx():
    """br-r37-c1-eulpath-src-bad: eulerian_path raised
    ``NodeNotFound`` (subclass of NetworkXException, NOT
    NetworkXError) on a missing source; nx raises plain
    ``NetworkXError("Node {n} is not in the graph.")``.
    Sibling eulerian_circuit already used NetworkXError
    correctly — eulerian_path was the gap.

    Lock the typed-error contract for the Eulerian-graph case
    (cycle_graph(3)).  Note: non-Eulerian graphs (e.g.
    path_graph(3)) trigger a different internal path in nx that
    leaks ``KeyError`` — fnx's wrapper validation now raises a
    cleaner ``NetworkXError`` regardless, which is more
    consistent than nx's contract here."""
    cycle = fnx.cycle_graph(3)

    # Bad source on Eulerian graph → NetworkXError matching nx
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        list(fnx.eulerian_path(cycle, source=99))

    # Bad source on directed Eulerian graph also matches
    DG = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        list(fnx.eulerian_path(DG, source=99))

    # Valid source still works (regression)
    assert list(fnx.eulerian_path(cycle, source=0)) == [(0, 1), (1, 2), (2, 0)]
    assert list(fnx.eulerian_path(cycle)) == [(0, 1), (1, 2), (2, 0)]


def test_predecessor_directed_match_nx():
    """br-r37-c1-pred-dir: ``predecessor`` (shortest-path BFS
    predecessor map) raised ``NetworkXNotImplemented`` on directed
    graphs because the Rust binding rejected directed inputs.  nx
    supports directed graphs and returns the BFS predecessor map
    on outgoing edges.  The wrapper now routes directed graphs to
    nx for parity and also normalizes the bad-source error to
    ``Source {source} not in G`` (the Rust binding emitted
    ``Source '99' is not in G`` with quoted repr)."""
    DG = fnx.DiGraph([(0, 1), (1, 2)])
    assert fnx.predecessor(DG, 0) == {0: [], 1: [0], 2: [1]}
    # cycle digraph — BFS only follows outgoing edges from source
    DGc = fnx.DiGraph([(0, 1), (1, 0)])
    assert fnx.predecessor(DGc, 0) == {0: [], 1: [0]}
    # target= path-list form
    assert fnx.predecessor(DG, 0, target=2) == [1]
    # cutoff truncates
    DG3 = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    assert fnx.predecessor(DG3, 0, cutoff=1) == {0: [], 1: [0]}
    # return_seen=True
    pmap, seen = fnx.predecessor(DG, 0, return_seen=True)
    assert pmap == {0: [], 1: [0], 2: [1]}
    assert seen == {0: 0, 1: 1, 2: 2}
    # bad target with return_seen → ([], -1) sentinel
    assert fnx.predecessor(DG, 0, target=99, return_seen=True) == ([], -1)
    # Bad source raises NodeNotFound with nx-shaped message on
    # both directed and undirected
    with pytest.raises(nx.NodeNotFound, match=r"Source 99 not in G"):
        fnx.predecessor(fnx.path_graph(3), 99)
    with pytest.raises(nx.NodeNotFound, match=r"Source 99 not in G"):
        fnx.predecessor(DG, 99)


def test_is_isolate_bad_node_match_nx():
    """br-r37-c1-isol-exc: ``is_isolate`` raised ``NodeNotFound``
    on a missing node because the Rust binding _raw_is_isolate
    used the wrong typed-error class.  ``NodeNotFound`` is a
    sibling of ``NetworkXError`` (both descend from
    ``NetworkXException``) — NOT a subclass — so callers
    following nx's contract with ``except NetworkXError:`` did
    not catch it.

    nx implements ``is_isolate(G, n)`` as ``G.degree(n) == 0``,
    so missing-node errors flow from the degree view as
    ``NetworkXError("Node {n} is not in the graph.")``.  fnx now
    mirrors that one-liner."""
    P = fnx.path_graph(3)
    DG = fnx.DiGraph([(0, 1)])
    MG = fnx.MultiGraph([(0, 1)])

    for G in (P, DG, MG):
        with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
            fnx.is_isolate(G, 99)

    # Valid regressions
    iso = fnx.path_graph(3)
    iso.add_node(7)
    assert fnx.is_isolate(iso, 7) is True
    assert fnx.is_isolate(iso, 1) is False

    # DiGraph: isolated node has neither in nor out neighbors
    DG2 = fnx.DiGraph([(0, 1)])
    DG2.add_node(8)
    assert fnx.is_isolate(DG2, 8) is True
    assert fnx.is_isolate(DG2, 0) is False
    assert fnx.is_isolate(DG2, 1) is False


def test_kcore_kshell_kcrust_empty_graph_raise_match_nx():
    """br-r37-c1-kcore-empty: ``k_core``, ``k_shell``, ``k_crust``
    on an empty graph with ``k=None`` previously silently coerced
    ``k`` to 0 and returned an empty subgraph view, masking the
    empty-input case.  nx's ``_core_subgraph`` does
    ``k = max(core.values())`` with no fallback, so empty input
    leaks ``ValueError("max() iterable argument is empty")``.

    fnx now matches: empty graph + k=None → ValueError. Empty
    graph + explicit k still returns the empty subgraph (both
    fnx and nx — that path doesn't compute max)."""
    for fn_name in ("k_core", "k_shell", "k_crust"):
        fn = getattr(fnx, fn_name)
        nx_fn = getattr(nx, fn_name)

        # Empty graph + k=None → ValueError (matches nx)
        with pytest.raises(ValueError, match=r"max\(\) iterable argument is empty"):
            fn(fnx.Graph())
        with pytest.raises(ValueError, match=r"max\(\) iterable argument is empty"):
            nx_fn(nx.Graph())

        # Empty graph + explicit k → empty subgraph (both libs)
        assert list(fn(fnx.Graph(), k=2).nodes()) == []
        assert list(nx_fn(nx.Graph(), k=2).nodes()) == []

    # Non-empty regressions
    P = fnx.path_graph(5)
    assert sorted(fnx.k_core(P).edges()) == [(0, 1), (1, 2), (2, 3), (3, 4)]
    K = fnx.karate_club_graph()
    Kx = nx.karate_club_graph()
    assert sorted(fnx.k_core(K).nodes()) == sorted(nx.k_core(Kx).nodes())


def test_k_crust_default_k_is_max_minus_one_match_nx():
    """br-r37-c1-qzdbg: ``k_crust`` with ``k=None`` is documented
    in nx as one less than _core_subgraph's default — explicit
    nx comment: "Default for k is one less than in
    _core_subgraph, so just inline."  fnx previously used
    ``max(core_number.values())`` (no -1), which returned the
    full graph as the "main crust" — wrong for every
    non-trivial input.

    Lock against re-introduction of the off-by-one."""
    # Karate-club golden: nx returns nodes with core_number<=3
    # (max=4), so the highest-core nodes (e.g. 0, 1, 2, 3, 7, 8,
    # 13, 30, 32, 33) are excluded.
    K = fnx.karate_club_graph()
    Kx = nx.karate_club_graph()
    fnx_crust = sorted(fnx.k_crust(K).nodes())
    nx_crust = sorted(nx.k_crust(Kx).nodes())
    assert fnx_crust == nx_crust
    # Sanity: not every node — some are excluded
    assert len(fnx_crust) < K.number_of_nodes()

    # Havel-Hakimi degree-sequence example from nx docstring
    H = fnx.havel_hakimi_graph([0, 1, 2, 2, 2, 2, 3])
    Hx = nx.havel_hakimi_graph([0, 1, 2, 2, 2, 2, 3])
    assert sorted(fnx.k_crust(H).nodes()) == sorted(nx.k_crust(Hx).nodes()) == [0, 4, 6]

    # Path/cycle: max core is 1 → main crust uses k=0 → empty
    assert list(fnx.k_crust(fnx.path_graph(5)).nodes()) == []
    assert list(fnx.k_crust(fnx.Graph([(0, 1)])).nodes()) == []
    assert list(fnx.k_crust(fnx.DiGraph([(0, 1), (1, 2), (2, 0)])).nodes()) == []

    # Explicit k still works (regression — these passed before)
    assert sorted(fnx.k_crust(K, k=2).nodes()) == sorted(nx.k_crust(Kx, k=2).nodes())


def test_union_type_mismatch_check_precedes_disjoint_check():
    """br-r37-c1-union-order: ``union(G, H)`` must check
    type-mismatch (directed-vs-undirected, graph-vs-multigraph)
    BEFORE the disjoint-nodes check.  Previously fnx checked
    disjoint-nodes first, so a Graph + DiGraph with overlapping
    node sets reported "node sets not disjoint" instead of the
    more fundamental "must be directed or undirected" — the
    disjoint check is meaningless when the graphs aren't even
    the same kind.

    Lock the order: type-mismatch errors must dominate
    disjoint-set errors when both apply."""
    G = fnx.path_graph(3)        # nodes 0,1,2
    DG = fnx.DiGraph([(0, 1)])   # nodes 0,1 — overlap with G
    MG = fnx.MultiGraph([(0, 1)])  # nodes 0,1 — overlap with G

    # Overlapping nodes + directed mismatch → directed message
    with pytest.raises(nx.NetworkXError,
                       match=r"All graphs must be directed or undirected"):
        fnx.union(G, DG)

    # Overlapping nodes + multigraph mismatch → multigraph message
    with pytest.raises(nx.NetworkXError,
                       match=r"All graphs must be graphs or multigraphs"):
        fnx.union(G, MG)

    # Disjoint nodes + type mismatch → type-mismatch still wins
    G_far = fnx.DiGraph([(10, 11)])  # disjoint from G
    with pytest.raises(nx.NetworkXError,
                       match=r"All graphs must be directed or undirected"):
        fnx.union(G, G_far)

    # Same type + overlap → disjoint-set error (regression)
    with pytest.raises(nx.NetworkXError,
                       match=r"node sets of the graphs are not disjoint"):
        fnx.union(G, fnx.path_graph(3))

    # Valid union of disjoint same-type still works
    G_a = fnx.path_graph(3)
    G_b = fnx.Graph([(10, 11), (11, 12)])
    out = fnx.union(G_a, G_b)
    assert sorted(out.edges()) == [(0, 1), (1, 2), (10, 11), (11, 12)]


def test_degree_assortativity_coefficient_edgeless_returns_nan():
    """br-r37-c1-asrt-edgeless: the Rust fast path returned
    ``0.0`` on graphs with no edges; nx returns ``nan``.

    ``0.0`` is a *meaningful* statistic ("no correlation") and
    silently coercing nan→0.0 erases the "input is undefined"
    signal.  nx's Pearson computation hits 0/0 on an empty
    mixing matrix and propagates ``nan``.

    Lock: edgeless graphs (empty / isolated-only) must return
    nan; non-degenerate graphs continue to return finite values.
    """
    import math

    # Empty graph
    f = fnx.degree_assortativity_coefficient(fnx.Graph())
    assert isinstance(f, float) and math.isnan(f)

    # Single isolated node
    G1 = fnx.Graph()
    G1.add_node(0)
    f = fnx.degree_assortativity_coefficient(G1)
    assert isinstance(f, float) and math.isnan(f)

    # Two isolated nodes, no edges
    G2 = fnx.Graph()
    G2.add_nodes_from([0, 1])
    f = fnx.degree_assortativity_coefficient(G2)
    assert isinstance(f, float) and math.isnan(f)

    # Non-degenerate regressions — finite values preserved
    P3 = fnx.path_graph(3)
    assert fnx.degree_assortativity_coefficient(P3) == -1.0
    star = fnx.star_graph(5)
    assert fnx.degree_assortativity_coefficient(star) == -1.0


def test_min_edge_cover_isolated_with_edges_match_nx():
    """br-r37-c1-mec-iso: ``min_edge_cover`` on a graph with
    BOTH edges and ≥1 isolated node leaked an uncaught
    ``StopIteration`` from ``next(iter(G.neighbors(v)))`` inside
    the post-matching uncovered-loop.  nx raises
    ``NetworkXException`` (not NetworkXError) the moment any
    node has degree 0, covering both this case and the pure
    "no edges with isolated nodes" case.

    Two contracts locked:
    1. The combined edges+isolated case must raise
       NetworkXException (not StopIteration).
    2. The pure no-edges case must also raise NetworkXException
       (previously fnx raised the narrower NetworkXError —
       mismatch with nx's documented class)."""
    # Edges-with-isolated: this leaked StopIteration before
    G = fnx.Graph([(1, 2)])
    G.add_node(0)
    with pytest.raises(nx.NetworkXException,
                       match=r"Graph has a node with no edge incident on it"):
        fnx.min_edge_cover(G)

    # Pure isolated: was raising NetworkXError (narrower)
    iso = fnx.Graph()
    iso.add_node("a")
    with pytest.raises(nx.NetworkXException,
                       match=r"Graph has a node with no edge incident on it"):
        fnx.min_edge_cover(iso)

    # Two isolated nodes
    iso2 = fnx.Graph()
    iso2.add_nodes_from([0, 1])
    with pytest.raises(nx.NetworkXException,
                       match=r"Graph has a node with no edge incident on it"):
        fnx.min_edge_cover(iso2)

    # Valid regressions: empty graph returns set(); fully-
    # covered graphs return correct cover.
    assert fnx.min_edge_cover(fnx.Graph()) == set()
    cover = fnx.min_edge_cover(fnx.path_graph(5))
    assert sorted(map(sorted, cover)) == [[0, 1], [1, 2], [3, 4]]


def test_graph_edges_single_bad_node_raises_match_nx():
    """br-r37-c1-edges-snnb: ``Graph.edges(nbunch=<single
    non-iterable hashable>)`` must raise NetworkXError when the
    node is not in the graph — distinct from the silent-skip
    contract for an iterable nbunch (e.g. ``edges([99])``
    returns ``[]``).  Sibling DiGraph and MultiGraph already
    raised correctly; only undirected Graph.edges silently
    returned ``[]``.

    The bug was that the wrapper unconditionally wrapped
    non-iterables into ``[nbunch]`` before iteration, losing
    the "this was a single specified node" signal that nx uses
    to decide whether to raise."""
    P = fnx.path_graph(3)

    # Single non-iterable bad node → NetworkXError (matches nx)
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        list(P.edges(nbunch=99))

    # Iterable with bad node still silently skips
    assert list(P.edges(nbunch=[99])) == []
    assert list(P.edges(nbunch=(99,))) == []
    assert list(P.edges(nbunch={99})) == []

    # Single good non-iterable still works
    assert list(P.edges(nbunch=1)) == [(1, 0), (1, 2)]

    # Mixed list — silently skips bad, includes good
    assert sorted(P.edges(nbunch=[0, 99, 2])) == [(0, 1), (2, 1)]

    # data=True / data="attr" must still raise on single bad node
    G_attr = fnx.Graph([(0, 1, {"w": 5})])
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        list(G_attr.edges(nbunch=99, data=True))
    with pytest.raises(nx.NetworkXError, match=r"Node 99 is not in the graph"):
        list(G_attr.edges(nbunch=99, data="w"))

    # String nbunch — fnx ergonomic enhancement preserves the
    # "treat string as a single node name" handling.  When the
    # string IS a node, return its edges.  When it ISN'T, both
    # nx (which iterates chars and finds none) and fnx (which
    # falls through silent-skip) return [] — match preserved.
    G_str = fnx.Graph()
    G_str.add_edge("foo", "bar")
    assert list(G_str.edges("foo")) == [("foo", "bar")]
    assert list(P.edges("missing")) == []


def test_minimum_maximum_spanning_edges_are_true_generators():
    """br-r37-c1-mse-gen: ``minimum_spanning_edges`` and
    ``maximum_spanning_edges`` returned a ``list_iterator`` from
    the Rust kruskal fast path while nx returns a true
    ``generator``.  Callers introspecting the return type
    (``isinstance(result, types.GeneratorType)``,
    ``inspect.isgenerator``) saw drop-in failures.

    Both wrappers are now generator functions (yield from)
    so the return type is normalised to ``generator`` across
    every code path (Rust kruskal default, weighted delegate,
    prim, boruvka)."""
    import types
    import inspect

    P = fnx.path_graph(5)
    W = fnx.Graph([(0, 1, {"weight": 2}),
                   (1, 2, {"weight": 3}),
                   (2, 3, {"weight": 1})])

    for fn in (fnx.minimum_spanning_edges, fnx.maximum_spanning_edges):
        # Rust kruskal default
        r = fn(P)
        assert isinstance(r, types.GeneratorType), \
            f"{fn.__name__} default kruskal not a generator: {type(r).__name__}"
        assert inspect.isgenerator(r)

        # Weighted delegate path
        r = fn(W, weight="weight")
        assert isinstance(r, types.GeneratorType)

        # Prim / Boruvka delegate paths
        for algo in ("prim", "boruvka"):
            r = fn(P, algorithm=algo)
            assert isinstance(r, types.GeneratorType)

    # Content regression: weighted MST edges still correct
    edges = sorted((u, v) for u, v, d in fnx.minimum_spanning_edges(W, data=True))
    assert edges == [(0, 1), (1, 2), (2, 3)]

    # Empty data pass-through
    assert list(fnx.minimum_spanning_edges(P, data=False)) == [
        (0, 1), (1, 2), (2, 3), (3, 4)
    ]


def test_bfs_layers_is_true_generator():
    """br-r37-c1-bfsl-gen: ``bfs_layers`` returned a
    ``list_iterator`` from the Rust raw binding while nx returns
    a true ``generator``.  Same family as br-r37-c1-i4d5n
    (spanning_edges) and br-r37-c1-lby4x (isolates) — Rust
    bindings eagerly materialise lists; the Python wrapper must
    ``yield from`` to expose the generator-protocol contract.

    Lock both: isinstance(GeneratorType) must hold and nx's
    lazy-validation timing (raise on iteration, not on call) is
    preserved."""
    import types
    import inspect

    P = fnx.path_graph(5)

    # Single-source good
    r = fnx.bfs_layers(P, 0)
    assert isinstance(r, types.GeneratorType)
    assert inspect.isgenerator(r)
    assert list(r) == [[0], [1], [2], [3], [4]]

    # List-source good
    r = fnx.bfs_layers(P, [0, 2])
    assert isinstance(r, types.GeneratorType)
    assert list(r) == [[0, 2], [1, 3], [4]]

    # Bad list source — generator returned on call, raises on
    # iteration (matches nx)
    r = fnx.bfs_layers(P, [99])
    assert isinstance(r, types.GeneratorType)
    with pytest.raises(nx.NetworkXError, match=r"The node 99 is not in the graph"):
        list(r)

    # Single bad non-iterable — generator returned, raises on
    # iteration with TypeError (nx contract)
    r = fnx.bfs_layers(P, 99)
    assert isinstance(r, types.GeneratorType)
    with pytest.raises(TypeError, match=r"'int' object is not iterable"):
        list(r)


def test_parse_gml_error_message_format_matches_nx():
    """br-r37-c1-gml-msg: nx's parse_gml uses a uniform error
    template ``f"{category} #{i} has no {attr!r} attribute"``
    (e.g. ``node #0 has no 'label' attribute``).  The Rust GML
    reader emitted ``gml node {id} missing label`` and a few
    other ad-hoc variants — same NetworkXError class but
    different message text, so drop-in callers using
    ``pytest.raises(NetworkXError, match=r"has no 'label'
    attribute")`` failed.

    Lock the actionable substring ``has no '<attr>' attribute``
    across all five sibling violations.  The numeric index
    cannot be perfectly recovered from the Rust error (it
    carries the node-id, not the list-position), so the
    template is best-effort: ``#{id}`` for label-missing,
    ``#?`` for the others.  Pattern-matching tests should rely
    on the trailing ``has no '<attr>' attribute`` portion."""
    cases = [
        ('graph [\n  node [id 100]\n]',
         "label"),
        ('graph [\n  node [id 0 label "a"]\n  edge [target 0]\n]',
         "source"),
        ('graph [\n  node [id 0 label "a"]\n  edge [source 0]\n]',
         "target"),
        ('graph [\n  node [label "a"]\n]',
         "id"),
        ('graph [\n  node [id 0 label "a"]\n  edge []\n]',
         "source"),
    ]
    for gml, attr in cases:
        with pytest.raises(nx.NetworkXError,
                           match=fr"has no '{attr}' attribute"):
            fnx.parse_gml(gml)

    # Successful parse still works (regression)
    G = fnx.parse_gml('graph [\n  node [id 0 label "a"]\n'
                      '  node [id 1 label "b"]\n'
                      '  edge [source 0 target 1]\n]')
    assert sorted(G.edges()) == [("a", "b")]


def test_has_edge_unhashable_raises_typeerror_match_nx():
    """br-r37-c1-hashed-he: nx's ``has_edge`` propagates
    ``TypeError: unhashable type: 'X'`` on unhashable u or v —
    the underlying ``self._adj[u]`` dict lookup raises.  fnx's
    Rust binding silently caught the error and returned False,
    masking caller bugs (e.g. accidentally passing a list as a
    node identifier).

    Lock: unhashable args must raise TypeError on every graph
    type (Graph, DiGraph, MultiGraph, MultiDiGraph).  Hashable-
    but-missing args still return False (nx contract preserved).
    """
    P = fnx.path_graph(3)
    DG = fnx.DiGraph([(0, 1)])
    MG = fnx.MultiGraph([(0, 1)])
    MDG = fnx.MultiDiGraph([(0, 1)])

    # Unhashable u
    for G in (P, DG, MG, MDG):
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.has_edge([1, 2], 0)
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.has_edge(0, [1, 2])
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.has_edge({1: 2}, 0)

    # Multigraph with key=
    for MG2 in (MG, MDG):
        with pytest.raises(TypeError, match=r"unhashable type"):
            MG2.has_edge([1, 2], 0, key=0)

    # Hashable but missing — still returns False (regression)
    assert P.has_edge(0, 99) is False
    assert P.has_edge(99, 0) is False
    assert DG.has_edge(99, 0) is False

    # Good edges still True (regression)
    assert P.has_edge(0, 1) is True
    assert MG.has_edge(0, 1) is True
    assert MG.has_edge(0, 1, key=0) is True


def test_get_edge_data_unhashable_raises_typeerror_match_nx():
    """br-r37-c1-ged-hash: nx propagates ``TypeError: unhashable
    type: 'X'`` from the underlying ``self._adj[u]`` lookup;
    fnx's Rust binding silently returned ``default`` (or None)
    on unhashable u/v, masking caller bugs.

    Sister of br-r37-c1-cvtv6 (has_edge fix in cycle 108).
    Lock: unhashable u or v raises TypeError on every graph
    type.  Hashable-but-missing args still return None /
    default (nx contract preserved)."""
    P = fnx.path_graph(3)
    DG = fnx.DiGraph([(0, 1)])
    MG = fnx.MultiGraph([(0, 1)])
    MDG = fnx.MultiDiGraph([(0, 1)])

    for G in (P, DG, MG, MDG):
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data([1, 2], 0)
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data(0, [1, 2])
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data({1: 2}, 0)
        # default= must NOT swallow the TypeError
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data([1, 2], 0, default="X")

    # Hashable-but-missing — still returns None / default
    assert P.get_edge_data(0, 99) is None
    assert P.get_edge_data(0, 99, default="X") == "X"

    # Good edges still return data dict
    assert P.get_edge_data(0, 1) == {}
    assert MG.get_edge_data(0, 1) == {0: {}}


def test_multigraph_add_edge_unhashable_key_raises_typeerror():
    """br-r37-c1-mae-keyhash: ``MultiGraph.add_edge`` /
    ``MultiDiGraph.add_edge`` with an unhashable ``key=`` arg
    silently stored the unhashable as a Python-id-keyed entry,
    corrupting the graph state.  Every subsequent operation
    that walked the adjacency map then crashed with an opaque
    ``TypeError: unhashable type: 'list'`` from a call site
    completely unrelated to the original add_edge.

    Worse than the read-side has_edge / get_edge_data
    silent-False bugs (br-r37-c1-cvtv6 / br-r37-c1-kgpaj):
    add_edge here mutates state.  The error is now raised
    eagerly at the add_edge call site, matching nx's contract
    (``self._adj[u][v][key] = data`` raises on unhashable
    key).

    Lock: unhashable key= raises TypeError; hashable keys
    (int / str / tuple / None / etc) all still work."""
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        # Unhashable key — TypeError matching nx
        for bad_key in ([1, 2], {1: 2}, {1, 2}):
            G = cls()
            with pytest.raises(TypeError, match=r"unhashable type"):
                G.add_edge(0, 1, key=bad_key)
            # Graph state must remain empty (failed-write)
            assert G.number_of_edges() == 0

        # Hashable keys still work — regression
        for good_key in (99, "x", (1, 2), None):
            G = cls()
            r = G.add_edge(0, 1, key=good_key)
            assert r == (0 if good_key is None else good_key)

        # Mix: explicit key + auto key
        G = cls()
        G.add_edge(0, 1)             # auto key 0
        G.add_edge(0, 1)             # auto key 1
        G.add_edge(0, 1, key="custom")
        edges = list(G.edges(keys=True))
        assert (0, 1, "custom") in edges
        assert (0, 1, 0) in edges
        assert (0, 1, 1) in edges


def test_multigraph_has_edge_unhashable_key_raises_typeerror():
    """br-r37-c1-mhe-keyhash: ``MultiGraph.has_edge`` /
    ``MultiDiGraph.has_edge`` with an unhashable ``key=`` arg
    silently returned False.  nx propagates ``TypeError:
    unhashable type: '<X>'`` from the inner ``key in
    neighbors[v]`` dict lookup.

    Sister of br-r37-c1-cl78j (mutation-side add_edge fix in
    cycle 110) and the same family as br-r37-c1-cvtv6 (u/v
    hashing in has_edge).  Lock: unhashable key= raises
    TypeError; hashable keys (int / str / None / etc) still
    work — missing keys still return False (nx contract
    preserved)."""
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls([(0, 1)])

        # Unhashable key — TypeError matching nx
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.has_edge(0, 1, key=[1, 2])
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.has_edge(0, 1, key={1: 2})
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.has_edge(0, 1, key={1, 2})

        # Hashable but missing — still returns False (regression)
        assert G.has_edge(0, 1, key=99) is False
        assert G.has_edge(0, 1, key="x") is False
        # Good key still True (regression)
        assert G.has_edge(0, 1, key=0) is True
        # No key arg means "any edge between u and v"
        assert G.has_edge(0, 1) is True
        assert G.has_edge(0, 1, key=None) is True


def test_multigraph_get_edge_data_unhashable_key_raises_typeerror():
    """br-r37-c1-mged-keyhash: ``MultiGraph.get_edge_data`` /
    ``MultiDiGraph.get_edge_data`` with an unhashable ``key=``
    arg silently returned ``default`` (or None).  nx propagates
    ``TypeError: unhashable type: '<X>'`` from the inner key
    lookup.

    Sister of br-r37-c1-exavo (has_edge key in cycle 111),
    br-r37-c1-cl78j (add_edge key in cycle 110), and
    br-r37-c1-kgpaj (u/v ged in cycle 109).  Closes the
    read-side variant for the multigraph key arg.

    Lock: unhashable key= raises TypeError; missing key still
    returns default (nx contract preserved); good key returns
    edge data."""
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls([(0, 1)])

        # Unhashable key
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data(0, 1, key=[1, 2])
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data(0, 1, key={1: 2})
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data(0, 1, key={1, 2})

        # default= must NOT swallow the TypeError
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.get_edge_data(0, 1, key=[1, 2], default="X")

        # Hashable but missing — still returns None / default
        assert G.get_edge_data(0, 1, key=99) is None
        assert G.get_edge_data(0, 1, key=99, default="X") == "X"
        assert G.get_edge_data(0, 1, key="x") is None

        # Good key returns edge data dict
        assert G.get_edge_data(0, 1, key=0) == {}
        # No key — returns mapping of all keys to data
        assert G.get_edge_data(0, 1) == {0: {}}


def test_estrada_index_returns_int_zero_on_empty_graph():
    """br-r37-c1-est-empty: nx returns plain
    ``sum(subgraph_centrality(G).values())`` (no float() wrap),
    so an empty graph yields ``int(0)`` not ``float(0.0)``.
    fnx unconditionally cast to float, breaking drop-in callers
    asserting ``isinstance(result, int)`` on the empty-graph
    case.

    Same family as the transitivity int/float fix
    (br-r37-c1-4jnwn).  Lock: empty graph returns int(0); non-
    empty inputs still return float (subgraph_centrality
    returns floats internally)."""
    nv = nx.estrada_index(nx.Graph())
    fv = fnx.estrada_index(fnx.Graph())
    assert nv == fv == 0
    assert type(fv) is type(nv) is int

    # Non-empty inputs return float (regression)
    for build in (
        lambda l: (lambda g: (g.add_node(0), g)[1])(l.Graph()),
        lambda l: l.complete_graph(2),
        lambda l: l.path_graph(5),
        lambda l: l.karate_club_graph(),
    ):
        fv = fnx.estrada_index(build(fnx))
        nv = nx.estrada_index(build(nx))
        assert isinstance(fv, float)
        assert isinstance(nv, float)
        assert abs(fv - nv) < 1e-9


def test_nodeview_contains_unhashable_raises_typeerror():
    """br-r37-c1-nv-hash: ``NodeView.__contains__`` (the
    ``in G.nodes`` operator) silently returned False on
    unhashable items.  nx propagates ``TypeError: unhashable
    type: '<X>'`` from the underlying ``item in self._nodes``
    dict lookup.

    Affects all four graph-class NodeView types (NodeView,
    DiNodeView, MultiGraphNodeView, MultiDiGraphNodeView).
    Sister of br-r37-c1-cvtv6 / br-r37-c1-kgpaj /
    br-r37-c1-cl78j / br-r37-c1-exavo / br-r37-c1-9ll82 — same
    root pattern (Rust binding silently catches TypeError).

    Lock: ``[unhashable] in G.nodes`` raises TypeError on
    every graph type.  Hashable-but-missing returns False (nx
    contract preserved); good nodes return True.

    Note: ``NodeDataView`` (the result of ``nodes(data=True)``)
    intentionally swallows TypeError on both nx and fnx — its
    ``__contains__`` accepts arbitrary 2-tuples, not just node
    keys, so type-checking the first element is too strict for
    nx's contract.  This test covers only the bare
    ``G.nodes`` view."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_node(0)
        G.add_node(1)

        # Unhashable items
        with pytest.raises(TypeError, match=r"unhashable type"):
            [1, 2] in G.nodes
        with pytest.raises(TypeError, match=r"unhashable type"):
            {1: 2} in G.nodes
        with pytest.raises(TypeError, match=r"unhashable type"):
            {1, 2} in G.nodes

        # Hashable but missing — returns False
        assert (99 in G.nodes) is False
        assert ("x" in G.nodes) is False

        # Good nodes — returns True
        assert (0 in G.nodes) is True
        assert (1 in G.nodes) is True

    # NodeDataView regression: still silently False (nx contract)
    P = fnx.path_graph(3)
    assert ([1, 2] in P.nodes(data=True)) is False
    assert (1 in P.nodes(data=True)) is True


def test_degree_view_subscript_raises_keyerror_typeerror_match_nx():
    """br-r37-c1-dv-subscript: ``G.degree[node]`` must raise
    ``KeyError`` on a missing node and ``TypeError`` on an
    unhashable node — matching nx's underlying dict-lookup
    semantics.

    Previously fnx's ``_WeightAwareDegreeView`` (used by
    Graph/DiGraph) raised ``NodeNotFound`` for both cases —
    NodeNotFound is a subclass of NetworkXException, NOT a
    sibling of KeyError, so ``except KeyError:`` callers
    missed the exception.  The Multi* DegreeViews leaked
    KeyError on unhashable inputs (wrong class — nx raises
    TypeError there).

    Sister of the broader unhashable-arg family
    (br-r37-c1-cvtv6 / kgpaj / cl78j / exavo / 9ll82 /
    9av1g)."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edge(0, 1)

        # Missing node — KeyError matching nx
        with pytest.raises(KeyError):
            G.degree[99]
        with pytest.raises(KeyError):
            G.degree[None]
        with pytest.raises(KeyError):
            G.degree["x"]

        # Unhashable subscript — TypeError matching nx
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.degree[[1, 2]]
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.degree[{1: 2}]
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.degree[{1, 2}]

        # Good subscript still returns degree (regression)
        assert G.degree[0] == 1
        assert G.degree[1] == 1


def test_edges_subscript_message_and_typeerror_match_nx():
    """br-r37-c1-eg-msg: ``G.edges[(u, v)]`` for missing edges
    must raise ``KeyError(f"The edge {e} is not in the graph.")``
    matching nx's exact message; unhashable endpoints must
    raise ``TypeError`` (not silent KeyError on the tuple).

    Previously fnx's ``_make_edge_view_getitem_preserving_key``
    re-raised any KeyError with the raw edge tuple as the
    KeyError arg, breaking ``pytest.raises(KeyError, match=
    r"is not in the graph")`` callers.  The Rust raw binding
    also rejected non-tuple subscripts (e.g. strings), where
    nx accepts any 2-element iterable.

    Lock: missing edges → KeyError with nx's wording;
    unhashable endpoints → TypeError; non-iterable subscript →
    TypeError("cannot unpack non-iterable …"); good edges
    return data dict; string subscripts work as 2-iterables."""
    P = fnx.path_graph(3)
    DG = fnx.DiGraph([(0, 1), (1, 2)])

    # Missing edge — exact nx message format
    for G in (P, DG):
        with pytest.raises(KeyError, match=r"The edge \(99, 0\) is not in the graph"):
            G.edges[(99, 0)]
        with pytest.raises(KeyError, match=r"The edge \(0, 99\) is not in the graph"):
            G.edges[(0, 99)]

    # Unhashable endpoints → TypeError
    for G in (P, DG):
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.edges[([1, 2], 0)]
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.edges[(0, [1, 2])]

    # Non-iterable subscript → unpack TypeError
    with pytest.raises(TypeError, match=r"cannot unpack non-iterable"):
        P.edges[123]
    with pytest.raises(TypeError, match=r"cannot unpack non-iterable"):
        P.edges[None]

    # Mis-sized iterable → ValueError from unpack
    with pytest.raises(ValueError, match=r"not enough values to unpack"):
        P.edges[(1,)]
    with pytest.raises(ValueError, match=r"too many values to unpack"):
        P.edges[(1, 2, 3)]

    # String subscript: nx accepts as 2-iterable; missing edge
    # gets the standard nx message ("The edge xy is not …").
    with pytest.raises(KeyError, match=r"The edge xy is not in the graph"):
        P.edges["xy"]

    # Good edges — returns data dict
    assert P.edges[(0, 1)] == {}
    assert DG.edges[(0, 1)] == {}

    # Good string-named edge
    G_s = fnx.Graph()
    G_s.add_edge("x", "y")
    assert G_s.edges["xy"] == {}


def test_multiedgeview_subscript_specific_keyerror_match_nx():
    """br-r37-c1-meg-msg: ``MultiGraph.edges[(u, v, k)]`` and
    ``MultiDiGraph.edges[(u, v, k)]`` must raise ``KeyError`` on
    the *specific* missing element from the chained lookup —
    not on the raw 3-tuple.  nx does ``u, v, k = e; return
    self._adjdict[u][v][k]`` so missing u → KeyError(u),
    missing v → KeyError(v), missing key → KeyError(k).

    Same family as br-r37-c1-ltri7 (cycle 116 simple EdgeView
    fix).  Closes the multigraph corner of the EdgeView
    subscript exception-class family.

    Lock: missing-element KeyError carries that exact element;
    unhashable u/v/k raises TypeError; mis-sized tuples raise
    ValueError from the unpack; reverse-orientation lookup on
    undirected MG still resolves; good edges return data dict.
    """
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls([(0, 1)])

        # Missing key (last element of the 3-tuple)
        with pytest.raises(KeyError) as ei:
            G.edges[(0, 1, 99)]
        assert ei.value.args[0] == 99

        # Missing u (first element)
        with pytest.raises(KeyError) as ei:
            G.edges[(99, 1, 0)]
        assert ei.value.args[0] == 99

        # Missing v (middle element)
        with pytest.raises(KeyError) as ei:
            G.edges[(0, 99, 0)]
        assert ei.value.args[0] == 99

        # Unhashable elements → TypeError
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.edges[([1, 2], 1, 0)]
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.edges[(0, [1, 2], 0)]
        with pytest.raises(TypeError, match=r"unhashable type"):
            G.edges[(0, 1, [1, 2])]

        # Mis-sized 2-tuple → unpack ValueError
        with pytest.raises(ValueError, match=r"not enough values to unpack"):
            G.edges[(0, 1)]
        # 4-tuple → unpack ValueError
        with pytest.raises(ValueError, match=r"too many values to unpack"):
            G.edges[(0, 1, 2, 3)]

        # Good edge — returns data dict
        assert G.edges[(0, 1, 0)] == {}

    # Reverse-orientation undirected fallback (br-multiedgeview-rev
    # behaviour preserved): MG.edges[(1, 0, 0)] resolves the same
    # underlying edge as (0, 1, 0)
    MG = fnx.MultiGraph([(0, 1)])
    assert MG.edges[(1, 0, 0)] == {}


def test_efficiency_int_zero_on_disconnected_and_message_match_nx():
    """br-r37-c1-eff-int0 / br-r37-c1-eff-msg: ``efficiency``
    diverged from nx in two ways:

    (1) Disconnected pair returned ``float(0.0)`` from the Rust
        binding; nx's reference does ``except NetworkXNoPath:
        eff = 0`` (literal int).

    (2) Bad-node error message used ``Node {n} is not in G``
        from the Rust path; nx says ``Source {u} is not in G``
        (when source missing) or ``Target {v} is not in G``
        (when only target missing).

    Same int/float family as br-r37-c1-3ejen / 4jnwn /
    transitivity.

    Lock: disconnected → int(0); connected → float; u==v →
    ZeroDivisionError; bad-source → 'Source {u} is not in G';
    bad-target-only → 'Target {v} is not in G'."""
    # Disconnected pair → int 0
    G = fnx.Graph([(0, 1), (2, 3)])
    val = fnx.efficiency(G, 0, 3)
    assert val == 0
    assert type(val) is int
    assert val == nx.efficiency(nx.Graph([(0, 1), (2, 3)]), 0, 3)
    assert type(val) is type(nx.efficiency(nx.Graph([(0, 1), (2, 3)]), 0, 3))

    # Connected pair → float
    P = fnx.path_graph(5)
    val = fnx.efficiency(P, 0, 4)
    assert val == 0.25
    assert isinstance(val, float)

    # u==v → ZeroDivisionError (matches nx; 1/0)
    with pytest.raises(ZeroDivisionError):
        fnx.efficiency(P, 1, 1)

    # Bad source — nx exact wording
    with pytest.raises(nx.NodeNotFound, match=r"Source 99 is not in G"):
        fnx.efficiency(P, 99, 0)

    # Bad target only (source valid) — nx says Target
    with pytest.raises(nx.NodeNotFound, match=r"Target 99 is not in G"):
        fnx.efficiency(P, 0, 99)

    # Both bad → Source first (matches nx ordering)
    with pytest.raises(nx.NodeNotFound, match=r"Source 99 is not in G"):
        fnx.efficiency(P, 99, 100)


def test_average_node_connectivity_int_zero_on_lt2_nodes():
    """br-r37-c1-anc-int0: ``average_node_connectivity`` on a
    graph with fewer than 2 nodes returned ``float(0.0)`` from
    the Rust binding; nx returns literal ``int(0)`` from its
    ``if den == 0: return 0`` branch (the (u, v) pair iterator
    is empty, so num/den are never computed).

    Same int/float family as br-r37-c1-eff-int0 (efficiency) /
    3ejen (estrada_index) / 4jnwn (transitivity).

    Lock: empty / single-node graphs return int 0; two
    isolated-only nodes return float 0.0 (the divide branch
    runs since den becomes 1); non-trivial inputs continue to
    return float."""
    # Empty / single-node — int 0
    for build in (
        lambda: fnx.Graph(),
        lambda: (lambda g: (g.add_node(0), g)[1])(fnx.Graph()),
    ):
        v = fnx.average_node_connectivity(build())
        assert v == 0
        assert type(v) is int

    # Two isolated nodes — float 0.0 (matches nx — divide ran)
    G = fnx.Graph()
    G.add_nodes_from([0, 1])
    v = fnx.average_node_connectivity(G)
    assert v == 0.0
    assert isinstance(v, float)

    # Non-trivial — float (regression)
    assert isinstance(fnx.average_node_connectivity(fnx.complete_graph(2)), float)
    assert isinstance(fnx.average_node_connectivity(fnx.path_graph(5)), float)
    assert fnx.average_node_connectivity(fnx.complete_graph(5)) == 4.0


def test_subgraph_view_shares_parent_graph_dict_identity():
    """br-r37-c1-fgv-graph-id: nx's subgraph_view and copy(
    as_view=True) share the parent's ``graph`` attribute dict
    by reference — ``view.graph is parent.graph`` must hold so
    mutations to the parent's graph attrs are visible through
    the view.

    fnx's _FilteredGraphView.__init__ did ``self.graph =
    graph.graph``, but the _GraphAttrsDescriptor.__set__ on
    the canonical Graph base class intercepted the assignment
    and clear+update'd the existing Rust-native dict instead
    of storing the reference — losing identity.

    Fix bypasses the descriptor by writing to the override
    slot directly via ``vars(self)[_GRAPH_ATTR_OVERRIDE]``.

    Lock: identity preservation across all four graph types ×
    {subgraph_view, copy(as_view=True)} + post-construction
    parent mutation visibility."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        # subgraph view
        g = cls([("a", "b"), ("b", "c")])
        g.graph["mode"] = "orig"
        sub = g.subgraph(["a", "b", "c"])
        assert sub.graph is g.graph, f"{cls.__name__}: subgraph identity broken"

        # copy(as_view=True)
        cv = g.copy(as_view=True)
        assert cv.graph is g.graph, f"{cls.__name__}: copy(as_view=True) identity broken"

        # Mutation visibility through both view types
        g.graph["mode"] = "updated"
        assert sub.graph["mode"] == "updated"
        assert cv.graph["mode"] == "updated"

        # New keys also propagate
        g.graph["new_key"] = 42
        assert sub.graph["new_key"] == 42
        assert cv.graph["new_key"] == 42


def test_filtered_view_has_node_tracks_parent_removals():
    """br-r37-c1-fgv-has-node: ``_FilteredGraphView.__contains__``
    correctly delegated to ``_node_visible`` (re-checks parent's
    current node set + the filter), but ``has_node`` was
    inherited from the canonical Graph base class (added as a
    second base for isinstance parity, br-r37-c1-rcd0e) and went
    through the Rust-native node lookup against the synthetic
    view's uninitialised Rust state.  Result:
    ``parent.remove_node(n)`` left ``view.has_node(n)``
    returning True forever — a stale-view defect breaking
    nx's "view tracks parent mutations" contract.

    Sister of br-r37-c1-95ws4 (graph-dict-identity fix in cycle
    121).  Closes the remaining 4 of the 5 deferred view-
    tracking failures."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        g = cls([("a", "b"), ("b", "c"), ("c", "d")])
        sub = g.subgraph(["a", "b", "c", "d"])

        # Initial state: 'a' is in the view
        assert "a" in sub
        assert sub.has_node("a")

        # Remove 'a' from parent
        g.remove_node("a")

        # Both __contains__ and has_node must agree the node is gone
        assert "a" not in sub
        assert sub.has_node("a") is False

        # Re-add 'a' to parent (still in subgraph filter set)
        g.add_node("a")
        assert "a" in sub
        assert sub.has_node("a") is True

        # Filter-excluded node never visible regardless of parent state
        sub2 = g.subgraph(["b", "c"])
        assert "a" not in sub2
        assert sub2.has_node("a") is False


def test_filtered_view_size_with_weight_honors_filter():
    """br-r37-c1-fgv-size: ``_FilteredGraphView.size(weight=w)``
    inherited from the canonical Graph base class delegated to
    the Rust raw size which read the parent's full Rust state
    without honoring the view's filters.  Result:
    ``view.size(weight="w")`` summed the parent's full edge
    weight (including filtered-out edges) rather than the
    visible subset.

    Last of the three view-tracking sister fixes
    (br-r37-c1-95ws4 graph-dict-identity, br-r37-c1-g8pso
    has_node).  Closes the final pre-existing failure in
    test_graph_utilities.py."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        g = cls()
        for n in "abcd":
            g.add_node(n)
        for u, v, w in [("a", "b", 1), ("b", "c", 3), ("c", "d", 4)]:
            g.add_edge(u, v, weight=w)

        # subgraph_view filtering out 'd'
        sub = fnx.subgraph_view(g, filter_node=lambda n: n != "d")

        # Visible edges: a-b (w=1), b-c (w=3) → size weighted = 4
        assert sub.size() == 2
        assert sub.size(weight="weight") == 4.0
        assert isinstance(sub.size(weight="weight"), float)

        # Empty filter → 0 unweighted, 0.0 weighted
        sub_empty = fnx.subgraph_view(g, filter_node=lambda n: False)
        assert sub_empty.size() == 0
        assert sub_empty.size(weight="weight") == 0.0

        # No filter → full graph size
        sub_all = fnx.subgraph_view(g, filter_node=lambda n: True)
        assert sub_all.size() == 3
        assert sub_all.size(weight="weight") == 8.0

    # Subgraph (not subgraph_view) also honors the filter
    g = fnx.Graph([("a", "b", {"weight": 1}),
                   ("b", "c", {"weight": 3}),
                   ("c", "d", {"weight": 4})])
    sub = g.subgraph(["a", "b", "c"])
    assert sub.size(weight="weight") == 4.0


def test_parse_multiline_adjlist_dict_data_with_edgetype():
    """br-r37-c1-mla-dict: ``write_multiline_adjlist`` writes
    edge data as dict literals (e.g. ``{'weight': 1.5}``) when
    edges have any attributes.  nx's ``parse_multiline_adjlist``
    rejects dict-serialized edge data when ``edgetype`` is
    supplied — so the natural round-trip
    ``write → read(edgetype=float)`` raises in nx too.

    fnx is more lenient: if the data string starts with ``{``,
    parse it via ``literal_eval`` regardless of ``edgetype``.
    Restores the documented round-trip use case (write
    weighted → read with edgetype hint) without breaking
    nx-parity for the scalar-data path.

    Lock: round-trip works; cross-compat (nx writes / fnx
    reads) works; scalar-data path still raises on bad input.
    """
    import io

    # Round-trip: fnx writes, fnx reads with edgetype
    g = fnx.Graph([(1, 2, {"weight": 1.5}), (2, 3, {"weight": 2.5})])
    buf = io.BytesIO()
    fnx.write_multiline_adjlist(g, buf)
    buf.seek(0)
    parsed = fnx.read_multiline_adjlist(buf, nodetype=int, edgetype=float)
    assert sorted(parsed.nodes()) == [1, 2, 3]
    assert sorted(parsed.edges()) == [(1, 2), (2, 3)]
    # edge attrs survive (literal_eval recovered them)
    edges_with_data = sorted(parsed.edges(data=True))
    assert edges_with_data == [
        (1, 2, {"weight": 1.5}),
        (2, 3, {"weight": 2.5}),
    ]

    # Cross-compat: nx writes, fnx reads with edgetype
    g_nx = nx.Graph(g)
    nx_buf = io.BytesIO()
    nx.write_multiline_adjlist(g_nx, nx_buf)
    nx_buf.seek(0)
    parsed_x = fnx.read_multiline_adjlist(nx_buf, nodetype=int, edgetype=float)
    assert sorted(parsed_x.nodes()) == [1, 2, 3]
    assert sorted(parsed_x.edges()) == [(1, 2), (2, 3)]

    # Scalar-data + edgetype path still works (preserved nx
    # contract for non-dict edges)
    text = "1 1\n2 2.5\n2 0\n"
    p = fnx.parse_multiline_adjlist(text.split("\n"), nodetype=int, edgetype=float)
    assert list(p.edges(data=True)) == [(1, 2, {"weight": 2.5})]

    # Bad scalar data + edgetype still raises (nx contract)
    text_bad = "1 1\n2 abc\n2 0\n"
    with pytest.raises(TypeError, match=r"Failed to convert edge data"):
        fnx.parse_multiline_adjlist(text_bad.split("\n"), nodetype=int, edgetype=float)


def test_dijkstra_neg_inf_weight_raises_match_nx():
    """br-r37-c1-djk-neginf: ``shortest_path`` / ``dijkstra_path``
    on a graph with a ``-inf`` edge weight silently returned a
    ``-inf``-cost path; nx detects the contradiction during
    relaxation and raises ``ValueError("Contradictory paths
    found: negative weights?")``.

    The negative-weight detection in
    ``_has_negative_edge_weight_for_dijkstra`` filtered values
    with ``isfinite(value) and value < 0`` (and the native Rust
    helper did the same SIMD-friendly check), so ``-inf``
    slipped past both screens — the wrapper never delegated to
    nx and the Rust dijkstra ran on a -inf-weighted graph.

    Lock: -inf weight raises the same nx ValueError on simple
    Graph, DiGraph, and MultiGraph.  Other special weights
    (NaN, +inf, finite negative) continue to behave as before
    (NaN/+inf return nominal path; finite negative raises
    the same nx error)."""
    # Undirected (Graph / MultiGraph) — nx detects the contradiction
    # via relaxation revisiting the source node and raises.
    for cls in (fnx.Graph, fnx.MultiGraph):
        g = cls()
        g.add_edge(0, 1, weight=-float("inf"))
        g.add_edge(1, 2, weight=1.0)
        with pytest.raises(ValueError, match=r"[Cc]ontradictory paths"):
            fnx.shortest_path(g, 0, 2, weight="weight")
        with pytest.raises(ValueError, match=r"[Cc]ontradictory paths"):
            fnx.dijkstra_path(g, 0, 2, weight="weight")
        with pytest.raises(ValueError, match=r"[Cc]ontradictory paths"):
            fnx.shortest_path_length(g, 0, 2, weight="weight")

    # Directed (DiGraph / MultiDiGraph) — nx silently returns a path
    # because the relaxation never revisits node 0 (no back-edge).
    # This is nx's documented asymmetry; fnx matches.
    for cls in (fnx.DiGraph, fnx.MultiDiGraph):
        g = cls()
        g.add_edge(0, 1, weight=-float("inf"))
        g.add_edge(1, 2, weight=1.0)
        assert fnx.shortest_path(g, 0, 2, weight="weight") == [0, 1, 2]

    # Finite negative — still raises (regression)
    g = fnx.Graph([(0, 1, {"weight": -1.0}), (1, 2, {"weight": 1.0})])
    with pytest.raises(ValueError, match=r"[Cc]ontradictory paths"):
        fnx.dijkstra_path(g, 0, 2, weight="weight")

    # +inf — returns path (matches nx, not a contradiction)
    g = fnx.Graph([(0, 1, {"weight": float("inf")}), (1, 2, {"weight": 1.0})])
    assert fnx.dijkstra_path(g, 0, 2, weight="weight") == [0, 1, 2]
    assert fnx.shortest_path_length(g, 0, 2, weight="weight") == float("inf")

    # NaN — returns path (matches nx; NaN comparisons silently relax)
    import math
    g = fnx.Graph([(0, 1, {"weight": float("nan")}), (1, 2, {"weight": 1.0})])
    assert fnx.dijkstra_path(g, 0, 2, weight="weight") == [0, 1, 2]
    length = fnx.shortest_path_length(g, 0, 2, weight="weight")
    assert math.isnan(length)


def test_random_tree_removed_matches_nx_attribute_error():
    """br-r37-c1-rt-removed: nx 3.4 removed ``random_tree`` and
    its module ``__getattr__`` raises an AttributeError on
    access pointing callers at ``random_labeled_tree``.

    fnx had a public ``random_tree`` Python function that
    silently kept working — a drop-in regression: callers that
    catch the deprecation AttributeError to switch APIs saw fnx
    happily proceeding, masking the breakage and producing
    silent semantic drift across libraries.

    Lock: fnx.random_tree access raises the same nx
    AttributeError; the replacement ``random_labeled_tree``
    works and matches nx output.  Internal callers that
    previously used random_tree (random_labeled_tree,
    random_unlabeled_tree, random_labeled_rooted_tree) now
    delegate to the renamed private ``_random_tree_internal``."""
    # Access — raises AttributeError matching nx
    with pytest.raises(AttributeError,
                       match=r"nx\.random_tree was removed in version 3\.4"):
        fnx.random_tree

    with pytest.raises(AttributeError,
                       match=r"nx\.random_tree was removed in version 3\.4"):
        # Call form too
        fnx.random_tree(5)

    # nx behaves identically
    with pytest.raises(AttributeError,
                       match=r"nx\.random_tree was removed in version 3\.4"):
        nx.random_tree(5)

    # Replacement works and matches nx output for same seed
    f = list(fnx.random_labeled_tree(5, seed=42).edges())
    n = list(nx.random_labeled_tree(5, seed=42).edges())
    assert f == n

    # Internal callers still work (regression)
    assert fnx.random_unlabeled_tree(5, seed=42).number_of_nodes() == 5
    assert fnx.random_labeled_rooted_tree(5, seed=42).number_of_nodes() == 5


def test_biadjacency_matrix_only_at_bipartite_namespace():
    """br-r37-c1-bia-removed: ``biadjacency_matrix`` and
    ``from_biadjacency_matrix`` are only on ``nx.bipartite``,
    not at nx top-level.  fnx had top-level Python re-
    implementations that masked the AttributeError nx raises
    for drop-in callers writing ``nx.biadjacency_matrix``.

    Sister of br-r37-c1-pmi1f (random_tree removed in nx 3.4).
    Same root pattern: fnx exposed a public symbol nx doesn't
    expose, breaking the 'access raises AttributeError' contract
    that drop-in code relies on.

    Lock: top-level access raises nx's exact AttributeError;
    the bipartite-namespaced versions still work and match nx
    output."""
    # Top-level access — raises matching nx
    with pytest.raises(AttributeError, match=r"has no attribute 'biadjacency_matrix'"):
        fnx.biadjacency_matrix
    with pytest.raises(AttributeError, match=r"has no attribute 'from_biadjacency_matrix'"):
        fnx.from_biadjacency_matrix
    # nx behaves identically
    with pytest.raises(AttributeError, match=r"has no attribute 'biadjacency_matrix'"):
        nx.biadjacency_matrix
    with pytest.raises(AttributeError, match=r"has no attribute 'from_biadjacency_matrix'"):
        nx.from_biadjacency_matrix

    # bipartite-namespaced versions still work and match nx
    B_f = fnx.Graph()
    B_f.add_nodes_from([0, 1, 2], bipartite=0)
    B_f.add_nodes_from(["a", "b"], bipartite=1)
    B_f.add_edges_from([(0, "a"), (1, "b")])

    B_n = nx.Graph()
    B_n.add_nodes_from([0, 1, 2], bipartite=0)
    B_n.add_nodes_from(["a", "b"], bipartite=1)
    B_n.add_edges_from([(0, "a"), (1, "b")])

    m_f = fnx.bipartite.biadjacency_matrix(B_f, [0, 1, 2], ["a", "b"])
    m_n = nx.bipartite.biadjacency_matrix(B_n, [0, 1, 2], ["a", "b"])
    assert m_f.toarray().tolist() == m_n.toarray().tolist()

    # Round-trip via from_biadjacency_matrix at the namespaced location
    H = fnx.bipartite.from_biadjacency_matrix(m_f)
    assert H.number_of_edges() == 2


def test_bipartite_sets_density_only_at_bipartite_namespace():
    """br-r37-c1-bipx-removed: ``bipartite_sets`` and
    ``bipartite_density`` are exposed by nx only at
    ``nx.bipartite.sets`` / ``nx.bipartite.density``; top-
    level ``nx.bipartite_sets`` raises AttributeError.

    fnx had top-level convenience aliases (a Rust binding for
    bipartite_sets and a Python re-implementation for
    bipartite_density) that masked the AttributeError nx raises
    for drop-in callers writing ``nx.bipartite_sets``.

    Same family as br-r37-c1-bia-removed (biadjacency_matrix)
    and br-r37-c1-pmi1f (random_tree).  Closes another nx-
    namespace parity gap.

    Lock: top-level access raises nx's exact AttributeError;
    the bipartite-namespaced versions still work and match nx
    output."""
    for name in ("bipartite_sets", "bipartite_density"):
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(fnx, name)
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(nx, name)

    # bipartite-namespaced versions still work and match nx
    B_f = fnx.Graph([(0, "a"), (0, "b"), (1, "a")])
    B_n = nx.Graph([(0, "a"), (0, "b"), (1, "a")])

    sets_f = tuple(map(sorted, fnx.bipartite.sets(B_f)))
    sets_n = tuple(map(sorted, nx.bipartite.sets(B_n)))
    assert sets_f == sets_n

    d_f = fnx.bipartite.density(B_f, [0, 1])
    d_n = nx.bipartite.density(B_n, [0, 1])
    assert d_f == d_n


def test_isomorphism_match_helpers_only_at_algorithms_isomorphism():
    """br-r37-c1-iso-removed: nine isomorphism matcher
    constructors (categorical/numerical/generic ×
    node/edge/multiedge) are exposed by nx only at
    ``nx.algorithms.isomorphism.X``; top-level access
    (``nx.categorical_node_match``) raises AttributeError.

    fnx had module-level aliases at top level that masked the
    AttributeError nx raises for drop-in callers.

    Same family as br-r37-c1-pmi1f (random_tree),
    br-r37-c1-bia-removed (biadjacency_matrix), and
    br-r37-c1-bipx-removed (bipartite_sets/density).  Cycle
    129's batch closes the iso-matcher cluster.

    Lock: top-level access raises nx's exact AttributeError
    for all 9 matchers; the algorithms.isomorphism-namespaced
    versions still work and are callable factories."""
    matchers = [
        "categorical_node_match", "categorical_edge_match",
        "categorical_multiedge_match",
        "numerical_node_match", "numerical_edge_match",
        "numerical_multiedge_match",
        "generic_node_match", "generic_edge_match",
        "generic_multiedge_match",
    ]
    for name in matchers:
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(fnx, name)
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(nx, name)

    # Namespaced versions still callable factories
    for name in matchers:
        f = getattr(fnx.algorithms.isomorphism, name)
        n = getattr(nx.algorithms.isomorphism, name)
        assert callable(f)
        assert callable(n)
        assert f is n  # fnx.algorithms.isomorphism is nx's module


def test_branching_weight_minimal_branching_only_at_branchings_namespace():
    """br-r37-c1-bw-removed: ``branching_weight`` and
    ``minimal_branching`` live only at
    ``nx.algorithms.tree.branchings.X`` in nx; top-level
    access raises AttributeError.

    fnx had top-level pure-delegate Python wrappers (which
    just routed to ``_nx.algorithms.tree.branchings.X``) that
    masked nx's AttributeError contract for drop-in callers.

    Continues the namespace-parity family: br-r37-c1-pmi1f
    (random_tree), bia-removed (biadjacency_matrix), bipx-
    removed (bipartite_sets/density), ofkcv (iso matchers).

    Lock: top-level access raises; the namespaced versions
    still work and produce numerical results."""
    for name in ("branching_weight", "minimal_branching"):
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(fnx, name)
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(nx, name)

    # Namespaced version still works (must build via nx so the
    # backend dispatch on the mutation-side function accepts the
    # input)
    G = nx.DiGraph()
    G.add_edge(0, 1, weight=5)
    G.add_edge(1, 2, weight=3)
    assert fnx.algorithms.tree.branchings.branching_weight(G) == 8
    # minimal_branching mutates input — just verify it runs
    out = fnx.algorithms.tree.branchings.minimal_branching(G, attr="weight")
    assert out is not None


def test_max_weight_matching_rejects_multigraph_match_nx():
    """br-r37-c1-mwm-mg: ``max_weight_matching`` on a MultiGraph
    silently projected parallel edges to a simple Graph (taking
    the max weight per pair) and returned a matching, masking
    nx's ``@not_implemented_for("multigraph")`` decorator
    contract.  Drop-in callers expecting nx's
    ``NetworkXNotImplemented`` saw a working result on fnx.

    fnx now mirrors nx's eager rejection.  Sister of the
    namespace-parity family — this is a behavioural-parity
    fix in the same family of "fnx silently extends nx"
    bugs.

    Lock: MG / MDG / DG all raise NetworkXNotImplemented;
    Graph still returns the matching."""
    # MultiGraph — raises on multigraph
    fg = fnx.MultiGraph([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented,
                       match=r"not implemented for multigraph type"):
        fnx.max_weight_matching(fg)

    # MultiDiGraph — raises on directed (decorator order)
    fmdg = fnx.MultiDiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented,
                       match=r"not implemented for directed type"):
        fnx.max_weight_matching(fmdg)

    # DiGraph — raises on directed (regression)
    fdg = fnx.DiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented,
                       match=r"not implemented for directed type"):
        fnx.max_weight_matching(fdg)

    # Graph — works (regression)
    fg2 = fnx.Graph([(0, 1)])
    assert fnx.max_weight_matching(fg2) == {(1, 0)}


def test_planarity_helpers_only_at_algorithms_planarity():
    """br-r37-c1-plr-removed: ``check_planarity_recursive``,
    ``get_counterexample``, and ``get_counterexample_recursive``
    are exposed by nx only at ``nx.algorithms.planarity.X``;
    nx top-level access raises AttributeError.

    fnx had module-level Python wrappers that masked nx's
    contract.  Drop-in callers writing
    ``nx.check_planarity_recursive(G)`` got a working result
    on fnx but AttributeError on nx.

    Continues the namespace-parity family.

    Lock: top-level access raises; the
    fnx.algorithms.planarity-namespaced versions still work
    and produce sensible output (K5 not planar)."""
    for name in (
        "check_planarity_recursive",
        "get_counterexample",
        "get_counterexample_recursive",
    ):
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(fnx, name)
        with pytest.raises(AttributeError, match=fr"has no attribute '{name}'"):
            getattr(nx, name)

    # Top-level non-recursive variants still work (nx exposes them)
    is_p, _ = fnx.check_planarity(fnx.complete_graph(5))
    assert is_p is False  # K5 not planar
    assert fnx.is_planar(fnx.complete_graph(5)) is False

    # Namespaced recursive variant works
    is_p_r, _ = fnx.algorithms.planarity.check_planarity_recursive(fnx.complete_graph(5))
    assert is_p_r is False

    # Counterexample at namespaced location returns Kuratowski subgraph
    counter = fnx.algorithms.planarity.get_counterexample(fnx.complete_graph(5))
    assert counter is not None
    assert counter.number_of_nodes() >= 5


def test_write_gexf_classified_as_py_wrapper_not_nx_delegated():
    """br-r37-c1-wgexf-cls: ``write_gexf`` had a ``from networkx
    import ...`` at function scope (the simple-graph delegation
    branch).  The coverage-matrix classifier scans function
    source via AST and flags any direct nx import/reference as
    ``NX_DELEGATED`` — a category disallowed for public exports
    per ``test_public_coverage_has_no_networkx_delegated_exports``.

    Sister of br-r37-c1-{eeawk, nlkkm, nhgtp, wgexf-parity} —
    same root pattern: keep public wrappers free of direct nx
    references so the byte-parity story is enforced via private
    helpers.

    Lock: write_gexf classifies as PY_WRAPPER (not NX_DELEGATED),
    NX_DELEGATED count remains 0 across the full export surface,
    and the byte output still matches nx exactly."""
    import sys as _sys
    _sys.path.insert(0, "/data/projects/franken_networkx/scripts")
    try:
        import generate_coverage_matrix as _gcm
    finally:
        _sys.path.pop(0)

    # write_gexf must be classified as PY_WRAPPER
    assert _gcm.classify_export(fnx.write_gexf) == "PY_WRAPPER"

    # No exports may be NX_DELEGATED
    exports, _ = _gcm.load_public_exports()
    delegated = [name for name, obj in exports
                 if _gcm.classify_export(obj) == "NX_DELEGATED"]
    assert delegated == []

    # Byte-parity preserved: simple-graph and multi-graph
    # branches still produce nx-matching output (single-quoted
    # XML decl, lowercase utf-8).
    import io
    buf = io.BytesIO()
    fnx.write_gexf(fnx.path_graph(3), buf)
    assert buf.getvalue().startswith(b"<?xml version='1.0' encoding='utf-8'?>")

    buf2 = io.BytesIO()
    fnx.write_gexf(fnx.MultiGraph([(0, 1), (0, 1)]), buf2)
    assert buf2.getvalue().startswith(b"<?xml version='1.0' encoding='utf-8'?>")


def test_display_accepts_canvas_kwarg_match_nx():
    """br-r37-c1-disp-canvas: nx.display accepts a positional
    ``canvas`` (matplotlib Axes) argument used as the drawing
    target.  fnx's signature was ``(G, **kwds)`` so drop-in
    code calling ``nx.display(G, canvas=ax)`` raised
    ``TypeError: write_network_text() got an unexpected
    keyword argument 'canvas'``.

    Lock: signature includes ``canvas=None`` matching nx;
    canvas=None still works (text fallback path);
    explicit canvas is routed as ``ax`` to draw when
    matplotlib is available."""
    import inspect

    # Signature parity (excluding the **kwargs name diff which
    # is cosmetic — both libs accept arbitrary kwargs)
    f_sig = inspect.signature(fnx.display)
    n_sig = inspect.signature(nx.display)
    f_params = [(p.name, p.default) for p in f_sig.parameters.values()
                if p.kind != p.VAR_KEYWORD]
    n_params = [(p.name, p.default) for p in n_sig.parameters.values()
                if p.kind != p.VAR_KEYWORD]
    assert f_params == n_params == [("G", inspect.Parameter.empty),
                                     ("canvas", None)]

    # Functional: text-fallback path with canvas=None
    G = fnx.path_graph(3)
    out = fnx.display(G, canvas=None)
    assert isinstance(out, str)
    assert "0" in out  # node label appears in text repr

    # Without canvas kwarg (positional)
    out2 = fnx.display(G)
    assert out == out2


def test_spectral_graph_forge_alpha_required_match_nx():
    """br-r37-c1-sgf-alpha: nx requires ``alpha`` as a
    positional argument (no default).  fnx provided
    ``alpha=0.8``, silently making ``fnx.spectral_graph_forge(G)``
    succeed while nx raises ``TypeError``.

    Drop-in callers writing the nx form (without alpha) saw a
    working result on fnx — silent semantic drift across
    libraries.  Same family pattern as the recent silent-
    extension fixes (br-r37-c1-mwm-mg, br-r37-c1-pmi1f,
    br-r37-c1-bia-removed, etc).

    Lock: signature matches nx exactly (alpha positional, no
    default); explicit alpha (positional or kwarg) works."""
    import inspect

    f_sig = inspect.signature(fnx.spectral_graph_forge)
    n_sig = inspect.signature(nx.spectral_graph_forge)
    f_alpha = f_sig.parameters["alpha"]
    n_alpha = n_sig.parameters["alpha"]
    assert f_alpha.default == n_alpha.default == inspect.Parameter.empty

    G = fnx.karate_club_graph()
    # Without alpha — must raise (parity)
    with pytest.raises(TypeError, match=r"missing 1 required positional argument: 'alpha'"):
        fnx.spectral_graph_forge(G, seed=42)

    # nx behaves identically
    with pytest.raises(TypeError, match=r"missing 1 required positional argument: 'alpha'"):
        nx.spectral_graph_forge(nx.karate_club_graph(), seed=42)

    # With explicit alpha — works (positional)
    out = fnx.spectral_graph_forge(G, 0.8, seed=42)
    assert out.number_of_nodes() == 34

    # With explicit alpha — works (kwarg)
    out2 = fnx.spectral_graph_forge(G, alpha=0.5, seed=42)
    assert out2.number_of_nodes() == 34


def test_all_simple_paths_handles_nan_inf_float_cutoff_match_nx():
    """br-r37-c1-asp-nan: ``all_simple_paths`` with non-integer
    ``cutoff`` (NaN / +inf / finite floats) raised TypeError on
    fnx because the Rust binding's PyO3 signature requires int.
    nx accepts any numeric cutoff via its ``len(stack) >= cutoff``
    comparison.

    Three normalisations restore parity with nx:
      * NaN / -inf / negative int → empty (positive predicate
        ``cutoff >= 0`` is False)
      * +inf → None (treated as unbounded)
      * finite float → ceil (matches nx's effective semantics
        empirically: nx(3.5) yields the 4-edge path, ceil(3.5)=4
        also yields it)

    Lock all 15 cases including the non-integer / non-finite
    edges that broke the Rust fast path before the wrapper
    normalised cutoff."""
    import math

    P = fnx.path_graph(5)
    expected_path = [0, 1, 2, 3, 4]

    # Empty cases
    for cv in (float("nan"), -float("inf"), -1, 0, 1, 2, 3):
        assert list(fnx.all_simple_paths(P, 0, 4, cutoff=cv)) == []

    # Cases where the path is yielded
    for cv in (4, None, float("inf"), 3.5, 3.7, 4.0, 4.5):
        result = list(fnx.all_simple_paths(P, 0, 4, cutoff=cv))
        assert result == [expected_path], f"cutoff={cv}: got {result}"

    # Cross-check against nx exactly for the boundary fractional
    # cases — must match without TypeError
    P_nx = nx.path_graph(5)
    for cv in (float("nan"), float("inf"), -float("inf"),
               2.5, 3.5, 3.7, 4.0, 4.5):
        f_paths = list(fnx.all_simple_paths(P, 0, 4, cutoff=cv))
        n_paths = list(nx.all_simple_paths(P_nx, 0, 4, cutoff=cv))
        assert f_paths == n_paths, f"cutoff={cv}: fnx={f_paths} != nx={n_paths}"


def test_bfs_edges_handles_nan_inf_float_depth_limit_match_nx():
    """br-r37-c1-bfs-cutfloat: ``bfs_edges`` with non-integer
    ``depth_limit`` (NaN / +inf / finite floats) raised
    ``TypeError`` / ``OverflowError`` on fnx because the Rust
    binding's PyO3 signature requires non-negative int.  nx
    accepts any numeric depth_limit.

    Sister of br-r37-c1-asp-nan (all_simple_paths cutoff).
    Same family of "Rust binding rejects non-int but nx
    accepts" defects across cutoff/depth_limit-accepting
    functions.

    Lock: NaN / -inf / negative → empty; +inf → unbounded;
    finite float → ceil; None → unbounded; non-negative int
    → bounded."""
    P = fnx.path_graph(5)
    full_path_edges = [(0, 1), (1, 2), (2, 3), (3, 4)]

    # Empty cases
    import math
    for dl in (float("nan"), -float("inf"), -1, 0):
        assert list(fnx.bfs_edges(P, 0, depth_limit=dl)) == []

    # Bounded cases
    assert list(fnx.bfs_edges(P, 0, depth_limit=1)) == [(0, 1)]

    # Unbounded / full-path cases
    for dl in (float("inf"), 4, None):
        assert list(fnx.bfs_edges(P, 0, depth_limit=dl)) == full_path_edges

    # Fractional float — ceil
    for dl in (3.5, 3.7, 4.0, 4.5):
        assert list(fnx.bfs_edges(P, 0, depth_limit=dl)) == full_path_edges

    # Direct nx-output cross-check on the boundary cases that
    # broke the Rust fast path before the wrapper normalised
    P_nx = nx.path_graph(5)
    for dl in (float("nan"), float("inf"), -float("inf"),
               2.5, 3.5, 3.7, 4.0):
        f_edges = list(fnx.bfs_edges(P, 0, depth_limit=dl))
        n_edges = list(nx.bfs_edges(P_nx, 0, depth_limit=dl))
        assert f_edges == n_edges, f"depth_limit={dl}: fnx={f_edges} != nx={n_edges}"


def test_cutoff_depth_limit_family_normalized_match_nx():
    """br-r37-c1-bfs-cutfloat-sister: extends br-r37-c1-bfs-
    cutfloat (cycle 137) to the broader cutoff/depth_limit
    family wrapped by the existing negative-int-coercion
    decorator (dfs_edges, dfs_predecessors, dfs_successors,
    dfs_postorder_nodes, dfs_preorder_nodes,
    single_source_shortest_path_length, single_target_shortest_
    path / _length, all_pairs_shortest_path / _length).

    The existing wrapper used ``int(val) < 0`` which raised
    OverflowError on ±inf and TypeError on NaN/float — same
    underlying defect as br-r37-c1-asp-nan / -bfs-cutfloat.
    Re-routed through ``_normalize_bfs_depth_limit`` so all
    these functions handle NaN/±inf/float consistently.

    Lock: each family member yields nx-matching output for the
    boundary cases (NaN / ±inf / fractional float)."""
    import math

    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)

    # dfs_edges: NaN/-inf treated as 0 → first edge only
    for dl in (float("nan"), -float("inf"), -1):
        f = list(fnx.dfs_edges(P, 0, depth_limit=dl))
        n = list(nx.dfs_edges(P_nx, 0, depth_limit=dl))
        assert f == n, f"dfs_edges depth={dl}: fnx={f} != nx={n}"

    # +inf and finite floats — full traversal
    for dl in (float("inf"), 3.5, 4.0):
        f = list(fnx.dfs_edges(P, 0, depth_limit=dl))
        n = list(nx.dfs_edges(P_nx, 0, depth_limit=dl))
        assert f == n

    # Sister wrappers handled by the same decorator
    for fn_name in ("dfs_predecessors", "dfs_successors",
                    "dfs_postorder_nodes", "dfs_preorder_nodes"):
        for dl in (float("inf"), 3.5):
            f = list(getattr(fnx, fn_name)(P, 0, depth_limit=dl))
            n = list(getattr(nx, fn_name)(P_nx, 0, depth_limit=dl))
            assert f == n, f"{fn_name} depth={dl}: fnx={f} != nx={n}"

    # shortest-path-length variants with cutoff=+inf / float
    for dl in (float("inf"), 3.5):
        f = dict(fnx.single_source_shortest_path_length(P, 0, cutoff=dl))
        n = dict(nx.single_source_shortest_path_length(P_nx, 0, cutoff=dl))
        assert f == n

    for dl in (float("inf"), float("nan")):
        f = dict(fnx.all_pairs_shortest_path_length(P, cutoff=dl))
        n = dict(nx.all_pairs_shortest_path_length(P_nx, cutoff=dl))
        assert f == n


def test_dfs_tree_single_source_shortest_path_normalize_nan_inf_match_nx():
    """br-r37-c1-cut-extend: extends br-r37-c1-s86fd (cycle 138)
    to two more cutoff/depth_limit functions still raising
    TypeError/OverflowError on NaN/+inf/float:

      * ``single_source_shortest_path``
      * ``dfs_tree``

    Lock: NaN / -inf / negative → empty / source-only;
    +inf → unbounded (full); finite float → ceil; None → unbounded."""
    import math

    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)

    # single_source_shortest_path
    for c in (float("nan"), -float("inf"), -1):
        f = dict(fnx.single_source_shortest_path(P, 0, cutoff=c))
        n = dict(nx.single_source_shortest_path(P_nx, 0, cutoff=c))
        assert f == n, f"sssp cutoff={c}: fnx={f} != nx={n}"

    for c in (float("inf"), 3.5, 4.0, None):
        f = dict(fnx.single_source_shortest_path(P, 0, cutoff=c))
        n = dict(nx.single_source_shortest_path(P_nx, 0, cutoff=c))
        assert f == n

    # dfs_tree
    for dl in (float("nan"), -float("inf"), -1):
        f = list(fnx.dfs_tree(P, 0, depth_limit=dl).edges())
        n = list(nx.dfs_tree(P_nx, 0, depth_limit=dl).edges())
        assert f == n, f"dfs_tree depth={dl}: fnx={f} != nx={n}"

    for dl in (float("inf"), 3.5, 4.0, None):
        f = list(fnx.dfs_tree(P, 0, depth_limit=dl).edges())
        n = list(nx.dfs_tree(P_nx, 0, depth_limit=dl).edges())
        assert f == n


def test_predecessor_handles_nan_inf_float_cutoff_match_nx():
    """br-r37-c1-pred-cutfloat: ``predecessor`` raised
    TypeError on non-int cutoff (NaN / +inf / fractional float)
    because the Rust binding requires int.  nx's loop is
    ``while nextlevel: level += 1; ...; if cutoff and
    cutoff <= level: break`` — truthy-aware, distinct from
    BFS-shape semantics.

    Mapping (per ``_normalize_predecessor_cutoff``):
      * None / 0 / NaN / +inf → unbounded (None)
      * -inf / negative finite → 1 (nx breaks after level 1)
      * finite float → ceil
      * positive int → unchanged

    Lock: 10 boundary cases + target= and return_seen=
    regressions."""
    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)

    for c in (float("inf"), float("nan"), -float("inf"), -1, 0, 1, 2,
              3.5, 4.0, None):
        f = dict(fnx.predecessor(P, 0, cutoff=c))
        n = dict(nx.predecessor(P_nx, 0, cutoff=c))
        assert f == n, f"predecessor cutoff={c}: fnx={f} != nx={n}"

    # target= path-list form still works
    assert fnx.predecessor(P, 0, target=2, cutoff=3) == [1]
    assert fnx.predecessor(P, 0, target=4) == [3]

    # return_seen= variant still works
    pred, seen = fnx.predecessor(P, 0, cutoff=2, return_seen=True)
    assert pred == {0: [], 1: [0], 2: [1]}
    assert seen == {0: 0, 1: 1, 2: 2}


def test_dijkstra_cutoff_nan_inf_match_nx():
    """br-r37-c1-djk-cutnan: nx Dijkstra's cutoff check is
    ``if d > cutoff: continue`` — for cutoff=NaN, ``d > NaN``
    is always False so the check NEVER skips → unbounded
    result.

    fnx used the inverse form ``if distance <= cutoff`` in
    ``_single_source_dijkstra_cutoff_view`` which is ALSO
    always False for NaN → filters out everything.  Symmetric
    inversion turned nx's "NaN means unbounded" into fnx's
    "NaN means empty".  Symptomatic across:
      * single_source_dijkstra / _path / _path_length
      * all_pairs_dijkstra_path_length (uses single_source
        internally)

    Fix routes NaN and +inf through the unbounded-cutoff
    short-circuit before the filter loop.

    Lock: all 8 boundary cases × 4 dijkstra functions match
    nx exactly."""
    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)

    cases = [
        (float("inf"), {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}),
        (float("nan"), {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}),
        (-float("inf"), {0: 0}),
        (-1, {0: 0}),
        (0, {0: 0}),
        (1, {0: 0, 1: 1}),
        (3.5, {0: 0, 1: 1, 2: 2, 3: 3}),
        (None, {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}),
    ]
    for c, expected_lengths in cases:
        f = dict(fnx.single_source_dijkstra_path_length(P, 0, cutoff=c))
        n = dict(nx.single_source_dijkstra_path_length(P_nx, 0, cutoff=c))
        assert f == n == expected_lengths, f"sssd_pl cutoff={c}: fnx={f} expected={expected_lengths}"

    # all_pairs_dijkstra_path_length matches too (uses single_source)
    for c in (float("nan"), float("inf"), 3.5):
        f = dict((k, dict(v)) for k, v in fnx.all_pairs_dijkstra_path_length(P, cutoff=c))
        n = dict((k, dict(v)) for k, v in nx.all_pairs_dijkstra_path_length(P_nx, cutoff=c))
        assert f == n


def test_multi_source_dijkstra_cutoff_intfloat_order_match_nx():
    """br-r37-c1-msd-cutnan / -intfloat / -order: three sister
    fixes to ``multi_source_dijkstra``:

    1. Cutoff filter ``distance <= cutoff`` was always False for
       NaN → returned empty.  nx uses ``d > cutoff: continue``
       which is also always False for NaN → unbounded.  Same
       symmetric inversion as br-r37-c1-djk-cutnan
       (single-source, cycle 142).

    2. The Rust multi_source binding casts distances to f64;
       nx preserves int when every edge weight is int.  Sister
       of br-ssintfloat (single_source).

    3. The Rust binding returns dict in adjacency-walk order;
       nx emits in priority-queue pop order (ascending
       distance).  Sister of br-r37-c1-62jy2 (single_source).

    Lock: 9 boundary cases for single-source-set + 3 multi-
    source-set cases — values, types, AND iteration order
    must all match nx exactly."""
    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)

    # Single source — values + int dtype + content
    cases = [
        (float("inf"), {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}),
        (float("nan"), {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}),
        (-float("inf"), {0: 0}),
        (-1, {0: 0}),
        (0, {0: 0}),
        (1, {0: 0, 1: 1}),
        (3.5, {0: 0, 1: 1, 2: 2, 3: 3}),
        (None, {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}),
    ]
    for c, expected in cases:
        f = dict(fnx.multi_source_dijkstra_path_length(P, {0}, cutoff=c))
        n = dict(nx.multi_source_dijkstra_path_length(P_nx, {0}, cutoff=c))
        assert f == n == expected, f"cutoff={c}: fnx={f}"
        # int dtype preserved (path graph default = unit weights)
        for v in f.values():
            assert type(v) is int, f"cutoff={c}: dist {v} is {type(v).__name__}"

    # Multi-source — iteration order must match (pop-order =
    # ascending distance).  nx returns sources first (d=0)
    # then expands outward.
    f = dict(fnx.multi_source_dijkstra_path_length(P, {0, 4}))
    n = dict(nx.multi_source_dijkstra_path_length(P_nx, {0, 4}))
    assert list(f.items()) == list(n.items()) == [
        (0, 0), (4, 0), (1, 1), (3, 1), (2, 2)
    ]

    # 3 sources case
    f = dict(fnx.multi_source_dijkstra_path_length(P, {0, 4, 2}))
    n = dict(nx.multi_source_dijkstra_path_length(P_nx, {0, 4, 2}))
    assert list(f.items()) == list(n.items())


def test_edge_connectivity_cutoff_match_nx():
    """br-r37-c1-ec-cutoff: ``edge_connectivity`` with any
    ``cutoff`` value raised ``NetworkXNotImplemented("does
    not support the cutoff parameter")`` from the Rust
    binding.  nx supports cutoff and short-circuits when
    connectivity ≥ cutoff.

    Drop-in callers writing ``nx.edge_connectivity(G, s, t,
    cutoff=N)`` got an error on fnx but a valid number on
    nx.

    Lock: 8 boundary cases × 2 graph types — all return the
    same value as nx; no-cutoff regression preserved."""
    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)
    K = fnx.complete_graph(5)
    K_nx = nx.complete_graph(5)

    # P5 s=0 t=4 (path graph, edge_connectivity = 1)
    for c, expected in [
        (float("nan"), 0),
        (float("inf"), 1),
        (3.5, 1),
        (-1, 0),
        (0, 0),
        (1, 1),
        (2, 1),
        (None, 1),
    ]:
        f = fnx.edge_connectivity(P, 0, 4, cutoff=c)
        n = nx.edge_connectivity(P_nx, 0, 4, cutoff=c)
        assert f == n == expected, f"P5 cutoff={c}: fnx={f} expected={expected}"

    # K5 s=0 t=4 (complete graph, edge_connectivity = 4)
    for c, expected in [(1, 1), (3, 3), (99, 4), (float("inf"), 4)]:
        f = fnx.edge_connectivity(K, 0, 4, cutoff=c)
        n = nx.edge_connectivity(K_nx, 0, 4, cutoff=c)
        assert f == n == expected

    # No-cutoff regression
    assert fnx.edge_connectivity(P) == nx.edge_connectivity(P_nx) == 1
    assert fnx.edge_connectivity(K) == nx.edge_connectivity(K_nx) == 4


def test_disjoint_paths_cutoff_match_nx():
    """br-r37-c1-edp-cutoff: ``edge_disjoint_paths`` and
    ``node_disjoint_paths`` ignored ``cutoff`` (and other
    advanced kwargs flow_func / auxiliary / residual) on the
    Rust fast path.  nx honours cutoff (max augmenting paths)
    and raises ``NetworkXNoPath`` for cutoff < 1
    (NaN / -inf / negative / 0).

    Lock: 9 boundary cutoff values × both functions match nx
    exactly (NaN / -inf / -1 / 0 raise NetworkXNoPath; 1 / 2 /
    3.5 / +inf / None return paths).  Default no-cutoff
    regression preserved on P5 and K5."""
    P = fnx.path_graph(5)
    P_nx = nx.path_graph(5)
    K = fnx.complete_graph(5)
    K_nx = nx.complete_graph(5)

    for fn_name in ("edge_disjoint_paths", "node_disjoint_paths"):
        f_fn = getattr(fnx, fn_name)
        n_fn = getattr(nx, fn_name)

        # Cutoff < 1 → NetworkXNoPath
        for c in (float("nan"), -float("inf"), -1, 0):
            with pytest.raises(nx.NetworkXNoPath):
                list(f_fn(P, 0, 4, cutoff=c))

        # Cutoff >= 1 / unbounded → returns the path
        for c in (1, 2, 3.5, float("inf"), None):
            f = list(f_fn(P, 0, 4, cutoff=c))
            n = list(n_fn(P_nx, 0, 4, cutoff=c))
            assert f == n == [[0, 1, 2, 3, 4]]

        # No-args regression
        assert list(f_fn(P, 0, 4)) == list(n_fn(P_nx, 0, 4))

        # K5 multi-path regression — both libs find 4 disjoint paths
        f_paths = sorted([sorted(p) for p in f_fn(K, 0, 4)])
        n_paths = sorted([sorted(p) for p in n_fn(K_nx, 0, 4)])
        assert f_paths == n_paths
        assert len(f_paths) == 4


def test_pagerank_eigenvector_max_iter_typeerror_no_pyo3_prefix_match_nx():
    """br-r37-c1-pyo3prefix: ``pagerank`` and ``eigenvector_centrality`` must
    raise nx-shaped ``TypeError: 'float' object cannot be interpreted as an
    integer`` (no ``argument 'max_iter':`` PyO3 prefix) for non-integral
    ``max_iter`` values such as NaN, 1.5, or 100.0.

    Pre-fix the Rust binding's unsigned-int signature surfaced
    ``TypeError: argument 'max_iter': 'float' object cannot be interpreted
    as an integer`` — drop-in callers that regex-match nx's exact wording
    failed.  The wrapper now coerces via ``operator.index`` to reproduce
    nx's ``range(max_iter)`` error shape.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    P = fnx.path_graph(5)
    P_nx = nx_mod.path_graph(5)

    expected = "'float' object cannot be interpreted as an integer"

    for fn_name in ("pagerank", "eigenvector_centrality"):
        f_fn = getattr(fnx, fn_name)
        n_fn = getattr(nx_mod, fn_name)
        for bad in (float("nan"), 1.5, 100.0):
            with pytest.raises(TypeError) as f_exc:
                f_fn(P, max_iter=bad)
            with pytest.raises(TypeError) as n_exc:
                n_fn(P_nx, max_iter=bad)
            # Both raise the bare nx-shaped message — no PyO3 prefix.
            assert str(f_exc.value) == expected, (
                f"{fn_name}(max_iter={bad!r}): fnx still has PyO3 prefix: "
                f"{f_exc.value!r}"
            )
            assert str(n_exc.value) == expected
        # Sanity: integer max_iter still passes through normally.
        # Use 1000 to ensure convergence on undirected path_graph for both
        # pagerank (which converges quickly) and eigenvector_centrality
        # (which needs more iterations on bipartite-like structure).
        f_fn(P, max_iter=1000)
        n_fn(P_nx, max_iter=1000)


def test_eigenvector_centrality_numpy_max_iter_validation_match_nx():
    """br-r37-c1-evnumiter: ``eigenvector_centrality_numpy`` must validate
    ``max_iter`` the same way nx does — nx delegates to
    ``scipy.sparse.linalg.eigs`` whose input validator does ``int(maxiter)``
    and ``maxiter <= 0``, surfacing distinct exception types and messages
    for NaN / +inf / -inf / 0 / negatives.

    Pre-fix the fnx implementation used ``numpy.linalg.eig`` (dense full
    eigendecomposition) and silently ignored ``max_iter`` entirely — bad
    inputs that nx rejects were accepted, masking caller bugs.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    P = fnx.path_graph(5)
    P_nx = nx_mod.path_graph(5)

    # NaN: ValueError (from int(NaN))
    with pytest.raises(ValueError, match="cannot convert float NaN"):
        fnx.eigenvector_centrality_numpy(P, max_iter=float("nan"))
    with pytest.raises(ValueError, match="cannot convert float NaN"):
        nx_mod.eigenvector_centrality_numpy(P_nx, max_iter=float("nan"))

    # +inf: OverflowError (from int(+inf))
    with pytest.raises(OverflowError, match="cannot convert float infinity"):
        fnx.eigenvector_centrality_numpy(P, max_iter=float("inf"))
    with pytest.raises(OverflowError, match="cannot convert float infinity"):
        nx_mod.eigenvector_centrality_numpy(P_nx, max_iter=float("inf"))

    # -inf: ValueError (positivity check fires before int())
    with pytest.raises(ValueError, match="maxiter must be positive"):
        fnx.eigenvector_centrality_numpy(P, max_iter=float("-inf"))
    with pytest.raises(ValueError, match="maxiter must be positive"):
        nx_mod.eigenvector_centrality_numpy(P_nx, max_iter=float("-inf"))

    # Zero / negative: ValueError with same message
    for bad in (0, -1):
        with pytest.raises(ValueError, match="maxiter must be positive"):
            fnx.eigenvector_centrality_numpy(P, max_iter=bad)
        with pytest.raises(ValueError, match="maxiter must be positive"):
            nx_mod.eigenvector_centrality_numpy(P_nx, max_iter=bad)

    # Sanity: integral floats and ints still pass
    fnx.eigenvector_centrality_numpy(P, max_iter=50)
    fnx.eigenvector_centrality_numpy(P, max_iter=1.5)  # nx accepts via int()
    fnx.eigenvector_centrality_numpy(P, max_iter=None)


def test_algorithms_submodule_import_paths_match_nx():
    """br-r37-c1-algsubmod: ``from franken_networkx.algorithms.X import Y``
    must work for every nx.algorithms submodule.

    Pre-fix only attribute access (``fnx.algorithms.flow``) worked; the
    import-from-submodule form raised ModuleNotFoundError because nx's
    submodules were not registered in ``sys.modules`` under the
    franken_networkx prefix.  Drop-in code that does
    ``from networkx.algorithms.flow import maximum_flow`` and naively
    text-substitutes ``networkx`` -> ``franken_networkx`` was broken.

    Fix: walk ``networkx.algorithms`` recursively and alias each
    submodule into ``sys.modules`` under the ``franken_networkx``
    prefix.  Verifies a representative sample of 1- and 2-deep paths.
    """
    import importlib
    import networkx as nx_mod

    # 1-deep paths — sample of high-traffic submodules
    for sub in (
        "approximation",
        "assortativity",
        "bipartite",
        "centrality",
        "community",
        "components",
        "connectivity",
        "flow",
        "isomorphism",
        "link_prediction",
        "matching",
        "operators",
        "shortest_paths",
        "similarity",
        "tree",
        "traversal",
    ):
        fnx_path = f"franken_networkx.algorithms.{sub}"
        nx_path = f"networkx.algorithms.{sub}"
        fnx_mod = importlib.import_module(fnx_path)
        nx_sub = importlib.import_module(nx_path)
        assert fnx_mod is nx_sub, (
            f"{fnx_path} should alias {nx_path} but got distinct objects"
        )

    # 2-deep paths — subpackages of subpackages
    for path in (
        "tree.branchings",
        "tree.mst",
        "shortest_paths.weighted",
        "shortest_paths.unweighted",
        "shortest_paths.generic",
        "flow.maxflow",
    ):
        fnx_mod = importlib.import_module(f"franken_networkx.algorithms.{path}")
        nx_sub = importlib.import_module(f"networkx.algorithms.{path}")
        assert fnx_mod is nx_sub

    # The from-import form — naive text-substitution drop-in
    from franken_networkx.algorithms.flow import maximum_flow
    from franken_networkx.algorithms.approximation import min_weighted_vertex_cover
    from franken_networkx.algorithms.tree.branchings import branching_weight

    assert maximum_flow is nx_mod.algorithms.flow.maximum_flow
    assert (
        min_weighted_vertex_cover
        is nx_mod.algorithms.approximation.min_weighted_vertex_cover
    )
    assert (
        branching_weight is nx_mod.algorithms.tree.branchings.branching_weight
    )


def test_bellman_ford_nan_inf_edge_weight_match_nx():
    """br-r37-c1-bfnannumeric: ``bellman_ford_path``,
    ``bellman_ford_path_length``, and
    ``bellman_ford_predecessor_and_distance`` must treat NaN / +/-inf
    edge weights the way nx does.

    nx's relaxation uses ``candidate < current`` where ``current``
    starts at ``inf``.  ``NaN < inf`` is False (NaN comparisons),
    ``inf < inf`` is False, so neither relaxes — the target stays
    out of the distance map and the function raises NetworkXNoPath.
    For ``-inf`` edges nx detects a negative cycle and raises
    NetworkXUnbounded.

    Pre-fix the fnx Rust path wrote NaN through to the distance map
    (because the only short-circuit was ``current is None`` first
    visit), and returned ``inf`` / ``-inf`` paths instead of the
    NetworkXNoPath / NetworkXUnbounded contracts.  Worse: when a
    NaN edge sat alongside a valid alternate path, fnx's algorithm
    *preferred* the NaN edge and returned ``nan`` instead of using
    the alternate.  The fix detects NaN/inf weights via
    ``_has_nan_or_inf_edge_weight`` and routes to nx.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    def _setup(w, lib):
        P = lib.path_graph(3)
        P[0][1]["weight"] = w
        return P

    # NaN: NetworkXNoPath
    for fn_name in (
        "bellman_ford_path",
        "bellman_ford_path_length",
    ):
        for w_label, w_val, exc_type in [
            ("NaN", float("nan"), nx_mod.NetworkXNoPath),
            ("+inf", float("inf"), nx_mod.NetworkXNoPath),
            ("-inf", float("-inf"), nx_mod.NetworkXUnbounded),
        ]:
            P_f, P_n = _setup(w_val, fnx), _setup(w_val, nx_mod)
            with pytest.raises(exc_type):
                getattr(fnx, fn_name)(P_f, 0, 2, weight="weight")
            with pytest.raises(exc_type):
                getattr(nx_mod, fn_name)(P_n, 0, 2, weight="weight")

    # bellman_ford_predecessor_and_distance with NaN: only source-self in dist
    P_f = _setup(float("nan"), fnx)
    P_n = _setup(float("nan"), nx_mod)
    f_pred, f_dist = fnx.bellman_ford_predecessor_and_distance(P_f, 0, weight="weight")
    n_pred, n_dist = nx_mod.bellman_ford_predecessor_and_distance(P_n, 0, weight="weight")
    assert f_dist == n_dist == {0: 0}
    assert f_pred == n_pred == {0: []}

    # NaN-on-alternate-edge: fnx must use the valid path, not the NaN edge
    G_f = fnx.Graph()
    G_f.add_weighted_edges_from([(0, 1, 1.0), (1, 2, 1.0), (0, 2, float("nan"))])
    G_n = nx_mod.Graph()
    G_n.add_weighted_edges_from([(0, 1, 1.0), (1, 2, 1.0), (0, 2, float("nan"))])
    assert fnx.bellman_ford_path_length(G_f, 0, 2, weight="weight") == 2.0
    assert nx_mod.bellman_ford_path_length(G_n, 0, 2, weight="weight") == 2.0

    # Sanity: ordinary positive weights still take the fast path
    G_f2 = fnx.Graph()
    G_f2.add_weighted_edges_from([(0, 1, 2.0), (1, 2, 3.0)])
    G_n2 = nx_mod.Graph()
    G_n2.add_weighted_edges_from([(0, 1, 2.0), (1, 2, 3.0)])
    assert fnx.bellman_ford_path_length(G_f2, 0, 2, weight="weight") == 5.0
    assert nx_mod.bellman_ford_path_length(G_n2, 0, 2, weight="weight") == 5.0


def test_is_d_separator_scalar_args_match_nx():
    """br-r37-c1-dsepscalar / dsepudt: ``is_d_separator`` and
    ``is_minimal_d_separator`` must accept scalar node arguments
    (``is_d_separator(G, 0, 2, 1)``) and raise NetworkXNotImplemented
    on undirected input — both matching nx's contract.

    Pre-fix:
      - ``is_d_separator(G, 0, 2, 1)`` raised
        ``TypeError: 'int' object is not iterable``
        from a bare ``set(0)`` call; nx normalizes via
        ``{x} if x in G else x`` and returned ``False``.
      - On undirected G, fnx raised plain
        ``NetworkXError('is_d_separator requires a DiGraph')``;
        nx is decorated with ``@not_implemented_for('undirected')``
        and raises ``NetworkXNotImplemented``.
      - ``is_minimal_d_separator`` reused the same broken
        normalization through its delegate to ``is_d_separator``
        and via its own ``z = set(z)`` line.

    Fix mirrors nx's exact normalize+disjoint+set_v block (with
    the same try/except TypeError -> NodeNotFound translation) and
    adds an explicit ``G.is_directed()`` guard.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    DG_f = fnx.DiGraph([(0, 1), (1, 2), (0, 2)])
    DG_n = nx_mod.DiGraph([(0, 1), (1, 2), (0, 2)])

    # Scalar args: was TypeError, now matches nx
    assert fnx.is_d_separator(DG_f, 0, 2, 1) is False
    assert nx_mod.is_d_separator(DG_n, 0, 2, 1) is False
    assert fnx.is_minimal_d_separator(DG_f, 0, 2, 1) is False
    assert nx_mod.is_minimal_d_separator(DG_n, 0, 2, 1) is False

    # Mixed scalar + set
    assert fnx.is_d_separator(DG_f, 0, 2, {1}) is False
    assert nx_mod.is_d_separator(DG_n, 0, 2, {1}) is False

    # Empty z
    assert fnx.is_d_separator(DG_f, 0, 2, set()) is False
    assert nx_mod.is_d_separator(DG_n, 0, 2, set()) is False

    # Frozenset
    assert fnx.is_d_separator(DG_f, {0}, {2}, frozenset({1})) is False
    assert nx_mod.is_d_separator(DG_n, {0}, {2}, frozenset({1})) is False

    # Node not in graph -> NodeNotFound (matches nx's translated TypeError)
    with pytest.raises(nx_mod.NodeNotFound):
        fnx.is_d_separator(DG_f, 99, 0, set())
    with pytest.raises(nx_mod.NodeNotFound):
        nx_mod.is_d_separator(DG_n, 99, 0, set())

    # Overlapping sets -> NetworkXError
    with pytest.raises(nx_mod.NetworkXError, match="not disjoint"):
        fnx.is_d_separator(DG_f, 0, 0, 1)
    with pytest.raises(nx_mod.NetworkXError, match="not disjoint"):
        nx_mod.is_d_separator(DG_n, 0, 0, 1)

    # Undirected -> NetworkXNotImplemented (was NetworkXError pre-fix)
    G_f_und = fnx.Graph([(0, 1)])
    G_n_und = nx_mod.Graph([(0, 1)])
    with pytest.raises(nx_mod.NetworkXNotImplemented):
        fnx.is_d_separator(G_f_und, {0}, {1}, set())
    with pytest.raises(nx_mod.NetworkXNotImplemented):
        nx_mod.is_d_separator(G_n_und, {0}, {1}, set())


def test_maximal_independent_set_seed_and_message_match_nx():
    """br-r37-c1-misseed: ``maximal_independent_set`` must accept any
    int (or None) for ``seed`` like nx does — including negative ints
    and ints exceeding u64 — and reject NaN with the same
    ``ValueError("nan cannot be used to generate a random.Random
    instance")`` wording.

    Pre-fix the Rust binding declared ``seed: u64`` and raised
    ``OverflowError("can't convert negative int to unsigned")`` on
    negative seeds and the PyO3-prefixed ``TypeError("argument
    'seed': 'float' object cannot be interpreted as an integer")``
    on NaN.

    Also: nx's ``NetworkXUnfeasible`` messages format the offending
    nodes as a set repr (``{99}``); fnx's Rust path used a quoted
    string-list (``["99"]``).  Verify the wrapper re-raises with
    nx's wording.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Negative seeds: must succeed (any maximal independent set is fine)
    G_f = fnx.cycle_graph(5)
    G_n = nx_mod.cycle_graph(5)
    for bad_seed in (-1, -100, -(2**63)):
        result_f = fnx.maximal_independent_set(G_f, seed=bad_seed)
        result_n = nx_mod.maximal_independent_set(G_n, seed=bad_seed)
        # Both must succeed and return a maximal independent set
        assert isinstance(result_f, list)
        assert isinstance(result_n, list)
        # Independence check
        for u in result_f:
            for v in result_f:
                if u != v:
                    assert v not in G_f[u]

    # Very large positive seeds also work
    fnx.maximal_independent_set(G_f, seed=2**128)
    nx_mod.maximal_independent_set(G_n, seed=2**128)

    # NaN seed -> matching ValueError
    with pytest.raises(ValueError, match="nan cannot be used"):
        fnx.maximal_independent_set(G_f, seed=float("nan"))
    with pytest.raises(ValueError, match="nan cannot be used"):
        nx_mod.maximal_independent_set(G_n, seed=float("nan"))

    # NetworkXUnfeasible message format: set-repr matches nx
    G_f4 = fnx.path_graph(5)
    G_n4 = nx_mod.path_graph(5)
    for bad_nodes in ([99], [0, 99]):
        with pytest.raises(nx_mod.NetworkXUnfeasible) as f_exc:
            fnx.maximal_independent_set(G_f4, bad_nodes, seed=42)
        with pytest.raises(nx_mod.NetworkXUnfeasible) as n_exc:
            nx_mod.maximal_independent_set(G_n4, bad_nodes, seed=42)
        assert str(f_exc.value) == str(n_exc.value), (
            f"message mismatch for bad_nodes={bad_nodes}: "
            f"fnx={f_exc.value!r} vs nx={n_exc.value!r}"
        )

    # Adjacent nodes -> "is not an independent set of G"
    with pytest.raises(nx_mod.NetworkXUnfeasible) as f_exc:
        fnx.maximal_independent_set(G_f4, [0, 1], seed=42)
    with pytest.raises(nx_mod.NetworkXUnfeasible) as n_exc:
        nx_mod.maximal_independent_set(G_n4, [0, 1], seed=42)
    assert str(f_exc.value) == str(n_exc.value)


def test_random_generators_seed_handling_match_nx():
    """br-r37-c1-rustseed: random graph generators must accept any int
    (including negatives and ints exceeding u64) for ``seed`` and
    raise nx's ``ValueError("nan cannot be used to generate a
    random.Random instance")`` on NaN.

    Pre-fix the Rust bindings declared ``seed: u64`` and raised:
      - ``OverflowError("can't convert negative int to unsigned")`` on
        negative seeds (erdos_renyi_graph, watts_strogatz_graph,
        random_regular_graph, newman_watts_strogatz_graph,
        connected_watts_strogatz_graph)
      - ``TypeError("argument 'seed': 'float' object cannot be
        interpreted as an integer")`` (PyO3 prefix) on NaN

    Two pure-Python wrappers (``gnm_random_graph``,
    ``random_geometric_graph``) silently accepted NaN via
    ``random.Random(NaN)``; nx surfaces ValueError from the numpy
    seeding path.

    Fix: the centralized ``_native_random_seed`` helper now hashes
    negative / oversized ints to u64 range and raises nx-shaped
    ValueError on NaN.  The two pure-Python wrappers add an explicit
    NaN guard.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Negative/large seeds must succeed (output may differ between
    # libs because RNG implementations differ; we only verify
    # acceptance, not exact-output parity).
    for fn_name, args in [
        ("erdos_renyi_graph", (5, 0.5)),
        ("watts_strogatz_graph", (10, 4, 0.1)),
        ("random_regular_graph", (3, 6)),
        ("newman_watts_strogatz_graph", (10, 4, 0.1)),
        ("connected_watts_strogatz_graph", (10, 4, 0.1)),
        ("gnm_random_graph", (5, 3)),
        ("random_geometric_graph", (10, 0.5)),
    ]:
        for bad_seed in (-1, -100, -(2**63), 2**128):
            getattr(fnx, fn_name)(*args, seed=bad_seed)
            getattr(nx_mod, fn_name)(*args, seed=bad_seed)

    # NaN -> matching ValueError across the affected family
    for fn_name, args in [
        ("erdos_renyi_graph", (5, 0.5)),
        ("watts_strogatz_graph", (10, 4, 0.1)),
        ("random_regular_graph", (3, 6)),
        ("newman_watts_strogatz_graph", (10, 4, 0.1)),
        ("connected_watts_strogatz_graph", (10, 4, 0.1)),
        ("gnm_random_graph", (5, 3)),
        ("random_geometric_graph", (10, 0.5)),
    ]:
        with pytest.raises(ValueError, match="nan cannot be used"):
            getattr(fnx, fn_name)(*args, seed=float("nan"))
        with pytest.raises(ValueError, match="nan cannot be used"):
            getattr(nx_mod, fn_name)(*args, seed=float("nan"))


def test_dual_ba_and_relaxed_caveman_nan_seed_match_nx():
    """br-r37-c1-rustseed (sister): two more pure-Python wrappers that
    silently accepted NaN seed via ``random.Random(NaN)`` while nx
    raises ``ValueError("nan cannot be used to generate a
    random.Random instance")``:

      - ``dual_barabasi_albert_graph``
      - ``relaxed_caveman_graph``

    Same fix shape as the gnm_random_graph / random_geometric_graph
    NaN guards in cycle 152 — these two wrappers also bypass
    ``_native_random_seed`` because they call ``random.Random(seed)``
    directly.  Add explicit NaN guards.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # NaN -> ValueError with nx's exact wording
    with pytest.raises(ValueError, match="nan cannot be used"):
        fnx.dual_barabasi_albert_graph(10, 2, 3, 0.5, seed=float("nan"))
    with pytest.raises(ValueError, match="nan cannot be used"):
        nx_mod.dual_barabasi_albert_graph(10, 2, 3, 0.5, seed=float("nan"))

    with pytest.raises(ValueError, match="nan cannot be used"):
        fnx.relaxed_caveman_graph(3, 4, 0.1, seed=float("nan"))
    with pytest.raises(ValueError, match="nan cannot be used"):
        nx_mod.relaxed_caveman_graph(3, 4, 0.1, seed=float("nan"))

    # Sanity: valid seeds still work
    fnx.dual_barabasi_albert_graph(10, 2, 3, 0.5, seed=42)
    fnx.dual_barabasi_albert_graph(10, 2, 3, 0.5, seed=-1)
    fnx.relaxed_caveman_graph(3, 4, 0.1, seed=42)
    fnx.relaxed_caveman_graph(3, 4, 0.1, seed=-1)


def test_graph_size_callable_weight_match_nx():
    """br-r37-c1-sizeweight: ``Graph.size(weight=...)`` must accept
    callable or arbitrary-key (non-string) ``weight`` like nx does.

    Pre-fix the Rust binding's ``weight: str`` PyO3 signature raised
    ``TypeError: argument 'weight': 'function' object is not an
    instance of 'str'`` (and similar for int / tuple) on any
    non-string weight.  nx's ``size`` dispatches through
    ``self.degree(weight=...)`` which natively handles callable +
    arbitrary-key + string forms via the canonical
    ``sum(d for _, d in self.degree(weight=...)) / 2`` formula.

    The fix routes non-string weights through the same formula in
    Python, only delegating to the Rust binding for the str case.
    Verifies parity across Graph / DiGraph / MultiGraph / MultiDiGraph.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    cases = [
        ("Graph", fnx.Graph, nx_mod.Graph, [(0, 1), (1, 2), (2, 0)]),
        ("DiGraph", fnx.DiGraph, nx_mod.DiGraph, [(0, 1), (1, 2)]),
        ("MultiGraph", fnx.MultiGraph, nx_mod.MultiGraph, [(0, 1), (0, 1), (1, 2)]),
        ("MultiDiGraph", fnx.MultiDiGraph, nx_mod.MultiDiGraph, [(0, 1), (0, 1), (1, 2)]),
    ]

    for name, ctor_f, ctor_n, edges in cases:
        G_f = ctor_f()
        G_n = ctor_n()
        for u, v in edges:
            G_f.add_edge(u, v, weight=10)
            G_n.add_edge(u, v, weight=10)

        # weight=None (int)
        assert G_f.size() == G_n.size()

        # weight="weight" (string-based weighted sum, fast path)
        assert G_f.size(weight="weight") == G_n.size(weight="weight")

        # callable weight — nx's degree treats it as a key-lookup
        # default-1 (the callable is never invoked), giving edge count.
        assert G_f.size(weight=lambda u, v, d: 2) == G_n.size(
            weight=lambda u, v, d: 2
        )

        # arbitrary-key weight (missing on every edge -> default 1)
        assert G_f.size(weight=5) == G_n.size(weight=5)
        assert G_f.size(weight=("w",)) == G_n.size(weight=("w",))


def test_attr_matrix_missing_attr_raises_keyerror_match_nx():
    """br-r37-c1-attrmtx: ``attr_matrix`` must raise ``KeyError`` when
    ``edge_attr`` or ``node_attr`` names an attribute that doesn't
    exist on every edge / node — except for the special case
    ``edge_attr=='weight'`` which nx defaults to 1.

    Pre-fix fnx used ``data.get(attr, 1)`` / ``G.nodes[n].get(attr, n)``
    everywhere, silently swallowing missing attributes and returning a
    default-1 / node-as-label matrix.  This masked caller bugs.

    Fix: mirror nx's ``_edge_value`` / ``_node_value`` helpers (direct
    subscript that raises KeyError, plus the ``edge_attr=='weight'``
    default and the callable-resolver branches).
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    G_f = fnx.cycle_graph(4)
    G_n = nx_mod.cycle_graph(4)
    G_f[0][1]["weight"] = 5
    G_n[0][1]["weight"] = 5
    for u, c in [(0, "red"), (1, "blue"), (2, "red"), (3, "blue")]:
        G_f.nodes[u]["color"] = c
        G_n.nodes[u]["color"] = c

    # Missing edge_attr -> KeyError (was silent default-1)
    with pytest.raises(KeyError):
        fnx.attr_matrix(G_f, edge_attr="nope")
    with pytest.raises(KeyError):
        nx_mod.attr_matrix(G_n, edge_attr="nope")

    # Missing node_attr -> KeyError (was silent node-as-label)
    with pytest.raises(KeyError):
        fnx.attr_matrix(G_f, node_attr="missing")
    with pytest.raises(KeyError):
        nx_mod.attr_matrix(G_n, node_attr="missing")

    # Special case: edge_attr="weight" with partial coverage uses default 1
    f_M, _ = fnx.attr_matrix(G_f, edge_attr="weight")
    n_M, _ = nx_mod.attr_matrix(G_n, edge_attr="weight")
    assert f_M.tolist() == n_M.tolist()

    # Callable edge_attr / node_attr work
    f_M, _ = fnx.attr_matrix(G_f, edge_attr=lambda u, v: 99)
    n_M, _ = nx_mod.attr_matrix(G_n, edge_attr=lambda u, v: 99)
    assert f_M.tolist() == n_M.tolist()

    f_M, _ = fnx.attr_matrix(G_f, node_attr=lambda u: u % 2)
    n_M, _ = nx_mod.attr_matrix(G_n, node_attr=lambda u: u % 2)
    assert f_M.tolist() == n_M.tolist()

    # MultiGraph: sum-over-keys of named attribute
    M_f = fnx.MultiGraph()
    M_f.add_edges_from([(0, 1, {"w": 2}), (0, 1, {"w": 3}), (1, 2, {"w": 5})])
    M_n = nx_mod.MultiGraph()
    M_n.add_edges_from([(0, 1, {"w": 2}), (0, 1, {"w": 3}), (1, 2, {"w": 5})])
    f_M, _ = fnx.attr_matrix(M_f, edge_attr="w")
    n_M, _ = nx_mod.attr_matrix(M_n, edge_attr="w")
    assert f_M.tolist() == n_M.tolist()


def test_edgeview_contains_match_nx_semantics():
    """br-r37-c1-edgeviewcontains: ``e in G.edges`` must match nx's
    permissive containment semantics across all four graph types.

    Pre-fix divergences:
      - ``Graph.edges`` (Rust EdgeView): raised
        ``TypeError("edge must be a (u, v) tuple")`` on str / list /
        non-tuple input — nx returns False for str, True for matching
        list, and propagates ``'X' object is not subscriptable``
        TypeError for non-subscriptable values.
      - ``DiGraph.edges``: too lenient — caught both TypeError and
        ValueError on bad shapes, returning False.  nx propagates
        ValueError ('too many values to unpack' / 'not enough') and
        TypeError ('cannot unpack non-iterable').
      - ``MultiGraph.edges`` / ``MultiDiGraph.edges``: rejected
        ``[0, 1]`` (list) via ``isinstance(tuple)`` guard — nx accepts.

    Fix:
      - Wrap the Rust ``EdgeView.__contains__`` to fall back through
        ``e[:2]`` when the bare lookup raises TypeError (matches nx's
        Graph EdgeView pattern).
      - Tighten ``_DiGraphEdgeView.__contains__`` to use ``u, v = e``
        and only catch KeyError / TypeError (matches nx OutEdgeView).
      - Replace ``isinstance(tuple)`` guards in
        ``_MultiGraphEdgeView`` / ``_MultiDiGraphEdgeView`` with
        ``len(e)``-dispatch (matches nx MultiEdgeView).
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Graph: permissive — non-edge str/list returns False, non-
    # subscriptable raises TypeError.
    G_f = fnx.path_graph(3)
    G_n = nx_mod.path_graph(3)
    assert ("foo" in G_f.edges) == ("foo" in G_n.edges) == False
    assert ([0, 1] in G_f.edges) == ([0, 1] in G_n.edges) == True
    assert ((0, 1) in G_f.edges) == ((0, 1) in G_n.edges) == True
    with pytest.raises(TypeError, match="not subscriptable"):
        123 in G_f.edges
    with pytest.raises(TypeError, match="not subscriptable"):
        123 in G_n.edges

    # DiGraph: stricter — bad shapes propagate.
    DG_f = fnx.DiGraph([(0, 1), (1, 2)])
    DG_n = nx_mod.DiGraph([(0, 1), (1, 2)])
    assert ((0, 1) in DG_f.edges) == ((0, 1) in DG_n.edges) == True
    assert ([0, 1] in DG_f.edges) == ([0, 1] in DG_n.edges) == True
    with pytest.raises(ValueError):
        "foo" in DG_f.edges
    with pytest.raises(ValueError):
        "foo" in DG_n.edges
    with pytest.raises(TypeError, match="cannot unpack"):
        123 in DG_f.edges
    with pytest.raises(TypeError, match="cannot unpack"):
        123 in DG_n.edges

    # MultiGraph: len-dispatch.
    M_f = fnx.MultiGraph([(0, 1), (0, 1)])
    M_n = nx_mod.MultiGraph([(0, 1), (0, 1)])
    assert ((0, 1) in M_f.edges) == ((0, 1) in M_n.edges) == True
    assert ([0, 1] in M_f.edges) == ([0, 1] in M_n.edges) == True
    assert ((0, 1, 0) in M_f.edges) == ((0, 1, 0) in M_n.edges) == True
    with pytest.raises(ValueError, match="length 2 or 3"):
        (0,) in M_f.edges
    with pytest.raises(ValueError, match="length 2 or 3"):
        (0,) in M_n.edges
    with pytest.raises(TypeError, match="has no len"):
        123 in M_f.edges
    with pytest.raises(TypeError, match="has no len"):
        123 in M_n.edges

    # MultiDiGraph: same len-dispatch.
    MD_f = fnx.MultiDiGraph([(0, 1), (0, 1)])
    MD_n = nx_mod.MultiDiGraph([(0, 1), (0, 1)])
    assert ([0, 1] in MD_f.edges) == ([0, 1] in MD_n.edges) == True
    assert ((0, 1, 0) in MD_f.edges) == ((0, 1, 0) in MD_n.edges) == True


def test_view_class_names_match_nx():
    """br-r37-c1-viewnames: ``type(G.edges).__name__`` and
    ``type(G.nodes).__name__`` must match nx exactly across all four
    graph types so introspecting code (test fixtures, debug repr,
    drop-in libraries that branch on view class names) works.

    Pre-fix mismatches:
      - DiGraph.edges:    '_DiGraphEdgeView'      vs nx 'OutEdgeView'
      - MultiGraph.edges: '_MultiGraphEdgeView'   vs nx 'MultiEdgeView'
      - MultiDiGraph.edges: '_MultiDiGraphEdgeView' vs nx 'OutMultiEdgeView'
      - DiGraph.nodes:    'DiNodeView'            vs nx 'NodeView'
      - MultiGraph.nodes: 'MultiGraphNodeView'    vs nx 'NodeView'
      - MultiDiGraph.nodes: 'MultiDiGraphNodeView' vs nx 'NodeView'

    Fix: rename ``__name__`` only (keep ``__qualname__`` so pickle's
    ``module.qualname`` lookup still finds the class).  The existing
    ``__reduce__`` snapshot semantic on these views handles pickle
    independent of the rename.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    cases = [
        ("Graph", fnx.Graph, nx_mod.Graph, [(0, 1)]),
        ("DiGraph", fnx.DiGraph, nx_mod.DiGraph, [(0, 1)]),
        ("MultiGraph", fnx.MultiGraph, nx_mod.MultiGraph, [(0, 1)]),
        ("MultiDiGraph", fnx.MultiDiGraph, nx_mod.MultiDiGraph, [(0, 1)]),
    ]
    for name, ctor_f, ctor_n, edges in cases:
        G_f = ctor_f()
        G_n = ctor_n()
        for u, v in edges:
            G_f.add_edge(u, v)
            G_n.add_edge(u, v)
        assert (
            type(G_f.edges).__name__ == type(G_n.edges).__name__
        ), (
            f"{name}.edges class name mismatch: "
            f"fnx={type(G_f.edges).__name__!r} vs "
            f"nx={type(G_n.edges).__name__!r}"
        )
        assert (
            type(G_f.nodes).__name__ == type(G_n.nodes).__name__
        ), (
            f"{name}.nodes class name mismatch: "
            f"fnx={type(G_f.nodes).__name__!r} vs "
            f"nx={type(G_n.nodes).__name__!r}"
        )

    # Sanity: pickle round-trip still works (the rename only touches
    # __name__, not __qualname__, so pickle's class-lookup path is
    # unchanged).
    import pickle
    G = fnx.Graph()
    G.add_edges_from([(0, 1), (1, 2)])
    DG = fnx.DiGraph()
    DG.add_edges_from([(0, 1), (1, 2)])
    M = fnx.MultiGraph()
    M.add_edges_from([(0, 1), (0, 1)])
    for view in (G.edges, G.degree, DG.edges, DG.degree, M.edges):
        pickle.dumps(view)


def test_in_out_edges_contains_match_nx():
    """br-r37-c1-iemvcontains: ``e in DG.in_edges`` / ``e in DG.out_edges``
    (and the multidigraph variants) must match nx's
    InEdgeView.__contains__ / OutEdgeView.__contains__ pattern.

    Pre-fix the shared ``_DiEdgeMethodView.__contains__`` did
    ``item in self._method(self._graph)`` which materialized the result
    as a list and used element-equality.  That meant:
      - ``[0, 1] in DG.in_edges`` returned False (list != tuple)
      - ``"foo" in DG.in_edges`` returned False
      - ``123 in DG.in_edges`` returned False
    nx accepts list-as-edge-spec (length-2 iterable) and propagates
    ValueError on length mismatch / TypeError on non-iterable; for
    multigraphs it dispatches on len(e).

    Same defect family as cycle 156's br-r37-c1-edgeviewcontains
    fix on the *forward* edge views; this is the in/out-method-view
    sister.  Fix mirrors the forward-view nx semantics.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    DG_f = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    DG_n = nx_mod.DiGraph([(0, 1), (1, 2), (2, 3)])

    # Tuples — present and absent
    assert ((0, 1) in DG_f.in_edges) == ((0, 1) in DG_n.in_edges) == True
    assert ((1, 0) in DG_f.in_edges) == ((1, 0) in DG_n.in_edges) == False
    assert ((99, 100) in DG_f.in_edges) == ((99, 100) in DG_n.in_edges) == False

    # Lists — accepted as length-2 iterable
    assert ([0, 1] in DG_f.in_edges) == ([0, 1] in DG_n.in_edges) == True
    assert ([0, 1] in DG_f.out_edges) == ([0, 1] in DG_n.out_edges) == True

    # Bad shapes propagate ValueError / TypeError matching nx
    with pytest.raises(ValueError):
        "foo" in DG_f.in_edges
    with pytest.raises(ValueError):
        "foo" in DG_n.in_edges
    with pytest.raises(TypeError, match="cannot unpack"):
        123 in DG_f.in_edges
    with pytest.raises(TypeError, match="cannot unpack"):
        123 in DG_n.in_edges

    # MultiDiGraph: len-dispatch
    MD_f = fnx.MultiDiGraph([(0, 1), (0, 1), (1, 2)])
    MD_n = nx_mod.MultiDiGraph([(0, 1), (0, 1), (1, 2)])
    assert ([0, 1] in MD_f.in_edges) == ([0, 1] in MD_n.in_edges) == True
    assert ((0, 1, 0) in MD_f.in_edges) == ((0, 1, 0) in MD_n.in_edges) == True
    assert ((0, 1, 99) in MD_f.in_edges) == ((0, 1, 99) in MD_n.in_edges) == False
    with pytest.raises(TypeError, match="has no len"):
        123 in MD_f.in_edges
    with pytest.raises(TypeError, match="has no len"):
        123 in MD_n.in_edges


def test_in_out_edges_call_returns_live_view_match_nx():
    """br-r37-c1-iemvcall: ``DG.in_edges()`` (no args) must return the
    live view, not a stale snapshot list.

    Pre-fix ``DG.in_edges()`` materialized a Python list via the Rust
    method:
      - ``[0,1] in DG.in_edges()`` returned False (plain list ==)
      - ``"foo" in DG.in_edges()`` returned False (no error)
      - mutating the graph did NOT update the previously-returned list
    nx's call form returns the same InEdgeView object as the property
    (``DG.in_edges() is DG.in_edges`` holds).

    Fix: ``_DiEdgeMethodView.__call__`` short-circuits to return
    ``self`` when invoked with no args, so the call form has the same
    live-view + nx-shaped __contains__ semantics as the attribute
    form.  Filtered calls (``in_edges([0])`` / ``data=True`` / etc.)
    still return the snapshot list — that's a separate parity gap.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    DG_f = fnx.DiGraph([(0, 1), (1, 2)])
    DG_n = nx_mod.DiGraph([(0, 1), (1, 2)])

    # Containment via the call form must now match nx
    assert ((0, 1) in DG_f.in_edges()) == ((0, 1) in DG_n.in_edges()) == True
    assert ([0, 1] in DG_f.in_edges()) == ([0, 1] in DG_n.in_edges()) == True
    with pytest.raises(ValueError):
        "foo" in DG_f.in_edges()
    with pytest.raises(ValueError):
        "foo" in DG_n.in_edges()
    with pytest.raises(TypeError, match="cannot unpack"):
        123 in DG_f.in_edges()
    with pytest.raises(TypeError, match="cannot unpack"):
        123 in DG_n.in_edges()

    # Live-view semantics: a previously-returned in_edges() reflects
    # later graph modifications.
    DG_f = fnx.DiGraph([(0, 1)])
    DG_n = nx_mod.DiGraph([(0, 1)])
    ie_f = DG_f.in_edges()
    ie_n = DG_n.in_edges()
    DG_f.add_edge(99, 100)
    DG_n.add_edge(99, 100)
    assert ((99, 100) in ie_f) == ((99, 100) in ie_n) == True
    assert len(ie_f) == len(ie_n) == 2

    # out_edges sister
    DG_f = fnx.DiGraph([(0, 1)])
    DG_n = nx_mod.DiGraph([(0, 1)])
    assert ([0, 1] in DG_f.out_edges()) == ([0, 1] in DG_n.out_edges()) == True

    # MultiDiGraph: nx's call form returns InMultiEdgeDataView (a
    # *different* class from the InMultiEdgeView property) with
    # stricter tuple-equality contains semantics, so we don't
    # short-circuit there — only verify the call-form survives.
    MD_f = fnx.MultiDiGraph([(0, 1), (0, 1)])
    MD_n = nx_mod.MultiDiGraph([(0, 1), (0, 1)])
    assert sorted(MD_f.in_edges()) == sorted(MD_n.in_edges())

    # Filtered call still works (returns a list / data view that
    # iterates correctly — sanity check, not a parity claim).
    DG_f = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    DG_n = nx_mod.DiGraph([(0, 1), (1, 2), (2, 0)])
    assert sorted(DG_f.in_edges([0])) == sorted(DG_n.in_edges([0]))


def test_graph_constructor_rejects_scalar_match_nx():
    """br-r37-c1-ctorscalar: ``Graph(5)``, ``Graph(1.5)``, ``Graph(True)``,
    ``Graph(complex(1, 2))`` etc. must raise ``NetworkXError("Input is
    not a known data type for conversion.")`` matching nx's
    ``to_networkx_graph`` terminal branch.

    Pre-fix the Rust ``__new__`` silently absorbed scalars as no-edge
    inputs, returning an empty graph.  Drop-in callers expecting nx's
    explicit-validation contract were silently getting a wrong (empty)
    graph instead of an error.

    Affects all 4 graph classes (Graph, DiGraph, MultiGraph,
    MultiDiGraph) — they share a single ``__init__`` wrapper.

    Fix: early ``isinstance(data, (int, float, complex))`` guard at
    the wrapper top, raising the nx-shaped NetworkXError before
    reaching the Rust __new__.  ``bool`` is captured by ``int``
    (subclass).  Strings / bytes are *iterable* and take a different
    nx code path that produces "Input is not a valid edge list" — out
    of scope for this fix.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    bad_inputs = [5, 0, 1.5, complex(1, 2), True, False]
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls_f = getattr(fnx, cls_name)
        cls_n = getattr(nx_mod, cls_name)
        for bad in bad_inputs:
            with pytest.raises(
                nx_mod.NetworkXError, match="Input is not a known data type"
            ):
                cls_f(bad)
            with pytest.raises(
                nx_mod.NetworkXError, match="Input is not a known data type"
            ):
                cls_n(bad)

    # Sanity: valid inputs still construct successfully
    G_f = fnx.Graph([(0, 1), (1, 2)])
    G_n = nx_mod.Graph([(0, 1), (1, 2)])
    assert sorted(G_f.edges()) == sorted(G_n.edges())

    H_f = fnx.Graph(fnx.path_graph(3))
    H_n = nx_mod.Graph(nx_mod.path_graph(3))
    assert sorted(H_f.edges()) == sorted(H_n.edges())

    fnx.Graph(None)  # explicit None still allowed
    fnx.Graph()  # default arg still allowed


def test_graph_constructor_rejects_non_edge_iterables_match_nx():
    """br-r37-c1-ctoredgelist: ``Graph([1, 2, 3])`` and other non-edge
    iterables (sets/tuples/ranges/strs/bytes of non-2-or-3-tuple
    items) must raise ``NetworkXError("Input is not a valid edge
    list")`` matching nx's terminal Collection branch in
    ``to_networkx_graph``.

    Pre-fix the Rust ``__new__`` silently absorbed each scalar element
    of these iterables as a graph node, returning ``Graph(N, 0)``
    instead of raising.

    Affected: list / tuple / set / frozenset / range / str / bytes of
    items that aren't sized-2-or-3 (i.e. not valid edge specs).

    Sister of cycle 160's br-r37-c1-ctorscalar fix on the bare-scalar
    case; this is the iterable-of-non-edges case.

    Fix: pre-validate concrete sized containers — walk the items and
    raise on any item that isn't a sized iterable of length 2 or 3.
    Special-cases str / bytes elements as scalars (they're sized but
    aren't edge specs).
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # All these should raise NetworkXError via either the
    # 'Input is not a valid edge list' path or (for str) the
    # 'Input is not a correct scipy sparse array type' path.  We
    # only assert NetworkXError class — message wording diverges
    # across the str/bytes/list branches in nx itself.
    bad_inputs = [
        [1, 2, 3],
        [(0, 1), 2],
        [(0,)],
        [(0, 1, 2, 3)],
        (1, 2, 3),
        {1, 2, 3},
        "abc",
        b"abc",
        range(3),
        ["a", "b", "c"],
    ]
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls_f = getattr(fnx, cls_name)
        cls_n = getattr(nx_mod, cls_name)
        for bad in bad_inputs:
            with pytest.raises(nx_mod.NetworkXError):
                cls_f(bad)
            with pytest.raises(nx_mod.NetworkXError):
                cls_n(bad)

    # Sanity: still accept canonical edge-list forms
    G_f = fnx.Graph([(0, 1), (1, 2)])
    G_n = nx_mod.Graph([(0, 1), (1, 2)])
    assert sorted(G_f.edges()) == sorted(G_n.edges())

    # Tuples, sets, iterators of tuples still work
    fnx.Graph((0, 1) for _ in range(1))
    fnx.Graph({(0, 1), (1, 2)})
    fnx.Graph(iter([(0, 1)]))

    # Empty iterables still work
    fnx.Graph([])
    fnx.Graph(())
    fnx.Graph(set())


def test_graph_constructor_accepts_list_of_list_edges_match_nx():
    """br-r37-c1-ctorlistedges: ``Graph([[0, 1], [1, 2]])`` and other
    list-of-list edge specs must construct correctly.  nx.from_edgelist
    accepts each edge as ANY 2- or 3-element iterable (tuple OR list);
    the Rust ``__new__`` accepts only tuples and stored list items as
    unhashable nodes-by-id, then the existing hashable-check raised
    ``NetworkXError("Input is not a valid edge list")``.

    Pre-fix the canonical nx idiom ``Graph([[u, v], ...])`` crashed
    under fnx — drop-in code that builds edge lists as lists (rather
    than tuples) was broken.

    Sister of cycle 161's br-r37-c1-ctoredgelist (which rejected
    non-edge iterables); this is the inverse — accept edges that
    happen to be lists.

    Fix: in the iterable pre-validation walk, also detect whether
    any element is a non-tuple (list) of length 2/3.  If so, after
    raw_init reset and rebuild via add_edges_from with each item
    converted to a tuple — preserving the per-edge attr dict in
    3-element specs.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Pure list-of-list across all 4 graph types
    cases = [
        ("Graph", fnx.Graph, nx_mod.Graph),
        ("DiGraph", fnx.DiGraph, nx_mod.DiGraph),
        ("MultiGraph", fnx.MultiGraph, nx_mod.MultiGraph),
        ("MultiDiGraph", fnx.MultiDiGraph, nx_mod.MultiDiGraph),
    ]
    for name, ctor_f, ctor_n in cases:
        G_f = ctor_f([[0, 1], [1, 2]])
        G_n = ctor_n([[0, 1], [1, 2]])
        assert sorted(G_f.edges()) == sorted(G_n.edges()), name

    # 3-element list with attr dict
    G_f = fnx.Graph([[0, 1, {"w": 5}], [1, 2]])
    G_n = nx_mod.Graph([[0, 1, {"w": 5}], [1, 2]])
    assert sorted(G_f.edges(data=True)) == sorted(G_n.edges(data=True))

    # Mixed tuple/list elements
    G_f = fnx.Graph([(0, 1), [1, 2]])
    G_n = nx_mod.Graph([(0, 1), [1, 2]])
    assert sorted(G_f.edges()) == sorted(G_n.edges())

    # Tuple-of-list (outer is tuple, inner is list)
    G_f = fnx.Graph(([0, 1], [1, 2]))
    G_n = nx_mod.Graph(([0, 1], [1, 2]))
    assert sorted(G_f.edges()) == sorted(G_n.edges())

    # graph kwargs preserved
    G_f = fnx.Graph([[0, 1]], name="X")
    G_n = nx_mod.Graph([[0, 1]], name="X")
    assert dict(G_f.graph) == dict(G_n.graph)

    # Sanity: pure tuple list still works (no regression from cycle 161)
    G_f = fnx.Graph([(0, 1), (1, 2)])
    G_n = nx_mod.Graph([(0, 1), (1, 2)])
    assert sorted(G_f.edges()) == sorted(G_n.edges())

    # Sanity: invalid iterables still rejected (no regression)
    with pytest.raises(nx_mod.NetworkXError):
        fnx.Graph([1, 2, 3])
    with pytest.raises(nx_mod.NetworkXError):
        fnx.Graph([(0,)])


def test_add_edges_from_accepts_list_edges_match_nx():
    """br-r37-c1-aeflist: ``G.add_edges_from([[0, 1], ...])`` must
    accept list-as-edge-spec like nx does.

    Pre-fix the Rust raw add_edges_from raised
    ``TypeError("each edge must be a tuple (u, v) or (u, v, attr_dict)")``
    on lists; nx's loop unpacks via ``u, v = e[:2]`` which accepts any
    2- or 3-element iterable.

    Direct sister of cycle 162's br-r37-c1-ctorlistedges (which fixed
    the constructor); this is the post-construction add_edges_from
    method form.

    Fix: in the materialization wrapper, convert non-tuple sized
    iterables of length 2/3 to tuples before delegating to the Rust
    raw path.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Graph + DiGraph use the materialized wrapper
    for cls_f, cls_n in [
        (fnx.Graph, nx_mod.Graph),
        (fnx.DiGraph, nx_mod.DiGraph),
    ]:
        G_f = cls_f()
        G_n = cls_n()
        G_f.add_edges_from([[0, 1], [1, 2]])
        G_n.add_edges_from([[0, 1], [1, 2]])
        assert sorted(G_f.edges()) == sorted(G_n.edges())

        # 3-element list with attrs
        G_f = cls_f()
        G_n = cls_n()
        G_f.add_edges_from([[0, 1, {"w": 5}]])
        G_n.add_edges_from([[0, 1, {"w": 5}]])
        assert list(G_f.edges(data=True)) == list(G_n.edges(data=True))

        # Mixed tuple/list
        G_f = cls_f()
        G_n = cls_n()
        G_f.add_edges_from([(0, 1), [1, 2]])
        G_n.add_edges_from([(0, 1), [1, 2]])
        assert sorted(G_f.edges()) == sorted(G_n.edges())

        # Generator yielding lists
        G_f = cls_f()
        G_n = cls_n()
        G_f.add_edges_from((e for e in [[0, 1], [1, 2]]))
        G_n.add_edges_from((e for e in [[0, 1], [1, 2]]))
        assert sorted(G_f.edges()) == sorted(G_n.edges())

    # Sanity: pure tuple list still works on all 4 graph types
    for cls_f, cls_n in [
        (fnx.Graph, nx_mod.Graph),
        (fnx.DiGraph, nx_mod.DiGraph),
        (fnx.MultiGraph, nx_mod.MultiGraph),
        (fnx.MultiDiGraph, nx_mod.MultiDiGraph),
    ]:
        G_f = cls_f()
        G_n = cls_n()
        G_f.add_edges_from([(0, 1), (1, 2)])
        G_n.add_edges_from([(0, 1), (1, 2)])
        assert sorted(G_f.edges()) == sorted(G_n.edges())

    # Sanity: bad-arity tuples still rejected with nx-shaped error
    with pytest.raises(nx_mod.NetworkXError, match="must be a 2-tuple or 3-tuple"):
        fnx.Graph().add_edges_from([(0,)])
    with pytest.raises(nx_mod.NetworkXError, match="must be a 2-tuple or 3-tuple"):
        nx_mod.Graph().add_edges_from([(0,)])


def test_remove_edges_from_accepts_list_edges_match_nx():
    """br-r37-c1-reflist: ``G.remove_edges_from([[0, 1], ...])`` must
    accept list-as-edge-spec like nx does.

    Pre-fix the Rust raw path raised
    ``TypeError("each element must be a (u, v) tuple")`` on Graph /
    DiGraph and ``TypeError("each edge must be a tuple")`` on
    MultiGraph / MultiDiGraph.  nx's loop unpacks via ``u, v = e[:2]``
    which accepts any 2- or 3-element iterable.

    Direct sister of cycle 163's br-r37-c1-aeflist (which fixed
    add_edges_from); this is the inverse remove operation.

    Fix: in the _remove_edges_from_materialized wrapper (applied to
    all 4 graph types), convert non-tuple sized iterables of length
    2/3 to tuples before delegating to the Rust raw path.  Preserves
    the 3-element key form for MultiGraph removal.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # All 4 graph types
    cases = [
        ("Graph", fnx.Graph, nx_mod.Graph, [(0, 1), (1, 2), (2, 3)]),
        ("DiGraph", fnx.DiGraph, nx_mod.DiGraph, [(0, 1), (1, 2), (2, 3)]),
        ("MultiGraph", fnx.MultiGraph, nx_mod.MultiGraph,
         [(0, 1), (0, 1), (1, 2)]),
        ("MultiDiGraph", fnx.MultiDiGraph, nx_mod.MultiDiGraph,
         [(0, 1), (0, 1), (1, 2)]),
    ]
    for name, ctor_f, ctor_n, init in cases:
        G_f = ctor_f(init)
        G_n = ctor_n(init)
        G_f.remove_edges_from([[0, 1]])
        G_n.remove_edges_from([[0, 1]])
        assert sorted(G_f.edges()) == sorted(G_n.edges()), name

        # Multiple list-edges
        G_f = ctor_f(init)
        G_n = ctor_n(init)
        G_f.remove_edges_from([[0, 1], [1, 2]])
        G_n.remove_edges_from([[0, 1], [1, 2]])
        assert sorted(G_f.edges()) == sorted(G_n.edges()), name

    # 3-element list form for MultiGraph (key removal)
    M_f = fnx.MultiGraph()
    M_f.add_edge(0, 1, key="a")
    M_f.add_edge(0, 1, key="b")
    M_n = nx_mod.MultiGraph()
    M_n.add_edge(0, 1, key="a")
    M_n.add_edge(0, 1, key="b")
    M_f.remove_edges_from([[0, 1, "a"]])
    M_n.remove_edges_from([[0, 1, "a"]])
    assert list(M_f.edges(keys=True)) == list(M_n.edges(keys=True))

    # Mixed tuple/list
    G_f = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    G_n = nx_mod.Graph([(0, 1), (1, 2), (2, 3)])
    G_f.remove_edges_from([(0, 1), [1, 2]])
    G_n.remove_edges_from([(0, 1), [1, 2]])
    assert sorted(G_f.edges()) == sorted(G_n.edges())

    # Sanity: pure tuples still work
    G_f = fnx.Graph([(0, 1), (1, 2)])
    G_n = nx_mod.Graph([(0, 1), (1, 2)])
    G_f.remove_edges_from([(0, 1)])
    G_n.remove_edges_from([(0, 1)])
    assert sorted(G_f.edges()) == sorted(G_n.edges())


def test_edges_data_arbitrary_key_match_nx():
    """br-r37-c1-edgesdatakey: ``G.edges(data=arbitrary_key)`` must
    accept any value for ``data`` and treat it as a dict-key into
    each edge's attrs (returning ``default`` for missing keys).

    Pre-fix the Rust binding declared ``data: bool | str`` and
    raised ``TypeError("data must be True, False, or a string
    attribute name")`` on callables, ints, tuples, etc.  nx's
    ``EdgeView.__call__`` uses ``attrs.get(data, default)`` which
    accepts any hashable as a key.

    Fix: in ``_EdgeDataView._materialize``, when ``data`` is not
    None / bool / str, route through a Python-side projection that
    looks up ``data`` in each edge's attrs dict.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    G_f = fnx.path_graph(3)
    G_n = nx_mod.path_graph(3)
    G_f[0][1]["weight"] = 5
    G_n[0][1]["weight"] = 5

    # Callable / int / tuple all return None (default) since they
    # aren't valid attr keys on these edges.
    for data_val in (lambda u, v: u + v, 5, ("w",)):
        assert list(G_f.edges(data=data_val)) == list(G_n.edges(data=data_val))

    # With explicit default: the default propagates.
    for data_val in (lambda u, v: u + v, 5):
        assert list(G_f.edges(data=data_val, default="X")) == list(
            G_n.edges(data=data_val, default="X")
        )

    # Sanity: bool/str/None still work
    assert list(G_f.edges(data=True)) == list(G_n.edges(data=True))
    assert list(G_f.edges(data="weight")) == list(G_n.edges(data="weight"))
    assert list(G_f.edges(data="missing")) == list(G_n.edges(data="missing"))
    assert list(G_f.edges()) == list(G_n.edges())

    # nbunch + non-string data
    assert sorted(G_f.edges([0], data=lambda u, v: u + v)) == sorted(
        G_n.edges([0], data=lambda u, v: u + v)
    )

    # MultiGraph variant — preserves keys=True 4-tuple form
    M_f = fnx.MultiGraph()
    M_f.add_edge(0, 1, weight=5)
    M_f.add_edge(0, 1, weight=10)
    M_n = nx_mod.MultiGraph()
    M_n.add_edge(0, 1, weight=5)
    M_n.add_edge(0, 1, weight=10)
    assert list(M_f.edges(data=lambda u, v: 0)) == list(
        M_n.edges(data=lambda u, v: 0)
    )
    assert list(M_f.edges(data=lambda u, v: 0, keys=True)) == list(
        M_n.edges(data=lambda u, v: 0, keys=True)
    )


def test_adj_subview_class_names_match_nx():
    """br-r37-c1-adjviewname: ``G.adj[u].keys()``, ``.values()``,
    ``.items()`` (and the parent G.adj variants) must return objects
    whose ``type(view).__name__`` matches nx — bare ``KeysView`` /
    ``ValuesView`` / ``ItemsView``.

    Pre-fix mismatches:
      - G.adj[0].keys():   fnx '_AdjKeysView'   vs nx 'KeysView'
      - G.adj[0].values(): fnx '_AdjValuesView' vs nx 'ValuesView'
      - G.adj[0].items():  fnx '_AdjItemsView'  vs nx 'ItemsView'

    Sister of cycle 157's br-r37-c1-viewnames (which fixed
    EdgeView/NodeView class names); this is the AdjView sub-view
    family.

    Fix: rename ``__name__`` on the local subclasses inside
    _adjacency_view_keys/_items/_values to the bare collections.abc
    names (matching nx, which returns the bare ABC types).
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    G_f = fnx.path_graph(3)
    G_n = nx_mod.path_graph(3)

    # Per-node sub-views
    assert type(G_f.adj[0].keys()).__name__ == type(G_n.adj[0].keys()).__name__
    assert type(G_f.adj[0].values()).__name__ == type(G_n.adj[0].values()).__name__
    assert type(G_f.adj[0].items()).__name__ == type(G_n.adj[0].items()).__name__

    # G.adj wrappers
    assert type(G_f.adj.keys()).__name__ == type(G_n.adj.keys()).__name__
    assert type(G_f.adj.values()).__name__ == type(G_n.adj.values()).__name__
    assert type(G_f.adj.items()).__name__ == type(G_n.adj.items()).__name__

    # Sanity: views still iterate / index correctly
    assert sorted(G_f.adj[0].keys()) == sorted(G_n.adj[0].keys())
    assert dict(G_f.adj[0].items()) == dict(G_n.adj[0].items())
    assert len(G_f.adj[0].values()) == len(G_n.adj[0].values())


def test_ego_graph_missing_source_and_nan_radius_match_nx():
    """br-r37-c1-egonotfound + br-r37-c1-egonan: ``ego_graph`` must:

    1. Raise ``NodeNotFound("Source <n> is not in G")`` (NOT
       ``NetworkXError``) when ``n`` isn't in the graph — matching
       nx, which delegates to ``single_source_shortest_path_length``.
       fnx surfaced the NetworkXError from ``G.neighbors(n)`` instead.
       NodeNotFound is a SIBLING of NetworkXError (both subclass
       NetworkXException), not a subclass — drop-in code that does
       ``except nx.NodeNotFound`` was missing fnx's NetworkXError.

    2. Treat ``radius=NaN`` as source-only (single node, no edges)
       — matching nx via the cycle 142 cutoff-NaN short-circuit on
       single_source_shortest_path_length.  fnx's BFS used
       ``depth >= radius`` which returns False for NaN, so the loop
       never depth-bounded and yielded the full reachable component.

    Fix: explicit ``if n not in G: raise NodeNotFound(...)`` guard +
    ``isinstance(radius, float) and isnan(radius) -> radius = -1`` at
    the top of ego_graph.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    G_f = fnx.path_graph(5)
    G_n = nx_mod.path_graph(5)

    # Source-missing -> NodeNotFound (was NetworkXError pre-fix)
    with pytest.raises(nx_mod.NodeNotFound, match="Source 99 is not in G"):
        fnx.ego_graph(G_f, 99)
    with pytest.raises(nx_mod.NodeNotFound, match="Source 99 is not in G"):
        nx_mod.ego_graph(G_n, 99)

    # radius=NaN -> source-only (no edges)
    f_eg = fnx.ego_graph(G_f, 2, radius=float("nan"))
    n_eg = nx_mod.ego_graph(G_n, 2, radius=float("nan"))
    assert sorted(f_eg.nodes()) == sorted(n_eg.nodes()) == [2]
    assert list(f_eg.edges()) == list(n_eg.edges()) == []

    # Sanity: ordinary radius still works
    f_eg = fnx.ego_graph(G_f, 2, radius=2)
    n_eg = nx_mod.ego_graph(G_n, 2, radius=2)
    assert sorted(f_eg.edges()) == sorted(n_eg.edges())

    # Sanity: radius=0 (source-only)
    f_eg = fnx.ego_graph(G_f, 2, radius=0)
    n_eg = nx_mod.ego_graph(G_n, 2, radius=0)
    assert sorted(f_eg.nodes()) == sorted(n_eg.nodes()) == [2]
    assert list(f_eg.edges()) == list(n_eg.edges()) == []


def test_min_cost_flow_empty_raises_match_nx():
    """br-r37-c1-mcfempty: ``min_cost_flow`` and its sister
    ``min_cost_flow_cost`` must raise ``NetworkXError("graph has no
    nodes")`` on an empty DiGraph — matching nx's
    ``_validate_network_simplex_inputs`` contract.

    Pre-fix the SSP path returned an empty ``{}`` dict for empty
    input, silently swallowing the error and propagating to
    ``min_cost_flow_cost`` and ``max_flow_min_cost`` which both
    route through this code path.

    Fix: explicit ``if n == 0: raise NetworkXError("graph has no
    nodes")`` at the top of the SSP solver, before the validation
    block.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    with pytest.raises(nx_mod.NetworkXError, match="graph has no nodes"):
        fnx.min_cost_flow(fnx.DiGraph())
    with pytest.raises(nx_mod.NetworkXError, match="graph has no nodes"):
        nx_mod.min_cost_flow(nx_mod.DiGraph())

    with pytest.raises(nx_mod.NetworkXError, match="graph has no nodes"):
        fnx.min_cost_flow_cost(fnx.DiGraph())
    with pytest.raises(nx_mod.NetworkXError, match="graph has no nodes"):
        nx_mod.min_cost_flow_cost(nx_mod.DiGraph())

    # Sanity: non-empty still works
    DG_f = fnx.DiGraph()
    DG_n = nx_mod.DiGraph()
    for u, v, c in [(0, 1, 5), (0, 2, 5), (1, 3, 5), (2, 3, 5)]:
        DG_f.add_edge(u, v, capacity=c, weight=1)
        DG_n.add_edge(u, v, capacity=c, weight=1)
    DG_f.nodes[0]["demand"] = -10
    DG_f.nodes[3]["demand"] = 10
    DG_n.nodes[0]["demand"] = -10
    DG_n.nodes[3]["demand"] = 10
    assert fnx.min_cost_flow_cost(DG_f) == nx_mod.min_cost_flow_cost(DG_n)


def test_resistance_distance_empty_raises_match_nx():
    """br-r37-c1-resdempty: ``resistance_distance`` on an empty graph
    must raise ``NetworkXError("Graph G must contain at least one
    node.")`` matching nx — sister of cycle 168's br-r37-c1-mcfempty
    on min_cost_flow.

    Pre-fix the empty-graph branch silently returned ``{}`` (or
    ``0.0`` when explicit nodeA/nodeB were given), masking the
    contract.  The same NetworkXError is raised by nx's
    effective_graph_resistance and kemeny_constant siblings.

    Fix: replace the early ``return {}`` with the nx-shaped
    NetworkXError, and reorder so the empty-graph check fires
    BEFORE the nodeA/nodeB membership checks (nx surfaces 'Graph G
    must contain at least one node.' even when explicit nodes are
    passed to an empty graph, not 'Node A is not in graph G.').
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Empty + various arg combinations
    for kwargs in [
        {},
        {"nodeA": 0},
        {"nodeA": 0, "nodeB": 1},
    ]:
        with pytest.raises(
            nx_mod.NetworkXError, match="must contain at least one node"
        ):
            fnx.resistance_distance(fnx.Graph(), **kwargs)
        with pytest.raises(
            nx_mod.NetworkXError, match="must contain at least one node"
        ):
            nx_mod.resistance_distance(nx_mod.Graph(), **kwargs)

    # Sanity: non-empty + missing node still raises 'Node A is not in graph G'
    G_f = fnx.path_graph(3)
    G_n = nx_mod.path_graph(3)
    with pytest.raises(nx_mod.NetworkXError, match="Node A is not in graph G"):
        fnx.resistance_distance(G_f, nodeA=99)
    with pytest.raises(nx_mod.NetworkXError, match="Node A is not in graph G"):
        nx_mod.resistance_distance(G_n, nodeA=99)

    # Sanity: non-empty + valid nodes still computes
    assert round(fnx.resistance_distance(G_f, 0, 2), 4) == round(
        nx_mod.resistance_distance(G_n, 0, 2), 4
    )


def test_find_negative_cycle_no_cycle_message_match_nx():
    """br-r37-c1-fnegmsg: ``find_negative_cycle`` must raise the
    nx-shaped ``NetworkXError("No negative cycles detected.")`` when
    no negative cycle exists.

    Pre-fix the Rust ``_raw_find_negative_cycle`` raised
    ``NetworkXError("No negative cycle found.")`` (singular, 'found').
    nx's wording is ``"No negative cycles detected."`` (plural,
    'detected').  Drop-in callers regex-matching nx's exact message
    string failed under fnx.

    Fix: wrap the Rust raw call and translate the message to nx's
    exact wording when the no-cycle case fires.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    # Undirected (Rust path): no negative cycle on a positive-weight
    # path -> NetworkXError with nx's wording
    with pytest.raises(
        nx_mod.NetworkXError, match=r"No negative cycles detected\."
    ):
        fnx.find_negative_cycle(fnx.path_graph(3), 0)
    with pytest.raises(
        nx_mod.NetworkXError, match=r"No negative cycles detected\."
    ):
        nx_mod.find_negative_cycle(nx_mod.path_graph(3), 0)

    # Directed (delegates to nx): same wording
    DG_f = fnx.DiGraph([(0, 1), (1, 2)])
    DG_n = nx_mod.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(
        nx_mod.NetworkXError, match=r"No negative cycles detected\."
    ):
        fnx.find_negative_cycle(DG_f, 0)
    with pytest.raises(
        nx_mod.NetworkXError, match=r"No negative cycles detected\."
    ):
        nx_mod.find_negative_cycle(DG_n, 0)

    # Sanity: actual negative cycle still found correctly
    DG_f = fnx.DiGraph()
    DG_n = nx_mod.DiGraph()
    for u, v, w in [(0, 1, 5), (1, 2, -10), (2, 0, 1)]:
        DG_f.add_edge(u, v, weight=w)
        DG_n.add_edge(u, v, weight=w)
    assert fnx.find_negative_cycle(DG_f, 0) == nx_mod.find_negative_cycle(DG_n, 0)

    # Sanity: missing source still raises NodeNotFound
    with pytest.raises(nx_mod.NodeNotFound):
        fnx.find_negative_cycle(DG_f, 99)
    with pytest.raises(nx_mod.NodeNotFound):
        nx_mod.find_negative_cycle(DG_n, 99)


def test_parse_gexf_accepts_bytes_input():
    """br-r37-c1-gexfbytes: ``parse_gexf`` must accept either ``str``
    or ``bytes`` input.

    Pre-fix the wrapper unconditionally called ``string.encode(...)``
    on the input, so bytes input crashed with
    ``AttributeError("'bytes' object has no attribute 'encode'")``.

    A natural drop-in pattern is to pipe the output of ``write_gexf``
    (which writes to a BytesIO) directly into ``parse_gexf`` for
    a round-trip — that pattern was broken by the encode-on-bytes
    assumption.

    Fix: branch on ``isinstance(string, (bytes, bytearray))`` and
    pass the bytes through unchanged; only utf-8-encode str.
    """
    import franken_networkx as fnx
    import io

    # Empty bytes / str / bytearray
    for empty in (b"", "", bytearray()):
        G = fnx.readwrite.parse_gexf(empty)
        assert G.number_of_nodes() == 0
        assert G.number_of_edges() == 0

    # Round-trip bytes via write_gexf -> parse_gexf
    G_orig = fnx.path_graph(3)
    G_orig.nodes[0]["x"] = 5
    buf = io.BytesIO()
    fnx.write_gexf(G_orig, buf)
    gexf_bytes = buf.getvalue()

    # bytes input
    G_parsed_bytes = fnx.readwrite.parse_gexf(gexf_bytes)
    assert G_parsed_bytes.number_of_nodes() == G_orig.number_of_nodes()
    assert G_parsed_bytes.number_of_edges() == G_orig.number_of_edges()

    # str input (already worked pre-fix)
    G_parsed_str = fnx.readwrite.parse_gexf(gexf_bytes.decode("utf-8"))
    assert G_parsed_str.number_of_nodes() == G_orig.number_of_nodes()


def test_graph_update_dup_kwarg_error_message_match_nx():
    """br-r37-c1-updatename: ``G.update(H, edges=...)`` (a programmer
    error — passing both a positional graph-like and the ``edges``
    kwarg explicitly) must surface Python's auto-generated TypeError
    with the canonical nx wording ``Graph.update() got multiple
    values for argument 'edges'`` rather than fnx's private
    ``_graph_update()`` name.

    Pre-fix the function was named ``_graph_update`` and Python's
    duplicate-kwarg TypeError exposed that private name in the
    error message — leaking implementation detail to drop-in code
    that error-message-matches.

    Sister of cycles 157 / 166's view-class-name renames; this is
    the function-name analogue.

    Fix: set ``__name__`` and ``__qualname__`` on the wrapper so
    Python's error machinery picks up nx's canonical ``Graph.update``
    name.
    """
    import franken_networkx as fnx
    import networkx as nx_mod

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls_f = getattr(fnx, cls_name)
        cls_n = getattr(nx_mod, cls_name)
        G_f = cls_f([(0, 1)])
        G_n = cls_n([(0, 1)])
        with pytest.raises(TypeError) as f_exc:
            G_f.update(cls_f([(2, 3)]), edges=[(4, 5)])
        with pytest.raises(TypeError) as n_exc:
            G_n.update(cls_n([(2, 3)]), edges=[(4, 5)])
        assert str(f_exc.value) == str(n_exc.value), (
            f"{cls_name}: fnx={f_exc.value!r} vs nx={n_exc.value!r}"
        )
        # nx's wording explicitly names "Graph.update" even on
        # DiGraph etc. (inherited method); verify both libs match.
        assert "Graph.update()" in str(f_exc.value)

    # Sanity: legitimate update calls still work
    G_f = fnx.Graph()
    G_f.update(fnx.path_graph(3))
    assert sorted(G_f.edges()) == [(0, 1), (1, 2)]

    # Sanity: no-args error wording unchanged
    with pytest.raises(nx_mod.NetworkXError, match="update needs"):
        fnx.Graph().update()
    with pytest.raises(nx_mod.NetworkXError, match="update needs"):
        nx_mod.Graph().update()


def test_graph_method_qualnames_no_private_leak():
    """br-r37-c1-methodqualname: ``method.__qualname__`` on the wrapped
    Graph methods must NOT leak the fnx-private closure name (e.g.
    ``_make_none_rejecting_add_edge.<locals>.add_edge``).  Each method
    should have a ``Class.method`` qualname so:

    1. ``inspect.signature`` introspection looks like nx (debug repr,
       test fixtures, drop-in libraries that branch on qualname).
    2. Python's auto-generated TypeError on duplicate kwargs uses
       ``Class.method() got multiple values for ...`` instead of
       leaking the wrapper closure.

    Sister of cycle 173 br-r37-c1-updatename (Graph.update) and the
    DegreeView / EdgeView class-name renames in cycles 157 / 166.

    Note: fnx shares some wrappers across classes (eg. ``copy`` is one
    function for all 4 graph types) where nx splits them.  We don't
    fork those wrappers — accept that ``fnx.MultiGraph.copy`` will
    have qualname ``Graph.copy`` (the first class to use it) rather
    than nx's ``MultiGraph.copy``.  The important contract is that
    NO method's qualname leaks the private closure name.
    """
    import franken_networkx as fnx

    bad_substrings = ("<locals>", "_make_", "_private_", "_size_with_")
    methods = (
        "add_edge", "remove_edge", "add_edges_from", "remove_edges_from",
        "add_node", "add_nodes_from", "remove_node", "remove_nodes_from",
        "has_node", "has_edge", "number_of_edges", "size", "copy",
        "edge_subgraph", "predecessors", "successors", "reverse",
        "update",
    )
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls = getattr(fnx, cls_name)
        for meth in methods:
            method = getattr(cls, meth, None)
            if method is None:
                continue
            qualname = getattr(method, "__qualname__", "")
            for bad in bad_substrings:
                assert bad not in qualname, (
                    f"{cls_name}.{meth}.__qualname__ leaks private name: "
                    f"{qualname!r}"
                )
            # Should be of the form "<SomeClass>.<method>"
            assert "." in qualname, (
                f"{cls_name}.{meth}.__qualname__ should be Class.method "
                f"form, got {qualname!r}"
            )

    # Specific check: TypeError on duplicate kwarg uses canonical name
    G_f = fnx.Graph([(0, 1)])
    with pytest.raises(TypeError, match=r"Graph\.add_edge\(\)") as exc:
        G_f.add_edge(0, 1, u_of_edge=99)
    assert "<locals>" not in str(exc.value)


def test_random_lobster_graph_signature_match_nx():
    """br-r37-c1-rlgsig: ``random_lobster_graph`` signature must use
    ``**backend_kwargs`` (variadic) like nx, not ``backend_kwargs=None``
    (single named kwarg).

    Pre-fix ``inspect.signature(fnx.random_lobster_graph)`` reported
    ``(n, p1, p2, seed=None, *, create_using=None, backend=None,
    backend_kwargs=None)`` while nx reports the canonical
    ``**backend_kwargs`` variadic.  Signature-parity-introspecting
    code (test fixtures, drop-in libs) saw a structural difference.

    Plus a behavioral consequence: nx's @_dispatchable validates
    that no unknown kwargs leaked through, raising
    ``TypeError: random_lobster_graph() got an unexpected keyword
    argument 'foo'``.  fnx's ``del backend, backend_kwargs``
    silently dropped them.

    Fix: change ``backend_kwargs=None`` to ``**backend_kwargs`` and
    route through ``_validate_backend_dispatch_keywords`` for the
    unknown-kwarg rejection.
    """
    import franken_networkx as fnx
    import networkx as nx_mod
    import inspect

    # Signature parity
    f_sig = str(inspect.signature(fnx.random_lobster_graph))
    n_sig = str(inspect.signature(nx_mod.random_lobster_graph))
    assert f_sig == n_sig, (
        f"signature mismatch:\n  fnx={f_sig}\n  nx ={n_sig}"
    )

    # Default still works
    G_f = fnx.random_lobster_graph(5, 0.5, 0.5, seed=42)
    G_n = nx_mod.random_lobster_graph(5, 0.5, 0.5, seed=42)
    assert type(G_f).__name__ == type(G_n).__name__

    # Backend dispatch
    G_f = fnx.random_lobster_graph(5, 0.5, 0.5, seed=42, backend="networkx")
    assert isinstance(G_f, fnx.Graph)

    # Unknown kwarg rejected with nx-shaped message
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        fnx.random_lobster_graph(5, 0.5, 0.5, seed=42, foo="bar")
    with pytest.raises(TypeError, match="unexpected keyword argument 'foo'"):
        nx_mod.random_lobster_graph(5, 0.5, 0.5, seed=42, foo="bar")

    # Invalid backend rejected with nx-shaped message
    with pytest.raises(ImportError, match="'invalid' backend is not installed"):
        fnx.random_lobster_graph(5, 0.5, 0.5, seed=42, backend="invalid")
    with pytest.raises(ImportError, match="'invalid' backend is not installed"):
        nx_mod.random_lobster_graph(5, 0.5, 0.5, seed=42, backend="invalid")


def test_subgraph_view_default_filters_match_nx():
    """br-r37-c1-svfilter: ``subgraph_view`` defaults for
    ``filter_node`` and ``filter_edge`` must be a callable
    (``no_filter``), matching nx's signature.

    Pre-fix fnx used ``filter_node=None`` / ``filter_edge=None`` —
    behavior was equivalent (None treated as no filter) but
    ``inspect.signature(fnx.subgraph_view)`` reported
    ``filter_node=None`` while nx reports
    ``filter_node=<function no_filter at ...>``.

    Drop-in code performing signature parity (test fixtures, library
    compatibility checks) saw the structural difference.

    Fix: change defaults from ``None`` to ``no_filter`` (the existing
    fnx callable) — the underlying ``_generic_filtered_graph_view``
    treats both equivalently so behavior is unchanged.
    """
    import franken_networkx as fnx
    import networkx as nx_mod
    import inspect

    sig_f = inspect.signature(fnx.subgraph_view)
    sig_n = inspect.signature(nx_mod.subgraph_view)

    # Both filter_node and filter_edge defaults must be callable
    for param in ("filter_node", "filter_edge"):
        f_default = sig_f.parameters[param].default
        n_default = sig_n.parameters[param].default
        assert callable(f_default), (
            f"fnx.subgraph_view {param} default not callable: {f_default!r}"
        )
        assert callable(n_default)
        # The default's name should be no_filter (exact pointer equality
        # would require sharing the function object, but the logical
        # contract is that the default is a no-op filter).
        assert f_default.__name__ == "no_filter" == n_default.__name__

    # Sanity: behavior unchanged
    G_f = fnx.path_graph(5)
    G_n = nx_mod.path_graph(5)
    assert sorted(fnx.subgraph_view(G_f).edges()) == sorted(
        nx_mod.subgraph_view(G_n).edges()
    )

    # With explicit filter
    assert sorted(
        fnx.subgraph_view(G_f, filter_node=lambda n: n != 2).edges()
    ) == sorted(
        nx_mod.subgraph_view(G_n, filter_node=lambda n: n != 2).edges()
    )


def test_display_signature_match_nx():
    """br-r37-c1-dispkwds: ``fnx.display`` variadic kwarg name must
    match nx's ``**kwargs`` (was ``**kwds``).

    Pre-fix ``inspect.signature(fnx.display)`` reported
    ``(G, canvas=None, **kwds)`` while nx reports
    ``(G, canvas=None, **kwargs)`` — a one-character cosmetic
    divergence that breaks signature-parity introspection but has
    no behavioral effect (kwarg names are caller-invisible).

    Fix: rename ``**kwds`` -> ``**kwargs`` in the function
    definition and the two internal forwards.
    """
    import franken_networkx as fnx
    import networkx as nx_mod
    import inspect

    f_sig = str(inspect.signature(fnx.display))
    n_sig = str(inspect.signature(nx_mod.display))
    assert f_sig == n_sig, (
        f"display signature mismatch:\n  fnx={f_sig}\n  nx ={n_sig}"
    )
    # Specifically: variadic should be **kwargs not **kwds
    assert "**kwargs" in f_sig
    assert "**kwds" not in f_sig


def test_readwrite_signatures_have_backend_kwargs_match_nx():
    """br-r37-c1-rwbackendkw: 15 readwrite functions had signatures
    missing the canonical ``*, backend=None, **backend_kwargs``
    suffix that nx adds via ``@_dispatchable``:

      parse_adjlist, parse_edgelist, parse_gml, parse_pajek,
      parse_leda, parse_multiline_adjlist,
      from_graph6_bytes, from_sparse6_bytes,
      read_gexf, read_graph6, read_leda, read_multiline_adjlist,
      read_pajek, read_sparse6, read_weighted_edgelist

    Drop-in callers using ``nx.parse_edgelist(..., backend='networkx')``
    crashed under fnx with TypeError(unexpected keyword 'backend').

    Fix: add ``*, backend=None, **backend_kwargs`` to each signature.
    Behavior unchanged for default invocations; backend dispatch
    args are silently consumed (matches the canonical fnx wrapper
    pattern at random_lobster_graph etc.).
    """
    import franken_networkx as fnx
    import networkx as nx_mod
    import inspect

    targets = (
        "parse_adjlist", "parse_edgelist", "parse_gml", "parse_pajek",
        "parse_leda", "parse_multiline_adjlist",
        "from_graph6_bytes", "from_sparse6_bytes",
        "read_gexf", "read_graph6", "read_leda", "read_multiline_adjlist",
        "read_pajek", "read_sparse6", "read_weighted_edgelist",
    )
    for name in targets:
        f_attr = getattr(fnx, name, None)
        n_attr = getattr(nx_mod, name, None)
        if f_attr is None or n_attr is None:
            continue
        f_sig = str(inspect.signature(f_attr))
        n_sig = str(inspect.signature(n_attr))
        assert f_sig == n_sig, (
            f"{name} signature mismatch:\n  fnx={f_sig}\n  nx ={n_sig}"
        )

    # Sanity: backend=networkx kwarg accepted (no TypeError)
    G = fnx.parse_edgelist(["a b"], backend="networkx")
    assert sorted(G.edges()) == [("a", "b")]
    fnx.parse_pajek([], backend="networkx")
    fnx.from_graph6_bytes(b"@", backend="networkx")


def test_add_edges_from_malformed_edge_error_contract():
    """br-r37-c1-aefnone: Graph/DiGraph.add_edges_from must replicate
    nx's ``ne = len(e)`` first-pass gate so error CLASS + message
    match networkx exactly:

    - ``[[1]]``, ``[(1,)]``, ``[()]``, ``[(1,2,3,4)]``,
      ``[[1,2,3,4]]`` raise
      ``NetworkXError(f"Edge tuple {e} must be a 2-tuple or 3-tuple.")``
      (nx's exception CLASS — not a generic TypeError).
    - ``[None]``, ``[1]`` (no-len inputs) raise
      ``TypeError("object of type X has no len()")`` exactly.

    Pre-fix the Rust raw path raised ``TypeError("each edge must be a
    tuple (u, v) or (u, v, attr_dict)")`` for all of these — an
    exception CLASS divergence (TypeError vs NetworkXError) for the
    list/tuple-arity case, which broke drop-in callers using
    ``except nx.NetworkXError:`` to detect malformed edge inputs.
    """
    cases = [
        ([[1]],         fnx.NetworkXError, "Edge tuple [1] must be a 2-tuple or 3-tuple."),
        ([(1,)],        fnx.NetworkXError, "Edge tuple (1,) must be a 2-tuple or 3-tuple."),
        ([()],          fnx.NetworkXError, "Edge tuple () must be a 2-tuple or 3-tuple."),
        ([(1, 2, 3, 4)], fnx.NetworkXError, "Edge tuple (1, 2, 3, 4) must be a 2-tuple or 3-tuple."),
        ([[1, 2, 3, 4]], fnx.NetworkXError, "Edge tuple [1, 2, 3, 4] must be a 2-tuple or 3-tuple."),
        ([None],        TypeError, "object of type 'NoneType' has no len()"),
        ([1],           TypeError, "object of type 'int' has no len()"),
    ]

    for cls in (fnx.Graph, fnx.DiGraph):
        for ebunch, exc_type, msg in cases:
            G = cls()
            try:
                G.add_edges_from(ebunch)
            except exc_type as e:
                assert str(e) == msg, (
                    f"{cls.__name__}.add_edges_from({ebunch!r}): "
                    f"expected {exc_type.__name__}({msg!r}), got "
                    f"{type(e).__name__}({str(e)!r})"
                )
            else:
                raise AssertionError(
                    f"{cls.__name__}.add_edges_from({ebunch!r}) did not raise"
                )

    # Positive controls: well-formed inputs still succeed unchanged.
    for cls in (fnx.Graph, fnx.DiGraph):
        G = cls()
        G.add_edges_from([(1, 2), [3, 4], (5, 6, {"w": 1})])
        assert (1, 2) in G.edges()
        assert (3, 4) in G.edges()
        assert (5, 6) in G.edges()
        assert G.get_edge_data(5, 6) == {"w": 1}


def test_int_float_node_identity_matches_python_dict():
    """br-r37-c1-intfloatnode: nx uses dicts for node storage, so
    Python's hash/eq semantics conflate numerically-equal int/bool/
    float as the SAME node (``hash(0) == hash(0.0) == hash(False)``).

    Pre-fix, fnx canonicalised node keys via ``node_key_to_string``
    that produced ``"0"`` for int 0 but ``"0.0"`` for float 0.0,
    splitting what should be a single node across two distinct
    Rust-side keys.  This broke any drop-in caller that round-trips
    int node ids through float (NumPy/JSON loaders, scientific
    pipelines, etc.):

      - ``0.0 in G`` returned False when node 0 was added
      - ``G.has_node(0.0)`` returned False
      - ``G[0.0]`` raised KeyError
      - ``G.degree[0.0]`` raised KeyError
      - ``G.has_edge(0.0, 1.0)`` returned False on edge (0, 1)
      - ``G.add_node(0.0)`` after ``add_node(0)`` created a duplicate
      - ``G.remove_node(0.0)`` raised NetworkXError on int-keyed node

    Fix: route integral floats (finite, in i64 range, zero
    fractional part — including ``-0.0``) through the int canonical
    form. Non-integral / out-of-range / non-finite floats remain
    distinct (preserving NaN, Inf, 1.5, 1e20 as separate nodes).
    """
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        # Membership for numerically-equal int/float/bool
        G = cls()
        G.add_node(0)
        G.add_edge(1, 2)
        for q in (0, 0.0, -0.0, False, 1, 1.0, True, 2, 2.0):
            assert q in G, f"{cls.__name__}: {q!r} not in G after add_node(0)+add_edge(1,2)"
            assert q in G.nodes, f"{cls.__name__}: {q!r} not in G.nodes"
            assert G.has_node(q), f"{cls.__name__}: has_node({q!r})"

        # Adjacency lookup with float key resolves to int-keyed neighbour
        G2 = cls()
        G2.add_edge(0, 1)
        assert dict(G2[0.0]) == dict(G2[0])
        assert G2.has_edge(0.0, 1.0)
        assert G2.has_edge(False, True)
        assert G2.degree[0.0] == G2.degree[0] == 1

        # Add deduplication
        G3 = cls()
        G3.add_node(0)
        G3.add_node(0.0)
        G3.add_node(False)
        assert G3.number_of_nodes() == 1, (
            f"{cls.__name__}: 0/0.0/False should coalesce to 1 node, "
            f"got {G3.number_of_nodes()}: {list(G3.nodes())}"
        )

        # Edge add via float endpoint must not create duplicate node
        G4 = cls()
        G4.add_edge(0, 1)
        G4.add_edge(0.0, 2)
        assert G4.number_of_nodes() == 3
        assert (0, 1) in G4.edges() or (1, 0) in G4.edges()
        assert (0, 2) in G4.edges() or (2, 0) in G4.edges()

        # remove_node by float on int-keyed node
        G5 = cls()
        G5.add_node(0)
        G5.add_node(1)
        G5.remove_node(0.0)
        assert 0 not in G5
        assert list(G5.nodes()) == [1]

    # Distinct: NaN, Inf, non-integral, out-of-i64-range floats remain separate
    G = fnx.Graph()
    G.add_node(0)
    G.add_node(0.5)
    G.add_node(float("nan"))
    G.add_node(float("inf"))
    G.add_node(float("-inf"))
    G.add_node(1e20)
    assert G.number_of_nodes() == 6, (
        f"non-integral / out-of-range / non-finite floats should "
        f"remain distinct, got nodes={list(G.nodes())}"
    )


def test_node_first_add_wins_for_displayed_py_object():
    """br-r37-c1-firstwins: nx uses dicts for node storage, so the
    FIRST Python object added under a given canonical key (e.g.
    ``hash(0) == hash(0.0) == hash(False)``) is what
    ``list(G.nodes())`` returns. Subsequent ``add_node`` calls with
    a hash-equivalent key are no-ops at the storage level — the
    original Py object is preserved.

    Pre-fix the Rust ``add_node`` paths in lib.rs and digraph.rs used
    unconditional ``HashMap::insert`` for ``node_key_map``, so the
    LAST Py form overwrote the canonical display:

      Operation             nx              fnx (pre-fix)
      ---------             ---             -------------
      add 0,0.0,False       [0]             [False]
      add 0.0,0,False       [0.0]           [False]
      add False,0,0.0       [False]         [0.0]
      add 1.0,1,True        [1.0]           [True]

    Affects iteration ordering / type introspection on every drop-in
    caller that round-trips int node ids through float.
    ``add_edge`` was already correct (uses ``entry().or_insert_with``);
    this aligns the four ``add_node`` sites with that pattern.
    """
    cases = [
        ([0, 0.0, False],   [0],     "int"),
        ([0.0, 0, False],   [0.0],   "float"),
        ([False, 0, 0.0],   [False], "bool"),
        ([1.0, 1, True],    [1.0],   "float"),
        ([True, 1, 1.0],    [True],  "bool"),
    ]

    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        for ops, expected_nodes, expected_type in cases:
            G = cls()
            for x in ops:
                G.add_node(x)
            actual = list(G.nodes())
            assert actual == expected_nodes, (
                f"{cls.__name__}.add_node sequence {ops}: "
                f"expected {expected_nodes}, got {actual}"
            )
            assert type(actual[0]).__name__ == expected_type, (
                f"{cls.__name__}.add_node sequence {ops}: "
                f"expected first node type {expected_type}, got "
                f"{type(actual[0]).__name__}"
            )

    # add_node before add_edge keeps the explicit-add Py form
    for cls in (fnx.Graph, fnx.DiGraph):
        G = cls()
        G.add_node(0.0)
        G.add_edge(0, 1)
        assert list(G.nodes())[0] == 0.0
        assert type(list(G.nodes())[0]).__name__ == "float"

    # add_edge before add_node keeps the edge-add Py form
    for cls in (fnx.Graph, fnx.DiGraph):
        G = cls()
        G.add_edge(0, 1)
        G.add_node(0.0)
        assert list(G.nodes())[0] == 0
        assert type(list(G.nodes())[0]).__name__ == "int"


def test_multigraph_edge_key_int_float_collide_like_python_dict():
    """br-r37-c1-edgekeyint: MultiGraph/MultiDiGraph edge keys use
    Python dict semantics — ``hash(0) == hash(0.0) == hash(False)``,
    so an edge added with ``key=0`` is the SAME edge that ``key=0.0``
    or ``key=False`` should look up.

    Pre-fix the Rust ``edge_key_lookup_string`` at
    crates/fnx-python/src/lib.rs:121 produced three distinct
    canonicals for hash-equivalent inputs:

      Input           canonical (pre-fix)
      -----           -------------------
      key=0           "int:0"
      key=0.0         "float:0.0"
      key=False       "bool:false"

    Splitting one logical edge across multiple Rust-side slots,
    breaking:

      MG.has_edge('a', 'b', key=0.0)         (returned False)
      MG.add_edge('a', 'b', key=0.0)         (created duplicate)
      MG.add_edge('a', 'b', key=False)       (created duplicate)

    Direct sister of the cycle-180 node-key int/float fix; same
    canonicalisation pattern applied to edge keys.

    Fix: collapse bool/int (via i64 extraction since bool is a subclass
    of int) AND integral floats (finite, in i64 range, zero fractional
    part) into a single ``"int:N"`` canonical; non-integral / out-of-
    range / non-finite floats keep ``"float:..."`` so NaN, Inf, 1.5,
    1e20 remain distinct edge keys.
    """
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edge('a', 'b', key=0)

        # has_edge with hash-equivalent keys
        for q in (0, 0.0, -0.0, False):
            assert G.has_edge('a', 'b', key=q), (
                f"{cls.__name__}.has_edge('a','b',key={q!r}) should be True "
                f"after add_edge(key=0)"
            )

        # has_edge with non-equivalent key returns False
        for q in (1, 1.0, True, 0.5, float('nan'), float('inf')):
            assert not G.has_edge('a', 'b', key=q), (
                f"{cls.__name__}.has_edge('a','b',key={q!r}) should be False"
            )

        # add_edge with hash-equivalent keys must dedup, not duplicate
        G2 = cls()
        G2.add_edge('a', 'b', key=0)
        G2.add_edge('a', 'b', key=0.0)
        G2.add_edge('a', 'b', key=False)
        G2.add_edge('a', 'b', key=-0.0)
        assert G2.number_of_edges() == 1, (
            f"{cls.__name__}: 0/0.0/False/-0.0 should coalesce to 1 edge, "
            f"got {G2.number_of_edges()}: {list(G2.edges(keys=True))}"
        )

        # Distinct: NaN, Inf, non-integral, out-of-i64-range floats
        # remain separate edges.
        G3 = cls()
        for k in (0, 0.5, float('nan'), float('inf'), 1e20):
            G3.add_edge('a', 'b', key=k)
        assert G3.number_of_edges() == 5, (
            f"{cls.__name__}: non-integral / out-of-range / non-finite "
            f"float keys should remain distinct edges, got "
            f"{G3.number_of_edges()}: {list(G3.edges(keys=True))}"
        )

        # Auto-assigned key collides with explicit float
        G4 = cls()
        k = G4.add_edge('a', 'b')  # auto-assigns 0
        assert k == 0
        G4.add_edge('a', 'b', key=0.0)  # should hit the same edge
        assert G4.number_of_edges() == 1


def test_multigraph_edge_key_first_add_wins_for_displayed_py_object():
    """br-r37-c1-edgekeyfirstwins: cosmetic sister of cycle 182's
    edge-key int/float canonicalisation fix and cycle 181's add_node
    first-wins fix.  After cycle 182, hash-equivalent edge keys
    (e.g. ``0`` / ``0.0`` / ``False``) coalesce to a single edge —
    but ``remember_edge_key`` / ``remember_edge_key_object`` in
    Rust used unconditional ``HashMap::insert`` for the
    ``edge_py_keys`` map, so the LAST Py-form overwrote the
    canonical display:

      Sequence              nx                       fnx (pre-fix)
      --------              ---                      -------------
      add(0),add(0.0),add(False)  [('a','b',0)]      [('a','b',False)]
      add(0.0),add(0),add(False)  [('a','b',0.0)]    [('a','b',False)]
      add(False),add(0),add(0.0)  [('a','b',False)]  [('a','b',0.0)]
      add(1.0),add(1),add(True)   [('a','b',1.0)]    [('a','b',True)]

    Affected ``list(G.edges(keys=True))``, edge-iteration ordering,
    and any caller introspecting edge-key types via
    ``type(triple[2])``. The numeric value comparison was correct
    (since ``0 == 0.0 == False``), but the displayed Py-form was
    last-wins instead of nx's first-wins.

    Critically: ``add_edge`` STILL echoes back the user-provided
    Py-form as its return value (matching nx's contract).  Only
    the stored display form is first-wins.

    Fix: align the four edge_py_keys mutation sites
    (``remember_edge_key`` × 2 + ``remember_edge_key_object`` × 2,
    in lib.rs and digraph.rs) with the entry().or_insert_with
    pattern, mirroring cycle 181's ``add_node`` fix.
    """
    cases = [
        ([0, 0.0, False],   [('a', 'b', 0)],     "int"),
        ([0.0, 0, False],   [('a', 'b', 0.0)],   "float"),
        ([False, 0, 0.0],   [('a', 'b', False)], "bool"),
        ([1.0, 1, True],    [('a', 'b', 1.0)],   "float"),
        ([True, 1, 1.0],    [('a', 'b', True)],  "bool"),
    ]

    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        for ops, expected_edges, expected_type in cases:
            G = cls()
            for k in ops:
                G.add_edge('a', 'b', key=k)
            actual = list(G.edges(keys=True))
            assert actual == expected_edges, (
                f"{cls.__name__}.add_edge keys {ops}: "
                f"expected {expected_edges}, got {actual}"
            )
            assert type(actual[0][2]).__name__ == expected_type, (
                f"{cls.__name__}.add_edge keys {ops}: "
                f"expected first edge-key type {expected_type}, got "
                f"{type(actual[0][2]).__name__}"
            )

    # add_edge STILL echoes the user-provided Py-form (matching nx)
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        k1 = G.add_edge('a', 'b', key=0)
        k2 = G.add_edge('a', 'b', key=0.0)
        k3 = G.add_edge('a', 'b', key=False)
        assert k1 == 0 and type(k1).__name__ == "int"
        assert k2 == 0.0 and type(k2).__name__ == "float"
        assert k3 is False and type(k3).__name__ == "bool"
        # But the displayed stored form is the first-added (int 0)
        edges = list(G.edges(keys=True))
        assert len(edges) == 1
        assert type(edges[0][2]).__name__ == "int"

    # Auto-assigned key (0) followed by explicit float key — still first-wins
    for cls in (fnx.MultiGraph, fnx.MultiDiGraph):
        G = cls()
        G.add_edge('a', 'b')
        G.add_edge('a', 'b', key=0.0)
        edges = list(G.edges(keys=True))
        assert edges == [('a', 'b', 0)]
        assert type(edges[0][2]).__name__ == "int"


def test_node_and_edge_views_are_unhashable():
    """br-r37-c1-viewhash: nx's NodeView, OutEdgeView, MultiEdgeView,
    OutMultiEdgeView, AtlasView, AdjacencyView all inherit from
    ``collections.abc.Mapping`` which sets ``__hash__ = None`` —
    making ``hash(view)`` raise ``TypeError: unhashable type: ...``
    and forbidding views as dict keys / set elements.

    Pre-fix fnx assigned an id-based ``__hash__`` to all four
    NodeView types (``_node_view_hash`` returning ``id(self)``)
    and to the three EdgeView classes for DiGraph/MultiGraph/
    MultiDiGraph (``id(self._graph)``).  This silently accepted
    views in hash contexts, diverging on a contract that drop-in
    callers rely on:

      ``set([G.nodes])``      — nx raises TypeError, fnx silently accepted
      ``{G.edges: 1}``        — nx raises, fnx (for DiGraph/MultiGraph/MDG) silently accepted
      ``hash(G.nodes)``       — nx raises, fnx returned an int

    Note ``Graph.edges`` (the first-defined EdgeView) was already
    correctly unhashable; the divergence affected NodeView for all
    four classes plus EdgeView for the three non-Graph classes.

    Fix: set ``__hash__ = None`` on the relevant view types.  Set
    protocol operators (``&``, ``|``, ``<=``, ``isdisjoint``)
    still work because they iterate the view contents rather than
    hashing the view itself.
    """
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls = getattr(fnx, cls_name)
        G = cls()
        G.add_edge(1, 2)

        for view_name in ("nodes", "edges", "adj"):
            view = getattr(G, view_name)
            try:
                hash(view)
            except TypeError:
                pass
            else:
                raise AssertionError(
                    f"{cls_name}.{view_name} should be unhashable, but hash() succeeded "
                    f"(type={type(view).__module__}.{type(view).__qualname__})"
                )

    # Set protocol operators still work (iterate, not hash)
    for cls_name in ("Graph", "DiGraph"):
        cls = getattr(fnx, cls_name)
        G1 = cls(); G1.add_nodes_from([1, 2, 3])
        G2 = cls(); G2.add_nodes_from([2, 3, 4])
        assert G1.nodes & G2.nodes == {2, 3}
        assert G1.nodes <= G1.nodes
        assert G1.nodes.isdisjoint({99})
        assert set(G1.nodes) == {1, 2, 3}
        assert G1.nodes == G1.nodes  # __eq__ still works

    # View-in-hash-context raises TypeError (matches nx)
    G = fnx.Graph()
    try:
        set([G.nodes])
    except TypeError:
        pass
    else:
        raise AssertionError("set([G.nodes]) should raise TypeError")

    G = fnx.DiGraph()
    try:
        {G.edges: 1}
    except TypeError:
        pass
    else:
        raise AssertionError("{DiGraph.edges: 1} should raise TypeError")


def test_node_and_edge_views_register_as_mapping_abc():
    """br-r37-c1-vmapabc: nx's NodeView, OutEdgeView, MultiEdgeView,
    OutMultiEdgeView all inherit from ``collections.abc.Mapping`` —
    so ``isinstance(G.nodes, Mapping)`` and ``isinstance(G.edges,
    Mapping)`` return True. Drop-in code that uses the Mapping ABC
    for type dispatch (e.g.  ``if isinstance(x, Mapping): for k, v
    in x.items(): ...``) handles views uniformly with plain dicts.

    Pre-fix the Rust-bound + Python-wrapped fnx view types were
    registered as ``Set`` virtual subclasses but NOT as ``Mapping``,
    so the isinstance check returned False — breaking type-dispatch
    paths across all 8 view × graph-class combinations:

      Graph.nodes / .edges                 Mapping check returned False
      DiGraph.nodes / .edges                Mapping check returned False
      MultiGraph.nodes / .edges             Mapping check returned False
      MultiDiGraph.nodes / .edges           Mapping check returned False

    The full Mapping protocol is already implemented (``__getitem__``
    / ``__len__`` / ``__iter__`` / ``__contains__`` / ``keys`` /
    ``values`` / ``items`` / ``get``), so virtual registration via
    ``Mapping.register(view_type)`` is safe.
    """
    from collections.abc import Mapping

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls = getattr(fnx, cls_name)
        G = cls()
        G.add_edge(1, 2)
        for view_name in ("nodes", "edges"):
            view = getattr(G, view_name)
            assert isinstance(view, Mapping), (
                f"{cls_name}.{view_name} should be isinstance(_, Mapping); "
                f"type={type(view).__module__}.{type(view).__qualname__}"
            )

    # Set protocol still works (registration as Mapping doesn't break Set ops)
    G1 = fnx.path_graph(5)
    G2 = fnx.path_graph(7)
    assert G1.nodes & G2.nodes == {0, 1, 2, 3, 4}
    assert G1.nodes <= G2.nodes
    assert G1.nodes.isdisjoint({99})

    # Mapping protocol works post-registration
    G = fnx.Graph()
    G.add_node(1, color="red")
    assert G.nodes[1] == {"color": "red"}
    assert G.nodes.get(1) == {"color": "red"}
    assert G.nodes.get(99) is None
    assert dict(G.nodes.items()) == {1: {"color": "red"}}


def test_view_keys_values_items_return_proper_view_types():
    """br-r37-c1-vkeysview: nx's NodeView and Multi*EdgeView return
    ``KeysView`` / ``ValuesView`` / ``ItemsView`` from
    ``.keys()`` / ``.values()`` / ``.items()`` (via Mapping
    inheritance), supporting Set algebra:

      G.nodes.keys() & {0, 1, 99}     # returns set intersection
      G.nodes.items() | other_items   # set union

    Pre-fix fnx returned plain ``list`` (or ``generator`` /
    ``list_iterator`` on Multi*Graph.edges), breaking these
    operations:

      G.nodes.keys() & {0, 1}
      → TypeError: unsupported operand type(s) for &: 'list' and 'set'

    Affected 18 method × view × class combinations:
      keys/values/items × {Graph, DiGraph, MultiGraph, MultiDiGraph}
      .nodes  (12 combos)
      keys/values/items × {MultiGraph, MultiDiGraph}.edges (6 combos)

    Graph.edges and DiGraph.edges already returned proper view types
    via the existing _adjacency_view_keys/items/values helpers.

    Fix: now that views register as Mapping (cycle 185), wrap each
    NodeView and Multi*EdgeView's keys/values/items to return
    ``cabc.KeysView(self)`` / ``cabc.ValuesView(self)`` /
    ``cabc.ItemsView(self)`` — the canonical Mapping-derived view
    types that nx returns.
    """
    from collections.abc import KeysView, ValuesView, ItemsView

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        cls = getattr(fnx, cls_name)
        G = cls()
        G.add_edge(1, 2)
        for view_name in ("nodes", "edges"):
            view = getattr(G, view_name)
            assert isinstance(view.keys(), KeysView), (
                f"{cls_name}.{view_name}.keys() should return KeysView, "
                f"got {type(view.keys()).__name__}"
            )
            assert isinstance(view.values(), ValuesView), (
                f"{cls_name}.{view_name}.values() should return ValuesView, "
                f"got {type(view.values()).__name__}"
            )
            assert isinstance(view.items(), ItemsView), (
                f"{cls_name}.{view_name}.items() should return ItemsView, "
                f"got {type(view.items()).__name__}"
            )

    # Set algebra on keys() works
    G = fnx.path_graph(5)
    assert G.nodes.keys() & {0, 1, 99} == {0, 1}
    assert G.nodes.keys() | {99} == {0, 1, 2, 3, 4, 99}
    assert G.nodes.keys() - {0, 1} == {2, 3, 4}

    # Re-iterability (a regression that the underlying generator
    # impl had on Multi*Graph.edges)
    MG = fnx.MultiGraph()
    MG.add_edge('a', 'b', key=0)
    MG.add_edge('a', 'b', key='x')
    items = MG.edges.items()
    pass1 = list(items)
    pass2 = list(items)
    assert pass1 == pass2 == [(('a', 'b', 0), {}), (('a', 'b', 'x'), {})], (
        f"Multi*Graph.edges.items() must be re-iterable; "
        f"pass1={pass1} pass2={pass2}"
    )

    # Functional values match
    G = fnx.Graph()
    G.add_node(1, color="red")
    G.add_node(2, color="blue")
    assert list(G.nodes.keys()) == [1, 2]
    assert list(G.nodes.values()) == [{"color": "red"}, {"color": "blue"}]
    assert list(G.nodes.items()) == [(1, {"color": "red"}), (2, {"color": "blue"})]
    assert len(G.nodes.keys()) == 2
    assert 1 in G.nodes.keys()


def test_edge_view_repr_class_name_matches_networkx():
    """br-r37-c1-evrname: the EdgeView ``__repr__`` was dispatching
    on the private ``_DiGraphEdgeView`` / ``_MultiGraphEdgeView`` /
    ``_MultiDiGraphEdgeView`` qualnames, but elsewhere these classes
    already had their ``__name__`` renamed to the canonical nx
    forms (``OutEdgeView`` / ``MultiEdgeView`` / ``OutMultiEdgeView``).
    The private-name branches never matched, falling through to the
    default ``EdgeView`` label — so ``repr(DG.edges)`` showed
    ``EdgeView([...])`` instead of nx's ``OutEdgeView([...])``.

    Affects three classes:
      DiGraph.edges:      "EdgeView"  →  should be "OutEdgeView"
      MultiGraph.edges:   "EdgeView"  →  should be "MultiEdgeView"
      MultiDiGraph.edges: "EdgeView"  →  should be "OutMultiEdgeView"

    Drop-in code that does ``repr(G.edges).startswith("OutEdgeView(")``
    to detect a directed graph's edge view (or similar string-prefix
    parsing) silently mis-detected.

    Fix: dispatch on ``type(self).__name__`` directly, which is
    already the canonical nx form by the time repr runs.

    Closes the three pre-existing failing tests in
    test_view_repr_parity.py:
      test_digraph_edge_view_uses_out_edge_view_prefix
      test_multigraph_edge_view_uses_multi_edge_view_prefix
      test_multidigraph_edge_view_uses_out_multi_edge_view_prefix
    """
    import networkx as nx

    cases = [
        (fnx.DiGraph,      nx.DiGraph,      "OutEdgeView"),
        (fnx.MultiGraph,   nx.MultiGraph,   "MultiEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "OutMultiEdgeView"),
        (fnx.Graph,        nx.Graph,        "EdgeView"),
    ]
    for f_cls, n_cls, expected_prefix in cases:
        Gf = f_cls([(0, 1), (1, 2)])
        Gn = n_cls([(0, 1), (1, 2)])
        assert repr(Gf.edges).startswith(f"{expected_prefix}("), (
            f"{f_cls.__name__}.edges repr should start with "
            f"{expected_prefix!r}, got: {repr(Gf.edges)}"
        )
        assert repr(Gf.edges) == repr(Gn.edges), (
            f"{f_cls.__name__}.edges repr should match nx exactly: "
            f"fnx={repr(Gf.edges)!r} nx={repr(Gn.edges)!r}"
        )


def test_directed_in_out_edge_and_degree_view_class_names_match_nx():
    """br-r37-c1-emvname / br-r37-c1-degviewname: nx exposes per-direction-
    × multi class names for DiGraph/MultiDiGraph in/out edges and
    degree views:

      DiGraph.in_edges            → InEdgeView
      DiGraph.out_edges           → OutEdgeView
      DiGraph.in_degree           → InDegreeView
      DiGraph.out_degree          → OutDegreeView
      MultiDiGraph.in_edges       → InMultiEdgeView
      MultiDiGraph.out_edges      → OutMultiEdgeView
      MultiDiGraph.in_degree      → InMultiDegreeView
      MultiDiGraph.out_degree     → OutMultiDegreeView

    Pre-fix fnx used a single ``_DiEdgeMethodView`` for all four edge
    properties and ``_DirectedDegreeView`` for all four degree
    properties — so ``type(view).__name__`` was always the private
    ``_DiEdgeMethodView`` / ``_DirectedDegreeView`` regardless of
    direction or multi-ness. Repr was correspondingly broken:

      DG.in_edges          repr: [(1, 2), (2, 3)]
                           (no class wrapper — nx shows InEdgeView([...]))

      DG.in_degree         repr: <franken_networkx.
                                   _DirectedDegreeView object at 0x...>
                           (default object repr — nx shows
                            InDegreeView({1: 0, 2: 1, ...}))

    Drop-in code that introspects ``type(view).__name__`` or parses
    ``repr(view).startswith("InEdgeView(")`` (a documented nx idiom)
    silently mis-detected.

    Fix: define four trivial subclasses of each base
    (``_InEdgeView``, ``_OutEdgeView``, ``_InMultiEdgeView``,
    ``_OutMultiEdgeView`` and ``_InDegreeView`` / ``_OutDegreeView``
    / ``_InMultiDegreeView`` / ``_OutMultiDegreeView``), each with
    the canonical nx ``__name__`` set, and route the four properties
    on each class to the right subclass. Add a base-class
    ``__repr__`` that uses ``type(self).__name__`` so each subclass
    formats correctly.
    """
    import networkx as nx

    cases = [
        (fnx.DiGraph,      nx.DiGraph,      "in_edges",   "InEdgeView"),
        (fnx.DiGraph,      nx.DiGraph,      "out_edges",  "OutEdgeView"),
        (fnx.DiGraph,      nx.DiGraph,      "in_degree",  "InDegreeView"),
        (fnx.DiGraph,      nx.DiGraph,      "out_degree", "OutDegreeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "in_edges",   "InMultiEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "out_edges",  "OutMultiEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "in_degree",  "InMultiDegreeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "out_degree", "OutMultiDegreeView"),
    ]
    for f_cls, n_cls, view_name, expected_name in cases:
        Gf = f_cls([(1, 2), (2, 3)])
        Gn = n_cls([(1, 2), (2, 3)])
        view_f = getattr(Gf, view_name)
        view_n = getattr(Gn, view_name)
        assert type(view_f).__name__ == expected_name, (
            f"{f_cls.__name__}.{view_name} class __name__ should be "
            f"{expected_name!r}, got {type(view_f).__name__!r}"
        )
        assert repr(view_f).startswith(f"{expected_name}("), (
            f"{f_cls.__name__}.{view_name} repr should start with "
            f"{expected_name!r}(, got: {repr(view_f)}"
        )
        assert repr(view_f) == repr(view_n), (
            f"{f_cls.__name__}.{view_name} repr should match nx: "
            f"fnx={repr(view_f)} nx={repr(view_n)}"
        )

    # Behavior of the views still works
    DG = fnx.DiGraph([(1, 2)])
    assert list(DG.in_edges) == [(1, 2)]
    assert (1, 2) in DG.in_edges
    assert DG.in_degree[1] == 0
    assert DG.in_degree[2] == 1
    assert list(DG.in_degree) == [(1, 0), (2, 1)]
    assert len(DG.in_edges) == 1


def test_signature_parity_with_backend_dispatch_for_dispatchable_wrappers():
    """br-r37-c1-sigsig: lock the cycle-178 architectural decision —
    fnx wrappers around @_dispatchable nx functions must mirror nx's
    full signature INCLUDING ``*, backend=None, **backend_kwargs``,
    so the canonical drop-in idiom

      result = nx.<fn>(..., backend='networkx')

    works on fnx without TypeError.

    A handful of older signature-parity tests had been written
    against the pre-cycle-178 reality where fnx wrappers exposed
    only the core public params; they stripped backend/backend_kwargs
    from nx's params and compared the stripped form to fnx's full
    params, which broke once cycle 178 made fnx mirror the full
    signature.

    This regression locks the new ground truth: ``str(fnx_sig) ==
    str(nx_sig)`` for the dispatchable wrappers that previously had
    stale tests, plus a sample of others to confirm the contract.
    """
    import networkx as nx
    import inspect

    targets = (
        "minimum_cycle_basis",
        "random_labeled_rooted_forest",
        "graph_edit_distance",
        "optimize_graph_edit_distance",
        "optimize_edit_paths",
        "join_trees",
    )
    for name in targets:
        f = getattr(fnx, name, None)
        n = getattr(nx, name, None)
        if f is None or n is None:
            continue
        f_sig = str(inspect.signature(f))
        n_sig = str(inspect.signature(n))
        assert f_sig == n_sig, (
            f"{name} signature mismatch:\n  fnx={f_sig}\n  nx ={n_sig}"
        )

    # Sanity: the canonical drop-in idiom works
    G = fnx.cycle_graph(4)
    cycles = fnx.minimum_cycle_basis(G, backend="networkx")
    assert len(cycles) == 1


def test_undirected_and_multi_degree_view_class_names_match_nx():
    """br-r37-c1-mdvname: completes the cycle-188 directed in/out
    degree view-name fix by aligning the four undirected-/multi-/
    self-direction degree views with nx's canonical class names:

      Graph.degree            → DegreeView
      DiGraph.degree          → DiDegreeView
      MultiGraph.degree       → MultiDegreeView
      MultiDiGraph.degree     → DiMultiDegreeView

    Pre-fix:
      Graph.degree class name was ``_WeightAwareDegreeView``
      DiGraph.degree class name was ``_WeightAwareDegreeView``
      MultiGraph.degree class name was ``MultiGraphDegreeView``
      MultiDiGraph.degree class name was ``MultiDiGraphDegreeView``
      MultiGraph.degree had no __repr__ (default object.__repr__)
      MultiDiGraph.degree had no __repr__ (default object.__repr__)

    Pre-fix the shared module-level _degree_view_repr hardcoded
    ``DegreeView`` as the label, masking the class-name divergence in
    the displayed repr but still wrong on ``type(view).__name__``.

    Fix:
      - Two trivial subclasses of _WeightAwareDegreeView
        (_GraphDegreeView named "DegreeView", _DiGraphDegreeView
        named "DiDegreeView") + bind to _graph_degree / _digraph_degree.
      - __name__ assignments on MultiGraphDegreeView ("MultiDegreeView")
        and MultiDiGraphDegreeView ("DiMultiDegreeView").
      - __repr__ added on the two Multi* classes.
      - module-level _degree_view_repr now uses
        type(self).__name__ instead of hardcoded "DegreeView".
    """
    import networkx as nx

    cases = [
        (fnx.Graph,        nx.Graph,        "DegreeView"),
        (fnx.DiGraph,      nx.DiGraph,      "DiDegreeView"),
        (fnx.MultiGraph,   nx.MultiGraph,   "MultiDegreeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "DiMultiDegreeView"),
    ]
    for f_cls, n_cls, expected_name in cases:
        Gf = f_cls([(1, 2), (2, 3)])
        Gn = n_cls([(1, 2), (2, 3)])
        assert type(Gf.degree).__name__ == expected_name, (
            f"{f_cls.__name__}.degree __name__ should be "
            f"{expected_name!r}, got {type(Gf.degree).__name__!r}"
        )
        assert repr(Gf.degree).startswith(f"{expected_name}("), (
            f"{f_cls.__name__}.degree repr should start with "
            f"{expected_name!r}(, got: {repr(Gf.degree)}"
        )
        assert repr(Gf.degree) == repr(Gn.degree), (
            f"{f_cls.__name__}.degree repr should match nx: "
            f"fnx={repr(Gf.degree)} nx={repr(Gn.degree)}"
        )

    # Behavior smoke tests post-fix
    G = fnx.path_graph(5)
    assert G.degree[2] == 2
    assert dict(G.degree) == {0: 1, 1: 2, 2: 2, 3: 2, 4: 1}
    DG = fnx.DiGraph([(1, 2), (2, 3)])
    assert DG.degree[2] == 2
    assert dict(DG.degree) == {1: 1, 2: 2, 3: 1}


def test_nodes_data_returns_node_data_view_matching_nx():
    """br-r37-c1-nvdata: nx's NodeView.data() returns a
    ``NodeDataView`` instance — a Set-typed view supporting indexing
    as a Mapping (``dv[node]`` → attrs) AND tuple-membership semantics
    (``(node, attrs) in dv`` → bool).

    Pre-fix the Rust-bound NodeView's ``data`` method returned the
    underlying NodeView itself, so:

      type(G.nodes.data()).__name__   →  "NodeView" (nx: "NodeDataView")
      (1, {"color": "red"}) in G.nodes.data()
                                      →  TypeError: unhashable
                                         type: 'dict'
                                         (nx: True)
      isinstance(G.nodes.data(), Set) →  False (nx: True)

    The ``__call__(data=True)`` path was already correctly wrapped
    via ``_node_view_call_with_attr_support`` to return NodeDataView,
    but the ``.data()`` shortcut bypassed that wrapper. This fix
    routes ``.data()`` through the same NodeDataView wrapper.

    Affects all 4 graph classes (Graph, DiGraph, MultiGraph,
    MultiDiGraph) since the bound ``.data()`` method comes from the
    Rust-bound NodeView types in each.
    """
    import networkx as nx
    import collections.abc as cabc

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        Gf = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        Gn = getattr(nx, cls_name)([(1, 2), (2, 3)])
        Gf.add_node(1, color="red")
        Gn.add_node(1, color="red")

        f_dv = Gf.nodes.data()
        n_dv = Gn.nodes.data()
        # Class-name parity
        assert type(f_dv).__name__ == type(n_dv).__name__ == "NodeDataView", (
            f"{cls_name}.nodes.data() class: fnx={type(f_dv).__name__} "
            f"nx={type(n_dv).__name__}"
        )
        # repr parity
        assert repr(f_dv) == repr(n_dv), (
            f"{cls_name}.nodes.data() repr: fnx={repr(f_dv)} nx={repr(n_dv)}"
        )
        # Indexing as Mapping: dv[node] → attrs
        assert f_dv[1] == n_dv[1] == {"color": "red"}
        # Set protocol: tuple-membership doesn't TypeError
        # (matches nx's NodeDataView.__contains__ semantics)
        assert (1, {"color": "red"}) in f_dv
        assert (1, {"color": "red"}) in n_dv
        # Set ABC registration
        assert isinstance(f_dv, cabc.Set), (
            f"{cls_name}.nodes.data() should be isinstance(_, Set)"
        )

    # data='attr' projection still works
    G = fnx.Graph()
    G.add_node(1, color="red")
    G.add_node(2)
    assert list(G.nodes.data("color")) == [(1, "red"), (2, None)]
    assert list(G.nodes.data("color", default="X")) == [(1, "red"), (2, "X")]

    # data=False returns the underlying NodeView (live)
    nv = G.nodes
    assert type(nv.data(False)).__name__ == "NodeView"
    assert nv.data(False) == nv


def test_edges_data_returns_canonical_edge_data_view_class():
    """br-r37-c1-edvname: nx exposes per-direction × multi class
    names for ``.edges.data()`` and ``.in_edges.data()`` /
    ``.out_edges.data()``:

      Graph.edges.data()              EdgeDataView
      DiGraph.edges.data()            OutEdgeDataView
      DiGraph.in_edges.data()         InEdgeDataView
      DiGraph.out_edges.data()        OutEdgeDataView
      MultiGraph.edges.data()         MultiEdgeDataView
      MultiDiGraph.edges.data()       OutMultiEdgeDataView
      MultiDiGraph.in_edges.data()    InMultiEdgeDataView
      MultiDiGraph.out_edges.data()   OutMultiEdgeDataView

    Pre-fix (post-cycle 188 view-class split, but pre this fix):

      Graph.edges.data()                    EdgeDataView   (already correct)
      DiGraph.edges.data()                  list           (wrong)
      DiGraph.in_edges.data()               list           (wrong)
      DiGraph.out_edges.data()              list           (wrong)
      MultiGraph.edges.data()               _EdgeListWithSetAlgebra (wrong)
      MultiDiGraph.edges.data()             _EdgeListWithSetAlgebra (wrong)
      MultiDiGraph.in_edges.data()          list           (wrong)
      MultiDiGraph.out_edges.data()         list           (wrong)

    7 of 8 combinations diverged on ``type(view).__name__``.

    Drop-in code that introspects ``type(view).__name__`` to detect
    direction / multi-ness, parses ``repr(view).startswith(
    'OutEdgeDataView(')``, or branches on the class hint silently
    misbehaved.

    Fix: define five trivial ``_EdgeListWithSetAlgebra`` subclasses
    (``_OutEdgeDataView``, ``_InEdgeDataView``, ``_MultiEdgeDataView``,
    ``_OutMultiEdgeDataView``, ``_InMultiEdgeDataView``) with
    canonical nx ``__name__`` set, and route each ``.data()``
    method to wrap the result in the appropriate one.  Set-algebra
    inherits from _EdgeListWithSetAlgebra so set-typed expressions
    still work.
    """
    import networkx as nx

    cases = [
        (fnx.Graph,        nx.Graph,        "edges",     "EdgeDataView"),
        (fnx.DiGraph,      nx.DiGraph,      "edges",     "OutEdgeDataView"),
        (fnx.DiGraph,      nx.DiGraph,      "in_edges",  "InEdgeDataView"),
        (fnx.DiGraph,      nx.DiGraph,      "out_edges", "OutEdgeDataView"),
        (fnx.MultiGraph,   nx.MultiGraph,   "edges",     "MultiEdgeDataView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "edges",     "OutMultiEdgeDataView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "in_edges",  "InMultiEdgeDataView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "out_edges", "OutMultiEdgeDataView"),
    ]
    for f_cls, n_cls, view_name, expected_name in cases:
        Gf = f_cls([(1, 2), (2, 3)])
        Gn = n_cls([(1, 2), (2, 3)])
        view_f = getattr(Gf, view_name)
        view_n = getattr(Gn, view_name)
        f_dv = view_f.data()
        n_dv = view_n.data()
        assert type(f_dv).__name__ == expected_name, (
            f"{f_cls.__name__}.{view_name}.data() class: "
            f"fnx={type(f_dv).__name__} expected={expected_name}"
        )
        assert type(n_dv).__name__ == expected_name, (
            f"sanity: nx {n_cls.__name__}.{view_name}.data() should be "
            f"{expected_name}, got {type(n_dv).__name__}"
        )

    # Functional smoke
    G = fnx.Graph([(1, 2, {"weight": 3.0})])
    assert list(G.edges.data()) == [(1, 2, {"weight": 3.0})]
    assert list(G.edges.data("weight")) == [(1, 2, 3.0)]
    DG = fnx.DiGraph([(1, 2)])
    assert list(DG.in_edges.data()) == [(1, 2, {})]
    assert list(DG.out_edges.data()) == [(1, 2, {})]
    MG = fnx.MultiGraph([(1, 2)])
    assert list(MG.edges.data(keys=True)) == [(1, 2, 0, {})]


def test_subgraph_view_edges_class_names_match_nx():
    """br-r37-c1-fevname: subgraph-view ``.edges`` returned the
    private ``_FilteredEdgeView`` regardless of underlying graph
    class, with default-``object``-style ``<...object at 0x...>``
    repr.  nx exposes the canonical per-class name and a proper
    formatted repr:

      class            S.edges                S.edges repr
      -----            -------                ------------
      Graph            EdgeView               EdgeView([(u, v), ...])
      DiGraph          OutEdgeView            OutEdgeView([(u, v), ...])
      MultiGraph       MultiEdgeView          MultiEdgeView([(u, v, k), ...])
      MultiDiGraph     OutMultiEdgeView       OutMultiEdgeView([(u, v, k), ...])

    Affects ``G.subgraph(...).edges``, ``G.edge_subgraph(...).edges``,
    and ``nx.subgraph_view(G, ...).edges`` for all four graph classes.

    Drop-in code that introspects ``type(view).__name__`` to detect
    direction / multi-ness, parses ``repr(view).startswith(
    'OutEdgeView(')``, or logs/displays subgraphs silently
    misbehaved (the bare object repr is useless for debugging).

    Fix: define four trivial ``_FilteredEdgeView`` subclasses with
    canonical ``__name__`` (``_FilteredGraphEdgeView`` ⇒ "EdgeView",
    ``_FilteredOutEdgeView`` ⇒ "OutEdgeView", etc.), dispatch in
    ``SubgraphView.edges`` based on ``self.is_directed()`` /
    ``self.is_multigraph()``, and add base-class ``__repr__`` using
    ``type(self).__name__``.
    """
    import networkx as nx

    cases = [
        (fnx.Graph,        nx.Graph,        "EdgeView"),
        (fnx.DiGraph,      nx.DiGraph,      "OutEdgeView"),
        (fnx.MultiGraph,   nx.MultiGraph,   "MultiEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "OutMultiEdgeView"),
    ]
    for f_cls, n_cls, expected_name in cases:
        Gf = f_cls([(1, 2), (2, 3), (3, 4)])
        Gn = n_cls([(1, 2), (2, 3), (3, 4)])
        Sf = Gf.subgraph([1, 2, 3])
        Sn = Gn.subgraph([1, 2, 3])
        assert type(Sf.edges).__name__ == expected_name, (
            f"{f_cls.__name__}.subgraph().edges class: "
            f"fnx={type(Sf.edges).__name__} expected={expected_name}"
        )
        assert repr(Sf.edges).startswith(f"{expected_name}("), (
            f"{f_cls.__name__}.subgraph().edges repr should start with "
            f"{expected_name!r}(, got: {repr(Sf.edges)}"
        )
        assert repr(Sf.edges) == repr(Sn.edges), (
            f"{f_cls.__name__}.subgraph().edges repr should match nx: "
            f"fnx={repr(Sf.edges)!r} nx={repr(Sn.edges)!r}"
        )

    # Functional smoke: behavior preserved through the subclass
    G = fnx.path_graph(5)
    S = G.subgraph([1, 2, 3])
    assert list(S.edges) == [(1, 2), (2, 3)]
    assert (1, 2) in S.edges
    assert S.edges == S.edges
    assert len(S.edges) == 2
    # Set algebra still works
    assert S.edges & {(1, 2)} == {(1, 2)}


def test_subgraph_view_nodes_and_degree_class_names_and_repr():
    """br-r37-c1-snvrepr: subgraph-view ``.nodes`` and ``.degree``
    diverged from nx on both class name (degree only) and repr
    formatting (both):

      class             S.nodes repr           S.degree class           S.degree repr
      -----             ------------           ----------------         -------------
      Graph             NodeView((1,2,3))      DegreeView               DegreeView({...})
      DiGraph           NodeView((1,2,3))      DiDegreeView             DiDegreeView({...})
      MultiGraph        NodeView((1,2,3))      MultiDegreeView          MultiDegreeView({...})
      MultiDiGraph      NodeView((1,2,3))      DiMultiDegreeView        DiMultiDegreeView({...})

    Pre-fix:
      - Subgraph ``NodeView`` (defined alongside _FilteredEdgeView,
        not the Rust-bound one used on plain Graph) had no
        ``__repr__`` — fell through to default
        ``<franken_networkx.NodeView object at 0x...>``.
      - All four ``S.degree`` views were instances of the private
        ``_AssignedPrivateDegreeView`` regardless of underlying
        graph class — wrong ``type(view).__name__`` and default
        ``<...object at 0x...>`` repr.

    Drop-in code that introspects ``type(view).__name__`` to detect
    direction / multi-ness from a degree view, parses
    ``repr(view).startswith('DiDegreeView(')``, or logs/displays
    subgraphs silently misbehaved.

    Fix:
      1. NodeView (subgraph variant): add ``__repr__`` returning
         ``f"NodeView({tuple(self)!r})"``.
      2. Define 4 trivial ``_AssignedPrivateDegreeView`` subclasses
         (``_AssignedDegreeView`` / ``_AssignedDiDegreeView`` /
         ``_AssignedMultiDegreeView`` / ``_AssignedDiMultiDegreeView``)
         with canonical nx ``__name__``.
      3. Dispatch in ``_private_aware_degree`` based on
         ``self.is_directed()`` / ``self.is_multigraph()``.
      4. Add base-class ``__repr__`` using ``type(self).__name__``.
    """
    import networkx as nx

    cases = [
        (fnx.Graph,        nx.Graph,        "DegreeView"),
        (fnx.DiGraph,      nx.DiGraph,      "DiDegreeView"),
        (fnx.MultiGraph,   nx.MultiGraph,   "MultiDegreeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "DiMultiDegreeView"),
    ]
    for f_cls, n_cls, expected_degree_name in cases:
        Gf = f_cls([(1, 2), (2, 3), (3, 4)])
        Gn = n_cls([(1, 2), (2, 3), (3, 4)])
        Sf = Gf.subgraph([1, 2, 3])
        Sn = Gn.subgraph([1, 2, 3])

        # NodeView repr parity
        assert repr(Sf.nodes) == repr(Sn.nodes), (
            f"{f_cls.__name__}.subgraph().nodes repr: "
            f"fnx={repr(Sf.nodes)!r} nx={repr(Sn.nodes)!r}"
        )
        assert repr(Sf.nodes).startswith("NodeView("), (
            f"{f_cls.__name__}.subgraph().nodes repr should start "
            f"with 'NodeView(', got: {repr(Sf.nodes)}"
        )

        # DegreeView class-name + repr parity
        assert type(Sf.degree).__name__ == expected_degree_name, (
            f"{f_cls.__name__}.subgraph().degree class: "
            f"fnx={type(Sf.degree).__name__} expected={expected_degree_name}"
        )
        assert repr(Sf.degree) == repr(Sn.degree), (
            f"{f_cls.__name__}.subgraph().degree repr: "
            f"fnx={repr(Sf.degree)} nx={repr(Sn.degree)}"
        )

    # Functional smoke
    G = fnx.path_graph(5)
    S = G.subgraph([1, 2, 3])
    assert list(S.nodes) == [1, 2, 3]
    assert dict(S.degree) == {1: 1, 2: 2, 3: 1}
    assert S.degree[2] == 2


def test_reverse_view_in_out_edges_and_degree_are_views_not_methods():
    """br-r37-c1-revview: ``DG.reverse(copy=False).in_edges /
    out_edges / degree`` must expose view-objects (callable +
    iterable + sized + indexable for degree) — matching nx's
    ``InEdgeView`` / ``OutEdgeView`` / ``DiDegreeView`` (and the
    Multi* variants).

    Pre-fix fnx exposed these as plain methods on
    ``_ReverseDirectedViewBase``, so ``R.in_edges`` returned a
    ``<bound method ...>`` and:

      list(R.in_edges)    →  TypeError: 'method' object is not iterable
      R.degree[node]       →  TypeError: 'method' object is not subscriptable

    nx exposes the equivalents as @property returning view objects,
    so ``list(R.in_edges)`` and ``R.degree[node]`` work directly.

    Fix: rename the existing computation methods to
    ``_in_edges_compute`` / ``_out_edges_compute`` / ``_degree_compute``
    and add ``@property`` getters returning small Proxy classes
    (``_RevInEdgeViewProxy`` etc.) with canonical nx ``__name__``
    that wrap the compute method as a callable + iterable + indexable
    view.

    Affects DiGraph and MultiDiGraph (the only classes with reverse
    views).
    """
    import networkx as nx

    cases = [
        (fnx.DiGraph,      nx.DiGraph,
            "InEdgeView", "OutEdgeView", "DiDegreeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph,
            "InMultiEdgeView", "OutMultiEdgeView", "DiMultiDegreeView"),
    ]
    for f_cls, n_cls, in_name, out_name, deg_name in cases:
        DGf = f_cls([(1, 2), (2, 3)])
        DGn = n_cls([(1, 2), (2, 3)])
        Rf = DGf.reverse(copy=False)
        Rn = DGn.reverse(copy=False)

        # In-edges: view, not bound method
        assert type(Rf.in_edges).__name__ == in_name
        assert list(Rf.in_edges) == list(Rn.in_edges)
        assert len(Rf.in_edges) == len(Rn.in_edges)

        # Out-edges
        assert type(Rf.out_edges).__name__ == out_name
        assert list(Rf.out_edges) == list(Rn.out_edges)

        # Degree: indexable + iterable
        assert type(Rf.degree).__name__ == deg_name
        assert Rf.degree[2] == Rn.degree[2]
        assert list(Rf.degree) == list(Rn.degree)
        # Calling forwards to the underlying compute method
        assert list(Rf.degree([2])) == list(Rn.degree([2]))

    # Smoke: complex case with weights
    DG = fnx.DiGraph()
    DG.add_edge(1, 2, weight=3.0)
    DG.add_edge(2, 3, weight=4.0)
    R = DG.reverse(copy=False)
    assert R.degree(1, weight="weight") == 3.0
    assert R.degree(2, weight="weight") == 7.0
    assert R.degree[2] == 2  # unweighted


def test_reverse_view_outer_class_name_and_view_class_names():
    """br-r37-c1-revouter / br-r37-c1-revadjname:
    ``DG.reverse(copy=False)`` returns a view object whose:

    - top-level class name should be ``DiGraph`` /
      ``MultiDiGraph`` (matching nx via @property over the
      underlying directed Graph type).  Pre-fix: private
      ``_ReverseDirectedView`` / ``_ReverseMultiDirectedView``.

    - ``.edges`` should be ``OutEdgeView`` /
      ``OutMultiEdgeView``.  Pre-fix: private ``_ReverseEdgeView``
      regardless of multi-ness; default-object repr.

    - ``.adj`` / ``.succ`` / ``.pred`` should be ``AdjacencyView``
      / ``MultiAdjacencyView``. Pre-fix: private
      ``_ReverseAdjacencyView``; default-object repr.

    Drop-in code that introspects ``type(view).__name__`` to
    detect direction / multi-ness or parses ``repr(view)
    .startswith('OutEdgeView(')`` silently misbehaved.

    Fix:
      1. Set ``__name__`` directly on _ReverseDirectedView /
         _ReverseMultiDirectedView to "DiGraph" / "MultiDiGraph".
      2. Add 2 _ReverseEdgeView subclasses (_ReverseOutEdgeView /
         _ReverseOutMultiEdgeView) with canonical names; dispatch
         in ``edges`` property based on multi-ness.
      3. Add 2 _ReverseAdjacencyView subclasses
         (_ReverseGraphAdjacencyView / _ReverseMultiAdjacencyView)
         with canonical names; dispatch at __init__ time based on
         multi-ness.
      4. Add base-class ``__repr__`` to both base view classes
         using ``type(self).__name__`` and a recursive Mapping-
         unwrap so the inner repr matches nx's plain-dict form.
    """
    import networkx as nx

    cases = [
        (fnx.DiGraph,      nx.DiGraph,
            "DiGraph", "OutEdgeView", "AdjacencyView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph,
            "MultiDiGraph", "OutMultiEdgeView", "MultiAdjacencyView"),
    ]
    for f_cls, n_cls, outer_name, edge_name, adj_name in cases:
        DGf = f_cls([(1, 2), (2, 3)])
        DGn = n_cls([(1, 2), (2, 3)])
        Rf = DGf.reverse(copy=False)
        Rn = DGn.reverse(copy=False)

        assert type(Rf).__name__ == outer_name, (
            f"{f_cls.__name__}.reverse(copy=False) outer class: "
            f"fnx={type(Rf).__name__} expected={outer_name}"
        )
        assert type(Rf.edges).__name__ == edge_name, (
            f"R.edges class: fnx={type(Rf.edges).__name__} expected={edge_name}"
        )
        for attr in ("adj", "succ", "pred"):
            v_f = getattr(Rf, attr)
            assert type(v_f).__name__ == adj_name, (
                f"R.{attr} class: fnx={type(v_f).__name__} expected={adj_name}"
            )
            # Repr matches nx exactly
            assert repr(v_f) == repr(getattr(Rn, attr)), (
                f"R.{attr} repr: fnx={repr(v_f)} nx={repr(getattr(Rn, attr))}"
            )
        assert repr(Rf.edges) == repr(Rn.edges)

        # isinstance still works for drop-in code that detects
        # directed/multi via isinstance instead of type-name string.
        assert isinstance(Rf, f_cls)


def test_subgraph_preserves_user_subclass():
    """br-r37-c1-subgraphsub: ``MyG(fnx.Graph).subgraph([1])`` must
    return a ``MyG`` instance — preserving the user subclass — to
    match nx's documented behaviour.

    Pre-fix fnx hardcoded the filtered-view type via
    ``_FILTERED_GRAPH_VIEW_TYPES`` keyed only on
    ``(directed, multi)``, casting any user subclass to the
    canonical Graph/DiGraph/MultiGraph/MultiDiGraph.

    nx parity:
      MyN.subgraph([1, 2])      → MyN
      MyN.edge_subgraph(...)    → MyN
      nx.subgraph_view(MyN, ..) → MyN

    Fix: in ``_generic_filtered_graph_view``, when the source graph
    is a user subclass (not one of the four canonical types AND
    not already a filtered-view), dynamically build a synthetic
    class combining ``_FilteredGraphView`` with the user subclass
    and cache it. Mark synthetic classes with
    ``_fnx_subclass_filtered_view = True`` so nested subgraph
    calls reuse the same synthetic class (preserving the user
    subclass through ``MyG.subgraph().subgraph()``).

    Standard graphs still use the canonical fast path
    (preserving cycle 188+ class-name parity).
    """
    class MyG(fnx.Graph):
        pass

    class MyDG(fnx.DiGraph):
        pass

    class MyMG(fnx.MultiGraph):
        pass

    class MyMDG(fnx.MultiDiGraph):
        pass

    # subgraph preserves user subclass
    g = MyG([(1, 2), (2, 3)])
    s = g.subgraph([1, 2])
    assert type(s).__name__ == "MyG"
    assert list(s.nodes) == [1, 2]
    assert fnx.is_frozen(s)

    # nested subgraph also preserves
    s2 = s.subgraph([1, 2])
    assert type(s2).__name__ == "MyG"
    assert list(s2.nodes) == [1, 2]

    # edge_subgraph preserves
    es = g.edge_subgraph([(1, 2)])
    assert type(es).__name__ == "MyG"

    # subgraph_view preserves
    sv = fnx.subgraph_view(g, filter_node=lambda n: n in (1, 2))
    assert type(sv).__name__ == "MyG"

    # All 4 canonical-class subclasses preserved
    for sub_cls, expected_name in [
        (MyDG, "MyDG"),
        (MyMG, "MyMG"),
        (MyMDG, "MyMDG"),
    ]:
        gg = sub_cls([(1, 2), (2, 3)])
        ss = gg.subgraph([1, 2])
        assert type(ss).__name__ == expected_name

    # Standard graph still uses canonical fast path
    G = fnx.path_graph(5)
    S = G.subgraph([1, 2, 3])
    assert type(S).__name__ == "Graph"
    # Idempotence preserved
    S2 = S.subgraph([1, 2])
    assert type(S2).__name__ == "Graph"


def test_view_copy_and_deepcopy_preserve_view_type():
    """br-r37-c1-vcopy: nx's NodeView and EdgeView preserve type
    through ``copy.copy`` and ``copy.deepcopy`` — both return a
    NodeView / EdgeView instance.

    Pre-fix the Rust-bound view types' ``__reduce__`` (used as the
    fallback by ``copy.copy`` and ``copy.deepcopy``) snapshotted to
    plain ``dict`` (NodeView) / ``list`` (EdgeView):

      copy.copy(G.nodes).__class__         dict      (nx: NodeView)
      copy.deepcopy(G.nodes).__class__     dict      (nx: NodeView)
      copy.copy(G.edges).__class__         list      (nx: EdgeView)
      copy.deepcopy(G.edges).__class__     list      (nx: EdgeView)

    isinstance(c, NodeView) returned False — breaking type-dispatch
    drop-in code that assumes view-type preservation.

    Fix: define ``__copy__`` / ``__deepcopy__`` on the Rust-bound
    view types that return self (semantically equivalent for
    read-only views; ``isinstance(c, NodeView)`` returns True).
    ``__reduce__`` keeps the snapshot behaviour for pickle (Rust
    graphs can't pickle by reference).
    """
    import copy
    import pickle

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        nv = G.nodes
        ev = G.edges

        # copy.copy preserves view type
        cnv = copy.copy(nv)
        cev = copy.copy(ev)
        assert type(cnv) is type(nv), (
            f"{cls_name}: copy.copy(G.nodes) class={type(cnv).__name__}"
        )
        assert type(cev) is type(ev), (
            f"{cls_name}: copy.copy(G.edges) class={type(cev).__name__}"
        )

        # copy.deepcopy preserves view type too
        dnv = copy.deepcopy(nv)
        dev = copy.deepcopy(ev)
        assert type(dnv) is type(nv), (
            f"{cls_name}: copy.deepcopy(G.nodes) class={type(dnv).__name__}"
        )
        assert type(dev) is type(ev), (
            f"{cls_name}: copy.deepcopy(G.edges) class={type(dev).__name__}"
        )

        # Behavior preserved
        assert list(cnv) == list(nv)
        assert list(cev) == list(ev)
        assert len(cnv) == len(nv)
        assert 1 in cnv
        # isinstance check works
        from collections.abc import Mapping
        assert isinstance(cnv, Mapping)

    # Pickle still snapshots (Rust graphs aren't picklable by
    # reference) — confirm pickle behaviour unchanged.
    G = fnx.path_graph(3)
    p = pickle.dumps(G.nodes)
    r = pickle.loads(p)
    # Restored as a snapshot dict (this is the existing pickle
    # contract — see _node_view_reduce docstring).
    assert isinstance(r, dict)
    assert dict(r) == {0: {}, 1: {}, 2: {}}


def test_degree_and_in_out_edge_view_copy_preserves_view_type():
    """br-r37-c1-vcopy: extends cycle 198's NodeView/EdgeView copy
    fix to the remaining view types whose ``__reduce__`` snapshotted
    to ``list``:

      view                                   nx                  fnx (pre-fix)
      ----                                   ---                 -------------
      copy.copy(G.degree)                    DegreeView          list
      copy.deepcopy(G.degree)                DegreeView          list
      copy.copy(DG.degree)                   DiDegreeView        list
      copy.deepcopy(DG.degree)               DiDegreeView        list
      copy.copy(DG.in_edges)                 InEdgeView          list
      copy.deepcopy(DG.in_edges)             InEdgeView          list
      copy.copy(DG.out_edges)                OutEdgeView         list
      copy.copy(MDG.in_edges)                InMultiEdgeView     list
      copy.copy(MDG.out_edges)               OutMultiEdgeView    list

    Drop-in code that does ``isinstance(c, DegreeView)`` after a
    copy round-trip silently misbehaved.

    Fix: define ``__copy__`` / ``__deepcopy__`` returning self on
    the two relevant base classes (``_WeightAwareDegreeView`` for
    Graph/DiGraph degree views, ``_DiEdgeMethodView`` for in_edges/
    out_edges across DiGraph/MultiDiGraph). ``__reduce__`` keeps
    the snapshot for pickle as before.
    """
    import copy

    # Graph and DiGraph: degree views
    cases_degree = [
        (fnx.Graph,        nx.Graph,        "DegreeView"),
        (fnx.DiGraph,      nx.DiGraph,      "DiDegreeView"),
    ]
    for f_cls, n_cls, expected in cases_degree:
        Gf = f_cls([(1, 2), (2, 3)])
        Gn = n_cls([(1, 2), (2, 3)])
        for op in (copy.copy, copy.deepcopy):
            cf = op(Gf.degree)
            cn = op(Gn.degree)
            assert type(cf).__name__ == expected, (
                f"{f_cls.__name__}.degree {op.__name__}: "
                f"fnx={type(cf).__name__} expected={expected}"
            )
            # Behavior preserved
            assert dict(cf) == dict(cn) == dict(Gn.degree)

    # DiGraph and MultiDiGraph: in_edges / out_edges
    cases_edges = [
        (fnx.DiGraph,      nx.DiGraph,      "in_edges",  "InEdgeView"),
        (fnx.DiGraph,      nx.DiGraph,      "out_edges", "OutEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "in_edges",  "InMultiEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "out_edges", "OutMultiEdgeView"),
    ]
    for f_cls, n_cls, attr, expected in cases_edges:
        Gf = f_cls([(1, 2), (2, 3)])
        Gn = n_cls([(1, 2), (2, 3)])
        for op in (copy.copy, copy.deepcopy):
            cf = op(getattr(Gf, attr))
            cn = op(getattr(Gn, attr))
            assert type(cf).__name__ == expected, (
                f"{f_cls.__name__}.{attr} {op.__name__}: "
                f"fnx={type(cf).__name__} expected={expected}"
            )
            assert list(cf) == list(cn) == list(getattr(Gn, attr))


def test_reverse_view_views_copy_and_deepcopy_preserve_type():
    """br-r37-c1-revvcopy: extends the view-copy fix to all reverse-
    view sub-views.  Pre-fix ``copy.deepcopy(R.degree)`` (and
    .edges, .adj, .succ, .pred, .in_edges, .out_edges) raised
    TypeError because deepcopy recursed into the parent reverse-
    view graph and tripped ``_graph_deepcopy``'s no-arg
    ``cls()`` constructor (reverse-view bases require a graph
    argument).

    nx parity: each reverse sub-view preserves its canonical type
    through both copy.copy and copy.deepcopy.

    Fix: define ``__copy__`` / ``__deepcopy__`` returning self on
    the four reverse-view base classes:
      - _RevDegreeViewBase (R.degree)
      - _RevEdgeMethodViewBase (R.in_edges, R.out_edges)
      - _ReverseAdjacencyView (R.adj, R.succ, R.pred)
      - _ReverseEdgeView (R.edges)
    """
    import copy

    for cls_name in ("DiGraph", "MultiDiGraph"):
        DGf = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        DGn = getattr(nx, cls_name)([(1, 2), (2, 3)])
        Rf = DGf.reverse(copy=False)
        Rn = DGn.reverse(copy=False)
        for view_attr in (
            "nodes", "edges", "adj", "degree",
            "in_edges", "out_edges", "succ", "pred",
        ):
            vf = getattr(Rf, view_attr)
            vn = getattr(Rn, view_attr)
            for op in (copy.copy, copy.deepcopy):
                cf = op(vf)
                cn = op(vn)
                assert type(cf).__name__ == type(cn).__name__, (
                    f"{cls_name}.reverse().{view_attr} {op.__name__}: "
                    f"fnx={type(cf).__name__} nx={type(cn).__name__}"
                )

    # Functional smoke
    DG = fnx.DiGraph([(1, 2), (2, 3)])
    R = DG.reverse(copy=False)
    cd = copy.copy(R.degree)
    assert type(cd).__name__ == "DiDegreeView"
    assert dict(cd) == {1: 1, 2: 2, 3: 1}
    cd2 = copy.deepcopy(R.degree)
    assert type(cd2).__name__ == "DiDegreeView"


def test_subgraph_view_and_reverse_view_top_level_copy_match_nx():
    """br-r37-c1-fgvcopy / br-r37-c1-revvcopy-outer:
    ``copy.copy(G.subgraph(...))`` and ``copy.copy(DG.reverse(copy=
    False))`` must return a frozen canonical-class graph with the
    same content — matching nx's documented behaviour for copying a
    view.

    Pre-fix fnx inherited Graph's ``__copy__`` (= ``_graph_shallowcopy``)
    which does ``type(self)()``.  This fails for ``_FilteredGraphView``
    and ``_ReverseDirectedViewBase`` subclasses because their
    ``__init__`` requires a ``graph`` argument:

      copy.copy(G.subgraph(...))
        → TypeError: _FilteredGraphView.__init__() missing 1 required
          positional argument: 'graph'

      copy.copy(DG.reverse(copy=False))
        → TypeError: _ReverseDirectedViewBase.__init__() missing 1
          required positional argument: 'graph'

    nx returns a frozen Graph/DiGraph/MultiGraph/MultiDiGraph with
    the same content (subgraph: filtered nodes/edges; reverse: edges
    flipped).

    Fix: define ``__copy__`` / ``__deepcopy__`` on both base classes
    that materialise via the existing ``copy()`` method (canonical
    class with same content) and freeze for nx parity.
    """
    import copy

    # Subgraph copy/deepcopy
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        Gf = getattr(fnx, cls_name)([(1, 2), (2, 3), (3, 4)])
        Gn = getattr(nx, cls_name)([(1, 2), (2, 3), (3, 4)])
        Sf = Gf.subgraph([1, 2, 3])
        Sn = Gn.subgraph([1, 2, 3])

        for op in (copy.copy, copy.deepcopy):
            cf = op(Sf)
            cn = op(Sn)
            assert type(cf).__name__ == type(cn).__name__ == cls_name, (
                f"{cls_name}.subgraph() {op.__name__}: "
                f"fnx={type(cf).__name__} nx={type(cn).__name__}"
            )
            assert fnx.is_frozen(cf) == nx.is_frozen(cn) == True, (
                f"{cls_name}.subgraph() {op.__name__}: "
                f"frozen mismatch fnx={fnx.is_frozen(cf)} nx={nx.is_frozen(cn)}"
            )
            # Content matches (filtered to [1, 2, 3])
            assert sorted(cf.nodes()) == sorted(cn.nodes()) == [1, 2, 3]

    # Reverse view copy/deepcopy
    for cls_name in ("DiGraph", "MultiDiGraph"):
        DGf = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        DGn = getattr(nx, cls_name)([(1, 2), (2, 3)])
        Rf = DGf.reverse(copy=False)
        Rn = DGn.reverse(copy=False)
        for op in (copy.copy, copy.deepcopy):
            cf = op(Rf)
            cn = op(Rn)
            assert type(cf).__name__ == type(cn).__name__ == cls_name
            assert fnx.is_frozen(cf) == nx.is_frozen(cn) == True
            # Content has reversed edges
            assert sorted(cf.edges()) == sorted(cn.edges())


def test_adjacency_generator_yields_dict_inner():
    """br-r37-c1-adjdict: ``G.adjacency()`` yields ``(node,
    inner_dict)`` tuples where ``inner_dict`` is a real ``dict`` in
    nx.  Pre-fix fnx yielded ``(node, AtlasView)`` (or
    ``AdjacencyView`` for Multi*Graph), so
    ``isinstance(adj, dict)`` returned False and drop-in code that
    type-dispatches on the inner adjacency map silently misbehaved.

    Affects all 4 graph classes (Graph, DiGraph, MultiGraph,
    MultiDiGraph).

    Fix: materialise the inner mapping as a ``dict`` at yield time
    in ``_simple_graph_adjacency`` (Graph/DiGraph) and
    ``_multigraph_adjacency`` (Multi*Graph, with recursive unwrap of
    the per-key attrs sub-dict).  Drop-in callers expecting LIVE
    mutation (uncommon — typically use ``G.adj[node]`` directly)
    keep that path unchanged.
    """
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        Gf = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        Gn = getattr(nx, cls_name)([(1, 2), (2, 3)])

        f_adj = list(Gf.adjacency())
        n_adj = list(Gn.adjacency())

        # Inner type matches nx
        assert type(f_adj[0][1]) is dict, (
            f"{cls_name}.adjacency() inner type: "
            f"fnx={type(f_adj[0][1]).__name__} expected=dict"
        )
        assert type(n_adj[0][1]) is dict, (
            f"sanity: {cls_name}.adjacency() inner type in nx: "
            f"{type(n_adj[0][1]).__name__}"
        )

        # Content matches
        f_dict = {k: v for k, v in f_adj}
        n_dict = {k: v for k, v in n_adj}
        assert f_dict == n_dict, (
            f"{cls_name}.adjacency() content: fnx={f_dict} nx={n_dict}"
        )

        # isinstance check works
        for node, adj in Gf.adjacency():
            assert isinstance(adj, dict)

    # MultiGraph deeper structure: inner dict nests the per-key
    # attrs as plain dicts too (recursive unwrap).
    MG = fnx.MultiGraph()
    MG.add_edge(1, 2, key="a", weight=10)
    MG.add_edge(1, 2, key="b", weight=20)
    for node, adj in MG.adjacency():
        assert isinstance(adj, dict)
        for nbr, keyed_attrs in adj.items():
            assert isinstance(keyed_attrs, dict)
            for key, attrs in keyed_attrs.items():
                assert isinstance(attrs, dict)


def test_nodes_call_unexpected_kwarg_error_qualifies_class_name():
    """br-r37-c1-callerrqual: nx qualifies the
    ``__call__() got an unexpected keyword argument`` TypeError
    with the view class name (e.g. ``NodeView.__call__() got an
    unexpected keyword argument 'badarg'``).  fnx's two view-call
    wrappers (``_node_view_call_with_attr_support`` and
    ``_edge_view_call_with_nbunch_first``) raised the bare
    ``__call__()`` error without class qualification — drop-in code
    parsing the error message for class hints silently misbehaved.

    Fix: prepend ``f"{type(self).__name__}.__call__()"`` to both
    error formats.

    Affects:
      G.nodes(badarg=1)         (all 4 graph classes)

    Note: the ``EdgeView`` family on DiGraph/MultiGraph/MultiDiGraph
    raises a similar error from Python's default mechanism (uses
    ``tp_name`` rather than the wrapper) — that's a separate
    architectural fix and remains out of scope for this cycle.
    Graph.edges and the NodeView family go through the wrapped
    path and DO benefit from the qualification.
    """
    import networkx as nx

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        Gf = getattr(fnx, cls_name)()
        Gn = getattr(nx, cls_name)()
        # nodes(badarg=1)
        try:
            Gf.nodes(badarg=1)
        except TypeError as e:
            f_msg = str(e)
        else:
            raise AssertionError(f"{cls_name}.nodes(badarg=1) did not raise")
        try:
            Gn.nodes(badarg=1)
        except TypeError as e:
            n_msg = str(e)
        assert f_msg == n_msg, (
            f"{cls_name}.nodes(badarg=1): fnx={f_msg!r} nx={n_msg!r}"
        )
        # Both should start with "NodeView." (the canonical class name).
        assert f_msg.startswith("NodeView."), (
            f"{cls_name}.nodes(badarg=1) error message should start with "
            f"'NodeView.', got {f_msg!r}"
        )


def test_random_regular_graph_seeded_output_matches_nx():
    """br-r37-c1-rrgseed: ``random_regular_graph(d, n, seed=N)`` must
    produce the exact same graph as ``nx.random_regular_graph(d, n,
    seed=N)`` for drop-in seeded reproducibility.

    Pre-fix fnx's no-``create_using`` fast path used the Rust
    ``_rust_random_regular_graph`` which has its own MT19937 with
    different state evolution from Python's ``random.Random``.
    Same seed produced different graphs:

      d=3, n=6, seed=42:
        nx:  [(0,1), (0,3), (0,4), (1,2), (1,5), (2,4), (2,5), (3,4), (3,5)]
        fnx: [(0,1), (0,3), (0,4), (1,2), (1,3), (2,4), (2,5), (3,5), (4,5)]

    Drop-in callers using ``seed=N`` for reproducibility silently
    got different graphs.

    Fix: route the no-``create_using`` path through the existing
    Python implementation below (which uses
    ``_generator_random_state`` = ``random.Random``) instead of the
    Rust fast path.  The lock-test
    ``test_native_random_generators_do_not_fallback_to_networkx``
    still passes because the algorithm runs in fnx's own Python
    code (no nx-fallback).
    """
    import networkx as nx

    for seed in (42, 0, 99, 7, 123):
        for d, n in ((3, 6), (4, 8), (3, 10), (2, 6)):
            f_edges = sorted(fnx.random_regular_graph(d, n, seed=seed).edges())
            n_edges = sorted(nx.random_regular_graph(d, n, seed=seed).edges())
            assert f_edges == n_edges, (
                f"random_regular_graph(d={d}, n={n}, seed={seed}):\n"
                f"  fnx={f_edges}\n  nx ={n_edges}"
            )

    # The create_using path was already correct — verify it still
    # produces the same graph as the no-create_using path (uses
    # the same Python implementation now).
    G_explicit = fnx.random_regular_graph(3, 6, seed=42, create_using=fnx.Graph())
    G_implicit = fnx.random_regular_graph(3, 6, seed=42)
    assert sorted(G_explicit.edges()) == sorted(G_implicit.edges())


def test_relaxed_caveman_graph_seeded_output_matches_nx():
    """br-r37-c1-rcgseed: ``relaxed_caveman_graph(l, k, p, seed=N)``
    must produce the exact same graph as nx for drop-in seeded
    reproducibility.

    Pre-fix fnx used a different rewiring algorithm:
      - removed the edge first, then LOOPED ``rng.randint`` until
        finding a non-conflicting target
      - different RNG state progression AND different edge-set
        outcome from nx

    nx's algorithm:
      - one ``seed.choice(nodes)`` to pick a target
      - skip the rewire if target already shares an edge with u
        (no looping retries)
      - remove the original edge only if rewire goes through

    Drop-in callers using ``seed=N`` for reproducibility silently
    got different graphs.

    Fix: match nx's algorithm exactly (single ``rng.choice`` +
    skip-on-conflict).
    """
    import networkx as nx

    for seed in (42, 0, 99, 7, 123):
        for l, k, p in ((3, 4, 0.3), (2, 5, 0.5), (4, 3, 0.1), (5, 2, 0.7)):
            f_edges = sorted(fnx.relaxed_caveman_graph(l, k, p, seed=seed).edges())
            n_edges = sorted(nx.relaxed_caveman_graph(l, k, p, seed=seed).edges())
            assert f_edges == n_edges, (
                f"relaxed_caveman_graph(l={l}, k={k}, p={p}, seed={seed}):\n"
                f"  fnx={f_edges}\n  nx ={n_edges}"
            )

    # NaN seed surfaces nx-shape ValueError
    import math
    try:
        fnx.relaxed_caveman_graph(3, 4, 0.3, seed=float("nan"))
    except ValueError as e:
        assert "nan cannot be used" in str(e)
    else:
        raise AssertionError("NaN seed should raise ValueError")


def test_fnx_community_louvain_communities_uses_fnx_wrapper():
    """br-r37-c1-louvainsubmod: ``fnx.community.louvain_communities``
    previously re-exported nx's function directly via the
    ``from networkx.algorithms.community import *`` line in the
    submodule.  Calling ``nx.community.louvain_communities`` on an
    fnx Graph (no conversion to a real nx Graph) produced WRONG
    partitions — nx's multi-level Louvain returned a trivial
    2-cluster partition on Karate (modularity ~0.40) instead of the
    canonical 4-cluster answer (modularity ~0.44).

    The top-level ``fnx.community.louvain_communities`` correctly converted
    via ``_louvain_impl`` → ``_call_networkx_submodule_for_parity``
    → ``_fnx_to_nx`` and returned 4 communities.  But drop-in code
    using the canonical submodule path
    (``fnx.community.louvain_communities``) silently got the wrong
    answer.

    Fix: route ``fnx.community.louvain_communities`` through the
    top-level ``fnx.community.louvain_communities`` wrapper.
    """
    import networkx as nx

    G_f = fnx.karate_club_graph()
    G_n = nx.karate_club_graph()

    for seed in (0, 7, 42, 99):
        f_communities = sorted(
            sorted(c) for c in fnx.community.louvain_communities(G_f, seed=seed)
        )
        n_communities = sorted(
            sorted(c) for c in nx.community.louvain_communities(G_n, seed=seed)
        )
        assert f_communities == n_communities, (
            f"louvain_communities seed={seed}:\n"
            f"  fnx={f_communities}\n  nx ={n_communities}"
        )

    # The top-level fnx.community.louvain_communities also yields 4 communities
    # (sanity check the submodule routes through it).
    top = fnx.community.louvain_communities(G_f, seed=42)
    sub = fnx.community.louvain_communities(G_f, seed=42)
    assert sorted(sorted(c) for c in top) == sorted(sorted(c) for c in sub)
    assert len(sub) == 4  # Canonical Karate 4-community answer


def test_view_deepcopy_is_snapshot_independent_of_subsequent_mutations():
    """br-r37-c1-vcopydc: cycle 198 fixed ``copy.copy(G.nodes)``
    type preservation, but the ``__deepcopy__`` override returned
    self too — making ``copy.deepcopy(G.nodes)`` a LIVE wrapper
    that saw subsequent G mutations.  nx's deepcopy contract is
    SNAPSHOT semantics: deep-copy the underlying graph, return a
    NodeView pointing to that snapshot — independent of any later
    mutation to the original G.

      Pre-fix divergence:
        nv_dc = copy.deepcopy(G.nodes); G.add_node(99)
        nx:  99 in nv_dc → False  (snapshot — nx is correct)
        fnx: 99 in nv_dc → True   (live wrapper — fnx is wrong)

    Drop-in code that uses deepcopy to FREEZE a view's state for
    later comparison silently saw G's mutations leak into the
    "snapshot".

    Fix: ``__deepcopy__`` materialises the current view content
    into a NEW fnx Graph (of the matching type) and returns its
    .nodes/.edges view.  Type preservation (NodeView/EdgeView) is
    maintained AND subsequent G mutations don't bleed in.
    """
    import copy

    # NodeView deepcopy is independent across all 4 graph classes
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        nv_dc = copy.deepcopy(G.nodes)
        # Snapshot taken — mutations to G must NOT show up in nv_dc.
        G.add_node(999)
        assert 999 not in nv_dc, (
            f"{cls_name}.nodes deepcopy should be snapshot — but 999 "
            f"leaked in after G.add_node(999): list(nv_dc)={list(nv_dc)}"
        )
        # Type preservation
        assert type(nv_dc).__name__ == "NodeView"
        # isinstance Mapping (cycle 185 ABC parity)
        from collections.abc import Mapping
        assert isinstance(nv_dc, Mapping)

    # EdgeView deepcopy is independent (Graph only — _EDGE_VIEW_TYPE
    # is shared with cycle-188 OutEdgeView et al., but those go
    # through _DiEdgeMethodView which is fixed elsewhere).
    G = fnx.Graph([(1, 2), (2, 3)])
    ev_dc = copy.deepcopy(G.edges)
    G.add_edge(99, 100)
    assert (99, 100) not in ev_dc, (
        f"Graph.edges deepcopy should be snapshot — but (99, 100) "
        f"leaked in after G.add_edge: list(ev_dc)={list(ev_dc)}"
    )
    assert type(ev_dc).__name__ == "EdgeView"

    # Behavior preservation: copy.copy is still LIVE (matches nx).
    G2 = fnx.path_graph(3)
    nv_c = copy.copy(G2.nodes)
    G2.add_node(99)
    assert 99 in nv_c  # live wrapper sees mutation

    # Pickle round-trip behaviour unchanged (still snapshot dict
    # because Rust graphs can't pickle by reference).
    import pickle
    G3 = fnx.path_graph(3)
    r = pickle.loads(pickle.dumps(G3.nodes))
    assert isinstance(r, dict)


def test_degree_and_in_out_edge_view_deepcopy_is_snapshot():
    """br-r37-c1-vcopydc (cycle 199 dual): same ``__deepcopy__ =
    self`` defect cycle 208 fixed for NodeView/EdgeView also
    affected ``_WeightAwareDegreeView`` (Graph.degree, DiGraph.degree)
    and ``_DiEdgeMethodView`` (DiGraph/MultiDiGraph in_edges,
    out_edges).  All returned self → live wrappers seeing
    subsequent G mutations.

      Pre-fix divergence:
        deg_dc = copy.deepcopy(G.degree); G.add_edge(99, 100)
        nx:  99 not in dict(deg_dc)  (snapshot)
        fnx: 99 in dict(deg_dc)      (live wrapper — wrong)

    Fix: ``__deepcopy__`` deep-copies the underlying graph
    (``self._graph``) and returns the matching view from the
    deep-copied graph (``new_graph.degree`` / ``new_graph.in_edges``
    / ``new_graph.out_edges``).  Type preservation maintained via
    the cycle-188/190 subclass __name__ dispatch.
    """
    import copy

    # Graph and DiGraph degree
    for cls_name, expected_type in (
        ("Graph", "DegreeView"),
        ("DiGraph", "DiDegreeView"),
    ):
        G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        dc = copy.deepcopy(G.degree)
        G.add_edge(99, 100)
        assert 99 not in dict(dc), (
            f"{cls_name}.degree deepcopy should be snapshot; "
            f"99 leaked: {dict(dc)}"
        )
        assert type(dc).__name__ == expected_type

    # DiGraph and MultiDiGraph in/out_edges
    for cls_name, expected_in, expected_out in (
        ("DiGraph", "InEdgeView", "OutEdgeView"),
        ("MultiDiGraph", "InMultiEdgeView", "OutMultiEdgeView"),
    ):
        DG = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        ie_dc = copy.deepcopy(DG.in_edges)
        oe_dc = copy.deepcopy(DG.out_edges)
        DG.add_edge(99, 100)
        assert not any(99 in t for t in list(ie_dc)), (
            f"{cls_name}.in_edges deepcopy should be snapshot; "
            f"99 leaked: {list(ie_dc)}"
        )
        assert not any(99 in t for t in list(oe_dc)), (
            f"{cls_name}.out_edges deepcopy should be snapshot; "
            f"99 leaked: {list(oe_dc)}"
        )
        assert type(ie_dc).__name__ == expected_in
        assert type(oe_dc).__name__ == expected_out

    # copy.copy still LIVE (matches nx — only deepcopy is snapshot)
    G = fnx.Graph([(1, 2)])
    deg_c = copy.copy(G.degree)
    G.add_edge(99, 100)
    # copy.copy returned self; mutation visible via the live wrapper
    assert 99 in dict(deg_c)


def test_reverse_view_subview_deepcopy_is_snapshot():
    """br-r37-c1-vcopydc (cycle 200 dual): closes the deepcopy-
    snapshot family on reverse-view sub-views.  Cycles 198-200
    introduced ``__deepcopy__ = self`` on multiple view classes;
    cycles 208 and 209 fixed the non-reverse paths.  This cycle
    closes the reverse-view sub-view paths (cycle 200's classes).

    Pre-fix divergence (DiGraph + MultiDiGraph reverse views):

      R = DG.reverse(copy=False)
      e_dc = copy.deepcopy(R.edges); DG.add_edge(99, 100)
      nx:  no (99,100) in e_dc  (snapshot)
      fnx: (99,100) in e_dc     (live wrapper — wrong)

    Same defect on R.adj/succ/pred, R.degree, R.in_edges,
    R.out_edges.

    Fix: ``__deepcopy__`` deep-copies the underlying directed
    graph (via the ``self._owner._graph`` or ``self._view._graph``
    attribute), builds a new reverse view from it, and returns the
    matching sub-view.  Type preservation maintained AND snapshot
    semantics restored.
    """
    import copy

    for cls_name in ("DiGraph", "MultiDiGraph"):
        DG = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        R = DG.reverse(copy=False)

        for attr in ("edges", "adj", "degree", "in_edges",
                     "out_edges", "succ", "pred"):
            v = getattr(R, attr)
            dc = copy.deepcopy(v)
            DG.add_edge(99, 100)

            if attr == "degree":
                sees_mutation = 99 in dict(dc)
            elif attr in ("edges", "in_edges", "out_edges"):
                sees_mutation = any(99 in t for t in list(dc))
            else:  # adj, succ, pred
                sees_mutation = 99 in dict(dc)

            assert not sees_mutation, (
                f"{cls_name}.reverse().{attr} deepcopy should be "
                f"snapshot — but mutation leaked: dc has node 99"
            )

            # Cleanup for next iteration
            DG.remove_edge(99, 100)
            DG.remove_node(99)
            DG.remove_node(100)

    # Type preservation through deepcopy on each sub-view
    DG = fnx.DiGraph([(1, 2), (2, 3)])
    R = DG.reverse(copy=False)
    expected_types = {
        "edges": "OutEdgeView",
        "adj": "AdjacencyView",
        "degree": "DiDegreeView",
        "in_edges": "InEdgeView",
        "out_edges": "OutEdgeView",
        "succ": "AdjacencyView",
        "pred": "AdjacencyView",
    }
    for attr, expected in expected_types.items():
        dc = copy.deepcopy(getattr(R, attr))
        assert type(dc).__name__ == expected, (
            f"reverse().{attr} deepcopy type: got "
            f"{type(dc).__name__}, expected {expected}"
        )


def test_subgraph_view_subview_deepcopy_is_snapshot_and_no_attribute_error():
    """br-r37-c1-vcopydc (cycle 211): default deepcopy of a
    subgraph view's NodeView / EdgeView recursively copied
    ``self._view`` (the subgraph view), which materialises to a
    plain frozen Graph via ``_FilteredGraphView.__deepcopy__`` —
    that Graph lacks the filter machinery (``_node_visible``,
    ``_edges``), so subsequent attribute access through the
    deep-copied NodeView/EdgeView raised AttributeError:

      G = fnx.path_graph(5); S = G.subgraph([1,2,3])
      copy.deepcopy(S.nodes)
      → AttributeError: 'franken_networkx.Graph' object has no
        attribute '_node_visible'

      copy.deepcopy(S.edges)
      → AttributeError: 'franken_networkx.Graph' object has no
        attribute '_edges'

    Drop-in code that snapshots a subgraph's view via deepcopy
    silently CRASHED.

    Fix: add ``__deepcopy__`` to the subgraph NodeView and
    _FilteredEdgeView base classes that materialises via
    ``deepcopy(self._view)`` (which yields a frozen Graph with
    the snapshot content) and returns its ``.nodes`` / ``.edges``
    (Rust-bound view, ``__name__`` matches nx).
    """
    import copy

    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        G = getattr(fnx, cls_name)([(1, 2), (2, 3), (3, 4)])
        S = G.subgraph([1, 2, 3])

        # All four sub-views must deepcopy without crashing.
        nv_dc = copy.deepcopy(S.nodes)
        ev_dc = copy.deepcopy(S.edges)
        adj_dc = copy.deepcopy(S.adj)
        deg_dc = copy.deepcopy(S.degree)

        # Snapshot independence: subsequent G mutation doesn't leak.
        G.add_node(99)
        G.add_edge(99, 100)
        assert 99 not in nv_dc
        assert 99 not in adj_dc
        assert 99 not in dict(deg_dc)
        assert (99, 100) not in list(ev_dc)
        assert (100, 99) not in list(ev_dc)

        # Type names match nx (cycle 188/190+ canonical forms).
        assert type(nv_dc).__name__ == "NodeView"

    # Functional smoke
    G = fnx.path_graph(5)
    S = G.subgraph([1, 2, 3])
    nv = copy.deepcopy(S.nodes)
    assert list(nv) == [1, 2, 3]
    assert 2 in nv
    assert len(nv) == 3


def test_node_data_view_and_edge_data_view_deepcopy_preserves_type():
    """br-r37-c1-vcopy (cycle 212): ``copy.deepcopy(G.nodes.data())``
    and ``copy.deepcopy(G.edges.data())`` previously returned a
    plain ``list`` (via the ``__reduce__`` snapshot path).  nx
    returns a ``NodeDataView`` / ``EdgeDataView`` — preserving
    type while staying snapshot-independent of subsequent G
    mutations.

    Affects all 4 graph classes for NodeDataView, plus Graph for
    EdgeDataView (Multi*Graph EdgeDataView already matched).

    Fix: define ``__copy__`` (returns self — live wrapper, matches
    nx) and ``__deepcopy__`` (materialises into a new fnx Graph and
    returns its ``.nodes.data()`` / ``.edges.data()``) on
    ``NodeDataView`` and ``EdgeDataView``.  Type preservation +
    snapshot semantics — matches nx exactly.
    """
    import copy

    # NodeDataView across all 4 graph classes
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        G = getattr(fnx, cls_name)([(1, 2), (2, 3)])
        G.add_node(1, color="red")
        ndv = G.nodes.data()
        dc = copy.deepcopy(ndv)
        assert type(dc).__name__ == "NodeDataView", (
            f"{cls_name}.nodes.data() deepcopy: "
            f"got {type(dc).__name__}, expected NodeDataView"
        )
        # Snapshot — independent of subsequent G mutation
        G.add_node(99)
        assert (99, {}) not in list(dc), (
            f"{cls_name}.nodes.data() deepcopy should be snapshot"
        )

    # EdgeDataView on Graph
    G = fnx.Graph([(1, 2, {"w": 3.0})])
    edv = G.edges.data()
    dc = copy.deepcopy(edv)
    assert type(dc).__name__ == "EdgeDataView"
    G.add_edge(99, 100)
    assert not any(99 in t[:2] for t in list(dc))

    # data='attr' projection variant works too
    G = fnx.Graph([(1, 2, {"w": 5.0})])
    edv_attr = G.edges.data("w")
    dc_attr = copy.deepcopy(edv_attr)
    assert type(dc_attr).__name__ == "EdgeDataView"
    assert list(dc_attr) == [(1, 2, 5.0)]


def test_multigraph_edges_call_with_data_returns_canonical_data_view():
    """br-r37-c1-mgcall (cycle 213): nx's MultiGraph.edges(...) /
    MultiDiGraph.edges(...) returns ``MultiEdgeDataView`` /
    ``OutMultiEdgeDataView`` whenever ``data`` is anything other
    than False.  fnx's ``__call__`` previously returned the
    private ``_EdgeListWithSetAlgebra`` regardless of args:

      Operation                                  nx                   fnx (pre-fix)
      ---------                                  ---                  -------------
      MG.edges(data=True)                        MultiEdgeDataView    _EdgeListWithSetAlgebra
      MG.edges(keys=True, data=True)             MultiEdgeDataView    _EdgeListWithSetAlgebra
      MG.edges(data="weight", default=99)        MultiEdgeDataView    _EdgeListWithSetAlgebra
      MDG.edges(data=True)                       OutMultiEdgeDataView _EdgeListWithSetAlgebra

    Drop-in code that does ``isinstance(MG.edges(data=True), MultiEdgeDataView)``
    silently misbehaved on fnx.

    Fix: in both ``_MultiGraphEdgeView.__call__`` and
    ``_MultiDiGraphEdgeView.__call__``, when ``data is not False``,
    wrap the result list in the canonical view class
    (``_MultiEdgeDataView`` / ``_OutMultiEdgeDataView`` from cycle
    192's subclass split) via ``_wrap_edge_data_view``.

    Note: the bare ``MG.edges()`` (no args) and ``MG.edges(keys=True)``
    (no data) cases use different result types (``_LiveMultiEdgeCallView``
    and ``_EdgeListWithSetAlgebra`` respectively); those remain
    out of scope for this fix.
    """
    import networkx as nx

    cases = [
        (fnx.MultiGraph,   nx.MultiGraph,   "MultiEdgeDataView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "OutMultiEdgeDataView"),
    ]
    for f_cls, n_cls, expected in cases:
        Gf = f_cls([(1, 2), (2, 3)])
        Gn = n_cls([(1, 2), (2, 3)])

        # data=True
        assert type(Gf.edges(data=True)).__name__ == expected
        assert type(Gn.edges(data=True)).__name__ == expected

        # data=True, keys=True
        assert type(Gf.edges(keys=True, data=True)).__name__ == expected
        assert type(Gn.edges(keys=True, data=True)).__name__ == expected

        # data='attr' projection
        assert type(Gf.edges(data="w", default=99)).__name__ == expected
        assert type(Gn.edges(data="w", default=99)).__name__ == expected

        # Functional smoke: contents match
        assert list(Gf.edges(data=True)) == list(Gn.edges(data=True))


def test_multigraph_edges_keys_view_supports_2tuple_contains():
    """br-r37-c1-mekvc (cycle 214): nx's ``MG.edges(keys=True)``
    returns a ``MultiEdgeView`` whose ``__contains__`` matches both
    3-tuple ``(u, v, k)`` AND 2-tuple ``(u, v)`` (any-key) queries.

    Pre-fix fnx returned a generic ``_EdgeListWithSetAlgebra`` (a
    plain ``list`` subclass), and ``list.__contains__`` rejected
    ``(u, v) in MG.edges(keys=True)`` because the items are
    3-tuples ``(u, v, k)``:

      Query                              nx     fnx (pre-fix)
      -----                              ---    -------------
      (1, 2)    in MG.edges(keys=True)   True   False  *** DIFF
      (1, 2, 0) in MG.edges(keys=True)   True   True   OK
      (3, 4)    in MG.edges(keys=True)   False  False  OK

    Drop-in code that asks ``if (u, v) in MG.edges(keys=True): ...``
    silently misbehaved, treating present edges as absent.

    Same defect on MultiDiGraph: ``MDG.edges(keys=True)`` exposed
    the same ``_EdgeListWithSetAlgebra`` and the same broken
    2-tuple containment.

    Fix: define ``_MultiEdgeView`` (an ``_EdgeListWithSetAlgebra``
    subclass) overriding ``__contains__`` to accept both 2- and
    3-element queries, and ``_OutMultiEdgesKeysView`` for the
    directed case.  In each ``__call__``, when ``data is False``
    and ``keys`` is truthy, wrap the result list in the canonical
    class via ``_wrap_edge_data_view``.

    Type parity also locked: ``type(MG.edges(keys=True)).__name__``
    is ``"MultiEdgeView"`` (was ``"_EdgeListWithSetAlgebra"``);
    ``type(MDG.edges(keys=True)).__name__`` is ``"OutMultiEdgeView"``.
    """
    import networkx as nx

    cases = [
        (fnx.MultiGraph,   nx.MultiGraph,   "MultiEdgeView"),
        (fnx.MultiDiGraph, nx.MultiDiGraph, "OutMultiEdgeView"),
    ]
    for f_cls, n_cls, expected in cases:
        Gf = f_cls()
        Gf.add_edges_from([(1, 2), (1, 2), (2, 3)])
        Gn = n_cls()
        Gn.add_edges_from([(1, 2), (1, 2), (2, 3)])

        # type parity
        assert type(Gf.edges(keys=True)).__name__ == expected
        assert type(Gn.edges(keys=True)).__name__ == expected

        # 2-tuple any-key contains: present edges True, absent False
        for q, want in [((1, 2), True), ((2, 3), True),
                        ((3, 4), False), ((99, 100), False)]:
            assert (q in Gf.edges(keys=True)) == want, (q, "fnx")
            assert (q in Gn.edges(keys=True)) == want, (q, "nx")

        # 3-tuple exact-key contains
        for q, want in [((1, 2, 0), True), ((1, 2, 1), True),
                        ((1, 2, 99), False), ((3, 4, 0), False)]:
            assert (q in Gf.edges(keys=True)) == want, (q, "fnx")
            assert (q in Gn.edges(keys=True)) == want, (q, "nx")

        # Set-algebra still works (was the original reason for
        # _EdgeListWithSetAlgebra; subclass must preserve it).
        edges_set = set(Gf.edges(keys=True))
        assert (1, 2, 0) in edges_set
        assert sorted(Gf.edges(keys=True)) == sorted(Gn.edges(keys=True))


def test_di_in_out_edges_call_returns_canonical_view_classes():
    """br-r37-c1-iemvcw (cycle 215): nx's ``DG.in_edges(...)``,
    ``DG.out_edges(...)``, ``MDG.in_edges(...)``, ``MDG.out_edges(...)``
    each return one of the canonical view classes
    (InEdgeDataView / OutEdgeDataView / InMultiEdgeDataView /
    OutMultiEdgeDataView / InMultiEdgeView / OutMultiEdgeView).
    fnx returned a plain ``list`` for every args case:

      Call                                       nx                    fnx (pre)
      ----                                       ---                   ---------
      DG.in_edges(data=True)                     InEdgeDataView         list
      DG.out_edges(data='w')                     OutEdgeDataView        list
      MDG.in_edges()                             InMultiEdgeDataView    list
      MDG.in_edges(keys=True)                    InMultiEdgeView        list
      MDG.in_edges(data=True)                    InMultiEdgeDataView    list
      MDG.in_edges(data=True, keys=True)         InMultiEdgeDataView    list
      MDG.out_edges()                            OutMultiEdgeDataView   list
      MDG.out_edges(keys=True)                   OutMultiEdgeView       list
      ... (and equivalent rows for out_edges)

    Drop-in code that does
    ``isinstance(MDG.in_edges(keys=True), MultiEdgeView)`` silently
    misbehaved.  Worse, ``(u, v) in MDG.{in,out}_edges(keys=True)``
    returned False even when the edge existed (sister of cycle 214's
    ``MG.edges(keys=True)`` containment defect).

    Sister of cycle 213 (``MG.edges(data=...)``) and cycle 214
    (``MG.edges(keys=True)``) — same wrap pattern, different surface
    (``DG``/``MDG`` ``in_edges``/``out_edges`` instead of ``edges``).

    Fix: in ``_DiEdgeMethodView.__call__``, after delegating to the
    bound method, dispatch on (cls_name, is_multi, data, keys) and
    wrap the result in the canonical class via
    ``_wrap_edge_data_view``.  Defines ``_InMultiEdgesKeysView``
    (analog of cycle-214's ``_OutMultiEdgesKeysView``) so
    ``MDG.in_edges(keys=True)`` exposes ``__name__ ==
    'InMultiEdgeView'`` with multi-edge any-key ``__contains__``.
    """
    import networkx as nx

    # DiGraph: data=... cases (no keys for non-multi).
    fG = fnx.DiGraph([(1, 2, {"weight": 5}), (2, 3, {"weight": 6})])
    nG = nx.DiGraph([(1, 2, {"weight": 5}), (2, 3, {"weight": 6})])
    for attr, attr_data, attr_proj in [
        ("in_edges",  "InEdgeDataView",  "InEdgeDataView"),
        ("out_edges", "OutEdgeDataView", "OutEdgeDataView"),
    ]:
        # data=True
        assert type(getattr(fG, attr)(data=True)).__name__ == attr_data
        assert type(getattr(nG, attr)(data=True)).__name__ == attr_data
        # data='w' projection
        assert type(getattr(fG, attr)(data="weight")).__name__ == attr_proj
        assert type(getattr(nG, attr)(data="weight")).__name__ == attr_proj
        # Contents match
        assert sorted(getattr(fG, attr)(data=True)) == sorted(getattr(nG, attr)(data=True))

    # MultiDiGraph: full data/keys matrix.
    fM = fnx.MultiDiGraph([(1, 2), (1, 2), (2, 3), (3, 4)])
    nM = nx.MultiDiGraph([(1, 2), (1, 2), (2, 3), (3, 4)])
    matrix = [
        # (kwargs,                expected for in_edges,    expected for out_edges)
        ({},                       "InMultiEdgeDataView",   "OutMultiEdgeDataView"),
        ({"data": True},           "InMultiEdgeDataView",   "OutMultiEdgeDataView"),
        ({"keys": True},           "InMultiEdgeView",       "OutMultiEdgeView"),
        ({"data": True, "keys": True}, "InMultiEdgeDataView", "OutMultiEdgeDataView"),
        ({"data": "weight"},       "InMultiEdgeDataView",   "OutMultiEdgeDataView"),
    ]
    for kwargs, want_in, want_out in matrix:
        assert type(fM.in_edges(**kwargs)).__name__ == want_in, (kwargs, "fnx in")
        assert type(nM.in_edges(**kwargs)).__name__ == want_in, (kwargs, "nx in")
        assert type(fM.out_edges(**kwargs)).__name__ == want_out, (kwargs, "fnx out")
        assert type(nM.out_edges(**kwargs)).__name__ == want_out, (kwargs, "nx out")

    # 2-tuple any-key contains parity (sister to cycle 214 fix
    # — applies to MDG.{in,out}_edges(keys=True) just like to
    # MG.edges(keys=True)).
    for attr in ("in_edges", "out_edges"):
        for q, want in [
            ((1, 2),       True),   # 2-tuple any-key
            ((1, 2, 0),    True),   # exact-key 0
            ((1, 2, 1),    True),   # exact-key 1
            ((1, 2, 99),   False),  # nonexistent key
            ((3, 4),       True),
            ((99, 100),    False),
        ]:
            assert (q in getattr(fM, attr)(keys=True)) == want, (attr, q, "fnx")
            assert (q in getattr(nM, attr)(keys=True)) == want, (attr, q, "nx")


def test_add_edges_from_generator_partial_progress_persists():
    """br-r37-c1-aefitexc (cycle 216): nx's ``add_edges_from``
    iterates the ebunch and adds each edge inline.  When the
    iterable is a generator (or any iterator) that raises
    mid-stream, edges yielded BEFORE the exception are persisted
    on the graph.  fnx previously called ``list(ebunch_to_add)``
    atomically in ``_add_edges_from_materialized``, so any
    exception during iteration discarded ALL previously yielded
    edges.

      Pattern (nx-canonical):
        try:
            g.add_edges_from(my_generator())
        except SomeError:
            ...  # g now has edges yielded BEFORE the error

      nx (Graph): yielded edges are present.
      fnx (pre-fix): yielded edges are LOST.

    Drop-in code that catches generator exceptions and inspects
    the graph silently saw different state on fnx vs nx.

    Multi*Graph wasn't affected (its ``_multi_add_edges_from``
    already iterates and adds inline), but the regression check
    locks the behaviour for all four graph classes.

    Fix: in ``_add_edges_from_materialized``, when the input is
    NOT already a list/tuple, iterate manually inside a try/except,
    capture any exception, then add the (partial) edges before
    re-raising the captured exception.
    """
    def gen_two_then_raise():
        yield (10, 20)
        yield (20, 30)
        raise RuntimeError("kaboom")

    classes = [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph]
    for cls in classes:
        g = cls([(1, 2)])
        with pytest.raises(RuntimeError, match="kaboom"):
            g.add_edges_from(gen_two_then_raise())
        # The two edges yielded before the exception must be
        # present on the graph.
        edges = sorted(set((u, v) for u, v in (e[:2] for e in g.edges())))
        assert (1, 2) in edges, f"{cls.__name__}: original edge lost"
        assert (10, 20) in edges, f"{cls.__name__}: yielded edge missing"
        assert (20, 30) in edges, f"{cls.__name__}: yielded edge missing"

    # Custom iterator (not a generator function) raising
    # mid-iteration: same partial-progress contract.
    class RaisingIter:
        def __init__(self, items):
            self._items = list(items)
            self._i = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self._i >= len(self._items):
                raise StopIteration
            v = self._items[self._i]
            if v == "BAD":
                raise RuntimeError("iter boom")
            self._i += 1
            return v

    for cls in (fnx.Graph, fnx.DiGraph):
        g = cls()
        with pytest.raises(RuntimeError, match="iter boom"):
            g.add_edges_from(RaisingIter([(1, 2), (2, 3), "BAD", (3, 4)]))
        assert sorted(g.edges()) == [(1, 2), (2, 3)], f"{cls.__name__}"

    # Successful generator (no exception): unchanged behaviour.
    def good_gen():
        yield (5, 6)
        yield (6, 7)
    g = fnx.Graph()
    g.add_edges_from(good_gen())
    assert sorted(g.edges()) == [(5, 6), (6, 7)]

    # List/tuple input still works (the batch path).
    g = fnx.Graph()
    g.add_edges_from([(1, 2), (2, 3)])
    assert sorted(g.edges()) == [(1, 2), (2, 3)]


def test_remove_edges_nodes_from_generator_partial_progress_persists():
    """br-r37-c1-refitexc / br-r37-c1-rnfitexc (cycle 217): sister
    of cycle 216's ``add_edges_from`` partial-progress fix.  When
    ``remove_edges_from`` or ``remove_nodes_from`` receive a
    generator (or any iterator) that raises mid-stream, items
    yielded BEFORE the exception must already have been removed
    from the graph (matching nx's iterate-and-remove-inline
    semantics).

      Pattern (nx-canonical):
        g = Graph([(1,2),(2,3),(3,4)])
        def gen():
            yield (1, 2)
            yield (2, 3)
            raise RuntimeError('boom')
        try: g.remove_edges_from(gen())
        except RuntimeError: pass

      nx:  g.edges() == [(3, 4)]   (1,2) and (2,3) removed
      fnx (pre-fix): g.edges() == [(1,2),(2,3),(3,4)] *** DIFF
                                    nothing removed; yielded items lost

    Same defect applied to ``remove_nodes_from``.

    Fix: dispatch on input type in both materializer wrappers.
    Lists/tuples take the existing batch path; generators/iterators
    are iterated manually with try/except, capturing the iteration
    exception and re-raising AFTER the (partial) raw call.
    """
    def gen_rm_edges():
        yield (1, 2)
        yield (2, 3)
        raise RuntimeError("rm-edge-boom")

    def gen_rm_nodes():
        yield 1
        yield 2
        raise RuntimeError("rm-node-boom")

    classes = [fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph]

    # remove_edges_from: yielded edges are removed; later edges remain.
    for cls in classes:
        g = cls([(1, 2), (2, 3), (3, 4)])
        with pytest.raises(RuntimeError, match="rm-edge-boom"):
            g.remove_edges_from(gen_rm_edges())
        # (1,2) and (2,3) yielded before exception -> gone.
        # (3,4) never yielded -> still present.
        edges = sorted(set((u, v) for u, v in (e[:2] for e in g.edges())))
        assert (1, 2) not in edges, f"{cls.__name__}: (1,2) not removed"
        assert (2, 3) not in edges, f"{cls.__name__}: (2,3) not removed"
        assert (3, 4) in edges, f"{cls.__name__}: (3,4) lost"

    # remove_nodes_from: yielded nodes are removed; later nodes remain.
    for cls in classes:
        g = cls()
        for n in [1, 2, 3, 4]:
            g.add_node(n)
        with pytest.raises(RuntimeError, match="rm-node-boom"):
            g.remove_nodes_from(gen_rm_nodes())
        assert sorted(g.nodes()) == [3, 4], f"{cls.__name__}"

    # Successful generator (no exception): unchanged behaviour.
    def good_gen_edges():
        yield (1, 2)

    g = fnx.Graph([(1, 2), (2, 3)])
    g.remove_edges_from(good_gen_edges())
    assert sorted(g.edges()) == [(2, 3)]

    # List input still works (the batch path).
    g = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    g.remove_edges_from([(1, 2), (2, 3)])
    assert sorted(g.edges()) == [(3, 4)]

    g = fnx.Graph()
    for n in [1, 2, 3]:
        g.add_node(n)
    g.remove_nodes_from([1, 2])
    assert sorted(g.nodes()) == [3]


def test_neighbors_successors_predecessors_return_dict_keyiterator():
    """br-r37-c1-nbritype (cycle 218): nx's
    ``Graph.neighbors(u)`` / ``DiGraph.successors(u)`` /
    ``DiGraph.predecessors(u)`` (and Multi-graph equivalents)
    return ``iter(self._adj[n])`` whose runtime type is
    ``dict_keyiterator``.  fnx previously returned
    ``list_iterator`` (via ``iter(list)``), diverging on
    ``type(G.neighbors(u)).__name__``:

      Method                                nx                  fnx (pre-fix)
      ------                                ---                 -------------
      type(G.neighbors(u))                  dict_keyiterator    list_iterator
      type(DG.successors(u))                dict_keyiterator    list_iterator
      type(DG.predecessors(u))              dict_keyiterator    list_iterator
      type(MG.neighbors(u))                 dict_keyiterator    list_iterator

    Drop-in code that does
    ``isinstance(it, type({}.__iter__()))`` (the standard way
    to detect a ``dict_keyiterator`` since the type isn't in
    ``types``) silently saw the wrong runtime type.

    Fix: in ``_neighbors_with_networkx_missing_node_error``,
    when the Rust impl returned a list, route through
    ``iter(dict.fromkeys(result))`` so the runtime iterator
    type is ``dict_keyiterator``.  Content semantics are
    unchanged (the list already had unique entries since nx
    deduplicates by adjacency-dict keys).
    """
    dict_keyiterator = type({}.__iter__())

    fG = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    nG = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert isinstance(fG.neighbors(2), dict_keyiterator)
    assert isinstance(nG.neighbors(2), dict_keyiterator)
    assert sorted(fG.neighbors(2)) == sorted(nG.neighbors(2))

    fD = fnx.DiGraph([(1, 2), (2, 3), (3, 1)])
    nD = nx.DiGraph([(1, 2), (2, 3), (3, 1)])
    assert isinstance(fD.successors(1), dict_keyiterator)
    assert isinstance(nD.successors(1), dict_keyiterator)
    assert isinstance(fD.predecessors(1), dict_keyiterator)
    assert isinstance(nD.predecessors(1), dict_keyiterator)
    assert isinstance(fD.neighbors(1), dict_keyiterator)
    assert isinstance(nD.neighbors(1), dict_keyiterator)

    fM = fnx.MultiGraph([(1, 2), (1, 2), (2, 3)])
    nM = nx.MultiGraph([(1, 2), (1, 2), (2, 3)])
    assert isinstance(fM.neighbors(1), dict_keyiterator)
    assert isinstance(nM.neighbors(1), dict_keyiterator)
    assert sorted(fM.neighbors(1)) == sorted(nM.neighbors(1))

    fMD = fnx.MultiDiGraph([(1, 2), (1, 2), (2, 3), (3, 1)])
    nMD = nx.MultiDiGraph([(1, 2), (1, 2), (2, 3), (3, 1)])
    assert isinstance(fMD.successors(1), dict_keyiterator)
    assert isinstance(nMD.successors(1), dict_keyiterator)
    assert isinstance(fMD.predecessors(1), dict_keyiterator)
    assert isinstance(nMD.predecessors(1), dict_keyiterator)

    # Iteration is stateful (the original cycle-XYZ br-nbriter
    # property must be preserved by the new wrapper).
    it = fG.neighbors(2)
    next(it)
    remaining = list(it)
    full = list(fG.neighbors(2))
    assert len(remaining) == len(full) - 1


def test_adjacency_view_iter_returns_dict_keyiterator():
    """br-r37-c1-adjitype (cycle 219): nx's
    ``AdjacencyView.__iter__`` is ``return iter(self._atlas)`` where
    ``_atlas`` is a Python dict, yielding a ``dict_keyiterator``.
    fnx's ``_atlas()`` returns a Rust-bound view whose ``__iter__``
    returns ``NodeIterator``, diverging on
    ``type(iter(G.adj)).__name__``.

      Method                           nx                 fnx (pre-fix)
      ------                           ---                -------------
      type(iter(G.adj))                dict_keyiterator   NodeIterator
      type(iter(DG.adj))               dict_keyiterator   NodeIterator
      type(iter(DG.pred))              dict_keyiterator   NodeIterator
      type(iter(DG.succ))              dict_keyiterator   NodeIterator
      type(iter(MG.adj))               dict_keyiterator   NodeIterator
      type(iter(MDG.{adj,pred,succ}))  dict_keyiterator   NodeIterator

    Sister of cycle 218 (br-r37-c1-nbritype) for
    ``neighbors``/``successors``/``predecessors``.

    Drop-in code that does
    ``isinstance(it, type({}.__iter__()))`` saw the wrong runtime
    type.

    Fix: in both ``AdjacencyView.__iter__`` and
    ``MultiAdjacencyView.__iter__``, materialise via
    ``iter(dict.fromkeys(self._atlas()))`` so the iterator runtime
    type is ``dict_keyiterator``.  Content semantics are unchanged
    (the underlying view is already keyed by unique node ids).
    """
    dict_keyiterator = type({}.__iter__())

    fG = fnx.Graph([(1, 2), (2, 3), (3, 4)])
    nG = nx.Graph([(1, 2), (2, 3), (3, 4)])
    assert isinstance(iter(fG.adj), dict_keyiterator)
    assert isinstance(iter(nG.adj), dict_keyiterator)
    assert sorted(fG.adj) == sorted(nG.adj)

    fD = fnx.DiGraph([(1, 2), (2, 3), (3, 1)])
    nD = nx.DiGraph([(1, 2), (2, 3), (3, 1)])
    for attr in ("adj", "pred", "succ"):
        assert isinstance(iter(getattr(fD, attr)), dict_keyiterator), attr
        assert isinstance(iter(getattr(nD, attr)), dict_keyiterator), attr
        assert sorted(getattr(fD, attr)) == sorted(getattr(nD, attr))

    fM = fnx.MultiGraph([(1, 2), (1, 2), (2, 3)])
    nM = nx.MultiGraph([(1, 2), (1, 2), (2, 3)])
    assert isinstance(iter(fM.adj), dict_keyiterator)
    assert isinstance(iter(nM.adj), dict_keyiterator)

    fMD = fnx.MultiDiGraph([(1, 2), (2, 3), (3, 1)])
    nMD = nx.MultiDiGraph([(1, 2), (2, 3), (3, 1)])
    for attr in ("adj", "pred", "succ"):
        assert isinstance(iter(getattr(fMD, attr)), dict_keyiterator), attr
        assert isinstance(iter(getattr(nMD, attr)), dict_keyiterator), attr

    # Mapping-protocol soundness: keys/items/values still work.
    assert sorted(fG.adj.keys()) == sorted(nG.adj.keys())
    assert sorted([(k, sorted(v)) for k, v in fG.adj.items()]) == \
           sorted([(k, sorted(v)) for k, v in nG.adj.items()])


def test_subclass_graph_attr_dict_factory_is_honored():
    """br-r37-c1-gattfact (cycle 220): nx's documented subclass
    extension point ``graph_attr_dict_factory`` allows callers to
    define a custom graph-attribute container type:

        class MyGraph(nx.Graph):
            graph_attr_dict_factory = MyDictType

    nx invokes the factory in ``__init__`` (``self.graph =
    self.graph_attr_dict_factory()``).  fnx ignored the factory and
    exposed the Rust-native plain ``dict`` directly, so
    ``MyGraph().graph`` was always a plain ``dict`` — drop-in
    subclasses with a custom factory silently lost both their
    custom container type and any default contents.

      Drop-in pattern (nx):
        class GraphWithDefaults(nx.Graph):
            graph_attr_dict_factory = SomeCustomDict   # populates
                                                       # default keys

        g = GraphWithDefaults()
        assert isinstance(g.graph, SomeCustomDict)
        assert g.graph == {...default keys from SomeCustomDict()...}

    fnx (pre-fix) silently returned ``{}`` (plain dict).

    Fix: in ``_GraphAttrsDescriptor.__get__``, when the subclass
    overrides ``graph_attr_dict_factory`` (i.e. it's not the default
    ``dict``), lazily materialise via the factory on first access
    and store as the attribute override.  Pre-existing Rust-side
    contents are preserved (merged into the new dict and the Rust
    dict is cleared).  The default ``dict`` path still uses the
    Rust-native fast path.

    All four graph classes (Graph/DiGraph/MultiGraph/MultiDiGraph)
    must honour the override.
    """
    import networkx as nx

    class CustomDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setdefault("_factory_marker", "custom")

    for fcls, ncls in [
        (fnx.Graph,        nx.Graph),
        (fnx.DiGraph,      nx.DiGraph),
        (fnx.MultiGraph,   nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        class FS(fcls):
            graph_attr_dict_factory = CustomDict

        class NS(ncls):
            graph_attr_dict_factory = CustomDict

        fs = FS()
        ns = NS()

        # Type matches nx.
        assert isinstance(fs.graph, CustomDict), \
            f"{fcls.__name__}: type(fs.graph)={type(fs.graph).__name__}"
        assert isinstance(ns.graph, CustomDict)

        # Default contents from the factory are present.
        assert fs.graph["_factory_marker"] == "custom"
        assert ns.graph["_factory_marker"] == "custom"

        # Subsequent mutation propagates.
        fs.graph["user_attr"] = 42
        assert fs.graph["user_attr"] == 42
        assert isinstance(fs.graph, CustomDict)

        # Re-access returns the SAME object (identity preserved).
        assert fs.graph is fs.graph

    # The default path (no factory override) still works and uses
    # the Rust-native dict.
    g = fnx.Graph()
    g.graph["x"] = 1
    assert g.graph == {"x": 1}
    assert type(g.graph) is dict


def test_clear_empties_graph_attr_factory_override_in_place():
    """br-r37-c1-clrovr (cycle 221): cycle 220's
    ``graph_attr_dict_factory`` fix stores the live attrs dict as an
    override on the instance.  The Rust-bound ``clear()`` doesn't
    know about the override, so subclasses with a custom factory
    saw stale attrs after ``g.clear()``.  nx's ``Graph.clear``
    invokes ``self.graph.clear()`` in-place — dict identity is
    preserved, contents emptied.  Mirror that contract here so:

      class S(Graph):
          graph_attr_dict_factory = MyDict
      g = S()
      g.graph['x'] = 1
      before = g.graph
      g.clear()
      after = g.graph
      assert before is after          # identity preserved
      assert dict(after) == {'_factory_marker': 'custom'}  # default contents
                                       # ``MyDict()`` re-populates upon
                                       # subsequent access.

    Wait — actually cycle 221 fixes the simpler property: clear()
    empties the dict (matching nx).  The factory's default keys
    don't re-populate after clear(); they only populate on FIRST
    access.  This matches nx's semantics: nx invokes the factory
    once in ``__init__`` and clear() empties the resulting dict.

      Drop-in property:
        before = g.graph
        g.clear()
        assert before is g.graph     # SAME dict object
        assert dict(g.graph) == {}   # but empty

    Sister to cycle 220 (br-r37-c1-nzzhs) which exposed the
    factory but left clear() interaction broken.
    """
    import networkx as nx

    class CustomDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setdefault("_factory_marker", "custom")

    for fcls, ncls in [
        (fnx.Graph,        nx.Graph),
        (fnx.DiGraph,      nx.DiGraph),
        (fnx.MultiGraph,   nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        class FS(fcls):
            graph_attr_dict_factory = CustomDict

        class NS(ncls):
            graph_attr_dict_factory = CustomDict

        fs = FS()
        ns = NS()

        fs.graph["x"] = 1
        ns.graph["x"] = 1
        fs.add_edge(1, 2)
        ns.add_edge(1, 2)

        before_fs = fs.graph
        before_ns = ns.graph

        fs.clear()
        ns.clear()

        # Identity preserved (in-place clear).
        assert fs.graph is before_fs, fcls.__name__
        assert ns.graph is before_ns, ncls.__name__

        # Contents emptied.
        assert dict(fs.graph) == {}, fcls.__name__
        assert dict(ns.graph) == {}, ncls.__name__

        # Type preserved (still the custom container).
        assert type(fs.graph) is CustomDict
        assert type(ns.graph) is CustomDict

    # Default path: clear() still works (no factory override).
    g = fnx.Graph()
    g.graph["x"] = 1
    g.add_edge(1, 2)
    g.clear()
    assert dict(g.graph) == {}
    assert sorted(g.nodes()) == []
    assert sorted(g.edges()) == []


def test_g_name_reads_through_graph_attr_factory_override():
    """br-r37-c1-namovr (cycle 222): cycle 220's
    ``graph_attr_dict_factory`` fix stores the live attrs dict as a
    Python-side override and clears the Rust-side dict to avoid
    double-tracking.  The Rust-bound ``name`` getter read from the
    (now-empty) Rust dict, so for subclasses with a custom factory:

      class S(Graph):
          graph_attr_dict_factory = CustomDict
      g = S()
      g.name = 'foo'
      # nx:  g.name == 'foo'
      # fnx: g.name == ''             *** DIFF — getter bypassed
                                       # the override

    Sister of cycles 220/221 — completes the factory-override
    contract for the documented ``name`` property.

    Fix: replace the Rust-bound ``name`` getset_descriptor with a
    Python ``property`` that round-trips through ``self.graph``
    (which already handles the override via the descriptor).
    Mirrors nx's implementation.

    Both default and override paths must work, all 4 graph classes.
    """
    import networkx as nx

    # Default path (no factory override)
    for fcls, ncls in [
        (fnx.Graph,        nx.Graph),
        (fnx.DiGraph,      nx.DiGraph),
        (fnx.MultiGraph,   nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        # Default empty
        assert fcls().name == ncls().name == ""

        # Constructor kwarg
        assert fcls(name="foo").name == ncls(name="foo").name == "foo"

        # Setter
        fg = fcls()
        ng = ncls()
        fg.name = "set_via_attr"
        ng.name = "set_via_attr"
        assert fg.name == ng.name == "set_via_attr"
        assert fg.graph["name"] == ng.graph["name"] == "set_via_attr"

    # Override path (subclass with custom graph_attr_dict_factory)
    class CustomDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setdefault("_marker", "custom")

    for fcls, ncls in [
        (fnx.Graph,        nx.Graph),
        (fnx.DiGraph,      nx.DiGraph),
        (fnx.MultiGraph,   nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        class FS(fcls):
            graph_attr_dict_factory = CustomDict

        class NS(ncls):
            graph_attr_dict_factory = CustomDict

        fs = FS()
        ns = NS()
        fs.name = "factory_path"
        ns.name = "factory_path"

        # Read through the override
        assert fs.name == "factory_path", f"{fcls.__name__}: fs.name={fs.name!r}"
        assert ns.name == "factory_path"

        # The override dict has the value too
        assert fs.graph["name"] == "factory_path"
        assert ns.graph["name"] == "factory_path"

        # Custom factory type preserved
        assert isinstance(fs.graph, CustomDict)
        assert isinstance(ns.graph, CustomDict)


def test_g_graph_inplace_or_operator_merges_correctly():
    """br-r37-c1-iorgrf (cycle 223): Python's in-place dict-union
    operator (``g.graph |= {...}``, PEP 584 / Python 3.9+) desugars
    to ``g.graph = dict.__ior__(g.graph, other)``.  ``dict.__ior__``
    mutates the dict in-place and returns ``self``, so the assigned
    value IS the same object as the current graph dict.

    The cycle-XYZ ``br-grattrident`` ``__set__`` did
    ``current.clear(); current.update(value)``.  When
    ``current is value``, the ``current.clear()`` call cleared the
    very dict whose merged-in contents we wanted to keep — so
    ``g.graph |= {x: 1}`` silently produced ``{}`` instead of
    ``{x: 1}``.

      Drop-in pattern (nx):
        g.graph |= {'k': 1}
        # nx:  g.graph == {'k': 1}
        # fnx (pre-fix): g.graph == {}        *** DIFF — silent loss

    Affects all 4 graph classes for both default and override paths.

    Sister of cycles 220-222 — completes the factory-override and
    Python-dict-protocol contract.

    Fix: detect ``current is value`` in ``_GraphAttrsDescriptor.__set__``
    and short-circuit (the in-place operator already mutated the
    dict; no clear-and-update is needed and would be destructive).
    """
    import networkx as nx

    # Default path: in-place |= works
    for fcls, ncls in [
        (fnx.Graph,        nx.Graph),
        (fnx.DiGraph,      nx.DiGraph),
        (fnx.MultiGraph,   nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        fg = fcls()
        ng = ncls()
        fg.graph |= {"x": 1, "y": 2}
        ng.graph |= {"x": 1, "y": 2}
        assert dict(fg.graph) == dict(ng.graph) == {"x": 1, "y": 2}, fcls.__name__

    # Override path (subclass with custom factory)
    class CustomDict(dict):
        pass

    for fcls, ncls in [
        (fnx.Graph,        nx.Graph),
        (fnx.DiGraph,      nx.DiGraph),
        (fnx.MultiGraph,   nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        class FS(fcls):
            graph_attr_dict_factory = CustomDict

        class NS(ncls):
            graph_attr_dict_factory = CustomDict

        fs = FS()
        ns = NS()
        fs.graph |= {"a": 1}
        ns.graph |= {"a": 1}
        assert dict(fs.graph) == dict(ns.graph) == {"a": 1}, fcls.__name__
        assert isinstance(fs.graph, CustomDict)
        assert isinstance(ns.graph, CustomDict)

    # Chained |= compounds correctly
    g = fnx.Graph()
    g.graph["a"] = 1
    g.graph |= {"b": 2}
    g.graph |= {"c": 3}
    assert dict(g.graph) == {"a": 1, "b": 2, "c": 3}

    # Identity preservation contract (br-grattrident) still holds for
    # ``g.graph = NEW_DICT`` (different object).
    g = fnx.Graph()
    before = g.graph
    g.graph = {"x": 1}
    assert before is g.graph
    assert dict(g.graph) == {"x": 1}


def test_set_operators_on_subgraph_views():
    """br-r37-c1-k7dct (cycle 225): the binary graph operators
    ``intersection`` / ``difference`` / ``symmetric_difference`` /
    ``compose`` / ``disjoint_union`` rebuild their output via
    ``type(G)()`` (directly or transitively through
    ``_operator_output_class`` / ``relabel_nodes``).  When ``G`` is a
    ``SubgraphView``, ``type(G)`` is the synthetic
    ``_FilteredGraphView`` whose ``__init__`` requires a ``graph``
    positional arg, so the bare ``cls()`` blew up with
    ``TypeError: _FilteredGraphView.__init__() missing 1 required
    positional argument: 'graph'``.  nx returns a concrete
    Graph/DiGraph/MultiGraph/MultiDiGraph in this case.

    Fix: route ``type(G)`` resolution through
    ``_concrete_class_for(G)``, which substitutes the canonical
    concrete fnx class for any ``_FilteredGraphView`` based on the
    view's (is_directed, is_multigraph) flavor.
    """
    import networkx as nx

    def _build_fnx():
        g1 = fnx.Graph()
        g1.add_nodes_from([0, 1, 2])
        g1.add_edges_from([(0, 1), (1, 2)])
        g2 = fnx.Graph()
        g2.add_nodes_from([0, 1, 2])
        g2.add_edges_from([(0, 1), (0, 2)])
        return g1.subgraph([0, 1, 2]), g2.subgraph([0, 1, 2])

    def _build_nx():
        g1 = nx.Graph()
        g1.add_nodes_from([0, 1, 2])
        g1.add_edges_from([(0, 1), (1, 2)])
        g2 = nx.Graph()
        g2.add_nodes_from([0, 1, 2])
        g2.add_edges_from([(0, 1), (0, 2)])
        return g1.subgraph([0, 1, 2]), g2.subgraph([0, 1, 2])

    fsg1, fsg2 = _build_fnx()
    nsg1, nsg2 = _build_nx()

    def _canon(g):
        return sorted(tuple(sorted(e)) for e in g.edges())

    # intersection/symmetric_difference/compose: same edge set as nx.
    for op_name in ("intersection", "symmetric_difference", "compose"):
        f_op = getattr(fnx, op_name)
        n_op = getattr(nx, op_name)
        assert _canon(f_op(fsg1, fsg2)) == _canon(n_op(nsg1, nsg2)), op_name

    # disjoint_union renumbers nodes to ints — compare canonical edges.
    assert _canon(fnx.disjoint_union(fsg1, fsg2)) == _canon(
        nx.disjoint_union(nsg1, nsg2)
    )

    # difference: edge set parity (fnx may emit tuples reversed, set parity is what counts).
    assert _canon(fnx.difference(fsg1, fsg2)) == _canon(
        nx.difference(nsg1, nsg2)
    )

    # The returned objects must be concrete classes (NOT view subclasses),
    # so callers can mutate them.
    out = fnx.intersection(fsg1, fsg2)
    assert type(out) is fnx.Graph
    out.add_edge(99, 100)  # must not raise (was previously a view => frozen)
    assert (99, 100) in [tuple(sorted(e)) for e in out.edges()]

    # Directed view → DiGraph output.
    fdg = fnx.DiGraph()
    fdg.add_nodes_from([0, 1, 2])
    fdg.add_edges_from([(0, 1), (1, 2)])
    sg = fdg.subgraph([0, 1, 2])
    out = fnx.intersection(sg, sg)
    assert type(out) is fnx.DiGraph


def test_rust_path_respects_subgraph_view_filter():
    """br-r37-c1-ajhcl (cycle 227): SubgraphView / _FilteredGraphView
    isinstance-passes the canonical fnx Graph type (a second-base trick
    added for isinstance parity), so ``_coerce_arg_to_fnx_graph`` used
    to pass the view through unchanged. But Rust ``_raw_*`` operators
    read the parent's Rust adjacency directly — they have no knowledge
    of the Python-side filter — so callers got the parent's full
    connectivity instead of the view's filtered one.

    Bug repro: g=path_graph(5); sg=g.subgraph([0,1,3,4]). View edges
    are [(0,1), (3,4)] — two components. fnx returned ONE component
    {0,1,2,3,4} (parent's full set) and is_connected=True.

    Sister operators (``difference`` / ``symmetric_difference``)
    likewise leaked the parent's hidden edges back into the result.

    Fix: ``_coerce_arg_to_fnx_graph`` now detects _FilteredGraphView
    first and materializes it via ``_materialize_filtered_view`` (a
    cheap copy of the view's visible nodes + edges + attrs into a
    fresh concrete fnx graph) before the Rust binding sees it.
    """
    import networkx as nx

    # connected_components on a SubgraphView that hides middle node 2
    g = fnx.path_graph(5)
    sg = g.subgraph([0, 1, 3, 4])
    cc_fnx = [sorted(c) for c in fnx.connected_components(sg)]
    cc_nx = [
        sorted(c)
        for c in nx.connected_components(nx.path_graph(5).subgraph([0, 1, 3, 4]))
    ]
    assert sorted(cc_fnx) == sorted(cc_nx) == [[0, 1], [3, 4]]
    assert fnx.is_connected(sg) is False
    assert fnx.number_connected_components(sg) == 2

    # difference: only the view's visible edges should be considered.
    g1 = fnx.path_graph(5)
    g2 = fnx.Graph()
    g2.add_nodes_from([0, 1, 3, 4])
    g2.add_edge(0, 1)
    sg1 = g1.subgraph([0, 1, 3, 4])
    # Visible edges of sg1: {(0,1), (3,4)}. g2 has {(0,1)}. Difference: {(3,4)}.
    diff = sorted(tuple(sorted(e)) for e in fnx.difference(sg1, g2).edges())
    assert diff == [(3, 4)]

    # symmetric_difference parity
    g3 = fnx.Graph()
    g3.add_nodes_from([0, 1, 3, 4])
    g3.add_edge(0, 1)
    g3.add_edge(0, 4)
    sym = sorted(
        tuple(sorted(e)) for e in fnx.symmetric_difference(sg1, g3).edges()
    )
    assert sym == [(0, 4), (3, 4)]


def test_clustering_respects_subgraph_view_filter():
    """br-r37-c1-c7xg2 (cycle 227): ``clustering`` short-circuited to
    ``_raw_clustering(G)`` (a Rust-fast path) without going through
    ``_coerce_arg_to_fnx_graph``. SubgraphView isinstance-passes the
    canonical Graph type but the Rust binding reads the parent's
    Rust state directly, so a view over four visible nodes ended up
    returning five entries (one per parent node, including the hidden
    one).

    Fix: route ``clustering`` through ``_coerce_arg_to_fnx_graph`` so
    the view gets materialized via _materialize_filtered_view first.
    """
    import networkx as nx

    g_fnx = fnx.path_graph(5)
    g_nx = nx.path_graph(5)
    sg_fnx = g_fnx.subgraph([0, 1, 3, 4])
    sg_nx = g_nx.subgraph([0, 1, 3, 4])
    c_fnx = fnx.clustering(sg_fnx)
    c_nx = nx.clustering(sg_nx)
    assert sorted(c_fnx.keys()) == sorted(c_nx.keys()) == [0, 1, 3, 4]
    assert c_fnx == c_nx


def test_average_neighbor_degree_respects_subgraph_view_filter():
    """br-r37-c1-2dbnk (cycle 228): sibling of br-r37-c1-c7xg2.
    ``average_neighbor_degree`` short-circuited the undirected /
    no-weight / no-nbunch / simple-graph case to
    ``_raw_average_neighbor_degree(G)`` without coercing first, so
    SubgraphView passed through and the Rust reader returned the
    parent's full degrees.

    Repro: K6.subgraph([0,1,2,3]) — view's K4 should give each node
    avg-neighbor-degree 3. Pre-fix fnx returned 5 (the K6 degree).
    """
    import networkx as nx

    gf = fnx.complete_graph(6)
    gn = nx.complete_graph(6)
    sg_fnx = gf.subgraph([0, 1, 2, 3])
    sg_nx = gn.subgraph([0, 1, 2, 3])
    assert (
        fnx.assortativity.average_neighbor_degree(sg_fnx)
        == nx.assortativity.average_neighbor_degree(sg_nx)
    )


def test_average_shortest_path_length_respects_subgraph_view_filter():
    """br-r37-c1-10xrd (cycle 228): sibling of ajhcl/c7xg2/2dbnk.
    ``average_shortest_path_length`` called ``_raw_average_shortest_path_
    length(G)`` directly; on a SubgraphView whose visible nodes happen
    to be disconnected (P5.subgraph([0,1,3,4]) — node 2 hidden), the
    Rust path reads the parent's connected P5 state and quietly
    returns a number instead of raising NetworkXError("Graph is not
    connected.") as nx does.

    Fix: coerce SG before the Rust call.
    """
    import networkx as nx

    gf = fnx.path_graph(5)
    gn = nx.path_graph(5)
    sg_fnx = gf.subgraph([0, 1, 3, 4])
    sg_nx = gn.subgraph([0, 1, 3, 4])
    import pytest as _pytest
    with _pytest.raises(fnx.NetworkXError):
        fnx.average_shortest_path_length(sg_fnx)
    with _pytest.raises(nx.NetworkXError):
        nx.average_shortest_path_length(sg_nx)


def test_more_rust_shortcuts_respect_subgraph_view_filter():
    """br-r37-c1-gr1ct (cycle 228): siblings of the earlier
    view-coerce family fixes. Five more Rust shortcuts —
    greedy_color, all_pairs_shortest_path_length,
    all_pairs_dijkstra_path_length, single_source_dijkstra_path,
    multi_source_dijkstra(_path_length) — short-circuited into the
    Rust binding without coercing, so they returned entries for
    nodes the view filters out.

    Repro: K6.subgraph([0,1,2,3]). View should only mention nodes
    0-3 but pre-fix versions returned data for 4, 5 too.
    """
    import networkx as nx

    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])

    # greedy_color: only the visible nodes should be colored.
    cf = fnx.greedy_color(sgf)
    cn = nx.greedy_color(sgn)
    assert sorted(cf.keys()) == sorted(cn.keys()) == [0, 1, 2, 3]

    # all_pairs_shortest_path_length: visible-only entries.
    apspl_f = dict(fnx.all_pairs_shortest_path_length(sgf))
    apspl_n = dict(nx.all_pairs_shortest_path_length(sgn))
    assert sorted(apspl_f.keys()) == sorted(apspl_n.keys()) == [0, 1, 2, 3]
    assert all(sorted(v.keys()) == [0, 1, 2, 3] for v in apspl_f.values())

    # all_pairs_dijkstra_path_length: visible-only entries.
    apdj_f = dict(fnx.all_pairs_dijkstra_path_length(sgf))
    apdj_n = dict(nx.all_pairs_dijkstra_path_length(sgn))
    assert sorted(apdj_f.keys()) == sorted(apdj_n.keys()) == [0, 1, 2, 3]
    assert all(sorted(v.keys()) == [0, 1, 2, 3] for v in apdj_f.values())

    # single_source_dijkstra_path: visible-only entries.
    ssdp_f = fnx.single_source_dijkstra_path(sgf, 0)
    ssdp_n = nx.single_source_dijkstra_path(sgn, 0)
    assert sorted(ssdp_f.keys()) == sorted(ssdp_n.keys()) == [0, 1, 2, 3]

    # multi_source_dijkstra_path_length: visible-only entries.
    msdpl_f = fnx.multi_source_dijkstra_path_length(sgf, [0, 1])
    msdpl_n = nx.multi_source_dijkstra_path_length(sgn, [0, 1])
    assert sorted(msdpl_f.keys()) == sorted(msdpl_n.keys()) == [0, 1, 2, 3]


def test_spanning_tree_helpers_respect_subgraph_view_filter():
    """br-r37-c1-zapl2 (cycle 228): sibling of gr1ct.
    minimum_spanning_edges and partition_spanning_tree short-circuit
    into the Rust kernel without coercing; SubgraphView callers got
    a spanning structure sized to the parent (e.g. 5 edges from a
    K6) instead of the view's K4 (3 edges).
    """
    import networkx as nx

    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])
    assert (
        len(list(fnx.minimum_spanning_edges(sgf)))
        == len(list(nx.minimum_spanning_edges(sgn)))
        == 3
    )
    assert (
        len(list(fnx.partition_spanning_tree(sgf).edges()))
        == len(list(nx.partition_spanning_tree(sgn).edges()))
        == 3
    )


def test_transitive_reduction_on_subgraph_view():
    """br-r37-c1-blaz5 (cycle 229): transitive_reduction's
    _transitive_reduction_via_parity helper rebuilt the result via
    bare ``type(G)()``, which is _FilteredGraphView for SubgraphView
    inputs — the synthetic class's __init__ requires a 'graph' arg,
    so the call raised TypeError. Route through _concrete_class_for(G).

    Same root cause as the cycle-225 operator fix family
    (br-r37-c1-k7dct).
    """
    import networkx as nx

    g = fnx.DiGraph([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])
    sg = g.subgraph([0, 1, 3, 4])
    # nx and fnx both treat the SG as: edges {(0,1), (3,4)} (node 2 hidden).
    out = fnx.transitive_reduction(sg)
    assert type(out) is fnx.DiGraph
    assert sorted(out.edges()) == [(0, 1), (3, 4)]
    assert sorted(out.edges()) == sorted(
        nx.transitive_reduction(nx.DiGraph([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]).subgraph([0, 1, 3, 4])).edges()
    )


def test_quotient_graph_on_subgraph_view():
    """br-r37-c1-5r04c (cycle 229): quotient_graph fell back to
    bare ``G.__class__()`` when create_using was None, crashing
    on _FilteredGraphView SubgraphView inputs. Same cycle-225
    family fix — route through _concrete_class_for(G).
    """
    import networkx as nx

    gf = fnx.complete_graph(6)
    gn = nx.complete_graph(6)
    sgf = gf.subgraph([0, 1, 2, 3])
    sgn = gn.subgraph([0, 1, 2, 3])
    # Trivial single-block partition collapses to a single super-node.
    qf = fnx.quotient_graph(sgf, lambda u, v: True)
    qn = nx.quotient_graph(sgn, lambda u, v: True)
    assert qf.number_of_nodes() == qn.number_of_nodes()
    assert qf.number_of_edges() == qn.number_of_edges()


def test_more_helpers_on_subgraph_view():
    """br-r37-c1-s8w2p (cycle 229): six more rebuild helpers used
    bare ``G.__class__()`` (or two sites in ``power``), all of which
    raised TypeError on SubgraphView (_FilteredGraphView.__init__
    requires a 'graph' arg). Replaced each with
    ``_concrete_class_for(G)()`` so views are rebuilt as their
    canonical concrete class.

    Functions covered: create_empty_copy, ego_graph, contracted_nodes,
    identified_nodes, panther_similarity, snap_aggregation, power.
    Plus the private helpers _nan_filtered_graph,
    _panther_induced_ordered_copy, _copy_graph_shallow.
    """
    import networkx as nx

    # K6 subgraph -> K4 view
    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])

    # create_empty_copy: returns 4 nodes, no edges
    cf = fnx.create_empty_copy(sgf)
    cn = nx.create_empty_copy(sgn)
    assert sorted(cf.nodes()) == sorted(cn.nodes()) == [0, 1, 2, 3]
    assert cf.number_of_edges() == cn.number_of_edges() == 0

    # ego_graph from a P5 SG
    gpf = fnx.path_graph(10).subgraph(range(5))
    gpn = nx.path_graph(10).subgraph(range(5))
    egf = fnx.ego_graph(gpf, 2)
    egn = nx.ego_graph(gpn, 2)
    assert sorted(egf.nodes()) == sorted(egn.nodes())

    # contracted_nodes
    cnf = fnx.contracted_nodes(sgf, 0, 1)
    cnn = nx.contracted_nodes(sgn, 0, 1)
    assert sorted(cnf.nodes()) == sorted(cnn.nodes())

    # power: K4 squared = K4 (already complete) — no crash, edge set matches
    pf = fnx.power(sgf, 2)
    pn = nx.power(sgn, 2)
    assert (
        sorted(tuple(sorted(e)) for e in pf.edges())
        == sorted(tuple(sorted(e)) for e in pn.edges())
    )

    # panther_similarity (k=2, fixed seed)
    psf = fnx.panther_similarity(sgf, 0, k=2, seed=42)
    psn = nx.panther_similarity(sgn, 0, k=2, seed=42)
    assert set(psf.keys()).issubset({0, 1, 2, 3})
    assert set(psn.keys()) == set(psf.keys())


def test_random_spanning_tree_and_tc_dag_on_subgraph_view():
    """br-r37-c1-lblzk (cycle 230): random_spanning_tree
    (_random_spanning_tree_via_parity) and transitive_closure_dag
    (_transitive_closure_dag_via_parity) rebuilt results via bare
    ``type(G)()`` — crashed on SubgraphView. Same cycle-225 family fix:
    route through _concrete_class_for(G).
    """
    import networkx as nx

    # random_spanning_tree: works on a connected SubgraphView (K6 -> K4).
    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])
    rstf = fnx.random_spanning_tree(sgf, seed=42)
    rstn = nx.random_spanning_tree(sgn, seed=42)
    assert type(rstf) is fnx.Graph
    assert rstf.number_of_nodes() == rstn.number_of_nodes() == 4
    assert rstf.number_of_edges() == rstn.number_of_edges() == 3

    # transitive_closure_dag on a DAG SubgraphView.
    dgf = fnx.DiGraph([(0, 1), (1, 2), (2, 3)]).subgraph([0, 1, 2, 3])
    dgn = nx.DiGraph([(0, 1), (1, 2), (2, 3)]).subgraph([0, 1, 2, 3])
    tcf = fnx.transitive_closure_dag(dgf)
    tcn = nx.transitive_closure_dag(dgn)
    assert type(tcf) is fnx.DiGraph
    assert sorted(tcf.edges()) == sorted(tcn.edges())


def test_cut_size_and_normalized_cut_size_respect_subgraph_view():
    """br-r37-c1-eog89 (cycle 230): cut_size and normalized_cut_size
    fed SubgraphView directly to Rust _raw_cut_size/
    _raw_normalized_cut_size, which read the parent's adjacency and
    returned wrong (parent-sized) results. mixing_expansion transitively
    inherits the cut_size fix.

    Repro: K6.subgraph([0,1,2,3]). cut_size(sg, [0,1]) — nx returns 4
    (K4 view's cut), pre-fix fnx returned 8 (K6 parent's cut).
    """
    import networkx as nx

    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])
    assert fnx.cut_size(sgf, [0, 1]) == nx.cut_size(sgn, [0, 1]) == 4
    assert (
        round(fnx.normalized_cut_size(sgf, [0, 1]), 6)
        == round(nx.normalized_cut_size(sgn, [0, 1]), 6)
    )
    assert (
        round(fnx.mixing_expansion(sgf, [0, 1]), 6)
        == round(nx.mixing_expansion(sgn, [0, 1]), 6)
    )


def test_boundary_and_single_source_dijkstra_on_subgraph_view():
    """br-r37-c1-e861i (cycle 230): node_boundary, edge_boundary, and
    single_source_dijkstra fed SubgraphView directly into the Rust
    _raw_* kernels and returned entries for nodes outside the view.
    boundary_expansion is fixed transitively (via node_boundary).
    """
    import networkx as nx

    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])

    assert fnx.node_boundary(sgf, [0, 1]) == nx.node_boundary(sgn, [0, 1]) == {2, 3}
    assert sorted(tuple(sorted(e)) for e in fnx.edge_boundary(sgf, [0, 1])) == sorted(
        tuple(sorted(e)) for e in nx.edge_boundary(sgn, [0, 1])
    )
    assert fnx.boundary_expansion(sgf, [0, 1]) == nx.boundary_expansion(sgn, [0, 1])

    dist_f, paths_f = fnx.single_source_dijkstra(sgf, 0)
    dist_n, paths_n = nx.single_source_dijkstra(sgn, 0)
    assert sorted(dist_f.keys()) == sorted(dist_n.keys()) == [0, 1, 2, 3]
    assert sorted(paths_f.keys()) == sorted(paths_n.keys()) == [0, 1, 2, 3]


def test_minimum_cycle_basis_respects_subgraph_view():
    """br-r37-c1-ey500 (cycle 230): minimum_cycle_basis fed
    SubgraphView straight to _raw_minimum_cycle_basis and got back
    cycles involving parent nodes outside the view. Add coerce preface.
    """
    import networkx as nx

    sgf = fnx.complete_graph(6).subgraph([0, 1, 2, 3])
    sgn = nx.complete_graph(6).subgraph([0, 1, 2, 3])
    cf = [sorted(c) for c in fnx.minimum_cycle_basis(sgf)]
    cn = [sorted(c) for c in nx.minimum_cycle_basis(sgn)]
    # Every cycle should be inside {0,1,2,3}
    allowed = {0, 1, 2, 3}
    for cycle in cf:
        assert set(cycle).issubset(allowed)
    assert sorted(cf) == sorted(cn)


def test_capacity_scaling_unfeasible_message_matches_nx():
    """br-r37-c1-8lsax (cycle 231): nx's network_simplex and
    capacity_scaling raise NetworkXUnfeasible with DIFFERENT wording.
    nx.network_simplex says "no flow satisfies all node demands";
    nx.capacity_scaling says "No flow satisfying all demands." (cap N,
    'satisfying', trailing period).

    fnx shares one min_cost_flow implementation that always raised
    the network_simplex message. Wrap the call in capacity_scaling to
    translate the message at that boundary so both functions match
    their nx counterparts exactly.
    """
    import networkx as nx
    import pytest as _pytest

    def make_fnx():
        g = fnx.DiGraph()
        g.add_node(0, demand=-5)
        g.add_node(1)
        g.add_node(2, demand=5)
        g.add_edges_from([
            (0, 1, {'capacity': 4, 'weight': 1}),
            (1, 2, {'capacity': 5, 'weight': 2}),
        ])
        return g

    def make_nx():
        g = nx.DiGraph()
        g.add_node(0, demand=-5)
        g.add_node(1)
        g.add_node(2, demand=5)
        g.add_edges_from([
            (0, 1, {'capacity': 4, 'weight': 1}),
            (1, 2, {'capacity': 5, 'weight': 2}),
        ])
        return g

    with _pytest.raises(fnx.NetworkXUnfeasible) as e_fnx_ns:
        fnx.network_simplex(make_fnx())
    with _pytest.raises(nx.NetworkXUnfeasible) as e_nx_ns:
        nx.network_simplex(make_nx())
    assert str(e_fnx_ns.value) == str(e_nx_ns.value) == (
        "no flow satisfies all node demands"
    )

    with _pytest.raises(fnx.NetworkXUnfeasible) as e_fnx_cs:
        fnx.capacity_scaling(make_fnx())
    with _pytest.raises(nx.NetworkXUnfeasible) as e_nx_cs:
        nx.capacity_scaling(make_nx())
    assert str(e_fnx_cs.value) == str(e_nx_cs.value) == (
        "No flow satisfying all demands."
    )


def test_min_cost_flow_inf_and_unbalanced_demand_match_nx():
    """br-r37-c1-74xas (cycle 231): min_cost_flow demand validation
    raised wrong exception type (NetworkXUnfeasible) and wrong message
    on the inf-demand path (nx uses NetworkXError "node X has infinite
    demand"), and the wrong wording on the unbalanced-demand path
    (nx uses "total node demand is not zero", lowercase, no period).

    Detect inf demand explicitly and use the nx wordings for parity.
    """
    import networkx as nx
    import pytest as _pytest

    # Infinite demand → NetworkXError
    def mk_inf_fnx():
        g = fnx.DiGraph()
        g.add_node(0, demand=float('inf'))
        g.add_node(1, demand=-5)
        g.add_edge(0, 1, capacity=5, weight=1)
        return g
    def mk_inf_nx():
        g = nx.DiGraph()
        g.add_node(0, demand=float('inf'))
        g.add_node(1, demand=-5)
        g.add_edge(0, 1, capacity=5, weight=1)
        return g
    with _pytest.raises(fnx.NetworkXError) as ef:
        fnx.min_cost_flow(mk_inf_fnx())
    with _pytest.raises(nx.NetworkXError) as en:
        nx.min_cost_flow(mk_inf_nx())
    assert str(ef.value) == str(en.value) == "node 0 has infinite demand"

    # Unbalanced demand → NetworkXUnfeasible with exact wording
    def mk_unbal_fnx():
        g = fnx.DiGraph()
        g.add_node(0, demand=-5)
        g.add_node(1, demand=3)
        g.add_edge(0, 1, capacity=10, weight=1)
        return g
    def mk_unbal_nx():
        g = nx.DiGraph()
        g.add_node(0, demand=-5)
        g.add_node(1, demand=3)
        g.add_edge(0, 1, capacity=10, weight=1)
        return g
    with _pytest.raises(fnx.NetworkXUnfeasible) as ef2:
        fnx.min_cost_flow(mk_unbal_fnx())
    with _pytest.raises(nx.NetworkXUnfeasible) as en2:
        nx.min_cost_flow(mk_unbal_nx())
    assert str(ef2.value) == str(en2.value) == "total node demand is not zero"


def test_add_edges_from_string_edge_raises_networkx_error():
    """br-r37-c1-icuqb (cycle 232): add_edges_from with a string
    'edge' fell through fnx's str/bytes short-circuit into Rust,
    which raised generic TypeError instead of nx's NetworkXError.
    Strings ARE iterable so nx treats them via the len() gate (a
    2- or 3-char str unpacks; anything else raises NetworkXError).

    Drop str/bytes from the short-circuit so the len() check applies.
    """
    import networkx as nx
    import pytest as _pytest

    # 'oops' has len 4 — should raise NetworkXError with nx wording.
    with _pytest.raises(fnx.NetworkXError) as ef:
        g = fnx.Graph()
        g.add_edges_from([(0, 1), 'oops'])
    with _pytest.raises(nx.NetworkXError) as en:
        g = nx.Graph()
        g.add_edges_from([(0, 1), 'oops'])
    assert str(ef.value) == str(en.value) == (
        "Edge tuple oops must be a 2-tuple or 3-tuple."
    )


def test_degree_nbunch_unhashable_raises_networkx_error():
    """br-r37-c1-tk51o (cycle 232): DegreeView.__call__(nbunch)
    silently filtered unhashable elements via the ``n in self._graph``
    short-circuit (returns False for unhashables). nx raises
    NetworkXError "Node X in sequence nbunch is not a valid node."

    Validate each nbunch element with hash() before the membership
    check so the error contract matches nx exactly.
    """
    import networkx as nx
    import pytest as _pytest

    with _pytest.raises(fnx.NetworkXError) as ef:
        list(fnx.path_graph(5).degree([[0]]))
    with _pytest.raises(nx.NetworkXError) as en:
        list(nx.path_graph(5).degree([[0]]))
    assert str(ef.value) == str(en.value) == (
        "Node [0] in sequence nbunch is not a valid node."
    )


def test_deepcopy_preserves_frozen_flag():
    """br-r37-c1-9e7gd (cycle 233): copy.deepcopy(g) stripped the
    frozen attribute because fnx's _graph_deepcopy constructs a fresh
    cls() instead of cloning instance __dict__. nx preserves it.

    Re-apply freeze on the new graph when the source was frozen.
    """
    import networkx as nx
    import copy

    # Frozen path
    g = fnx.path_graph(3)
    fnx.freeze(g)
    h = copy.deepcopy(g)
    assert fnx.is_frozen(h)
    assert h.frozen is True

    # Mutator is rejected post-deepcopy
    import pytest as _pytest
    with _pytest.raises(fnx.NetworkXError):
        h.add_node(99)

    # Round-trip parity vs nx
    gn = nx.path_graph(3)
    nx.freeze(gn)
    hn = copy.deepcopy(gn)
    assert nx.is_frozen(hn) == fnx.is_frozen(h)

    # Non-frozen graph stays non-frozen after deepcopy
    g2 = fnx.path_graph(3)
    h2 = copy.deepcopy(g2)
    assert not fnx.is_frozen(h2)


def test_pickle_and_shallow_copy_preserve_frozen_flag():
    """br-r37-c1-ish29 (cycle 233): sibling of 9e7gd. pickle and
    copy.copy also dropped the frozen flag because the Rust __reduce_ex__
    and the existing _graph_shallowcopy didn't propagate it.

    Wrap __reduce_ex__ at the Python layer to capture the frozen
    state and re-apply on reconstruction; add the same re-freeze
    branch to _graph_shallowcopy.
    """
    import networkx as nx
    import copy
    import pickle

    for cls_pair in [
        (fnx.Graph, nx.Graph),
        (fnx.DiGraph, nx.DiGraph),
        (fnx.MultiGraph, nx.MultiGraph),
        (fnx.MultiDiGraph, nx.MultiDiGraph),
    ]:
        fcls, ncls = cls_pair
        g = fcls()
        g.add_edge(0, 1)
        fnx.freeze(g)
        gn = ncls()
        gn.add_edge(0, 1)
        nx.freeze(gn)

        # Pickle round-trip
        h = pickle.loads(pickle.dumps(g))
        hn = pickle.loads(pickle.dumps(gn))
        assert fnx.is_frozen(h) is True, f"{fcls.__name__} pickle"
        assert fnx.is_frozen(h) == nx.is_frozen(hn)

        # Shallow copy
        s = copy.copy(g)
        sn = copy.copy(gn)
        assert fnx.is_frozen(s) is True, f"{fcls.__name__} shallow"
        assert fnx.is_frozen(s) == nx.is_frozen(sn)

    # Non-frozen graph stays unfrozen through pickle + shallow
    g = fnx.Graph([(0, 1)])
    assert not fnx.is_frozen(pickle.loads(pickle.dumps(g)))
    assert not fnx.is_frozen(copy.copy(g))


def test_all_triangles_iteration_order_matches_nx():
    """br-r37-c1-ulojb (cycle 238): all_triangles routed nbunch=None
    to the Rust binding which produced triangles with unsorted vertex
    tuples (e.g. ``(0, 12, 3)``) and a non-nx iteration order. nx's
    contract yields ``(u, v, w)`` with insertion-id order
    ``id(u) < id(v) < id(w)`` and iterates in nx-canonical order.

    Use the Python reference impl for both branches.
    """
    import networkx as nx

    # K4
    assert list(fnx.all_triangles(fnx.complete_graph(4))) == list(
        nx.all_triangles(nx.complete_graph(4))
    )

    # Karate club — 45 triangles, exact order should match
    assert list(fnx.all_triangles(fnx.karate_club_graph())) == list(
        nx.all_triangles(nx.karate_club_graph())
    )

    # nbunch path still works
    assert list(fnx.all_triangles(fnx.complete_graph(5), nbunch=[0])) == list(
        nx.all_triangles(nx.complete_graph(5), nbunch=[0])
    )


def test_all_shortest_paths_iteration_order_matches_nx():
    """br-r37-c1-o92w8 (cycle 239): the Rust ``_raw_all_shortest_paths``
    yields paths in adj-iteration order rather than nx's BFS-discovery
    order. karate(0->33) gave [(0,13,33),(0,19,33),(0,31,33),(0,8,33)]
    while nx yields [(0,8,33),(0,13,33),(0,19,33),(0,31,33)].

    Delegate the unweighted case (and the method='unweighted' branch)
    to nx so iteration order matches the documented contract.
    """
    import networkx as nx

    fp = [tuple(p) for p in fnx.all_shortest_paths(fnx.karate_club_graph(), 0, 33)]
    npp = [tuple(p) for p in nx.all_shortest_paths(nx.karate_club_graph(), 0, 33)]
    assert fp == npp == [(0, 8, 33), (0, 13, 33), (0, 19, 33), (0, 31, 33)]

    # C6 multiple paths
    fp2 = [tuple(p) for p in fnx.all_shortest_paths(fnx.cycle_graph(6), 0, 3)]
    np2 = [tuple(p) for p in nx.all_shortest_paths(nx.cycle_graph(6), 0, 3)]
    assert fp2 == np2

    # method='unweighted' explicit
    fp3 = [tuple(p) for p in fnx.all_shortest_paths(fnx.karate_club_graph(), 0, 33, method='unweighted')]
    np3 = [tuple(p) for p in nx.all_shortest_paths(nx.karate_club_graph(), 0, 33, method='unweighted')]
    assert fp3 == np3


def test_view_identity_is_cached_like_nx():
    """br-r37-c1-b3cnf (cycle 240): nx uses @cached_property for view
    accessors so ``g.nodes is g.nodes`` returns True. fnx created a
    fresh wrapper each access (False), breaking caller code that
    relies on view identity.

    Add per-instance caching slots so repeat access returns the same
    object across nodes, edges, adj, succ, pred for all 4 graph types.
    """
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        g = cls()
        g.add_edge(0, 1)
        assert g.nodes is g.nodes, f"{cls.__name__}.nodes not cached"
        assert g.edges is g.edges, f"{cls.__name__}.edges not cached"
        assert g.adj is g.adj, f"{cls.__name__}.adj not cached"
        if g.is_directed():
            assert g.succ is g.succ, f"{cls.__name__}.succ not cached"
            assert g.pred is g.pred, f"{cls.__name__}.pred not cached"

    # Live tracking: cached view still reflects mutations to underlying graph
    g = fnx.path_graph(3)
    nv = g.nodes
    g.add_node(99)
    assert 99 in nv
    assert g.nodes is nv

    # br-r37-c1-b3cnf follow-up: DegreeView (incl multi/digraph variants)
    g_path = fnx.path_graph(3)
    assert g_path.degree is g_path.degree

    mdg = fnx.MultiDiGraph()
    mdg.add_edge(0, 1)
    assert mdg.in_degree is mdg.in_degree
    assert mdg.out_degree is mdg.out_degree

    # DiGraph in/out_degree cached too
    dg = fnx.DiGraph([(0, 1)])
    assert dg.in_degree is dg.in_degree
    assert dg.out_degree is dg.out_degree

    # SubgraphView.edges cached
    g = fnx.path_graph(5)
    sg = g.subgraph([0, 1, 2])
    assert sg.edges is sg.edges
    assert sg.nodes is sg.nodes


def test_community_modularity_honors_weight():
    """br-r37-c1-nim1v (cycle 242): the Rust ``_raw_modularity`` ignored
    the ``weight`` kwarg — it returned the unweighted modularity even
    when the user asked for a weighted attribute.

    Repro: K4 with weights ``w(u,v)=abs(u-v)+1`` and partition
    ``[{0,1},{2,3}]``. nx returns -0.25 (weighted); fnx pre-fix returned
    -1/6 (the unweighted value).

    Fix in ``_modularity_backend_impl``: detect "actually weighted"
    inputs via ``_graph_has_nonunit_weight`` and delegate to nx's
    reference implementation.
    """
    import networkx as nx

    fg = fnx.complete_graph(4)
    for u, v in fg.edges():
        fg[u][v]['w'] = abs(u - v) + 1
    ng = nx.complete_graph(4)
    for u, v in ng.edges():
        ng[u][v]['w'] = abs(u - v) + 1

    partition = [{0, 1}, {2, 3}]
    f_mod = fnx.community.modularity(fg, partition, weight='w')
    n_mod = nx.community.modularity(ng, partition, weight='w')
    assert round(f_mod, 10) == round(n_mod, 10) == -0.25

    # Unweighted path still works
    f_un = fnx.community.modularity(fg, partition)
    n_un = nx.community.modularity(ng, partition)
    assert round(f_un, 10) == round(n_un, 10)

    # Resolution kwarg honored alongside weight
    f_res = fnx.community.modularity(fg, partition, weight='w', resolution=2)
    n_res = nx.community.modularity(ng, partition, weight='w', resolution=2)
    assert round(f_res, 10) == round(n_res, 10)


def test_cut_size_and_conductance_honor_weight():
    """br-r37-c1-2c8ed (cycle 242): sister of br-r37-c1-nim1v
    (modularity weight bug). The Rust ``_raw_cut_size`` ignores the
    weight kwarg too — returning the unweighted edge count instead
    of the weighted sum. conductance depends on cut_size and is
    broken transitively.

    Repro: K4 with weights ``w(u,v)=abs(u-v)+1``, S=[0,1].
    nx.cut_size returns 12 (sum: 3+4+2+3); fnx pre-fix returned 4.

    Fix: delegate to nx in ``cut_size`` and ``normalized_cut_size``
    when the input actually has a non-unit weight attribute.
    """
    import networkx as nx

    fg = fnx.complete_graph(4)
    for u, v in fg.edges():
        fg[u][v]['w'] = abs(u - v) + 1
    ng = nx.complete_graph(4)
    for u, v in ng.edges():
        ng[u][v]['w'] = abs(u - v) + 1

    assert fnx.cut_size(fg, [0, 1], weight='w') == nx.cut_size(ng, [0, 1], weight='w') == 12
    assert (
        round(fnx.conductance(fg, [0, 1], weight='w'), 10)
        == round(nx.conductance(ng, [0, 1], weight='w'), 10)
    )
    assert (
        round(fnx.normalized_cut_size(fg, [0, 1], weight='w'), 10)
        == round(nx.normalized_cut_size(ng, [0, 1], weight='w'), 10)
    )
    # Unweighted path still works
    assert fnx.cut_size(fg, [0, 1]) == nx.cut_size(ng, [0, 1]) == 4


def test_add_edges_from_rejects_none_endpoint():
    """br-r37-c1-83r45 (cycle 243): add_edge(None, 1) correctly raised
    ValueError("None cannot be a node") in both fnx and nx, but
    add_edges_from([(None, 1)]) silently accepted None on fnx while
    nx raised. Add the None-endpoint check to the add_edges_from
    wrapper to match nx's contract.
    """
    import networkx as nx
    import pytest as _pytest

    # nx behavior reference
    with _pytest.raises(ValueError) as en:
        g = nx.Graph()
        g.add_edges_from([(None, 1)])
    assert str(en.value) == "None cannot be a node"

    # fnx now matches
    with _pytest.raises(ValueError) as ef:
        g = fnx.Graph()
        g.add_edges_from([(None, 1)])
    assert str(ef.value) == "None cannot be a node"

    # Symmetric: second endpoint
    with _pytest.raises(ValueError):
        fnx.Graph().add_edges_from([(0, None)])

    # add_edge still rejects None
    with _pytest.raises(ValueError):
        fnx.Graph().add_edge(None, 1)


def test_add_weighted_edges_from_rejects_none_endpoint():
    """br-r37-c1-3qswx (cycle 243): sister of br-r37-c1-83r45.
    add_weighted_edges_from skipped the None-endpoint check just like
    add_edges_from did. Add the same guard.
    """
    import networkx as nx
    import pytest as _pytest

    with _pytest.raises(ValueError) as ef:
        fnx.Graph().add_weighted_edges_from([(None, 1, 5)])
    assert str(ef.value) == "None cannot be a node"

    with _pytest.raises(ValueError) as en:
        nx.Graph().add_weighted_edges_from([(None, 1, 5)])
    assert str(en.value) == "None cannot be a node"


def test_custom_python_attrs_survive_deepcopy_and_pickle():
    """br-r37-c1-8nz0x (cycle 233): nx preserves user-set instance
    attrs (``g.custom_attr = 'x'``) across deepcopy and pickle via its
    default __dict__ copy. fnx's _graph_deepcopy and the Rust
    __reduce_ex__ omitted them.

    Carry over any non-internal __dict__ keys (excluding the
    fnx-managed ``_fnx_*`` slots and the separately-handled ``frozen``
    flag) in both _graph_deepcopy and the reduce wrapper.
    """
    import networkx as nx
    import copy
    import pickle

    # deepcopy
    g = fnx.Graph([(0, 1)])
    g.custom_attr = "hello"
    g.numeric_attr = 42
    h = copy.deepcopy(g)
    assert h.custom_attr == "hello"
    assert h.numeric_attr == 42

    # nx parity
    gn = nx.Graph([(0, 1)])
    gn.custom_attr = "hello"
    hn = copy.deepcopy(gn)
    assert h.custom_attr == hn.custom_attr

    # pickle
    h2 = pickle.loads(pickle.dumps(g))
    assert h2.custom_attr == "hello"
    assert h2.numeric_attr == 42

    # Mutability of the custom attr in the copy doesn't affect original.
    g.custom_attr = "original"
    h3 = copy.deepcopy(g)
    h3.custom_attr = "mutated"
    assert g.custom_attr == "original"

    # SubgraphView pickle still works AND preserves frozen.
    g4 = fnx.path_graph(5)
    sg = g4.subgraph([0, 1, 2])
    h4 = pickle.loads(pickle.dumps(sg))
    assert type(h4) is fnx.Graph
    assert sorted(h4.nodes()) == [0, 1, 2]
    assert sorted(h4.edges()) == [(0, 1), (1, 2)]
    assert fnx.is_frozen(h4)


def test_shallow_copy_returns_independent_writable_graph():
    """br-r37-c1-4wqn9 (cycle 250): the previous _graph_shallowcopy
    overrode result._adj / result._node to point at self.adj / self._node
    while result was a fresh-empty Rust graph. h.add_edge(2, 3) wrote to
    h's own Rust storage, but h.edges read through the overridden view
    pointing at g — so the write was silently invisible.

    Fix: delegate to self.copy() so copy.copy(g) returns an independent
    writable copy (diverges from nx's shared-state contract, but is
    consistent with g.copy() and never silently drops writes).
    """
    import copy

    # Undirected: copy is independent, h's writes don't leak to g
    g = fnx.Graph([(0, 1)])
    h = copy.copy(g)
    h.add_edge(2, 3)
    assert sorted(h.edges()) == [(0, 1), (2, 3)]
    assert sorted(g.edges()) == [(0, 1)]

    # Frozen flag survives
    g2 = fnx.path_graph(3)
    fnx.freeze(g2)
    h2 = copy.copy(g2)
    assert fnx.is_frozen(h2)

    # DiGraph: independent + correct direction semantics
    g3 = fnx.DiGraph([(0, 1), (1, 2)])
    h3 = copy.copy(g3)
    h3.add_edge(2, 3)
    assert sorted(h3.edges()) == [(0, 1), (1, 2), (2, 3)]
    assert sorted(g3.edges()) == [(0, 1), (1, 2)]

    # MultiGraph: parallel edge keys still work after copy.copy
    g4 = fnx.MultiGraph()
    g4.add_edge(0, 1, key='a')
    h4 = copy.copy(g4)
    h4.add_edge(0, 1, key='b')
    assert h4.number_of_edges(0, 1) == 2
    assert g4.number_of_edges(0, 1) == 1

    # Graph + node attrs survive
    g5 = fnx.Graph()
    g5.graph['name'] = 'orig'
    g5.add_node(0, color='red')
    h5 = copy.copy(g5)
    assert h5.graph['name'] == 'orig'
    assert h5.nodes[0]['color'] == 'red'
