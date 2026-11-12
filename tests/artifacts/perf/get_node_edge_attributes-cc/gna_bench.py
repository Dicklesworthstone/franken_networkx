import franken_networkx as fnx, networkx as nx, time, sys
tag=sys.argv[1]
def wm(fn,N,reps=7):
    for _ in range(2):fn()
    b=1e18
    for _ in range(reps):
        t=time.perf_counter()
        for _ in range(N):fn()
        b=min(b,(time.perf_counter()-t)/N)
    return b
G=nx.barabasi_albert_graph(800,4,seed=1); Gf=fnx.Graph(G)
Gw=nx.barabasi_albert_graph(800,4,seed=1); 
for n in Gw.nodes(): Gw.nodes[n]['w']=n
Gwf=fnx.Graph(); Gwf.add_nodes_from(Gw.nodes(data=True)); Gwf.add_edges_from(Gw.edges())
# attr-absent probe (common)
tf=wm(lambda:fnx.get_node_attributes(Gf,'x'),200); tx=wm(lambda:nx.get_node_attributes(G,'x'),200)
print(f"[{tag}] get_node_attrs ABSENT: fnx={tf*1e3:.4f}ms nx={tx*1e3:.4f}ms nx/fnx={tx/tf:.2f}x")
# attr-present
tf2=wm(lambda:fnx.get_node_attributes(Gwf,'w'),200); tx2=wm(lambda:nx.get_node_attributes(Gw,'w'),200)
print(f"[{tag}] get_node_attrs PRESENT: fnx={tf2*1e3:.4f}ms nx={tx2*1e3:.4f}ms nx/fnx={tx2/tf2:.2f}x")
# edge attr absent
tf3=wm(lambda:fnx.get_edge_attributes(Gf,'weight'),200); tx3=wm(lambda:nx.get_edge_attributes(G,'weight'),200)
print(f"[{tag}] get_edge_attrs ABSENT: fnx={tf3*1e3:.4f}ms nx={tx3*1e3:.4f}ms nx/fnx={tx3/tf3:.2f}x")
