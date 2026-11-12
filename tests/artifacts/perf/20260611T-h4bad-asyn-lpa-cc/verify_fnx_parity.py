import time, random, hashlib, json, sys
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx


def to_fnx(G):
    H = fnx.Graph()
    H.add_nodes_from(G.nodes())
    H.add_edges_from((u, v, dict(d)) for u, v, d in G.edges(data=True))
    return H


def comm_sig(communities):
    # order-sensitive signature of the yielded communities
    parts = []
    for s in communities:
        parts.append(",".join(map(str, sorted(s, key=lambda x: (str(type(x)), x)))))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


# --- correctness: fnx-native vs nx-on-converted-graph (same adjacency) ---
fails = 0
checks = 0
for seed in range(80):
    for n, p in [(30, 0.1), (80, 0.05), (150, 0.05), (60, 0.12)]:
        G = nx.gnp_random_graph(n, p, seed=seed)
        H = to_fnx(G)
        Gnx = _fnx_to_nx(H)
        ref = list(nx.community.asyn_lpa_communities(Gnx, seed=seed))
        got = list(fnx.community.asyn_lpa_communities(H, seed=seed))
        checks += 1
        if comm_sig(ref) != comm_sig(got):
            fails += 1
            if fails <= 5:
                print(f"MISMATCH n={n} p={p} seed={seed}")
                print("  ref", [sorted(s) for s in ref][:3])
                print("  got", [sorted(s) for s in got][:3])
# weighted
for seed in range(30):
    rng = random.Random(seed)
    G = nx.gnp_random_graph(70, 0.08, seed=seed)
    for u, v in G.edges():
        G[u][v]["weight"] = rng.choice([1.0, 2.0, 3.0])
    H = to_fnx(G)
    Gnx = _fnx_to_nx(H)
    ref = list(nx.community.asyn_lpa_communities(Gnx, weight="weight", seed=seed))
    got = list(fnx.community.asyn_lpa_communities(H, weight="weight", seed=seed))
    checks += 1
    if comm_sig(ref) != comm_sig(got):
        fails += 1
        print(f"WEIGHTED MISMATCH seed={seed}")
# string-keyed
for seed in range(20):
    base = nx.gnp_random_graph(40, 0.1, seed=seed)
    G = nx.relabel_nodes(base, {i: f"n{i}" for i in base})
    H = to_fnx(G)
    Gnx = _fnx_to_nx(H)
    ref = list(nx.community.asyn_lpa_communities(Gnx, seed=seed))
    got = list(fnx.community.asyn_lpa_communities(H, seed=seed))
    checks += 1
    if comm_sig(ref) != comm_sig(got):
        fails += 1
        print(f"STR MISMATCH seed={seed}")
# directed should raise
G = nx.DiGraph([(0, 1), (1, 2)])
H = fnx.DiGraph(); H.add_edges_from(G.edges())
try:
    list(fnx.community.asyn_lpa_communities(H, seed=1)); draised = "NO"
except Exception as e:
    draised = type(e).__name__
print(f"directed raises: {draised}")
print(f"CORRECTNESS checks={checks} fails={fails}")

# --- golden sha + bench ---
G = nx.gnp_random_graph(400, 0.05, seed=7)
H = to_fnx(G)
Gnx = _fnx_to_nx(H)
sig_fnx = comm_sig(list(fnx.community.asyn_lpa_communities(H, seed=42)))
sig_nx = comm_sig(list(nx.community.asyn_lpa_communities(Gnx, seed=42)))
print(f"golden sha fnx={sig_fnx[:16]} nx={sig_nx[:16]} MATCH={sig_fnx==sig_nx}")


def bench(fn, reps=7, inner=3):
    best = []
    for _ in range(reps):
        ts = []
        for _ in range(inner):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        best.append(min(ts))
    return min(best)


ft = bench(lambda: list(fnx.community.asyn_lpa_communities(H, seed=42)))
nt = bench(lambda: list(nx.community.asyn_lpa_communities(Gnx, seed=42)))
print(f"AFTER fnx {ft*1000:.3f}ms  nx {nt*1000:.3f}ms  ratio {ft/nt:.3f}x")
