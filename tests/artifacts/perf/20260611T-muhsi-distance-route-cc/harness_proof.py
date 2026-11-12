"""Proof for br-r37-c1-muhsi (distance_measures routing).

Parity: fnx.algorithms.distance_measures.X(H) vs genuine nx...X(Gnx) golden sha.
Speedup: routed (fnx top-level) vs the previous raw-nx submodule path on H.
"""
import time, hashlib, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.distance_measures as nxd
from franken_networkx.backend import _fnx_to_nx


def gsig(obj):
    if isinstance(obj, dict):
        body = repr([(str(k), round(float(v), 9)) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))])
    elif isinstance(obj, (list, set)):
        body = repr(sorted(obj, key=str))
    else:
        body = repr(round(float(obj), 9))
    return hashlib.sha256(body.encode()).hexdigest()


def bench(fn, r=5):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"routing": {}, "parity": {}, "speedup": {}}
for name in ["center", "diameter", "radius", "periphery", "eccentricity",
             "barycenter", "harmonic_diameter", "kemeny_constant"]:
    out["routing"][name] = getattr(fnx.algorithms.distance_measures, name) is getattr(fnx, name)

for n, p, seed in [(200, 0.04, 3), (600, 0.02, 7)]:
    G = nx.gnp_random_graph(n, p, seed=seed)
    if not nx.is_connected(G):
        continue
    H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
    Gnx = _fnx_to_nx(H)
    for name in ["center", "diameter", "eccentricity", "harmonic_diameter", "kemeny_constant"]:
        routed = getattr(fnx.algorithms.distance_measures, name)
        fr = routed(H); nr = getattr(nxd, name)(Gnx)
        out["parity"][f"{name}_n{n}"] = {"sha_match": gsig(fr) == gsig(nr)}
    if n == 600:
        for name in ["harmonic_diameter", "kemeny_constant"]:
            routed = getattr(fnx.algorithms.distance_measures, name)
            raw = getattr(nxd, name)  # previous submodule behavior
            a = bench(lambda: routed(H)); b = bench(lambda: raw(H))
            out["speedup"][name] = {"routed_ms": round(a, 2), "before_raw_nx_ms": round(b, 2), "speedup": round(b / a, 1)}
            # honest vs genuine nx too
            gn = bench(lambda: raw(Gnx))
            out["speedup"][name]["vs_genuine_nx"] = round(gn / a, 1)

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dm_proof.json", "w") as f:
    json.dump(out, f, indent=2)
