"""Which half of `to_directed(g).number_of_edges()` is the 0.0521x row?

The survey measured the pair. A single cold call suggested the two libraries
differ in OPPOSITE directions on the two halves, so split them:

    A  mod.to_directed(g)                  build the frozen live view
    B  view.number_of_edges()              count edges THROUGH that view
    C  mod.to_directed(g).number_of_edges() the surveyed pair

Semantics were checked first and match exactly: in BOTH libraries the module
function returns a frozen live view sharing edge-attr dicts with the parent,
and the METHOD returns an independent mutable copy. So this is a like-for-like
comparison, not a view-vs-copy artifact.
"""
import json, os, sys
sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph

def build(mod, n=400, m=1600, seed=11):
    import random
    rng = random.Random(seed); seen, st = set(), []
    while len(st) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u,v),max(u,v)) in seen: continue
        seen.add((min(u,v),max(u,v))); st.append((u,v))
    g = mod.Graph(); g.add_nodes_from(range(n))
    g.add_edges_from([(u,v,{"weight":1}) for u,v in st]); return g

def main():
    import networkx as nx, franken_networkx as fnx, franken_networkx._fnx as _fnx
    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError("wrong .so")
    ph.provenance_header("probe=to_directed-decomposition")
    gnx, gfx = build(nx), build(fnx)
    vnx, vfx = nx.to_directed(gnx), fnx.to_directed(gfx)
    rows = [
        ("to_directed(g) build only",
         lambda: nx.to_directed(gnx) is not None, lambda: fnx.to_directed(gfx) is not None),
        ("view.number_of_edges()",
         lambda: vnx.number_of_edges(), lambda: vfx.number_of_edges()),
        ("to_directed(g).number_of_edges() [surveyed]",
         lambda: nx.to_directed(gnx).number_of_edges(), lambda: fnx.to_directed(gfx).number_of_edges()),
        ("view: len(list(view.edges))",
         lambda: len(list(vnx.edges)), lambda: len(list(vfx.edges))),
        ("g.to_directed() METHOD (copy)",
         lambda: gnx.to_directed().number_of_edges(), lambda: gfx.to_directed().number_of_edges()),
    ]
    out = []
    for lab, a, b in rows:
        if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
            print(f"  PARITY-DIVERGENCE {lab}", flush=True); continue
        na, nb = ph.paired(f"[A/A nx] {lab}", a, a), ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b); gate = ph.gate_decision(cand, na, nb)
        r = {"label":lab,"ratio_p50":cand.ratio_p50,"ratio_ci":list(cand.ratio_ci),
             "null_nx":na.ratio_p50,"null_fnx":nb.ratio_p50,"decidable":gate["decidable"],
             "nx_us":cand.p50_a*1e6,"fnx_us":cand.p50_b*1e6}
        out.append(r)
        print(f"  {r['ratio_p50']:9.4f}x nx={r['nx_us']:9.2f}us fnx={r['fnx_us']:9.2f}us "
              f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)
    print("todirected_json="+json.dumps(out,sort_keys=True,separators=(",",":")), flush=True)
    return 0
raise SystemExit(main())
