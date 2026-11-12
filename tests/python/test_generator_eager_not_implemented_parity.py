"""Regression: directed-only generator functions must raise
NetworkXNotImplemented EAGERLY (on the call), matching networkx's
@not_implemented_for decorator — not lazily on first iteration.

These functions were defined as generator functions in fnx, so the
``if not G.is_directed(): raise`` guard was deferred until the returned
generator was iterated. A drop-in caller wrapping only the *call* in
``try/except NetworkXNotImplemented`` would catch it in networkx but not in
fnx. They now do the type check eagerly and return an inner generator.
(br-r37-c1-scceager)
"""

import networkx as nx
import franken_networkx as fnx

import pytest

_FUNCS = [
    "strongly_connected_components",
    "weakly_connected_components",
    "kosaraju_strongly_connected_components",
    "antichains",
    "all_topological_sorts",
]


@pytest.mark.parametrize("name", _FUNCS)
def test_raises_eagerly_on_undirected_like_networkx(name):
    UG_nx = nx.Graph([(0, 1), (1, 2)])
    UG_fnx = fnx.Graph([(0, 1), (1, 2)])
    nx_fn, fnx_fn = getattr(nx, name), getattr(fnx, name)

    # networkx raises on the call (eager).
    with pytest.raises(nx.NetworkXNotImplemented):
        nx_fn(UG_nx)
    # fnx must too — the exception must surface from the call, before iteration.
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx_fn(UG_fnx)


@pytest.mark.parametrize("name", _FUNCS)
def test_directed_results_unchanged(name):
    edges = [(0, 1), (1, 2), (0, 2), (2, 3)]
    gn, gf = nx.DiGraph(edges), fnx.DiGraph(edges)
    nx_fn, fnx_fn = getattr(nx, name), getattr(fnx, name)

    def canon(gen):
        out = []
        for item in gen:
            out.append(tuple(item) if isinstance(item, (list, tuple)) else tuple(sorted(item)))
        return sorted(out)

    assert canon(fnx_fn(gf)) == canon(nx_fn(gn))


# Undirected-only generators: must raise NetworkXNotImplemented EAGERLY on a
# DiGraph (nx is @not_implemented_for('directed')).
_UNDIRECTED_ONLY = [
    "connected_components",
    "biconnected_components",
    "articulation_points",
    "bridges",
    "find_cliques",
    "enumerate_all_cliques",
]


@pytest.mark.parametrize("name", _UNDIRECTED_ONLY)
def test_undirected_only_raises_eagerly_on_directed(name):
    DG_nx = nx.DiGraph([(0, 1), (1, 2)])
    DG_fnx = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(nx, name)(DG_nx)
    with pytest.raises(fnx.NetworkXNotImplemented):
        getattr(fnx, name)(DG_fnx)


@pytest.mark.parametrize("name", _UNDIRECTED_ONLY)
def test_undirected_only_results_unchanged(name):
    edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 0)]
    gn, gf = nx.Graph(edges), fnx.Graph(edges)

    def canon(gen):
        out = []
        for item in gen:
            out.append(tuple(item) if isinstance(item, (list, tuple)) else tuple(sorted(item)))
        return sorted(out)

    assert canon(getattr(fnx, name)(gf)) == canon(getattr(nx, name)(gn))


# More undirected-only generators (link prediction, MST edges, chain
# decomposition, etc.) — eager NetworkXNotImplemented on a DiGraph.
_MORE_UNDIRECTED_ONLY = [
    "adamic_adar_index",
    "jaccard_coefficient",
    "preferential_attachment",
    "resource_allocation_index",
    "all_triangles",
    "biconnected_component_edges",
    "chain_decomposition",
    "find_cliques_recursive",
    "minimum_spanning_edges",
    "maximum_spanning_edges",
]


@pytest.mark.parametrize("name", _MORE_UNDIRECTED_ONLY)
def test_more_undirected_only_raises_eagerly_on_directed(name):
    DG_nx = nx.DiGraph([(0, 1), (1, 2)])
    DG_fnx = fnx.DiGraph([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(nx, name)(DG_nx)
    with pytest.raises(fnx.NetworkXNotImplemented):
        getattr(fnx, name)(DG_fnx)


# These also reject multigraphs eagerly (networkx @not_implemented_for both).
_MULTIGRAPH_REJECTORS = [
    "adamic_adar_index",
    "jaccard_coefficient",
    "preferential_attachment",
    "resource_allocation_index",
    "chain_decomposition",
]


@pytest.mark.parametrize("name", _MULTIGRAPH_REJECTORS)
def test_multigraph_rejectors_raise_eagerly(name):
    MG_nx = nx.MultiGraph([(0, 1), (0, 1)])
    MG_fnx = fnx.MultiGraph([(0, 1), (0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented):
        getattr(nx, name)(MG_nx)
    with pytest.raises(fnx.NetworkXNotImplemented):
        getattr(fnx, name)(MG_fnx)
    # MultiDiGraph reports the multigraph message (checked before directed), as nx.
    mdg_nx, mdg_fnx = nx.MultiDiGraph([(0, 1)]), fnx.MultiDiGraph([(0, 1)])
    with pytest.raises(nx.NetworkXNotImplemented, match="multigraph"):
        getattr(nx, name)(mdg_nx)
    with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph"):
        getattr(fnx, name)(mdg_fnx)


def test_cyclic_topological_still_raises_lazily():
    # The DAG requirement (NetworkXUnfeasible) is correctly lazy in nx — the
    # eager fix must not turn it eager.
    dc_nx = nx.DiGraph([(0, 1), (1, 0)])
    dc_fnx = fnx.DiGraph([(0, 1), (1, 0)])
    for fn_nx, fn_fnx in [(nx.all_topological_sorts, fnx.all_topological_sorts),
                          (nx.antichains, fnx.antichains)]:
        # call succeeds (no eager raise for a directed graph)
        gen_nx = fn_nx(dc_nx)
        gen_fnx = fn_fnx(dc_fnx)
        with pytest.raises(nx.NetworkXUnfeasible):
            list(gen_nx)
        with pytest.raises(fnx.NetworkXUnfeasible):
            list(gen_fnx)
