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
def pairs():
    out=[]
    out.append((fnx.path_graph(5),nx.path_graph(5),fnx.cycle_graph(4),nx.cycle_graph(4)))
    out.append((fnx.complete_graph(4),nx.complete_graph(4),fnx.path_graph(4),nx.path_graph(4)))
    for s in range(4):
        out.append((fnx.gnp_random_graph(7,0.4,seed=s),nx.gnp_random_graph(7,0.4,seed=s),fnx.gnp_random_graph(6,0.5,seed=s+10),nx.gnp_random_graph(6,0.5,seed=s+10)))
    out.append((fnx.empty_graph(5),nx.empty_graph(5),fnx.path_graph(3),nx.path_graph(3)))  # no G-edges
    out.append((fnx.complete_graph(5),nx.complete_graph(5),fnx.empty_graph(4),nx.empty_graph(4)))  # no H-edges
    out.append((fnx.Graph([("a","b"),("b","c")]),nx.Graph([("a","b"),("b","c")]),fnx.path_graph(3),nx.path_graph(3)))  # string
    out.append((fnx.Graph(),nx.Graph(),fnx.path_graph(3),nx.path_graph(3)))  # empty
    out.append((fnx.path_graph(1),nx.path_graph(1),fnx.cycle_graph(4),nx.cycle_graph(4)))  # single
    return out
for gf,gn,hf,hn in pairs():
    pf=fnx.modular_product(gf,hf); pn=nx.modular_product(gn,hn)
    total+=1
    ok = cnodes(pf)==cnodes(pn) and cedges(pf)==cedges(pn)
    if not ok:
        mism+=1
        if mism<=3: print(f"MISMATCH: nodes={cnodes(pf)==cnodes(pn)} edges={cedges(pf)==cedges(pn)} ne={pf.number_of_edges()}/{pn.number_of_edges()}")
    nh.update((json.dumps(cnodes(pn))+json.dumps(cedges(pn))).encode())
    fh.update((json.dumps(cnodes(pf))+json.dumps(cedges(pf))).encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
