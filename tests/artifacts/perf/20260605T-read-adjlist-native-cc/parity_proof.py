"""br-r37-c1-770mm parity proof: native read_adjlist_simple vs nx + old delegated path."""
import hashlib, os, random, sys, tempfile

import networkx as nx
import franken_networkx as fnx
from franken_networkx import readwrite as fnx_rw

TMP = tempfile.mkdtemp(prefix="adjparity", dir="/data/tmp")
fails = []

def canon(g):
    """Canonical dump capturing node order, edge order, adjacency order, attrs."""
    parts = []
    parts.append(repr([(n, dict(a)) for n, a in g.nodes(data=True)]))
    parts.append(repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]))
    parts.append(repr({n: list(g[n]) for n in g}))
    parts.append(repr(dict(g.graph)))
    return "\n".join(parts)

def check(name, path, **kwargs):
    gnx = nx.read_adjlist(path, **kwargs)
    gfx = fnx.read_adjlist(path, **kwargs)
    gold = fnx_rw._from_nx_graph(nx.read_adjlist(path, **kwargs))  # old delegated result
    cn, cf, cg = canon(gnx), canon(gfx), canon(gold)
    ok = (cn == cf == cg) and type(gfx) is fnx.Graph
    if not ok:
        fails.append(name)
        print(f"FAIL {name}")
        if cf != cn:
            for ln, lf in zip(cn.split("\n"), cf.split("\n")):
                if ln != lf:
                    print("  nx :", ln[:200]); print("  fnx:", lf[:200]); break
        if cf != cg:
            print("  fast path != old delegated path")
    return ok

random.seed(1234)
ncase = 0
# --- corpus: nx-written files across shapes ---
for trial in range(60):
    n = random.choice([0, 1, 2, 5, 30, 200])
    g = nx.Graph()
    labels = []
    style = random.choice(["int", "str", "uni", "mixed"])
    for i in range(n):
        if style == "int": labels.append(str(i))
        elif style == "str": labels.append(f"node_{i}")
        elif style == "uni": labels.append(f"ñd{i}")
        else: labels.append(random.choice([str(i), f"x{i}", f"ü{i}"]))
    g.add_nodes_from(labels)
    for _ in range(int(n * random.uniform(0, 4))):
        u, v = random.choice(labels), random.choice(labels)
        g.add_edge(u, v)  # may include self-loops
    p = os.path.join(TMP, f"c{trial}.adjlist")
    nx.write_adjlist(g, p)
    ncase += check(f"corpus-{trial}-{style}-n{n}", p)

# --- hand-crafted adversarial files (valid for nx) ---
hand = {
    "tabs": "a\tb\tc\nb\td\n",
    "dup_edges": "a b b c\nb a\nc a\n",
    "self_loop": "a a b\nb b\n",
    "inline_comment": "a b # rest ignored\nb c#tight\n",
    "comment_only_lines": "# header\n#another\na b\n# mid\nb c\n",
    "isolated": "a\nb\nc a\n",
    "no_trailing_newline": "a b\nb c",
    "crlf": "a b\r\nb c\r\n",
    "unicode_ws": "a b\nc d\n",
    "single_node_lines": "a\nb\nc\n",
    "shared_targets": "a b c d\nb c d\nc d\nd\n",
    "numeric_lookalike": "1 2 3\n2 4\n10 1\n",
}
for name, content in hand.items():
    p = os.path.join(TMP, f"h_{name}.adjlist")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    ncase += check(f"hand-{name}", p)

# --- error parity: blank / ws-only lines must raise IndexError in both ---
for name, content in {"blank": "a b\n\nc d\n", "wsonly": "a b\n   \nc d\n", "wscomment": "a b\n  # x\nc d\n"}.items():
    p = os.path.join(TMP, f"e_{name}.adjlist")
    open(p, "w").write(content)
    rn = rf = None
    try: nx.read_adjlist(p)
    except Exception as e: rn = (type(e).__name__, str(e))
    try: fnx.read_adjlist(p)
    except Exception as e: rf = (type(e).__name__, str(e))
    if rn != rf or rn is None:
        fails.append(f"err-{name}"); print("FAIL err", name, rn, rf)
    else:
        ncase += 1

# --- missing file parity ---
rn = rf = None
try: nx.read_adjlist(os.path.join(TMP, "nope.adjlist"))
except Exception as e: rn = type(e).__name__
try: fnx.read_adjlist(os.path.join(TMP, "nope.adjlist"))
except Exception as e: rf = type(e).__name__
if rn != rf: fails.append("err-missing"); print("FAIL missing", rn, rf)
else: ncase += 1

# --- non-default kwargs still honoured (delegated path) ---
p = os.path.join(TMP, "kw.adjlist")
open(p, "w").write("1 2 3\n2 4\n")
g_int = fnx.read_adjlist(p, nodetype=int)
gn_int = nx.read_adjlist(p, nodetype=int)
assert list(g_int) == list(gn_int) == [1, 2, 3, 4], list(g_int)
g_di = fnx.read_adjlist(p, create_using=fnx.DiGraph)
assert g_di.is_directed() and list(g_di.edges()) == [("1","2"),("1","3"),("2","4")]
g_cu = fnx.read_adjlist(p, create_using=fnx.Graph)  # class create_using: fast path eligible
assert type(g_cu) is fnx.Graph and canon(g_cu) == canon(fnx.read_adjlist(p))
g_dl = fnx.read_adjlist(p, delimiter=" ")
assert list(g_dl) == list(nx.read_adjlist(p, delimiter=" "))
ncase += 5

# --- downstream mutation behavior of fast-path graph ---
p2 = os.path.join(TMP, "mut.adjlist")
open(p2, "w").write("a b c\nb c\n")
gm = fnx.read_adjlist(p2)
gm["a"]["b"]["w"] = 3
assert gm["b"]["a"]["w"] == 3
gm.add_edge("c", "zz")
gm.add_node("solo", color="red")
assert gm.number_of_edges() == 4 and "zz" in gm and gm.nodes["solo"]["color"] == "red"
cp = gm.copy()
assert list(cp.edges()) == list(gm.edges())
assert sorted(d for _, d in gm.degree()) == sorted(d for _, d in cp.degree())
import pickle
ncase += 1

# golden corpus sha
shas = []
for trial in range(60):
    p = os.path.join(TMP, f"c{trial}.adjlist")
    shas.append(hashlib.sha256(canon(fnx.read_adjlist(p)).encode()).hexdigest())
for name in hand:
    p = os.path.join(TMP, f"h_{name}.adjlist")
    shas.append(hashlib.sha256(canon(fnx.read_adjlist(p)).encode()).hexdigest())
print("GOLDEN_CORPUS_SHA256:", hashlib.sha256("".join(shas).encode()).hexdigest())
print(f"cases passed: {ncase}, failures: {len(fails)}", fails[:10])
sys.exit(1 if fails else 0)
