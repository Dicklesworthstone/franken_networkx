from __future__ import annotations

import hashlib
import json
import pickle
from typing import Any

import franken_networkx as fnx
import networkx as nx


EXPECTED_CONSTRUCTION_DIGEST = (
    "a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf"
)


def _token(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def graph_digest(graph: Any) -> str:
    payload = {
        "nodes": [_token(node) for node in graph.nodes()],
        "edges": [
            [_token(u), _token(v), _token(key), sorted((str(k), repr(vv)) for k, vv in data.items())]
            for u, v, key, data in graph.edges(keys=True, data=True)
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_str_key_chain(module: Any, n: int) -> Any:
    graph = module.MultiGraph()
    for i in range(n):
        graph.add_edge(i, i + 1, key=str(i))
    return graph


def public_edges(graph: Any, limit: int = 32) -> list[tuple[Any, Any, Any, dict[str, Any]]]:
    return [
        (u, v, key, dict(attrs))
        for u, v, key, attrs in list(graph.edges(keys=True, data=True))[:limit]
    ]


def assert_same(label: str, left: Any, right: Any) -> None:
    if left != right:
        raise AssertionError(f"{label} diverged:\nfnx={left!r}\nnx={right!r}")


def auto_key_surface(module: Any) -> dict[str, Any]:
    graph = module.MultiGraph()
    returns = [
        graph.add_edge("a", "b"),
        graph.add_edge("a", "b"),
        graph.add_edge("a", "b", key=4),
        graph.add_edge("a", "b"),
    ]
    return {
        "returns": returns,
        "edge_keys": list(graph["a"]["b"].keys()),
        "edges": public_edges(graph, 8),
    }


def equal_key_attr_surface(module: Any) -> dict[str, Any]:
    graph = module.MultiGraph()
    first_key = "".join(["edge", "-", "0"])
    equal_key = "".join(["edge", "-", "0"])
    graph.add_edge(0, 1, key=first_key, weight=1)
    graph.add_edge(0, 1, key=equal_key, color="red")
    graph[0][1][first_key]["live"] = True
    return {
        "edges": public_edges(graph, 8),
        "edge_data": {key: dict(attrs) for key, attrs in graph.get_edge_data(0, 1).items()},
        "weighted_size": graph.size(weight="weight"),
    }


def structural_surface(module: Any) -> dict[str, Any]:
    graph = build_str_key_chain(module, 256)
    copied_ctor = module.MultiGraph(graph)
    copied_method = graph.copy()
    subgraph = graph.subgraph(range(33))
    edge_subgraph = graph.edge_subgraph([(5, 6, "5"), (70, 71, "70")])
    restored = pickle.loads(pickle.dumps(graph))
    return {
        "nodes": list(graph.nodes())[:40],
        "neighbors_5": list(graph.neighbors(5)),
        "edges": public_edges(graph, 40),
        "copy_ctor_edges": public_edges(copied_ctor, 40),
        "copy_method_edges": public_edges(copied_method, 40),
        "subgraph_nodes": list(subgraph.nodes())[:40],
        "subgraph_edges": public_edges(subgraph, 40),
        "edge_subgraph_nodes": list(edge_subgraph.nodes()),
        "edge_subgraph_edges": public_edges(edge_subgraph, 8),
        "pickle_edges": public_edges(restored, 40),
    }


def main() -> None:
    fnx_chain = build_str_key_chain(fnx, 50_000)
    nx_chain = build_str_key_chain(nx, 50_000)
    fnx_digest = graph_digest(fnx_chain)
    nx_digest = graph_digest(nx_chain)
    assert_same("construction digest", fnx_digest, nx_digest)
    assert_same("expected construction digest", fnx_digest, EXPECTED_CONSTRUCTION_DIGEST)

    surfaces = {
        "auto_key": (auto_key_surface(fnx), auto_key_surface(nx)),
        "equal_key_attrs": (equal_key_attr_surface(fnx), equal_key_attr_surface(nx)),
        "structural": (structural_surface(fnx), structural_surface(nx)),
    }
    for label, (fnx_value, nx_value) in surfaces.items():
        assert_same(label, fnx_value, nx_value)

    payload = {
        "case": "br-r37-c1-nj976",
        "target": "MultiGraph.add_edge(i, i + 1, key=str(i))",
        "construction_digest": fnx_digest,
        "construction_nodes": fnx_chain.number_of_nodes(),
        "construction_edges": fnx_chain.number_of_edges(),
        "auto_key": surfaces["auto_key"][0],
        "equal_key_attrs": surfaces["equal_key_attrs"][0],
        "structural": surfaces["structural"][0],
        "ordering_tie_breaking": "nodes, neighbors, public edge keys, copies, subgraphs, and pickle match NetworkX",
        "floating_point": "no floating-point algorithmic output; weighted size deterministic smoke matches NetworkX",
        "rng": "no RNG inputs",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    print(hashlib.sha256(encoded).hexdigest())
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
