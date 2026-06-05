import networkx as nx, franken_networkx as fnx
def build(mod,edges):
    G=mod.Graph(); G.add_edges_from(edges); return G
E=[(0,1),(1,2),(2,3),(0,3),(3,4),(4,0)]
mism=0; cases=0
def norm(s): return sorted(tuple(sorted(e)) for e in s)
for sub in ([0,1,2],[0,1,2,3],[2,3,4],[0,4]):
    Gf=build(fnx,E); Gn=build(nx,E)
    sgf=Gf.subgraph(sub); sgn=Gn.subgraph(sub)
    ops={
      'G-sg': (lambda: Gf.edges - sgf.edges, lambda: Gn.edges - sgn.edges),
      'sg-G': (lambda: sgf.edges - Gf.edges, lambda: sgn.edges - Gn.edges),
      'G&sg': (lambda: Gf.edges & sgf.edges, lambda: Gn.edges & sgn.edges),
      'G|sg': (lambda: Gf.edges | sgf.edges, lambda: Gn.edges | sgn.edges),
      'G^sg': (lambda: Gf.edges ^ sgf.edges, lambda: Gn.edges ^ sgn.edges),
      'sg&G': (lambda: sgf.edges & Gf.edges, lambda: sgn.edges & Gn.edges),
    }
    for name,(ff,nf) in ops.items():
        try: rf=norm(ff())
        except Exception as e: print(f"{name} sub{sub} fnx EXC {type(e).__name__}: {e}"); mism+=1; continue
        try: rn=norm(nf())
        except Exception as e: print(f"{name} sub{sub} nx EXC {type(e).__name__}"); continue
        if rf!=rn: mism+=1; print(f"{name} sub{sub}: nx={rn} fx={rf}")
        cases+=1
    # also G.edges - plain set
    s={(0,1),(2,3)}
    if norm(Gf.edges - s)!=norm(Gn.edges - s): mism+=1; print('G-set diff')
    cases+=1
print(f"setop cases={cases} mismatches={mism}")
