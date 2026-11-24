"""Differential + golden parity for ``chain_decomposition``.

``chain_decomposition(G[, root])`` yields the chains of a DFS-based
(Gabow) chain decomposition — each chain is a list of directed edges.
fnx replicates networkx's traversal exactly, so chain order AND edge
orientation are compared byte-for-byte. No dedicated test file existed.

br-r37-c1-xsvhs
"""

from __future__ import annotations

import random
from functools import wraps

import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(6, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


@pytest.mark.parametrize("seed", range(60))
def test_chain_decomposition_exact_match_networkx(seed):
    fg, ng = _pair(seed)
    fc = [list(c) for c in fnx.chain_decomposition(fg)]
    nc = [list(c) for c in nx.chain_decomposition(ng)]
    assert fc == nc


@pytest.mark.parametrize("seed", range(20))
def test_chain_decomposition_root_param_matches_networkx(seed):
    fg, ng = _pair(seed)
    if 0 not in [n for n in ng.nodes()]:
        pytest.skip("node 0 absent")
    fc = [list(c) for c in fnx.chain_decomposition(fg, root=0)]
    nc = [list(c) for c in nx.chain_decomposition(ng, root=0)]
    assert fc == nc


def test_chain_decomposition_goldens():
    # A single cycle decomposes into exactly one chain covering every edge.
    cyc = fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    ncyc = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    fchains = [list(c) for c in fnx.chain_decomposition(cyc)]
    assert len(fchains) == 1
    assert len(fchains[0]) == 4
    assert fchains == [list(c) for c in nx.chain_decomposition(ncyc)]
    # A tree has no chains (no cycles).
    tree = fnx.Graph([(0, 1), (1, 2), (2, 3)])
    assert list(fnx.chain_decomposition(tree)) == []


@pytest.mark.parametrize("input_kind", ["native", "foreign", "native_view", "foreign_view"])
@pytest.mark.parametrize("root", [None, 0, 5, "isolated"])
def test_chain_decomposition_preserves_loops_and_component_roots(input_kind, root):
    reference = nx.Graph()
    reference.add_nodes_from(["isolated", 0, 1, 2, 5, 6])
    reference.add_edges_from([(0, 1), (1, 2), (2, 0), (0, 0), (5, 6), (5, 5)])
    module = nx if input_kind.startswith("foreign") else fnx
    graph = module.Graph(reference)
    subject = module.subgraph_view(graph) if input_kind.endswith("view") else graph
    assert list(fnx.chain_decomposition(subject, root=root)) == list(
        nx.chain_decomposition(reference, root=root)
    )


@pytest.mark.parametrize("input_kind", ["native", "foreign", "native_view", "foreign_view"])
@pytest.mark.parametrize("mutation", ["add", "remove"])
def test_chain_decomposition_reads_mutations_before_first_advance(input_kind, mutation):
    def run(reference):
        module = nx if reference or input_kind.startswith("foreign") else fnx
        graph = module.path_graph(5)
        if mutation == "remove":
            graph.add_edge(0, 4)
        subject = module.subgraph_view(graph) if input_kind.endswith("view") else graph
        algorithm = nx.chain_decomposition if reference else fnx.chain_decomposition
        chains = algorithm(subject)
        if mutation == "add":
            graph.add_edge(0, 4)
        else:
            graph.remove_edge(0, 4)
        return list(chains)

    assert run(False) == run(True)


@pytest.mark.parametrize("input_module", [fnx, nx], ids=["native", "foreign"])
@pytest.mark.parametrize("filter_kind", ["node", "edge"])
def test_chain_decomposition_reads_changed_view_filters(input_module, filter_kind):
    def run(module, algorithm):
        graph = module.cycle_graph(5)
        visible = False
        if filter_kind == "node":
            view = module.subgraph_view(graph, filter_node=lambda node: visible or node != 4)
        else:
            view = module.subgraph_view(
                graph, filter_edge=lambda u, v: visible or {u, v} != {0, 4}
            )
        chains = algorithm(view)
        visible = True
        return list(chains)

    assert run(input_module, fnx.chain_decomposition) == run(nx, nx.chain_decomposition)


@pytest.mark.parametrize("input_module", [fnx, nx], ids=["native", "foreign"])
@pytest.mark.parametrize("mutation", ["add_root", "remove_root"])
def test_chain_decomposition_validates_root_when_advanced(input_module, mutation):
    def run(module, algorithm):
        graph = module.cycle_graph(4)
        root = 4 if mutation == "add_root" else 0
        chains = algorithm(graph, root=root)
        if mutation == "add_root":
            graph.add_edges_from([(0, 4), (2, 4)])
            return list(chains)
        graph.remove_node(root)
        with pytest.raises(module.NodeNotFound, match="Root node 0 is not in graph"):
            next(chains)
        return "missing root"

    assert run(input_module, fnx.chain_decomposition) == run(nx, nx.chain_decomposition)


@pytest.mark.parametrize("provider_kind", ["instance", "class", "subclass"])
@pytest.mark.parametrize("behavior", ["reverse", "mutate", "raise"])
@pytest.mark.parametrize("timing", ["before_call", "before_first"])
def test_chain_decomposition_preserves_live_neighbor_providers(
    provider_kind, behavior, timing, monkeypatch
):
    def run(module):
        graph_type = module.Graph
        if provider_kind == "subclass":
            class ProviderGraph(graph_type):
                pass

            graph_type = ProviderGraph
        graph = graph_type()
        graph.add_edges_from([(0, 1), (0, 2), (1, 3), (3, 2), (2, 4), (4, 5), (5, 0)])
        original = graph.neighbors
        events = []

        def neighbors(node):
            events.append(node)
            if behavior == "mutate" and node == 0:
                graph.add_edge(2, 5)
            if behavior == "raise" and node == 2:
                raise LookupError("neighbor provider stopped")
            nodes = original(node)
            return iter(reversed(list(nodes))) if behavior == "reverse" else nodes

        with monkeypatch.context() as patch:
            def install():
                if provider_kind == "instance":
                    patch.setattr(graph, "neighbors", neighbors)
                else:
                    patch.setattr(graph_type, "neighbors", lambda self, node: neighbors(node))

            if timing == "before_call":
                install()
            chains = module.chain_decomposition(graph)
            assert events == []
            if timing == "before_first":
                install()
            try:
                result = "chains", list(chains)
            except LookupError as error:
                result = "error", type(error), error.args
            return result, events

    assert run(fnx) == run(nx)


def test_chain_decomposition_class_getattribute_does_not_probe_instance_storage(monkeypatch):
    graph = fnx.cycle_graph(5)
    expected = list(nx.chain_decomposition(nx.cycle_graph(5)))
    original = fnx.Graph.__getattribute__

    def getattribute(self, name):
        if name == "__dict__":
            raise AssertionError("chain traversal must not probe instance storage")
        return original(self, name)

    monkeypatch.setattr(fnx.Graph, "__getattribute__", getattribute)
    assert list(fnx.chain_decomposition(graph)) == expected


@pytest.mark.parametrize("input_kind", ["native", "foreign", "native_view", "foreign_view"])
def test_chain_decomposition_finishes_dfs_before_yielding(input_kind):
    def run(reference):
        module = nx if reference or input_kind.startswith("foreign") else fnx
        graph = module.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
        subject = module.subgraph_view(graph) if input_kind.endswith("view") else graph
        algorithm = nx.chain_decomposition if reference else fnx.chain_decomposition
        chains = algorithm(subject)
        first = next(chains)
        graph.remove_edges_from(list(graph.edges()))
        return first, list(chains)

    assert run(False) == run(True)


def test_chain_decomposition_keeps_plain_graph_on_native_kernel(monkeypatch):
    graph = fnx.cycle_graph(6)
    original = fnx._fnx.chain_decomposition
    calls = []

    def native(subject, root):
        calls.append((subject, root))
        return original(subject, root)

    monkeypatch.setattr(fnx._fnx, "chain_decomposition", native)
    assert list(fnx.chain_decomposition(graph, root=0)) == list(
        nx.chain_decomposition(nx.cycle_graph(6), root=0)
    )
    assert len(calls) == 1 and calls[0][0] is graph and calls[0][1] == 0


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("view", [False, True])
def test_backend_chain_decomposition_keeps_original_live_graph(
    cached, automatic, view, monkeypatch
):
    from franken_networkx import backend as backend_module

    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)
    graph = nx.path_graph(5)
    subject = nx.subgraph_view(graph) if view else graph
    if cached:
        nx.relabel_nodes(subject, {}, backend="franken_networkx")
        assert subject.__networkx_cache__["backends"]["franken_networkx"]
    implementation = backend_module._SUPPORTED_ALGORITHMS["chain_decomposition"]
    inputs = []

    @wraps(implementation)
    def observed(*args, **kwargs):
        inputs.append(args[0] if args else kwargs["G"])
        return implementation(*args, **kwargs)

    monkeypatch.setitem(backend_module._SUPPORTED_ALGORITHMS, "chain_decomposition", observed)
    if automatic:
        monkeypatch.setattr(nx.config.backend_priority, "algos", ["franken_networkx"])
        chains = nx.chain_decomposition(G=subject)
    else:
        chains = nx.chain_decomposition(G=subject, backend="franken_networkx")
    graph.add_edge(0, 4)
    assert list(chains) == list(nx.chain_decomposition(subject, backend="networkx"))
    assert len(inputs) == 1 and inputs[0] is subject
    assert not subject.__networkx_cache__.get("backends")


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_backend_chain_decomposition_preserves_provider_callbacks(cached, failure, monkeypatch):
    monkeypatch.setattr(nx.config, "cache_converted_graphs", True)

    def run(backend):
        graph = nx.path_graph(5)
        if cached and backend == "franken_networkx":
            nx.relabel_nodes(graph, {}, backend=backend)
        original = graph.neighbors
        events = []

        def neighbors(node):
            events.append(node)
            if node == 0:
                graph.add_edge(0, 4)
                if failure:
                    raise LookupError("chain reader stopped")
            return original(node)

        graph.neighbors = neighbors
        chains = nx.chain_decomposition(graph, backend=backend)
        assert events == []
        try:
            result = "chains", list(chains)
        except LookupError as error:
            result = "error", type(error), error.args
        if backend == "franken_networkx":
            assert not graph.__networkx_cache__.get("backends")
        return result, events

    assert run("franken_networkx") == run("networkx")


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_backend_chain_decomposition_rejects_unsupported_graphs_eagerly(cls_name):
    graph = getattr(nx, cls_name)([(0, 1)])
    message = "multigraph" if graph.is_multigraph() else "directed"
    with pytest.raises(nx.NetworkXNotImplemented, match=message):
        nx.chain_decomposition(graph, backend="franken_networkx")
