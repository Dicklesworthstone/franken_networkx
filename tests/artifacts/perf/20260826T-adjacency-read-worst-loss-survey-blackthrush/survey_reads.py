"""Worst-loss survey of the adjacency READ surface on HEAD, vs LIVE networkx.

All four public graph classes x both node-key types x the five read spellings
that reach adjacency: edges[u,v], get_edge_data, adj[u][v], neighbors, has_node.

Purpose is ranking, not a before/after: this establishes which op is the worst
remaining loss now that the int-key canonicalization + index lookaside lever has
landed in views.rs (acb088e3a), digraph.rs (ab94f800f) and lib.rs (da0471d24).

Substrate is perf_harness.paired(): both arms interleaved inside ONE loop with
the order alternated per round, 21 rounds, min-of-3 per slot, bootstrap median
CI, byte-parity proof, and the two arm-specific A/A nulls. Every row prints its
own nulls; a row whose nulls do not bracket 1.0 is not usable and says so.
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
    multi = cls_name.startswith("Multi")
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((key(u), key(v), {"weight": rng.randint(1, 20)}))
    nodes = [key(i) for i in range(n)]
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    gnx.add_nodes_from(nodes)
    gfx.add_nodes_from(nodes)
    gnx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    gfx.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    if not type(gnx).__module__.startswith("networkx"):
        raise RuntimeError("nx arm is not genuine upstream")
    return gnx, gfx, multi


def main():
    import franken_networkx._fnx as _fnx
    expected = os.environ.get("FNX_EXPECT_SO")
    if expected and os.path.realpath(_fnx.__file__) != os.path.realpath(expected):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header("probe=adjacency-read-worst-loss-survey HEAD")

    rows = []
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        for as_int, klabel in ((True, "int"), (False, "str")):
            gnx, gfx, multi = build(2000, 8000, seed=7, cls_name=cls_name, as_int=as_int)
            probes = list(gnx.edges)[:CALLS]
            probes = [(u, v) for u, v, *_ in probes] if multi else probes
            nodes = list(gnx.nodes)[:CALLS]
            tag = f"{cls_name}/{klabel}"

            def mk(pyobj_nx, pyobj_fx, fn):
                return (lambda *, o=pyobj_nx: fn(o)), (lambda *, o=pyobj_fx: fn(o))

            a1, b1 = mk(gnx.edges, gfx.edges, lambda v, e=probes: [v[x] for x in e])
            a2, b2 = mk(gnx, gfx, lambda g, e=probes: [g.get_edge_data(u, w) for u, w in e])
            a3, b3 = mk(gnx.adj, gfx.adj, lambda d, e=probes: [d[u][w] for u, w in e])
            a4, b4 = mk(gnx, gfx, lambda g, ns=nodes: [len(list(g.neighbors(x))) for x in ns])
            a5, b5 = mk(gnx, gfx, lambda g, ns=nodes: [g.has_node(x) for x in ns])

            rows += [
                (f"{tag:18s} edges[u,v]", a1, b1),
                (f"{tag:18s} get_edge_data", a2, b2),
                (f"{tag:18s} adj[u][v]", a3, b3),
                (f"{tag:18s} neighbors", a4, b4),
                (f"{tag:18s} has_node", a5, b5),
            ]

    results = []
    for lab, a, b in rows:
        try:
            if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
                print(f"{lab:<44} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
                continue
        except Exception as exc:  # noqa: BLE001
            print(f"{lab:<44} SETUP-ERROR {type(exc).__name__}: {exc} -- NOT TIMED", flush=True)
            continue
        na = ph.paired(f"[A/A nx]  {lab}", a, a)
        nb = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        gate = ph.gate_decision(cand, na, nb)
        results.append({
            "label": lab.strip(), "ratio_p50": cand.ratio_p50, "ratio_ci": list(cand.ratio_ci),
            "null_nx_median": na.ratio_p50, "null_fnx_median": nb.ratio_p50,
            "decidable": gate["decidable"],
            "nx_ns": cand.p50_a * 1e9 / CALLS, "fnx_ns": cand.p50_b * 1e9 / CALLS,
        })
        print(f"  {cand.ratio_p50:7.4f}x  nx={results[-1]['nx_ns']:6.1f}ns fnx={results[-1]['fnx_ns']:7.1f}ns "
              f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f}  dec={gate['decidable']}  {lab}", flush=True)

    print("\n==== WORST LOSSES ON THE ADJACENCY READ SURFACE (decidable only) ====", flush=True)
    for r in sorted([r for r in results if r["decidable"]], key=lambda r: r["ratio_p50"])[:12]:
        print(f"  {r['ratio_p50']:7.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"nx={r['nx_ns']:6.1f}ns fnx={r['fnx_ns']:7.1f}ns  {r['label']}", flush=True)
    und = [r for r in results if not r["decidable"]]
    print(f"\ndecidable {len(results)-len(und)}/{len(results)}"
          + (f"; UNDECIDABLE (not ranked): {[r['label'] for r in und]}" if und else ""), flush=True)
    print("survey_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
