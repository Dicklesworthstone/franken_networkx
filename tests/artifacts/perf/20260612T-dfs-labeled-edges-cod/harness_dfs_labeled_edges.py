#!/usr/bin/env python3
import argparse
import cProfile
import hashlib
import importlib
import json
import os
import pstats
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PYTHON_DIR = ROOT / "python"
LEGACY_NX = ROOT / "legacy_networkx_code"


def preload_candidate_extension() -> None:
    candidate = os.environ.get("CANDIDATE_FNX_SO")
    if not candidate:
        return
    import importlib.util

    spec = importlib.util.spec_from_file_location("franken_networkx._fnx", candidate)
    module = importlib.util.module_from_spec(spec)
    sys.modules["franken_networkx._fnx"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)


def import_modules():
    sys.path.insert(0, str(PYTHON_DIR))
    sys.path.insert(0, str(LEGACY_NX))
    preload_candidate_extension()
    fnx = importlib.import_module("franken_networkx")
    nx = importlib.import_module("networkx")
    return fnx, nx


def make_graphs(mod):
    base = mod.watts_strogatz_graph(200, 6, 0.17, seed=20260612)
    directed = mod.DiGraph()
    directed.add_nodes_from(base.nodes())
    directed.add_edges_from(base.edges())
    directed.add_edges_from((v, u) for u, v in list(base.edges())[::3])
    return {
        "ws200": base,
        "digraph_ws200": directed,
        "depth3": base,
        "source17": base,
    }


def materialize(mod, graph, case):
    if case == "depth3":
        return list(mod.dfs_labeled_edges(graph, depth_limit=3))
    if case == "source17":
        return list(mod.dfs_labeled_edges(graph, source=17))
    return list(mod.dfs_labeled_edges(graph))


def normalize(events):
    return [[repr(u), repr(v), label] for u, v, label in events]


def digest_payload(payload) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def proof(args):
    fnx, nx = import_modules()
    fnx_graphs = make_graphs(fnx)
    nx_graphs = make_graphs(nx)
    cases = ["ws200", "digraph_ws200", "depth3", "source17"]
    rows = []
    for case in cases:
        fnx_events = normalize(materialize(fnx, fnx_graphs[case], case))
        nx_events = normalize(materialize(nx, nx_graphs[case], case))
        rows.append(
            {
                "case": case,
                "fnx_digest": digest_payload(fnx_events),
                "nx_digest": digest_payload(nx_events),
                "match": fnx_events == nx_events,
                "event_count": len(fnx_events),
                "first_events": fnx_events[:8],
                "last_events": fnx_events[-8:],
            }
        )
    payload = {
        "all_match": all(row["match"] for row in rows),
        "cases": rows,
        "combined_fnx_digest": digest_payload([row["fnx_digest"] for row in rows]),
        "combined_nx_digest": digest_payload([row["nx_digest"] for row in rows]),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["all_match"] else 1


def bench(args):
    fnx, _ = import_modules()
    graph = make_graphs(fnx)[args.case]
    for _ in range(args.warmups):
        materialize(fnx, graph, args.case)
    samples = []
    result_len = None
    for _ in range(args.samples):
        start = time.perf_counter()
        for _ in range(args.calls):
            result_len = len(materialize(fnx, graph, args.case))
        samples.append((time.perf_counter() - start) / args.calls)
    payload = {
        "case": args.case,
        "calls": args.calls,
        "samples": samples,
        "mean": statistics.mean(samples),
        "median": statistics.median(samples),
        "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "result_len": result_len,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


def profile(args):
    fnx, _ = import_modules()
    graph = make_graphs(fnx)[args.case]
    profiler = cProfile.Profile()
    profiler.enable()
    total = 0
    for _ in range(args.calls):
        total += len(materialize(fnx, graph, args.case))
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats("cumtime")
    if args.prof:
        stats.dump_stats(args.prof)
    stats.print_stats(args.limit)
    print(json.dumps({"case": args.case, "calls": args.calls, "total_events": total}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    proof_parser = sub.add_parser("proof")
    proof_parser.set_defaults(func=proof)

    bench_parser = sub.add_parser("bench")
    bench_parser.add_argument("--case", default="ws200")
    bench_parser.add_argument("--calls", type=int, default=200)
    bench_parser.add_argument("--samples", type=int, default=7)
    bench_parser.add_argument("--warmups", type=int, default=2)
    bench_parser.set_defaults(func=bench)

    profile_parser = sub.add_parser("profile")
    profile_parser.add_argument("--case", default="ws200")
    profile_parser.add_argument("--calls", type=int, default=200)
    profile_parser.add_argument("--limit", type=int, default=20)
    profile_parser.add_argument("--prof")
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
