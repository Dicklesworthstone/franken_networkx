import franken_networkx as fnx, networkx as nx, hashlib, time
def norm(L):
    # order-insensitive canonical form: sorted nodes + sorted endpoint-normalized edges
    nodes = sorted(map(repr, L.nodes()))
    edges = sorted(tuple(sorted(map(repr, e))) for e in L.edges())
    return (nodes, edges)
cases=[
 ("path5", nx.path_graph(5)),
 ("ba300", nx.barabasi_albert_graph(300,4,seed=1)),
 ("ba500_3", nx.barabasi_albert_graph(500,3,seed=7)),
 ("gnp", nx.gnp_random_graph(150,0.1,seed=3)),
 ("star", nx.star_graph(40)),
 ("complete", nx.complete_graph(30)),
 ("cycle", nx.cycle_graph(20)),
 ("single_edge", nx.Graph([(0,1)])),
 ("isolated_edge_plus", nx.Graph([(0,1),(2,3),(3,4),(4,5)])),
 ("str_nodes", nx.Graph([("a","b"),("b","c"),("c","a"),("c","d")])),
 ("ws", nx.watts_strogatz_graph(120,4,0.3,seed=5)),
 ("empty", nx.Graph()),
]
mism=0
for name,G in cases:
    Gf=fnx.Graph(G)
    Lx=nx.line_graph(G); Lf=fnx.line_graph(Gf)
    if type(Lf).__name__ != "Graph": print("TYPE", name, type(Lf)); mism+=1; continue
    if norm(Lx)!=norm(Lf):
        mism+=1
        nx_n,nx_e=norm(Lx); f_n,f_e=norm(Lf)
        print("MISMATCH",name,"nodes_eq",nx_n==f_n,"edges_eq",nx_e==f_e, "nNX",len(nx_n),"nF",len(f_n),"eNX",len(nx_e),"eF",len(f_e))
print("cases:",len(cases),"mismatches:",mism)
# directed still works
DG=nx.gnp_random_graph(80,0.05,seed=2,directed=True); DGf=fnx.DiGraph(DG)
print("directed ok:", norm(nx.line_graph(DG))==norm(fnx.line_graph(DGf)) if False else (sorted(map(repr,nx.line_graph(DG).edges()))==sorted(map(repr,fnx.line_graph(DGf).edges()))))
# inverse_line_graph round trip (test_graph_utilities pattern)
line=fnx.line_graph(fnx.path_graph(5))
inv=fnx.inverse_line_graph(line)
print("inverse_line_graph ok:", inv.number_of_nodes()>0)
# golden on BA800
G=nx.barabasi_albert_graph(800,4,seed=1); Gf=fnx.Graph(G)
nrm=norm(fnx.line_graph(Gf)); nrx=norm(nx.line_graph(G))
print("BA800 match:", nrm==nrx, "sha", hashlib.sha256(repr(nrm).encode()).hexdigest()[:16])
