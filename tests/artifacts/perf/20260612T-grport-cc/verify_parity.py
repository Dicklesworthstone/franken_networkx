import warnings, time, random, hashlib, json
warnings.filterwarnings('ignore')
import networkx as nx, franken_networkx as fnx

def rebuilt(G):  # fair baseline: same adjacency order as fnx.DiGraph(G)
    H = nx.DiGraph(); H.add_nodes_from(G.nodes()); H.add_edges_from(G.edges(data=True)); return H

fails = 0; fps = []
for seed in range(20):
    n = 20 + seed * 6
    G = nx.gnp_random_graph(n, 0.06, seed=seed, directed=True)
    rng = random.Random(seed)
    for u, v in G.edges():
        G.edges[u, v]['weight'] = rng.randint(-1, 9) if seed % 3 == 0 else (1 if seed % 3 == 1 else rng.randint(1, 4))
    gf = fnx.DiGraph(G); ng = rebuilt(G)
    try:
        fp, fd = fnx.goldberg_radzik(gf, 0)
        np_, nd = nx.goldberg_radzik(ng, 0)
        if (dict(fp), dict(fd)) != (dict(np_), dict(nd)):
            fails += 1; print('MISMATCH seed', seed)
        fps.append((seed, sorted(fp.items()), sorted(fd.items())))
    except nx.NetworkXUnbounded:
        try:
            nx.goldberg_radzik(ng, 0); fails += 1; print('seed', seed, 'fnx raised, nx did not')
        except nx.NetworkXUnbounded:
            fps.append((seed, 'NEGCYCLE'))
# negative-cycle case
ncg = nx.cycle_graph(5, create_using=nx.DiGraph); ncg[1][2]['weight'] = -7
gf = fnx.DiGraph(ncg)
try:
    fnx.goldberg_radzik(gf, 0); print('neg-cycle: NO RAISE (BUG)')
except nx.NetworkXUnbounded: print('neg-cycle: raised OK')
sha = hashlib.sha256(json.dumps(fps, sort_keys=True, default=str).encode()).hexdigest()
print('mismatches vs nx:', fails, '/ 20'); print('GOLDEN', sha)

def tm(f, r=7):
    ts = []
    for _ in range(r): t0 = time.perf_counter(); f(); ts.append(time.perf_counter() - t0)
    return min(ts) * 1e3
for n in [200, 300, 500, 800]:
    G = nx.gnp_random_graph(n, 0.04, seed=1, directed=True); gf = fnx.DiGraph(G)
    print('bench n=%d: nx=%.3f fnx=%.3f ratio=%.2f'%(n, tm(lambda: nx.goldberg_radzik(G, 0)), tm(lambda: fnx.goldberg_radzik(gf, 0)), tm(lambda: fnx.goldberg_radzik(gf, 0))/tm(lambda: nx.goldberg_radzik(G, 0))))
