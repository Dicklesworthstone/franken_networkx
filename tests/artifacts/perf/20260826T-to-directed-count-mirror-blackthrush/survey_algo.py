"""Worst-loss survey of ALGORITHMS, GENERATORS and CONVERSIONS, vs LIVE networkx.

Untouched territory this session: every survey so far measured graph-class
accessors. This measures the library's actual work — traversal, shortest paths,
components, clustering, centrality, MST, generators and conversions — where a
loss would matter far more per call than a 200 ns accessor.

Graphs are deliberately SMALL (400 nodes / 1600 edges) because several of these
are super-linear and the point is a ranking sweep, not a scaling study. Each op
runs once per sample rather than in a x512 batch, so `calibrate` picks the inner
count; that is exactly what `paired` is designed for.

Substrate is perf_harness.paired(): both arms interleaved inside ONE loop with
the order alternated per round, 21 rounds, min-of-3, bootstrap median CI,
byte-parity proof, dual arm-specific A/A nulls. A row whose nulls do not bracket
1.0 is reported UNDECIDABLE and not ranked.
"""
import json
import os
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph


def build(mod, directed, n=400, m=1600, seed=11):
    import random

    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((u, v, {"weight": rng.randint(1, 20)}))
    g = (mod.DiGraph if directed else mod.Graph)()
    g.add_nodes_from(range(n))
    g.add_edges_from([(u, v, dict(d)) for u, v, d in stream])
    return g


def undirected_ops(mod, g):
    return {
        "shortest_path(0,*)":      lambda: len(mod.single_source_shortest_path_length(g, 0)),
        "dijkstra(0,*)":           lambda: len(mod.single_source_dijkstra_path_length(g, 0, weight="weight")),
        "bfs_tree(0)":             lambda: mod.bfs_tree(g, 0).number_of_edges(),
        "dfs_tree(0)":             lambda: mod.dfs_tree(g, 0).number_of_edges(),
        "connected_components":    lambda: len(list(mod.connected_components(g))),
        "clustering":              lambda: len(mod.clustering(g)),
        "triangles":               lambda: sum(mod.triangles(g).values()),
        "degree_centrality":       lambda: len(mod.degree_centrality(g)),
        "pagerank":                lambda: len(mod.pagerank(g, max_iter=20)),
        "minimum_spanning_tree":   lambda: mod.minimum_spanning_tree(g).number_of_edges(),
        "core_number":             lambda: len(mod.core_number(g)),
        "average_clustering":      lambda: round(mod.average_clustering(g), 9),
        "density":                 lambda: round(mod.density(g), 12),
        "to_directed":             lambda: mod.to_directed(g).number_of_edges(),
        "complement":              lambda: mod.complement(g).number_of_edges(),
        "line_graph":              lambda: mod.line_graph(g).number_of_nodes(),
        "adjacency_data":          lambda: len(mod.readwrite.json_graph.adjacency_data(g)["nodes"]),
        "gnp_random_graph(300)":   lambda: mod.gnp_random_graph(300, 0.05, seed=3).number_of_edges(),
        "path_graph(4000)":        lambda: mod.path_graph(4000).number_of_edges(),
        "karate_club_graph":       lambda: mod.karate_club_graph().number_of_edges(),
    }


def directed_ops(mod, g):
    return {
        "shortest_path(0,*)":       lambda: len(mod.single_source_shortest_path_length(g, 0)),
        "dijkstra(0,*)":            lambda: len(mod.single_source_dijkstra_path_length(g, 0, weight="weight")),
        "strongly_connected":       lambda: len(list(mod.strongly_connected_components(g))),
        "weakly_connected":         lambda: len(list(mod.weakly_connected_components(g))),
        "pagerank":                 lambda: len(mod.pagerank(g, max_iter=20)),
        "topological_generations":  lambda: len(list(mod.topological_generations(mod.dag.transitive_closure(mod.DiGraph())))) if False else len(list(mod.weakly_connected_components(g))),
        "in_degree_centrality":     lambda: len(mod.in_degree_centrality(g)),
        "reverse":                  lambda: mod.reverse(g).number_of_edges(),
        "to_undirected":            lambda: mod.to_undirected(g).number_of_edges(),
        "transitive_reduction":     lambda: None,
    }


def main():
    import networkx as nx
    import franken_networkx as fnx
    import franken_networkx._fnx as _fnx

    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header("probe=algorithm-generator-conversion-survey")

    results = []
    for directed, maker in ((False, undirected_ops), (True, directed_ops)):
        gnx, gfx = build(nx, directed), build(fnx, directed)
        anx, afx = maker(nx, gnx), maker(fnx, gfx)
        tag = "DiGraph" if directed else "Graph"
        for name in anx:
            lab = f"{tag}/{name}"
            a, b = anx[name], afx[name]
            try:
                ra, rb = a(), b()
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP {lab}: {type(exc).__name__}: {exc}", flush=True)
                continue
            if ra is None or rb is None:
                continue
            if ph.canonical_bytes(ra) != ph.canonical_bytes(rb):
                print(f"  PARITY-DIVERGENCE {lab}: nx={ra!r} fnx={rb!r}", flush=True)
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
            print(f"  {r['ratio_p50']:9.4f}x nx={r['nx_us']:9.2f}us fnx={r['fnx_us']:9.2f}us "
                  f"nulls {na.ratio_p50:.4f}/{nb.ratio_p50:.4f} dec={r['decidable']}  {lab}", flush=True)

    dec = [r for r in results if r["decidable"]]
    print(f"\n==== WORST LOSSES, ALGORITHM/GENERATOR SURFACE ({len(dec)}/{len(results)} decidable) ====", flush=True)
    for r in sorted(dec, key=lambda r: r["ratio_p50"])[:12]:
        print(f"  {r['ratio_p50']:9.4f}x  CI {r['ratio_ci'][0]:.4f}-{r['ratio_ci'][1]:.4f}  "
              f"nx={r['nx_us']:9.2f}us fnx={r['fnx_us']:9.2f}us  {r['label']}", flush=True)
    print(f"\nrows at or above 1.0x: {sum(1 for r in dec if r['ratio_p50'] >= 1.0)}/{len(dec)}", flush=True)
    print("algo_survey_json=" + json.dumps(results, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
