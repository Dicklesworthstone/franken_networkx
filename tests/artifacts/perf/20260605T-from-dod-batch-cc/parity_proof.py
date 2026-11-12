"""br-r37-c1-nlanb parity proof: from_dict_of_dicts batched vs nx."""
import hashlib, random, sys
import networkx as nx
import franken_networkx as fnx

fails = []

def canon(g):
    return "\n".join([
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g[n]) for n in g}),
        repr(type(g).__name__),
    ])

def check(name, d, **kw):
    rn = rf = cn = cf = None
    try: cn = canon(nx.from_dict_of_dicts(d, **{k: (getattr(nx, v.__name__) if isinstance(v, type) and hasattr(nx, v.__name__) else v) for k, v in kw.items()}))
    except Exception as e: rn = (type(e).__name__, str(e))
    try: cf = canon(fnx.from_dict_of_dicts(d, **kw))
    except Exception as e: rf = (type(e).__name__, str(e))
    # type name differs (nx.Graph vs fnx Graph both 'Graph') — canon includes name only
    ok = (cn == cf) and (rn == rf)
    if not ok:
        fails.append(name); print(f"FAIL {name} err nx={rn} fnx={rf}")
        if cn and cf:
            for a, b in zip(cn.split("\n"), cf.split("\n")):
                if a != b: print("  nx :", a[:170]); print("  fnx:", b[:170]); break
    return ok

rnd = random.Random(20260605)
ncase = 0

# random dods from random graphs (the canonical round-trip input)
for trial in range(40):
    n = rnd.choice([0, 1, 2, 30, 200])
    g = nx.Graph()
    labels = [rnd.choice([rnd.randrange(50), f"s{rnd.randrange(50)}", float(rnd.randrange(25))]) for _ in range(n)]
    g.add_nodes_from(labels)
    for _ in range(n * 2):
        u, v = rnd.choice(labels) if labels else 0, rnd.choice(labels) if labels else 1
        if rnd.random() < 0.5:
            g.add_edge(u, v)
        else:
            g.add_edge(u, v, weight=rnd.random(), color="red")
    d = nx.to_dict_of_dicts(g)
    ncase += check(f"rt-{trial}", d)

# hand-crafted
ncase += check("empty", {})
ncase += check("isolated", {"a": {}, "b": {}})
ncase += check("selfloop", {"a": {"a": {"w": 1}}})
ncase += check("attrs-shared-object", (lambda s: {"a": {"b": s}, "b": {"a": s}})({"w": 5}))
ncase += check("asym-input", {"a": {"b": {"w": 1}}})  # only one direction listed

# aliasing: result edge dict must not alias the input dict
d_alias = {"a": {"b": {"w": 1}}, "b": {"a": {"w": 1}}}
gf = fnx.from_dict_of_dicts(d_alias)
d_alias["a"]["b"]["w"] = 999
if gf["a"]["b"]["w"] != 1: fails.append("aliasing"); print("FAIL aliasing")
else: ncase += 1
gf["a"]["b"]["x"] = 7
if "x" in d_alias["a"]["b"]: fails.append("aliasing-rev"); print("FAIL aliasing-rev")
else: ncase += 1

# malformed: non-dict attrs value — nx leaves nodes but NO edge
d_bad = {"a": {"b": 1.5}}
rn = rf = None
gn_state = gf_state = None
try: nx.from_dict_of_dicts(d_bad)
except Exception as e: rn = (type(e).__name__, str(e))
try: fnx.from_dict_of_dicts(d_bad)
except Exception as e: rf = (type(e).__name__, str(e))
if rn != rf: fails.append("malformed-err"); print("FAIL malformed err", rn, rf)
else: ncase += 1

# create_using variants must keep old behavior (loop path)
ncase += check("digraph", {"a": {"b": {"w": 1}}, "b": {"a": {"w": 1}}}, create_using=fnx.DiGraph)
ncase += check("multigraph-input", {"a": {"b": {0: {"w": 1}, 1: {"w": 2}}}, "b": {"a": {0: {"w": 1}, 1: {"w": 2}}}}, create_using=fnx.MultiGraph, multigraph_input=True)

# node order: nodes from d FIRST (incl isolated), then edge-discovered — none new here
ncase += check("node-order", {"z": {"a": {}}, "a": {"z": {}}, "m": {}})

# golden corpus sha
shas = []
rnd2 = random.Random(5)
for t in range(25):
    g = nx.Graph()
    for _ in range(60):
        g.add_edge(rnd2.randrange(30), rnd2.randrange(30), w=round(rnd2.random(), 9))
    d = nx.to_dict_of_dicts(g)
    shas.append(hashlib.sha256(canon(fnx.from_dict_of_dicts(d)).encode()).hexdigest())
print("GOLDEN_CORPUS_SHA256:", hashlib.sha256("".join(shas).encode()).hexdigest())
print(f"cases passed: {ncase}, failures: {len(fails)}", fails[:8])
sys.exit(1 if fails else 0)
