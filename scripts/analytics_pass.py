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
        ("radius", lambda: engine.radius(graph), True),
        # center/periphery are compared as SORTED lists, not as returned: nx emits
        # them in node-iteration order while fnx returns them sorted. That is a
        # real (cosmetic) API-order difference, called out here rather than hidden
        # -- the SET of center/periphery nodes is the mathematical content, and
        # that is what is being gated.
        ("center", lambda: sorted(engine.center(graph)), True),
        ("periphery", lambda: sorted(engine.periphery(graph)), True),
    ]
    return [(n, f) for (n, f, slow) in items if not (slow and skip_slow)]


def max_rel_delta(a, b):
    """Largest relative delta over matching numeric leaves, or None if the two
    results are not even structurally comparable.

    Used only to CLASSIFY a stage that already failed the byte-identity gate, so a
    divergence gets reported as the size it actually is instead of a bare
    DIVERGENT. Never used to pass a stage that should be byte-identical.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return None
        vals = [max_rel_delta(a[k], b[k]) for k in a]
    elif isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return None
        vals = [max_rel_delta(x, y) for x, y in zip(a, b)]
    elif isinstance(a, bool) or isinstance(b, bool):
        return None if a != b else 0.0
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a == b:
            return 0.0
        scale = max(abs(a), abs(b))
        return abs(a - b) / scale if scale else abs(a - b)
    else:
        return None if a != b else 0.0
    return None if any(v is None for v in vals) else max(vals, default=0.0)


# Stages allowed to miss byte-identity, mapped to the relative bound they must
# stay inside.
#
# DELIBERATELY EMPTY. Every stage in this pass is byte-identical to nx 3.6.1 on
# HEAD, including harmonic_centrality -- `br-r37-c1-4l10m` replays nx's `set`
# iteration order through a source-ordered kernel, so the f64 sums associate the
# same way. An earlier run of this pass reported harmonic as DIVERGENT (2993/3000
# nodes, max 3.92e-11); that was measured against a stale .so and is void on HEAD.
#
# Keep this empty unless a divergence is genuinely unfixable: the machinery below
# reports the SIZE of any divergence either way, which is the useful part. A
# standing tolerance here would silently absorb a real regression.
ULP_EXACT_STAGES = {}


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

    def timed(fn):
        """Wall AND process CPU time. cpu/wall is MEASURED parallelism: a
        single-threaded stage pins at ~1.0 no matter what it claims."""
        w0, c0 = time.perf_counter(), time.process_time()
        fn()
        return time.perf_counter() - w0, time.process_time() - c0

    total_nx = total_fnx = 0.0
    print(f"{'stage':<26}{'nx ms':>11}{'fnx ms':>11}{'ratio':>10}"
          f"{'nx c/w':>9}{'fnx c/w':>9}  parity")
    for name in nx_stages:
        a_fn, b_fn = nx_stages[name], fnx_stages[name]
        a, b = a_fn(), b_fn()
        identical = ph.canonical_bytes(a) == ph.canonical_bytes(b)
        rel = None if identical else max_rel_delta(a, b)
        bound = ULP_EXACT_STAGES.get(name)
        if identical:
            verdict, ok = "IDENTICAL", True
        elif bound is not None and rel is not None and rel <= bound:
            verdict, ok = f"ULP-EXACT rel<={rel:.1e}", True
        else:
            verdict, ok = (f"DIVERGENT rel={rel:.1e}" if rel is not None
                           else "DIVERGENT"), False

        ta, ca = timed(a_fn)
        tb, cb = timed(b_fn)
        total_nx += ta
        total_fnx += tb
        rows.append({"stage": name, "nx_s": ta, "fnx_s": tb,
                     "ratio": ta / tb if tb else None,
                     "nx_cpu_wall": ca / ta if ta else None,
                     "fnx_cpu_wall": cb / tb if tb else None,
                     "identical": identical, "rel_delta": rel, "parity_ok": ok})
        print(f"{name:<26}{ta*1000:11.1f}{tb*1000:11.1f}{ta/tb:9.1f}x"
              f"{ca/ta:9.2f}{cb/tb:9.2f}  {verdict}")

    print("-" * 88)
    print(f"{'WHOLE JOB':<26}{total_nx*1000:11.1f}{total_fnx*1000:11.1f}"
          f"{total_nx/total_fnx:9.1f}x")
    print()

    slowest = max(rows, key=lambda r: r["fnx_s"])
    share = slowest["fnx_s"] / total_fnx * 100.0
    print(f"fnx bottleneck: {slowest['stage']} = {share:.1f}% of fnx job time "
          f"(ratio {slowest['ratio']:.1f}x)")
    n_ident = sum(1 for r in rows if r["identical"])
    ulp = [r["stage"] for r in rows if not r["identical"] and r["parity_ok"]]
    divergent = [r["stage"] for r in rows if not r["parity_ok"]]
    print(f"parity: {n_ident}/{len(rows)} stages byte-identical"
          + (f"; ULP-exact: {ulp}" if ulp else "")
          + (f"; DIVERGENT: {divergent}" if divergent else ""))
    peak = max((r["fnx_cpu_wall"] or 0) for r in rows)
    print(f"parallelism: nx peak cpu/wall = "
          f"{max((r['nx_cpu_wall'] or 0) for r in rows):.2f}, "
          f"fnx peak cpu/wall = {peak:.2f}"
          f"  (1.00 = single-threaded; nx has no path above it)")
    print("analytics_pass_json=" + json.dumps(
        {"nodes": n, "edges": g_nx.number_of_edges(), "seed": seed,
         "elf_sha256": sha, "host": os.uname().nodename,
         "whole_job_ratio": total_nx / total_fnx, "stages": rows},
        sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
