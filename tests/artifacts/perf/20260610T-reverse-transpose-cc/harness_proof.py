import hashlib, json, warnings
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx

def canon(G):
    # full structural + attr fingerprint in iteration order
    parts = []
    parts.append("NODES")
    for n, d in G.nodes(data=True):
        parts.append(f"{n!r}|{sorted(d.items())!r}")
    parts.append("EDGES")
    if G.is_multigraph():
        for u, v, k, d in G.edges(keys=True, data=True):
            parts.append(f"{u!r}->{v!r}#{k!r}|{sorted(d.items())!r}")
    else:
        for u, v, d in G.edges(data=True):
            parts.append(f"{u!r}->{v!r}|{sorted(d.items())!r}")
    parts.append(f"GRAPH|{sorted(G.graph.items())!r}")
    return "\n".join(parts)

def build(modn, modf, kind, n, seed, attrs):
    if kind == "di":
        gn = nx.gnp_random_graph(n, 0.06, seed=seed, directed=True)
        gf = fnx.gnp_random_graph(n, 0.06, seed=seed, directed=True)
    else:
        gn = nx.MultiDiGraph(nx.gnp_random_graph(n, 0.06, seed=seed, directed=True))
        gf = fnx.MultiDiGraph(fnx.gnp_random_graph(n, 0.06, seed=seed, directed=True))
        # add a few parallel edges deterministically
        es = list(gn.edges())[:5]
        for (u, v) in es:
            gn.add_edge(u, v); gf.add_edge(u, v)
    if attrs:
        # set edge + node + graph attrs on both via uniform API
        for (a, b) in list(gn.edges())[:20]:
            for G in (gn, gf):
                if G.is_multigraph():
                    G[a][b][0]["w"] = 3
                else:
                    G[a][b]["w"] = 3
        for nd in list(gn.nodes())[:10]:
            gn.nodes[nd]["c"] = "x"; gf.nodes[nd]["c"] = "x"
        gn.graph["lbl"] = "g"; gf.graph["lbl"] = "g"
    return gn, gf

fh = hashlib.sha256(); nh = hashlib.sha256(); mism = 0; total = 0
for kind in ("di", "multi"):
    for seed in range(5):
        for attrs in (False, True):
            for copy in (True,):
                gn, gf = build(nx, fnx, kind, 120, seed, attrs)
                rn = gn.reverse(copy=copy)
                rf = gf.reverse(copy=copy)
                cn = canon(rn); cf = canon(rf)
                total += 1
                nh.update(cn.encode()); nh.update(b"||")
                fh.update(cf.encode()); fh.update(b"||")
                if cn != cf:
                    mism += 1
                    if mism <= 2:
                        print(f"MISMATCH kind={kind} seed={seed} attrs={attrs}")
                        for ln_n, ln_f in zip(cn.split("\n"), cf.split("\n")):
                            if ln_n != ln_f:
                                print("  nx :", ln_n); print("  fnx:", ln_f); break
print(f"cases={total} mismatches={mism}")
print(f"fnx_sha={fh.hexdigest()}")
print(f"nx_sha ={nh.hexdigest()}")
print(f"MATCH={fh.hexdigest()==nh.hexdigest()}")
