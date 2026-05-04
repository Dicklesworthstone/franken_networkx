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
    assert type(fv) is type(nv)  # both int, not float


def test_transitivity_returns_float_on_graph_with_triangles():
    G_nx = nx.complete_graph(4)
    G_fnx = fnx.complete_graph(4)
    nv, fv = nx.transitivity(G_nx), fnx.transitivity(G_fnx)
    assert nv == fv == 1.0
    assert type(fv) is type(nv)  # both float


# --- wiener_index (br-r37-c1-t26b4) ---------------------------------

def test_wiener_index_directed_returns_int():
    """Directed branch: nx returns ``total`` un-divided (int)."""
    G_nx = nx.DiGraph([(0, 1), (1, 2), (2, 0)])
    G_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    nv, fv = nx.wiener_index(G_nx), fnx.wiener_index(G_fnx)
    assert nv == fv
    assert type(fv) is type(nv) is int


def test_wiener_index_undirected_returns_float():
    """Undirected branch: nx returns ``total / 2`` (float)."""
    G_nx = nx.path_graph(5)
    G_fnx = fnx.path_graph(5)
    nv, fv = nx.wiener_index(G_nx), fnx.wiener_index(G_fnx)
    assert nv == fv
    assert type(fv) is type(nv) is float


# --- barycenter (br-r37-c1-pooue) -----------------------------------

def test_barycenter_directed_disconnected_raises_no_path():
    """Non-strongly-connected DiGraph: NetworkXNoPath in both libs."""
    G_nx = nx.DiGraph([(0, 1), (1, 2), (2, 3)])
    G_fnx = fnx.DiGraph([(0, 1), (1, 2), (2, 3)])
    with pytest.raises(nx.NetworkXNoPath):
        nx.barycenter(G_nx)
    with pytest.raises(nx.NetworkXNoPath):
        fnx.barycenter(G_fnx)


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
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_exception_type_parity(name, builder, call, exc):
    """Drop-in code that catches specific nx.NetworkX* subclasses
    must catch the same class on fnx. ValueError-vs-NetworkXError is
    a real divergence."""
    G_nx = builder(nx)
    G_fnx = builder(fnx)
    with pytest.raises(exc):
        call(nx, G_nx)
    with pytest.raises(exc):
        call(fnx, G_fnx)
