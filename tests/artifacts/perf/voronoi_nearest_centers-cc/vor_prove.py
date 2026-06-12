import franken_networkx as fnx, networkx as nx, time, hashlib, random
random.seed(11)
def cells_repr(c):
    # order-sensitive on dict KEYS, sets normalized
    return repr([(k, sorted(map(repr,v))) for k,v in c.items()])

mism=0; total=0
gens=[]
for n,m,s in [(200,4,1),(500,3,7),(150,5,2),(300,2,9)]:
    gens.append(("ba%d"%n, nx.barabasi_albert_graph(n,m,seed=s)))
gens.append(("gnp", nx.gnp_random_graph(250,0.03,seed=4)))
gens.append(("path", nx.path_graph(120)))
gens.append(("disc", nx.disjoint_union(nx.path_graph(60), nx.cycle_graph(60))))
# weighted graph
Gw=nx.gnp_random_graph(120,0.06,seed=5)
for u,v in Gw.edges(): Gw[u][v]["weight"]=random.randint(1,7)
gens.append(("weighted", Gw))

for name,G in gens:
    Gf=fnx.Graph(G)
    nodes=list(G.nodes())
    for _ in range(6):
        k=random.randint(1,4)
        centers=set(random.sample(nodes, min(k,len(nodes))))
        cx=nx.voronoi_cells(G, centers); cf=fnx.voronoi_cells(Gf, centers)
        total+=1
        if cells_repr(cx)!=cells_repr(cf):
            mism+=1
            if mism<=3: print("MISMATCH",name,centers, "keys nx",list(cx)[:4],"fnx",list(cf)[:4])
print("voronoi comparisons:",total,"mismatches:",mism)
# golden on bench case
G=nx.barabasi_albert_graph(600,4,seed=1); Gf=fnx.Graph(G)
c={0,100,300}
gold=cells_repr(fnx.voronoi_cells(Gf,c)); goldx=cells_repr(nx.voronoi_cells(G,c))
print("bench match:", gold==goldx, "sha", hashlib.sha256(gold.encode()).hexdigest()[:16])
def wm(fn,N=50,reps=7):
    for _ in range(3):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
tx=wm(lambda:nx.voronoi_cells(G,c)); tf=wm(lambda:fnx.voronoi_cells(Gf,c))
print(f"BA600 centers3: nx={tx*1e3:.3f}ms fnx={tf*1e3:.3f}ms  nx/fnx={tx/tf:.2f}x")
