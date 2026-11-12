"""G.degree(n) by class, vs LIVE networkx same invocation.

TREATED: Graph and DiGraph on INT node keys -- the classes whose __call__ had a
fast path for exact `str` and none for exact `int`.
CONTROLS: the same call on str keys (already had the hoist), and MultiGraph /
MultiDiGraph, which use a different wrapper class entirely and were already
beating the incumbent (2.6950x / 2.9415x).

Both arms load the SAME .so; only python/franken_networkx/__init__.py differs,
so the in-process ELF sha256 is identical and no part of a difference can come
from the binary.
"""
import json, os, sys
sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph
CALLS = 512

def build(cls_name, as_int, n=2000, m=8000, seed=7):
    import random, networkx as nx, franken_networkx as fnx
    rng = random.Random(seed); key = (lambda i: i) if as_int else (lambda i: str(i))
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u,v),max(u,v)) in seen: continue
        seen.add((min(u,v),max(u,v))); stream.append((key(u), key(v)))
    gnx, gfx = getattr(nx,cls_name)(), getattr(fnx,cls_name)()
    for g in (gnx,gfx):
        g.add_nodes_from([key(i) for i in range(n)])
        g.add_edges_from([(u,v,{"weight":1}) for u,v in stream])
    if not type(gnx).__module__.startswith("networkx"): raise RuntimeError("nx arm not upstream")
    return gnx, gfx

def main():
    arm = os.environ.get("FNX_ARM","?")
    ph.provenance_header(f"probe=degree-scalar-intkey arm={arm}")
    results = []
    for cls_name in ("Graph","DiGraph","MultiGraph","MultiDiGraph"):
        for as_int, k in ((True,"int"),(False,"str")):
            gnx, gfx = build(cls_name, as_int)
            nodes = list(gnx.nodes)[:CALLS]
            def a(*, g=gnx, ns=nodes): return [g.degree(x) for x in ns]
            def b(*, g=gfx, ns=nodes): return [g.degree(x) for x in ns]
            lab = f"{cls_name}/{k} degree(n)"
            if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
                print(f"  PARITY-DIVERGENCE {lab}", flush=True); continue
            na, nb = ph.paired(f"[A/A nx] {lab}",a,a), ph.paired(f"[A/A fnx] {lab}",b,b)
            cand = ph.paired(lab,a,b); gate = ph.gate_decision(cand,na,nb)
            r = {"arm":arm,"label":lab,"ratio_p50":cand.ratio_p50,"ratio_ci":list(cand.ratio_ci),
                 "null_nx":na.ratio_p50,"null_fnx":nb.ratio_p50,"decidable":gate["decidable"],
                 "nx_ns":cand.p50_a*1e9/CALLS,"fnx_ns_per_call":cand.p50_b*1e9/CALLS}
            results.append(r)
            print(f"  {r['ratio_p50']:8.4f}x nx={r['nx_ns']:6.1f}ns fnx={r['fnx_ns_per_call']:6.1f}ns "
                  f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)
    ok = sum(1 for r in results if r["decidable"])
    print(f"\ndecidable {ok}/{len(results)}; nulls nx "
          f"[{min(r['null_nx'] for r in results):.4f},{max(r['null_nx'] for r in results):.4f}] "
          f"fnx [{min(r['null_fnx'] for r in results):.4f},{max(r['null_fnx'] for r in results):.4f}]", flush=True)
    print("arm_results_json="+json.dumps(results,sort_keys=True,separators=(",",":")), flush=True)
    return 0
raise SystemExit(main())
