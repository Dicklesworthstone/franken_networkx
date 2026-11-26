"""Structural bounds and value-only solves for public connectivity queries."""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("case,node_cut,edge_cut", [
    ("path", 1, 1), ("cycle", 2, 2), ("bowtie", 1, 2),
    ("barbell", 1, 1), ("loop", 2, 2), ("disconnected", 0, 0),
])
def test_low_degree_global_connectivity_needs_no_flow(monkeypatch, case, node_cut, edge_cut):
    if case == "path":
        reference = nx.path_graph(64)
    elif case in ("cycle", "loop", "disconnected"):
        reference = nx.cycle_graph(12)
        if case == "loop":
            reference.add_edge(0, 0)
        if case == "disconnected":
            reference.add_node(20)
    elif case == "bowtie":
        reference = nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
    else:
        reference = nx.barbell_graph(3, 0)
    graph = fnx.Graph()
    graph.add_nodes_from(reference)
    graph.add_edges_from(reference.edges)

    def unexpected(*args, **kwargs):
        pytest.fail("a proved connectivity bound built an auxiliary flow graph")

    monkeypatch.setattr(fnx, "_build_auxiliary_node_connectivity_fast", unexpected)
    monkeypatch.setattr(fnx, "_build_auxiliary_edge_connectivity_fast", unexpected)
    assert fnx.node_connectivity(graph) == nx.node_connectivity(reference) == node_cut
    assert fnx.edge_connectivity(graph) == nx.edge_connectivity(reference) == edge_cut


@pytest.mark.parametrize("name", ["node_connectivity", "edge_connectivity"])
@pytest.mark.parametrize("local", [False, True])
def test_flows_needed_for_higher_connectivity_only_compute_values(monkeypatch, name, local):
    reference = nx.complete_bipartite_graph(3, 3)
    graph = fnx.Graph()
    graph.add_edges_from(reference.edges)
    solve_value = fnx._minimum_cut_value_raw
    calls = []

    def value(*args, **kwargs):
        calls.append(1)
        return solve_value(*args, **kwargs)

    def partition(*args, **kwargs):
        pytest.fail("a scalar connectivity query built a residual cut partition")

    monkeypatch.setattr(fnx, "_minimum_cut_value_raw", value)
    monkeypatch.setattr(fnx, "_minimum_cut_raw", partition)
    terminals = (0, 1) if local else ()
    assert getattr(fnx, name)(graph, *terminals) == getattr(nx, name)(reference, *terminals) == 3
    assert calls


@pytest.mark.parametrize("kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("name", ["edge_connectivity", "node_connectivity"])
def test_singletons_loops_and_parallel_edges_keep_reference_conventions(kind, name):
    for shape in ("empty", "isolate", "loop", "complete"):
        graphs = []
        for module in (nx, fnx):
            graph = getattr(module, kind)()
            if shape == "isolate":
                graph.add_node(0)
            elif shape == "loop":
                graph.add_edge(0, 0)
            elif shape == "complete":
                for u in range(3):
                    for v in range(3):
                        graph.add_edge(u, v)
                        graph.add_edge(u, v)
            graphs.append(graph)

        def run(module, graph, terminals):
            try:
                return getattr(module, name)(graph, *terminals)
            except module.NetworkXException as exc:
                return type(exc).__name__, exc.args

        for terminals in ([(), (0, 2)] if shape == "complete" else [()]):
            assert run(fnx, graphs[1], terminals) == run(nx, graphs[0], terminals)


@pytest.mark.parametrize("name", ["edge_connectivity", "node_connectivity"])
def test_explicit_flow_solver_runs_on_a_path(name):
    def run(module):
        calls = []
        graph = module.path_graph(8)

        def solve(*args, **kwargs):
            calls.append(kwargs["value_only"])
            return module.algorithms.flow.edmonds_karp(*args, **kwargs)

        kwargs = {"flow_func": solve}
        if name == "edge_connectivity":
            kwargs["cutoff"] = 1
        return getattr(module, name)(graph, 0, 7, **kwargs), calls

    expected, calls = run(nx)
    assert calls
    assert run(fnx) == (expected, calls)


@pytest.mark.parametrize("order", [3, 8, 32])
def test_complete_graph_connectivity_uses_its_degree_bound(monkeypatch, order):
    reference = nx.complete_graph(order)
    graph = fnx.Graph()
    graph.add_edges_from(reference.edges)
    expected_node = nx.node_connectivity(reference)
    expected_edge = nx.edge_connectivity(reference)

    def unexpected(*args, **kwargs):
        pytest.fail("a complete graph scanned candidate cuts")

    monkeypatch.setattr(fnx, "_build_auxiliary_node_connectivity_fast", unexpected)
    monkeypatch.setattr(fnx, "_build_auxiliary_edge_connectivity_fast", unexpected)
    monkeypatch.setattr(fnx, "dominating_set", unexpected)
    assert fnx.node_connectivity(graph) == expected_node == order - 1
    assert fnx.edge_connectivity(graph) == expected_edge == order - 1


def test_loops_cannot_certify_complete_graph_connectivity():
    # Each vertex has degree n - 1, but its loop replaces two distinct neighbors.
    reference = nx.cycle_graph(5)
    reference.add_edges_from((v, v) for v in reference)
    graph = fnx.Graph()
    graph.add_edges_from(reference.edges)
    assert fnx.node_connectivity(graph) == nx.node_connectivity(reference) == 2
    assert fnx.edge_connectivity(graph) == nx.edge_connectivity(reference) == 2


@pytest.mark.parametrize("name", ["node_connectivity", "edge_connectivity"])
def test_dense_components_stop_after_a_unit_cut(monkeypatch, name):
    # A dominating set needs a representative from every clique. Each clique
    # is separated from the next by a single edge at its last vertex.
    reference = nx.Graph()
    for start in range(0, 20, 5):
        reference.add_edges_from(nx.complete_graph(range(start, start + 5)).edges)
        if start:
            reference.add_edge(start - 1, start + 4)
    graph = fnx.Graph()
    graph.add_edges_from(reference.edges)
    solve = fnx._minimum_cut_value_raw
    values = []

    def observe(*args, **kwargs):
        value = solve(*args, **kwargs)
        values.append(value)
        return value

    monkeypatch.setattr(fnx, "_minimum_cut_value_raw", observe)
    assert getattr(fnx, name)(graph) == getattr(nx, name)(reference) == 1
    assert values == [1]
