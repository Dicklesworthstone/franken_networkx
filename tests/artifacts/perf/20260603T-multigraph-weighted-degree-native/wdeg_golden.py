import franken_networkx as fnx, networkx as nx, random, json, hashlib

def build(M, seed, n=40, e=140, with_selfloops=True, mixed=True):
    r = random.Random(seed); g = M()
    g.add_nodes_from(range(n))
    for i in range(e):
        u, v = r.randint(0, n-1), r.randint(0, n-1)
        if not with_selfloops and u == v:
            v = (v + 1) % n
        # mix: some edges have int weight, some float, some NO weight (default 1)
        kind = r.randint(0, 3) if mixed else 0
        if kind == 0:
            g.add_edge(u, v, w=r.randint(1, 9))         # int
        elif kind == 1:
            g.add_edge(u, v, w=r.random() * 5.0)        # float
        elif kind == 2:
            g.add_edge(u, v)                            # no w -> default 1
        else:
            g.add_edge(u, v, w=r.randint(1, 9), other=1)
    return g

records = []
mism = 0
for label, Mf, Mn in [
    ("MultiGraph", fnx.MultiGraph, nx.MultiGraph),
    ("MultiDiGraph", fnx.MultiDiGraph, nx.MultiDiGraph),
]:
    for seed in (1, 2, 3):
        for sl in (True, False):
            gf = build(Mf, seed, with_selfloops=sl)
            gn = build(Mn, seed, with_selfloops=sl)
            df = list(gf.degree(weight='w'))
            dn = list(gn.degree(weight='w'))
            # exact value + order + type comparison
            if df != dn:
                mism += 1
                # find first divergence
                for i,(a,b) in enumerate(zip(df,dn)):
                    if a != b:
                        print(f"  MISMATCH {label} seed={seed} sl={sl} idx={i}: fnx={a!r} nx={b!r}")
                        break
            # type fidelity: each total must match nx's python type exactly
            for (nf, vf), (nn, vn) in zip(df, dn):
                if type(vf) is not type(vn):
                    mism += 1
                    print(f"  TYPE MISMATCH {label} node={nf}: fnx {type(vf).__name__} vs nx {type(vn).__name__}")
            records.append([label, seed, sl, [[n, (round(v,12) if isinstance(v,float) else v)] for n,v in df]])
            # also test single-node + nbunch subset still correct (fallback path)
            for node in list(gf.nodes())[:5]:
                if gf.degree(node, weight='w') != gn.degree(node, weight='w'):
                    mism += 1; print(f"  SINGLE MISMATCH {label} node={node}")

blob = json.dumps(records, sort_keys=True).encode()
h = hashlib.sha256(blob).hexdigest()
print(f"mismatches={mism}")
print(f"WDEG_GOLDEN {h}")
