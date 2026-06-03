#!/usr/bin/env python3
"""Focused sparse export benchmark for br-r37-c1-04z53.20."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import statistics
import time
from pathlib import Path
from typing import Any, Callable

import franken_networkx as fnx
import networkx as nx
import numpy as np


CASE_FUNCS: dict[str, Callable[[Any, Any], Any]] = {
    "to_scipy_default": lambda mod, graph: mod.to_scipy_sparse_array(
        graph, format="csr"
    ),
    "to_scipy_weighted": lambda mod, graph: mod.to_scipy_sparse_array(
        graph, weight="weight", format="csr"
    ),
    "adjacency_weighted": lambda mod, graph: mod.adjacency_matrix(
        graph, weight="weight"
    ),
}


def build_pair(n: int, m: int, seed: int) -> tuple[Any, Any]:
    base = nx.barabasi_albert_graph(n, m, seed=seed)
    for u, v in base.edges():
        base[u][v]["weight"] = float((u * 131 + v * 17) % 97) / 7.0 + 1.0
    graph = fnx.Graph()
    graph.add_nodes_from(base.nodes())
    graph.add_edges_from((u, v, dict(data)) for u, v, data in base.edges(data=True))
    return graph, base


def sparse_digest(matrix: Any) -> str:
    csr = matrix.tocsr()
    csr.sort_indices()
    hasher = hashlib.sha256()
    hasher.update(np.asarray(csr.shape, dtype=np.int64).tobytes())
    hasher.update(csr.dtype.str.encode())
    hasher.update(np.asarray(csr.indptr).tobytes())
    hasher.update(np.asarray(csr.indices).tobytes())
    hasher.update(np.ascontiguousarray(csr.data).tobytes())
    return hasher.hexdigest()


def measure(
    case: str,
    impl: str,
    graph: Any,
    module: Any,
    repeats: int,
) -> dict[str, Any]:
    func = CASE_FUNCS[case]
    result = func(module, graph)
    digest = sparse_digest(result)
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = func(module, graph)
        samples.append(time.perf_counter() - start)
    return {
        "case": case,
        "impl": impl,
        "repeats": repeats,
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "max_sec": max(samples),
        "samples_sec": samples,
        "digest": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("sample", "profile"))
    parser.add_argument("--case", choices=sorted(CASE_FUNCS), default="to_scipy_default")
    parser.add_argument("--impl", choices=("fnx", "nx", "both"), default="fnx")
    parser.add_argument("--n", type=int, default=8000)
    parser.add_argument("--m", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--profile-output", default="")
    parser.add_argument("--profile-limit", type=int, default=80)
    args = parser.parse_args()

    fnx_graph, nx_graph = build_pair(args.n, args.m, args.seed)
    targets = []
    if args.impl in {"fnx", "both"}:
        targets.append(("fnx", fnx, fnx_graph))
    if args.impl in {"nx", "both"}:
        targets.append(("nx", nx, nx_graph))

    for impl_name, module, graph in targets:
        CASE_FUNCS[args.case](module, graph)
        if args.mode == "profile":
            profiler = cProfile.Profile()
            profiler.enable()
            record = measure(args.case, impl_name, graph, module, args.repeats)
            profiler.disable()
            stream = io.StringIO()
            pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(
                "cumtime"
            ).print_stats(args.profile_limit)
            if args.profile_output:
                Path(args.profile_output).write_text(stream.getvalue(), encoding="utf-8")
            else:
                print(stream.getvalue())
        else:
            record = measure(args.case, impl_name, graph, module, args.repeats)
        record.update({"n": args.n, "m": args.m, "seed": args.seed})
        print(json.dumps(record, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
