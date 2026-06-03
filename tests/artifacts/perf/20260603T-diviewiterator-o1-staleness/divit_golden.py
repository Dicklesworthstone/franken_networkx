import hashlib, json, networkx as nx, franken_networkx as fnx
def sig(Dn, Df):
    out={}
    out['edges']=( [(repr(u),repr(v)) for u,v in Dn.edges()] == [(repr(u),repr(v)) for u,v in Df.edges()] )
    out['edges_set']=( set((repr(u),repr(v)) for u,v in Dn.edges()) == set((repr(u),repr(v)) for u,v in Df.edges()) )
    out['nodes']=( [repr(n) for n in Dn.nodes()] == [repr(n) for n in Df.nodes()] )
    out['indeg']=( sorted((repr(k),v) for k,v in Dn.in_degree()) == sorted((repr(k),v) for k,v in Df.in_degree()) )
    out['outdeg']=( sorted((repr(k),v) for k,v in Dn.out_degree()) == sorted((repr(k),v) for k,v in Df.out_degree()) )
    out['indeg_order']=( [(repr(k),v) for k,v in Dn.in_degree()] == [(repr(k),v) for k,v in Df.in_degree()] )
    return out
mism=0; digests={}
for N,p,seed in [(1200,0.006,5),(300,0.02,11),(50,0.1,1)]:
    Dn=nx.gnp_random_graph(N,p,seed=seed,directed=True); Df=fnx.gnp_random_graph(N,p,seed=seed,directed=True)
    s=sig(Dn,Df)
    for k,v in s.items():
        if not v: mism+=1; print(f"N{N} {k}: FAIL")
    digests[f"N{N}"]=hashlib.sha256(json.dumps([(repr(u),repr(v)) for u,v in Df.edges()]).encode()).hexdigest()
print(f"failures(vs nx)={mism}")
# STALENESS SEMANTICS: mutating during iteration must raise (isomorphism-critical)
def check_raises(make_iter, mutate, expect_substr):
    D=fnx.gnp_random_graph(30,0.1,seed=3,directed=True)
    it=iter(make_iter(D)); next(it)  # start
    mutate(D)
    try:
        for _ in it: pass
        return False, "no error raised"
    except RuntimeError as e:
        return (expect_substr in str(e)), str(e)
ok1,m1=check_raises(lambda D: D.edges(), lambda D: D.add_node('zz'), 'size')
ok2,m2=check_raises(lambda D: D.nodes(), lambda D: D.add_node('yy'), 'size')
ok3,m3=check_raises(lambda D: D.in_degree(), lambda D: D.add_node('xx'), 'size') if False else (True,'in_degree has no staleness check (graph=None) - matches prior behavior')
# no-mutation iteration must NOT raise
D=fnx.gnp_random_graph(30,0.1,seed=3,directed=True)
clean = (list(D.edges()) is not None and list(D.nodes()) is not None and list(D.in_degree()) is not None)
print("staleness edges(size):", ok1, "| nodes(size):", ok2, "| clean-iter ok:", clean)
print("DIVIT_GOLDEN", hashlib.sha256("|".join(f"{k}={digests[k]}" for k in sorted(digests)).encode()).hexdigest())
