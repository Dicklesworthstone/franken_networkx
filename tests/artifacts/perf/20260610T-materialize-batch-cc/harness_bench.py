import time, warnings, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
from franken_networkx import _materialize_filtered_view
def wm(fn,n=6):
    ts=[]
    for _ in range(n): t0=time.perf_counter(); r=fn(); ts.append(time.perf_counter()-t0)
    return min(ts)*1000, r
for n,p in ((300,0.05),(600,0.03),(1000,0.02)):
    g=fnx.gnp_random_graph(n,p,seed=3)
    sub=list(g)[:int(n*0.7)]
    view=g.subgraph(sub)  # SubgraphView
    # uncached time (fresh view each call)
    def make_and_mat():
        v=g.subgraph(sub); 
        # bust cache by removing the cache attr
        try: v.__dict__.pop("_fnx_materialized_cache",None)
        except Exception: pass
        return _materialize_filtered_view(v)
    t,r=wm(make_and_mat)
    print(f"n={n}: materialize {int(n*0.7)}-node view = {t:.2f}ms (result {r.number_of_nodes()}n/{r.number_of_edges()}e)")
