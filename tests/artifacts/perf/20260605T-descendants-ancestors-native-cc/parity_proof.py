import os, hashlib, json, time, random
for v in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[v]='2'
import networkx as nx, franken_networkx as fnx

def graphs(seed, directed, n):
    rng = random.Random(seed)
    if directed:
        Gn = nx.gnp_random_graph(n, 0.08, seed=seed, directed=True)
    else:
        Gn = nx.gnp_random_graph(n, 0.06, seed=seed)
    Fn = (fnx.DiGraph if directed else fnx.Graph)()
    Fn.add_nodes_from(list(Gn.nodes()))
    Fn.add_edges_from(list(Gn.edges()))
    return Fn, Gn

sha = hashlib.sha256(); mism = 0; cases = 0
for case in range(80):
    directed = case % 2 == 1
    n = 10 + case % 30
    F, G = graphs(2000+case, directed, n)
    nodes = list(G.nodes())
    for s in nodes:
        for fn in ('descendants','ancestors'):
            rf = sorted(getattr(fnx, fn)(F, s))
            rg = sorted(getattr(nx, fn)(G, s))
            if rf != rg:
                mism += 1
                if mism <= 5: print(f"MISMATCH {fn} case={case} dir={directed} s={s}\n fnx={rf}\n nx ={rg}")
            sha.update(f"{case}|{directed}|{fn}|{s}|{rg}".encode())
            cases += 1
# error parity: missing node
for fn in ('descendants','ancestors'):
    for mod,g in (('fnx',fnx.Graph()),('nx',nx.Graph())):
        g.add_edge(1,2)
    Fg=fnx.Graph(); Fg.add_edge(1,2); Gg=nx.Graph(); Gg.add_edge(1,2)
    try: getattr(fnx,fn)(Fg, 99); ef="noerr"
    except Exception as e: ef=f"{type(e).__name__}:{e}"
    try: getattr(nx,fn)(Gg, 99); en="noerr"
    except Exception as e: en=f"{type(e).__name__}:{e}"
    print(f"{fn} missing-node: fnx[{ef}] nx[{en}] match={ef==en}")
print(f"cases={cases} mismatches={mism}")
print(f"golden_sha256={sha.hexdigest()}")
