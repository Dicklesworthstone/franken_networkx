from __future__ import annotations

import hashlib
import json
import pickle
from typing import Any

import franken_networkx as fnx
import networkx as nx


def token(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def public_edges(graph: Any, limit: int = 32) -> list[Any]:
    return [
        (token(u), token(v), token(key), sorted((str(k), repr(vv)) for k, vv in data.items()))
        for u, v, key, data in list(graph.edges(keys=True, data=True))[:limit]
    ]


def assert_same(label: str, left: Any, right: Any) -> None:
    if left != right:
        raise AssertionError(f"{label} diverged:\nfnx={left!r}\nnx={right!r}")


def build_new_endpoint_path(module: Any, n: int, key_kind: str) -> Any:
    graph = module.MultiGraph()
    for i in range(n):
        key = str(i) if key_kind == "str" else i
        returned = graph.add_edge(i, i + 1, key=key)
        if returned != key:
            raise AssertionError(f"add_edge returned {returned!r}, expected {key!r}")
    return graph


def build_existing_endpoint_path(module: Any, n: int) -> Any:
    graph = module.MultiGraph()
    graph.add_nodes_from(range(n + 1))
    for i in range(n):
        key = str(i)
        returned = graph.add_edge(i, i + 1, key=key)
        if returned != key:
            raise AssertionError(f"add_edge returned {returned!r}, expected {key!r}")
    return graph


def duplicate_string_key_surface(module: Any) -> dict[str, Any]:
    graph = module.MultiGraph()
    first = "".join(["edge", "-", "0"])
    equal = "".join(["edge", "-", "0"])
    first_return = graph.add_edge(0, 1, key=first)
    second_return = graph.add_edge(0, 1, key=equal, weight=7)
    graph[0][1][first]["color"] = "red"
    return {
        "first_return_is_first": first_return is first,
        "second_return_equals": second_return == equal,
        "edge_count": graph.number_of_edges(),
        "keys": list(graph[0][1].keys()),
        "edge_data": dict(graph.get_edge_data(0, 1, key=equal)),
        "edges": public_edges(graph, 8),
        "weighted_size": graph.size(weight="weight"),
    }


def validation_and_auto_key_surface(module: Any) -> dict[str, Any]:
    def observed_error(callable_obj: Any) -> tuple[str, str]:
        try:
            callable_obj()
        except Exception as exc:  # noqa: BLE001 - proof captures public exception surface.
            return (type(exc).__name__, str(exc))
        raise AssertionError("expected exception")

    graph = module.MultiGraph()
    returns = [
        graph.add_edge(0, 1),
        graph.add_edge(0, 1),
        graph.add_edge(0, 1, key=4),
        graph.add_edge(0, 1),
    ]
    return {
        "none_node_error": observed_error(lambda: module.MultiGraph().add_edge(None, 1)),
        "unhashable_node_error": observed_error(lambda: module.MultiGraph().add_edge([], 1)),
        "unhashable_key_error": observed_error(
            lambda: module.MultiGraph().add_edge(0, 1, key=[])
        ),
        "auto_key_returns": returns,
        "auto_key_edges": public_edges(graph, 8),
    }


def graph_surface(graph: Any) -> dict[str, Any]:
    copied = graph.copy()
    ctor_copy = graph.__class__(graph)
    sub = graph.subgraph(range(12))
    edge_sub = graph.edge_subgraph([(2, 3, "2"), (8, 9, "8")])
    restored = pickle.loads(pickle.dumps(graph))
    return {
        "nodes_prefix": [token(node) for node in list(graph.nodes())[:24]],
        "neighbors_5": [token(node) for node in graph.neighbors(5)],
        "edges_prefix": public_edges(graph, 24),
        "get_edge_data_5_6": {
            token(key): sorted((str(k), repr(v)) for k, v in attrs.items())
            for key, attrs in graph.get_edge_data(5, 6).items()
        },
        "copy_nodes": [token(node) for node in list(copied.nodes())[:24]],
        "copy_edges": public_edges(copied, 24),
        "ctor_copy_nodes": [token(node) for node in list(ctor_copy.nodes())[:24]],
        "ctor_copy_edges": public_edges(ctor_copy, 24),
        "subgraph_nodes": [token(node) for node in sub.nodes()],
        "subgraph_edges": public_edges(sub, 24),
        "edge_subgraph_nodes": [token(node) for node in edge_sub.nodes()],
        "edge_subgraph_edges": public_edges(edge_sub, 8),
        "pickle_nodes": [token(node) for node in list(restored.nodes())[:24]],
        "pickle_edges": public_edges(restored, 24),
        "size_missing_weight": graph.size(weight="missing"),
    }


def main() -> None:
    cases: dict[str, tuple[Any, Any]] = {
        "new_endpoint_str_path": (
            build_new_endpoint_path(fnx, 128, "str"),
            build_new_endpoint_path(nx, 128, "str"),
        ),
        "new_endpoint_int_path": (
            build_new_endpoint_path(fnx, 128, "int"),
            build_new_endpoint_path(nx, 128, "int"),
        ),
        "existing_endpoint_str_path": (
            build_existing_endpoint_path(fnx, 64),
            build_existing_endpoint_path(nx, 64),
        ),
    }

    payload: dict[str, Any] = {
        "case": "br-r37-c1-kt0vp",
        "lever": "native MultiGraph.add_edge exact int-endpoint explicit-key fast path",
        "rng": "none",
        "floating_point": "only deterministic MultiGraph.size smoke values",
        "tie_breaking": "node order, edge order, key order, copy, subgraph, edge_subgraph, pickle",
    }
    for label, (fnx_graph, nx_graph) in cases.items():
        fnx_surface = graph_surface(fnx_graph)
        nx_surface = graph_surface(nx_graph)
        assert_same(label, fnx_surface, nx_surface)
        payload[label] = fnx_surface

    dup_fnx = duplicate_string_key_surface(fnx)
    dup_nx = duplicate_string_key_surface(nx)
    assert_same("duplicate string key fallback", dup_fnx, dup_nx)
    payload["duplicate_string_key_fallback"] = dup_fnx

    validation_fnx = validation_and_auto_key_surface(fnx)
    validation_nx = validation_and_auto_key_surface(nx)
    assert_same("validation and auto-key behavior", validation_fnx, validation_nx)
    payload["validation_and_auto_key_behavior"] = validation_fnx

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(hashlib.sha256(encoded).hexdigest())
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
