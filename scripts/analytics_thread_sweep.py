"""Thread sweep for the analytics pass: decompose the win into its two factors.

A speedup over NetworkX conflates two very different claims:
  1. "we left Python"      -- a constant factor, available to any compiled rewrite;
  2. "we used the cores"   -- the one NetworkX has no path to at any core count.

Running the same fnx job at RAYON_NUM_THREADS = 1, 2, 4, ... separates them. The
--threads 1 row is the load-bearing one: it is fnx with the parallelism switched
OFF, so `t(1)/t(64)` is the part of the win that is genuinely about cores, and
`t_nx/t(1)` is the part that is merely about not being interpreted.

RAYON_NUM_THREADS is read when the pool is first built and cannot be changed
afterwards, so each setting needs its own subprocess.

usage: analytics_thread_sweep.py [nodes] [edges] [seed]     (parent)
       analytics_thread_sweep.py --worker <nodes> <edges> <seed>
"""

import json
import os
import subprocess
import sys
import time

STAGES = ("closeness_centrality", "harmonic_centrality", "betweenness_centrality",
          "eccentricity", "diameter", "radius", "center", "periphery")


def worker(nodes, edges, seed):
    import networkx as nx
    import franken_networkx as fnx

    src = nx.gnm_random_graph(nodes, edges, seed=seed)
    if not nx.is_connected(src):
        src = src.subgraph(max(nx.connected_components(src), key=len)).copy()
        src = nx.convert_node_labels_to_integers(src, ordering="sorted")
    n = src.number_of_nodes()
    g = fnx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(src.edges())

    calls = {
        "closeness_centrality": lambda: fnx.closeness_centrality(g),
        "harmonic_centrality": lambda: fnx.harmonic_centrality(g),
        "betweenness_centrality": lambda: fnx.betweenness_centrality(g),
        "eccentricity": lambda: fnx.eccentricity(g),
        "diameter": lambda: fnx.diameter(g),
        "radius": lambda: fnx.radius(g),
        "center": lambda: fnx.center(g),
        "periphery": lambda: fnx.periphery(g),
    }
    for fn in calls.values():          # warm: pool spin-up, CSR build
        fn()

    out, total_w, total_c = {}, 0.0, 0.0
    for name in STAGES:
        w0, c0 = time.perf_counter(), time.process_time()
        calls[name]()
        w, c = time.perf_counter() - w0, time.process_time() - c0
        out[name] = {"wall": w, "cpu_wall": c / w if w else None}
        total_w += w
        total_c += c
    out["_total"] = {"wall": total_w, "cpu_wall": total_c / total_w}
    print("SWEEP_JSON=" + json.dumps(out))


def main(argv):
    if "--worker" in argv:
        i = argv.index("--worker")
        return worker(int(argv[i + 1]), int(argv[i + 2]), int(argv[i + 3]))

    nodes = int(argv[1]) if len(argv) > 1 else 3000
    edges = int(argv[2]) if len(argv) > 2 else 15000
    seed = int(argv[3]) if len(argv) > 3 else 7

    results = {}
    for t in (1, 2, 4, 8, 16, 32, 64):
        env = dict(os.environ, RAYON_NUM_THREADS=str(t))
        proc = subprocess.run(
            [sys.executable, __file__, "--worker", str(nodes), str(edges), str(seed)],
            capture_output=True, text=True, env=env,
        )
        line = next((l for l in proc.stdout.splitlines() if l.startswith("SWEEP_JSON=")), None)
        if line is None:
            print(f"threads={t}: FAILED\n{proc.stderr[-800:]}")
            continue
        results[t] = json.loads(line.split("=", 1)[1])
        r = results[t]["_total"]
        print(f"threads={t:3d}  fnx job {r['wall']*1000:9.1f} ms   cpu/wall {r['cpu_wall']:6.2f}")

    if 1 in results and 64 in results:
        one, many = results[1]["_total"]["wall"], results[64]["_total"]["wall"]
        print()
        print(f"parallel scaling 1 -> 64 threads: {one/many:.2f}x "
              f"({one*1000:.1f} ms -> {many*1000:.1f} ms)")
        print()
        print(f"{'stage':<26}{'1 thr ms':>11}{'64 thr ms':>11}{'scaling':>10}{'cpu/wall':>10}")
        for s in STAGES:
            a, b = results[1][s]["wall"], results[64][s]["wall"]
            print(f"{s:<26}{a*1000:11.1f}{b*1000:11.1f}{a/b:9.1f}x"
                  f"{results[64][s]['cpu_wall']:10.1f}")
    print("THREAD_SWEEP_JSON=" + json.dumps(results, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
