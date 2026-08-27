"""Ir per iter(row), isolated by subtracting a ZERO-WORK run of the SAME library.

The naive baseline (a process importing neither library) is wrong: fnx's import
alone is ~1e9 Ir and would swamp the signal. Running each library twice - once
with N work iterations, once with zero - and differencing cancels its own import,
interpreter startup and graph construction exactly.
"""
import sys, random
mode, N = sys.argv[1], int(sys.argv[2])
rng = random.Random(13); seen=set(); st=[]
while len(st) < 3200:
    u,v = rng.randrange(800), rng.randrange(800)
    if u==v or (u,v) in seen: continue
    seen.add((u,v)); st.append((u,v))
mod = __import__("networkx" if mode=="nx" else "franken_networkx")
g = mod.MultiGraph(); g.add_nodes_from(range(800)); g.add_edges_from(st)
rows = [g[u] for u,_ in st[:300]]
for _ in range(3):
    for r in rows: iter(r)
for _ in range(N):
    for r in rows: iter(r)
