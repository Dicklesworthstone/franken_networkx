"""subgraph_view with a callable filter_node, vs LIVE networkx same invocation.

TREATED: subgraph_view(G, filter_node=<lambda>). Its edge walk fell between two
fast paths -- the node-set chain (used by subgraph() and show_nodes) and the
non-default-edge-filter path (used by restricted_view) -- and took the generic
per-edge self.adj[source][target] route.

CONTROLS: the three sibling variants that already had a fast path. If the gate
relaxation touched them, they move; they must not.
"""
import json, os, sys
sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph

def build(mod, directed=False, n=400, m=1600, seed=11):
    import random
    rng=random.Random(seed); seen,st=set(),[]
    while len(st)<m:
        u,v=rng.randrange(n),rng.randrange(n)
        if u==v or (min(u,v),max(u,v)) in seen: continue
        seen.add((min(u,v),max(u,v))); st.append((u,v))
    g=(mod.DiGraph if directed else mod.Graph)(); g.add_nodes_from(range(n))
    g.add_edges_from([(u,v,{"w":1}) for u,v in st]); return g

def main():
    import networkx as nx, franken_networkx as fnx, franken_networkx._fnx as _fnx
    exp=os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__)!=os.path.realpath(exp): raise RuntimeError("wrong .so")
    ph.provenance_header(f"probe=filtered-view-edges arm={os.environ.get('FNX_ARM','?')}")
    keep=set(range(200)); klist=list(keep)
    N,F = build(nx), build(fnx)
    ND,FD = build(nx,True), build(fnx,True)
    pairs=[("TREATED subgraph_view(lambda).edges",
            nx.subgraph_view(N, filter_node=lambda n: n in keep), fnx.subgraph_view(F, filter_node=lambda n: n in keep)),
           ("TREATED subgraph_view(lambda) DiGraph",
            nx.subgraph_view(ND, filter_node=lambda n: n in keep), fnx.subgraph_view(FD, filter_node=lambda n: n in keep)),
           ("control subgraph_view(show_nodes)",
            nx.subgraph_view(N, filter_node=nx.filters.show_nodes(klist)), fnx.subgraph_view(F, filter_node=fnx.filters.show_nodes(klist))),
           ("control restricted_view",
            nx.restricted_view(N, list(range(200,400)), []), fnx.restricted_view(F, list(range(200,400)), [])),
           ("control G.subgraph()", N.subgraph(klist), F.subgraph(klist))]
    out=[]
    for lab,vn,vf in pairs:
        a=lambda vn=vn: len(list(vn.edges)); b=lambda vf=vf: len(list(vf.edges))
        if ph.canonical_bytes(a())!=ph.canonical_bytes(b()):
            print(f"  PARITY-DIVERGENCE {lab}"); continue
        na,nb=ph.paired(f"[A/A nx] {lab}",a,a), ph.paired(f"[A/A fnx] {lab}",b,b)
        cand=ph.paired(lab,a,b); gate=ph.gate_decision(cand,na,nb)
        r={"label":lab,"ratio_p50":cand.ratio_p50,"ratio_ci":list(cand.ratio_ci),
           "null_nx":na.ratio_p50,"null_fnx":nb.ratio_p50,"decidable":gate["decidable"],
           "nx_us":cand.p50_a*1e6,"fnx_us":cand.p50_b*1e6}
        out.append(r)
        print(f"  {r['ratio_p50']:9.4f}x nx={r['nx_us']:9.2f}us fnx={r['fnx_us']:9.2f}us "
              f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)
    print("ne_json="+json.dumps(out,sort_keys=True,separators=(",",":")), flush=True)
    return 0
raise SystemExit(main())
