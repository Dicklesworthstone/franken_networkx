import json
import hashlib
import time
import sys
import networkx as nx
import franken_networkx as fnx


def build(n, m, seed):
    g = fnx.barabasi_albert_graph(n, m, seed=seed)
    return g


def mintime(fn, reps=5):
    best = float("inf")
    out = None
    for _ in range(reps):
        t = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t
        best = min(best, dt)
    return best, out


def sha_scores(d):
    # canonical: sorted by node repr, full float repr
    items = sorted(((repr(k), repr(v)) for k, v in d.items()))
    h = hashlib.sha256()
    for k, v in items:
        h.update(k.encode())
        h.update(b"\x00")
        h.update(v.encode())
        h.update(b"\x01")
    return h.hexdigest()


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    results = {}
    for (n, m) in [(2000, 4), (3000, 4)]:
        g = build(n, m, 42)
        # parity vs genuine nx
        gnx = nx.barabasi_albert_graph(n, m, seed=42)
        t, scores = mintime(lambda: fnx.betweenness_centrality(g, normalized=True), reps=5)
        # endpoints variant
        t_ep, scores_ep = mintime(lambda: fnx.betweenness_centrality(g, normalized=True, endpoints=True), reps=3)
        # unnormalized
        t_un, scores_un = mintime(lambda: fnx.betweenness_centrality(g, normalized=False), reps=3)
        results[f"n{n}_m{m}"] = {
            "n": n, "m": m,
            "time_ms": t * 1e3,
            "time_ep_ms": t_ep * 1e3,
            "time_un_ms": t_un * 1e3,
            "sha_norm": sha_scores(scores),
            "sha_ep": sha_scores(scores_ep),
            "sha_un": sha_scores(scores_un),
        }
        print(f"n={n} m={m}: norm={t*1e3:.2f}ms ep={t_ep*1e3:.2f}ms un={t_un*1e3:.2f}ms sha={results[f'n{n}_m{m}']['sha_norm'][:12]}")
    with open(f"tests/artifacts/perf/20260609T-betweenness-parallel-brandes-cc/{label}.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
