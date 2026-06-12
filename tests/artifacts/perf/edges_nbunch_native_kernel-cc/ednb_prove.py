import franken_networkx as fnx, networkx as nx, random, sys, time
tag=sys.argv[1] if len(sys.argv)>1 else "AFTER"
mism=0; total=0
for seed in range(10):
    r=random.Random(seed); edges=[]
    attr = seed%2==0
    while len(edges)<120:
        a,b=r.randrange(60),r.randrange(60)
        if a!=b: edges.append((a,b,{'w':r.randint(1,9)}) if attr else (a,b,{}))
    # include a self-loop sometimes
    if seed%3==0: edges.append((5,5,{}))
    G=nx.Graph(); G.add_nodes_from(range(60)); G.add_edges_from(edges)
    Gf=fnx.Graph(); Gf.add_nodes_from(range(60)); Gf.add_edges_from(edges)
    for nb in [range(30), [0,1,2], list(r.sample(range(60),25)), range(60), [5]]:
        nbl=list(nb)
        for data in [True, False, 'w', 'missing', None]:
            ex=list(G.edges(nbl,data=data)); fx=list(Gf.edges(nbl,data=data))
            total+=1
            if ex!=fx:
                mism+=1
                if mism<=4: print(f"MISMATCH seed{seed} nb={nbl[:3]} data={data}: nx[:2]={ex[:2]} fx[:2]={fx[:2]} lens {len(ex)},{len(fx)}")
print(f"[{tag}] total {total} mismatches {mism}")
# live-dict check
if tag=="AFTER":
    G2=fnx.Graph([(0,1),(1,2)]); G2[0][1]['w']=5
    e=[t for t in G2.edges([0],data=True) if t[0]==0 and t[1]==1][0]
    e[2]['w']=99
    print("data=True LIVE dict (nx parity):", G2[0][1]['w']==99)
def wm(fn,N=20,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
# attr-less
G=nx.barabasi_albert_graph(300,4,seed=1); Gf=fnx.Graph(G); nb=list(range(150))
tf=wm(lambda:list(Gf.edges(nb,data=True))); tx=wm(lambda:list(G.edges(nb,data=True)))
print(f"[{tag}] attrless edges(nb,data=True): fnx={tf*1e3:.3f}ms nx={tx*1e3:.3f}ms nx/fnx={tx/tf:.2f}x")
# attr-present
Gw=nx.barabasi_albert_graph(300,4,seed=1)
for u,v in Gw.edges(): Gw[u][v]['weight']=(u+v)%9+1
Gwf=fnx.Graph(); Gwf.add_nodes_from(Gw.nodes()); Gwf.add_edges_from((u,v,d) for u,v,d in Gw.edges(data=True))
tf=wm(lambda:list(Gwf.edges(nb,data='weight'))); tx=wm(lambda:list(Gw.edges(nb,data='weight')))
print(f"[{tag}] attr edges(nb,data='weight'): fnx={tf*1e3:.3f}ms nx={tx*1e3:.3f}ms nx/fnx={tx/tf:.2f}x")
