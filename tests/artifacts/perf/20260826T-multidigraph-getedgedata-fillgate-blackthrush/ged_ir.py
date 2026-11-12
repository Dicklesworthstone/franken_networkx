import os, random, sys
import franken_networkx as fnx
CLS = os.environ["FNX_CLS"]; AS_INT = os.environ["FNX_KEY"] == "int"; N = int(os.environ.get("FNX_N","20000"))
key = (lambda i: i) if AS_INT else (lambda i: str(i))
rng = random.Random(7); seen=set(); stream=[]
while len(stream) < 4000:
    u,v = rng.randrange(1000), rng.randrange(1000)
    if u==v or (min(u,v),max(u,v)) in seen: continue
    seen.add((min(u,v),max(u,v))); stream.append((key(u),key(v)))
G = getattr(fnx,CLS)(); G.add_nodes_from([key(i) for i in range(1000)])
G.add_edges_from([(u,v,{"weight":1}) for u,v in stream])
pairs = stream[:256]
for u,v in pairs: G.get_edge_data(u,v)          # warm
for i in range(N):
    u,v = pairs[i & 255]; G.get_edge_data(u,v)
print(f"{CLS} {os.environ['FNX_KEY']} N={N}", file=sys.stderr)
