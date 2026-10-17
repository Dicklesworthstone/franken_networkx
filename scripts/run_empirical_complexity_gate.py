#!/usr/bin/env python3
"""Empirical Computational Complexity Catalogue & Slope Gate (wvztf.2).

Implements trend-prof style empirical complexity measurement (Goldsmith, Aiken &
Wilkerson, FSE 2007) across sparse constant-degree graph families at multiple
scales N in {500, 2000, 8000, 32000} ("scale the parent, not the request").

Combines:
1. Load-independent deterministic CPython `sys.monitoring` bytecode instruction
   and call counts (`inst_count`) for Python-level paths.
2. Same-process interleaved wall-clock timing (`wall_ns`) + Rust/C extension
   work detection so O(N) loops inside native extensions (such as `copy.copy(G)`
   prior to yr2oc.3) are caught alongside Python-level O(N) scans.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

import franken_networkx as fnx  # noqa: E402
import networkx as nx  # noqa: E402

DEFAULT_SIZES = (500, 2000, 8000, 32000)
SLOPE_TOLERANCE = 0.15

# Allowlist of known open asymptotic-complexity debt, keyed by (op_id, graph_class) -> bead_id.
# When yr2oc.3 lands, copy_shallow flips green and this entry must be removed.
KNOWN_COMPLEXITY_DEBT_ALLOWLIST: dict[tuple[str, str], str] = {
    ("copy_shallow", "Graph"): "br-r37-c1-epic-storage-architecture-yr2oc.3",
    ("copy_shallow", "DiGraph"): "br-r37-c1-epic-storage-architecture-yr2oc.3",
    ("copy_shallow", "MultiGraph"): "br-r37-c1-epic-storage-architecture-yr2oc.3",
    ("copy_shallow", "MultiDiGraph"): "br-r37-c1-epic-storage-architecture-yr2oc.3",
}


def compute_so_sha256() -> str:
    so_path = Path(fnx._fnx.__file__)
    return hashlib.sha256(so_path.read_bytes()).hexdigest()


def fit_log_log_slope(xs: list[float] | tuple[int, ...], ys: list[float]) -> tuple[float, float]:
    """Fit log(y) = a + b * log(x) and return (slope b, R^2)."""
    lx = [math.log(max(float(x), 1.0)) for x in xs]
    ly = [math.log(max(float(y), 1.0)) for y in ys]
    n = len(lx)
    mx = sum(lx) / n
    my = sum(ly) / n
    num = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
    den_x = sum((x - mx) ** 2 for x in lx)
    den_y = sum((y - my) ** 2 for y in ly)
    if den_x <= 1e-15:
        return 0.0, 1.0
    slope = num / den_x
    r2 = (num * num) / (den_x * den_y) if den_y > 1e-15 else 1.0
    return slope, r2


def count_python_events(fn: Callable[[], Any]) -> int:
    """Deterministic load-independent CPython 3.12+ sys.monitoring instruction + frame counter."""
    tool_id = 4
    events = sys.monitoring.events
    mask = events.INSTRUCTION | events.PY_START
    count = 0

    def _cb(*_args: Any) -> Any:
        nonlocal count
        count += 1

    sys.monitoring.use_tool_id(tool_id, "fnx_complexity_gate")
    try:
        sys.monitoring.register_callback(tool_id, events.INSTRUCTION, _cb)
        sys.monitoring.register_callback(tool_id, events.PY_START, _cb)
        sys.monitoring.set_events(tool_id, mask)
        fn()
        sys.monitoring.set_events(tool_id, 0)
    finally:
        sys.monitoring.register_callback(tool_id, events.INSTRUCTION, None)
        sys.monitoring.register_callback(tool_id, events.PY_START, None)
        sys.monitoring.free_tool_id(tool_id)
    return count


def build_sparse_ring_chord_pair(cls_name: str, n: int) -> tuple[Any, Any]:
    """Build identical sparse constant-degree (deg=4) fnx and nx graphs of size n."""
    edges = [(i, (i + 1) % n, {"weight": 1.0}) for i in range(n)] + [
        (i, (i + 7) % n, {"weight": 2.0}) for i in range(n)
    ]
    fg = getattr(fnx, cls_name)()
    ng = getattr(nx, cls_name)()
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng


def measure_op_across_scales(
    op_id: str,
    cls_name: str,
    theoretical_max_slope: float,
    runner_factory: Callable[[Any, int], Callable[[], Any]],
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    iters: int = 15,
    mutates_graph: bool = False,
) -> dict[str, Any]:
    fnx_inst_series: list[int] = []
    nx_inst_series: list[int] = []
    fnx_wall_series: list[float] = []
    nx_wall_series: list[float] = []

    for n in sizes:
        fg, ng = build_sparse_ring_chord_pair(cls_name, n)
        fnx_op = runner_factory(fg, n)
        nx_op = runner_factory(ng, n)
        # Warm up caches/views once so one-time initialization is not conflated with per-op complexity
        fnx_op()
        nx_op()

        fnx_inst = count_python_events(fnx_op)
        nx_inst = count_python_events(nx_op)
        fnx_inst_series.append(max(fnx_inst, 1))
        nx_inst_series.append(max(nx_inst, 1))

        # Interleaved same-process timing
        fnx_samples: list[float] = []
        nx_samples: list[float] = []
        trials = 3
        per_trial = max(1, iters // trials)
        for _ in range(trials):
            t0 = time.perf_counter_ns()
            for _ in range(per_trial):
                fnx_op()
            t1 = time.perf_counter_ns()
            for _ in range(per_trial):
                nx_op()
            t2 = time.perf_counter_ns()
            fnx_samples.append((t1 - t0) / per_trial)
            nx_samples.append((t2 - t1) / per_trial)
        fnx_samples.sort()
        nx_samples.sort()
        fnx_wall_series.append(fnx_samples[len(fnx_samples) // 2])
        nx_wall_series.append(nx_samples[len(nx_samples) // 2])

    fnx_inst_slope, fnx_inst_r2 = fit_log_log_slope(sizes, [float(x) for x in fnx_inst_series])
    nx_inst_slope, nx_inst_r2 = fit_log_log_slope(sizes, [float(x) for x in nx_inst_series])
    fnx_wall_slope, fnx_wall_r2 = fit_log_log_slope(sizes, fnx_wall_series)
    nx_wall_slope, nx_wall_r2 = fit_log_log_slope(sizes, nx_wall_series)

    # Effective empirical slope:
    # - Load-independent Python instruction slope is primary.
    # - When a call executes inside a C/Rust extension (constant Python instructions)
    #   but performs an O(N) native loop (high R^2 wall-time growth of >10x across 64x N
    #   and >50us at largest N), capture the native slope so C/Rust O(N) bugs like
    #   unshared copy.copy(G) cannot hide behind a single PyO3 call boundary.
    native_loop_detected = (
        abs(fnx_inst_slope) < 0.05
        and fnx_wall_r2 >= 0.92
        and fnx_wall_series[-1] >= 50_000.0
        and (fnx_wall_series[-1] / max(fnx_wall_series[0], 1.0)) >= 12.0
    )
    fnx_effective_slope = fnx_wall_slope if native_loop_detected else fnx_inst_slope
    nx_native_loop = (
        abs(nx_inst_slope) < 0.05
        and nx_wall_r2 >= 0.92
        and nx_wall_series[-1] >= 50_000.0
        and (nx_wall_series[-1] / max(nx_wall_series[0], 1.0)) >= 12.0
    )
    nx_effective_slope = (
        max(nx_wall_slope, nx_inst_slope)
        if (native_loop_detected or nx_native_loop)
        else nx_inst_slope
    )

    budget = max(nx_effective_slope, theoretical_max_slope) + SLOPE_TOLERANCE
    raw_pass = fnx_effective_slope <= budget
    debt_bead = KNOWN_COMPLEXITY_DEBT_ALLOWLIST.get((op_id, cls_name))

    if raw_pass:
        status = "PASS"
    elif debt_bead is not None:
        status = "ALLOWLISTED_DEBT"
    else:
        status = "FAIL"

    return {
        "op_id": op_id,
        "graph_class": cls_name,
        "theoretical_max_slope": theoretical_max_slope,
        "sizes": list(sizes),
        "fnx_inst_counts": fnx_inst_series,
        "nx_inst_counts": nx_inst_series,
        "fnx_wall_ns_median": [round(x, 1) for x in fnx_wall_series],
        "nx_wall_ns_median": [round(x, 1) for x in nx_wall_series],
        "fnx_inst_slope": round(fnx_inst_slope, 4),
        "nx_inst_slope": round(nx_inst_slope, 4),
        "fnx_wall_slope": round(fnx_wall_slope, 4),
        "nx_wall_slope": round(nx_wall_slope, 4),
        "fnx_effective_slope": round(fnx_effective_slope, 4),
        "nx_effective_slope": round(nx_effective_slope, 4),
        "slope_budget": round(budget, 4),
        "native_loop_detected": native_loop_detected,
        "raw_pass": raw_pass,
        "allowlisted_debt_bead": debt_bead,
        "status": status,
    }


def build_catalogue_specs() -> list[tuple[str, tuple[str, ...], float, Callable[[Any, int], Callable[[], Any]], int]]:
    all_classes = ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph")

    def _remove_node_runner(g: Any, n: int) -> Callable[[], Any]:
        cursor = n // 3

        def _step() -> None:
            nonlocal cursor
            target = cursor % n
            cursor += 1
            if g.has_node(target):
                g.remove_node(target)

        return _step

    def _add_remove_edge_runner(g: Any, n: int) -> Callable[[], Any]:
        u = n // 2
        w = (u + 13) % n

        def _step() -> None:
            g.add_edge(u, w, weight=1.0)
            g.remove_edge(u, w)

        return _step

    return [
        ("has_node", all_classes, 0.0, lambda g, n: (lambda u=n // 2: u in g), 30),
        ("has_edge", all_classes, 0.0, lambda g, n: (lambda u=n // 2, v=(n // 2 + 1) % n: g.has_edge(u, v)), 30),
        ("getitem_row", all_classes, 0.0, lambda g, n: (lambda u=n // 2: g[u]), 30),
        ("getitem_cell", all_classes, 0.0, lambda g, n: (lambda u=n // 2, v=(n // 2 + 1) % n: g[u][v]), 30),
        ("get_edge_data", all_classes, 0.0, lambda g, n: (lambda u=n // 2, v=(n // 2 + 1) % n: g.get_edge_data(u, v)), 30),
        ("degree_u", all_classes, 0.0, lambda g, n: (lambda u=n // 2: g.degree(u)), 30),
        ("neighbors_u", all_classes, 0.0, lambda g, n: (lambda u=n // 2: list(g.neighbors(u))), 30),
        ("edges_nbunch", all_classes, 0.0, lambda g, n: (lambda u=n // 2: list(g.edges([u]))), 25),
        ("subgraph_pair", all_classes, 0.0, lambda g, n: (lambda u=n // 2, v=(n // 2 + 1) % n: len(g.subgraph([u, v]))), 20),
        ("add_remove_edge", all_classes, 0.0, _add_remove_edge_runner, 20),
        ("remove_node", all_classes, 0.0, _remove_node_runner, 20),
        ("copy_shallow", all_classes, 0.0, lambda g, _n: (lambda: copy.copy(g)), 6),
        ("copy_deep", ("Graph", "DiGraph"), 1.0, lambda g, _n: (lambda: g.copy()), 3),
        ("to_directed", ("Graph",), 1.0, lambda g, _n: (lambda: g.to_directed()), 3),
        (
            "connected_components",
            ("Graph",),
            1.0,
            lambda g, _n: (
                (lambda: list(fnx.connected_components(g)))
                if isinstance(g, fnx.Graph)
                else (lambda: list(nx.connected_components(g)))
            ),
            3,
        ),
        (
            "shortest_path_length_single_source",
            ("Graph", "DiGraph"),
            1.0,
            lambda g, _n: (
                (lambda: fnx.single_source_shortest_path_length(g, 0))
                if type(g).__module__.startswith("franken_networkx")
                else (lambda: nx.single_source_shortest_path_length(g, 0))
            ),
            3,
        ),
    ]


def run_catalogue(
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    disallow_allowlist: bool = False,
) -> dict[str, Any]:
    so_sha256 = compute_so_sha256()
    rows: list[dict[str, Any]] = []
    jsonl_records: list[dict[str, Any]] = []
    failures: list[str] = []
    stale_allowlist: list[str] = []

    for op_id, classes, theoretical_max_slope, factory, iters in build_catalogue_specs():
        for cls_name in classes:
            t0 = time.perf_counter()
            row = measure_op_across_scales(
                op_id=op_id,
                cls_name=cls_name,
                theoretical_max_slope=theoretical_max_slope,
                runner_factory=factory,
                sizes=sizes,
                iters=iters,
            )
            duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            if disallow_allowlist and not row["raw_pass"]:
                row["status"] = "FAIL"
            if row["status"] == "FAIL":
                failures.append(
                    f"{op_id}[{cls_name}]: fnx_effective_slope={row['fnx_effective_slope']} > budget={row['slope_budget']}"
                )
            if row["allowlisted_debt_bead"] and row["raw_pass"]:
                stale_allowlist.append(
                    f"{op_id}[{cls_name}] ({row['allowlisted_debt_bead']}) now passes (slope={row['fnx_effective_slope']}) — remove from KNOWN_COMPLEXITY_DEBT_ALLOWLIST"
                )
            rows.append(row)

            case_id = f"complexity_slope::{op_id}::{cls_name}"
            input_sha = hashlib.sha256(f"{case_id}:{sizes}".encode("utf-8")).hexdigest()
            passed = row["status"] in ("PASS", "ALLOWLISTED_DEBT")
            record: dict[str, Any] = {
                "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
                "case_id": case_id,
                "input_sha256": input_sha,
                "fnx_version": getattr(fnx, "__version__", "0.1.0"),
                "nx_version": nx.__version__,
                "so_sha256": so_sha256,
                "graph_class": cls_name,
                "construction_path": "add_edges_from(sparse_ring_chord_deg4)",
                "expected": f"slope <= {row['slope_budget']} (theoretical <= {theoretical_max_slope})",
                "actual": {
                    "fnx_effective_slope": row["fnx_effective_slope"],
                    "nx_effective_slope": row["nx_effective_slope"],
                    "status": row["status"],
                },
                "pass": passed,
                "duration_ms": duration_ms,
            }
            if not passed:
                record["reproducer"] = (
                    f"python3 scripts/run_empirical_complexity_gate.py --disallow-allowlist # failed on {case_id}"
                )
            jsonl_records.append(record)

    return {
        "schema_version": "1.0.0",
        "report_id": "empirical-complexity-catalogue-v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "so_sha256": so_sha256,
        "sizes": list(sizes),
        "slope_tolerance": SLOPE_TOLERANCE,
        "summary": {
            "total_cases": len(rows),
            "passed_green": sum(1 for r in rows if r["status"] == "PASS"),
            "allowlisted_debt": sum(1 for r in rows if r["status"] == "ALLOWLISTED_DEBT"),
            "failed": len(failures),
            "stale_allowlist": len(stale_allowlist),
        },
        "failures": failures,
        "stale_allowlist": stale_allowlist,
        "rows": rows,
        "jsonl_records": jsonl_records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Empirical Computational Complexity Catalogue (wvztf.2)",
        "",
        f"- **Generated (UTC):** `{report['generated_at_utc']}`",
        f"- **Loaded `_fnx.abi3.so` SHA256:** `{report['so_sha256']}`",
        f"- **Scales (`N`):** `{report['sizes']}` (sparse degree-4 ring+chord family, fixed request size)",
        f"- **Slope Tolerance:** `+{report['slope_tolerance']}` over `max(nx_slope, theoretical_max_slope)`",
        f"- **Summary:** `{report['summary']['passed_green']}` green, `{report['summary']['allowlisted_debt']}` allowlisted open debt, `{report['summary']['failed']}` failed",
        "",
        "| Operation | Class | Theoretical | `fnx` Inst Slope | `nx` Inst Slope | `fnx` Wall Slope | Effective Slope | Budget | Status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in report["rows"]:
        status_cell = r["status"]
        if r["allowlisted_debt_bead"]:
            status_cell = f"`{r['status']}` (`{r['allowlisted_debt_bead']}`)"
        else:
            status_cell = f"`{r['status']}`"
        lines.append(
            f"| `{r['op_id']}` | `{r['graph_class']}` | `{r['theoretical_max_slope']:.2f}` | "
            f"`{r['fnx_inst_slope']:+.3f}` | `{r['nx_inst_slope']:+.3f}` | "
            f"`{r['fnx_wall_slope']:+.3f}` | `{r['fnx_effective_slope']:+.3f}` | "
            f"`{r['slope_budget']:+.3f}` | {status_cell} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPO_ROOT / "artifacts/perf/latest/empirical_complexity_catalogue_v1.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=REPO_ROOT / "artifacts/perf/latest/empirical_complexity_catalogue_v1.md",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=REPO_ROOT / "artifacts/perf/latest/empirical_complexity_e2e.jsonl",
    )
    parser.add_argument(
        "--disallow-allowlist",
        action="store_true",
        help="Fail closed on allowlisted complexity debt items as well.",
    )
    args = parser.parse_args()

    report = run_catalogue(disallow_allowlist=args.disallow_allowlist)
    jsonl_records = report.pop("jsonl_records")

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    args.output_jsonl.write_text(
        "\n".join(json.dumps(rec, sort_keys=True) for rec in jsonl_records) + "\n",
        encoding="utf-8",
    )

    if report["failures"] or report["stale_allowlist"]:
        for msg in report["failures"] + report["stale_allowlist"]:
            print(f"COMPLEXITY GATE FAILURE: {msg}", file=sys.stderr)
        return 1

    print(
        f"EMPIRICAL COMPLEXITY GATE PASSED: {report['summary']['passed_green']} green, "
        f"{report['summary']['allowlisted_debt']} allowlisted debt "
        f"(artefact: {args.output_json})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
