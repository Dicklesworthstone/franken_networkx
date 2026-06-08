import time,statistics,random
import networkx as nx, franken_networkx as fnx
def build(mod,n,deg,seed=7):
    rng=random.Random(seed); G=mod.Graph(); G.add_nodes_from(range(n))
    hub=list(range(1,deg+1))
    for x in hub: G.add_edge(0,x)
    # moderate local density
    for _ in range(deg*8):
        a=rng.choice(hub); b=rng.choice(hub)
        if a!=b: G.add_edge(a,b)
    # background
    for _ in range(n):
        a=rng.randrange(n); b=rng.randrange(n)
        if a!=b: G.add_edge(a,b)
    return G
def bench(fn,reps=7):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
# native via _fnx directly vs nx, across degrees
for deg in [8,16,24,32,48,64,128]:
    Gn=build(nx,2000,deg); Gf=build(fnx,2000,deg)
    tn=bench(lambda:nx.dispersion(Gn,0))
    tnat=bench(lambda: fnx._fnx.dispersion_node_rust(fnx._coerce_arg_to_fnx_graph(Gf),0,1.0,0.0,0.0))
    print(f"deg={deg:4d}: nx={tn*1e3:8.3f}ms native={tnat*1e3:8.3f}ms  nat_speedup={tn/tnat:6.2f}x")
