"""adj[u][v] by node-key type, all four classes, vs LIVE networkx same invocation.

TREATED: Graph. Its adj row IS the native AtlasView whose __getitem__ is a C
slot, so the str-only index-lookaside gate inside views.rs is the binding
constraint there. Measured on HEAD it is the only class with a key-type gap on
this op: 341.0 ns/call on int against 285.7 on str, 1.19x.

CONTROLS: DiGraph, MultiGraph, MultiDiGraph. Their adj rows are PYTHON view
classes that never enter views.rs at all, so this gate cannot reach them --
verified by MRO probe, not assumed. Their cost is the Python view chain and
should be untouched.

Substrate is perf_harness.paired(): arms interleaved inside ONE loop, order
alternated per round, 21 rounds, min-of-3, bootstrap median CI, byte-parity
proof, dual arm-specific A/A nulls.
"""
import json
import os
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph

CALLS = 512


def build(n, m, seed, cls_name, as_int):
    import random
    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(seed)
    key = (lambda i: i) if as_int else (lambda i: str(i))
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((key(u), key(v), {"weight": rng.randint(1, 20)}))
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    nodes = [key(i) for i in range(n)]
    gnx.add_nodes_from(nodes)
    gfx.add_nodes_from(nodes)
    gnx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    gfx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    if not type(gnx).__module__.startswith("networkx"):
        raise RuntimeError("nx arm is not genuine upstream")
    return gnx, gfx


def main():
    arm = os.environ.get("FNX_ARM", "HEAD")
    import franken_networkx._fnx as _fnx
    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header(f"probe=atlasview-rowsubscript-keytype arm={arm}")

    rows = []
    for cls_name in ("MultiDiGraph", "MultiGraph", "DiGraph", "Graph"):
        for as_int, klabel in ((True, "int"), (False, "str")):
            gnx, gfx = build(2000, 8000, seed=7, cls_name=cls_name, as_int=as_int)
            pairs = [(u, v) for u, v, *_ in list(gnx.edges)[:CALLS]]

            nxa, fxa = gnx.adj, gfx.adj

            def a(*, d=nxa, e=pairs):
                return [d[u][w] for u, w in e]

            def b(*, d=fxa, e=pairs):
                return [d[u][w] for u, w in e]

            rows.append((f"{cls_name}/{klabel:3s} adj[u][v]", a, b))

    results = []
    for lab, a, b in rows:
        if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
            print(f"{lab:<36} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
            continue
        na = ph.paired(f"[A/A nx]  {lab}", a, a)
        nb = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        gate = ph.gate_decision(cand, na, nb)
        r = {
            "arm": arm, "label": lab, "ratio_p50": cand.ratio_p50,
            "ratio_ci": list(cand.ratio_ci), "null_nx_median": na.ratio_p50,
            "null_fnx_median": nb.ratio_p50, "decidable": gate["decidable"],
            "nx_ns": cand.p50_a * 1e9 / CALLS,
            "fnx_ns_per_call": cand.p50_b * 1e9 / CALLS,
        }
        results.append(r)
        print(f"  {r['ratio_p50']:7.4f}x nx={r['nx_ns']:6.1f}ns fnx={r['fnx_ns_per_call']:7.1f}ns "
              f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)

    print("\nKEY-TYPE GAP on adj[u][v] (fnx int ns / fnx str ns), 1.00 = no gap:", flush=True)
    by = {r["label"].split()[0]: r for r in results}
    for cls_name in ("MultiDiGraph", "MultiGraph", "DiGraph", "Graph"):
        i = by.get(f"{cls_name}/int"); s = by.get(f"{cls_name}/str")
        if i and s:
            print(f"  {cls_name:14s} int={i['fnx_ns_per_call']:7.1f}ns str={s['fnx_ns_per_call']:7.1f}ns "
                  f"gap={i['fnx_ns_per_call']/s['fnx_ns_per_call']:5.2f}x  "
                  f"ratios {i['ratio_p50']:.4f}x / {s['ratio_p50']:.4f}x", flush=True)
    ok = sum(1 for r in results if r["decidable"])
    print(f"\ndecidable {ok}/{len(results)}; nulls nx "
          f"[{min(r['null_nx_median'] for r in results):.4f},{max(r['null_nx_median'] for r in results):.4f}] "
          f"fnx [{min(r['null_fnx_median'] for r in results):.4f},{max(r['null_fnx_median'] for r in results):.4f}]",
          flush=True)
    print("arm_results_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
