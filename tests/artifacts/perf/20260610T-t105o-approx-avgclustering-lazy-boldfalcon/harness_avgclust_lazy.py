from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import time
from pathlib import Path

import franken_networkx as fnx
import networkx as nx


def build_graphs(n: int, m: int) -> tuple[object, object]:
    nx_graph = nx.barabasi_albert_graph(n, m, seed=17)
    fnx_graph = fnx.Graph()
    fnx_graph.add_nodes_from(nx_graph.nodes())
    fnx_graph.add_edges_from(nx_graph.edges())
    return fnx_graph, nx_graph


def canonical_payload(n: int, m: int, trials: int, seeds: list[int]) -> dict[str, object]:
    fnx_graph, nx_graph = build_graphs(n, m)
    cases = []
    for seed in seeds:
        fnx_value = fnx.approximation.average_clustering(
            fnx_graph, trials=trials, seed=seed
        )
        nx_value = nx.approximation.average_clustering(nx_graph, trials=trials, seed=seed)
        cases.append(
            {
                "seed": seed,
                "fnx": fnx_value,
                "nx": nx_value,
                "match": fnx_value == nx_value,
                "delta": fnx_value - nx_value,
            }
        )
    payload = {"n": n, "m": m, "trials": trials, "cases": cases}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(blob).hexdigest()
    payload["all_match"] = all(case["match"] for case in cases)
    return payload


def bench_one(label: str, graph: object, trials: int, repeats: int) -> dict[str, object]:
    values = []
    for seed in range(repeats):
        start = time.perf_counter()
        result = fnx.approximation.average_clustering(
            graph, trials=trials, seed=seed
        ) if label == "fnx" else nx.approximation.average_clustering(
            graph, trials=trials, seed=seed
        )
        values.append({"seconds": time.perf_counter() - start, "result": result})
    ordered = sorted(item["seconds"] for item in values)
    return {
        "label": label,
        "repeats": repeats,
        "min": ordered[0],
        "median": ordered[len(ordered) // 2],
        "mean": sum(ordered) / len(ordered),
        "max": ordered[-1],
        "results_sha256": hashlib.sha256(
            json.dumps(
                [item["result"] for item in values],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    }


def profile_fnx(out: Path, n: int, m: int, trials: int, repeats: int) -> None:
    fnx_graph, _ = build_graphs(n, m)
    profiler = cProfile.Profile()
    profiler.enable()
    for seed in range(repeats):
        fnx.approximation.average_clustering(fnx_graph, trials=trials, seed=seed)
    profiler.disable()
    with out.open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumtime")
        stats.print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["proof", "bench", "profile", "fnx", "nx"])
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--trials", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--profile-out", type=Path)
    args = parser.parse_args()

    if args.mode == "proof":
        payload = canonical_payload(args.n, args.m, args.trials, list(range(args.repeats)))
        print(json.dumps(payload, sort_keys=True, indent=2))
        return

    if args.mode == "profile":
        if args.profile_out is None:
            raise SystemExit("--profile-out is required for profile mode")
        profile_fnx(args.profile_out, args.n, args.m, args.trials, args.repeats)
        return

    fnx_graph, nx_graph = build_graphs(args.n, args.m)
    if args.mode == "bench":
        payload = {
            "n": args.n,
            "m": args.m,
            "trials": args.trials,
            "fnx": bench_one("fnx", fnx_graph, args.trials, args.repeats),
            "nx": bench_one("nx", nx_graph, args.trials, args.repeats),
        }
        print(json.dumps(payload, sort_keys=True, indent=2))
        return

    graph = fnx_graph if args.mode == "fnx" else nx_graph
    lib = fnx if args.mode == "fnx" else nx
    for seed in range(args.repeats):
        lib.approximation.average_clustering(graph, trials=args.trials, seed=seed)


if __name__ == "__main__":
    main()
