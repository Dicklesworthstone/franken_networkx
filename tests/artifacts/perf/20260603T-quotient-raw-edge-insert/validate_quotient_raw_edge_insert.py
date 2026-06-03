#!/usr/bin/env python3
"""Behavior checks for quotient_graph trusted raw edge insertion."""

from __future__ import annotations

import hashlib
import json
import math

import franken_networkx as fnx
import networkx as nx


def canonical_node(node):
    return sorted(node) if isinstance(node, frozenset) else node


def digest_graph(graph):
    payload = {
        "nodes": [
            {
                "node": canonical_node(node),
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
                "u": canonical_node(u),
                "v": canonical_node(v),
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


def compare_default_case(fnx_graph, nx_graph, partition, **kwargs):
    result = fnx.quotient_graph(fnx_graph, partition, **kwargs)
    expected = nx.quotient_graph(nx_graph, partition, **kwargs)

    assert list(result.nodes()) == list(expected.nodes())
    assert list(result.edges(data=True)) == list(expected.edges(data=True))
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
    compare_default_case(graph, expected_graph, partition)

    weighted_fnx = fnx.Graph()
    weighted_fnx.add_edge(0, 2, weight=2)
    weighted_fnx.add_edge(1, 3, weight=4)
    weighted_nx = nx.Graph()
    weighted_nx.add_edges_from(
        [
            (0, 2, {"weight": 2}),
            (1, 3, {"weight": 4}),
        ]
    )
    weighted_result, weighted_expected = compare_default_case(
        weighted_fnx,
        weighted_nx,
        [{0, 1}, {2, 3}],
    )
    assert list(weighted_result.edges(data=True)) == list(
        weighted_expected.edges(data=True)
    )

    relabeled_result = fnx.quotient_graph(
        fnx.path_graph(4),
        [{0, 1}, {2, 3}],
        relabel=True,
    )
    relabeled_expected = nx.quotient_graph(
        nx.path_graph(4),
        [{0, 1}, {2, 3}],
        relabel=True,
    )
    assert list(relabeled_result.nodes()) == list(relabeled_expected.nodes())
    assert list(relabeled_result.edges(data=True)) == list(
        relabeled_expected.edges(data=True)
    )

    custom_node_result = fnx.quotient_graph(
        fnx.path_graph(4),
        [{0, 1}, {2, 3}],
        node_data=lambda block: {"size": len(block)},
    )
    assert [dict(data) for _, data in custom_node_result.nodes(data=True)] == [
        {"size": 2},
        {"size": 2},
    ]

    digest, payload = digest_graph(
        fnx.quotient_graph(fnx.path_graph(6), [{0, 1, 2}, {3, 4, 5}])
    )
    print(json.dumps({"digest": digest, "payload": payload}, sort_keys=True))


if __name__ == "__main__":
    main()
