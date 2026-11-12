"""br-r37-c1-2vmel parity proof: native read_edgelist_simple vs nx + delegated path."""
import hashlib, os, random, sys, tempfile

import networkx as nx
import franken_networkx as fnx

TMP = tempfile.mkdtemp(prefix="elparity", dir="/data/tmp")
fails = []

def canon(g):
    return "\n".join([
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g[n]) for n in g}),
    ])

def check(name, path, weighted=False, **kwargs):
    rn = rf = cn = cf = None
    try:
        cn = canon((nx.read_weighted_edgelist if weighted else nx.read_edgelist)(path, **kwargs))
    except Exception as e:
        rn = (type(e).__name__, str(e))
    try:
        cf = canon((fnx.read_weighted_edgelist if weighted else fnx.read_edgelist)(path, **kwargs))
    except Exception as e:
        rf = (type(e).__name__, str(e))
    ok = cn == cf and rn == rf
    if not ok:
        fails.append(name)
        print(f"FAIL {name} err nx={rn} fnx={rf}")
        if cn and cf:
            for a, b in zip(cn.split("\n"), cf.split("\n")):
                if a != b:
                    print("  nx :", a[:170]); print("  fnx:", b[:170]); break
    return ok

ncase = 0
rnd = random.Random(99)

# corpus: nx-written no-data files (the 5.39x bench shape)
for trial in range(30):
    n = rnd.choice([0, 1, 2, 50, 400])
    g = nx.Graph()
    labels = [rnd.choice([str(i), f"node_{i}", f"ü{i}"]) for i in range(n)]
    g.add_nodes_from(labels)
    for _ in range(n * 2):
        g.add_edge(rnd.choice(labels), rnd.choice(labels))
    p = os.path.join(TMP, f"nd{trial}.el")
    nx.write_edgelist(g, p, data=False)
    ncase += check(f"nodata-{trial}", p)
    ncase += check(f"nodata-dataFalse-{trial}", p, data=False)

# corpus: weighted files
for trial in range(20):
    n = rnd.choice([2, 40, 300])
    g = nx.Graph()
    for _ in range(n * 2):
        u, v = rnd.randrange(n), rnd.randrange(n)
        g.add_edge(str(u), str(v), weight=round(rnd.uniform(-100, 100), 6))
    p = os.path.join(TMP, f"w{trial}.el")
    nx.write_weighted_edgelist(g, p)
    ncase += check(f"weighted-{trial}", p, weighted=True)

# hand-crafted
hand = {
    "blank_lines": ("a b\n\nc d\n", {}),
    "one_token_lines": ("a b\nlonely\nc d\n", {}),
    "comments": ("# hdr\na b # tail\nc d#tight\n", {}),
    "tabs": ("a\tb\nc\td\n", {}),
    "dup_edges": ("a b\nb a\na b\n", {}),
    "self_loop": ("a a\nb b\n", {}),
    "crlf": ("a b\r\nc d\r\n", {}),
    "no_trailing_nl": ("a b\nc d", {}),
    "extras_ignored_dataFalse": ("a b junk more\nc d x\n", {"data": False}),
}
for name, (content, kw) in hand.items():
    p = os.path.join(TMP, f"h_{name}.el")
    open(p, "w", encoding="utf-8").write(content)
    ncase += check(f"hand-{name}", p, **kw)

# weighted hand-crafted incl. float-parity surfaces and error paths
whand = {
    "w_basic": "a b 1.5\nc d 2\n",
    "w_missing_col": "a b\nc d 2\n",
    "w_exp": "a b 1e-3\nc d -2.5E2\ne f +4.25\n",
    "w_inf_nan": "a b inf\nc d nan\ne f -Infinity\ng h NAN\n",
    "w_underscore": "a b 1_0\nc d 2\n",      # Python-only float syntax -> delegate
    "w_extra_col": "a b 1.5 9\n",            # IndexError in nx
    "w_bad_float": "a b xyz\n",              # TypeError in nx
    "w_dup_overwrite": "a b 1\na b 2.5\n",
    "w_neg_zero": "a b -0.0\n",
    "w_huge": "a b 1e308\nc d 1e309\n",      # 1e309 -> inf in python float
}
for name, content in whand.items():
    p = os.path.join(TMP, f"wh_{name}.el")
    open(p, "w", encoding="utf-8").write(content)
    ncase += check(f"hand-{name}", p, weighted=True)

# data=True with dict-repr columns (must delegate, stay correct)
g = nx.Graph()
g.add_edge("a", "b", weight=2, color="red")
g.add_edge("b", "c")
p = os.path.join(TMP, "dictcols.el")
nx.write_edgelist(g, p)
ncase += check("dictcols-dataTrue", p)

# non-default kwargs still delegate correctly
p2 = os.path.join(TMP, "kw.el")
open(p2, "w").write("1 2\n2 3\n")
g_int = fnx.read_edgelist(p2, nodetype=int)
assert list(g_int) == [1, 2, 3], list(g_int)
g_di = fnx.read_edgelist(p2, create_using=fnx.DiGraph)
assert g_di.is_directed()
g_cu = fnx.read_edgelist(p2, create_using=fnx.Graph)
assert type(g_cu) is fnx.Graph and canon(g_cu) == canon(fnx.read_edgelist(p2))
ncase += 3

# missing file parity
rn = rf = None
try: nx.read_edgelist(os.path.join(TMP, "nope.el"))
except Exception as e: rn = type(e).__name__
try: fnx.read_edgelist(os.path.join(TMP, "nope.el"))
except Exception as e: rf = type(e).__name__
if rn != rf: fails.append("missing"); print("FAIL missing", rn, rf)
else: ncase += 1

# mutability of fast-path graph
p3 = os.path.join(TMP, "mut.el")
open(p3, "w").write("a b 1.5\nb c 2\n")
gm = fnx.read_weighted_edgelist(p3)
gm["a"]["b"]["weight"] = 7
assert gm["b"]["a"]["weight"] == 7
gm.add_edge("c", "z")
assert gm.number_of_edges() == 3
assert dict(fnx.single_source_dijkstra_path_length(gm, "a")) == dict(
    nx.single_source_dijkstra_path_length(
        nx.Graph([("a", "b", {"weight": 7}), ("b", "c", {"weight": 2.0}), ("c", "z", {})]), "a"))
ncase += 1

# golden corpus sha
shas = []
for trial in range(30):
    shas.append(hashlib.sha256(canon(fnx.read_edgelist(os.path.join(TMP, f"nd{trial}.el"))).encode()).hexdigest())
for trial in range(20):
    shas.append(hashlib.sha256(canon(fnx.read_weighted_edgelist(os.path.join(TMP, f"w{trial}.el"))).encode()).hexdigest())
print("GOLDEN_CORPUS_SHA256:", hashlib.sha256("".join(shas).encode()).hexdigest())
print(f"cases passed: {ncase}, failures: {len(fails)}", fails[:10])
sys.exit(1 if fails else 0)
