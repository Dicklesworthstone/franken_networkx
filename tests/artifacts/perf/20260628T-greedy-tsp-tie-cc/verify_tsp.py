import time, random
import networkx as nx, franken_networkx as fnx

def build(mod,n,seed,directed=False,floatw=False,wrange=30):
    r=random.Random(seed)
    G=mod.complete_graph(n, create_using=mod.DiGraph if directed else mod.Graph)
    for u,v in G.edges(): G[u][v]['weight']=(r.random()*100 if floatw else r.randint(1,wrange))
    return G

# ---- byte-exact sweep through the real wrapper ----
mism=0; total=0
for seed in range(80):
  for d in (False,True):
    for n in (1,2,3,4,5,12,40):
      for fw in (False,True):
        for wr in (3,30):  # wr=3 => heavy ties
          if fw and wr==3: continue
          total+=1
          Gnx=build(nx,n,seed,d,fw,wr); Gfx=build(fnx,n,seed,d,fw,wr)
          src=None if seed%4 else min(n-1, n//2)
          try: e=nx.approximation.greedy_tsp(Gnx,source=src)
          except Exception as ex: e=('ERR',type(ex).__name__,str(ex))
          try: g=fnx.approximation.greedy_tsp(Gfx,source=src)
          except Exception as ex: g=('ERR',type(ex).__name__,str(ex))
          if e!=g:
            mism+=1
            if mism<=8: print('MISMATCH',seed,'dir' if d else 'und',n,'flt' if fw else 'int',wr,src,'\n  nx=',e,'\n  fx=',g)
print(f'wrapper byte-exact: {mism}/{total} mismatches')

# error contracts
def cmp(name, bnx, bfx, **kw):
    try: e=nx.approximation.greedy_tsp(bnx(),**kw); en=None
    except Exception as ex: e,en=None,(type(ex).__name__,str(ex))
    try: g=fnx.approximation.greedy_tsp(bfx(),**kw); gn=None
    except Exception as ex: g,gn=None,(type(ex).__name__,str(ex))
    ok=(e==g)and(en==gn)
    print(('OK ' if ok else 'BAD ')+name+f': nx={e if en is None else en} fx={g if gn is None else gn}')
def inc(mod):
    G=mod.Graph(); G.add_edges_from([(0,1),(1,2),(2,3)]); return G
cmp('incomplete', lambda: inc(nx), lambda: inc(fnx))
cmp('empty', lambda: nx.Graph(), lambda: fnx.Graph())
def c6(mod):
    G=mod.complete_graph(6)
    for u,v in G.edges(): G[u][v]['weight']=1
    return G
cmp('bad-source', lambda: c6(nx), lambda: c6(fnx), source=99)
cmp('weight=None', lambda: c6(nx), lambda: c6(fnx), weight=None)
# directed incomplete (missing some arcs)
def dinc(mod):
    G=mod.DiGraph(); G.add_edges_from([(0,1),(1,2),(2,0),(0,2)]);
    for u,v in G.edges(): G[u][v]['weight']=1
    return G
cmp('dir-incomplete', lambda: dinc(nx), lambda: dinc(fnx))

# ---- timing ----
def bench(fn,reps=11):
    for _ in range(3): fn()
    ts=[]
    for _ in range(reps):
        t0=time.perf_counter(); fn(); ts.append(time.perf_counter()-t0)
    return min(ts)
print('--- INT weights (tie path) ---')
for n in (40,60,100,150,250,400):
    Gnx=build(nx,n,1); Gfx=build(fnx,n,1)
    tnx=bench(lambda: nx.approximation.greedy_tsp(Gnx)); tfx=bench(lambda: fnx.approximation.greedy_tsp(Gfx))
    print(f'  n={n:4d}: nx={tnx*1e6:9.1f}us fnx={tfx*1e6:9.1f}us  ratio={tnx/tfx:6.3f}x')
print('--- FLOAT weights (native fast path) ---')
for n in (60,150,250,400):
    Gnx=build(nx,n,1,floatw=True); Gfx=build(fnx,n,1,floatw=True)
    tnx=bench(lambda: nx.approximation.greedy_tsp(Gnx)); tfx=bench(lambda: fnx.approximation.greedy_tsp(Gfx))
    print(f'  n={n:4d}: nx={tnx*1e6:9.1f}us fnx={tfx*1e6:9.1f}us  ratio={tnx/tfx:6.3f}x')
