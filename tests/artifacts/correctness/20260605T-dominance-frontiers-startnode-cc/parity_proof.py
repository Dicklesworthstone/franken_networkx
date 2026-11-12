import hashlib, random
import networkx as nx, franken_networkx as fnx
def fg(edges): G=fnx.DiGraph(); G.add_edges_from(edges); return G
def ng(edges): G=nx.DiGraph(); G.add_edges_from(edges); return G
sha=hashlib.sha256(); mism=0; cases=0
# explicit cases
explicit=[
 [(0,1),(0,2),(1,3),(2,3),(3,0)],
 [(1,2),(1,3),(2,5),(3,4),(4,5)],
 [(0,1),(1,2),(2,1),(1,3)],
 [(0,1),(1,0)],
 [(0,1),(1,2),(2,3),(3,1),(3,0)],
]
def run(edges, start):
    global mism, cases
    Gn=ng(edges); Gf=fg(edges)
    try: rn=nx.dominance_frontiers(Gn,start)
    except Exception as en:
        try: fnx.dominance_frontiers(Gf,start); rf="ok"
        except Exception as ef: rf=type(ef).__name__
        if rf!=type(en).__name__: print(f"err mismatch start{start}: nx{type(en).__name__} fx{rf}"); mism+=1
        return
    rf=fnx.dominance_frontiers(Gf,start)
    # compare values AND key order
    if rn!=rf or list(rn.keys())!=list(rf.keys()):
        mism+=1
        if mism<=4: print(f"MISMATCH edges{edges} start{start}\n nx={rn} keys={list(rn.keys())}\n fx={rf} keys={list(rf.keys())}")
    sha.update(repr((edges,start,list(rn.items()))).encode()); cases+=1
for e in explicit: run(e, e[0][0])
# random
for seed in range(400):
    rng=random.Random(seed); n=rng.randint(2,10); edges=set()
    for _ in range(rng.randint(n,n*3)):
        a=rng.randrange(n); b=rng.randrange(n)
        if a!=b or rng.random()<0.25: edges.add((a,b))
    edges=list(edges)
    if not edges: continue
    run(edges, edges[0][0])
# error: start not in G
try: fnx.dominance_frontiers(fg([(0,1)]),99); ef="ok"
except Exception as e: ef=type(e).__name__
try: nx.dominance_frontiers(ng([(0,1)]),99); en="ok"
except Exception as e: en=type(e).__name__
print("start-missing err: nx",en,"fx",ef,"match",en==ef)
print(f"cases={cases} mismatches={mism}")
print(f"golden_sha256={sha.hexdigest()}")
