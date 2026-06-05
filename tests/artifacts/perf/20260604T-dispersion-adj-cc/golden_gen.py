import networkx as nx, franken_networkx as fnx, random, hashlib, struct, math
def cp(G):
    F=fnx.Graph(); F.add_nodes_from(G.nodes()); F.add_edges_from(G.edges()); return F
def golden():
    blob=bytearray()
    for seed in range(80):
        rnd=random.Random(seed); n=rnd.randint(2,40); p=rnd.uniform(0.05,0.5)
        G=nx.gnp_random_graph(n,p,seed=seed); F=cp(G)
        r=fnx.dispersion(F)  # full dict form
        for node in sorted(r,key=str):
            for nbr in sorted(r[node],key=str):
                val=r[node][nbr]
                bits=struct.pack(">q",0x7ff8000000000001) if (isinstance(val,float) and math.isnan(val)) else struct.pack(">d",float(val))
                blob+=str(node).encode()+b">"+str(nbr).encode()+b"="+bits+b";"
        blob+=b"|"
    return hashlib.sha256(bytes(blob)).hexdigest()
print(golden())
