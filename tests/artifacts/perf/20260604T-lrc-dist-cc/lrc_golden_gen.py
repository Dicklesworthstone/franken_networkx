import networkx as nx, franken_networkx as fnx, random, hashlib, struct, math
def cp(G,d=False):
    F=fnx.DiGraph() if d else fnx.Graph()
    F.add_nodes_from(G.nodes()); F.add_edges_from(G.edges()); return F
def golden():
    blob=bytearray()
    for seed in range(120):
        rnd=random.Random(seed); n=rnd.randint(2,50); p=rnd.uniform(0.02,0.4); directed=seed%2==0
        G=nx.gnp_random_graph(n,p,seed=seed,directed=directed); F=cp(G,directed)
        for v in list(G.nodes())[:6]:
            try:
                r=fnx.local_reaching_centrality(F,v)
                bits=struct.pack(">q",0x7ff8000000000001) if (isinstance(r,float) and math.isnan(r)) else struct.pack(">d",float(r))
                blob+=str(v).encode()+b"="+bits+b";"
            except Exception as e:
                blob+=b"ERR:"+type(e).__name__.encode()+b";"
        blob+=b"|"
    return hashlib.sha256(bytes(blob)).hexdigest()
print(golden())
