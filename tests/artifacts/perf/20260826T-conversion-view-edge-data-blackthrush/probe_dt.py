"""Single-row A/B: number_of_edges() through a to_directed view, plus one control.

Cut to two rows so each pass is short and its exposure to the peer load on this
host is minimal. The control is the SAME call on a to_undirected view of a
DiGraph -- the mirror direction, which already had its native branch and which
this change does not touch.
"""
import json, os, sys
sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph

def build(mod, directed, n=400, m=1600, seed=11):
    import random
    rng=random.Random(seed); seen,st=set(),[]
    while len(st)<m:
        u,v=rng.randrange(n),rng.randrange(n)
        if u==v or (min(u,v),max(u,v)) in seen: continue
        seen.add((min(u,v),max(u,v))); st.append((u,v))
    g=(mod.DiGraph if directed else mod.Graph)(); g.add_nodes_from(range(n))
    g.add_edges_from([(u,v,{"weight":1}) for u,v in st]); return g

def main():
    import networkx as nx, franken_networkx as fnx, franken_networkx._fnx as _fnx
    exp=os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__)!=os.path.realpath(exp): raise RuntimeError("wrong .so")
    ph.provenance_header(f"probe=to_directed-iteration arm={os.environ.get('FNX_ARM','?')}")
    unx,ufx = build(nx,False), build(fnx,False)
    dnx,dfx = build(nx,True),  build(fnx,True)
    vnx,vfx = nx.to_directed(unx), fnx.to_directed(ufx)
    wnx,wfx = nx.to_undirected(dnx), fnx.to_undirected(dfx)
    rows=[("TREATED len(list(to_directed(G).edges))", lambda: len(list(vnx.edges)), lambda: len(list(vfx.edges))),
          ("TREATED to_directed(G).edges(data=True)", lambda: len(list(vnx.edges(data=True))), lambda: len(list(vfx.edges(data=True)))),
          ("control len(list(to_undirected(D).edges))", lambda: len(list(wnx.edges)), lambda: len(list(wfx.edges))),
          ("control to_directed(G).number_of_edges()", lambda: vnx.number_of_edges(), lambda: vfx.number_of_edges())]
    out=[]
    for lab,a,b in rows:
        if ph.canonical_bytes(a())!=ph.canonical_bytes(b()):
            print(f"  PARITY-DIVERGENCE {lab}"); continue
        na,nb=ph.paired(f"[A/A nx] {lab}",a,a), ph.paired(f"[A/A fnx] {lab}",b,b)
        cand=ph.paired(lab,a,b); gate=ph.gate_decision(cand,na,nb)
        r={"label":lab,"ratio_p50":cand.ratio_p50,"ratio_ci":list(cand.ratio_ci),
           "null_nx":na.ratio_p50,"null_fnx":nb.ratio_p50,"decidable":gate["decidable"],
           "nx_us":cand.p50_a*1e6,"fnx_us":cand.p50_b*1e6}
        out.append(r)
        print(f"  {r['ratio_p50']:10.4f}x nx={r['nx_us']:8.2f}us fnx={r['fnx_us']:8.2f}us "
              f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)
    print("ne_json="+json.dumps(out,sort_keys=True,separators=(",",":")), flush=True)
    return 0
raise SystemExit(main())
