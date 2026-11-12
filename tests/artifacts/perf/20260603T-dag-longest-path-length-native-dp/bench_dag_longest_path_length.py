from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import random
import sys
import time


def _build_dag(module, *, n: int, p: float, seed: int):
    rng = random.Random(seed)
    graph = module.DiGraph()
    graph.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                graph.add_edge(u, v)
    return graph


def _result_payload(module, graph):
    length = module.dag_longest_path_length(graph)
    return {
        "length": length,
        "length_type": type(length).__name__,
    }


def _sha256(payload) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _time_module(module, graph, repeat: int):
    start = time.perf_counter()
    payload = None
    for _ in range(repeat):
        payload = _result_payload(module, graph)
    elapsed = time.perf_counter() - start
    return payload, elapsed


def _profile_module(module, graph, repeat: int):
    profiler = cProfile.Profile()
    profiler.enable()
    payload, elapsed = _time_module(module, graph, repeat)
    profiler.disable()
    print(
        json.dumps(
            {
                "elapsed_s": elapsed,
                "repeat": repeat,
                "sha256": _sha256(payload),
                "payload": payload,
            },
            sort_keys=True,
        )
    )
    pstats.Stats(profiler, stream=sys.stdout).strip_dirs().sort_stats(
        "cumulative"
    ).print_stats(40)


def _load_module(name: str):
    if name == "fnx":
        import franken_networkx as module
    elif name == "nx":
        import networkx as module
    else:
        raise ValueError(name)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", choices=["fnx", "nx"], required=True)
    parser.add_argument("--repeat", type=int, default=200)
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--p", type=float, default=0.02)
    parser.add_argument("--seed", type=int, default=20260603)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()

    module = _load_module(args.module)
    graph = _build_dag(module, n=args.n, p=args.p, seed=args.seed)
    if args.profile:
        _profile_module(module, graph, args.repeat)
        return

    payload, elapsed = _time_module(module, graph, args.repeat)
    print(
        json.dumps(
            {
                "module": args.module,
                "n": args.n,
                "p": args.p,
                "repeat": args.repeat,
                "seed": args.seed,
                "elapsed_s": elapsed,
                "per_call_s": elapsed / args.repeat,
                "sha256": _sha256(payload),
                "payload": payload,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
