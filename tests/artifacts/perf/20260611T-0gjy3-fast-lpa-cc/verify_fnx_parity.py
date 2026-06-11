import time, random, hashlib
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx
import networkx.algorithms.community as nxc


def to_fnx(G):
    H = fnx.Graph(); H.add_nodes_from(G.nodes())
    H.add_edges_from((u, v, dict(d)) for u, v, d in G.edges(data=True)); return H


def sig(c):
    return hashlib.sha256("\n".join(
        ",".join(map(str, sorted(s, key=lambda x: (str(type(x)), x)))) for s in c
    ).encode()).hexdigest()


fails = 0; checks = 0
for seed in range(80):
    for n, p in [(30, 0.1), (80, 0.05), (150, 0.05), (60, 0.12), (250, 0.03)]:
        G = nx.gnp_random_graph(n, p, seed=seed)
        H = to_fnx(G); Gnx = _fnx_to_nx(H)
        ref = list(nxc.fast_label_propagation_communities(Gnx, seed=seed))
        got = list(fnx.community.fast_label_propagation_communities(H, seed=seed))
        checks += 1
        if sig(ref) != sig(got):
            fails += 1
            if fails <= 5:
                print(f"MISMATCH n={n} p={p} seed={seed}")
# isolated nodes
for seed in range(20):
    G = nx.gnp_random_graph(50, 0.05, seed=seed); G.add_nodes_from([100, 101])
    H = to_fnx(G); Gnx = _fnx_to_nx(H)
    if sig(list(nxc.fast_label_propagation_communities(Gnx, seed=seed))) != \
       sig(list(fnx.community.fast_label_propagation_communities(H, seed=seed))):
        fails += 1; print(f"ISO MISMATCH seed={seed}")
    checks += 1
# weighted delegates -> still must match
for seed in range(15):
    rng = random.Random(seed); G = nx.gnp_random_graph(50, 0.08, seed=seed)
    for u, v in G.edges(): G[u][v]["weight"] = rng.choice([1.0, 2.0])
    H = to_fnx(G); Gnx = _fnx_to_nx(H)
    if sig(list(nxc.fast_label_propagation_communities(Gnx, weight="weight", seed=seed))) != \
       sig(list(fnx.community.fast_label_propagation_communities(H, weight="weight", seed=seed))):
        fails += 1; print(f"WEIGHTED MISMATCH seed={seed}")
    checks += 1
print(f"CORRECTNESS checks={checks} fails={fails}")

# golden + bench
G = nx.gnp_random_graph(400, 0.05, seed=7); H = to_fnx(G); Gnx = _fnx_to_nx(H)
sa = sig(list(fnx.community.fast_label_propagation_communities(H, seed=42)))
sn = sig(list(nxc.fast_label_propagation_communities(Gnx, seed=42)))
print(f"golden fnx={sa[:16]} nx={sn[:16]} MATCH={sa==sn}")


def bench(fn, reps=9, inner=3):
    best = []
    for _ in range(reps):
        ts = [(lambda: (lambda t0: (fn(), time.perf_counter() - t0)[1])(time.perf_counter()))() for _ in range(inner)]
        best.append(min(ts))
    return min(best)


a = bench(lambda: list(fnx.community.fast_label_propagation_communities(H, seed=42)))
b = bench(lambda: list(nxc.fast_label_propagation_communities(H, seed=42)))
nn = bench(lambda: list(nxc.fast_label_propagation_communities(Gnx, seed=42)))
print(f"before(nx-on-fnx) {b*1000:.3f}ms  after {a*1000:.3f}ms  nx {nn*1000:.3f}ms  self {b/a:.2f}x  after/nx {a/nn:.3f}x")
