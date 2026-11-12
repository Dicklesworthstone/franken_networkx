#!/usr/bin/env python3
"""Behavior checks for the quotient_graph default node-metrics perf pass."""

from __future__ import annotations

import hashlib
import json
import math

import franken_networkx as fnx
import networkx as nx


def digest_graph(graph):
    payload = {
        "nodes": [
            {
                "node": sorted(node) if isinstance(node, frozenset) else node,
                "keys": list(data.keys()),
                "nnodes": data.get("nnodes"),
                "nedges": data.get("nedges"),
                "density": data.get("density"),
                "graph_nodes": sorted(data["graph"].nodes())
                if "graph" in data
                else None,
                "graph_edges": data["graph"].number_of_edges()
                if "graph" in data
                else None,
            }
            for node, data in graph.nodes(data=True)
        ],
        "edges": [
            {
                "u": sorted(u) if isinstance(u, frozenset) else u,
                "v": sorted(v) if isinstance(v, frozenset) else v,
                "attrs": sorted(data.items()),
            }
            for u, v, data in graph.edges(data=True)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, default=repr).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def assert_close(left, right):
    if isinstance(left, float) or isinstance(right, float):
        assert math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
    else:
        assert left == right


def compare_default_node_metrics(fnx_graph, nx_graph, partition):
    result = fnx.quotient_graph(fnx_graph, partition)
    expected = nx.quotient_graph(nx_graph, partition)
    assert list(result.nodes()) == list(expected.nodes())
    for block in result.nodes():
        result_attrs = result.nodes[block]
        expected_attrs = expected.nodes[block]
        assert list(result_attrs.keys()) == list(expected_attrs.keys())
        assert list(result_attrs.keys()) == ["graph", "nnodes", "nedges", "density"]
        assert sorted(result_attrs["graph"].nodes()) == sorted(
            expected_attrs["graph"].nodes()
        )
        assert result_attrs["nnodes"] == expected_attrs["nnodes"]
        assert result_attrs["nedges"] == expected_attrs["nedges"]
        assert_close(result_attrs["density"], expected_attrs["density"])
    return result, expected


def main():
    simple_fnx = fnx.path_graph(4)
    simple_nx = nx.path_graph(4)
    simple_result, simple_expected = compare_default_node_metrics(
        simple_fnx, simple_nx, [{0, 1}, {2, 3}]
    )
    simple_block = frozenset({0, 1})
    simple_fnx.add_edge(0, 0)
    simple_nx.add_edge(0, 0)
    assert simple_result.nodes[simple_block]["graph"].number_of_edges() == 2
    assert simple_expected.nodes[simple_block]["graph"].number_of_edges() == 2
    assert simple_result.nodes[simple_block]["nedges"] == 1
    assert simple_expected.nodes[simple_block]["nedges"] == 1

    directed_fnx = fnx.DiGraph()
    directed_fnx.add_edges_from([(0, 1), (1, 0), (1, 2), (2, 2), (2, 3)])
    directed_nx = nx.DiGraph()
    directed_nx.add_edges_from(directed_fnx.edges())
    compare_default_node_metrics(directed_fnx, directed_nx, [{0, 1}, {2, 3}])

    multi_fnx = fnx.MultiGraph()
    multi_fnx.add_edge(0, 1)
    multi_fnx.add_edge(0, 1)
    multi_fnx.add_edge(1, 1)
    multi_fnx.add_edge(1, 2)
    multi_nx = nx.MultiGraph()
    multi_nx.add_edges_from(multi_fnx.edges(keys=True))
    compare_default_node_metrics(multi_fnx, multi_nx, [{0, 1, 2}])

    weighted_fnx = fnx.Graph()
    weighted_fnx.add_edge(0, 2, weight=1.5)
    weighted_nx = nx.Graph()
    weighted_nx.add_edge(0, 2, weight=1.5)
    weighted_result = fnx.quotient_graph(weighted_fnx, [{0}, {2}])
    weighted_expected = nx.quotient_graph(weighted_nx, [{0}, {2}])
    assert list(weighted_result.edges(data=True)) == list(
        weighted_expected.edges(data=True)
    )

    relabeled_result = fnx.quotient_graph(fnx.path_graph(4), [{0, 1}, {2, 3}], relabel=True)
    relabeled_expected = nx.quotient_graph(nx.path_graph(4), [{0, 1}, {2, 3}], relabel=True)
    assert list(relabeled_result.nodes()) == list(relabeled_expected.nodes())
    assert list(relabeled_result.edges(data=True)) == list(relabeled_expected.edges(data=True))

    digest, payload = digest_graph(fnx.quotient_graph(fnx.path_graph(6), [{0, 1, 2}, {3, 4, 5}]))
    print(json.dumps({"digest": digest, "payload": payload}, sort_keys=True))


if __name__ == "__main__":
    main()
