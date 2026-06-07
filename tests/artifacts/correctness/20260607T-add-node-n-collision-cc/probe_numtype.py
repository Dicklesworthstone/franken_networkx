"""Phase B: numpy-type-leak + value parity across centrality/linalg/
link-analysis. nx returns python floats; fnx must not leak np.float64.
Fixed graph both impls. nx self-determinism gated for randomized fns."""
import random
import networkx as nx
import franken_networkx as fnx

R = random.Random(9)
E = [(u,v) for u,v in ((R.randrange(25), R.randrange(25)) for _ in range(90)) if u!=v]
def mk(mod, directed=False):
    g = (mod.DiGraph if directed else mod.Graph)()
    for u,v in E: g.add_edge(u,v, weight=1.5)
    return g

fails = []
def chk(name, fa, fb, typ=True):
    try: a = fa()
    except Exception as e: a = ('ERR', type(e).__name__, str(e)[:40])
    try: b = fb()
    except Exception as e: b = ('ERR', type(e).__name__, str(e)[:40])
    if isinstance(a, dict) and isinstance(b, dict):
        av = [(repr(k), round(float(v),7), type(v).__name__) for k,v in a.items()]
        bv = [(repr(k), round(float(v),7), type(v).__name__) for k,v in b.items()]
        av.sort(); bv.sort()
        if av != bv:
            # separate value vs type
            avt = {k:t for k,_,t in av}; bvt = {k:t for k,_,t in bv}
            tmism = [(k,avt[k],bvt.get(k)) for k in avt if avt[k]!=bvt.get(k)]
            vmism = [(k,dict((kk,vv) for kk,vv,_ in av)[k], dict((kk,vv) for kk,vv,_ in bv).get(k)) for k in dict((kk,vv) for kk,vv,_ in av) if dict((kk,vv) for kk,vv,_ in av)[k]!=dict((kk,vv) for kk,vv,_ in bv).get(k)]
            fails.append((name, f'TYPE{tmism[:3]}' if tmism else '', f'VAL{vmism[:3]}' if vmism else ''))
    else:
        if a != b: fails.append((name, str(a)[:60], str(b)[:60]))

gf, gn = mk(fnx), mk(nx)
chk('degree_centrality', lambda: fnx.degree_centrality(gf), lambda: nx.degree_centrality(gn))
chk('closeness_centrality', lambda: fnx.closeness_centrality(gf), lambda: nx.closeness_centrality(gn))
chk('betweenness_centrality', lambda: fnx.betweenness_centrality(gf), lambda: nx.betweenness_centrality(gn))
chk('eigenvector_centrality', lambda: fnx.eigenvector_centrality(gf, max_iter=1000), lambda: nx.eigenvector_centrality(gn, max_iter=1000))
chk('pagerank', lambda: fnx.pagerank(gf), lambda: nx.pagerank(gn))
chk('clustering', lambda: fnx.clustering(gf), lambda: nx.clustering(gn))
chk('harmonic_centrality', lambda: fnx.harmonic_centrality(gf), lambda: nx.harmonic_centrality(gn))
chk('load_centrality', lambda: fnx.load_centrality(gf), lambda: nx.load_centrality(gn))
chk('katz_centrality', lambda: fnx.katz_centrality(gf, max_iter=5000), lambda: nx.katz_centrality(gn, max_iter=5000))
chk('avg_neighbor_degree', lambda: fnx.average_neighbor_degree(gf), lambda: nx.average_neighbor_degree(gn))
chk('square_clustering', lambda: fnx.square_clustering(gf), lambda: nx.square_clustering(gn))
chk('constraint', lambda: fnx.constraint(gf), lambda: nx.constraint(gn))
# scalars
chk('transitivity', lambda: round(fnx.transitivity(gf),9), lambda: round(nx.transitivity(gn),9))
chk('density', lambda: (fnx.density(gf), type(fnx.density(gf)).__name__), lambda: (nx.density(gn), type(nx.density(gn)).__name__))
gfd, gnd = mk(fnx, True), mk(nx, True)
chk('pagerank_directed', lambda: fnx.pagerank(gfd), lambda: nx.pagerank(gnd))
chk('in_degree_centrality', lambda: fnx.in_degree_centrality(gfd), lambda: nx.in_degree_centrality(gnd))
chk('reciprocity', lambda: round(fnx.reciprocity(gfd),9), lambda: round(nx.reciprocity(gnd),9))

print('NUMTYPE PROBE:', len(fails), 'divergences')
for n,a,b in fails: print(f'  {n}: {a} | {b}')
