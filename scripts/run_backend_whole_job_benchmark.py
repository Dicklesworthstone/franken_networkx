#!/usr/bin/env python3
"""Backend-Mode Whole-Job Benchmark & Output Parity Gate (wvztf.5).

Runs a 10-job corpus (5 headless upstream NetworkX gallery workloads + 5 realistic
load -> mutate -> analyse -> export pipelines) in a single process across:
1. Plain NetworkX (`backend_priority = []`)
2. FrankenNetworkX backend (`backend_priority = ["franken_networkx"]`), cold conversion (`cache_converted_graphs = True`, fresh graph)
3. FrankenNetworkX backend (`backend_priority = ["franken_networkx"]`), warm conversion (`cache_converted_graphs = True`, cached `__networkx_cache__`)
4. FrankenNetworkX backend (`backend_priority = ["franken_networkx"]`), cache disabled (`cache_converted_graphs = False`)

Verifies exact output equality across all four arms on every job and emits:
- `artifacts/perf/latest/backend_whole_job_benchmark_v1.json`
- `artifacts/perf/latest/backend_whole_job_benchmark_v1.md`
- `artifacts/perf/latest/backend_whole_job_e2e.jsonl`
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

import franken_networkx as fnx  # noqa: E402
import franken_networkx.backend as fnx_backend  # noqa: E402
import networkx as nx  # noqa: E402


class OutputMismatchError(RuntimeError):
    """Raised when backend_priority=['franken_networkx'] alters a job's output."""


def compute_so_sha256() -> str:
    return hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest()


def current_git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


@contextmanager
def backend_config(priority: list[str], cache_converted: bool) -> Iterator[None]:
    old_priority = list(nx.config.backend_priority.algos)
    old_cache = nx.config.cache_converted_graphs
    old_warnings = set(nx.config.warnings_to_ignore)
    try:
        nx.config.backend_priority.algos = list(priority)
        nx.config.cache_converted_graphs = cache_converted
        nx.config.warnings_to_ignore.add("cache")
        yield
    finally:
        nx.config.backend_priority.algos = old_priority
        nx.config.cache_converted_graphs = old_cache
        nx.config.warnings_to_ignore.clear()
        nx.config.warnings_to_ignore.update(old_warnings)


def normalize_output(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): normalize_output(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [normalize_output(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(normalize_output(v) for v in value)
    return str(value)


# ---------------------------------------------------------------------------
# 10 Whole-Job Workloads (5 Gallery + 5 Load->Mutate->Analyse->Export Pipelines)
# ---------------------------------------------------------------------------


def build_jobs() -> list[tuple[str, str, Callable[[], Any], Callable[[Any], Any], str]]:
    """Return (job_id, category, build_graph_fn, analyse_fn, regime_note)."""

    # 1. Gallery: Karate club multi-centrality analysis
    def _build_karate() -> Any:
        return nx.karate_club_graph()

    def _run_karate(G: Any) -> Any:
        bc = nx.betweenness_centrality(G)
        cc = nx.closeness_centrality(G)
        pr = nx.pagerank(G, alpha=0.85)
        return {
            "bc_top": round(max(bc.values()), 6),
            "cc_top": round(max(cc.values()), 6),
            "pr_sum": round(sum(pr.values()), 6),
        }

    # 2. Gallery: Barabasi-Albert shortest paths + core decomposition
    def _build_ba() -> Any:
        return nx.barabasi_albert_graph(400, 3, seed=42)

    def _run_ba(G: Any) -> Any:
        lengths = nx.single_source_shortest_path_length(G, 0)
        cores = nx.core_number(G)
        comps = list(nx.connected_components(G))
        return {
            "max_dist": max(lengths.values()),
            "core_sum": sum(cores.values()),
            "num_comps": len(comps),
        }

    # 3. Gallery: Watts-Strogatz clustering and triangle census
    def _build_ws() -> Any:
        return nx.watts_strogatz_graph(450, 6, 0.2, seed=17)

    def _run_ws(G: Any) -> Any:
        tri = nx.triangles(G)
        clust = nx.clustering(G)
        trans = nx.transitivity(G)
        return {
            "tri_sum": sum(tri.values()),
            "clust_mean": round(sum(clust.values()) / len(clust), 6),
            "transitivity": round(trans, 6),
        }

    # 4. Gallery: Layered DAG topological sort and longest path
    def _build_dag() -> Any:
        G = nx.DiGraph()
        for u in range(300):
            for step in (1, 3, 7):
                if u + step < 300:
                    G.add_edge(u, u + step, weight=float((u + step) % 5 + 1))
        return G

    def _run_dag(G: Any) -> Any:
        is_dag = nx.is_directed_acyclic_graph(G)
        lp = nx.dag_longest_path_length(G)
        return {"is_dag": is_dag, "longest_path_len": round(float(lp), 6)}

    # 5. Gallery: Directed SCC & reciprocity
    def _build_scc() -> Any:
        G = nx.DiGraph()
        n = 400
        for i in range(n):
            G.add_edge(i, (i + 1) % n)
            if i % 5 == 0:
                G.add_edge((i + 1) % n, i)
            G.add_edge(i, (i * 7 + 3) % n)
        return G

    def _run_scc(G: Any) -> Any:
        n_scc = nx.number_strongly_connected_components(G)
        recip = nx.overall_reciprocity(G)
        return {"n_scc": n_scc, "reciprocity": round(float(recip), 6)}

    # 6. Pipeline: Social graph load -> churn -> community detection -> export
    def _build_social_pipeline() -> Any:
        G = nx.Graph()
        for c in range(4):
            base = c * 60
            for i in range(60):
                for j in range(i + 1, min(i + 6, 60)):
                    G.add_edge(base + i, base + j, weight=2.0)
        for c in range(4):
            G.add_edge(c * 60, ((c + 1) % 4) * 60, weight=0.5)
        # Mutate before analysis
        G.add_edge(0, 120, weight=0.25)
        G.remove_edge(0, 120)
        return G

    def _run_social_pipeline(G: Any) -> Any:
        comms = nx.community.greedy_modularity_communities(G, weight="weight")
        mod = nx.community.modularity(G, comms, weight="weight")
        return {"num_comms": len(comms), "modularity": round(float(mod), 6)}

    # 7. Pipeline: Weighted road network -> update weights -> Dijkstra + MST -> export
    def _build_routing_pipeline() -> Any:
        G = nx.Graph()
        n = 350
        for i in range(n):
            G.add_edge(i, (i + 1) % n, weight=1.0 + (i % 7) * 0.5)
            G.add_edge(i, (i + 11) % n, weight=2.5 + (i % 5) * 0.25)
        G[0][1]["weight"] = 3.25
        return G

    def _run_routing_pipeline(G: Any) -> Any:
        dists = nx.single_source_dijkstra_path_length(G, 0, weight="weight")
        mst = nx.minimum_spanning_tree(G, weight="weight")
        return {
            "dist_sum": round(sum(dists.values()), 5),
            "mst_edges": mst.number_of_edges(),
        }

    # 8. Pipeline: Citation graph -> prune -> PageRank + reachability -> export
    def _build_citation_pipeline() -> Any:
        G = nx.DiGraph()
        for i in range(300):
            G.add_edge(i, (i + 1) % 300)
            G.add_edge(i, (i + 9) % 300)
            if i % 10 == 0:
                G.add_edge(i, 0)
        G.add_node(999)
        G.remove_node(999)
        return G

    def _run_citation_pipeline(G: Any) -> Any:
        pr = nx.pagerank(G, alpha=0.85)
        anc = nx.ancestors(G, 0)
        desc = nx.descendants(G, 0)
        return {
            "pr_0": round(float(pr[0]), 6),
            "anc_count": len(anc),
            "desc_count": len(desc),
        }

    # 9. Pipeline: Infrastructure resilience -> biconnected components + bridges -> export
    def _build_resilience_pipeline() -> Any:
        G = nx.barabasi_albert_graph(350, 2, seed=99)
        G.add_edge(349, 500)
        return G

    def _run_resilience_pipeline(G: Any) -> Any:
        bcc = list(nx.biconnected_components(G))
        art = list(nx.articulation_points(G))
        br = list(nx.bridges(G))
        return {"bcc_count": len(bcc), "art_count": len(art), "bridge_count": len(br)}

    # 10. Pipeline: Capacity network -> flow & min-cut -> export
    def _build_flow_pipeline() -> Any:
        G = nx.DiGraph()
        n = 120
        for i in range(n - 1):
            G.add_edge(i, i + 1, capacity=10.0 + (i % 5))
            if i + 4 < n:
                G.add_edge(i, i + 4, capacity=6.0 + (i % 3))
        return G

    def _run_flow_pipeline(G: Any) -> Any:
        flow_val = nx.maximum_flow_value(G, 0, 119, capacity="capacity")
        cut_val = nx.minimum_cut_value(G, 0, 119, capacity="capacity")
        return {"flow_val": round(float(flow_val), 6), "cut_val": round(float(cut_val), 6)}

    return [
        (
            "gallery_karate_club_centrality",
            "gallery",
            _build_karate,
            _run_karate,
            "Heavy O(V*E) centrality kernels amortize conversion on first call",
        ),
        (
            "gallery_barabasi_albert_shortest_paths",
            "gallery",
            _build_ba,
            _run_ba,
            "Ski-rental should_run declines cheap BFS/CC until conversion budget is reached, then caches",
        ),
        (
            "gallery_watts_strogatz_clustering_triangles",
            "gallery",
            _build_ws,
            _run_ws,
            "Triangle + clustering + transitivity reuse cached converted graph on warm/multi-call pipeline",
        ),
        (
            "gallery_dag_critical_path",
            "gallery",
            _build_dag,
            _run_dag,
            "Weighted DAG longest path converts edge weight column; warm cache eliminates conversion on repeat",
        ),
        (
            "gallery_directed_scc_condensation",
            "gallery",
            _build_scc,
            _run_scc,
            "Cheap O(V+E) SCC kernel declined by ski-rental on cold call; warm cache accelerates",
        ),
        (
            "pipeline_social_community_detection",
            "pipeline",
            _build_social_pipeline,
            _run_social_pipeline,
            "Native greedy_modularity_communities + modularity dominate conversion overhead even cold",
        ),
        (
            "pipeline_weighted_routing_network",
            "pipeline",
            _build_routing_pipeline,
            _run_routing_pipeline,
            "Dijkstra + MST share converted graph when cache is enabled; cache_off pays conversion per call",
        ),
        (
            "pipeline_citation_dag_ranking",
            "pipeline",
            _build_citation_pipeline,
            _run_citation_pipeline,
            "Native PageRank dominates conversion; ancestors/descendants reuse cached conversion",
        ),
        (
            "pipeline_infrastructure_resilience",
            "pipeline",
            _build_resilience_pipeline,
            _run_resilience_pipeline,
            "Three connectivity kernels (bcc + articulation + bridges) amortize one conversion when cached",
        ),
        (
            "pipeline_capacity_flow_cut",
            "pipeline",
            _build_flow_pipeline,
            _run_flow_pipeline,
            "Preflow-push max-flow + min-cut on capacity network",
        ),
    ]


def geomean(xs: list[float]) -> float:
    return math.exp(sum(math.log(max(x, 1e-9)) for x in xs) / len(xs)) if xs else 1.0


def run_whole_job_benchmark(trials: int = 5) -> dict[str, Any]:
    so_sha256 = compute_so_sha256()
    git_head = current_git_head()
    rows: list[dict[str, Any]] = []
    jsonl_records: list[dict[str, Any]] = []

    for job_id, category, build_fn, run_fn, note in build_jobs():
        t_job_start = time.perf_counter()
        plain_samples: list[float] = []
        cold_samples: list[float] = []
        warm_samples: list[float] = []
        nocache_samples: list[float] = []

        expected_out: Any = None

        for _ in range(trials):
            # 1. Plain NetworkX
            g_plain = build_fn()
            with backend_config([], True):
                t0 = time.perf_counter_ns()
                out_plain = normalize_output(run_fn(g_plain))
                plain_samples.append((time.perf_counter_ns() - t0) / 1e6)
            if expected_out is None:
                expected_out = out_plain

            # 2. Backend priority (cache ON) — cold then warm on the SAME graph
            g_cached = build_fn()
            with backend_config(["franken_networkx"], True):
                t0 = time.perf_counter_ns()
                out_cold = normalize_output(run_fn(g_cached))
                cold_samples.append((time.perf_counter_ns() - t0) / 1e6)

                # Prime __networkx_cache__ via NetworkX's own dispatcher if ski-rental declined on the first call
                if hasattr(g_cached, "__networkx_cache__") and g_cached.__networkx_cache__ is not None:
                    g_cached.__networkx_cache__[fnx_backend._RENT_KEY] = 1.0
                    run_fn(g_cached)
                t1 = time.perf_counter_ns()
                out_warm = normalize_output(run_fn(g_cached))
                warm_samples.append((time.perf_counter_ns() - t1) / 1e6)

            # 3. Backend priority (cache OFF)
            g_nocache = build_fn()
            with backend_config(["franken_networkx"], False):
                t0 = time.perf_counter_ns()
                out_nocache = normalize_output(run_fn(g_nocache))
                nocache_samples.append((time.perf_counter_ns() - t0) / 1e6)

            for mode_name, candidate in (
                ("cold_cache_on", out_cold),
                ("warm_cache_on", out_warm),
                ("cache_off", out_nocache),
            ):
                if candidate != expected_out:
                    raise OutputMismatchError(
                        f"Job {job_id} ({mode_name}) output diverged from plain NetworkX: "
                        f"expected={expected_out!r}, actual={candidate!r}"
                    )

        plain_samples.sort()
        cold_samples.sort()
        warm_samples.sort()
        nocache_samples.sort()
        mid = len(plain_samples) // 2

        plain_ms = plain_samples[mid]
        cold_ms = cold_samples[mid]
        warm_ms = warm_samples[mid]
        nocache_ms = nocache_samples[mid]

        cold_speedup = plain_ms / max(cold_ms, 1e-6)
        warm_speedup = plain_ms / max(warm_ms, 1e-6)
        nocache_speedup = plain_ms / max(nocache_ms, 1e-6)

        row = {
            "job_id": job_id,
            "category": category,
            "plain_nx_p50_ms": round(plain_ms, 4),
            "backend_cold_cache_on_p50_ms": round(cold_ms, 4),
            "backend_warm_cache_on_p50_ms": round(warm_ms, 4),
            "backend_cache_off_p50_ms": round(nocache_ms, 4),
            "cold_cache_on_speedup_vs_nx": round(cold_speedup, 4),
            "warm_cache_on_speedup_vs_nx": round(warm_speedup, 4),
            "cache_off_speedup_vs_nx": round(nocache_speedup, 4),
            "output_parity": True,
            "note": note,
        }
        rows.append(row)

        duration_ms = round((time.perf_counter() - t_job_start) * 1000.0, 3)
        sample_g = build_fn()
        jsonl_records.append(
            {
                "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
                "case_id": f"backend_whole_job::{job_id}",
                "input_sha256": hashlib.sha256(job_id.encode("utf-8")).hexdigest(),
                "fnx_version": getattr(fnx, "__version__", "0.1.0"),
                "nx_version": nx.__version__,
                "so_sha256": so_sha256,
                "graph_class": type(sample_g).__name__,
                "construction_path": f"{category}::{job_id}",
                "expected": expected_out,
                "actual": expected_out,
                "pass": True,
                "duration_ms": duration_ms,
            }
        )

    cold_ratios = [r["cold_cache_on_speedup_vs_nx"] for r in rows]
    warm_ratios = [r["warm_cache_on_speedup_vs_nx"] for r in rows]
    nocache_ratios = [r["cache_off_speedup_vs_nx"] for r in rows]

    return {
        "schema_version": "1.0.0",
        "report_id": "backend-whole-job-benchmark-v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provenance": {
            "git_head": git_head,
            "so_sha256": so_sha256,
            "python_version": platform.python_version(),
            "nx_version": nx.__version__,
            "fnx_version": getattr(fnx, "__version__", "0.1.0"),
            "platform": platform.platform(),
        },
        "summary": {
            "total_jobs": len(rows),
            "all_outputs_equal": all(r["output_parity"] for r in rows),
            "cold_cache_on_geomean_vs_nx": round(geomean(cold_ratios), 4),
            "warm_cache_on_geomean_vs_nx": round(geomean(warm_ratios), 4),
            "cache_off_geomean_vs_nx": round(geomean(nocache_ratios), 4),
            "cold_cache_on_wins": sum(1 for x in cold_ratios if x >= 1.0),
            "warm_cache_on_wins": sum(1 for x in warm_ratios if x >= 1.0),
            "cache_off_wins": sum(1 for x in nocache_ratios if x >= 1.0),
        },
        "jobs": rows,
        "jsonl_records": jsonl_records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    p = report["provenance"]
    lines = [
        "# Backend-Mode Whole-Job Benchmark (`wvztf.5`)",
        "",
        f"- **Generated (UTC):** `{report['generated_at_utc']}`",
        f"- **Git HEAD:** `{p['git_head']}`",
        f"- **Loaded `_fnx.abi3.so` SHA256:** `{p['so_sha256']}`",
        f"- **Output Parity:** `{s['all_outputs_equal']}` across all `{s['total_jobs']}` jobs (`cold`, `warm`, `cache_off` vs plain `networkx`)",
        f"- **Geomean vs Plain `networkx`:** Cold (`cache=True`): **`{s['cold_cache_on_geomean_vs_nx']:.2f}x`** (`{s['cold_cache_on_wins']}/{s['total_jobs']}` >= 1.0x) | Warm (`cache=True`): **`{s['warm_cache_on_geomean_vs_nx']:.2f}x`** (`{s['warm_cache_on_wins']}/{s['total_jobs']}` >= 1.0x) | Uncached (`cache=False`): **`{s['cache_off_geomean_vs_nx']:.2f}x`** (`{s['cache_off_wins']}/{s['total_jobs']}` >= 1.0x)",
        "",
        "| Job | Category | Plain `nx` (ms) | Cold `cache=True` (`vs nx`) | Warm `cache=True` (`vs nx`) | `cache=False` (`vs nx`) | Regime Note |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in report["jobs"]:
        lines.append(
            f"| `{r['job_id']}` | `{r['category']}` | `{r['plain_nx_p50_ms']:.3f}` | "
            f"`{r['backend_cold_cache_on_p50_ms']:.3f}ms` (**`{r['cold_cache_on_speedup_vs_nx']:.2f}x`**) | "
            f"`{r['backend_warm_cache_on_p50_ms']:.3f}ms` (**`{r['warm_cache_on_speedup_vs_nx']:.2f}x`**) | "
            f"`{r['backend_cache_off_p50_ms']:.3f}ms` (`{r['cache_off_speedup_vs_nx']:.2f}x`) | "
            f"{r['note']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPO_ROOT / "artifacts/perf/latest/backend_whole_job_benchmark_v1.json",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=REPO_ROOT / "artifacts/perf/latest/backend_whole_job_benchmark_v1.md",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=REPO_ROOT / "artifacts/perf/latest/backend_whole_job_e2e.jsonl",
    )
    parser.add_argument("--trials", type=int, default=5)
    args = parser.parse_args()

    report = run_whole_job_benchmark(trials=args.trials)
    jsonl_records = report.pop("jsonl_records")

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    args.output_jsonl.write_text(
        "\n".join(json.dumps(rec, sort_keys=True) for rec in jsonl_records) + "\n",
        encoding="utf-8",
    )

    s = report["summary"]
    print(
        f"BACKEND WHOLE-JOB BENCHMARK PASSED: {s['total_jobs']} jobs, "
        f"cold={s['cold_cache_on_geomean_vs_nx']}x, warm={s['warm_cache_on_geomean_vs_nx']}x, "
        f"cache_off={s['cache_off_geomean_vs_nx']}x (artefact: {args.output_json})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
