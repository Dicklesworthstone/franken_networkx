#!/usr/bin/env python3
"""Baseline/golden harness for br-r37-c1-2a00r DiGraph edge-view guards."""

from __future__ import annotations

import argparse
import cProfile
import gc
import hashlib
import io
import json
import os
import pstats
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("NETWORKX_AUTOMATIC_BACKENDS", "")

import networkx as nx

import franken_networkx as fnx

try:
    nx.config.backend_priority = []
except Exception:
    pass


NODE_COUNT = 5_000
EDGE_COUNT = 40_000
EDGE_SPAN = 8


def deterministic_edges():
    edges = []
    for u in range(NODE_COUNT):
        for span in range(1, EDGE_SPAN + 1):
            v = (u + span) % NODE_COUNT
            w = ((u * 1_315_423_911) ^ (v * 2_654_435_761) ^ span) & 0xFFFF
            edges.append((u, v, {"w": w}))
    assert len(edges) == EDGE_COUNT
    return edges


EDGES = deterministic_edges()


def build_graph(mod):
    graph = mod.DiGraph()
    graph.add_nodes_from(range(NODE_COUNT))
    graph.add_edges_from(EDGES)
    return graph


def normalize(value):
    if isinstance(value, tuple):
        return [normalize(item) for item in value]
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize(value[key]) for key in sorted(value)}
    return value


def stable_bytes(value) -> bytes:
    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def sha256_hex(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def capture_call(fn):
    try:
        return {"kind": "ok", "value": normalize(fn())}
    except Exception as exc:
        return {
            "kind": "err",
            "type": type(exc).__name__,
            "message": str(exc),
        }


def target_cases():
    return {
        "edges": lambda graph: list(graph.edges()),
        "edges_data_true": lambda graph: list(graph.edges(data=True)),
        "edges_data_w": lambda graph: list(graph.edges(data="w")),
        "out_edges_data_true": lambda graph: list(graph.out_edges(data=True)),
        "edges_data_view_w": lambda graph: list(graph.edges.data("w")),
    }


def run_case(graph, case):
    return target_cases()[case](graph)


def mutation_graph(mod):
    graph = mod.DiGraph()
    graph.add_nodes_from(range(8))
    for u, v in (
        (0, 1),
        (0, 2),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (6, 7),
    ):
        graph.add_edge(u, v, w=(u * 17) + v)
    return graph


def mutation_cases():
    def node_add(graph):
        iterator = iter(graph.edges())
        first = next(iterator)
        graph.add_node(99)
        second = next(iterator)
        return [first, second]

    def edge_add(graph):
        iterator = iter(graph.edges())
        first = next(iterator)
        graph.add_edge(0, 7, w=7)
        second = next(iterator)
        return [first, second]

    def edge_remove_add_same_count(graph):
        iterator = iter(graph.edges())
        first = next(iterator)
        graph.remove_edge(0, 2)
        graph.add_edge(7, 0, w=119)
        second = next(iterator)
        return [first, second]

    def edge_attr_update_data_view(graph):
        iterator = iter(graph.edges(data=True))
        first = next(iterator)
        graph[0][1]["w"] = 999
        second = next(iterator)
        return [first, second]

    return {
        "node_add_after_edges_iter": {
            "fn": node_add,
            "compare_to_networkx": False,
            "fnx_expected": {
                "kind": "err",
                "type": "RuntimeError",
                "message": "dictionary changed size during iteration",
            },
            "reason": (
                "Current FNX guard_edge_count=True watches nodes_seq and raises "
                "on node structural mutation; NetworkX permits isolated node "
                "mutations during DiGraph edge iteration."
            ),
        },
        "edge_add_after_edges_iter": {
            "fn": edge_add,
            "compare_to_networkx": True,
        },
        "edge_remove_add_same_count_after_edges_iter": {
            "fn": edge_remove_add_same_count,
            "compare_to_networkx": True,
        },
        "edge_attr_update_after_edges_data_iter": {
            "fn": edge_attr_update_data_view,
            "compare_to_networkx": True,
        },
    }


def percentile(values, pct):
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * pct)))
    return ordered[index]


def summarize_samples(samples, loops):
    return {
        "seconds": samples,
        "median": statistics.median(samples),
        "mean": statistics.mean(samples),
        "p95": percentile(samples, 0.95),
        "per_call_median_ms": statistics.median(samples) * 1_000 / loops,
        "per_call_mean_ms": statistics.mean(samples) * 1_000 / loops,
    }


def bench_one(which, graph, case, loops, repeats, warmup_calls):
    for _ in range(warmup_calls):
        run_case(graph, case)
    samples = []
    checksum = 0
    for _ in range(repeats):
        gc.collect()
        start = time.perf_counter()
        for _ in range(loops):
            result = run_case(graph, case)
            checksum += len(result)
        samples.append(time.perf_counter() - start)
    row = summarize_samples(samples, loops)
    row.update({"which": which, "case": case, "checksum": checksum})
    return row


def loop_one(which, case, loops, warmup_calls):
    graph = build_graph(fnx if which == "fnx" else nx)
    for _ in range(warmup_calls):
        run_case(graph, case)
    checksum = 0
    for _ in range(loops):
        checksum += len(run_case(graph, case))
    print(checksum)
    return 0


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(data)
    return data


def cmd_golden(args):
    nx_graph = build_graph(nx)
    fnx_graph = build_graph(fnx)
    edge_cases = []
    for name in target_cases():
        nx_value = run_case(nx_graph, name)
        fnx_value = run_case(fnx_graph, name)
        nx_blob = stable_bytes(nx_value)
        fnx_blob = stable_bytes(fnx_value)
        edge_cases.append(
            {
                "case": name,
                "length": len(fnx_value),
                "byte_equal": nx_blob == fnx_blob,
                "nx_sha256": sha256_hex(nx_blob),
                "fnx_sha256": sha256_hex(fnx_blob),
                "first_3": normalize(fnx_value[:3]),
                "last_3": normalize(fnx_value[-3:]),
            }
        )

    mutation_rows = []
    for name, spec in mutation_cases().items():
        nx_observed = capture_call(lambda spec=spec: spec["fn"](mutation_graph(nx)))
        fnx_observed = capture_call(lambda spec=spec: spec["fn"](mutation_graph(fnx)))
        row = {
            "case": name,
            "compare_to_networkx": spec["compare_to_networkx"],
            "nx": nx_observed,
            "fnx": fnx_observed,
        }
        if spec["compare_to_networkx"]:
            row["match"] = nx_observed == fnx_observed
        else:
            row["fnx_obligation_match"] = fnx_observed == spec["fnx_expected"]
            row["fnx_expected"] = spec["fnx_expected"]
            row["reason"] = spec["reason"]
        mutation_rows.append(row)

    payload = {
        "metadata": {
            "bead": "br-r37-c1-2a00r",
            "target": "combined _FailFastEdgeIterator guard-token residual",
            "python": sys.version,
            "networkx_version": nx.__version__,
            "franken_networkx_file": getattr(fnx, "__file__", None),
            "graph": {
                "kind": "DiGraph",
                "nodes": NODE_COUNT,
                "edges": EDGE_COUNT,
                "construction": "circulant directed edge list, span 1..8, stable insertion order, int attr w",
            },
        },
        "edge_output_cases": edge_cases,
        "mutation_cases": mutation_rows,
        "isomorphism_obligations": {
            "ordering": "Exact node-major, successor-insertion edge order compared by byte hash against NetworkX for all timed edge-view cases.",
            "tie_breaking": "N/A: edge-view drain has no algorithmic tie-break beyond insertion order.",
            "floating_point": "N/A: integer node ids and integer edge attribute w only.",
            "rng": "N/A: graph construction is deterministic and seed-free.",
            "guard_semantics": "Future guard-token lever must preserve current FNX RuntimeError behavior for nodes_seq/edges_seq changes and attr-only non-structural updates.",
        },
    }
    payload["all_edge_outputs_byte_equal"] = all(
        row["byte_equal"] for row in edge_cases
    )
    payload["all_compared_mutations_match"] = all(
        row.get("match", True) for row in mutation_rows
    )
    payload["fnx_current_guard_obligations_pass"] = all(
        row.get("fnx_obligation_match", True) for row in mutation_rows
    )
    payload["all_match"] = (
        payload["all_edge_outputs_byte_equal"]
        and payload["all_compared_mutations_match"]
        and payload["fnx_current_guard_obligations_pass"]
    )

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["bundle_sha256"] = sha256_hex(canonical)
    written = write_json(args.output, payload)
    file_sha = sha256_hex(written)
    args.sha_output.write_text(f"{file_sha}  {args.output.name}\n", encoding="utf-8")
    return 0 if payload["all_match"] else 1


def cmd_bench(args):
    cases = list(target_cases()) if args.case == "all" else [args.case]
    which_values = ("fnx", "nx") if args.which == "both" else (args.which,)
    graphs = {
        "fnx": build_graph(fnx),
        "nx": build_graph(nx),
    }
    rows = []
    for which in which_values:
        for case in cases:
            rows.append(
                bench_one(
                    which,
                    graphs[which],
                    case,
                    args.loops,
                    args.repeats,
                    args.warmup_calls,
                )
            )
    by_case = {}
    for case in cases:
        fnx_row = next((row for row in rows if row["which"] == "fnx" and row["case"] == case), None)
        nx_row = next((row for row in rows if row["which"] == "nx" and row["case"] == case), None)
        if fnx_row is not None and nx_row is not None:
            by_case[case] = {
                "fnx_over_nx_median": fnx_row["median"] / nx_row["median"],
                "fnx_over_nx_mean": fnx_row["mean"] / nx_row["mean"],
                "fnx_median_ms": fnx_row["per_call_median_ms"],
                "nx_median_ms": nx_row["per_call_median_ms"],
            }
    payload = {
        "metadata": {
            "bead": "br-r37-c1-2a00r",
            "loops": args.loops,
            "repeats": args.repeats,
            "warmup_calls": args.warmup_calls,
            "graph": {"nodes": NODE_COUNT, "edges": EDGE_COUNT},
        },
        "rows": rows,
        "comparisons": by_case,
    }
    write_json(args.output, payload)
    return 0


def cmd_loop(args):
    return loop_one(args.which, args.case, args.loops, args.warmup_calls)


def cmd_profile(args):
    graph = build_graph(fnx if args.which == "fnx" else nx)
    cases = list(target_cases()) if args.case == "all" else [args.case]
    for case in cases:
        for _ in range(args.warmup_calls):
            run_case(graph, case)

    profiler = cProfile.Profile()
    checksum = 0
    profiler.enable()
    for _ in range(args.loops):
        for case in cases:
            checksum += len(run_case(graph, case))
    profiler.disable()

    output = io.StringIO()
    print(
        f"bead=br-r37-c1-2a00r which={args.which} cases={cases} loops={args.loops} checksum={checksum}",
        file=output,
    )
    print(
        f"graph=DiGraph nodes={NODE_COUNT} edges={EDGE_COUNT} warmup_calls={args.warmup_calls}",
        file=output,
    )
    stats = pstats.Stats(profiler, stream=output)
    stats.sort_stats("cumtime").print_stats(args.limit)
    print("\n--- tottime ---", file=output)
    stats.sort_stats("tottime").print_stats(args.limit)

    interesting = []
    for (filename, lineno, funcname), values in stats.stats.items():
        if (
            "_FailFastEdgeIterator" in funcname
            or funcname == "_gen"
            or "nodes_seq" in funcname
            or "edges_seq" in funcname
            or "EdgeView" in funcname
            or "_guarded_edge_list" in funcname
        ):
            cc, nc, tt, ct, _callers = values
            interesting.append(
                {
                    "filename": filename,
                    "line": lineno,
                    "function": funcname,
                    "primitive_calls": cc,
                    "total_calls": nc,
                    "tottime": tt,
                    "cumtime": ct,
                }
            )
    print("\n--- guard-token relevant frames ---", file=output)
    for row in sorted(interesting, key=lambda item: item["cumtime"], reverse=True):
        print(json.dumps(row, sort_keys=True), file=output)

    args.output.write_text(output.getvalue(), encoding="utf-8")
    return 0


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_report(args):
    golden = _load_json(args.golden)
    direct = _load_json(args.direct)
    hyperfine = _load_json(args.hyperfine)
    profile_text = args.profile.read_text(encoding="utf-8")

    hf_rows = []
    for result in hyperfine.get("results", []):
        command = result.get("command", "")
        mean = result.get("mean")
        median = result.get("median")
        hf_rows.append((command, mean, median))

    lines = [
        "# Guard Token EdgeView Baseline",
        "",
        "Bead: `br-r37-c1-2a00r`",
        "",
        "## Workload",
        "",
        f"- DiGraph nodes: `{NODE_COUNT}`",
        f"- DiGraph edges: `{EDGE_COUNT}`",
        "- Deterministic directed circulant insertion order, spans `1..8`, integer edge attr `w`.",
        "- Timed consumers: `list(DG.edges())`, `list(DG.edges(data=True))`, `list(DG.edges(data=\"w\"))`, `list(DG.out_edges(data=True))`, `list(DG.edges.data(\"w\"))`.",
        "",
        "## Golden",
        "",
        f"- Golden bundle SHA: `{golden['bundle_sha256']}`",
        f"- Golden file SHA: `{args.golden_sha.read_text(encoding='utf-8').split()[0]}`",
        f"- Edge outputs byte-equal FNX vs NetworkX: `{golden['all_edge_outputs_byte_equal']}`",
        f"- Compared structural edge mutations match NetworkX: `{golden['all_compared_mutations_match']}`",
        f"- FNX current node/edge guard obligations pass: `{golden['fnx_current_guard_obligations_pass']}`",
        "",
        "## Direct Timing",
        "",
        "| Case | FNX median ms | NX median ms | FNX/NX median | FNX mean ms | NX mean ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    row_lookup = {(row["which"], row["case"]): row for row in direct["rows"]}
    for case in target_cases():
        fnx_row = row_lookup[("fnx", case)]
        nx_row = row_lookup[("nx", case)]
        ratio = fnx_row["median"] / nx_row["median"]
        lines.append(
            "| {case} | {fm:.6f} | {nm:.6f} | {ratio:.3f}x | {fmean:.6f} | {nmean:.6f} |".format(
                case=case,
                fm=fnx_row["per_call_median_ms"],
                nm=nx_row["per_call_median_ms"],
                ratio=ratio,
                fmean=fnx_row["per_call_mean_ms"],
                nmean=nx_row["per_call_mean_ms"],
            )
        )

    lines.extend(
        [
            "",
            "## Hyperfine",
            "",
            "| Command | Mean s | Median s |",
            "| --- | ---: | ---: |",
        ]
    )
    for command, mean, median in hf_rows:
        lines.append(f"| `{command}` | {mean:.6f} | {median:.6f} |")

    guard_lines = [
        line
        for line in profile_text.splitlines()
        if "_FailFastEdgeIterator" in line
        or '"function": "_gen"' in line
        or "nodes_seq" in line
        or "edges_seq" in line
    ]
    lines.extend(
        [
            "",
            "## Profile Evidence",
            "",
            "cProfile still attributes a material share of FNX edge-view drain time to the `_FailFastEdgeIterator` generator frame. The combined profile also shows `_native_edges_data_key` as the largest frame for the `data=\"w\"` consumers, so the hotspot has partly shifted there; the guard-token lever remains the common residual across guarded drains but will not by itself fix the native data-key materializer.",
            "",
            "The two guarded structural-token property reads are not broken out as Python functions, but the `_gen` frame below is the loop containing the current `nodes_seq` and `edges_seq` checks.",
            "",
            "```text",
        ]
    )
    lines.extend(guard_lines[:12] if guard_lines else ["No guard-token frames matched the profile filter."])
    lines.extend(
        [
            "```",
            "",
            "## Isomorphism Obligations",
            "",
            "- Ordering: preserve byte-identical node-major/successor-insertion edge order for all five consumers.",
            "- Tie-breaking: N/A beyond insertion order.",
            "- Floating point: N/A.",
            "- RNG: N/A, deterministic graph.",
            "- Guard behavior: preserve FNX current `RuntimeError(\"dictionary changed size during iteration\")` on structural node/edge token changes with `guard_edge_count=True`; preserve attr-only updates as non-structural.",
            "",
            "## Opportunity Score",
            "",
            "- Proposed single lever: add one PyO3 getter returning a packed `(nodes_seq, edges_seq)` guard token for DiGraph/Graph/Multi* and make `_FailFastEdgeIterator` compare one token per yielded edge when `guard_edge_count=True`.",
            "- Impact: `3` (all guarded edge-view drains, strongest on `edges()` and `_EdgeListWithSetAlgebra` consumers).",
            "- Confidence: `4` (profile still lands in the guard generator and bead history isolated this residual after materialization wins).",
            "- Effort: `2` (one Rust getter family plus one Python guard branch and focused property tests).",
            "- Score: `6.0`; still above the `>=2.0` threshold for an implementation pass.",
            "",
            "## Future Implementation Surface",
            "",
            "- `python/franken_networkx/__init__.py`: `_FailFastEdgeIterator` guard capture/compare branch.",
            "- `crates/fnx-python/src/digraph.rs`: `PyDiGraph`/`PyMultiDiGraph` combined guard-token getter.",
            "- `crates/fnx-python/src/lib.rs`: `PyGraph`/`PyMultiGraph` combined guard-token getter if the lever is generalized to all guarded edge consumers.",
        ]
    )
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    golden = sub.add_parser("golden")
    golden.add_argument("--output", type=Path, required=True)
    golden.add_argument("--sha-output", type=Path, required=True)
    golden.set_defaults(func=cmd_golden)

    bench = sub.add_parser("bench")
    bench.add_argument("--which", choices=("fnx", "nx", "both"), default="both")
    bench.add_argument("--case", choices=tuple(target_cases()) + ("all",), default="all")
    bench.add_argument("--loops", type=int, default=5)
    bench.add_argument("--repeats", type=int, default=15)
    bench.add_argument("--warmup-calls", type=int, default=2)
    bench.add_argument("--output", type=Path, required=True)
    bench.set_defaults(func=cmd_bench)

    loop = sub.add_parser("loop")
    loop.add_argument("--which", choices=("fnx", "nx"), required=True)
    loop.add_argument("--case", choices=tuple(target_cases()), required=True)
    loop.add_argument("--loops", type=int, default=10)
    loop.add_argument("--warmup-calls", type=int, default=2)
    loop.set_defaults(func=cmd_loop)

    profile = sub.add_parser("profile")
    profile.add_argument("--which", choices=("fnx", "nx"), default="fnx")
    profile.add_argument("--case", choices=tuple(target_cases()) + ("all",), default="all")
    profile.add_argument("--loops", type=int, default=20)
    profile.add_argument("--warmup-calls", type=int, default=2)
    profile.add_argument("--limit", type=int, default=40)
    profile.add_argument("--output", type=Path, required=True)
    profile.set_defaults(func=cmd_profile)

    report = sub.add_parser("report")
    report.add_argument("--golden", type=Path, required=True)
    report.add_argument("--golden-sha", type=Path, required=True)
    report.add_argument("--direct", type=Path, required=True)
    report.add_argument("--hyperfine", type=Path, required=True)
    report.add_argument("--profile", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
