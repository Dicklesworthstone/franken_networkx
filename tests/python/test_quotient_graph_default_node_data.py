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
