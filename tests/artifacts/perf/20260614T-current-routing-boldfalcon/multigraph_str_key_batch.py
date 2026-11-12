#!/usr/bin/env python3
"""Proof and timing harness for br-r37-c1-04z53.80."""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import time
from collections.abc import Callable
from io import StringIO
from typing import Any

import franken_networkx as fnx
import networkx as nx


class KeySubclass(str):
    pass


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _payload(graph: Any) -> dict[str, Any]:
    return {
        "adj": [
            [
                node,
                [
                    [
                        nbr,
                        [
                            [key, {name: data[name] for name in sorted(data)}]
                            for key, data in graph[node][nbr].items()
                        ],
                    ]
                    for nbr in graph[node]
                ],
            ]
            for node in graph
        ],
        "edges": [
            [u, v, key, {name: data[name] for name in sorted(data)}]
            for u, v, key, data in graph.edges(keys=True, data=True)
        ],
        "nodes": list(graph.nodes(data=True)),
    }


def _make_graph(module: Any, case: str, size: int) -> Any:
    graph = module.MultiGraph()
    if case == "string_keys":
        graph.add_edges_from((i, i + 1, f"k{i}") for i in range(size))
    elif case == "string_keys_list":
        graph.add_edges_from([(i, i + 1, f"k{i}") for i in range(size)])
    elif case == "duplicate_key_merge":
        graph.add_edges_from([(0, 1, "k"), (0, 1, "k")])
    elif case == "with_global_attr":
        graph.add_edges_from([(i, i + 1, f"k{i}") for i in range(size)], color="red")
    elif case == "with_data_dict":
        graph.add_edges_from([(i, i + 1, f"k{i}", {"w": i % 7}) for i in range(size)])
    elif case == "dictable_third_is_data":
        graph.add_edges_from([(0, 1, (("w", 1),)), (1, 2, (("w", 2),))])
    elif case == "empty_string_is_data":
        graph.add_edges_from([(0, 1, ""), (1, 2, "")])
    elif case == "str_subclass_key":
        graph.add_edges_from([(0, 1, KeySubclass("k0")), (1, 2, KeySubclass("k1"))])
    elif case == "node_only_existing":
        graph.add_nodes_from([(0, {"color": "zero"}), (1, {"color": "one"})])
        graph.add_edges_from([(0, 1, "k0"), (1, 2, "k1")])
    elif case == "nonfresh_append":
        graph.add_edge(-1, 0, key="seed")
        graph.add_edges_from([(i, i + 1, f"k{i}") for i in range(size)])
    elif case == "tuple_input":
        graph.add_edges_from(tuple((i, i + 1, f"k{i}") for i in range(size)))
    else:
        raise ValueError(case)
    return graph


def _cases(size: int) -> list[tuple[str, int]]:
    small = min(size, 16)
    return [
        ("string_keys", size),
        ("string_keys_list", size),
        ("duplicate_key_merge", small),
        ("with_global_attr", small),
        ("with_data_dict", small),
        ("dictable_third_is_data", small),
        ("empty_string_is_data", small),
        ("str_subclass_key", small),
        ("node_only_existing", small),
        ("nonfresh_append", small),
        ("tuple_input", small),
    ]


def command_golden(args: argparse.Namespace) -> int:
    rows = []
    for case, case_size in _cases(args.size):
        fnx_payload = _payload(_make_graph(fnx, case, case_size))
        nx_payload = _payload(_make_graph(nx, case, case_size))
        rows.append(
            {
                "case": case,
                "fnx": fnx_payload,
                "match": fnx_payload == nx_payload,
                "nx": nx_payload,
                "size": case_size,
            }
        )
    bundle = {
        "ordering_tie_rng_fp": {
            "floating_point": "not applicable; integer node labels and string keys",
            "ordering": "node, adjacency, edge, and key iteration order are byte-compared",
            "rng": "not used",
            "tie_breaking": "duplicate explicit-key merge and dictable-third data cases compare exact key/data result",
        },
        "rows": rows,
    }
    bundle["bundle_sha256"] = _digest(bundle["rows"])
    print(json.dumps(bundle, sort_keys=True))
    return 0 if all(row["match"] for row in rows) else 1


def _time(factory: Callable[[], Any], repeats: int) -> dict[str, Any]:
    samples = []
    digest = ""
    for _ in range(repeats):
        start = time.perf_counter()
        graph = factory()
        samples.append(time.perf_counter() - start)
        digest = _digest(_payload(graph))
    return {
        "digest": digest,
        "max_s": max(samples),
        "mean_s": statistics.fmean(samples),
        "median_s": statistics.median(samples),
        "min_s": min(samples),
        "repeats": repeats,
        "samples_s": samples,
    }


def command_bench(args: argparse.Namespace) -> int:
    module = fnx if args.impl == "fnx" else nx
    stats = _time(lambda: _make_graph(module, args.case, args.size), args.repeats)
    stats.update({"case": args.case, "impl": args.impl, "size": args.size})
    print(json.dumps(stats, sort_keys=True))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.repeats):
        graph = _make_graph(fnx, args.case, args.size)
    profiler.disable()
    out = StringIO()
    pstats.Stats(profiler, stream=out).strip_dirs().sort_stats("cumtime").print_stats(args.limit)
    print("case=" + args.case + " sha256=" + _digest(_payload(graph)) + "\n" + out.getvalue())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--size", type=int, default=50000)
    golden.set_defaults(func=command_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("--case", default="string_keys_list")
    bench.add_argument("--impl", choices=("fnx", "nx"), required=True)
    bench.add_argument("--size", type=int, default=50000)
    bench.add_argument("--repeats", type=int, default=7)
    bench.set_defaults(func=command_bench)

    profile = sub.add_parser("profile")
    profile.add_argument("--case", default="string_keys_list")
    profile.add_argument("--size", type=int, default=50000)
    profile.add_argument("--repeats", type=int, default=5)
    profile.add_argument("--limit", type=int, default=50)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
