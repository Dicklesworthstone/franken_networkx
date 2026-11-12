#!/usr/bin/env python3
"""Focused proof and benchmark for MultiGraph string-key edge batches."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from io import StringIO
from typing import Any

import franken_networkx as fnx
import networkx as nx


class Label(str):
    pass


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _value_payload(value: Any) -> dict[str, str]:
    return {
        "repr": repr(value),
        "type": f"{type(value).__module__}.{type(value).__qualname__}",
    }


def _attrs_payload(attrs: dict[Any, Any]) -> list[tuple[dict[str, str], dict[str, str]]]:
    rows = [(_value_payload(key), _value_payload(value)) for key, value in attrs.items()]
    rows.sort(key=lambda row: (row[0]["type"], row[0]["repr"]))
    return rows


def _graph_payload(graph: Any) -> dict[str, Any]:
    return {
        "edge_count": graph.number_of_edges(),
        "edges": [
            [
                _value_payload(u),
                _value_payload(v),
                _value_payload(key),
                _attrs_payload(attrs),
            ]
            for u, v, key, attrs in graph.edges(keys=True, data=True)
        ],
        "node_count": graph.number_of_nodes(),
        "nodes": [_value_payload(node) for node in graph.nodes()],
    }


def _unique_edges(size: int) -> list[tuple[int, int, str]]:
    return [(i, i + 1, f"k{i}") for i in range(size)]


def _case_edges(name: str, size: int) -> Any:
    if name == "unique_path":
        return _unique_edges(size)
    if name == "parallel_keys":
        return [(0, 1, "a"), (0, 1, "b"), (1, 0, "c"), (2, 2, "loop"), (2, 2, "loop2")]
    if name == "duplicate_public_key":
        return [(0, 1, "a"), (1, 0, "a"), (0, 1, "b")]
    if name == "empty_string_data":
        return [(0, 1, ""), (1, 2, "ok")]
    if name == "str_subclass":
        return [(0, 1, Label("a")), (1, 2, Label("b"))]
    if name == "tuple_input":
        return tuple(_unique_edges(min(size, 128)))
    if name == "large_int_endpoint":
        base = 1 << 80
        return [(base, base + 1, "huge"), (base + 1, base + 2, "next")]
    if name == "bool_endpoint":
        return [(True, 2, "bool"), (1, 2, "int")]
    if name == "negative_endpoint":
        return [(-i, -(i + 1), f"k{i}") for i in range(size)]
    raise ValueError(name)


def build_graph(impl: str, case: str, size: int) -> Any:
    mod = fnx if impl == "fnx" else nx
    graph = mod.MultiGraph()
    if case == "non_fresh":
        graph.add_edge(100, 101, key="seed")
        graph.add_edges_from(_unique_edges(min(size, 128)))
        return graph
    graph.add_edges_from(_case_edges(case, size))
    return graph


def command_golden(args: argparse.Namespace) -> int:
    rows = []
    for case in CASES:
        records = []
        for impl in ("fnx", "nx"):
            graph = build_graph(impl, case, args.size)
            payload = _graph_payload(graph)
            records.append({"digest": _digest(payload), "impl": impl, "payload": payload})
        rows.append(
            {
                "case": case,
                "digests_match": records[0]["digest"] == records[1]["digest"],
                "records": records,
            }
        )
    bundle = {
        "cases": rows,
        "isomorphism": {
            "floating_point": "not used by this construction path",
            "golden_sha256": "bundle rows are byte-stable JSON with type/repr payloads",
            "ordering": "node order and edges(keys=True,data=True) order are compared exactly",
            "rng": "not used by this deterministic construction path",
            "tie_breaking": "parallel edge key order and duplicate public key fallback are compared exactly",
        },
    }
    bundle["bundle_sha256"] = _digest(bundle["cases"])
    print(json.dumps(bundle, sort_keys=True, indent=2))
    return 0 if all(row["digests_match"] for row in rows) else 1


def command_direct(args: argparse.Namespace) -> int:
    samples = []
    payload = None
    for _ in range(args.loops):
        start = time.perf_counter()
        graph = build_graph(args.impl, args.case, args.size)
        samples.append(time.perf_counter() - start)
        payload = _graph_payload(graph)
    result = {
        "case": args.case,
        "digest": _digest(payload),
        "impl": args.impl,
        "loops": args.loops,
        "max_sec": max(samples),
        "mean_sec": statistics.fmean(samples),
        "median_sec": statistics.median(samples),
        "min_sec": min(samples),
        "samples_sec": samples,
        "size": args.size,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def command_once(args: argparse.Namespace) -> int:
    payload = None
    for _ in range(args.loops):
        payload = _graph_payload(build_graph(args.impl, args.case, args.size))
    print(_digest(payload))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.loops):
        graph = build_graph(args.impl, args.case, args.size)
    profiler.disable()
    out = StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumtime").print_stats(args.limit)
    payload = _graph_payload(graph)
    print(
        "case="
        + args.case
        + " impl="
        + args.impl
        + " sha256="
        + _digest(payload)
        + "\n"
        + out.getvalue()
    )
    return 0


CASES = (
    "unique_path",
    "parallel_keys",
    "duplicate_public_key",
    "empty_string_data",
    "str_subclass",
    "tuple_input",
    "large_int_endpoint",
    "bool_endpoint",
    "negative_endpoint",
    "non_fresh",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--size", type=int, default=257)
    golden.set_defaults(func=command_golden)

    direct = sub.add_parser("direct")
    direct.add_argument("--impl", choices=("fnx", "nx"), required=True)
    direct.add_argument("--case", choices=CASES, default="unique_path")
    direct.add_argument("--size", type=int, default=50000)
    direct.add_argument("--loops", type=int, default=7)
    direct.set_defaults(func=command_direct)

    once = sub.add_parser("once")
    once.add_argument("--impl", choices=("fnx", "nx"), required=True)
    once.add_argument("--case", choices=CASES, default="unique_path")
    once.add_argument("--size", type=int, default=50000)
    once.add_argument("--loops", type=int, default=1)
    once.set_defaults(func=command_once)

    profile = sub.add_parser("profile")
    profile.add_argument("--impl", choices=("fnx", "nx"), default="fnx")
    profile.add_argument("--case", choices=CASES, default="unique_path")
    profile.add_argument("--size", type=int, default=50000)
    profile.add_argument("--loops", type=int, default=5)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
