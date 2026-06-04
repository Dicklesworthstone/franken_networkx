import networkx as nx, franken_networkx as fnx, random, hashlib, struct, math
def cp(G,d=False):
    F=fnx.DiGraph() if d else fnx.Graph(); F.add_nodes_from(G.nodes()); F.add_edges_from(G.edges()); return F
def golden():
    blob=bytearray()
    for seed in range(120):
        rnd=random.Random(seed); n=rnd.randint(2,45); p=rnd.uniform(0.02,0.4); directed=seed%2==0
        G=nx.gnp_random_graph(n,p,seed=seed,directed=directed); F=cp(G,directed)
        try:
            r=fnx.global_reaching_centrality(F)
            bits=struct.pack(">q",0x7ff8000000000001) if (isinstance(r,float) and math.isnan(r)) else struct.pack(">d",float(r))
            blob+=bits
        except Exception as e:
            blob+=b"ERR:"+type(e).__name__.encode()
        blob+=b"|"
    return hashlib.sha256(bytes(blob)).hexdigest()
print(golden())
