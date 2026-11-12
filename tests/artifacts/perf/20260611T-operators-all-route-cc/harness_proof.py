"""Proof: fnx.algorithms.operators.{union_all,intersection_all,compose_all,
disjoint_union_all} route to native fnx (4.5-8x vs old nx+double-convert path).
Parity: golden full signature (nodes+edges+attrs) vs genuine nx."""
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


def attr(g):
    for i, (u, v) in enumerate(g.edges()):
        g[u][v]["weight"] = i
    for n in g:
        g.nodes[n]["c"] = str(n)
    return g


def bench(fn, r=5):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"parity": {}, "speedup": {}}

# parity (attributed)
pf = {"union_all": 0, "union_all_rename": 0, "disjoint_union_all": 0, "compose_all": 0, "intersection_all": 0}
for s in range(30):
    djs = [attr(nx.relabel_nodes(nx.gnp_random_graph(10, 0.3, seed=s * 4 + i), lambda x, o=i * 100: x + o)) for i in range(3)]
    Hdj = []
    for g in djs:
        H = fnx.Graph(); H.add_nodes_from(g.nodes(data=True)); H.add_edges_from((u, v, dict(d)) for u, v, d in g.edges(data=True)); Hdj.append(H)
    Ndj = [_fnx_to_nx(H) for H in Hdj]
    pf["union_all"] += fullsig(op.union_all(Hdj)) != fullsig(nx.union_all(Ndj))
    pf["union_all_rename"] += fullsig(op.union_all(Hdj, rename=("a", "b", "c"))) != fullsig(nx.union_all(Ndj, rename=("a", "b", "c")))
    pf["disjoint_union_all"] += fullsig(op.disjoint_union_all(Hdj)) != fullsig(nx.disjoint_union_all(Ndj))
    sn = [attr(nx.gnp_random_graph(12, 0.3, seed=s * 4 + i)) for i in range(3)]
    Hsn = []
    for g in sn:
        H = fnx.Graph(); H.add_nodes_from(g.nodes(data=True)); H.add_edges_from((u, v, dict(d)) for u, v, d in g.edges(data=True)); Hsn.append(H)
    Nsn = [_fnx_to_nx(H) for H in Hsn]
    pf["compose_all"] += fullsig(op.compose_all(Hsn)) != fullsig(nx.compose_all(Nsn))
    pf["intersection_all"] += fullsig(op.intersection_all(Hsn)) != fullsig(nx.intersection_all(Nsn))
out["parity"] = {k: {"checks": 30, "fails": int(v)} for k, v in pf.items()}

# speedup at scale (4x 400-node graphs)
djs = [nx.relabel_nodes(nx.gnp_random_graph(400, 0.01, seed=s), lambda x, o=s * 1000: x + o) for s in range(4)]
Hdj = [fnx.Graph() for _ in djs]
for H, g in zip(Hdj, djs):
    H.add_nodes_from(g.nodes()); H.add_edges_from(g.edges())
Ndj = [_fnx_to_nx(H) for H in Hdj]
sn = [fnx.Graph() for _ in range(3)]
for i, H in enumerate(sn):
    g = nx.gnp_random_graph(400, 0.02, seed=i + 10); H.add_nodes_from(range(400)); H.add_edges_from(g.edges())
Ns = [_fnx_to_nx(H) for H in sn]
out["speedup"]["union_all"] = {"routed_ms": round(bench(lambda: op.union_all(Hdj)), 2), "genuine_nx_ms": round(bench(lambda: nx.union_all(Ndj)), 2)}
out["speedup"]["disjoint_union_all"] = {"routed_ms": round(bench(lambda: op.disjoint_union_all(Hdj)), 2), "genuine_nx_ms": round(bench(lambda: nx.disjoint_union_all(Ndj)), 2)}
out["speedup"]["compose_all"] = {"routed_ms": round(bench(lambda: op.compose_all(sn)), 2), "genuine_nx_ms": round(bench(lambda: nx.compose_all(Ns)), 2)}
out["speedup"]["intersection_all"] = {"routed_ms": round(bench(lambda: op.intersection_all(sn)), 2), "genuine_nx_ms": round(bench(lambda: nx.intersection_all(Ns)), 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/all_proof.json", "w") as f:
    json.dump(out, f, indent=2)
