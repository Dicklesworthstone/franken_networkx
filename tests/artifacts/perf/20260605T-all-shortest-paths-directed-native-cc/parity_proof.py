import os, hashlib, random
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx

def build(seed, directed, n, p):
    Gn = nx.gnp_random_graph(n, p, seed=seed, directed=directed)
    F = (fnx.DiGraph if directed else fnx.Graph)()
    F.add_nodes_from(list(Gn.nodes()))
    F.add_edges_from(list(Gn.edges()))
    return F, Gn

sha = hashlib.sha256(); mism=0; cases=0; nopath=0
# include karate explicitly (the cited regression)
Kn = nx.karate_club_graph(); Kf = fnx.Graph(); Kf.add_nodes_from(Kn.nodes()); Kf.add_edges_from(Kn.edges())
specials = [(Kf, Kn, True)]
for case in range(120):
    directed = case % 2 == 1
    n = 8 + case % 22; p = 0.12 + (case%4)*0.05
    F, G = build(11000+case, directed, n, p)
    specials.append((F, G, directed))
for F, G, directed in specials:
    nodes = list(G.nodes())
    for s in nodes[:6]:
        for t in nodes[:6]:
            try:
                gn = list(nx.all_shortest_paths(G, s, t))
            except Exception as en:
                try:
                    list(fnx.all_shortest_paths(F, s, t)); rf="noerr"
                except Exception as ef: rf=type(ef).__name__+":"+str(ef)
                ename = type(en).__name__+":"+str(en)
                if rf != ename:
                    mism+=1
                    if mism<=5: print(f"ERR-MISMATCH s={s} t={t} dir={directed}\n nx[{ename}]\n fx[{rf}]")
                nopath+=1
                continue
            gf = list(fnx.all_shortest_paths(F, s, t))
            if gf != gn:
                mism+=1
                if mism<=6: print(f"MISMATCH s={s} t={t} dir={directed}\n nx={gn}\n fx={gf}")
            sha.update(repr((s,t,directed,gn)).encode()); cases+=1
print(f"path-cases={cases} nopath-cases={nopath} mismatches={mism}")
print(f"golden_sha256={sha.hexdigest()}")
