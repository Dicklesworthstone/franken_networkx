import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass

def fp(G):
    parts=["N:"+"|".join(f"{n!r}:{sorted(d.items())!r}" for n,d in G.nodes(data=True))]
    if G.is_multigraph():
        parts.append("E:"+"|".join(f"{u!r}->{v!r}#{k!r}:{sorted(d.items())!r}" for u,v,k,d in G.edges(keys=True,data=True)))
    else:
        parts.append("E:"+"|".join(f"{u!r}->{v!r}:{sorted(d.items())!r}" for u,v,d in G.edges(data=True)))
    parts.append("G:"+repr(sorted(G.graph.items())))
    return "\n".join(parts)

def gens():
    out=[]
    for seed in range(5):
        out.append((f"fast_gnp_di{seed}", lambda s=seed: nx.fast_gnp_random_graph(60,0.1,seed=s,directed=True), lambda s=seed: fnx.fast_gnp_random_graph(60,0.1,seed=s,directed=True)))
        out.append((f"gnp_di{seed}", lambda s=seed: nx.gnp_random_graph(60,0.1,seed=s,directed=True), lambda s=seed: fnx.gnp_random_graph(60,0.1,seed=s,directed=True)))
    for seed in range(3):
        out.append((f"gn{seed}", lambda s=seed: nx.gn_graph(40,seed=s), lambda s=seed: fnx.gn_graph(40,seed=s)))
        out.append((f"gnr{seed}", lambda s=seed: nx.gnr_graph(40,0.3,seed=s), lambda s=seed: fnx.gnr_graph(40,0.3,seed=s)))
        out.append((f"gnc{seed}", lambda s=seed: nx.gnc_graph(40,seed=s), lambda s=seed: fnx.gnc_graph(40,seed=s)))
        out.append((f"scalefree{seed}", lambda s=seed: nx.scale_free_graph(60,seed=s), lambda s=seed: fnx.scale_free_graph(60,seed=s)))
    return out

fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
for name,nf,ff in gens():
    gn=nf(); gf=ff()
    total+=1
    a=fp(gn); b=fp(gf)
    if a!=b:
        mism+=1
        if mism<=4:
            for x,y in zip(a.split("\n"),b.split("\n")):
                if x!=y: print(f"MISMATCH {name}:\n nx ={x[:100]}\n fnx={y[:100]}"); break
    # attr identity + mutation on first edge
    if gf.number_of_edges()>0:
        e=list(gf.edges(keys=True)) if gf.is_multigraph() else list(gf.edges())
        if gf.is_multigraph():
            u,v,k=e[0]; assert gf[u][v][k] is gf[u][v][k]; gf[u][v][k]["w"]=1
        else:
            u,v=e[0]; assert gf[u][v] is gf[u][v]; gf[u][v]["w"]=1
    nh.update(a.encode()); fh.update(b.encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
