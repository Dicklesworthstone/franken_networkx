import franken_networkx as fnx, networkx as nx, hashlib, time, sys
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
# correctness across graphs
mism=0
for seed in range(12):
    for n,p in [(40,0.15),(60,0.1),(50,0.2),(30,0.3)]:
        G=nx.gnp_random_graph(n,p,seed=seed); Gf=fnx.Graph(G)
        Bx=nx.make_max_clique_graph(G); Bf=fnx.make_max_clique_graph(Gf)
        if list(Bx.nodes())!=list(Bf.nodes()) or list(Bx.edges())!=list(Bf.edges()):
            mism+=1
if tag=="AFTER":
    print("comparisons mismatches:",mism)
    # golden
    G=nx.gnp_random_graph(60,0.1,seed=2); Gf=fnx.Graph(G)
    ef=list(fnx.make_max_clique_graph(Gf).edges())
    print("golden sha:", hashlib.sha256(repr(ef).encode()).hexdigest()[:16],
          "nx sha:", hashlib.sha256(repr(list(nx.make_max_clique_graph(G).edges())).encode()).hexdigest()[:16])
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
for n,p,N in [(60,0.1,20),(80,0.12,10),(100,0.1,8)]:
    G=nx.gnp_random_graph(n,p,seed=2); Gf=fnx.Graph(G)
    tf=wm(lambda:fnx.make_max_clique_graph(Gf),N); tx=wm(lambda:nx.make_max_clique_graph(G),N)
    print(f"[{tag}] gnp({n},{p}): fnx={tf*1e3:7.3f}ms nx={tx*1e3:7.3f}ms nx/fnx={tx/tf:.2f}x")
