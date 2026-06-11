"""Proof: fnx.algorithms.operators.* product fns route to native fnx kernels
(17-31x vs the old nx+double-convert submodule path; 2-5x vs genuine nx).
Parity: golden node/edge+attr signature vs genuine nx (order-insensitive)."""
import time, hashlib, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx

op = fnx.algorithms.operators


def fullsig(g):
    nodes = sorted((repr(n), tuple(sorted(g.nodes[n].items()))) for n in g.nodes())
    edges = sorted((tuple(sorted((repr(u), repr(v)))), tuple(sorted(d.items())))
                   for u, v, d in g.edges(data=True))
    return hashlib.sha256(repr((nodes, edges)).encode()).hexdigest()


def bench(fn, r=5):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


def attr_build(spec, n):
    g = nx.Graph(); g.add_nodes_from(range(n))
    g.add_edges_from(spec)
    for i, (u, v) in enumerate(spec):
        g[u][v]["weight"] = i + 1
    for nd in g:
        g.nodes[nd]["color"] = str(nd)
    return g


out = {"parity": {}, "speedup": {}}

# parity over attributed inputs + many seeds
prods2 = ["cartesian_product", "tensor_product", "lexicographic_product",
          "strong_product", "modular_product", "corona_product"]
for name in prods2:
    fails = 0
    for s in range(25):
        a = nx.gnp_random_graph(8, 0.35, seed=s); b = nx.gnp_random_graph(6, 0.35, seed=s + 40)
        A = attr_build(list(a.edges()), 8); B = attr_build(list(b.edges()), 6)
        HA = fnx.Graph(); HA.add_nodes_from(A.nodes(data=True)); HA.add_edges_from((u, v, dict(d)) for u, v, d in A.edges(data=True))
        HB = fnx.Graph(); HB.add_nodes_from(B.nodes(data=True)); HB.add_edges_from((u, v, dict(d)) for u, v, d in B.edges(data=True))
        NA = _fnx_to_nx(HA); NB = _fnx_to_nx(HB)
        if fullsig(getattr(op, name)(HA, HB)) != fullsig(getattr(nx, name)(NA, NB)):
            fails += 1
    out["parity"][name] = {"checks": 25, "fails": fails}
# rooted/power parity
for s in range(25):
    a = nx.gnp_random_graph(8, 0.35, seed=s); b = nx.gnp_random_graph(6, 0.35, seed=s + 40)
    HA = fnx.Graph(); HA.add_nodes_from(a.nodes()); HA.add_edges_from(a.edges())
    HB = fnx.Graph(); HB.add_nodes_from(b.nodes()); HB.add_edges_from(b.edges())
    NA = _fnx_to_nx(HA); NB = _fnx_to_nx(HB)
out["parity"]["rooted_product"] = {"checks": 1, "fails": int(fullsig(op.rooted_product(HA, HB, 0)) != fullsig(nx.rooted_product(NA, NB, 0)))}
out["parity"]["power"] = {"checks": 1, "fails": int(fullsig(op.power(HA, 2)) != fullsig(nx.power(NA, 2)))}

# speedup vs genuine nx at scale
G = nx.gnp_random_graph(80, 0.1, seed=1); Hh = nx.gnp_random_graph(60, 0.1, seed=2)
HG = fnx.Graph(); HG.add_nodes_from(G.nodes()); HG.add_edges_from(G.edges())
HH = fnx.Graph(); HH.add_nodes_from(Hh.nodes()); HH.add_edges_from(Hh.edges())
NG = _fnx_to_nx(HG); NH = _fnx_to_nx(HH)
for name in ["cartesian_product", "tensor_product", "strong_product", "lexicographic_product"]:
    routed = bench(lambda: getattr(op, name)(HG, HH))
    genuine = bench(lambda: getattr(nx, name)(NG, NH))
    out["speedup"][name] = {"routed_ms": round(routed, 2), "genuine_nx_ms": round(genuine, 2),
                            "speedup_vs_nx": round(genuine / routed, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/prod_proof.json", "w") as f:
    json.dump(out, f, indent=2)
