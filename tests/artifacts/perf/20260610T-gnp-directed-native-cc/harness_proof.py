import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass

def fp(G):
    parts=["N:"+",".join(repr(n) for n in G.nodes())]
    parts.append("E:"+"|".join(f"{u!r}->{v!r}" for u,v in G.edges()))
    return "\n".join(parts)

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
cfgs=[]
for n in (30,60,100):
    for p in (0.05,0.1,0.3,0.5):
        for seed in range(6):
            cfgs.append((n,p,seed))
# edge cases
cfgs += [(0,0.1,1),(1,0.1,1),(2,0.5,1),(50,0.0001,3),(40,0.999,2)]
for n,p,seed in cfgs:
    gn=nx.gnp_random_graph(n,p,seed=seed,directed=True)
    gf=fnx.gnp_random_graph(n,p,seed=seed,directed=True)
    total+=1
    a=fp(gn); b=fp(gf)
    if a!=b:
        mism+=1
        if mism<=3:
            en=set(gn.edges()); ef=set(gf.edges())
            print(f"MISMATCH n={n} p={p} seed={seed}: nx-only={list(en-ef)[:3]} fnx-only={list(ef-en)[:3]} order_diff={a!=b and en==ef}")
    nh.update(a.encode()); fh.update(b.encode())
# negative seed + create_using fall-through parity
for seed in (-1,-100):
    gn=nx.gnp_random_graph(40,0.1,seed=seed,directed=True)
    gf=fnx.gnp_random_graph(40,0.1,seed=seed,directed=True)
    total+=1
    if sorted(gn.edges())!=sorted(gf.edges()): mism+=1; print(f"NEG SEED MISMATCH {seed}")
    nh.update(fp(gn).encode()); fh.update(fp(gf).encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
