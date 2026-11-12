from __future__ import annotations

import hashlib
import json

import franken_networkx as fnx
import networkx as nx


def build(module, n: int = 2000):
    graph = module.MultiGraph()
    for i in range(n):
        graph.add_edge(i, i + 1, key=str(i))
    return graph


def public_edges(graph, n: int = 24):
    return [
        (u, v, key, dict(attrs))
        for u, v, key, attrs in list(graph.edges(keys=True, data=True))[:n]
    ]


def public_key_order(graph, n: int = 24):
    return [(u, v, key) for u, v, key in list(graph.edges(keys=True))[:n]]


def assert_same(label, left, right):
    if left != right:
        raise AssertionError(f"{label} diverged:\nfnx={left!r}\nnx={right!r}")


def assert_live_attr_dicts(module):
    graph = module.MultiGraph()
    first_key = "".join(["edge", "-", "0"])
    equal_key = "".join(["edge", "-", "0"])
    graph.add_edge(0, 1, key=first_key)
    graph.add_edge(0, 1, key=equal_key)

    keydict = graph[0][1]
    attrs = keydict[first_key]
    attrs["weight"] = 7

    if graph.get_edge_data(0, 1, key=first_key)["weight"] != 7:
        raise AssertionError("get_edge_data did not expose the live attr dict")
    if list(graph.edges(keys=True, data=True))[0][3]["weight"] != 7:
        raise AssertionError("edges(data=True) did not expose the live attr dict")
    if graph.size(weight="weight") != 7.0:
        raise AssertionError("weighted size did not observe lazy attr mutation")

    observed_key = list(graph.edges(keys=True))[0][2]
    return {
        "first_wins_equal_key": observed_key is first_key,
        "key_order": list(graph[0][1].keys()),
        "attrs": dict(graph.get_edge_data(0, 1, key=equal_key)),
        "size_weight": graph.size(weight="weight"),
    }


def assert_live_node_attr_dicts(module):
    graph = module.MultiGraph()
    graph.add_edge(0, 1, key="0")

    attrs = graph.nodes[0]
    attrs["color"] = "red"
    data_attrs = dict(list(graph.nodes(data=True))[0][1])

    if graph.nodes[0]["color"] != "red":
        raise AssertionError("node view did not expose the live attr dict")
    if data_attrs != {"color": "red"}:
        raise AssertionError("nodes(data=True) did not observe live node attr mutation")

    return {
        "node_order": list(graph.nodes()),
        "node_zero_attrs": dict(graph.nodes[0]),
        "nodes_data_prefix": [(node, dict(attrs)) for node, attrs in graph.nodes(data=True)],
    }


def assert_sparse_empty_edge_preservation(module):
    graph = build(module, 128)
    sub = graph.subgraph(range(33))
    copied = module.MultiGraph(graph)
    shallow = graph.copy()

    return {
        "subgraph_edges": public_key_order(sub, 40),
        "copy_edge_count": copied.number_of_edges(),
        "copy_edges": public_key_order(copied, 40),
        "shallow_edge_count": shallow.number_of_edges(),
        "shallow_edges": public_key_order(shallow, 40),
        "size_weight_missing": graph.size(weight="missing"),
    }


def main():
    fnx_graph = build(fnx)
    nx_graph = build(nx)

    assert_same("node order", list(fnx_graph.nodes())[:64], list(nx_graph.nodes())[:64])
    assert_same("edge/key order", public_key_order(fnx_graph), public_key_order(nx_graph))
    assert_same("edge data", public_edges(fnx_graph), public_edges(nx_graph))
    assert_same(
        "get_edge_data",
        {
            key: dict(attrs)
            for key, attrs in fnx_graph.get_edge_data(5, 6).items()
        },
        {
            key: dict(attrs)
            for key, attrs in nx_graph.get_edge_data(5, 6).items()
        },
    )

    live_fnx = assert_live_attr_dicts(fnx)
    live_nx = assert_live_attr_dicts(nx)
    assert_same("live attr dict behavior", live_fnx, live_nx)

    live_node_fnx = assert_live_node_attr_dicts(fnx)
    live_node_nx = assert_live_node_attr_dicts(nx)
    assert_same("live node attr dict behavior", live_node_fnx, live_node_nx)

    sparse_fnx = assert_sparse_empty_edge_preservation(fnx)
    sparse_nx = assert_sparse_empty_edge_preservation(nx)
    assert_same("sparse empty edge preservation", sparse_fnx, sparse_nx)

    payload = {
        "case": "br-r37-c1-941xy",
        "target": "MultiGraph.add_edge(i, i + 1, key=str(i))",
        "nodes_prefix": list(fnx_graph.nodes())[:64],
        "edges_prefix": public_key_order(fnx_graph, 64),
        "edge_data_prefix": public_edges(fnx_graph, 64),
        "get_edge_data_5_6": {
            key: dict(attrs)
            for key, attrs in fnx_graph.get_edge_data(5, 6).items()
        },
        "live_attr_dict_behavior": live_fnx,
        "live_node_attr_dict_behavior": live_node_fnx,
        "sparse_empty_edge_preservation": sparse_fnx,
        "fp_rng": "no random inputs; only weighted size smoke uses deterministic integer weight 7",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(hashlib.sha256(encoded).hexdigest())
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
