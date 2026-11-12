"""Broad worst-ratio survey across the read, traversal and mutation surface.

Finds the current worst vs-networkx row rather than continuing to mine a surface
I have already worked. Every row is perf_harness.paired(): fnx and LIVE networkx
interleaved inside ONE loop with the order alternated per round, dual A/A nulls,
bootstrap median CI. Results are compared before timing, so a row that diverges
is reported rather than timed.

Rows whose nulls do not bracket 1.0 are reported UNDECIDABLE and excluded from
the ranking.
"""
import json
import os
import random
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph


def build(mod, cls, n=800, m=3200, seed=13):
    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (u, v) in seen:
            continue
        seen.add((u, v))
        stream.append((u, v, {"weight": rng.randint(1, 9)}))
    g = getattr(mod, cls)()
    g.add_nodes_from(range(n))
    g.add_edges_from(stream)
    return g, stream


def ops(mod, g, stream, cls):
    pairs = [(u, v) for u, v, _ in stream[:300]]
    nodes = list(range(0, 800, 3))
    multi = cls.startswith("Multi")
    d = {
        "len(G)": lambda: len(g),
        "G.number_of_edges()": lambda: g.number_of_edges(),
        "list(G)": lambda: len(list(g)),
        "list(G.nodes)": lambda: len(list(g.nodes)),
        "list(G.edges)": lambda: len(list(g.edges)),
        "list(G.edges(data=True))": lambda: len(list(g.edges(data=True))),
        "dict(G.degree)": lambda: len(dict(g.degree)),
        "G.adjacency() drained": lambda: sum(1 for _ in g.adjacency()),
        "nodes(data=True)": lambda: len(list(g.nodes(data=True))),
        "G.subgraph(nb).copy()": lambda: g.subgraph(nodes).copy().number_of_edges(),
        "G.edges(nbunch)": lambda: len(list(g.edges(nodes))),
        "G.neighbors bulk": lambda: sum(len(list(g.neighbors(n))) for n in nodes),
        "has_edge bulk": lambda: sum(g.has_edge(u, v) for u, v in pairs),
        "n in G bulk": lambda: sum(n in g for n in nodes),
        "G[u] bulk": lambda: sum(len(g[u]) for u, _ in pairs),
        "nbunch_iter": lambda: len(list(g.nbunch_iter(nodes))),
        "G.copy()": lambda: g.copy().number_of_edges(),
        "to_undirected()": lambda: g.to_undirected().number_of_edges(),
        "to_directed()": lambda: g.to_directed().number_of_edges(),
        "G.reverse()" if g.is_directed() else "G.copy2()":
            (lambda: g.reverse(copy=True).number_of_edges()) if g.is_directed()
            else (lambda: g.copy().number_of_nodes()),
    }
    if not multi:
        d["G.degree(nbunch)"] = lambda: sum(v for _, v in g.degree(nodes))
    # mutation shapes on throwaway copies
    def _mut_add():
        h = getattr(mod, cls)()
        h.add_nodes_from(range(400))
        h.add_edges_from((u % 400, v % 400) for u, v, _ in stream[:800])
        return h.number_of_edges()

    def _mut_remove():
        h = g.copy()
        h.remove_nodes_from(range(0, 200, 2))
        return h.number_of_nodes()

    d["build add_edges_from"] = _mut_add
    d["remove_nodes_from"] = _mut_remove
    return d


def main():
    import networkx as nx
    import franken_networkx as fnx
    import franken_networkx._fnx as _fnx

    ph.provenance_header(f"probe=broad-survey arm={os.environ.get('FNX_ARM', '?')}")
    rows = []
    for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        gn, stream = build(nx, cls)
        gf, _ = build(fnx, cls)
        on, of = ops(nx, gn, stream, cls), ops(fnx, gf, stream, cls)
        for name in on:
            label = f"{cls:12s} {name}"
            a, b = on[name], of[name]
            try:
                ra, rb = a(), b()
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP {label}: {type(exc).__name__}", flush=True)
                continue
            if ra != rb:
                print(f"  PARITY-DIVERGENCE {label}: nx={ra!r} fnx={rb!r}", flush=True)
                continue
            na = ph.paired(f"[A/A nx] {label}", a, a)
            nb = ph.paired(f"[A/A fnx] {label}", b, b)
            cand = ph.paired(label, a, b)
            gate = ph.gate_decision(cand, na, nb)
            rows.append({"label": label, "ratio_p50": cand.ratio_p50,
                         "decidable": gate["decidable"],
                         "nx_us": cand.p50_a * 1e6, "fnx_us": cand.p50_b * 1e6})
            print(f"  {cand.ratio_p50:9.4f}x nx={cand.p50_a * 1e6:10.2f}us "
                  f"fnx={cand.p50_b * 1e6:10.2f}us  {label}"
                  f"{'' if gate['decidable'] else '  UNDECIDABLE'}", flush=True)

    dec = [r for r in rows if r["decidable"]]
    print(f"\n==== WORST ROWS ({len(dec)}/{len(rows)} decidable) ====", flush=True)
    for r in sorted(dec, key=lambda r: r["ratio_p50"])[:15]:
        print(f"  {r['ratio_p50']:9.4f}x nx={r['nx_us']:10.2f}us "
              f"fnx={r['fnx_us']:10.2f}us  {r['label']}", flush=True)
    print(f"\n  rows below 1.0: {sum(1 for r in dec if r['ratio_p50'] < 1.0)}/{len(dec)}",
          flush=True)
    print("broad_json=" + json.dumps(rows, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
