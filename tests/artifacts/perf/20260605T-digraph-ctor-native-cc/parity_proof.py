"""br-r37-c1-dgctor parity proof: DiGraph(Graph) native ctor vs nx."""
import hashlib, random, sys
import networkx as nx
import franken_networkx as fnx

fails = []

def canon(g):
    return "\n".join([
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g.succ[n]) for n in g}),
        repr({n: list(g.pred[n]) for n in g}),
        repr(dict(g.graph)),
    ])

def build_pair(edges, nodes=(), gattrs=None, nattrs=None):
    gn, gf = nx.Graph(), fnx.Graph()
    for g in (gn, gf):
        g.add_nodes_from(nodes)
        g.add_edges_from(edges)
        if gattrs: g.graph.update(gattrs)
        if nattrs:
            for n, a in nattrs.items():
                if n in g: g.nodes[n].update(a)
    return gn, gf

def check(name, edges, nodes=(), gattrs=None, nattrs=None, attr=None):
    gn, gf = build_pair(edges, nodes, gattrs, nattrs)
    kw = attr or {}
    rn = rf = cn = cf = None
    try: cn = canon(nx.DiGraph(gn, **kw))
    except Exception as e: rn = (type(e).__name__, str(e))
    try: cf = canon(fnx.DiGraph(gf, **kw))
    except Exception as e: rf = (type(e).__name__, str(e))
    ok = cn == cf and rn == rf
    if not ok:
        fails.append(name); print(f"FAIL {name} err nx={rn} fnx={rf}")
        if cn and cf:
            for a, b in zip(cn.split("\n"), cf.split("\n")):
                if a != b: print("  nx :", a[:170]); print("  fnx:", b[:170]); break
    return ok

rnd = random.Random(20260605)
ncase = 0
# random corpora — str labels (z6uka excluded), weighted/plain, self-loops, isolated nodes
for trial in range(40):
    n = rnd.choice([0, 1, 2, 30, 200])
    labels = [f"s{rnd.randrange(60)}" for _ in range(n)]
    edges = []
    for _ in range(n * 2):
        u, v = rnd.choice(labels) if labels else "a", rnd.choice(labels) if labels else "b"
        if rnd.random() < 0.4: edges.append((u, v))
        else: edges.append((u, v, {"w": rnd.random(), "c": "x"}))
    iso = [f"iso{i}" for i in range(rnd.randrange(3))]
    ncase += check(f"rand-{trial}", edges, nodes=labels + iso,
                   gattrs={"name": f"g{trial}"} if rnd.random() < 0.5 else None,
                   nattrs={labels[0]: {"tag": trial}} if labels else None)

# attr override kwarg
ncase += check("attr-kwarg", [("a", "b", {"w": 1})], attr={"name": "X", "k": 2})
# empty
ncase += check("empty", [])
# self-loop ordering
ncase += check("selfloops", [("a", "a"), ("a", "b"), ("b", "b", {"w": 2})])

# copy depth: fresh dicts, shared values; mutation isolation
gn, gf = build_pair([("a", "b", {"w": [1]})], gattrs={"meta": [9]})
dn, df = nx.DiGraph(gn), fnx.DiGraph(gf)
ok = (df["a"]["b"] is not gf["a"]["b"] and df["a"]["b"]["w"] is gf["a"]["b"]["w"]
      and df["a"]["b"] is not df["b"]["a"]
      and df.graph is not gf.graph and df.graph["meta"] is gf.graph["meta"])
ok_nx = (dn["a"]["b"] is not gn["a"]["b"] and dn["a"]["b"]["w"] is gn["a"]["b"]["w"]
         and dn["a"]["b"] is not dn["b"]["a"]
         and dn.graph is not gn.graph and dn.graph["meta"] is gn.graph["meta"])
if not (ok and ok_nx): fails.append("copy-depth"); print("FAIL copy-depth", ok, ok_nx)
else: ncase += 1
# source unaffected by target mutation
df.add_edge("zz", "qq"); df["a"]["b"]["new"] = 1
if "zz" in gf or "new" in gf["a"]["b"]: fails.append("isolation"); print("FAIL isolation")
else: ncase += 1

# post-ctor mutability + kernels exact
gn2, gf2 = build_pair([(f"n{i}", f"n{(i*3)%20}", {"weight": (i % 7) + 0.5}) for i in range(60)])
dn2, df2 = nx.DiGraph(gn2), fnx.DiGraph(gf2)
src = next(iter(dn2))
if dict(nx.single_source_dijkstra_path_length(dn2, src)) != dict(fnx.single_source_dijkstra_path_length(df2, src)):
    fails.append("dijkstra"); print("FAIL dijkstra")
else: ncase += 1
df2.remove_node(src); dn2.remove_node(src)
if canon(dn2) != canon(df2): fails.append("post-mutation"); print("FAIL post-mutation")
else: ncase += 1

# non-fast-path combos still correct (MultiGraph source, DiGraph source, subclass)
gm_n, gm_f = nx.MultiGraph(), fnx.MultiGraph()
for g in (gm_n, gm_f): g.add_edges_from([("a", "b", {"w": 1}), ("a", "b", {"w": 2})])
if sorted(nx.DiGraph(gm_n).edges(data=True)) != sorted(fnx.DiGraph(gm_f).edges(data=True)):
    fails.append("multi-src"); print("FAIL multi-src")
else: ncase += 1
gd_n, gd_f = nx.DiGraph([("a", "b")]), fnx.DiGraph([("a", "b")])
if canon(nx.DiGraph(gd_n)) != canon(fnx.DiGraph(gd_f)): fails.append("digraph-src"); print("FAIL digraph-src")
else: ncase += 1

# int-keyed graphs (lazy-int display path)
gn3, gf3 = nx.Graph(), fnx.Graph()
for g in (gn3, gf3): g.add_edges_from([(i, i + 1) for i in range(30)])
if canon(nx.DiGraph(gn3)) != canon(fnx.DiGraph(gf3)): fails.append("int-keys"); print("FAIL int-keys")
else: ncase += 1

# golden sha
shas = []
rnd2 = random.Random(4)
for t in range(25):
    edges = [(f"a{rnd2.randrange(25)}", f"a{rnd2.randrange(25)}", {"w": round(rnd2.random(), 9)}) for _ in range(50)]
    gf = fnx.Graph(); gf.add_edges_from(edges)
    shas.append(hashlib.sha256(canon(fnx.DiGraph(gf)).encode()).hexdigest())
print("GOLDEN_CORPUS_SHA256:", hashlib.sha256("".join(shas).encode()).hexdigest())
print(f"cases passed: {ncase}, failures: {len(fails)}", fails[:8])
sys.exit(1 if fails else 0)
