"""Ir/call for one (library, op) pair. Differenced against N=0 by the driver."""
import sys, random
mode, op, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
rng = random.Random(13); seen=set(); st=[]
while len(st) < 3200:
    u,v = rng.randrange(800), rng.randrange(800)
    if u==v or (u,v) in seen: continue
    seen.add((u,v)); st.append((u,v))
mod = __import__("networkx" if mode=="nx" else "franken_networkx")
cls_name, opname = op.split(":")
g = getattr(mod, cls_name)(); g.add_nodes_from(range(800)); g.add_edges_from(st)
U = [u for u,_ in st[:300]]
rows = [g[u] for u in U]
OPS = {
 "iter_row":   lambda: [iter(r) for r in rows],
 "len_row":    lambda: [len(r) for r in rows],
 "keys_row":   lambda: [r.keys() for r in rows],
 "list_keys":  lambda: [list(r.keys()) for r in rows],
 "getitem":    lambda: [g[u] for u in U],
 "neighbors":  lambda: [g.neighbors(u) for u in U],
 "has_edge":   lambda: [g.has_edge(u,v) for u,v in st[:300]],
 "degree_n":   lambda: [g.degree(u) for u in U],
}
work = OPS[opname]
for _ in range(3): work()
for _ in range(N): work()
