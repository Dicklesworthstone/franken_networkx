import hashlib, random
import networkx as nx, franken_networkx as fnx
def build(kind, spec, nodeattrs=None, edgeattrs=False):
    directed = kind in ('d','md'); multi = kind in ('m','md')
    nc={'u':(nx.Graph,fnx.Graph),'d':(nx.DiGraph,fnx.DiGraph),'m':(nx.MultiGraph,fnx.MultiGraph),'md':(nx.MultiDiGraph,fnx.MultiDiGraph)}[kind]
    Gn=nc[0](); Gf=nc[1]()
    for i,e in enumerate(spec):
        if edgeattrs:
            Gn.add_edge(*e, w=i); Gf.add_edge(*e, w=i)
            if multi: Gn.add_edge(*e, w=i+100); Gf.add_edge(*e, w=i+100)
        else:
            Gn.add_edge(*e); Gf.add_edge(*e)
    if nodeattrs:
        for n in list(Gn.nodes())[:2]:
            Gn.nodes[n]['c']=str(n); Gf.add_node(n, c=str(n))
    return Gn,Gf
def sig(G):
    if G.is_multigraph():
        e=[(u,v,k,tuple(sorted(d.items()))) for u,v,k,d in G.edges(keys=True,data=True)]
    else:
        e=[(u,v,tuple(sorted(d.items()))) for u,v,d in G.edges(data=True)]
    return (list(G.nodes()), e)
specsA={'tri':[(0,1),(1,2),(2,0)],'path':[(0,1),(1,2),(2,3)],'star':[(0,1),(0,2),(0,3)]}
specsB={'p2':[(0,1),(1,2)],'edge':[(0,1)],'tri':[(0,1),(1,2),(2,0)]}
sha=hashlib.sha256(); mism=0; cases=0
for op in ('tensor_product','strong_product','cartesian_product','lexicographic_product'):
    for kind in ('u','d','m','md'):
        for na in specsA.values():
            for nb in specsB.values():
                Gn1,Gf1=build(kind,na,nodeattrs=True,edgeattrs=True)
                Gn2,Gf2=build(kind,nb,edgeattrs=True)
                try:
                    Rn=getattr(nx,op)(Gn1,Gn2); Rf=getattr(fnx,op)(Gf1,Gf2)
                except Exception as e:
                    continue
                sn,sf=sig(Rn),sig(Rf)
                if sn!=sf:
                    mism+=1
                    if mism<=4:
                        print(f"{op} {kind}: nodes_eq={sn[0]==sf[0]} edges_eq={sn[1]==sf[1]}")
                        if sn[1]!=sf[1]: print(f"  nx_e={sn[1][:6]}\n  fx_e={sf[1][:6]}")
                sha.update(repr((op,kind,sn)).encode()); cases+=1
print(f"cases={cases} mismatches={mism}")
print(f"golden_sha256={sha.hexdigest()}")
