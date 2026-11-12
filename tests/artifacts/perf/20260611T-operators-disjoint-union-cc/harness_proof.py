"""Proof: fnx.algorithms.operators.disjoint_union routes to native fnx (6x +
return-type fix). Parity: golden node/edge signature vs genuine nx."""
import time, hashlib, json, sys, warnings
warnings.filterwarnings("ignore")
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx

op = fnx.algorithms.operators


def parts(g):
    return (sorted(map(str, g.nodes())),
            sorted(tuple(sorted(map(str, e))) for e in g.edges()))


def gh(g):
    return hashlib.sha256(repr(parts(g)).encode()).hexdigest()


def bench(fn, r=7):
    fn(); b = 1e9
    for _ in range(r):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b * 1000


out = {"return_type": {}, "parity": {}, "speedup": {}}

# return type fix
G1 = nx.gnp_random_graph(20, 0.2, seed=1); G2 = nx.gnp_random_graph(15, 0.2, seed=2)
H1 = fnx.Graph(); H1.add_nodes_from(G1.nodes()); H1.add_edges_from(G1.edges())
H2 = fnx.Graph(); H2.add_nodes_from(G2.nodes()); H2.add_edges_from(G2.edges())
r = op.disjoint_union(H1, H2)
out["return_type"] = {"module": type(r).__module__, "is_fnx_graph": isinstance(r, fnx.Graph)}

# golden parity over many graph pairs
fails = 0
for s in range(80):
    a = nx.gnp_random_graph(30, 0.15, seed=s); b = nx.gnp_random_graph(25, 0.18, seed=s + 100)
    Ha = fnx.Graph(); Ha.add_nodes_from(a.nodes()); Ha.add_edges_from(a.edges())
    Hb = fnx.Graph(); Hb.add_nodes_from(b.nodes()); Hb.add_edges_from(b.edges())
    Na = _fnx_to_nx(Ha); Nb = _fnx_to_nx(Hb)
    if gh(op.disjoint_union(Ha, Hb)) != gh(nx.disjoint_union(Na, Nb)):
        fails += 1
out["parity"] = {"checks": 80, "fails": fails}

# speedup at scale
for n, p in [(800, 0.01), (1600, 0.005)]:
    A = nx.gnp_random_graph(n, p, seed=1); B = nx.gnp_random_graph(n, p, seed=2)
    HA = fnx.Graph(); HA.add_nodes_from(A.nodes()); HA.add_edges_from(A.edges())
    HB = fnx.Graph(); HB.add_nodes_from(B.nodes()); HB.add_edges_from(B.edges())
    NA = _fnx_to_nx(HA); NB = _fnx_to_nx(HB)
    routed = bench(lambda: op.disjoint_union(HA, HB))
    genuine = bench(lambda: nx.disjoint_union(NA, NB))
    out["speedup"][f"n{n}"] = {"routed_ms": round(routed, 2), "genuine_nx_ms": round(genuine, 2),
                              "speedup_vs_nx": round(genuine / routed, 2)}

print(json.dumps(out, indent=2))
with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/du_proof.json", "w") as f:
    json.dump(out, f, indent=2)
