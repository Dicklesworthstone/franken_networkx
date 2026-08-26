"""Worst-loss survey OUTSIDE the adjacency read surface, vs LIVE networkx.

Every previous survey this session covered five adjacency read spellings. That
surface is now characterised and its remaining lever is a project, so this looks
everywhere else: degree, sizing, iteration, membership, node/edge attribute
access, copies, views and a few kernels.

Read-only ops only. Mutation arms are non-stationary (a build/mutate loop is not
a fixed point) and need a scaling-shape design rather than a paired ratio, so
they are deliberately NOT mixed in here.

Substrate is perf_harness.paired(): both arms interleaved inside ONE loop with
the order alternated per round, 21 rounds, min-of-3, bootstrap median CI,
byte-parity proof, dual arm-specific A/A nulls. A row whose nulls do not bracket
1.0 is reported UNDECIDABLE and is not ranked.
"""
import json
import os
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph


def build(cls_name, n=2000, m=8000, seed=7):
    import random
    import networkx as nx
    import franken_networkx as fnx

    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((u, v, {"weight": rng.randint(1, 20)}))
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for g in (gnx, gfx):
        g.add_nodes_from(range(n))
        g.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    if not type(gnx).__module__.startswith("networkx"):
        raise RuntimeError("nx arm is not genuine upstream")
    return gnx, gfx


def ops(g, nodes, pairs):
    """name -> zero-arg callable. Identical source for both libraries."""
    return {
        "degree(n) x512":        lambda: [g.degree(x) for x in nodes],
        "G.degree view build":   lambda: [g.degree for _ in range(64)],
        "len(G) x512":           lambda: [len(g) for _ in range(512)],
        "number_of_edges x512":  lambda: [g.number_of_edges() for _ in range(512)],
        "n in G x512":           lambda: [x in g for x in nodes],
        "has_edge x512":         lambda: [g.has_edge(u, v) for u, v in pairs],
        "G.nodes[n] x512":       lambda: [g.nodes[x] for x in nodes],
        "list(G.nodes)":         lambda: [len(list(g.nodes))],
        "list(G.edges)":         lambda: [len(list(g.edges))],
        "list(G.adj) iter":      lambda: [len(list(g.adj))],
        "G.nodes(data=True)":    lambda: [len(list(g.nodes(data=True)))],
        "G.edges(data=True)":    lambda: [len(list(g.edges(data=True)))],
        "adjacency() sweep":     lambda: [sum(len(r) for _, r in g.adjacency())],
        "G.copy()":              lambda: [g.copy().number_of_edges()],
        "G.subgraph(512)":       lambda: [g.subgraph(nodes).number_of_edges()],
        "G.degree(nbunch)":      lambda: [len(list(g.degree(nodes)))],
        "nbunch_iter":           lambda: [len(list(g.nbunch_iter(nodes)))],
    }


def main():
    import franken_networkx._fnx as _fnx
    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header("probe=wide-surface-worst-loss-survey")

    results = []
    for cls_name in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        gnx, gfx = build(cls_name)
        nodes = list(gnx.nodes)[:512]
        pairs = [(u, v) for u, v, *_ in list(gnx.edges)[:512]]
        anx, afx = ops(gnx, nodes, pairs), ops(gfx, nodes, pairs)
        for name in anx:
            lab = f"{cls_name}/{name}"
            a, b = anx[name], afx[name]
            try:
                if ph.canonical_bytes(a()) != ph.canonical_bytes(b()):
                    print(f"  PARITY-DIVERGENCE  {lab}", flush=True)
                    continue
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP {lab}: {type(exc).__name__}: {exc}", flush=True)
                continue
            na = ph.paired(f"[A/A nx]  {lab}", a, a)
            nb = ph.paired(f"[A/A fnx] {lab}", b, b)
            cand = ph.paired(lab, a, b)
            gate = ph.gate_decision(cand, na, nb)
            results.append({
                "label": lab, "ratio_p50": cand.ratio_p50, "ratio_ci": list(cand.ratio_ci),
                "null_nx": na.ratio_p50, "null_fnx": nb.ratio_p50,
                "decidable": gate["decidable"],
                "nx_us": cand.p50_a * 1e6, "fnx_us": cand.p50_b * 1e6,
            })
            r = results[-1]
            flag = "" if r["decidable"] else "  UNDECIDABLE"
            print(f"  {r['ratio_p50']:8.4f}x nx={r['nx_us']:8.2f}us fnx={r['fnx_us']:8.2f}us "
                  f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f}  {lab}{flag}", flush=True)

    dec = [r for r in results if r["decidable"]]
    print(f"\n==== WORST LOSSES OFF THE ADJACENCY READ SURFACE ({len(dec)}/{len(results)} decidable) ====", flush=True)
    for r in sorted(dec, key=lambda r: r["ratio_p50"])[:15]:
        print(f"  {r['ratio_p50']:8.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"nx={r['nx_us']:8.2f}us fnx={r['fnx_us']:8.2f}us  {r['label']}", flush=True)
    wins = [r for r in dec if r["ratio_p50"] > 1.0]
    print(f"\nrows where fnx BEATS networkx: {len(wins)}/{len(dec)}", flush=True)
    print("wide_survey_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
