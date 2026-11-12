import hashlib
import networkx as nx, franken_networkx as fnx
def build(spec):
    bn=nx.Graph(); bf=fnx.Graph()
    bn.add_edges_from(spec); bf.add_edges_from(spec)
    return bn,bf
specs = {
 'cycle5': [(0,1),(1,2),(2,3),(3,4),(4,0)],
 'path4': [(0,1),(1,2),(2,3)],
 'complete4': [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)],
 'star': [(0,1),(0,2),(0,3),(0,4)],
 'string': [('a','b'),('b','c'),('c','a'),('a','d')],
 'mixed': [(1,5),(5,9),(9,1),(2,5)],
 'single': [(0,1)],
 'triangle_str': [('x','y'),('y','z'),('z','x')],
}
sha=hashlib.sha256(); mism=0; cases=0
for name,spec in specs.items():
    for it in (0,1,2,3):
        bn,bf=build(spec)
        try: Gn=nx.mycielskian(bn,iterations=it)
        except Exception as en:
            try: fnx.mycielskian(bf,iterations=it); rf="ok"
            except Exception as ef: rf=type(ef).__name__
            print(f"{name} it={it}: nx ERR vs fx[{rf}]"); continue
        Gf=fnx.mycielskian(bf,iterations=it)
        sn=(list(Gn.nodes()), list(Gn.edges()), [(x,sorted(Gn.nodes[x].items())) for x in Gn.nodes()])
        sf=(list(Gf.nodes()), list(Gf.edges()), [(x,sorted(Gf.nodes[x].items())) for x in Gf.nodes()])
        if sn!=sf:
            mism+=1
            if mism<=4:
                print(f"{name} it={it}: nodes_eq={sn[0]==sf[0]} edges_eq={sn[1]==sf[1]}")
                if sn[0]!=sf[0]: print(f"  nx_n={sn[0][:10]}\n  fx_n={sf[0][:10]}")
                if sn[1]!=sf[1]: print(f"  nx_e={sn[1][:10]}\n  fx_e={sf[1][:10]}")
        sha.update(repr(sn).encode()); cases+=1
# also test mycielski_graph(n)
for n in range(1,7):
    try: Gn=nx.mycielski_graph(n); Gf=fnx.mycielski_graph(n)
    except Exception as en:
        try: fnx.mycielski_graph(n); rf="ok"
        except Exception as ef: rf=type(ef).__name__
        if rf!=type(en).__name__: print(f"mycielski_graph({n}) err mismatch nx[{type(en).__name__}] fx[{rf}]"); 
        continue
    sn=(list(Gn.nodes()),list(Gn.edges())); sf=(list(Gf.nodes()),list(Gf.edges()))
    if sn!=sf: mism+=1; print(f"mycielski_graph({n}) MISMATCH")
    sha.update(repr(('mg',n,sn)).encode()); cases+=1
print(f"cases={cases} mismatches={mism}")
print(f"golden_sha256={sha.hexdigest()}")
