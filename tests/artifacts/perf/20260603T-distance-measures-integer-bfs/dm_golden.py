import hashlib, json, networkx as nx, franken_networkx as fnx
def canon(Gn, Gf):
    out={}
    for name, fn in [
        ("diameter", lambda G,M: M.diameter(G)),
        ("radius", lambda G,M: M.radius(G)),
        ("eccentricity", lambda G,M: sorted((repr(k),v) for k,v in M.eccentricity(G).items())),
        ("center", lambda G,M: sorted(repr(x) for x in M.center(G))),
        ("periphery", lambda G,M: sorted(repr(x) for x in M.periphery(G))),
    ]:
        rn=fn(Gn,nx); rf=fn(Gf,fnx)
        out[name]=("OK" if rn==rf else f"MISMATCH nx={rn} fnx={rf}", rf)
    return out
results={}; mism=0
for N,m,seed in [(800,5,3),(400,3,11),(150,4,7),(60,2,1)]:
    Gn=nx.barabasi_albert_graph(N,m,seed=seed); Gf=fnx.barabasi_albert_graph(N,m,seed=seed)
    c=canon(Gn,Gf)
    for k,(status,val) in c.items():
        if status!="OK": mism+=1; print(f"N{N} {k}: {status}")
        results[f"N{N}_{k}"]=hashlib.sha256(json.dumps(val).encode()).hexdigest()
print(f"mismatches={mism} cases={len(results)}")
print("DM_GOLDEN", hashlib.sha256("|".join(f"{k}={results[k]}" for k in sorted(results)).encode()).hexdigest())
