import hashlib, json, random
import networkx as nx, franken_networkx as fnx

def build(N, m, seed, weighted=True, directed=False):
    if directed:
        Gnx = nx.gnp_random_graph(N, 0.02, seed=seed, directed=True)
        Gfnx = fnx.gnp_random_graph(N, 0.02, seed=seed, directed=True)
    else:
        Gnx = nx.barabasi_albert_graph(N, m, seed=seed)
        Gfnx = fnx.barabasi_albert_graph(N, m, seed=seed)
    if weighted:
        rnd = random.Random(seed*7+1)
        for u, v in list(Gnx.edges()):
            w = rnd.random()+0.1
            Gnx[u][v]['weight'] = w; Gfnx[u][v]['weight'] = w
    return Gnx, Gfnx

def canon(d):
    # dict in INSERTION (finalize) order: keys + values, order-sensitive
    return json.dumps([(repr(k), round(float(v), 12)) for k, v in d.items()])

results = {}
mism = 0
for directed in (False, True):
    for weighted in (True, False):
        for N, m, seed in ((2000,4,42),(300,3,7),(80,2,5)):
            Gnx, Gfnx = build(N, m, seed, weighted, directed)
            for src in (0, N//3):
                rnx = nx.single_source_dijkstra_path_length(Gnx, src)
                rfnx = fnx.single_source_dijkstra_path_length(Gfnx, src)
                cnx, cfnx = canon(rnx), canon(rfnx)
                key = f"d{directed}_w{weighted}_N{N}_s{seed}_src{src}"
                ok = (cnx == cfnx)
                results[key] = hashlib.sha256(cfnx.encode()).hexdigest()
                if not ok:
                    mism += 1
                    print("MISMATCH", key)
                    a, b = json.loads(cnx), json.loads(cfnx)
                    print("  len nx", len(a), "fnx", len(b))
                    for i,(x,y) in enumerate(zip(a,b)):
                        if x!=y:
                            print("  first diff at", i, "nx", x, "fnx", y); break
print(f"mismatches={mism} cases={len(results)}")
overall = hashlib.sha256("|".join(f"{k}={results[k]}" for k in sorted(results)).encode()).hexdigest()
print("DIJKSTRA_GOLDEN", overall)
