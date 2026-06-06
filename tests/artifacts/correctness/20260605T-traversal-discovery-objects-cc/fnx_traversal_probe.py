"""br-r37-c1-6hpa9: which traversal fns diverge on discovery objects?"""
import networkx as nx
import franken_networkx as fnx


def build(mod, directed=True):
    g = (mod.DiGraph if directed else mod.Graph)()
    g.add_node(28)
    g.add_edge(7, 28.0)
    g.add_edge(28.0, 5)
    g.add_edge(5, 7)
    g.add_edge(5, 9)
    return g


def rr(x):
    if isinstance(x, tuple):
        return tuple(rr(i) for i in x)
    if isinstance(x, (list, set)):
        return sorted(map(rr, x)) if isinstance(x, set) else [rr(i) for i in x]
    if isinstance(x, dict):
        return {rr(k): rr(v) for k, v in x.items()}
    if hasattr(x, "nodes"):
        return [repr(n) for n in x]
    return repr(x)


CASES = [
    ("dfs_edges", lambda m, g: list(m.dfs_edges(g, 7))),
    ("bfs_edges", lambda m, g: list(m.bfs_edges(g, 7))),
    ("dfs_tree", lambda m, g: list(m.dfs_tree(g, 7))),
    ("bfs_tree", lambda m, g: list(m.bfs_tree(g, 7))),
    ("dfs_preorder_nodes", lambda m, g: list(m.dfs_preorder_nodes(g, 7))),
    ("dfs_postorder_nodes", lambda m, g: list(m.dfs_postorder_nodes(g, 7))),
    ("dfs_predecessors", lambda m, g: m.dfs_predecessors(g, 7)),
    ("dfs_successors", lambda m, g: m.dfs_successors(g, 7)),
    ("bfs_predecessors", lambda m, g: dict(m.bfs_predecessors(g, 7))),
    ("bfs_successors", lambda m, g: dict(m.bfs_successors(g, 7))),
    ("bfs_layers", lambda m, g: list(m.bfs_layers(g, [7]))),
    ("descendants", lambda m, g: m.descendants(g, 7)),
    ("ancestors", lambda m, g: m.ancestors(g, 7)),
    ("edge_dfs", lambda m, g: list(m.edge_dfs(g, 7))),
    ("edge_bfs", lambda m, g: list(m.edge_bfs(g, 7))),
    ("generic_bfs_edges", lambda m, g: list(m.generic_bfs_edges(g, 7))),
    ("shortest_path", lambda m, g: m.shortest_path(g, 7, 5)),
    ("single_source_shortest_path_length", lambda m, g: dict(m.single_source_shortest_path_length(g, 7))),
]
for directed in (True, False):
    print(f"--- directed={directed} ---")
    for name, fn in CASES:
        try:
            a = rr(fn(fnx, build(fnx, directed)))
            b = rr(fn(nx, build(nx, directed)))
            if a != b:
                print(f"DIVERGES {name}: fnx={str(a)[:90]} nx={str(b)[:90]}")
        except Exception as e:
            print(f"ERR {name}: {type(e).__name__} {str(e)[:60]}")
