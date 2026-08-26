"""Is the adjacency-read deficit a CROSSING bound, or a NODE-KEY-TYPE bound?

Same graph shape, same call, same substrate (perf_harness.paired: arms
interleaved inside one loop, ABBA order alternation, bootstrap median CI, dual
arm-specific A/A nulls).  The ONLY axis varied is the Python type of the node
keys: exact `str` (which reaches the pooled-canonical buffer br-r37-c1-afiq8
and the index lookaside br-r37-c1-ptiz2) vs exact `int` (which reaches
neither and pays `i.to_string()` per endpoint per call).

networkx is the control on BOTH rows: nx stores a dict-of-dicts and is
key-type agnostic, so if nx's own str/int ratio is flat while fnx's is not,
the gap is fnx's canonicalization, not the FFI crossing.
"""
import json
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph


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
    ph.provenance_header("probe=node-key-type axis on G.edges[u,v] (gate-bypassed, dual-null gated)")

    rows = []
    for directed, dlabel in ((False, "Graph"), (True, "DiGraph")):
        for as_int, klabel in ((False, "str-keys"), (True, "int-keys")):
            gnx, gfx = build(2000, 8000, seed=7, directed=directed, as_int=as_int)
            probes = list(gnx.edges)[:512]
            nx_ev, fnx_ev = gnx.edges, gfx.edges

            def a(*, view=nx_ev, edges=probes):
                return [view[e] for e in edges]

            def b(*, view=fnx_ev, edges=probes):
                return [view[e] for e in edges]

            rows.append((f"{dlabel}.edges[u,v] x512 {klabel} [nx/fnx]", a, b))

    results = []
    for lab, a, b in rows:
        if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
            print(f"{lab:<54} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
            continue
        na = ph.paired(f"[A/A nx]  {lab}", a, a)
        nb = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        ph.report(na); ph.report(nb); ph.report(cand, (na, nb))
        gate = ph.gate_decision(cand, na, nb)
        results.append({
            "label": lab, "ratio_p50": cand.ratio_p50, "ratio_ci": list(cand.ratio_ci),
            "null_nx_median": na.ratio_p50, "null_nx_ci": list(na.ratio_ci),
            "null_fnx_median": nb.ratio_p50, "null_fnx_ci": list(nb.ratio_ci),
            "decidable": gate["decidable"], "decision_gate": gate,
            "nx_us": cand.p50_a * 1e6, "fnx_us": cand.p50_b * 1e6, "wins": cand.wins,
        })

    print("\nsorted by ratio (worst first):", flush=True)
    for r in sorted(results, key=lambda r: r["ratio_p50"]):
        print(f"  {r['ratio_p50']:7.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"nx={r['nx_us']:7.2f}us fnx={r['fnx_us']:7.2f}us  decidable={r['decidable']}  {r['label']}",
              flush=True)
    print("probe_results_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
