"""Substrate-epoch baseline harness (br-r37-c1-d58s8).
Run on a QUIET host (load < 10); interleaved min-of-9 per fn."""
import time, random, json, sys
import networkx as nx
import franken_networkx as fnx

rnd = random.Random(1)
edges = [(rnd.randrange(3000), rnd.randrange(3000)) for _ in range(12000)]
gf, gn = fnx.DiGraph(edges), nx.DiGraph(edges)
gfu, gnu = fnx.Graph(edges), nx.Graph(edges)
gf2 = fnx.relabel_nodes(gfu, lambda x: x + 5000)
gn2 = nx.relabel_nodes(gnu, lambda x: x + 5000)
wf = fnx.Graph(); wn = nx.Graph()
for u, v in edges:
    if u != v:
        wf.add_edge(u, v, weight=1 + (u % 5)); wn.add_edge(u, v, weight=1 + (u % 5))

def t(f, n=9):
    best = 1e9
    for _ in range(n):
        s = time.perf_counter(); f(); best = min(best, time.perf_counter() - s)
    return best

ROWS = [
    ("compose", lambda: fnx.compose(gfu, gfu), lambda: nx.compose(gnu, gnu)),
    ("union", lambda: fnx.union(gfu, gf2), lambda: nx.union(gnu, gn2)),
    ("bfs_tree directed", lambda: fnx.bfs_tree(gf, 0), lambda: nx.bfs_tree(gn, 0)),
    ("sssp_len directed", lambda: fnx.single_source_shortest_path_length(gf, 0), lambda: nx.single_source_shortest_path_length(gn, 0)),
    ("dijkstra weighted", lambda: fnx.single_source_dijkstra_path_length(wf, 0), lambda: nx.single_source_dijkstra_path_length(wn, 0)),
    ("betweenness k=60", lambda: fnx.betweenness_centrality(gfu, k=60, seed=1), lambda: nx.betweenness_centrality(gnu, k=60, seed=1)),
    ("closeness", lambda: fnx.closeness_centrality(gfu), lambda: nx.closeness_centrality(gnu)),
    ("pagerank", lambda: fnx.pagerank(gf), lambda: nx.pagerank(gn)),
    ("copy", lambda: gf.copy(), lambda: gn.copy()),
    ("to_directed", lambda: gfu.to_directed(), lambda: gnu.to_directed()),
    ("Graph(edges) ctor", lambda: fnx.Graph(edges), lambda: nx.Graph(edges)),
]
out = {}
for name, ff, fn_ in ROWS:
    a, b = t(ff), t(fn_)
    out[name] = {"fnx_ms": round(a * 1000, 2), "nx_ms": round(b * 1000, 2), "ratio": round(a / b, 3)}
    print(f"{name:22s} fnx {a*1000:8.1f}ms  nx {b*1000:7.1f}ms  {a/b:5.2f}x")
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/dev/stdout", "w"), indent=1)
# P1 landed 2026-06-06: DiGraph::csr() revision-keyed CSR cache + first
# kernel port (sssp_len directed w/ parents). Loaded-host directional
# signal: 0.47x vs nx (~2x faster). Quiet-host run still owed.
# P1 COMPLETE 2026-06-07 (br-r37-c1-d58s8): every directed traversal /
# shortest-path kernel on integer CSR. Loaded-host directional ratios:
# sssp 0.47x, bfs_edges 0.62x, dfs_edges 0.51x, dijkstra -40% kernel,
# bellman 0.67x, bfs_layers 0.28x, bfs/dfs_tree 0.74x/0.72x.
# Quiet-host formal baseline still owed. P2 next: NodeId edge side-table.
# POST-P1 BASELINE CAPTURED 2026-06-07, load ~15-17 (lowest window in 16
# sessions; re-run if a <10 window appears): see
# baseline_post_p1_load15.json. P1 confirmed (sssp 0.41x, bfs_tree 0.69x,
# pagerank 0.73x, betweenness 0.99x, closeness 0.06x). REMAINING GAPS =
# construction family: Graph(edges) ctor 3.77x, union 2.13x, compose
# 1.71x, copy 1.17x, dijkstra-weighted 1.20x -> P2 priority confirmed.
# QUIET SCOREBOARD 2026-06-07 (load 14-19, quietest of the epoch):
# scoreboard_quiet_load15.json. WINS: bfs_tree 0.31x, sssp 0.30x,
# closeness 0.06x, copy 0.42x, to_directed 0.56x, pagerank 0.82x,
# union 1.13x, betweenness 1.03x. REGRESSIONS FOUND+FIXED same session:
# dijkstra-weighted 1.91x + compose 1.92x = the String-lookup tradeoff
# biting index-holding paths -> edge_attrs_by_indices accessors +
# index-keyed CSR weight builders (1.66x) + pred-based length queries
# replacing full-path builds (1.33x). compose recheck owed next quiet
# window post-fix.
