#!/usr/bin/env python3
"""Baseline/proof harness for br-r37-c1-pyun7 current-flow betweenness."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import math
import pstats
import statistics
import time
from collections.abc import Mapping

import networkx as nx

import franken_networkx as fnx


def _nx_graph(case: str) -> nx.Graph:
    if case == "path_8":
        return nx.path_graph(8)
    if case == "cycle_10":
        return nx.cycle_graph(10)
    if case == "complete_7":
        return nx.complete_graph(7)
    if case == "watts_40":
        return nx.watts_strogatz_graph(40, 6, 0.2, seed=17)
    if case == "watts_120":
        return nx.watts_strogatz_graph(120, 6, 0.2, seed=17)
    if case == "watts_180":
        return nx.watts_strogatz_graph(180, 6, 0.2, seed=17)
    raise ValueError(f"unknown case {case!r}")


def _fnx_graph(nx_graph: nx.Graph):
    graph = fnx.Graph()
    graph.add_nodes_from(nx_graph.nodes())
    graph.add_edges_from(nx_graph.edges())
    return graph


def _graph(case: str, impl: str):
    graph = _nx_graph(case)
    if not nx.is_connected(graph):
        raise RuntimeError(f"case {case} is unexpectedly disconnected")
    return graph if impl == "nx" else _fnx_graph(graph)


def _call(impl: str, algo: str, case: str, normalized: bool):
    mod = nx if impl == "nx" else fnx
    graph = _graph(case, impl)
    if algo == "node":
        return mod.current_flow_betweenness_centrality(
            graph, normalized=normalized, solver="full"
        )
    if algo == "edge":
        return mod.edge_current_flow_betweenness_centrality(
            graph, normalized=normalized, solver="full"
        )
    raise ValueError(f"unknown algo {algo!r}")


def _key_text(key) -> str:
    if isinstance(key, (tuple, list)):
        return "(" + ",".join(_key_text(item) for item in key) + ")"
    if isinstance(key, frozenset):
        return "{" + ",".join(sorted(_key_text(item) for item in key)) + "}"
    return repr(key)


def _canonical_mapping(value: Mapping) -> list[list[str]]:
    rows = []
    for key, val in value.items():
        canonical_key = frozenset(key) if isinstance(key, tuple) else key
        rows.append([_key_text(canonical_key), format(float(val), ".17g")])
    rows.sort(key=lambda item: item[0])
    return rows


def _sha(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def proof() -> None:
    cases = ["path_8", "cycle_10", "complete_7", "watts_40"]
    algos = ["node", "edge"]
    normalized_values = [True, False]
    records = []
    max_abs = 0.0
    max_rel = 0.0
    all_close = True
    for case in cases:
        for algo in algos:
            for normalized in normalized_values:
                expected = _call("nx", algo, case, normalized)
                actual = _call("fnx", algo, case, normalized)
                nx_rows = _canonical_mapping(expected)
                fnx_rows = _canonical_mapping(actual)
                nx_keys = [row[0] for row in nx_rows]
                fnx_keys = [row[0] for row in fnx_rows]
                if nx_keys != fnx_keys:
                    all_close = False
                diffs = []
                for (_, nx_value), (_, fnx_value) in zip(nx_rows, fnx_rows):
                    expected_float = float(nx_value)
                    actual_float = float(fnx_value)
                    abs_diff = abs(actual_float - expected_float)
                    rel_diff = abs_diff / max(abs(expected_float), 1.0)
                    max_abs = max(max_abs, abs_diff)
                    max_rel = max(max_rel, rel_diff)
                    diffs.append(abs_diff)
                    if not math.isclose(
                        actual_float,
                        expected_float,
                        rel_tol=1e-5,
                        abs_tol=1e-7,
                    ):
                        all_close = False
                records.append(
                    {
                        "case": case,
                        "algo": algo,
                        "normalized": normalized,
                        "keys_sha256": _sha(fnx_keys),
                        "fnx_sha256": _sha(fnx_rows),
                        "nx_sha256": _sha(nx_rows),
                        "max_case_abs": max(diffs) if diffs else 0.0,
                        "key_count": len(fnx_rows),
                    }
                )
    payload = {
        "all_close": all_close,
        "max_abs": max_abs,
        "max_rel": max_rel,
        "tolerance": {"rel": 1e-5, "abs": 1e-7},
        "records": records,
    }
    payload["sha256"] = _sha(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def direct(impl: str, algo: str, case: str, normalized: bool, repeat: int) -> None:
    values = []
    result_sha = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = _call(impl, algo, case, normalized)
        values.append(time.perf_counter() - start)
        result_sha = _sha(_canonical_mapping(result))
    payload = {
        "impl": impl,
        "algo": algo,
        "case": case,
        "normalized": normalized,
        "repeat": repeat,
        "times": values,
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.mean(values),
        "result_sha256": result_sha,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def profile(impl: str, algo: str, case: str, normalized: bool, repeat: int) -> None:
    _call(impl, algo, case, normalized)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeat):
        _call(impl, algo, case, normalized)
    profiler.disable()
    output = io.StringIO()
    stats = pstats.Stats(profiler, stream=output).sort_stats("cumulative")
    stats.print_stats(80)
    print(output.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("proof")
    for name in ("direct", "profile"):
        p = sub.add_parser(name)
        p.add_argument("--impl", choices=["fnx", "nx"], required=True)
        p.add_argument("--algo", choices=["node", "edge"], required=True)
        p.add_argument("--case", required=True)
        p.add_argument("--normalized", action="store_true", default=False)
        p.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    if args.cmd == "proof":
        proof()
    elif args.cmd == "direct":
        direct(args.impl, args.algo, args.case, args.normalized, args.repeat)
    elif args.cmd == "profile":
        profile(args.impl, args.algo, args.case, args.normalized, args.repeat)


if __name__ == "__main__":
    main()
