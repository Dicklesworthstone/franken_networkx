"""Does the DiGraph.edges[u,v] ratio depend on the number of DISTINCT keys?

br-r37-c1-bnv3h banked 0.1544x with 300 distinct keys and recorded that a
single repeated key screened at 0.34-0.41x -- i.e. the distinct-key count is
itself an axis.  My 512-distinct-key row reads 0.43x on HEAD, which is
better than that bead predicts, so the count is swept here against the SAME
fixture and the SAME nx control.  networkx is the control on every row: if
nx is flat in the key count and fnx is not, the count is a real axis; if both
move together it is working-set locality, not an fnx cache effect.
"""
import json
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph


def main():
    ph.provenance_header("probe=distinct-key-count sweep on DiGraph.edges[u,v] (gate-bypassed, dual-null gated)")

    gnx, gfx = ph._build_pair(2000, 8000, seed=7, weighted=True, directed=True)
    all_edges = list(gnx.edges)
    nx_ev, fnx_ev = gnx.edges, gfx.edges

    rows = []
    for count in (1, 32, 300, 512, 4000, 8000):
        # Hold TOTAL SUBSCRIPTS per call fixed at 512 so the per-call cost is
        # comparable across rows; only the number of DISTINCT keys varies.
        base = all_edges[:count]
        probes = [base[i % count] for i in range(512)]

        def a(*, view=nx_ev, edges=probes):
            return [view[e] for e in edges]

        def b(*, view=fnx_ev, edges=probes):
            return [view[e] for e in edges]

        rows.append((f"DiGraph.edges[u,v] x512 subscripts / {count:5d} distinct [nx/fnx]", a, b))

    results = []
    for lab, a, b in rows:
        if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
            print(f"{lab:<58} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
            continue
        na = ph.paired(f"[A/A nx]  {lab}", a, a)
        nb = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        ph.report(na); ph.report(nb); ph.report(cand, (na, nb))
        gate = ph.gate_decision(cand, na, nb)
        results.append({
            "label": lab, "ratio_p50": cand.ratio_p50, "ratio_ci": list(cand.ratio_ci),
            "null_nx_median": na.ratio_p50, "null_fnx_median": nb.ratio_p50,
            "decidable": gate["decidable"], "nx_us": cand.p50_a * 1e6,
            "fnx_us": cand.p50_b * 1e6, "wins": cand.wins,
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
