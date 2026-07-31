"""Whole-job graph-analytics pass: live NetworkX 3.6.1 vs FrankenNetworkX, same invocation.

This is a *job*, not a microbenchmark: one graph is loaded once and then carried
through a realistic analytics pipeline, with both engines running the identical
stage list on identical input in the same process. Every stage's output is
compared for byte-identical canonical form before any timing is reported.

Stages are ordered as an analyst would run them — structure, then centrality,
then distance — and each is timed separately so the pass shows *where* the job's
time actually goes rather than a single blended number.

usage: bench_analytics_pass.py <nodes> <edges> <seed> [--skip-slow]
"""

import importlib.util
import json
import os
import sys
import time

SPEC = importlib.util.spec_from_file_location("perf_harness", "scripts/perf_harness.py")
ph = importlib.util.module_from_spec(SPEC)
sys.modules["perf_harness"] = ph
SPEC.loader.exec_module(ph)

import networkx as nx  # noqa: E402
import franken_networkx as fnx  # noqa: E402


def stages(engine, graph, skip_slow):
    """The pipeline. Each entry is (name, callable, is_slow)."""
    items = [
        ("connected_components", lambda: [sorted(c) for c in engine.connected_components(graph)], False),
        ("core_number", lambda: engine.core_number(graph), False),
        ("triangles", lambda: engine.triangles(graph), False),
        ("average_clustering", lambda: round(engine.average_clustering(graph), 12), False),
        ("degree_assortativity", lambda: round(engine.degree_assortativity_coefficient(graph), 12), False),
        ("pagerank", lambda: {k: round(v, 12) for k, v in engine.pagerank(graph).items()}, False),
        ("closeness_centrality", lambda: {k: round(v, 12) for k, v in engine.closeness_centrality(graph).items()}, True),
        ("harmonic_centrality", lambda: {k: round(v, 12) for k, v in engine.harmonic_centrality(graph).items()}, True),
        ("betweenness_centrality", lambda: {k: round(v, 12) for k, v in engine.betweenness_centrality(graph).items()}, True),
        ("eccentricity", lambda: engine.eccentricity(graph), True),
        ("diameter", lambda: engine.diameter(graph), True),
    ]
    return [(n, f) for (n, f, slow) in items if not (slow and skip_slow)]


def main(argv):
    nodes = int(argv[1]) if len(argv) > 1 else 3_000
    edges = int(argv[2]) if len(argv) > 2 else 15_000
    seed = int(argv[3]) if len(argv) > 3 else 7
    skip_slow = "--skip-slow" in argv

    if nx.__version__ != "3.6.1":
        raise RuntimeError(f"need live NetworkX 3.6.1, got {nx.__version__}")

    # A connected graph: eccentricity/diameter are only defined on one.
    src = nx.gnm_random_graph(nodes, edges, seed=seed)
    if not nx.is_connected(src):
        src = src.subgraph(max(nx.connected_components(src), key=len)).copy()
        src = nx.convert_node_labels_to_integers(src, ordering="sorted")
    edge_list = list(src.edges())
    n = src.number_of_nodes()

    g_nx = nx.Graph()
    g_nx.add_nodes_from(range(n))
    g_nx.add_edges_from(edge_list)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(range(n))
    g_fnx.add_edges_from(edge_list)

    path, sha, size = ph.binary_sha256()
    print(f"bench_elf_sha256={sha} ({size} bytes) {path}", flush=True)
    print(f"host_identity={os.uname().nodename}  nx={nx.__version__}")
    print(f"graph: n={n} m={g_nx.number_of_edges()} seed={seed} connected=True")
    print()

    rows = []
    nx_stages = dict(stages(nx, g_nx, skip_slow))
    fnx_stages = dict(stages(fnx, g_fnx, skip_slow))

    total_nx = total_fnx = 0.0
    print(f"{'stage':<26}{'nx ms':>11}{'fnx ms':>11}{'ratio':>10}  parity")
    for name in nx_stages:
        a_fn, b_fn = nx_stages[name], fnx_stages[name]
        a, b = a_fn(), b_fn()
        parity = ph.canonical_bytes(a) == ph.canonical_bytes(b)
        t0 = time.perf_counter(); a_fn(); ta = time.perf_counter() - t0
        t0 = time.perf_counter(); b_fn(); tb = time.perf_counter() - t0
        total_nx += ta
        total_fnx += tb
        rows.append({"stage": name, "nx_s": ta, "fnx_s": tb,
                     "ratio": ta / tb if tb else None, "parity": parity})
        print(f"{name:<26}{ta*1000:11.1f}{tb*1000:11.1f}{ta/tb:9.1f}x  "
              f"{'IDENTICAL' if parity else 'DIVERGENT'}")

    print("-" * 70)
    print(f"{'WHOLE JOB':<26}{total_nx*1000:11.1f}{total_fnx*1000:11.1f}"
          f"{total_nx/total_fnx:9.1f}x")
    print()

    slowest = max(rows, key=lambda r: r["fnx_s"])
    share = slowest["fnx_s"] / total_fnx * 100.0
    print(f"fnx bottleneck: {slowest['stage']} = {share:.1f}% of fnx job time "
          f"(ratio {slowest['ratio']:.1f}x)")
    divergent = [r["stage"] for r in rows if not r["parity"]]
    print(f"parity: {len(rows) - len(divergent)}/{len(rows)} stages byte-identical"
          + (f"; DIVERGENT: {divergent}" if divergent else ""))
    print("analytics_pass_json=" + json.dumps(
        {"nodes": n, "edges": g_nx.number_of_edges(), "seed": seed,
         "elf_sha256": sha, "host": os.uname().nodename,
         "whole_job_ratio": total_nx / total_fnx, "stages": rows},
        sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
