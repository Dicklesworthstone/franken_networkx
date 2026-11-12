"""DiGraph int-key edge reads vs LIVE networkx, for one built arm.

TREATED by the six widened gates in digraph.rs (int endpoints now reach the
index lookaside instead of falling past it to two node_key_to_string heap
allocations plus a string-keyed probe):

    DiGraph.edges[u,v]        -> Python OutEdgeView.__getitem__ -> native get_edge_data
    DiGraph.get_edge_data()   -> the same native call, no Python view frame
    DiGraph G.adj[u][v]       -> Python AtlasView -> _fnx_edge_attr_dict_fast

CONTROLS, which this change must not move: the same three on str keys (already
admitted by the old gate), and Graph, whose subscript goes through the native
EdgeView C slot in views.rs and never touches digraph.rs at all.

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


def build(n, m, seed, directed, as_int):
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
    nodes = [key(i) for i in range(n)]
    gnx = (nx.DiGraph if directed else nx.Graph)()
    gfx = (fnx.DiGraph if directed else fnx.Graph)()
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
    expected = os.environ.get("FNX_EXPECT_SO")
    if expected and os.path.realpath(_fnx.__file__) != os.path.realpath(expected):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header(f"probe=digraph-intkey-lookaside arm={arm}")

    rows = []
    for directed, dlabel in ((True, "DiGraph"), (False, "Graph")):
        for as_int, klabel in ((True, "int"), (False, "str")):
            if not directed and klabel == "str":
                continue  # Graph str: a second untouched control adds time, not information
            gnx, gfx = build(2000, 8000, seed=7, directed=directed, as_int=as_int)
            probes = list(gnx.edges)[:CALLS]
            nx_ev, fnx_ev = gnx.edges, gfx.edges
            nx_adj, fnx_adj = gnx.adj, gfx.adj

            def a_sub(*, view=nx_ev, e=probes):
                return [view[x] for x in e]

            def b_sub(*, view=fnx_ev, e=probes):
                return [view[x] for x in e]

            def a_ged(*, g=gnx, e=probes):
                return [g.get_edge_data(u, v) for u, v in e]

            def b_ged(*, g=gfx, e=probes):
                return [g.get_edge_data(u, v) for u, v in e]

            def a_adj(*, adj=nx_adj, e=probes):
                return [adj[u][v] for u, v in e]

            def b_adj(*, adj=fnx_adj, e=probes):
                return [adj[u][v] for u, v in e]

            rows.append((f"{dlabel}.edges[u,v]      x{CALLS} {klabel}", a_sub, b_sub))
            rows.append((f"{dlabel}.get_edge_data() x{CALLS} {klabel}", a_ged, b_ged))
            rows.append((f"{dlabel}.adj[u][v]       x{CALLS} {klabel}", a_adj, b_adj))

    results = []
    for lab, a, b in rows:
        if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
            print(f"{lab:<44} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
            continue
        na = ph.paired(f"[A/A nx]  {lab}", a, a)
        nb = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        ph.report(na)
        ph.report(nb)
        ph.report(cand, (na, nb))
        gate = ph.gate_decision(cand, na, nb)
        results.append({
            "arm": arm, "label": lab,
            "ratio_p50": cand.ratio_p50, "ratio_ci": list(cand.ratio_ci),
            "null_nx_median": na.ratio_p50, "null_nx_ci": list(na.ratio_ci),
            "null_fnx_median": nb.ratio_p50, "null_fnx_ci": list(nb.ratio_ci),
            "decidable": gate["decidable"], "decision_gate": gate,
            "nx_us": cand.p50_a * 1e6, "fnx_us": cand.p50_b * 1e6,
            "fnx_ns_per_call": cand.p50_b * 1e9 / CALLS,
            "wins": cand.wins,
        })

    print(f"\narm={arm} (worst first):", flush=True)
    for r in sorted(results, key=lambda r: r["ratio_p50"]):
        print(f"  {r['ratio_p50']:7.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"nx={r['nx_us']:7.2f} fnx={r['fnx_us']:7.2f}us ({r['fnx_ns_per_call']:6.1f}ns/call)  "
              f"dec={r['decidable']}  {r['label']}", flush=True)
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
