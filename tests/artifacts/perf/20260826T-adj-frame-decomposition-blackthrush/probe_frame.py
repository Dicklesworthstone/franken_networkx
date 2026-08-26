"""How much of adj[u][v] is the Python view frame, and how much is the native call?

Two things differ between Graph (284 ns/call) and DiGraph (487): Graph's row
subscript is a native C slot, DiGraph's is a Python function that calls the
native single-edge accessor. To size the routing lever, remove exactly ONE thing:

    arm A  G._fnx_edge_attr_dict_fast(u, v)   native accessor ALONE
    arm B  G.adj[u][v]                         Python row frame + the same call

ratio = t_A / t_B, so a ratio of 0.5 means the frame doubles the cost, and
(t_B - t_A) is the frame in ns. Both arms are FrankenNetworkX, so this is a
decomposition, not a vs-incumbent claim -- but it is measured in ONE invocation
with the same dual A/A nulls, which is what makes it load-robust.

Graph is carried alongside DiGraph as the reference: it is the class that
already HAS the native slot, so its frame cost is the floor the lever aims at.
"""
import json
import os
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph

CALLS = 512


def build(n, m, seed, cls_name, as_int=True):
    import random
    import franken_networkx as fnx

    rng = random.Random(seed)
    key = (lambda i: i) if as_int else (lambda i: str(i))
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((key(u), key(v)))
    g = getattr(fnx, cls_name)()
    g.add_nodes_from([key(i) for i in range(n)])
    g.add_edges_from([(u, v, {"weight": 1}) for u, v in stream])
    return g, stream[:CALLS]


def main():
    import franken_networkx._fnx as _fnx
    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header("probe=adj-frame-decomposition")

    results = []
    for cls_name in ("DiGraph", "Graph"):
        for as_int, klabel in ((True, "int"), (False, "str")):
            g, pairs = build(2000, 8000, seed=7, cls_name=cls_name, as_int=as_int)
            fast = g._fnx_edge_attr_dict_fast
            adj = g.adj
            for u, v in pairs:          # warm both routes
                fast(u, v); adj[u][v]

            def a(*, f=fast, e=pairs):
                return [f(u, v) for u, v in e]

            def b(*, d=adj, e=pairs):
                return [d[u][v] for u, v in e]

            lab = f"{cls_name}/{klabel} native-accessor vs adj[u][v]"
            if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
                print(f"{lab:<46} DIVERGENT -- the two routes are not the same object", flush=True)
                continue
            na = ph.paired(f"[A/A native] {lab}", a, a)
            nb = ph.paired(f"[A/A adj]    {lab}", b, b)
            cand = ph.paired(lab, a, b)
            gate = ph.gate_decision(cand, na, nb)
            native_ns = cand.p50_a * 1e9 / CALLS
            full_ns = cand.p50_b * 1e9 / CALLS
            results.append({
                "label": lab, "ratio_p50": cand.ratio_p50, "decidable": gate["decidable"],
                "native_ns": native_ns, "full_ns": full_ns, "frame_ns": full_ns - native_ns,
                "null_native": na.ratio_p50, "null_adj": nb.ratio_p50,
            })
            print(f"  {cls_name}/{klabel}: native={native_ns:6.1f}ns  adj[u][v]={full_ns:6.1f}ns  "
                  f"FRAME={full_ns - native_ns:6.1f}ns ({100*(full_ns-native_ns)/full_ns:4.1f}%)  "
                  f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={gate['decidable']}", flush=True)

    print("\nPRIZE if DiGraph's row became a native slot like Graph's:", flush=True)
    d = {r["label"].split()[0]: r for r in results}
    for k in ("DiGraph/int", "DiGraph/str"):
        di = next((r for r in results if r["label"].startswith(k)), None)
        gr = next((r for r in results if r["label"].startswith(k.replace("DiGraph", "Graph"))), None)
        if di and gr:
            target = di["native_ns"] + gr["frame_ns"]
            print(f"  {k}: {di['full_ns']:.1f}ns -> ~{target:.1f}ns "
                  f"(keeps DiGraph's native cost, adopts Graph's frame) = {di['full_ns']/target:.2f}x", flush=True)
    print("probe_frame_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
