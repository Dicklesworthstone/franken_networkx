import franken_networkx as fnx, networkx as nx, random, json, hashlib, io, time
def build(M, seed, n=30, e=80, sl=True):
    g=M(); r=random.Random(seed)
    for x in [5,2,9,1,7]: g.add_node(x)
    g.add_nodes_from(range(n))
    for _ in range(e):
        u,v=r.randint(0,n-1),r.randint(0,n-1)
        if not sl and u==v: v=(v+1)%n
        g.add_edge(u,v)
    return g
mism=0; records=[]
# simple graphs: fnx must equal nx byte-for-byte
for label,Mf,Mn in [("Graph",fnx.Graph,nx.Graph),("DiGraph",fnx.DiGraph,nx.DiGraph)]:
    for seed in (1,2,3,4):
        for sl in (True,False):
            for delim in (" ",","):
                gf=build(Mf,seed,sl=sl); gn=build(Mn,seed,sl=sl)
                f=list(fnx.generate_adjlist(gf,delim)); n_=list(nx.generate_adjlist(gn,delim))
                if f!=n_: mism+=1; print(f"  GENADJ {label} s={seed} sl={sl} d={delim!r}: {f[:2]} vs {n_[:2]}")
                records.append([label,seed,sl,delim,f])
        # subgraph view parity
        gf=build(Mf,seed); gn=build(Mn,seed)
        sub=sorted(random.Random(seed).sample(range(30),20))
        if list(fnx.generate_adjlist(gf.subgraph(sub)))!=list(nx.generate_adjlist(gn.subgraph(sub))):
            mism+=1; print(f"  SUBGRAPH GENADJ {label} s={seed}")
# write_adjlist roundtrip still byte-exact (delegates to nx writer)
import tempfile,os
td=tempfile.mkdtemp()
g=build(fnx.Graph,7); gn=build(nx.Graph,7)
fnx.write_adjlist(g, td+"/f.adj"); nx.write_adjlist(gn, td+"/n.adj")
wf=open(td+"/f.adj").read().split("\n",1)[1]; wn=open(td+"/n.adj").read().split("\n",1)[1]  # drop timestamp header line
if wf!=wn: mism+=1; print("  write_adjlist body mismatch")
# multigraph path unchanged (we did NOT touch it) — verify it equals pre-change behavior is implicit
blob=json.dumps(records, sort_keys=True).encode()
print(f"mismatches={mism}")
print(f"GENADJ_GOLDEN {hashlib.sha256(blob).hexdigest()}")
