import networkx as nx, franken_networkx as fnx, random, hashlib, struct, math
def cp(G):
    F=fnx.Graph(); F.add_nodes_from(G.nodes()); F.add_edges_from(G.edges()); return F
def golden():
    blob=bytearray()
    for seed in range(80):
        rnd=random.Random(seed); n=rnd.randint(0,60); p=rnd.uniform(0,0.3)
        G=nx.gnp_random_graph(n,p,seed=seed); F=cp(G)
        try:
            r=fnx.constraint(F); blob+=b"OK:"
            for k in sorted(r,key=lambda x:str(x)):
                v=r[k]
                bits=struct.pack(">q",0x7ff8000000000001) if (isinstance(v,float) and math.isnan(v)) else struct.pack(">d",float(v))
                blob+=str(k).encode()+b"="+bits+b";"
        except Exception as e:
            blob+=b"ERR:"+type(e).__name__.encode()
        blob+=b"|"
    return hashlib.sha256(bytes(blob)).hexdigest()
print(golden())
