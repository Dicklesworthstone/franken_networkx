from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from typing import Any

import franken_networkx as fnx
import networkx as nx


def stable(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return {"float": "nan"}
        if math.isinf(value):
            return {"float": "inf" if value > 0 else "-inf"}
        return value
    if isinstance(value, tuple):
        return [stable(item) for item in value]
    if isinstance(value, list):
        return [stable(item) for item in value]
    if isinstance(value, dict):
        return {
            repr(key): stable(val)
            for key, val in sorted(value.items(), key=lambda item: repr(item[0]))
        }
    return value


def digest(value: Any) -> str:
    payload = json.dumps(stable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def build_graph(module: Any, n: int) -> Any:
    graph = module.Graph()
    for node in range(n):
        graph.add_edge(node, (node + 1) % n, weight=float((node % 11) + 1))
        graph.add_edge(node, (node + 7) % n, weight=float((node % 13) + 2))
        if node % 5 == 0:
            graph.add_edge(node, (node + 19) % n, weight=float((node % 17) + 3))
    return graph


def call(module: Any, graph: Any, weighted: bool) -> Any:
    return module.hyper_wiener_index(graph, weight="weight" if weighted else None)


def bench(args: argparse.Namespace) -> None:
    modules = {"fnx": fnx, "nx": nx}
    selected = ("fnx", "nx") if args.impl == "both" else (args.impl,)
    records = []
    for name in selected:
        module = modules[name]
        graph = build_graph(module, args.nodes)
        samples = []
        value = None
        for _ in range(args.warmup):
            call(module, graph, args.weighted)
        for _ in range(args.repeats):
            start = time.perf_counter()
            value = call(module, graph, args.weighted)
            samples.append(time.perf_counter() - start)
        records.append(
            {
                "impl": name,
                "nodes": args.nodes,
                "weighted": args.weighted,
                "repeats": args.repeats,
                "mean_sec": statistics.fmean(samples),
                "median_sec": statistics.median(samples),
                "min_sec": min(samples),
                "max_sec": max(samples),
                "samples_sec": samples,
                "value": value,
                "digest": digest(value),
            }
        )
    fnx_record = next((row for row in records if row["impl"] == "fnx"), None)
    nx_record = next((row for row in records if row["impl"] == "nx"), None)
    print(
        json.dumps(
            {
                "mode": "bench",
                "records": records,
                "fnx_over_nx": (
                    fnx_record["mean_sec"] / nx_record["mean_sec"]
                    if fnx_record is not None and nx_record is not None
                    else None
                ),
                "digests_match": (
                    fnx_record["digest"] == nx_record["digest"]
                    if fnx_record is not None and nx_record is not None
                    else None
                ),
                "golden_sha256": digest(records),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def proof(args: argparse.Namespace) -> None:
    cases = []
    for n in (0, 1, 2, 5, 20, args.nodes):
        for weighted in (False, True):
            fg = build_graph(fnx, max(n, 1))
            ng = build_graph(nx, max(n, 1))
            if n == 0:
                fg.clear()
                ng.clear()
            fnx_value = None
            nx_value = None
            fnx_error = None
            nx_error = None
            try:
                fnx_value = call(fnx, fg, weighted)
            except Exception as exc:  # noqa: BLE001 - proof records public parity.
                fnx_error = (type(exc).__name__, str(exc))
            try:
                nx_value = call(nx, ng, weighted)
            except Exception as exc:  # noqa: BLE001 - proof records public parity.
                nx_error = (type(exc).__name__, str(exc))
            cases.append(
                {
                    "nodes": n,
                    "weighted": weighted,
                    "fnx": {"value": fnx_value, "error": fnx_error},
                    "nx": {"value": nx_value, "error": nx_error},
                }
            )

    bad = [row for row in cases if row["fnx"] != row["nx"]]
    payload = {"mode": "proof", "cases": cases, "failures": bad}
    print(
        json.dumps(
            {
                "mode": "proof",
                "cases": len(cases),
                "failures": len(bad),
                "golden_sha256": digest(payload),
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["bench", "proof"], required=True)
    parser.add_argument("--impl", choices=["both", "fnx", "nx"], default="both")
    parser.add_argument("--nodes", type=int, default=80)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--weighted", action="store_true")
    args = parser.parse_args()
    if args.mode == "bench":
        bench(args)
    else:
        proof(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
