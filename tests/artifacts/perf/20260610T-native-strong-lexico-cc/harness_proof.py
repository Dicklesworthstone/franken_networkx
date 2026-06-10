import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def cedges(G):
    if G.is_multigraph():
        return sorted((tuple(sorted((repr(u),repr(v)))), tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True))
    return sorted((tuple(sorted((repr(u),repr(v)))), tuple(sorted(d.items()))) for u,v,d in G.edges(data=True))
def cnodes(G):
    return sorted((repr(n), tuple(sorted(d.items()))) for n,d in G.nodes(data=True))
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
def pairs():
    out=[]
    for (a,an),(b,bn) in [((fnx.path_graph(5),nx.path_graph(5)),(fnx.cycle_graph(4),nx.cycle_graph(4))),
                          ((fnx.complete_graph(4),nx.complete_graph(4)),(fnx.path_graph(3),nx.path_graph(3))),
                          ((fnx.gnp_random_graph(6,0.4,seed=1),nx.gnp_random_graph(6,0.4,seed=1)),(fnx.gnp_random_graph(5,0.5,seed=2),nx.gnp_random_graph(5,0.5,seed=2)))]:
        out.append((a,an,b,bn))
    # directed
    df=fnx.gnp_random_graph(5,0.4,seed=1,directed=True); dn=nx.gnp_random_graph(5,0.4,seed=1,directed=True)
    df2=fnx.gnp_random_graph(4,0.5,seed=2,directed=True); dn2=nx.gnp_random_graph(4,0.5,seed=2,directed=True)
    out.append((df,dn,df2,dn2))
    # string-labeled
    sf=fnx.Graph([("a","b"),("b","c")]); sn=nx.Graph([("a","b"),("b","c")])
    out.append((sf,sn,fnx.path_graph(3),nx.path_graph(3)))
    # empty/single
    out.append((fnx.Graph(),nx.Graph(),fnx.path_graph(3),nx.path_graph(3)))
    out.append((fnx.path_graph(1),nx.path_graph(1),fnx.cycle_graph(4),nx.cycle_graph(4)))
    return out
for gf,gn,hf,hn in pairs():
    for prod in ("strong_product","lexicographic_product","cartesian_product","tensor_product"):
        try:
            pf=getattr(fnx,prod)(gf,hf); pn=getattr(nx,prod)(gn,hn)
        except Exception as e:
            print(f"ERR {prod}: {e}"); continue
        total+=1
        ok = cnodes(pf)==cnodes(pn) and cedges(pf)==cedges(pn)
        if not ok:
            mism+=1
            if mism<=3: print(f"MISMATCH {prod}: nodes={cnodes(pf)==cnodes(pn)} edges={cedges(pf)==cedges(pn)} ne={pf.number_of_edges()}/{pn.number_of_edges()}")
        nh.update((prod+json.dumps(cnodes(pn))+json.dumps(cedges(pn))).encode())
        fh.update((prod+json.dumps(cnodes(pf))+json.dumps(cedges(pf))).encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
