"""Post-w7nn3 delegation re-audit, round 2: broad battery with a
self-determinism gate (call nx twice; skip upstream-nondeterministic
fns like hits/svds-based instead of false-flagging)."""
import random
import networkx as nx
import franken_networkx as fnx


def tie_dag(mod):
    g = mod.DiGraph()
    for e in [(0, 2), (1, 2), (0, 1), (2, 4), (2, 3), (3, 5), (4, 5), (0, 5)]:
        g.add_edge(*e)
    return g


def tie_rich(mod, seed=23):
    g = mod.DiGraph()
    g.add_edge("s", "a"); g.add_edge("s", "b"); g.add_edge("b", "t"); g.add_edge("a", "t")
    rnd = random.Random(seed)
    for _ in range(30):
        u, v = rnd.randrange(10), rnd.randrange(10)
        if u != v:
            g.add_edge(u, v)
    g.add_edge("t", 0); g.add_edge(9, "s")
    return g


def tie_undirected(mod, seed=7):
    g = mod.Graph()
    rnd = random.Random(seed)
    for _ in range(40):
        u, v = rnd.randrange(12), rnd.randrange(12)
        if u != v:
            g.add_edge(u, v, weight=1 + (u + v) % 3)
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
        out = {repr(n): [repr(y) for y in x.adj[n]] for n in x}
        if x.is_directed():
            out["__pred__"] = {repr(n): [repr(y) for y in x.pred[n]] for n in x}
        return out
    if isinstance(x, float):
        return round(x, 9)
    return repr(x)


D = [  # (name, builder, fn)
    ("all_topological_sorts", tie_dag, lambda m, g: list(m.all_topological_sorts(g))),
    ("lexicographical_topological_sort", tie_dag, lambda m, g: list(m.lexicographical_topological_sort(g))),
    ("topological_generations", tie_dag, lambda m, g: list(m.topological_generations(g))),
    ("dag_longest_path", tie_dag, lambda m, g: m.dag_longest_path(g)),
    ("antichains", tie_dag, lambda m, g: list(m.antichains(g))),
    ("transitive_reduction", tie_dag, lambda m, g: rr(m.transitive_reduction(g))),
    ("dominance_frontiers", tie_dag, lambda m, g: m.dominance_frontiers(g, 0)),
    ("dag_to_branching", tie_dag, lambda m, g: rr(m.dag_to_branching(g))),
    ("greedy_color_directed", tie_rich, lambda m, g: m.greedy_color(g)),
    ("eccentricity", tie_rich, lambda m, g: m.eccentricity(g.subgraph(max(m.strongly_connected_components(g), key=len)).copy())),
    ("average_shortest_path_length", tie_rich, lambda m, g: round(m.average_shortest_path_length(g.subgraph(max(m.strongly_connected_components(g), key=len)).copy()), 9)),
    ("core_number_dir", tie_rich, lambda m, g: m.core_number(g)),
    ("flow_hierarchy", tie_rich, lambda m, g: round(m.flow_hierarchy(g), 9)),
    ("goldberg_radzik", tie_rich, lambda m, g: tuple(dict(d) for d in m.goldberg_radzik(g, "s"))),
    ("maximum_branching", tie_rich, lambda m, g: rr(m.maximum_branching(g))),
    ("min_cost_flow_zero", tie_dag, lambda m, g: m.max_flow_min_cost(g, 0, 5)),
]
U = [
    ("stoer_wagner", lambda m, g: m.stoer_wagner(g)),
    ("articulation_points", lambda m, g: list(m.articulation_points(g))),
    ("bridges", lambda m, g: list(m.bridges(g))),
    ("biconnected_components", lambda m, g: [sorted(map(repr, c)) for c in m.biconnected_components(g)]),
    ("chain_decomposition", lambda m, g: list(m.chain_decomposition(g))),
    ("is_chordal", lambda m, g: m.is_chordal(g)),
    ("k_components", lambda m, g: rr(dict(m.k_components(g)))),
    ("k_edge_components", lambda m, g: [sorted(map(repr, c)) for c in m.k_edge_components(g, 2)]),
    ("max_weight_clique", lambda m, g: m.max_weight_clique(g, weight=None)),
    ("min_weight_matching", lambda m, g: sorted(map(repr, m.min_weight_matching(g)))),
    ("junction_tree", lambda m, g: rr(m.junction_tree(g))),
    ("core_number", lambda m, g: m.core_number(g)),
    ("onion_layers", lambda m, g: m.onion_layers(g)),
    ("wiener_index", lambda m, g: round(m.wiener_index(g), 9)),
    ("voronoi_cells_u", lambda m, g: rr(m.voronoi_cells(g, {0, 5}))),
    ("simple_cycles_u", lambda m, g: sorted(rr(c) for c in m.simple_cycles(g, length_bound=5))),
]

flags = skips = 0
for name, builder, fn in D:
    try:
        n1, n2 = rr(fn(nx, builder(nx))), rr(fn(nx, builder(nx)))
        if n1 != n2:
            print(f"SKIP {name}: nx nondeterministic"); skips += 1; continue
        a = rr(fn(fnx, builder(fnx)))
    except Exception as e:
        try:
            fn(nx, builder(nx)); print(f"ERR-FNX {name}: {type(e).__name__} {str(e)[:70]}"); flags += 1
        except Exception:
            pass
        continue
    if a != n1:
        print(f"DIVERGES {name}:\n  fnx={str(a)[:130]}\n  nx ={str(n1)[:130]}"); flags += 1
for name, fn in U:
    try:
        n1, n2 = rr(fn(nx, tie_undirected(nx))), rr(fn(nx, tie_undirected(nx)))
        if n1 != n2:
            print(f"SKIP {name}: nx nondeterministic"); skips += 1; continue
        a = rr(fn(fnx, tie_undirected(fnx)))
    except Exception as e:
        try:
            fn(nx, tie_undirected(nx)); print(f"ERR-FNX {name}: {type(e).__name__} {str(e)[:70]}"); flags += 1
        except Exception:
            pass
        continue
    if a != n1:
        print(f"DIVERGES {name}:\n  fnx={str(a)[:130]}\n  nx ={str(n1)[:130]}"); flags += 1
print(f"round-2 done: {flags} flags, {skips} upstream-nondeterministic skips")
