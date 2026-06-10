import warnings, hashlib, json, os; warnings.filterwarnings("ignore")
os.environ["NETWORKX_AUTOMATIC_BACKENDS"]=""
import networkx as nx, franken_networkx as fnx
try: nx.config.backend_priority=[]
except Exception: pass
fh=hashlib.sha256(); nh=hashlib.sha256(); mism=0; total=0
cfgs=[]
for n in (30,80,150):
    for p in (0.05,0.1,0.3):
        for seed in range(4):
            cfgs.append((n,p,seed))
for it in (1,2,5):
    cfgs.append((100,0.1,1,it))
import warnings as _w
for cfg in cfgs:
    n,p,seed = cfg[0],cfg[1],cfg[2]
    it = cfg[3] if len(cfg)>3 else 3
    gn=nx.gnp_random_graph(n,p,seed=seed); gf=fnx.gnp_random_graph(n,p,seed=seed)
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        hn=nx.weisfeiler_lehman_graph_hash(gn, iterations=it)
        hf=fnx.weisfeiler_lehman_graph_hash(gf, iterations=it)
        sn=nx.weisfeiler_lehman_subgraph_hashes(gn, iterations=it)
        sf=fnx.weisfeiler_lehman_subgraph_hashes(gf, iterations=it)
    total+=1
    ok = hn==hf and sn==sf
    if not ok:
        mism+=1
        if mism<=3: print(f"MISMATCH n={n} p={p} seed={seed} it={it}: hash {hn==hf} subhash {sn==sf}")
    nh.update((hn+json.dumps({str(k):v for k,v in sn.items()})).encode())
    fh.update((hf+json.dumps({str(k):v for k,v in sf.items()})).encode())
# string-labeled + self loop
gn=nx.Graph([("a","b"),("b","c"),("c","c"),("a","d")]); gf=fnx.Graph([("a","b"),("b","c"),("c","c"),("a","d")])
with _w.catch_warnings():
    _w.simplefilter("ignore")
    total+=1
    if nx.weisfeiler_lehman_graph_hash(gn)!=fnx.weisfeiler_lehman_graph_hash(gf): mism+=1; print("STR MISMATCH")
    nh.update(nx.weisfeiler_lehman_graph_hash(gn).encode()); fh.update(fnx.weisfeiler_lehman_graph_hash(gf).encode())
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
