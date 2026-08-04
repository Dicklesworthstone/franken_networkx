"""Whole-job analytics pass over a REAL graph: live NetworkX 3.6.1 vs FrankenNetworkX,
both engines in the SAME invocation, on the SAME in-memory edge list.

This is a job, not a microbenchmark. One graph is loaded once and carried through a
realistic analytics pipeline; every stage's output is compared for byte-identical
canonical form BEFORE any timing is reported, so a fast wrong answer cannot score.

Each stage is timed with wall AND process CPU time. cpu/wall is MEASURED parallelism:
a single-threaded stage pins at ~1.0 no matter what it claims.

Companion to `scripts/analytics_pass.py`, which runs the same stage list on a
synthetic `gnm_random_graph`. This one runs it on a published SNAP graph, because
a real degree distribution is where the geodesic stages actually bite.

Graphs are the ones `scripts/parallel_analytics_pass.py --role fetch` caches into
`graphs/` (facebook_combined, ca-AstroPh, ca-CondMat). Run that first if `graphs/`
is empty; nothing here touches the network.

A disconnected input is reduced to its giant component and the run says so:
eccentricity/diameter/radius/center/periphery are undefined otherwise.

usage (from the repo root):
    python3 scripts/real_graph_job.py graphs facebook_combined
    python3 scripts/real_graph_job.py graphs ca-AstroPh --skip-geodesic
"""
import gzip
import importlib.util
import json
import os
import sys
import time

SPEC = importlib.util.spec_from_file_location("perf_harness", "scripts/perf_harness.py")
ph = importlib.util.module_from_spec(SPEC)
sys.modules["perf_harness"] = ph
SPEC.loader.exec_module(ph)

import networkx as nx          # noqa: E402
import franken_networkx as fnx  # noqa: E402


def load_edges(path):
    op = gzip.open if path.endswith(".gz") else open
    edges = []
    with op(path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            u, v = int(parts[0]), int(parts[1])
            if u != v:                      # drop self-loops: eccentricity family needs simple
                edges.append((u, v))
    return edges


def stages(engine, graph, skip_geodesic):
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
        ("center", lambda: sorted(engine.center(graph)), True),
        ("periphery", lambda: sorted(engine.periphery(graph)), True),
    ]
    return [(n, f) for (n, f, slow) in items if not (slow and skip_geodesic)]


def main(argv):
    graph_dir, name = argv[1], argv[2]
    skip_geodesic = "--skip-geodesic" in argv
    only = None
    for a in argv:
        if a.startswith("--only"):
            only = set(a.split("=", 1)[1].split(","))

    if nx.__version__ != "3.6.1":
        raise RuntimeError(f"need live NetworkX 3.6.1, got {nx.__version__}")

    edges = load_edges(os.path.join(graph_dir, f"{name}.txt.gz"))
    src = nx.Graph()
    src.add_edges_from(edges)
    note = "as published"
    if not nx.is_connected(src):
        giant = max(nx.connected_components(src), key=len)
        src = src.subgraph(giant).copy()
        note = "giant component (geodesic stages are undefined on a disconnected graph)"
    edge_list = list(src.edges())
    nodes = list(src.nodes())

    g_nx = nx.Graph()
    g_nx.add_nodes_from(nodes)
    g_nx.add_edges_from(edge_list)
    g_fnx = fnx.Graph()
    g_fnx.add_nodes_from(nodes)
    g_fnx.add_edges_from(edge_list)

    path, sha, size = ph.binary_sha256()
    print(f"bench_elf_sha256={sha} ({size} bytes) {path}", flush=True)
    print(f"host_identity={os.uname().nodename}  nx={nx.__version__}  "
          f"loadavg={open('/proc/loadavg').read().split()[0]}")
    print(f"graph: {name}  n={g_nx.number_of_nodes()}  m={g_nx.number_of_edges()}  [{note}]")
    print()

    nx_stages = dict(stages(nx, g_nx, skip_geodesic))
    fnx_stages = dict(stages(fnx, g_fnx, skip_geodesic))
    if only:
        nx_stages = {k: v for k, v in nx_stages.items() if k in only}
        fnx_stages = {k: v for k, v in fnx_stages.items() if k in only}

    def timed(fn):
        w0, c0 = time.perf_counter(), time.process_time()
        fn()
        return time.perf_counter() - w0, time.process_time() - c0

    rows, total_nx, total_fnx = [], 0.0, 0.0
    print(f"{'stage':<26}{'nx ms':>12}{'fnx ms':>10}{'ratio':>10}{'nx c/w':>9}{'fnx c/w':>9}  parity")
    for sname in nx_stages:
        a_fn, b_fn = nx_stages[sname], fnx_stages[sname]
        a, b = a_fn(), b_fn()
        identical = ph.canonical_bytes(a) == ph.canonical_bytes(b)
        ta, ca = timed(a_fn)
        tb, cb = timed(b_fn)
        total_nx += ta
        total_fnx += tb
        rows.append({"stage": sname, "nx_s": ta, "fnx_s": tb, "ratio": ta / tb if tb else None,
                     "nx_cpu_wall": ca / ta if ta else None, "fnx_cpu_wall": cb / tb if tb else None,
                     "identical": identical})
        print(f"{sname:<26}{ta*1000:12.1f}{tb*1000:10.1f}{ta/tb:9.1f}x{ca/ta:9.2f}{cb/tb:9.2f}  "
              f"{'IDENTICAL' if identical else 'DIVERGENT'}", flush=True)

    print("-" * 88)
    print(f"{'WHOLE JOB':<26}{total_nx*1000:12.1f}{total_fnx*1000:10.1f}{total_nx/total_fnx:9.1f}x")
    print()
    n_ident = sum(1 for r in rows if r["identical"])
    print(f"parity: {n_ident}/{len(rows)} stages byte-identical")
    print(f"parallelism: nx peak cpu/wall = {max(r['nx_cpu_wall'] for r in rows):.2f}, "
          f"fnx peak cpu/wall = {max(r['fnx_cpu_wall'] for r in rows):.2f}")
    print(f"nx wall total = {total_nx:.1f}s ({total_nx/60:.1f} min); fnx wall total = {total_fnx:.2f}s")
    print("real_job_json=" + json.dumps(
        {"graph": name, "n": g_nx.number_of_nodes(), "m": g_nx.number_of_edges(),
         "elf_sha256": sha, "host": os.uname().nodename,
         "whole_job_ratio": total_nx / total_fnx, "stages": rows},
        sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
