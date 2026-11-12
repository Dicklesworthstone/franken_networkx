import time, hashlib
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.community as nxc
from franken_networkx.backend import _fnx_to_nx


def to_fnx(G):
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges()); return H


def sig(c):
    return hashlib.sha256("\n".join(
        ",".join(map(str, sorted(s, key=lambda x: (str(type(x)), x)))) for s in c
    ).encode()).hexdigest()


fails = 0; checks = 0
for seed in range(80):
    for n, p in [(40, 0.15), (80, 0.1), (120, 0.08), (200, 0.05), (60, 0.2)]:
        for k in (2, 3, 4):
            G = nx.gnp_random_graph(n, p, seed=seed)
            H = to_fnx(G); Gnx = _fnx_to_nx(H)
            ref = list(nxc.k_clique_communities(Gnx, k))
            got = list(fnx.community.k_clique_communities(H, k))
            checks += 1
            if sig(ref) != sig(got):
                fails += 1
                if fails <= 5:
                    print(f"MISMATCH n={n} p={p} seed={seed} k={k}")
# string-keyed
for seed in range(20):
    base = nx.gnp_random_graph(50, 0.12, seed=seed)
    G = nx.relabel_nodes(base, {i: f"n{i}" for i in base})
    H = to_fnx(G); Gnx = _fnx_to_nx(H)
    if sig(list(nxc.k_clique_communities(Gnx, 3))) != sig(list(fnx.community.k_clique_communities(H, 3))):
        fails += 1; print(f"STR MISMATCH seed={seed}")
    checks += 1
# cliques provided
G = nx.gnp_random_graph(60, 0.15, seed=1); H = to_fnx(G); Gnx = _fnx_to_nx(H)
pre = list(nx.find_cliques(Gnx))
if sig(list(nxc.k_clique_communities(Gnx, 3, cliques=list(pre)))) != \
   sig(list(fnx.community.k_clique_communities(H, 3, cliques=list(pre)))):
    fails += 1; print("CLIQUES-PROVIDED MISMATCH")
checks += 1
# k<2 lazy raise parity
def raises(fn):
    try:
        list(fn()); return None
    except Exception as e:
        return type(e).__name__
rn = raises(lambda: nxc.k_clique_communities(Gnx, 1))
rf = raises(lambda: fnx.community.k_clique_communities(H, 1))
print(f"k<2 raise: nx={rn} fnx={rf} match={rn==rf}")
checks += 1
if rn != rf:
    fails += 1
print(f"CORRECTNESS checks={checks} fails={fails}")

# golden + bench
G = nx.gnp_random_graph(300, 0.04, seed=3); H = to_fnx(G); Gnx = _fnx_to_nx(H)
sa = sig(list(fnx.community.k_clique_communities(H, 3)))
sn = sig(list(nxc.k_clique_communities(Gnx, 3)))
print(f"golden fnx={sa[:16]} nx={sn[:16]} MATCH={sa==sn}")


def bench(fn, reps=9, inner=3):
    best = []
    for _ in range(reps):
        ts = []
        for _ in range(inner):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        best.append(min(ts))
    return min(best)


a = bench(lambda: list(fnx.community.k_clique_communities(H, 3)))
b = bench(lambda: list(nxc.k_clique_communities(H, 3)))  # before: dispatch+convert
nn = bench(lambda: list(nxc.k_clique_communities(Gnx, 3)))
print(f"before(nx-on-fnx) {b*1000:.3f}ms  after {a*1000:.3f}ms  nx {nn*1000:.3f}ms  self {b/a:.2f}x  after/nx {a/nn:.3f}x")
