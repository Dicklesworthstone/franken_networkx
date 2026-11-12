"""Adjacency reads vs LIVE networkx, by node-key type, for one built arm.

Run once per arm with PYTHONPATH pointing at that arm's shadow package.  The
int rows are the TREATED rows; the str rows are CONTROLS that the int-only
canonicalization lever must not move, and they also bound the binary noise
floor (two builds of the same project differing in one function have been
observed to disagree ~5% on untouched rows).

Substrate is perf_harness's own paired(): both arms interleaved inside ONE
loop with the order alternated per round, 21 rounds, min-of-3 per slot,
bootstrap median CI, dual arm-specific A/A nulls, byte-parity proof, and the
in-process ELF sha256 from provenance_header.
"""
import json
import os
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
    arm = os.environ.get("FNX_ARM", "unlabelled")
    import franken_networkx._fnx as _fnx

    expected = os.environ.get("FNX_EXPECT_SO")
    if expected and os.path.realpath(_fnx.__file__) != os.path.realpath(expected):
        raise RuntimeError(
            f"wrong extension loaded: {_fnx.__file__} is not {expected}"
        )
    ph.provenance_header(f"probe=adjacency-reads-by-keytype arm={arm}")

    rows = []
    for directed, dlabel in ((False, "Graph"), (True, "DiGraph")):
        for as_int, klabel in ((True, "int-keys"), (False, "str-keys")):
            gnx, gfx = build(2000, 8000, seed=7, directed=directed, as_int=as_int)
            probes = list(gnx.edges)[:512]
            nodes = list(gnx.nodes)[:512]
            nx_ev, fnx_ev = gnx.edges, gfx.edges

            def a_edge(*, view=nx_ev, edges=probes):
                return [view[e] for e in edges]

            def b_edge(*, view=fnx_ev, edges=probes):
                return [view[e] for e in edges]

            def a_has(*, g=gnx, ns=nodes):
                return [g.has_node(n) for n in ns]

            def b_has(*, g=gfx, ns=nodes):
                return [g.has_node(n) for n in ns]

            def a_nbr(*, g=gnx, ns=nodes):
                return [len(list(g.neighbors(n))) for n in ns]

            def b_nbr(*, g=gfx, ns=nodes):
                return [len(list(g.neighbors(n))) for n in ns]

            rows.append((f"{dlabel}.edges[u,v]  x512 {klabel}", a_edge, b_edge))
            rows.append((f"{dlabel}.has_node(n) x512 {klabel}", a_has, b_has))
            rows.append((f"{dlabel}.neighbors(n) x512 {klabel}", a_nbr, b_nbr))

    results = []
    for lab, a, b in rows:
        if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
            print(f"{lab:<46} PARITY-DIVERGENCE -- NOT TIMED", flush=True)
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
            "nx_us": cand.p50_a * 1e6, "fnx_us": cand.p50_b * 1e6, "wins": cand.wins,
        })

    print(f"\narm={arm} sorted by ratio (worst first):", flush=True)
    for r in sorted(results, key=lambda r: r["ratio_p50"]):
        print(f"  {r['ratio_p50']:7.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"nx={r['nx_us']:7.2f}us fnx={r['fnx_us']:7.2f}us  dec={r['decidable']}  {r['label']}",
              flush=True)
    print("arm_results_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
