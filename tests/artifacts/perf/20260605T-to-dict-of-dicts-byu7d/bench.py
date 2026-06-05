#!/usr/bin/env python3
"""Benchmark/proof harness for br-r37-c1-byu7d."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import importlib.util
import json
import pstats
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PYTHON = ROOT / "python"
for path in (str(ROOT), str(PYTHON)):
    while path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)


def _module(name: str):
    if name == "fnx":
        venv_candidates = sorted(
            (ROOT / ".venv" / "lib").glob(
                "python*/site-packages/franken_networkx/_fnx*.so"
            )
        )
        if venv_candidates:
            spec = importlib.util.spec_from_file_location(
                "franken_networkx._fnx", venv_candidates[0]
            )
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                sys.modules["franken_networkx._fnx"] = module
                spec.loader.exec_module(module)
        import franken_networkx as nx_mod
    elif name == "nx":
        import networkx as nx_mod
    else:
        raise ValueError(name)
    return nx_mod


def _make_graph(nx_mod, mode: str, n: int, m: int, prob: float, directed: bool):
    cls = nx_mod.DiGraph if directed else nx_mod.Graph
    graph = cls()
    graph.add_nodes_from(range(n))
    if mode == "generated" and hasattr(nx_mod, "gnp_random_graph"):
        return nx_mod.gnp_random_graph(n, prob, seed=17, directed=directed)
    for i in range(n):
        for step in range(1, m + 1):
            j = (i + step) % n
            if directed or i < j:
                graph.add_edge(i, j)
    return graph


def _digest_payload(d):
    rows = []
    alias_pairs = 0
    for u, nbrs in d.items():
        row = []
        for v, attrs in nbrs.items():
            row.append((v, tuple(sorted(attrs.items()))))
            if u != v and v in d and u in d[v] and d[v][u] is attrs:
                alias_pairs += 1
        rows.append((u, row))
    payload = {
        "rows": rows,
        "alias_pairs": alias_pairs,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest(), payload


def run_once(args):
    nx_mod = _module(args.module)
    graph = _make_graph(nx_mod, args.mode, args.nodes, args.degree, args.prob, args.directed)
    start = time.perf_counter()
    result = None
    for _ in range(args.repeats):
        result = nx_mod.to_dict_of_dicts(graph)
    elapsed = time.perf_counter() - start
    digest, payload = _digest_payload(result)
    mutation_live = None
    returned_is_graph_attr = None
    reverse_alias = None
    first_edge = next(iter(graph.edges()), None)
    if first_edge is not None:
        u, v = first_edge[:2]
        returned_is_graph_attr = result[u][v] is graph[u][v]
        if not args.directed and u != v:
            reverse_alias = result[u][v] is result[v][u]
        result[u][v]["__probe__"] = 1
        mutation_live = graph[u][v].get("__probe__") == 1
        del result[u][v]["__probe__"]
    return {
        "module": args.module,
        "mode": args.mode,
        "nodes": args.nodes,
        "degree": args.degree,
        "directed": args.directed,
        "repeats": args.repeats,
        "elapsed": elapsed,
        "digest": digest,
        "alias_pairs": payload["alias_pairs"],
        "mutation_live": mutation_live,
        "returned_is_graph_attr": returned_is_graph_attr,
        "reverse_alias": reverse_alias,
        "node_count": len(result),
        "edge_rows": sum(len(v) for v in result.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", choices=["fnx", "nx"], required=True)
    parser.add_argument("--mode", choices=["generated", "added"], default="generated")
    parser.add_argument("--nodes", type=int, default=2000)
    parser.add_argument("--degree", type=int, default=4)
    parser.add_argument("--prob", type=float, default=0.002)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--directed", action="store_true")
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()

    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        result = run_once(args)
        profiler.disable()
        stats = pstats.Stats(profiler, stream=sys.stderr).strip_dirs().sort_stats("cumtime")
        stats.print_stats(25)
    else:
        result = run_once(args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
