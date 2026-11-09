"""``franken_networkx.connectivity`` routes to fnx-native connectivity fns.

``from networkx.algorithms.connectivity import *`` left node/edge
connectivity, cuts, disjoint paths, k-edge components and stoer_wagner
bound to networkx's implementations instead of fnx's native versions
(``node_connectivity`` even carries the br-r37-c1-cqlms / ebd8d local
connectivity fixes). These now route to the fnx top-level functions.

br-r37-c1-2qsqf
"""

from __future__ import annotations

import importlib.util
import inspect
import math
import sys
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import franken_networkx as fnx
import networkx as nx
import pytest
from franken_networkx import connectivity as fnx_conn

_NAMES = [
    "all_node_cuts", "all_pairs_node_connectivity", "average_node_connectivity",
    "edge_connectivity", "edge_disjoint_paths", "is_k_edge_connected",
    "k_components", "k_edge_augmentation", "k_edge_components", "k_edge_subgraphs",
    "minimum_edge_cut", "minimum_node_cut", "node_connectivity",
    "node_disjoint_paths", "stoer_wagner",
]


@lru_cache(maxsize=1)
def _legacy_networkx():
    module_name = "franken_networkx_legacy_networkx_connectivity_surface"
    legacy_init = (
        Path(__file__).resolve().parents[2]
        / "legacy_networkx_code"
        / "networkx"
        / "networkx"
        / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, legacy_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", _NAMES)
def test_connectivity_fn_is_not_networkx_version(name):
    fn = getattr(fnx_conn, name)
    if hasattr(nx, name):
        assert fn is not getattr(nx, name)


@pytest.mark.parametrize("name", _NAMES)
def test_connectivity_module_signatures_match_legacy_networkx(name):
    legacy = _legacy_networkx()
    assert str(inspect.signature(getattr(fnx_conn, name))) == str(
        inspect.signature(getattr(legacy.algorithms.connectivity, name))
    )


def test_connectivity_values_match_networkx():
    g = fnx.complete_graph(5)
    ng = nx.complete_graph(5)
    assert fnx_conn.node_connectivity(g) == nx.node_connectivity(ng)
    assert fnx_conn.edge_connectivity(g) == nx.edge_connectivity(ng)
    # The cqlms/ebd8d local-connectivity fixes flow through the namespace too:
    # adjacent pair in K5 has local node connectivity 4 (not 0).
    assert fnx_conn.node_connectivity(g, 0, 4) == 4
    assert fnx_conn.node_connectivity(g, 0, 4) == nx.node_connectivity(ng, 0, 4)
    assert fnx_conn.stoer_wagner(g)[0] == nx.stoer_wagner(ng)[0]
    assert len(list(fnx_conn.edge_disjoint_paths(g, 0, 4))) == (
        len(list(nx.edge_disjoint_paths(ng, 0, 4)))
    )


@pytest.mark.parametrize("directed", [False, True])
def test_default_flow_function_paths_match_networkx(directed):
    """flow_func=None with a cutoff, an auxiliary digraph or a residual network
    takes networkx's default, edmonds_karp; it was looked up at fnx's top level,
    which neither library exports it from, so every such call raised
    AttributeError (br-r37-c1-7jhpr)."""
    from networkx.algorithms import connectivity as nx_conn
    from networkx.algorithms.flow import build_residual_network as nx_residual

    from franken_networkx.flow import build_residual_network as fnx_residual

    edges = [(0, 1), (0, 2), (1, 2), (1, 3), (2, 4), (3, 4), (3, 5), (4, 5), (0, 5)]
    fg = (fnx.DiGraph if directed else fnx.Graph)(edges)
    ng = (nx.DiGraph if directed else nx.Graph)(edges)
    f_node_aux = fnx_conn.build_auxiliary_node_connectivity(fg)
    n_node_aux = nx_conn.build_auxiliary_node_connectivity(ng)
    f_edge_aux = fnx_conn.build_auxiliary_edge_connectivity(fg)
    n_edge_aux = nx_conn.build_auxiliary_edge_connectivity(ng)
    for cutoff in (1, 2, None):
        assert fnx_conn.local_node_connectivity(fg, 0, 5, cutoff=cutoff, auxiliary=f_node_aux) == (
            nx_conn.local_node_connectivity(ng, 0, 5, cutoff=cutoff, auxiliary=n_node_aux)
        )
        assert fnx_conn.local_edge_connectivity(fg, 0, 5, cutoff=cutoff, auxiliary=f_edge_aux) == (
            nx_conn.local_edge_connectivity(ng, 0, 5, cutoff=cutoff, auxiliary=n_edge_aux)
        )
    f_cut = fnx_conn.minimum_st_edge_cut(
        fg, 0, 5, auxiliary=f_edge_aux, residual=fnx_residual(f_edge_aux, "capacity")
    )
    n_cut = nx_conn.minimum_st_edge_cut(
        ng, 0, 5, auxiliary=n_edge_aux, residual=nx_residual(n_edge_aux, "capacity")
    )
    assert len(f_cut) == len(n_cut)
    cut_graph = fg.copy()
    cut_graph.remove_edges_from(f_cut)
    assert not fnx.has_path(cut_graph, 0, 5)
    with pytest.raises(KeyError):
        fnx_conn.local_node_connectivity(fg, 99, 5, cutoff=1)


def _connectivity_pair(graph_type):
    nodes = [1024 * i for i in range(6)]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0),
        (0, 2), (0, 3), (1, 3), (2, 4), (3, 5),
    ]
    graphs = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(nodes)
        graph.add_edges_from((nodes[u], nodes[v], {"capacity": 23}) for u, v in edges)
        if graph.is_multigraph():
            graph.add_edge(nodes[0], nodes[1], capacity=37)
        graphs.append(graph)
    return graphs


def _forbid_connectivity_delegation(*args, **kwargs):
    raise AssertionError("connectivity query delegated to NetworkX")


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["edge_connectivity", "minimum_edge_cut", "minimum_node_cut"])
@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize(
    "algorithm", ["edmonds_karp", "dinitz", "shortest_augmenting_path", "preflow_push"]
)
def test_connectivity_owned_solver_routes_match_networkx(
    monkeypatch, graph_type, name, local, algorithm
):
    from networkx.algorithms import connectivity as nx_conn
    from networkx.algorithms import flow as nx_flow
    from franken_networkx import backend as fnx_backend
    from franken_networkx import flow as fnx_flow

    fg, ng = _connectivity_pair(graph_type)
    kwargs = {"s": 0, "t": 4096} if local else {}
    expected = getattr(nx, name)(ng, flow_func=getattr(nx_flow, algorithm), **kwargs)
    for module in (nx, nx_conn, nx_conn.connectivity, nx_conn.cuts):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, _forbid_connectivity_delegation)
    monkeypatch.setattr(fnx_backend, "_fnx_to_nx", _forbid_connectivity_delegation)

    actual = getattr(fnx_conn, name)(fg, flow_func=getattr(fnx_flow, algorithm), **kwargs)
    assert actual == expected
    assert type(actual) is type(expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize("cutoff", [-1, 0, Fraction(1, 2), Fraction(3, 2), 2, math.inf, math.nan])
def test_connectivity_owned_cutoff_keeps_exact_value_and_local_flow(
    monkeypatch, graph_type, local, cutoff
):
    from networkx.algorithms import connectivity as nx_conn

    fg, ng = _connectivity_pair(graph_type)
    kwargs = {"s": 0, "t": 4096} if local else {}
    expected = nx.edge_connectivity(ng, cutoff=cutoff, **kwargs)
    monkeypatch.setattr(
        nx_conn.connectivity, "edge_connectivity", _forbid_connectivity_delegation
    )
    actual = fnx.edge_connectivity(fg, cutoff=cutoff, **kwargs)
    if isinstance(expected, float) and math.isnan(expected):
        assert math.isnan(actual)
    else:
        assert actual == expected
    assert type(actual) is type(expected)


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["edge_connectivity", "minimum_edge_cut", "minimum_node_cut"])
@pytest.mark.parametrize("local", [False, True])
def test_connectivity_solver_callback_schedule_and_shared_residual(graph_type, name, local):
    """Check callback options, graph snapshots, residual order and state reuse."""
    from networkx.algorithms.flow import edmonds_karp

    outcomes = []
    for module, graph in zip((fnx, nx), _connectivity_pair(graph_type)):
        run_flow = fnx.flow.edmonds_karp if module is fnx else edmonds_karp
        calls = []
        auxiliaries = []
        residuals = []
        returned_residuals = []

        class Solver:
            def __bool__(self):
                return False

            def __call__(self, auxiliary, source, target, **kwargs):
                residual = kwargs["residual"]
                calls.append((
                    source,
                    target,
                    tuple((key, value) for key, value in kwargs.items() if key != "residual"),
                    list(auxiliary.nodes(data=True)),
                    list(auxiliary.edges(data=True)),
                    list(residual.edges()) if residual is not None else None,
                    residual.graph.get("callback_visits", 0) if residual is not None else None,
                ))
                auxiliaries.append(auxiliary)
                residuals.append(residual)
                result = run_flow(auxiliary, source, target, **kwargs)
                result.graph["callback_visits"] = result.graph.get("callback_visits", 0) + 1
                returned_residuals.append(result)
                return result

        kwargs = {"s": 0, "t": 4096} if local else {}
        result = getattr(module, name)(graph, flow_func=Solver(), **kwargs)
        assert calls
        assert all(auxiliary is auxiliaries[0] for auxiliary in auxiliaries)
        assert all(residual is residuals[0] for residual in residuals)
        outcomes.append((result, calls, [list(r.edges()) for r in returned_residuals]))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("name", ["local_node_connectivity", "local_edge_connectivity"])
@pytest.mark.parametrize("solver_name", ["preflow_push", "shortest_augmenting_path", "custom"])
def test_connectivity_callback_names_do_not_select_builtin_options(name, solver_name):
    from networkx.algorithms import connectivity as nx_conn
    from networkx.algorithms.flow import edmonds_karp

    outcomes = []
    for module, graph in zip((fnx_conn, nx_conn), _connectivity_pair("Graph")):
        calls = []

        def solver(auxiliary, source, target, **kwargs):
            calls.append(tuple((key, value) for key, value in kwargs.items() if key != "residual"))
            return edmonds_karp(auxiliary, source, target, **kwargs)

        solver.__name__ = solver_name
        value = getattr(module, name)(graph, 0, 4096, flow_func=solver, cutoff=Fraction(1, 2))
        outcomes.append((value, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
def test_connectivity_edge_cut_keeps_auxiliary_snapshot_during_solver_mutation(monkeypatch, graph_type):
    from networkx.algorithms.flow import edmonds_karp
    from franken_networkx import backend as fnx_backend

    outcomes = []
    monkeypatch.setattr(fnx_backend, "_fnx_to_nx", _forbid_connectivity_delegation)
    for module in (fnx, nx):
        graph = getattr(module, graph_type)([(0, 1), (1, 2), (2, 3)])
        run_flow = fnx.flow.edmonds_karp if module is fnx else edmonds_karp

        def solver(auxiliary, source, target, **kwargs):
            graph.add_edge(0, 3, callback=True)
            return run_flow(auxiliary, source, target, **kwargs)

        result = module.minimum_edge_cut(graph, 0, 3, flow_func=solver)
        assert graph.has_edge(0, 3)
        assert (0, 3) not in result
        outcomes.append(result)
    assert outcomes[0] == outcomes[1]


def test_connectivity_cut_reads_residual_after_removal_hooks():
    """A callback-owned residual may change its topology when arcs are removed."""
    from networkx.algorithms import connectivity as nx_conn
    from networkx.algorithms.flow import edmonds_karp

    outcomes = []
    for module in (fnx_conn, nx_conn):
        events = []

        class Residual(nx.DiGraph):
            def remove_edges_from(self, edges):
                edges = list(edges)
                events.append(("remove", [(u, v) for u, v, _ in edges]))
                super().remove_edges_from(edges)
                # The newly inserted arc is saturated too. Reachability must
                # inspect the residual after this hook, not re-filter it.
                self.add_edge(0, 3, capacity=1, flow=1)

        def solver(auxiliary, source, target, **kwargs):
            return Residual(edmonds_karp(auxiliary, source, target, **kwargs))

        graph = nx.path_graph(4)
        cut = module.minimum_st_edge_cut(graph, 0, 3, flow_func=solver)
        outcomes.append((cut, events))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == set()


@pytest.mark.parametrize("name", ["minimum_st_edge_cut", "minimum_st_node_cut"])
def test_connectivity_cut_requires_flow_value_after_restoring_residual(name):
    from networkx.algorithms import connectivity as nx_conn
    from networkx.algorithms.flow import edmonds_karp

    for module in (fnx_conn, nx_conn):
        returned = []

        def solver(auxiliary, source, target, **kwargs):
            residual = edmonds_karp(auxiliary, source, target, **kwargs)
            returned.append((residual, set(residual.edges())))
            del residual.graph["flow_value"]
            return residual

        with pytest.raises(KeyError, match="flow_value"):
            getattr(module, name)(nx.path_graph(3), 0, 2, flow_func=solver)
        residual, edges = returned[0]
        assert set(residual.edges()) == edges


@pytest.mark.parametrize("name", ["minimum_st_edge_cut", "minimum_st_node_cut"])
@pytest.mark.parametrize("empty", [False, True])
def test_connectivity_cut_residual_missing_sink_reports_reverse_source(name, empty):
    from networkx.algorithms import connectivity as nx_conn

    outcomes = []
    for module in (fnx_conn, nx_conn):
        residual = nx.DiGraph()
        if not empty:
            residual.add_edge(0, 1, capacity=1, flow=1)
        residual.graph["flow_value"] = 1

        def solver(*args, **kwargs):
            return residual

        try:
            getattr(module, name)(nx.path_graph(3), 0, 2, flow_func=solver)
        except Exception as exc:
            outcomes.append((type(exc).__name__, str(exc), list(residual.edges())))
        else:
            pytest.fail("residual without a sink was accepted")
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == "NodeNotFound"
    assert outcomes[0][1].startswith("Source ")


@pytest.mark.parametrize("name", ["edge_connectivity", "minimum_edge_cut", "minimum_node_cut"])
@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize(
    "nodes,edges,kwargs",
    [
        ([], [], {}),
        ([], [], {"s": 0}),
        ([], [], {"s": 0, "t": 1}),
        ([0], [], {"s": 0, "t": 0}),
        ([0, 1], [], {}),
        ([0, 1], [], {"s": 0, "t": 7}),
    ],
)
def test_connectivity_solver_validation_precedence(name, graph_type, nodes, edges, kwargs):
    from networkx.algorithms.flow import edmonds_karp

    outcomes = []
    for module in (fnx, nx):
        graph = getattr(module, graph_type)()
        graph.add_nodes_from(nodes)
        graph.add_edges_from(edges)
        try:
            result = getattr(module, name)(graph, flow_func=edmonds_karp, **kwargs)
        except Exception as exc:
            outcomes.append((type(exc).__name__, str(exc)))
        else:
            outcomes.append(("value", result))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize(
    "name", ["node_connectivity", "all_pairs_node_connectivity", "average_node_connectivity"]
)
def test_custom_node_connectivity_uses_original_public_graph(directed, name):
    graph_type = nx.DiGraph if directed else nx.Graph
    outcomes = []
    for module in (nx, fnx):
        class PublicGraph(graph_type):
            @property
            def nodes(self):
                raise AssertionError("node connectivity exported input node attributes")

        graph = PublicGraph()
        graph.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)])
        if directed:
            graph.add_edges_from([(1, 0), (2, 1), (3, 2), (0, 3), (2, 0)])
        calls = []
        auxiliary_ids = set()
        residual_ids = set()

        def solver(auxiliary, source, target, **kwargs):
            auxiliary_ids.add(id(auxiliary))
            residual_ids.add(id(kwargs["residual"]))
            calls.append((source, target, kwargs.get("cutoff")))
            return nx.algorithms.flow.edmonds_karp(
                auxiliary, source, target, backend="networkx", **kwargs
            )

        options = {"backend": "networkx"} if module is nx else {}
        result = getattr(module, name)(graph, flow_func=solver, **options)
        assert len(auxiliary_ids) == 1
        assert len(residual_ids) == 1
        outcomes.append((result, calls))
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize("directed", [False, True])
def test_local_node_connectivity_uses_original_public_graph(directed):
    graph_type = nx.DiGraph if directed else nx.Graph

    class PublicGraph(graph_type):
        @property
        def nodes(self):
            raise AssertionError("local node connectivity exported input attributes")

    graph = PublicGraph([(0, 1), (1, 2), (0, 3), (3, 2)])
    expected = nx.node_connectivity(
        graph, 0, 2, flow_func=nx.algorithms.flow.edmonds_karp, backend="networkx"
    )
    actual = fnx.node_connectivity(graph, 0, 2, flow_func=fnx.flow.edmonds_karp)
    assert actual == expected == 2
