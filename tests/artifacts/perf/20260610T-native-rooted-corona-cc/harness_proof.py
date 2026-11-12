import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
def cedges(G):
    return sorted((tuple(sorted((repr(u),repr(v)))), tuple(sorted(d.items()))) for u,v,d in G.edges(data=True))
def cnodes(G):
    return sorted((repr(n), tuple(sorted(d.items()))) for n,d in G.nodes(data=True))
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
def base():
    out=[]
    out.append((fnx.path_graph(5),nx.path_graph(5),fnx.cycle_graph(4),nx.cycle_graph(4)))
    out.append((fnx.complete_graph(4),nx.complete_graph(4),fnx.path_graph(4),nx.path_graph(4)))
    for s in range(4):
        out.append((fnx.gnp_random_graph(6,0.4,seed=s),nx.gnp_random_graph(6,0.4,seed=s),fnx.gnp_random_graph(5,0.5,seed=s+9),nx.gnp_random_graph(5,0.5,seed=s+9)))
    out.append((fnx.Graph([("a","b"),("b","c")]),nx.Graph([("a","b"),("b","c")]),fnx.path_graph(3),nx.path_graph(3)))
    out.append((fnx.empty_graph(4),nx.empty_graph(4),fnx.path_graph(3),nx.path_graph(3)))  # no G edges
    out.append((fnx.path_graph(4),nx.path_graph(4),fnx.empty_graph(3),nx.empty_graph(3)))  # no H edges
    out.append((fnx.Graph(),nx.Graph(),fnx.path_graph(3),nx.path_graph(3)))  # empty G
    return out
for gf,gn,hf,hn in base():
    # corona
    for prod,args in (("corona_product",()),):
        try:
            pf=getattr(fnx,prod)(gf,hf,*args); pn=getattr(nx,prod)(gn,hn,*args)
        except Exception as e:
            print(f"ERR {prod}: {e}"); continue
        total+=1
        ok = cnodes(pf)==cnodes(pn) and cedges(pf)==cedges(pn)
        if not ok:
            mism+=1
            if mism<=3: print(f"MISMATCH {prod}: nodes={cnodes(pf)==cnodes(pn)} edges={cedges(pf)==cedges(pn)} ne={pf.number_of_edges()}/{pn.number_of_edges()} nn={pf.number_of_nodes()}/{pn.number_of_nodes()}")
        nh.update((prod+json.dumps(cnodes(pn))+json.dumps(cedges(pn))).encode()); fh.update((prod+json.dumps(cnodes(pf))+json.dumps(cedges(pf))).encode())
    # rooted (root = each h node, test a couple)
    for root in list(hf.nodes())[:2] or [None]:
        if root is None: continue
        pf=fnx.rooted_product(gf,hf,root); pn=nx.rooted_product(gn,hn,root)
        total+=1
        ok = cnodes(pf)==cnodes(pn) and cedges(pf)==cedges(pn)
        if not ok:
            mism+=1
            if mism<=3: print(f"MISMATCH rooted root={root}: nodes={cnodes(pf)==cnodes(pn)} edges={cedges(pf)==cedges(pn)}")
        nh.update(("rooted"+json.dumps(cnodes(pn))+json.dumps(cedges(pn))).encode()); fh.update(("rooted"+json.dumps(cnodes(pf))+json.dumps(cedges(pf))).encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
