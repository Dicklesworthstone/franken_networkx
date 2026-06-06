"""br-r37-c1-c1gz0 parity proof: node/edge_connectivity across shapes."""
import hashlib, random
import networkx as nx
import franken_networkx as fnx

rnd = random.Random(20260605)
fails, lines = [], []


def check(tag, fn_name, build, **kw):
    gn = build(nx)
    gf = build(fnx)
    rn = rf = en = ef = None
    try:
        rn = getattr(nx, fn_name)(gn, **kw)
    except Exception as e:
        en = (type(e).__name__, str(e))
    try:
        rf = getattr(fnx, fn_name)(gf, **kw)
    except Exception as e:
        ef = (type(e).__name__, str(e))
    ok = rn == rf and en == ef
    lines.append(f"{tag}|{fn_name}|{kw}|{rn}|{en}")
    if not ok:
        fails.append(tag)
        print(f"FAIL {tag} {fn_name} {kw}: nx={rn}/{en} fnx={rf}/{ef}")


def rand_graph(mod, directed, multi, n, m, selfloops):
    cls = (mod.MultiDiGraph if multi else mod.DiGraph) if directed else (mod.MultiGraph if multi else mod.Graph)
    g = cls()
    g.add_nodes_from(range(n))
    r = random.Random(7)
    for _ in range(m):
        u, v = r.randrange(n), r.randrange(n)
        if not selfloops and u == v:
            continue
        g.add_edge(u, v)
    return g


cases = 0
for fn in ("node_connectivity", "edge_connectivity"):
    for directed in (False, True):
        for multi in (False, True):
            for selfloops in (False, True):
                for n, m in [(1, 0), (2, 1), (8, 4), (8, 30), (30, 25), (30, 120), (60, 40)]:
                    tag = f"{fn}-d{directed}-m{multi}-sl{selfloops}-{n}/{m}"
                    check(tag, fn, lambda mod, d=directed, mu=multi, sl=selfloops, nn=n, mm=m:
                          rand_graph(mod, d, mu, nn, mm, sl))
                    cases += 1
    # s/t local pairs on a disconnected graph (must NOT short-circuit)
    check(f"{fn}-st-disconnected", fn,
          lambda mod: rand_graph(mod, False, False, 20, 10, False), s=0, t=19)
    check(f"{fn}-st-connected", fn,
          lambda mod: rand_graph(mod, False, False, 12, 40, False), s=0, t=11)
    cases += 2
    # flow_func on disconnected (nx returns 0 without calling it)
    from networkx.algorithms.flow import edmonds_karp
    check(f"{fn}-flowfunc-disc", fn,
          lambda mod: rand_graph(mod, False, False, 20, 8, False), flow_func=edmonds_karp)
    cases += 1
# cutoff for edge_connectivity
check("ec-cutoff-disc", "edge_connectivity",
      lambda mod: rand_graph(mod, True, False, 20, 8, False), cutoff=2)
check("ec-cutoff-conn", "edge_connectivity",
      lambda mod: rand_graph(mod, False, False, 10, 40, False), cutoff=1)
cases += 2

sha = hashlib.sha256("\n".join(lines).encode()).hexdigest()
print(f"cases: {cases + 0}, failures: {len(fails)} {fails[:6]}")
print("GOLDEN_SHA256:", sha)
