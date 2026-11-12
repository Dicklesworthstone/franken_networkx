"""Post-w7nn3 delegation re-audit: pred-order-sensitive directed fns on
tie-rich graphs. Pre-w7nn3, delegation validations ran against a
conversion that scrambled pred rows — re-verify now that it's faithful.
"""
import random

import networkx as nx
import franken_networkx as fnx


def tie_rich(mod, seed=23, n=10, m=30):
    """Directed graph with many equal-length paths + a tie diamond."""
    g = mod.DiGraph()
    g.add_edge("s", "a")
    g.add_edge("s", "b")
    g.add_edge("b", "t")
    g.add_edge("a", "t")
    rnd = random.Random(seed)
    for _ in range(m):
        u, v = rnd.randrange(n), rnd.randrange(n)
        if u != v:
            g.add_edge(u, v)
    g.add_edge("t", 0)
    g.add_edge(n - 1, "s")
    return g


def rr(x, depth=0):
    if depth > 6:
        return repr(x)
    if isinstance(x, tuple):
        return tuple(rr(i, depth + 1) for i in x)
    if isinstance(x, list):
        return [rr(i, depth + 1) for i in x]
    if isinstance(x, (set, frozenset)):
        return sorted(repr(i) for i in x)
    if isinstance(x, dict):
        return {repr(k): rr(v, depth + 1) for k, v in x.items()}
    if hasattr(x, "adj"):
        return {repr(n): [repr(y) for y in x.adj[n]] for n in x}
    return repr(x)


CASES = [
    ("all_shortest_paths", lambda m, g: list(m.all_shortest_paths(g, "s", "t"))),
    ("all_simple_paths", lambda m, g: list(m.all_simple_paths(g, "s", "t", cutoff=5))),
    ("all_simple_edge_paths", lambda m, g: list(m.all_simple_edge_paths(g, "s", "t", cutoff=4))),
    ("all_topological_sorts", lambda m, g: list(m.all_topological_sorts(m.dag(g)) if hasattr(m, "dag") else [])),
    ("simple_cycles", lambda m, g: list(m.simple_cycles(g))),
    ("eulerian_path_has", lambda m, g: m.has_eulerian_path(g)),
    ("flow_hierarchy", lambda m, g: m.flow_hierarchy(g)),
    ("trophic_levels", lambda m, g: m.trophic_levels(m.DiGraph([(1, 2), (2, 3), (1, 3)]))),
    ("johnson", lambda m, g: m.johnson(g)),
    ("floyd_warshall", lambda m, g: {k: dict(v) for k, v in m.floyd_warshall(g).items()}),
    ("bfs_labeled_edges", lambda m, g: list(m.generic_bfs_edges(g, "s"))),
    ("voronoi_cells", lambda m, g: m.voronoi_cells(g, {"s", 0})),
    ("immediate_dominators", lambda m, g: m.immediate_dominators(g, "s")),
    ("dominance_frontiers", lambda m, g: m.dominance_frontiers(g, "s")),
    ("transitive_closure", lambda m, g: rr(m.transitive_closure(g))),
    ("transitive_reduction_dag", lambda m, g: rr(m.transitive_reduction(m.DiGraph([(1, 2), (2, 3), (1, 3)])))),
    ("condensation", lambda m, g: rr(m.condensation(g))),
    ("pagerank", lambda m, g: {repr(k): round(v, 12) for k, v in m.pagerank(g).items()}),
    ("hits", lambda m, g: tuple({repr(k): round(v, 10) for k, v in d.items()} for d in m.hits(g, max_iter=200))),
    ("in_degree_centrality", lambda m, g: m.in_degree_centrality(g)),
    ("katz_centrality", lambda m, g: {repr(k): round(v, 12) for k, v in m.katz_centrality(g).items()}),
    ("reverse_view_rows", lambda m, g: rr(m.reverse_view(g))),
    ("edge_bfs_reverse", lambda m, g: list(m.edge_bfs(g, "t", orientation="reverse"))),
    ("edge_dfs_reverse", lambda m, g: list(m.edge_dfs(g, "t", orientation="reverse"))),
    ("ancestors_t", lambda m, g: m.ancestors(g, "t")),
    ("lowest_common_ancestor", lambda m, g: m.lowest_common_ancestor(m.DiGraph([(0, 2), (1, 2), (0, 1)]), 1, 2)),
]

for name, fn in CASES:
    try:
        a = rr(fn(fnx, tie_rich(fnx)))
    except Exception as e:
        a = ("ERR", type(e).__name__, str(e)[:60])
    try:
        b = rr(fn(nx, tie_rich(nx)))
    except Exception as e:
        b = ("ERR", type(e).__name__, str(e)[:60])
    if a != b:
        print(f"DIVERGES {name}:\n  fnx={str(a)[:140]}\n  nx ={str(b)[:140]}")
print("sweep done")
