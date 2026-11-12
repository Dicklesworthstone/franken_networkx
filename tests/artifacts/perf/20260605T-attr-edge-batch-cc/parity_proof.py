"""br-r37-c1-pr8q6 parity proof: attributed add_edges_from batch vs nx + per-edge path."""
import hashlib, random, sys
import networkx as nx
import franken_networkx as fnx

fails = []

def canon(g):
    return "\n".join([
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g[n]) for n in g}),
        repr(dict(g.graph)),
    ])

def check(name, build):
    """build(mod) -> graph; compare fnx vs nx canonical."""
    try:
        cn = canon(build(nx))
        en = None
    except Exception as e:
        cn, en = None, (type(e).__name__, str(e))
    try:
        cf = canon(build(fnx))
        ef = None
    except Exception as e:
        cf, ef = None, (type(e).__name__, str(e))
    if cn != cf or en != ef:
        fails.append(name)
        print(f"FAIL {name}: err nx={en} fnx={ef}")
        if cn and cf:
            for a, b in zip(cn.split("\n"), cf.split("\n")):
                if a != b:
                    print("  nx :", a[:160]); print("  fnx:", b[:160]); break
    return cn == cf and en == ef

rnd = random.Random(20260605)
ncase = 0

# random attributed batches: sizes straddling the MIN=8 gate, dup edges, self-loops,
# mixed 2/3-tuples, varied attr value types, int/str/float/tuple node keys
for trial in range(80):
    n_edges = rnd.choice([0, 1, 7, 8, 9, 25, 400])
    keystyle = rnd.choice(["int", "str", "float", "tuple", "mixed"])
    def mk(i):
        if keystyle == "int": return rnd.randrange(60)
        if keystyle == "str": return f"n{rnd.randrange(60)}"
        if keystyle == "float": return float(rnd.randrange(30))
        if keystyle == "tuple": return (rnd.randrange(9), rnd.randrange(9))
        return rnd.choice([rnd.randrange(60), f"n{rnd.randrange(60)}", float(rnd.randrange(30))])
    edges = []
    for i in range(n_edges):
        u, v = mk(i), mk(i)
        r = rnd.random()
        if r < 0.25:
            edges.append((u, v))
        elif r < 0.5:
            edges.append((u, v, {}))
        elif r < 0.75:
            edges.append((u, v, {"weight": rnd.random()}))
        else:
            edges.append((u, v, {"weight": rnd.randrange(10), "color": "red", "flag": bool(rnd.randrange(2)), "f": rnd.random()}))
    if rnd.random() < 0.3 and edges:
        edges.append(edges[0])  # exact dup
    if rnd.random() < 0.3 and edges and len(edges[0]) == 3:
        u, v = edges[0][0], edges[0][1]
        edges.append((v, u, {"weight": 99}))  # reversed dup with attr overwrite
    def build(mod, edges=edges):
        g = mod.Graph()
        g.add_edges_from(edges)
        return g
    ncase += check(f"rand-{trial}-{keystyle}-{n_edges}", build)

# attr merge semantics on pre-existing edges
def build_merge(mod):
    g = mod.Graph()
    g.add_edge(1, 2, weight=1, keep="x")
    g.add_edges_from([(1, 2, {"weight": 7}), (2, 3, {"w": 1})] + [(i, i + 1) for i in range(3, 14)])
    return g
ncase += check("merge-preexisting", build_merge)

# global **attr (must bypass batch, still correct)
def build_global(mod):
    g = mod.Graph()
    g.add_edges_from([(i, i + 1, {"a": i}) for i in range(20)], weight=5)
    return g
ncase += check("global-attr", build_global)

# list-of-lists input (wrapper converts; raw path per-edge)
def build_lists(mod):
    g = mod.Graph()
    g.add_edges_from([[i, i + 1] for i in range(20)])
    return g
ncase += check("list-edges", build_lists)

# error paths: bad arity mid-batch (partial prefix must persist identically)
def build_badarity(mod):
    g = mod.Graph()
    try:
        g.add_edges_from([(0, 1, {"w": 1})] * 10 + [(1, 2, 3, 4)] + [(5, 6)])
    except Exception:
        pass
    return g
ncase += check("bad-arity-partial", build_badarity)

# non-dict third element (float) — TypeError, partial prefix
def build_baddata(mod):
    g = mod.Graph()
    try:
        g.add_edges_from([(0, 1, {"w": 1})] * 9 + [(1, 2, 1.5)])
    except Exception:
        pass
    return g
ncase += check("bad-third-partial", build_baddata)

# None endpoint mid-batch
def build_none(mod):
    g = mod.Graph()
    try:
        g.add_edges_from([(0, 1, {"w": 1})] * 9 + [(2, None)])
    except Exception:
        pass
    return g
ncase += check("none-endpoint-partial", build_none)

# unhashable endpoint mid-batch
def build_unhash(mod):
    g = mod.Graph()
    try:
        g.add_edges_from([(0, 1, {"w": 1})] * 9 + [([1, 2], 3)])
    except Exception:
        pass
    return g
ncase += check("unhashable-partial", build_unhash)

# mutation-after-batch: shared source dict must NOT alias edge data
def build_alias(mod):
    g = mod.Graph()
    shared = {"w": 1}
    g.add_edges_from([(i, i + 1, shared) for i in range(15)])
    shared["w"] = 999  # post-hoc mutation of the SOURCE dict
    g[0][1]["extra"] = 5
    return g
ncase += check("source-dict-no-alias", build_alias)

# weighted kernel exactness after batch (inner AttrMap sync)
gf = fnx.Graph(); gn = nx.Graph()
batch = [(i, (i * 7) % 40, {"weight": (i % 9) + 0.5}) for i in range(200)]
gf.add_edges_from(batch); gn.add_edges_from(batch)
import networkx.algorithms.shortest_paths.weighted as _w
df = fnx.single_source_dijkstra_path_length(gf, 0)
dn = nx.single_source_dijkstra_path_length(gn, 0)
if dict(df) != dict(dn):
    fails.append("dijkstra-after-batch"); print("FAIL dijkstra", )
else:
    ncase += 1
# generic graph ops post-batch
sub = gf.subgraph([0, 7, 14, 21]).copy()
deg_f = sorted(d for _, d in gf.degree(weight="weight"))
deg_n = sorted(d for _, d in gn.degree(weight="weight"))
if deg_f != deg_n:
    fails.append("weighted-degree"); print("FAIL weighted degree")
else:
    ncase += 1

# golden corpus sha
shas = []
rnd2 = random.Random(7)
for t in range(40):
    edges = [(rnd2.randrange(30), rnd2.randrange(30), {"w": rnd2.random()}) for _ in range(50)]
    g = fnx.Graph(); g.add_edges_from(edges)
    shas.append(hashlib.sha256(canon(g).encode()).hexdigest())
print("GOLDEN_CORPUS_SHA256:", hashlib.sha256("".join(shas).encode()).hexdigest())
print(f"cases passed: {ncase}, failures: {len(fails)}", fails[:8])
sys.exit(1 if fails else 0)
