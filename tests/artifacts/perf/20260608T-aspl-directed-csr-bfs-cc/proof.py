import time,statistics,random,hashlib,json,math
import networkx as nx, franken_networkx as fnx
def build(mod,n,m,seed,sl=False):
    rng=random.Random(seed); G=mod.DiGraph(); G.add_nodes_from(range(n)); edges=[]
    for i in range(n): edges.append((i,(i+1)%n))  # cycle backbone -> strongly connected
    seen=set(edges)
    while len(seen)<m:
        u=rng.randrange(n); v=rng.randrange(n)
        if u!=v and (u,v) not in seen:
            seen.add((u,v)); edges.append((u,v))
    if sl:
        for _ in range(n//20):
            x=rng.randrange(n)
            if (x,x) not in seen: seen.add((x,x)); edges.append((x,x))
    gn=nx.DiGraph(); gn.add_nodes_from(range(n)); gn.add_edges_from(edges)
    gf=fnx.DiGraph(); gf.add_nodes_from(range(n)); gf.add_edges_from(edges)
    return gn,gf
mism=0;checked=0
for seed in range(50):
    n=random.Random(seed).randrange(3,60); m=random.Random(seed+1).randrange(n,n*3)
    gn,gf=build(nx if False else nx,n,m,seed,sl=(seed%4==0))[0],None
    gn,gf=build(nx,n,m,seed,sl=(seed%4==0))
    try: rn=nx.average_shortest_path_length(gn)
    except Exception as e: rn=("ERR",type(e).__name__)
    try: rf=fnx.average_shortest_path_length(gf)
    except Exception as e: rf=("ERR",type(e).__name__)
    checked+=1
    ok = (rn==rf) or (isinstance(rn,float) and isinstance(rf,float) and abs(rn-rf)<1e-9)
    if not ok: mism+=1; print(f"seed{seed} n{n} m{m}: nx={rn} fnx={rf}")
print(f"PARITY: {checked} graphs, {mism} mismatches")
gf_d={};gn_d={}
for seed in [1,2,7,42,99]:
    gn,gf=build(nx,50,200,seed)
    gf_d[seed]=repr(fnx.average_shortest_path_length(gf)); gn_d[seed]=repr(nx.average_shortest_path_length(gn))
shf=hashlib.sha256(json.dumps(gf_d,sort_keys=True).encode()).hexdigest()
shn=hashlib.sha256(json.dumps(gn_d,sort_keys=True).encode()).hexdigest()
print("GOLDEN MATCH:",shf==shn,shf[:16])
def bench(fn,reps=5):
    ts=[]
    for _ in range(reps):
        t=time.perf_counter(); fn(); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
for (n,m) in [(400,3000),(800,6000)]:
    gn,gf=build(nx,n,m,7)
    tn=bench(lambda:nx.average_shortest_path_length(gn)); tf=bench(lambda:fnx.average_shortest_path_length(gf))
    print(f"directed n={n} m={m}: nx={tn*1e3:8.2f}ms fnx={tf*1e3:7.2f}ms speedup={tn/tf:6.2f}x")
