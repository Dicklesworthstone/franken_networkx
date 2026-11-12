"""Proof: fnx.algorithms.assortativity.* routes to native fnx top-level.
Parity: golden vs genuine nx (incl. order-sensitive mixing matrices, adversarial
degree distributions). Speedup: routed vs the old raw-nx-on-fnx submodule path."""
import time, hashlib, json, sys, warnings, random
warnings.filterwarnings("ignore")
import numpy as np
import franken_networkx as fnx
import networkx as nx
import networkx.algorithms.assortativity as nas
from franken_networkx.backend import _fnx_to_nx

asr = fnx.algorithms.assortativity


def bench(fn, r=6):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"routing": {}, "parity": {}, "speedup": {}}
for nm in ["degree_pearson_correlation_coefficient", "attribute_assortativity_coefficient",
           "numeric_assortativity_coefficient", "degree_assortativity_coefficient",
           "degree_mixing_matrix", "attribute_mixing_matrix", "average_neighbor_degree"]:
    out["routing"][nm] = getattr(asr, nm) is getattr(fnx, nm)

# parity over adversarial graphs (wide degree ranges stress mixing-matrix order)
gens = [lambda s: nx.barabasi_albert_graph(200, 3, seed=s),
        lambda s: nx.powerlaw_cluster_graph(180, 4, 0.3, seed=s),
        lambda s: nx.watts_strogatz_graph(160, 6, 0.2, seed=s),
        lambda s: nx.gnp_random_graph(140, 0.08, seed=s)]
pf = {"degree_pearson": 0, "attribute_assort": 0, "numeric_assort": 0,
      "degree_mixing_matrix": 0, "attribute_mixing_matrix": 0, "avg_neighbor_degree": 0}
checks = 0
for s in range(30):
    for gen in gens:
        G = gen(s); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
        rng = random.Random(s)
        for n in H:
            H.nodes[n]["v"] = rng.choice(["a", "b", "c"]); H.nodes[n]["num"] = float(rng.randint(0, 9))
        Gnx = _fnx_to_nx(H)
        checks += 1

        def close(a, b):
            return (a != a and b != b) or abs(a - b) < 1e-9
        if not close(asr.degree_pearson_correlation_coefficient(H), nas.degree_pearson_correlation_coefficient(Gnx)):
            pf["degree_pearson"] += 1
        if not close(asr.attribute_assortativity_coefficient(H, "v"), nas.attribute_assortativity_coefficient(Gnx, "v")):
            pf["attribute_assort"] += 1
        if not close(asr.numeric_assortativity_coefficient(H, "num"), nas.numeric_assortativity_coefficient(Gnx, "num")):
            pf["numeric_assort"] += 1
        if not np.allclose(np.asarray(asr.degree_mixing_matrix(H)), np.asarray(nas.degree_mixing_matrix(Gnx))):
            pf["degree_mixing_matrix"] += 1
        if not np.allclose(np.asarray(asr.attribute_mixing_matrix(H, "v")), np.asarray(nas.attribute_mixing_matrix(Gnx, "v"))):
            pf["attribute_mixing_matrix"] += 1
        if asr.average_neighbor_degree(H) != nas.average_neighbor_degree(Gnx):
            pf["avg_neighbor_degree"] += 1
out["parity"] = {"checks": checks, **pf}

# speedup vs old submodule path (raw nx on fnx graph) and genuine nx
G = nx.gnp_random_graph(1500, 0.01, seed=7); H = fnx.Graph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges())
for n in H:
    H.nodes[n]["v"] = n % 5
Gnx = _fnx_to_nx(H)
for nm, fkwargs, raw_on_H in [
    ("degree_pearson_correlation_coefficient", {}, True),
    ("attribute_assortativity_coefficient", {"a": "v"}, True),
    ("degree_mixing_matrix", {}, True),
    ("attribute_mixing_matrix", {"a": "v"}, True),
]:
    if "a" in fkwargs:
        routed = bench(lambda: getattr(asr, nm)(H, "v"))
        old = bench(lambda: getattr(nas, nm)(H, "v"))
        genuine = bench(lambda: getattr(nas, nm)(Gnx, "v"))
    else:
        routed = bench(lambda: getattr(asr, nm)(H))
        old = bench(lambda: getattr(nas, nm)(H))
        genuine = bench(lambda: getattr(nas, nm)(Gnx))
    out["speedup"][nm] = {"routed_ms": round(routed, 2), "old_submodule_ms": round(old, 2),
                          "genuine_nx_ms": round(genuine, 2),
                          "vs_old": round(old / routed, 1), "vs_nx": round(genuine / routed, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/asrt.json", "w") as f:
    json.dump(out, f, indent=2)
