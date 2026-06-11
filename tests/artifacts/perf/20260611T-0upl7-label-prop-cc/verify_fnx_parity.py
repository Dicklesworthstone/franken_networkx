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
    for n, p in [(40, 0.1), (80, 0.08), (150, 0.05), (60, 0.15), (200, 0.04), (100, 0.12)]:
        G = nx.gnp_random_graph(n, p, seed=seed)
        H = to_fnx(G); Gnx = _fnx_to_nx(H)
        ref = list(nxc.label_propagation_communities(Gnx))
        got = list(fnx.community.label_propagation_communities(H))
        checks += 1
        if sig(ref) != sig(got):
            fails += 1
            if fails <= 5:
                print(f"MISMATCH n={n} p={p} seed={seed}")
# string-keyed + isolated
for seed in range(25):
    base = nx.gnp_random_graph(50, 0.1, seed=seed)
    G = nx.relabel_nodes(base, {i: f"n{i}" for i in base}); G.add_nodes_from(["iso1", "iso2"])
    H = to_fnx(G); Gnx = _fnx_to_nx(H)
    if sig(list(nxc.label_propagation_communities(Gnx))) != sig(list(fnx.community.label_propagation_communities(H))):
        fails += 1; print(f"STR MISMATCH seed={seed}")
    checks += 1
# directed raise parity
GD = fnx.DiGraph(); GD.add_edges_from([(0, 1), (1, 2)])
GDn = nx.DiGraph([(0, 1), (1, 2)])
def err(fn):
    try:
        list(fn()); return None
    except Exception as e:
        return type(e).__name__
rn = err(lambda: nxc.label_propagation_communities(GDn))
rf = err(lambda: fnx.community.label_propagation_communities(GD))
print(f"directed raise: nx={rn} fnx={rf} match={rn==rf}")
checks += 1
if rn != rf:
    fails += 1
print(f"CORRECTNESS checks={checks} fails={fails}")

# golden + bench
G = nx.gnp_random_graph(300, 0.04, seed=3); H = to_fnx(G); Gnx = _fnx_to_nx(H)
sa = sig(list(fnx.community.label_propagation_communities(H)))
sn = sig(list(nxc.label_propagation_communities(Gnx)))
print(f"golden fnx={sa[:16]} nx={sn[:16]} MATCH={sa==sn}")


def bench(fn, reps=9, inner=3):
    best = []
    for _ in range(reps):
        ts = []
        for _ in range(inner):
            t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
        best.append(min(ts))
    return min(best)


for n, p, seed in [(300, 0.04, 3), (800, 0.02, 5), (1500, 0.012, 7)]:
    G = nx.gnp_random_graph(n, p, seed=seed); H = to_fnx(G); Gnx = _fnx_to_nx(H)
    a = bench(lambda: list(fnx.community.label_propagation_communities(H)))
    nn = bench(lambda: list(nxc.label_propagation_communities(Gnx)))
    print(f"n{n} p{p}: after {a*1000:.3f}ms  nx {nn*1000:.3f}ms  after/nx {a/nn:.3f}x")
