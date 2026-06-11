"""Before/after interleaved proof for br-r37-c1-jl0xr.

BEFORE = delegate boruvka to nx via _fnx_to_nx (the HEAD path).
AFTER  = in-process _boruvka_spanning_edges_inproc (this change).
Both run on the IDENTICAL fnx graph H; nx baseline runs on the converted
graph (same adjacency) so ordering/tie-breaks are an apples-to-apples
contract. Reports byte-exact golden sha256 over the yielded edge stream.
"""
import time, random, hashlib, json, sys
import franken_networkx as fnx
import networkx as nx
from franken_networkx.backend import _fnx_to_nx


def build(G):
    H = fnx.Graph()
    H.add_nodes_from(G.nodes())
    H.add_edges_from((u, v, dict(d)) for u, v, d in G.edges(data=True))
    return H


def make(n, deg, seed=42):
    rng = random.Random(seed)
    G = nx.gnm_random_graph(n, n * deg // 2, seed=seed)
    for u, v in G.edges():
        G[u][v]["weight"] = rng.random()
    return G


def sha(edges):
    s = "\n".join(f"{u}|{v}|{d.get('weight')}" for u, v, d in edges)
    return hashlib.sha256(s.encode()).hexdigest()


def after(H):
    return list(fnx.minimum_spanning_edges(H, algorithm="boruvka", weight="weight", data=True))


def before(H):
    # explicit delegation = the HEAD path
    Gnx = _fnx_to_nx(H)
    return [(u, v, H[u][v]) for u, v, d in
            nx.minimum_spanning_edges(Gnx, algorithm="boruvka", weight="weight", data=True)]


def nx_only(Gnx):
    return list(nx.minimum_spanning_edges(Gnx, algorithm="boruvka", weight="weight", data=True))


def bench(fn, arg, n=3):
    return min((lambda: (time.perf_counter(), fn(arg), time.perf_counter()))()
               and 0 for _ in range(0)) if False else _bench(fn, arg, n)


def _bench(fn, arg, n=3):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(arg); ts.append(time.perf_counter() - t0)
    return min(ts)


if __name__ == "__main__":
    out = {}
    for n, deg in [(1500, 8), (3000, 8)]:
        G = make(n, deg)
        H = build(G)
        Gnx = _fnx_to_nx(H)
        ea, eb, en = after(H), before(H), nx_only(Gnx)
        sa, sb, sn = sha(ea), sha(eb), sha(en)
        bt, at, nt = [], [], []
        for _ in range(9):
            bt.append(_bench(before, H)); at.append(_bench(after, H)); nt.append(_bench(nx_only, Gnx))
        b, a, nn = min(bt), min(at), min(nt)
        out[f"n{n}_deg{deg}"] = {
            "before_ms": round(b * 1000, 3), "after_ms": round(a * 1000, 3), "nx_ms": round(nn * 1000, 3),
            "self_speedup": round(b / a, 3), "before_vs_nx": round(b / nn, 3), "after_vs_nx": round(a / nn, 3),
            "sha_after": sa, "sha_before": sb, "sha_nx": sn,
            "sha_match": sa == sb == sn,
        }
        print(json.dumps({f"n{n}_deg{deg}": out[f"n{n}_deg{deg}"]}, indent=2))
    with open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/proof.json", "w") as f:
        json.dump(out, f, indent=2)
