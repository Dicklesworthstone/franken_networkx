#!/usr/bin/env python3
"""Current-head generator routing harness.

Run with PYTHONPATH pointing at an extracted release wheel for the exact commit
under test. The script compares observable graph payloads against NetworkX and
profiles the FrankenNetworkX side only after digest parity is known.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import pstats
import statistics
import sys
import time
from collections.abc import Callable
from io import StringIO
from typing import Any

import franken_networkx as fnx
import networkx as nx


CaseFunc = Callable[[Any], Any]


def _digest_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _graph_payload(value: Any) -> dict[str, Any]:
    return {
        "nodes": [
            [node, {key: attrs[key] for key in sorted(attrs)}]
            for node, attrs in value.nodes(data=True)
        ],
        "edges": [list(edge) for edge in value.edges()],
        "node_count": value.number_of_nodes(),
        "edge_count": value.number_of_edges(),
    }


def _case_table(module: Any) -> dict[str, CaseFunc]:
    return {
        "random_powerlaw_tree": lambda mod=module: mod.random_powerlaw_tree(
            300, gamma=3, seed=5, tries=1000
        ),
        "random_lobster_graph": lambda mod=module: mod.random_lobster_graph(
            800, 0.35, 0.7, seed=11
        ),
        "duplication_divergence_graph": lambda mod=module: mod.duplication_divergence_graph(
            800, 0.4, seed=7
        ),
        "random_geometric_graph": lambda mod=module: mod.random_geometric_graph(
            800, 0.08, seed=3
        ),
    }


def _run_case(impl: str, case: str) -> Any:
    module = fnx if impl == "fnx" else nx
    return _case_table(module)[case]()


def _time_case(impl: str, case: str, loops: int) -> dict[str, Any]:
    timings = []
    payload_digest = None
    edge_count = None
    node_count = None
    for _ in range(loops):
        start = time.perf_counter()
        value = _run_case(impl, case)
        timings.append(time.perf_counter() - start)
        payload = _graph_payload(value)
        payload_digest = _digest_payload(payload)
        edge_count = payload["edge_count"]
        node_count = payload["node_count"]
    return {
        "best_s": min(timings),
        "edge_count": edge_count,
        "impl": impl,
        "loops": loops,
        "mean_s": statistics.fmean(timings),
        "median_s": statistics.median(timings),
        "node_count": node_count,
        "sha256": payload_digest,
        "timings_s": timings,
    }


def command_sweep(args: argparse.Namespace) -> int:
    rows = []
    for case in sorted(_case_table(fnx)):
        fnx_row = _time_case("fnx", case, args.loops)
        nx_row = _time_case("nx", case, args.loops)
        rows.append(
            {
                "case": case,
                "digests_match": fnx_row["sha256"] == nx_row["sha256"],
                "fnx": fnx_row,
                "fnx_over_nx_median": fnx_row["median_s"] / nx_row["median_s"],
                "nx": nx_row,
            }
        )
    print(json.dumps({"impl": "current-head generator routing", "rows": rows}, sort_keys=True))
    return 0


def command_profile(args: argparse.Namespace) -> int:
    before_payload = _graph_payload(_run_case("fnx", args.case))
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.loops):
        value = _run_case("fnx", args.case)
    profiler.disable()
    after_payload = _graph_payload(value)
    if before_payload != after_payload:
        print("non-deterministic payload", file=sys.stderr)
        return 1
    out = StringIO()
    pstats.Stats(profiler, stream=out).sort_stats("cumtime").print_stats(args.limit)
    print(
        "case="
        + args.case
        + " sha256="
        + _digest_payload(after_payload)
        + "\n"
        + out.getvalue()
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sweep = sub.add_parser("sweep")
    sweep.add_argument("--loops", type=int, default=7)
    sweep.set_defaults(func=command_sweep)

    profile = sub.add_parser("profile")
    profile.add_argument("case", choices=sorted(_case_table(fnx)))
    profile.add_argument("--loops", type=int, default=20)
    profile.add_argument("--limit", type=int, default=40)
    profile.set_defaults(func=command_profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
