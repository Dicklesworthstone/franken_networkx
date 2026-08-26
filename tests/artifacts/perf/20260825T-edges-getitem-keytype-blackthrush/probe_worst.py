"""Confirm the worst measured vs-NetworkX loss on the adjacency read surface.

Reuses perf_harness's OWN substrate -- `paired()` (arms interleaved inside one
loop, order alternated per round: ABBAABBA...), bootstrap median CI, the two
arm-specific A/A nulls, byte-parity proof, and the in-process ELF sha256 --
but does NOT take the host-wide quiescence admission gate, which cannot be
reached on this host (peer agent processes hold load at 12-17).  The dual A/A
nulls are therefore load-˜-the discriminator: a candidate ratio is only
reported as decidable when it sits outside BOTH null intervals.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
sys.path.insert(0, "/data/projects/franken_networkx/scripts")

import perf_harness as ph


def main():
    ph.provenance_header("probe=worst-adjacency-read (gate-bypassed, dual-null gated)")

    import networkx as nx
    import franken_networkx as fnx

    rows = []
    for directed, label in ((False, "Graph"), (True, "DiGraph")):
        gnx, gfx = ph._build_pair(2000, 8000, seed=7, weighted=True, directed=directed)
        probes = list(gnx.edges)[:512]
        nodes = [n for n in list(gnx.nodes)[:512]]

        fnx_ev, nx_ev = gfx.edges, gnx.edges

        def nx_edge(*, view=nx_ev, edges=probes):
            return [view[e] for e in edges]

        def fnx_edge(*, view=fnx_ev, edges=probes):
            return [view[e] for e in edges]

        def nx_nbr(*, g=gnx, ns=nodes):
            return [len(list(g.neighbors(n))) for n in ns]

        def fnx_nbr(*, g=gfx, ns=nodes):
            return [len(list(g.neighbors(n))) for n in ns]

        rows.append((f"{label}.edges[u,v] x512 [nx/fnx]", nx_edge, fnx_edge))
        rows.append((f"{label}.neighbors(n) x512 [nx/fnx]", nx_nbr, fnx_nbr))

    results = []
    for lab, a, b in rows:
        la, lb = a(), b()
        ba, bb = ph.canonical_bytes(la), ph.canonical_bytes(lb)
        if ba != bb:
            print(f"{lab:<50} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
            continue
        null_a = ph.paired(f"[A/A nx]  {lab}", a, a)
        null_b = ph.paired(f"[A/A fnx] {lab}", b, b)
        cand = ph.paired(lab, a, b)
        ph.report(null_a)
        ph.report(null_b)
        ph.report(cand, (null_a, null_b))
        gate = ph.gate_decision(cand, null_a, null_b)
        results.append({
            "label": lab,
            "ratio_p50": cand.ratio_p50,
            "ratio_ci": list(cand.ratio_ci),
            "null_nx_median": null_a.ratio_p50,
            "null_nx_ci": list(null_a.ratio_ci),
            "null_fnx_median": null_b.ratio_p50,
            "null_fnx_ci": list(null_b.ratio_ci),
            "decidable": gate["decidable"],
            "decision_gate": gate,
            "p50_us": [cand.p50_a * 1e6, cand.p50_b * 1e6],
            "wins": cand.wins,
        })

    print("\nsorted by ratio (worst first):", flush=True)
    for r in sorted(results, key=lambda r: r["ratio_p50"]):
        print(f"  {r['ratio_p50']:7.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"decidable={r['decidable']}  {r['label']}", flush=True)
    print("probe_results_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
