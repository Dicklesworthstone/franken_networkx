"""br-r37-c1-sg4dw: nx.scale_free_graph(initial_graph=fnx_multidigraph)
must accept fnx graphs as initial_graph instead of raising
NetworkXError("initial_graph must be a MultiDiGraph.").

nx.generators.directed.scale_free_graph is decorated as
``@_dispatchable(graphs=None, returns_graph=True)`` so its
``initial_graph`` argument bypasses the backend dispatcher entirely
and is checked with a hard ``isinstance(initial_graph, nx.MultiDiGraph)``
guard. fnx.MultiDiGraph is not a subclass of nx.MultiDiGraph, so
without an explicit conversion the call raises.

fnx patches the function at import to convert fnx multidigraph inputs
to nx.MultiDiGraph before delegating.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_nx_scale_free_graph_accepts_fnx_multidigraph():
    fmd = fnx.MultiDiGraph()
    fmd.add_edges_from([(0, 1), (1, 2)])
    g = nx.scale_free_graph(10, initial_graph=fmd, seed=42)
    assert isinstance(g, nx.MultiDiGraph)
    assert g.number_of_nodes() == 10


@needs_nx
def test_nx_scale_free_graph_no_initial_graph_regression():
    """Without ``initial_graph`` the call still works (uses the
    default 3-cycle inside scale_free_graph)."""
    g = nx.scale_free_graph(10, seed=42)
    assert isinstance(g, nx.MultiDiGraph)
    assert g.number_of_nodes() == 10


@needs_nx
def test_nx_scale_free_graph_nx_initial_graph_regression():
    """An nx.MultiDiGraph initial_graph must continue to work
    unchanged after the patch."""
    nmd = nx.MultiDiGraph()
    nmd.add_edges_from([(0, 1), (1, 2)])
    g = nx.scale_free_graph(10, initial_graph=nmd, seed=42)
    assert isinstance(g, nx.MultiDiGraph)
    assert g.number_of_nodes() == 10


@needs_nx
def test_scale_free_graph_alias_paths_share_patched_object():
    """All three exposed references to scale_free_graph in nx point
    to the same patched callable."""
    assert nx.scale_free_graph is nx.generators.scale_free_graph
    assert nx.scale_free_graph is nx.generators.directed.scale_free_graph


@needs_nx
def test_nx_scale_free_graph_with_fnx_digraph_also_works():
    """Edge case: pass an fnx.DiGraph (not MultiDiGraph) — the patch
    should still convert it (via the MultiDiGraph promotion step in
    the wrapper) and let the call succeed."""
    fdg = fnx.DiGraph()
    fdg.add_edges_from([(0, 1), (1, 2), (2, 0)])
    g = nx.scale_free_graph(10, initial_graph=fdg, seed=42)
    assert isinstance(g, nx.MultiDiGraph)
    assert g.number_of_nodes() == 10
