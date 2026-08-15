"""Same-invocation A/B for the multigraph edge-membership walk (br-r37-c1-6fs77).

incumbent = the adjacency WALK this change replaced, restored on the view class
            (with the key-0 fix already in it, so both arms answer identically
            and only the path differs)
candidate = the shipped `self._graph.has_edge(u, v, key)` delegation
networkx  = live networkx 3.6.1, same fixture, same invocation

Balanced ABBAABBA square, per-arm A/A nulls, class attribute rebound OUTSIDE
every timed region.
"""
import gc, hashlib, os, platform, random, statistics, time
import networkx as nx
import franken_networkx as fnx

SQUARE, NULL_BOUND = "ABBAABBA", 0.02
ROUNDS = int(os.environ.get("ROUNDS", "61"))
REPS = int(os.environ.get("REPS", "400"))
WARMUP = 8


def build(module, nodes=2000, edges=8000, seed=11):
    rng = random.Random(seed)
    graph = module.MultiGraph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from(names)
    seen = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]], weight=1.0)
    return graph, [(names[a], names[b]) for a, b in seen]


g_fx, edges_fx = build(fnx)
g_nx, edges_nx = build(nx)
VIEW = type(g_fx.edges)
SHIPPED = VIEW.__contains__


def walk_contains(self, edge):
    """The pre-change path, with the key-0 fix, so only the ROUTE differs."""
    N = len(edge)
    if N == 3:
        u, v, key = edge[0], edge[1], edge[2]
    elif N == 2:
        u, v, key = edge[0], edge[1], 0
    else:
        raise ValueError("MultiEdge must have length 2 or 3")
    adj = self._graph.adj
    try:
        if u in adj and v in adj[u]:
            return key in adj[u][v]
        if v in adj and u in adj[v]:
            return key in adj[v][u]
    except (KeyError, TypeError):
        return False
    return False


rng = random.Random(7)
probes = [edges_fx[rng.randrange(len(edges_fx))] for _ in range(REPS)]
rng2 = random.Random(7)
probes_nx = [edges_nx[rng2.randrange(len(edges_nx))] for _ in range(REPS)]
view_fx, view_nx = g_fx.edges, g_nx.edges


def use_walk():
    VIEW.__contains__ = walk_contains


def use_shipped():
    VIEW.__contains__ = SHIPPED


def noop():
    return None


def probe_fx():
    return sum(1 for p in probes if p in view_fx)


def probe_nx():
    return sum(1 for p in probes_nx if p in view_nx)


def time_slot(fn):
    gc.collect(); gc.disable()
    try:
        t = time.perf_counter_ns(); fn(); return time.perf_counter_ns() - t
    finally:
        gc.enable()


def bootstrap_ci(values, iters=4000, seed=3):
    rng = random.Random(seed); n = len(values)
    m = sorted(statistics.median(values[rng.randrange(n)] for _ in range(n)) for _ in range(iters))
    return m[int(0.025 * iters)], m[int(0.975 * iters)]


def run_row(label, a_setup, a_fn, b_setup, b_fn):
    for _ in range(WARMUP):
        a_setup(); a_fn(); b_setup(); b_fn()
    ratios, na, nb = [], [], []
    for _ in range(ROUNDS):
        a, b = [], []
        for slot in SQUARE:
            if slot == "A":
                a_setup(); a.append(time_slot(a_fn))
            else:
                b_setup(); b.append(time_slot(b_fn))
        ratios.append(statistics.median(a) / statistics.median(b))
        na.append(statistics.median(a[:2]) / statistics.median(a[2:]))
        nb.append(statistics.median(b[:2]) / statistics.median(b[2:]))
    r = statistics.median(ratios); lo, hi = bootstrap_ci(ratios)
    x, y = statistics.median(na), statistics.median(nb)
    ok = abs(x - 1.0) <= NULL_BOUND and abs(y - 1.0) <= NULL_BOUND
    verdict = "NULL-FAILED" if not ok else ("STRADDLES-1" if lo <= 1.0 <= hi else "ADMISSIBLE")
    print(f"  {label:30s} {r:7.4f}x  CI [{lo:.4f}, {hi:.4f}]  nulls {x:.4f}/{y:.4f}  {verdict}")


import franken_networkx._fnx as ext
with open(ext.__file__, "rb") as fh:
    print(f"  bench_elf_sha256={hashlib.sha256(fh.read()).hexdigest()}")
print(f"  host {platform.node()}  nx {nx.__version__}  loadavg {os.getloadavg()}  rounds/reps {ROUNDS}/{REPS}")

use_walk(); assert probe_fx() == REPS == probe_nx()
use_shipped(); assert probe_fx() == REPS

print(f"\nsquare={SQUARE}")
print("  RATIO t_walk / t_native   (>1 means the delegation is faster)")
run_row("MG contains: walk -> native", use_walk, probe_fx, use_shipped, probe_fx)
print("  RATIO t_networkx / t_fnx  (>1 means fnx faster)")
run_row("nx vs fnx WALK (before)", noop, probe_nx, use_walk, probe_fx)
run_row("nx vs fnx NATIVE (after)", noop, probe_nx, use_shipped, probe_fx)
run_row("CONTROL nx vs nx", noop, probe_nx, noop, probe_nx)
use_shipped()
print(f"  loadavg_end {os.getloadavg()}")
