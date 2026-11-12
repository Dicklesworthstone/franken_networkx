import franken_networkx as fnx, networkx as nx, hashlib, time, sys
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
if tag=="AFTER":
    mism=0
    for seed in range(6):
        for n,m in [(100,3),(150,3),(80,4)]:
            for k in [2,3,4]:
                G=nx.barabasi_albert_graph(n,m,seed=seed); Gf=fnx.Graph(G)
                Px=nx.power(G,k); Pf=fnx.power(Gf,k)
                if list(Px.nodes())!=list(Pf.nodes()) or list(Px.edges())!=list(Pf.edges()):
                    mism+=1
    print("comparisons mismatches:",mism)
    G=nx.barabasi_albert_graph(150,3,seed=1); Gf=fnx.Graph(G)
    ef=list(fnx.power(Gf,3).edges())
    print("golden sha:", hashlib.sha256(repr(ef).encode()).hexdigest()[:16],
          "nx:", hashlib.sha256(repr(list(nx.power(G,3).edges())).encode()).hexdigest()[:16])
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
for n,m,k,N in [(150,3,3,10),(250,4,2,8),(150,3,4,6)]:
    G=nx.barabasi_albert_graph(n,m,seed=1); Gf=fnx.Graph(G)
    tf=wm(lambda:fnx.power(Gf,k),N); tx=wm(lambda:nx.power(G,k),N)
    print(f"[{tag}] BA({n},{m})^{k}: fnx={tf*1e3:7.2f}ms nx={tx*1e3:7.2f}ms nx/fnx={tx/tf:.2f}x")
