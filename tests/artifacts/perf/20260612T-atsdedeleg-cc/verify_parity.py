import warnings, time, hashlib, json
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx

def dag(n, p, seed):
    g = nx.gnp_random_graph(n, p, seed=seed, directed=True)
    return nx.DiGraph((u, v) for u, v in g.edges() if u < v)

fails = 0; fps = []; total = 0
for seed in range(25):
    n = 5 + (seed % 7)
    D = dag(n, 0.35, seed)
    order = list(range(n)); order = order[::-1] if seed % 2 else order
    Dr = nx.DiGraph(); Dr.add_nodes_from(order); Dr.add_edges_from(D.edges())
    gf = fnx.DiGraph(Dr)
    nx_list = [tuple(s) for s in nx.all_topological_sorts(Dr)]
    fx_list = [tuple(s) for s in fnx.all_topological_sorts(gf)]
    total += 1
    if nx_list != fx_list:
        fails += 1; print('MISMATCH seed', seed, 'n', n, 'nx#', len(nx_list), 'fnx#', len(fx_list))
    fps.append((seed, fx_list[:50]))

empty = nx.DiGraph(); gf = fnx.DiGraph(empty)
e_nx = [tuple(s) for s in nx.all_topological_sorts(empty)]; e_fx = [tuple(s) for s in fnx.all_topological_sorts(gf)]
print('empty: match', e_nx == e_fx, e_fx)
single = nx.DiGraph(); single.add_node(7); gf = fnx.DiGraph(single)
s_nx = [tuple(s) for s in nx.all_topological_sorts(single)]; s_fx = [tuple(s) for s in fnx.all_topological_sorts(gf)]
print('single: match', s_nx == s_fx, s_fx)
cyc = nx.DiGraph([(0,1),(1,2),(2,0)]); gf = fnx.DiGraph(cyc)
try:
    list(fnx.all_topological_sorts(gf)); print('cyclic: NO RAISE (BUG)')
except nx.NetworkXUnfeasible as ex: print('cyclic: raised NetworkXUnfeasible OK')
sha = hashlib.sha256(json.dumps(fps, sort_keys=True, default=str).encode()).hexdigest()
print('full-enum cases', total, 'mismatches', fails)
print('GOLDEN', sha)

def tm(f, r=7):
    ts = []
    for _ in range(r): t0 = time.perf_counter(); f(); ts.append(time.perf_counter() - t0)
    return min(ts) * 1e6
for n in [250, 600, 1200]:
    D = dag(n, 0.05, 1); gf = fnx.DiGraph(D)
    rn = tm(lambda: next(nx.all_topological_sorts(D))); rf = tm(lambda: next(fnx.all_topological_sorts(gf)))
    print('bench n=%d first-sort: nx=%.1fus fnx=%.1fus speedup=%.1fx'%(n, rn, rf, rn/rf))
