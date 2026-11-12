"""MultiAtlasView/MultiDiAtlasView existence-hoist A/B, vs LIVE networkx.

TREATED: MultiGraph / MultiDiGraph `adj[u][v]`. Those two `__getitem__`s used to
build a heap canonical for `v` and then ask a string-keyed `has_edge` (hashing
BOTH full-length endpoints) for an answer `has_edge_by_indices` gives in O(1)
from positions the same function already resolved. The hoist answers existence
from the positions and keeps the canonical only for constructing the cell view.

CONTROLS: `adj[u][v]` on Graph and DiGraph (different classes, untouched by this
edit) and `get_edge_data` on all four (a different native entry point).

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
    arm = os.environ.get("FNX_ARM", "unlabelled")
    import franken_networkx._fnx as _fnx
    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header(f"probe=multiatlas-existence-hoist arm={arm}")

    rows = []
    for cls_name in ("MultiGraph", "MultiDiGraph", "Graph", "DiGraph"):
        for as_int, klabel in ((True, "int"), (False, "str")):
            gnx, gfx = build(2000, 8000, seed=7, cls_name=cls_name, as_int=as_int)
            pairs = [(u, v) for u, v, *_ in list(gnx.edges)[:CALLS]]
            tag = f"{cls_name}/{klabel}"

            def a_adj(*, d=gnx.adj, e=pairs):
                return [d[u][w] for u, w in e]

            def b_adj(*, d=gfx.adj, e=pairs):
                return [d[u][w] for u, w in e]

            def a_ged(*, g=gnx, e=pairs):
                return [g.get_edge_data(u, w) for u, w in e]

            def b_ged(*, g=gfx, e=pairs):
                return [g.get_edge_data(u, w) for u, w in e]

            rows.append((f"{tag:18s} adj[u][v]", a_adj, b_adj))
            rows.append((f"{tag:18s} get_edge_data", a_ged, b_ged))

    results = []
    for lab, a, b in rows:
        try:
            if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
                print(f"{lab:<40} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
                continue
        except Exception as exc:  # noqa: BLE001
            print(f"{lab:<40} SETUP-ERROR {type(exc).__name__}: {exc}", flush=True)
            continue
        na = ph.paired(f"[A/A nx]  {lab}", a, a)
        nb = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        gate = ph.gate_decision(cand, na, nb)
        results.append({
            "arm": arm, "label": lab.strip(),
            "ratio_p50": cand.ratio_p50, "ratio_ci": list(cand.ratio_ci),
            "null_nx_median": na.ratio_p50, "null_fnx_median": nb.ratio_p50,
            "decidable": gate["decidable"],
            "nx_ns": cand.p50_a * 1e9 / CALLS,
            "fnx_ns_per_call": cand.p50_b * 1e9 / CALLS,
        })
        r = results[-1]
        print(f"  {r['ratio_p50']:7.4f}x nx={r['nx_ns']:6.1f}ns fnx={r['fnx_ns_per_call']:7.1f}ns "
              f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)

    ok = sum(1 for r in results if r["decidable"])
    print(f"\ndecidable {ok}/{len(results)}; "
          f"nulls nx [{min(r['null_nx_median'] for r in results):.4f},"
          f"{max(r['null_nx_median'] for r in results):.4f}] "
          f"fnx [{min(r['null_fnx_median'] for r in results):.4f},"
          f"{max(r['null_fnx_median'] for r in results):.4f}]", flush=True)
    print("arm_results_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
