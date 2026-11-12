"""br-r37-c1-ja61l: regression tests for quotient_graph default node-data."""

from __future__ import annotations

import inspect

import pytest

import franken_networkx as fnx
import franken_networkx.minors as fnx_minors

try:
    import networkx as nx

    HAS_NX = True
except ImportError:
    HAS_NX = False


needs_nx = pytest.mark.skipif(not HAS_NX, reason="networkx not installed")


@needs_nx
def test_minors_quotient_graph_signature_matches_networkx():
    fnx_contract = tuple(inspect.signature(fnx_minors.quotient_graph).parameters.items())
    nx_contract = tuple(
        inspect.signature(nx.algorithms.minors.quotient_graph).parameters.items()
    )
    if fnx_contract != nx_contract:
        pytest.fail(f"fnx {fnx_contract!r} != nx {nx_contract!r}")


@needs_nx
def test_minors_quotient_graph_default_relabel_matches_networkx():
    partition = [{0, 1}, {2, 3}]

    result = fnx_minors.quotient_graph(fnx.path_graph(4), partition)
    expected = nx.algorithms.minors.quotient_graph(nx.path_graph(4), partition)

    assert set(result.nodes()) == set(expected.nodes())
    assert all(isinstance(node, frozenset) for node in result.nodes())


@needs_nx
def test_minors_quotient_graph_accepts_weight_keyword():
    graph = fnx.Graph()
    graph.add_edges_from([(0, 2), (1, 3)])
    expected_graph = nx.Graph()
    expected_graph.add_edges_from([(0, 2), (1, 3)])
    partition = [{0, 1}, {2, 3}]

    result = fnx_minors.quotient_graph(graph, partition, weight="capacity")
    expected = nx.algorithms.minors.quotient_graph(
        expected_graph, partition, weight="capacity"
    )

    assert sorted(result.edges(data=True), key=repr) == sorted(
        expected.edges(data=True), key=repr
    )


@needs_nx
def test_quotient_graph_default_node_data_matches_nx():
    """When node_data is not provided, both fnx and nx attach
    graph/nnodes/nedges/density to each block node."""
    fg = fnx.path_graph(4)
    ng = nx.path_graph(4)
    rf = fnx.quotient_graph(fg, [{0, 1}, {2, 3}])
    rn = nx.quotient_graph(ng, [{0, 1}, {2, 3}])
    # Both should have the same block-node keys
    assert set(rf.nodes()) == set(rn.nodes())
    # And matching default attrs (graph/nnodes/nedges/density)
    for node in rf.nodes():
        rf_attrs = rf.nodes[node]
        rn_attrs = rn.nodes[node]
        # graph attribute is a subgraph; compare node sets
        if "graph" in rf_attrs and "graph" in rn_attrs:
            assert set(rf_attrs["graph"].nodes()) == set(rn_attrs["graph"].nodes())
        assert rf_attrs.get("nnodes") == rn_attrs.get("nnodes")
        assert rf_attrs.get("nedges") == rn_attrs.get("nedges")
        assert rf_attrs.get("density") == pytest.approx(rn_attrs.get("density"))


def test_quotient_graph_custom_node_data_unchanged():
    """When node_data IS provided, fnx uses it (default attrs NOT applied)."""
    g = fnx.path_graph(4)
    rf = fnx.quotient_graph(g, [{0, 1}, {2, 3}], node_data=lambda b: {"size": len(b)})
    for node in rf.nodes():
        attrs = rf.nodes[node]
        assert attrs == {"size": len(node)}  # custom data only, no defaults


def test_quotient_graph_default_attrs_present():
    g = fnx.path_graph(3)
    rf = fnx.quotient_graph(g, [{0, 1, 2}])
    block = next(iter(rf.nodes()))
    attrs = rf.nodes[block]
    assert set(attrs.keys()) >= {"graph", "nnodes", "nedges", "density"}
    assert attrs["nnodes"] == 3
    assert attrs["nedges"] == 2


def test_quotient_graph_default_graph_attr_stays_live_and_ordered():
    graph = fnx.path_graph(4)
    result = fnx.quotient_graph(graph, [{0, 1}, {2, 3}])
    block = frozenset({0, 1})
    attrs = result.nodes[block]

    assert list(attrs.keys()) == ["graph", "nnodes", "nedges", "density"]
    assert attrs["nedges"] == 1

    graph.add_edge(0, 0)

    assert attrs["graph"].number_of_edges() == 2
    assert attrs["nedges"] == 1


@needs_nx
def test_quotient_graph_default_directed_node_metrics_match_networkx():
    fnx_graph = fnx.DiGraph()
    fnx_graph.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 2), (2, 3)])
    nx_graph = nx.DiGraph()
    nx_graph.add_edges_from(fnx_graph.edges())
    partition = [{0, 1}, {2, 3}]

    result = fnx.quotient_graph(fnx_graph, partition)
    expected = nx.quotient_graph(nx_graph, partition)

    for block in result.nodes():
        result_attrs = result.nodes[block]
        expected_attrs = expected.nodes[block]
        assert result_attrs["nnodes"] == expected_attrs["nnodes"]
        assert result_attrs["nedges"] == expected_attrs["nedges"]
        assert result_attrs["density"] == pytest.approx(expected_attrs["density"])


@needs_nx
def test_quotient_graph_default_multigraph_node_metrics_match_networkx():
    fnx_graph = fnx.MultiGraph()
    fnx_graph.add_edge(0, 1)
    fnx_graph.add_edge(0, 1)
    fnx_graph.add_edge(1, 1)
    fnx_graph.add_edge(1, 2)
    nx_graph = nx.MultiGraph()
    nx_graph.add_edges_from(fnx_graph.edges(keys=True))
    partition = [{0, 1, 2}]

    result = fnx.quotient_graph(fnx_graph, partition)
    expected = nx.quotient_graph(nx_graph, partition)
    block = frozenset({0, 1, 2})

    assert result.nodes[block]["nnodes"] == expected.nodes[block]["nnodes"]
    assert result.nodes[block]["nedges"] == expected.nodes[block]["nedges"]
    assert result.nodes[block]["density"] == pytest.approx(
        expected.nodes[block]["density"]
    )


@needs_nx
def test_quotient_graph_default_unweighted_bucket_path_matches_networkx():
    graph = fnx.Graph()
    graph.add_edges_from(
        [
            (0, 3),
            (1, 4),
            (2, 5),
            (2, 6),
            (7, 9),
            (8, 10),
        ]
    )
    expected_graph = nx.Graph()
    expected_graph.add_edges_from(graph.edges())
    partition = [{0, 1, 2}, {3, 4, 5, 6}, {7, 8}, {9, 10}]

    result = fnx.quotient_graph(graph, partition)
    expected = nx.quotient_graph(expected_graph, partition)

    assert list(result.edges(data=True)) == list(expected.edges(data=True))


# br-r37-c1-ljkp0: networkx's _quotient_graph, everywhere the undirected bucket
# path above does not apply. A multigraph quotient gets one edge per adjacent
# (u, v) carrying G.get_edge_data(u, v) (fnx raised ValueError); a directed
# default weight sums the edges joining two blocks in EITHER direction; a dict
# partition's values are its blocks; a callable partition's blocks come from
# equivalence_classes (a set of frozensets, in its iteration order); and an
# undirected H sees each block pair once, b before c, so an asymmetric
# edge_relation / edge_data is called as networkx calls it.
_QG_EDGES = [(i, (i + 1) % 12, float(i % 5) + 1.5) for i in range(12)] + [
    (i, (i + 5) % 12, float(i % 3) + 2.25) for i in range(0, 12, 3)
]
_QG_PARTITIONS = {
    "list": lambda: [set(range(0, 4)), set(range(4, 8)), set(range(8, 12))],
    "dict": lambda: {"a": {0, 1, 2, 3}, "b": {4, 5, 6, 7}, "c": {8, 9, 10, 11}},
    "callable": lambda: (lambda u, v: u % 3 == v % 3),
    "partial": lambda: [{0, 1}, {5, 6, 7}],
}
_QG_OPTIONS = {
    "default": {},
    "relabel": {"relabel": True},
    "asym_relation": {"edge_relation": lambda b, c: min(b) > min(c)},
    "asym_data": {"edge_data": lambda b, c: {"lo": min(b)}},
    "relation_without_edges": {"edge_relation": lambda b, c: True},
}


def _qg_block(node):
    return tuple(sorted(node)) if isinstance(node, frozenset) else node


def _qg_data(data):
    out = []
    for key, value in data.items():
        if key == "graph":
            value = (sorted(value.nodes()), sorted(map(repr, value.edges())))
        elif isinstance(value, dict):
            value = sorted((repr(k), repr(v)) for k, v in value.items())
        out.append((repr(key), repr(value)))
    return sorted(out)


def _qg_summary(lib, cls, parallel, partition, options):
    graph = getattr(lib, cls)()
    graph.add_weighted_edges_from(_QG_EDGES)
    if parallel:
        graph.add_weighted_edges_from([(0, 1, 4.0), (6, 7, 0.25), (1, 0, 0.5)])
    try:
        quotient = lib.quotient_graph(graph, _QG_PARTITIONS[partition](), **_QG_OPTIONS[options])
    except Exception as exc:  # noqa: BLE001 - the raise is the answer
        return ("raise", type(exc).__name__, str(exc))
    kw = {"keys": True} if quotient.is_multigraph() else {}
    return (
        type(quotient).__name__,
        [(_qg_block(n), _qg_data(d)) for n, d in quotient.nodes(data=True)],
        [tuple(map(_qg_block, e[:-1])) + (_qg_data(e[-1]),) for e in quotient.edges(data=True, **kw)],
    )


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("partition", sorted(_QG_PARTITIONS))
@pytest.mark.parametrize("options", sorted(_QG_OPTIONS))
@pytest.mark.parametrize("parallel", [False, True], ids=["simple_edges", "parallel_edges"])
def test_quotient_graph_matches_networkx_node_and_edge_order(cls, partition, options, parallel):
    assert _qg_summary(fnx, cls, parallel, partition, options) == _qg_summary(
        nx, cls, parallel, partition, options
    )


@needs_nx
@pytest.mark.parametrize("library", [fnx, nx], ids=["native", "networkx"])
@pytest.mark.parametrize("view", ["graph", "subgraph", "reverse"])
def test_quotient_block_views_retain_the_original_source(library, view):
    graph = library.DiGraph() if view == "reverse" else library.Graph()
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    source = graph
    if view == "subgraph":
        source = graph.subgraph([0, 1, 2, 3])
    elif view == "reverse":
        source = graph.reverse(copy=False)
    result = fnx.quotient_graph(source, [{0, 1}, {2, 3}])
    block_data = result.nodes[frozenset({0, 1})]

    graph.add_edge(0, 0, marker="later")
    graph.nodes[1]["state"] = "changed"

    assert block_data["graph"].has_edge(0, 0)
    assert block_data["graph"][0][0]["marker"] == "later"
    assert block_data["graph"].nodes[1]["state"] == "changed"
    assert block_data["nedges"] == 1
    assert block_data["nnodes"] == 2
    assert block_data["density"] == (0.5 if graph.is_directed() else 1.0)


@needs_nx
@pytest.mark.parametrize("weight", [None, 0, "", False])
@pytest.mark.parametrize("library", [fnx, nx], ids=["native", "networkx"])
def test_quotient_default_weights_use_falsy_attribute_keys(library, weight):
    graph = library.Graph()
    graph.add_edges_from([(0, 2, {weight: 7}), (1, 3, {weight: 11}), (0, 3)])
    result = fnx.quotient_graph(graph, [{0, 1}, {2, 3}], weight=weight)
    assert result[frozenset({0, 1})][frozenset({2, 3})]["weight"] == 19


@needs_nx
@pytest.mark.parametrize("library", [fnx, nx], ids=["native", "networkx"])
@pytest.mark.parametrize("values", [
    [1e16, 1.0, -1e16],
    [2**80, 1, -(2**80)],
    [1e308, -1e308, 3.0],
])
def test_quotient_aggregation_preserves_python_sum(library, values):
    edges = [(i, i + 3, {"weight": value}) for i, value in enumerate(values)]
    graph = library.Graph()
    graph.add_edges_from(edges)
    reference = nx.Graph()
    reference.add_edges_from(edges)
    partition = [{0, 1, 2}, {3, 4, 5}]

    result = fnx.quotient_graph(graph, partition)
    expected = nx.quotient_graph(reference, partition)

    assert list(result.edges(data=True)) == list(expected.edges(data=True))
    edge = (frozenset(partition[0]), frozenset(partition[1]))
    assert type(result.edges[edge]["weight"]) is type(expected.edges[edge]["weight"])


@needs_nx
@pytest.mark.parametrize("library", [fnx, nx], ids=["native", "networkx"])
def test_quotient_custom_node_data_accepts_nonstring_keys(library):
    graph = library.path_graph(4)
    payload = []
    result = fnx.quotient_graph(
        graph, [{0, 1}, {2, 3}], node_data=lambda block: {0: len(block), None: payload}
    )
    for _, attrs in result.nodes(data=True):
        assert attrs[0] == 2
        assert attrs[None] is payload


@needs_nx
@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_quotient_node_callback_mutations_reach_later_edges(cls):
    def run(library, operation):
        graph = getattr(library, cls)()
        graph.add_nodes_from(range(4))
        calls = []

        def node_data(block):
            calls.append(block)
            if 2 in block:
                graph.add_edge(0, 2, weight=7)
            return {"size": len(block)}

        result = operation(graph, [{0, 1}, {2, 3}], node_data=node_data)
        kwargs = {"keys": True} if result.is_multigraph() else {}
        return calls, list(result.nodes(data=True)), list(result.edges(data=True, **kwargs))

    assert run(nx, fnx.quotient_graph) == run(nx, nx.quotient_graph)
    assert run(fnx, fnx.quotient_graph) == run(nx, nx.quotient_graph)


@needs_nx
@pytest.mark.parametrize("prewarm", [False, True])
def test_quotient_backend_keeps_live_block_views(prewarm):
    import franken_networkx.backend as backend

    graph = nx.path_graph(4)
    if prewarm:
        nx.shortest_path(graph, 0, 3, backend="franken_networkx")
    assert backend.BackendInterface.can_run(
        "quotient_graph", (graph, [{0, 1}, {2, 3}]), {}
    )
    result = nx.quotient_graph(
        graph, [{0, 1}, {2, 3}], backend="franken_networkx"
    )
    graph.add_edge(0, 0)
    assert result.nodes[frozenset({0, 1})]["graph"].has_edge(0, 0)


@needs_nx
def test_quotient_metadata_uses_the_subgraph_public_protocol():
    def run(library, operation):
        calls = []

        class SubgraphStats:
            def __len__(self):
                calls.append("len")
                return 2

            def number_of_nodes(self):
                calls.append("number_of_nodes")
                return 4

            def number_of_edges(self):
                calls.append("number_of_edges")
                return 3

            def is_directed(self):
                calls.append("is_directed")
                return True

        class SourceGraph(library.Graph):
            def subgraph(self, nodes):
                return SubgraphStats()

        graph = SourceGraph()
        graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
        result = operation(graph, [{0, 1}, {2, 3}])
        metadata = [
            (attrs["nnodes"], attrs["nedges"], attrs["density"])
            for _, attrs in result.nodes(data=True)
        ]
        return metadata, calls

    expected = run(nx, nx.quotient_graph)
    assert expected[0] == [(2, 3, 0.25), (2, 3, 0.25)]
    assert run(nx, fnx.quotient_graph) == expected
    assert run(fnx, fnx.quotient_graph) == expected
