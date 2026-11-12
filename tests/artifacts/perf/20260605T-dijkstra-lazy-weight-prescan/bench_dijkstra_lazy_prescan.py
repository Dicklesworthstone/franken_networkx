import argparse
import hashlib
import json
import math
import random
import time
from typing import Any

import networkx as nx
import franken_networkx as fnx


def stable_record(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return {"float": "nan"}
        if math.isinf(value):
            return {"float": "inf" if value > 0 else "-inf"}
        return value
    if isinstance(value, tuple):
        return [stable_record(item) for item in value]
    if isinstance(value, list):
        return [stable_record(item) for item in value]
    if isinstance(value, dict):
        return {str(key): stable_record(val) for key, val in sorted(value.items(), key=lambda kv: repr(kv[0]))}
    return value


def call_record(lib: Any, graph: Any, source: Any, target: Any, weight: Any = "weight") -> dict[str, Any]:
    try:
        value = lib.bidirectional_dijkstra(graph, source, target, weight=weight)
    except Exception as exc:  # noqa: BLE001 - parity artifact records public exception shape.
        return {
            "ok": False,
            "type": type(exc).__name__,
            "message": str(exc),
        }
    return {
        "ok": True,
        "value": stable_record(value),
        "length_type": type(value[0]).__name__,
        "path_types": [type(node).__name__ for node in value[1]],
    }


def digest_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def add_edges(graph: Any, edges: list[tuple[int, int, Any]]) -> None:
    for left, right, weight in edges:
        graph.add_edge(left, right, weight=weight)


def make_query_graph(lib: Any, n: int, extra_edges: int) -> Any:
    graph = lib.Graph()
    graph.add_nodes_from(range(n))
    for node in range(n - 1):
        graph.add_edge(node, node + 1, weight=1.0)
    rng = random.Random(91827)
    added = 0
    seen = {(node, node + 1) for node in range(n - 1)}
    while added < extra_edges:
        left = rng.randrange(n)
        right = rng.randrange(n)
        if left == right:
            continue
        edge = (left, right) if left < right else (right, left)
        if edge in seen:
            continue
        seen.add(edge)
        # Keep weights positive, finite, and numeric for the fast-path benchmark.
        graph.add_edge(edge[0], edge[1], weight=float(1 + (added % 7)))
        added += 1
    return graph


def time_calls(fn: Any, reps: int) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(reps):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    ordered = sorted(samples)
    return {
        "reps": reps,
        "mean_s": sum(samples) / len(samples),
        "median_s": ordered[len(ordered) // 2],
        "p95_s": ordered[int((len(ordered) - 1) * 0.95)],
        "min_s": ordered[0],
        "max_s": ordered[-1],
    }


def golden_cases() -> dict[str, Any]:
    cases: dict[str, tuple[list[tuple[int, int, Any]], int, int, Any]] = {
        "valid_int_path": ([(0, 1, 2), (1, 2, 3), (0, 2, 10)], 0, 2, "weight"),
        "valid_float_path": ([(0, 1, 1.5), (1, 2, 2.25), (0, 2, 9.0)], 0, 2, "weight"),
        "missing_weight_defaults_to_one": ([(0, 1, 1), (1, 2, 1)], 0, 2, "missing"),
        "positive_inf_touched": ([(0, 1, math.inf), (0, 2, 5), (2, 1, 1)], 0, 1, "weight"),
        "nan_touched": ([(0, 1, math.nan), (0, 2, 5), (2, 1, 1)], 0, 1, "weight"),
        "negative_touched": ([(0, 1, 1), (1, 2, -5), (0, 2, 10)], 0, 2, "weight"),
        "string_touched": ([(0, 1, "5"), (1, 2, 1), (0, 2, 10)], 0, 2, "weight"),
        "none_touched": ([(0, 1, None), (1, 2, 1), (0, 2, 10)], 0, 2, "weight"),
        "invalid_disconnected_not_touched": ([(0, 1, 1), (1, 2, 1), (10, 11, "bad")], 0, 2, "weight"),
    }
    payload: dict[str, Any] = {}
    for name, (edges, source, target, weight) in cases.items():
        nx_graph = nx.Graph()
        fnx_graph = fnx.Graph()
        add_edges(nx_graph, edges)
        add_edges(fnx_graph, edges)
        payload[name] = {
            "nx": call_record(nx, nx_graph, source, target, weight),
            "fnx": call_record(fnx, fnx_graph, source, target, weight),
        }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["bench", "golden", "scan"], required=True)
    parser.add_argument("--reps", type=int, default=80)
    parser.add_argument("--nodes", type=int, default=3000)
    parser.add_argument("--extra-edges", type=int, default=12000)
    parser.add_argument("--disable-cache", action="store_true")
    args = parser.parse_args()

    if args.disable_cache:
        fnx._native_dijkstra_weight_cache_token = None

    if args.mode == "golden":
        payload = golden_cases()
        print(json.dumps({"mode": "golden", "digest": digest_payload(payload), "payload": payload}, sort_keys=True))
        return

    graph_fnx = make_query_graph(fnx, args.nodes, args.extra_edges)
    source = 0
    target = args.nodes - 1

    if args.mode == "scan":
        scan = getattr(fnx, "_native_check_dijkstra_weights_fast")
        stats = time_calls(lambda: scan(graph_fnx, "weight"), args.reps)
        print(json.dumps({"mode": "scan", "stats": stats}, sort_keys=True))
        return

    graph_nx = make_query_graph(nx, args.nodes, args.extra_edges)
    fnx_record = call_record(fnx, graph_fnx, source, target)
    nx_record = call_record(nx, graph_nx, source, target)
    fnx_stats = time_calls(lambda: fnx.bidirectional_dijkstra(graph_fnx, source, target, weight="weight"), args.reps)
    nx_stats = time_calls(lambda: nx.bidirectional_dijkstra(graph_nx, source, target, weight="weight"), args.reps)
    payload = {"fnx": fnx_record, "nx": nx_record}
    print(
        json.dumps(
            {
                "mode": "bench",
                "nodes": args.nodes,
                "extra_edges": args.extra_edges,
                "records_match": fnx_record == nx_record,
                "digest": digest_payload(payload),
                "fnx_stats": fnx_stats,
                "nx_stats": nx_stats,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
