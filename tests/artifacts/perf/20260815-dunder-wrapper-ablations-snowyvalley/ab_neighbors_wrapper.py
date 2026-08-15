"""Same-invocation A/B for br-r37-c1-6mxtl: the `G.neighbors(n)` Python wrapper.

incumbent = the pre-change shipped path — the exact wrapper body recovered from
            git 718916464, re-applied over the new native slot
candidate = the native slot
networkx  = live networkx 3.6.1, same fixture, same invocation

Balanced ABBAABBA square, per-arm A/A nulls, one collect per ROUND with two
untimed warm calls per arm (br-r37-c1-7x25w), class attribute rebound OUTSIDE
every timed region.
"""
import gc, hashlib, os, platform, random, statistics, time
import networkx as nx
import franken_networkx as fnx
import franken_networkx._fnx as ext

SQUARE, NULL_BOUND = "ABBAABBA", 0.02
ROUNDS = int(os.environ.get("ROUNDS", "41"))
REPS = int(os.environ.get("REPS", "4000"))
WARMUP, ROUND_WARM = 8, 2

VIEW = fnx.Graph
NATIVE = VIEW.neighbors
_PRIVATE_MISSING = fnx._PRIVATE_MISSING
Graph = fnx.Graph
_EDGE_VIEW_GRAPH_OWNER = fnx._EDGE_VIEW_GRAPH_OWNER
_has_networkx_private_storage = fnx._has_networkx_private_storage
_GRAPH_PRIVATE_AWARE_GET_EDGE_DATA = fnx._GRAPH_PRIVATE_AWARE_GET_EDGE_DATA

_PRIVATE_ADJ_OVERRIDE = fnx._PRIVATE_ADJ_OVERRIDE
_PRIVATE_SUCC_OVERRIDE = fnx._PRIVATE_SUCC_OVERRIDE
_PRIVATE_PRED_OVERRIDE = fnx._PRIVATE_PRED_OVERRIDE
_PRIVATE_NODE_OVERRIDE = fnx._PRIVATE_NODE_OVERRIDE
NetworkXError = fnx.NetworkXError
_cached_adj_row_key_iter = fnx._cached_adj_row_key_iter
exec(open("old_neighbors_wrapper.py.txt").read())  # noqa: S102 — recovered verbatim
WRAPPED = _private_aware_graph_neighbors()  # noqa: F821


def build(module, nodes=2000, edges=8000, seed=11):
    rng = random.Random(seed)
    g = module.Graph()
    names = [f"n{i}" for i in range(nodes)]
    g.add_nodes_from((n, {"color": "r", "rank": i}) for i, n in enumerate(names))
    seen = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        g.add_edge(names[pair[0]], names[pair[1]], weight=1.0)
    return g, [(names[a], names[b]) for a, b in seen]


g_fx, edges_fx = build(fnx)
g_nx, edges_nx = build(nx)
rng = random.Random(7)
probes_fx = [edges_fx[rng.randrange(len(edges_fx))] for _ in range(REPS)]
rng2 = random.Random(7)
probes_nx = [edges_nx[rng2.randrange(len(edges_nx))] for _ in range(REPS)]
view_fx, view_nx = g_fx.edges, g_nx.edges


def wrap():
    VIEW.neighbors = WRAPPED


def unwrap():
    VIEW.neighbors = NATIVE


def noop():
    return None


def probe_fx():
    return sum(len(list(g_fx.neighbors(u))) for u, _v in probes_fx)


def probe_nx():
    return sum(len(list(g_nx.neighbors(u))) for u, _v in probes_nx)


def time_slot(fn):
    t = time.perf_counter_ns(); fn(); return time.perf_counter_ns() - t


def bootstrap_ci(values, iters=4000, seed=3):
    r = random.Random(seed); n = len(values)
    m = sorted(statistics.median(values[r.randrange(n)] for _ in range(n)) for _ in range(iters))
    return m[int(0.025 * iters)], m[int(0.975 * iters)]


def run_row(label, a_setup, a_fn, b_setup, b_fn):
    for _ in range(WARMUP):
        a_setup(); a_fn(); b_setup(); b_fn()
    ratios, na, nb = [], [], []
    for _ in range(ROUNDS):
        gc.collect(); gc.disable()
        try:
            for _ in range(ROUND_WARM):
                a_setup(); a_fn(); b_setup(); b_fn()
            a, b = [], []
            for slot in SQUARE:
                if slot == "A":
                    a_setup(); a.append(time_slot(a_fn))
                else:
                    b_setup(); b.append(time_slot(b_fn))
        finally:
            gc.enable()
        ratios.append(statistics.median(a) / statistics.median(b))
        na.append(statistics.median(a[:2]) / statistics.median(a[2:]))
        nb.append(statistics.median(b[:2]) / statistics.median(b[2:]))
    r = statistics.median(ratios); lo, hi = bootstrap_ci(ratios)
    x, y = statistics.median(na), statistics.median(nb)
    ok = abs(x - 1.0) <= NULL_BOUND and abs(y - 1.0) <= NULL_BOUND
    v = "NULL-FAILED" if not ok else ("STRADDLES-1" if lo <= 1.0 <= hi else "ADMISSIBLE")
    print(f"  {label:32s} {r:7.4f}x  CI [{lo:.4f}, {hi:.4f}]  nulls {x:.4f}/{y:.4f}  {v}")


with open(ext.__file__, "rb") as fh:
    print(f"  bench_elf_sha256={hashlib.sha256(fh.read()).hexdigest()}")
print(f"  harness=ab_neighbors_wrapper.py  same_host={platform.node()}  rch_worker=none")
print(f"  nx {nx.__version__}  loadavg {os.getloadavg()}  rounds/reps {ROUNDS}/{REPS}")

wrap(); assert probe_fx() == probe_nx()
unwrap(); assert probe_fx() == probe_nx()

print(f"\nsquare={SQUARE}")
print("  RATIO t_wrapped / t_native  (>1 means dropping the wrapper is faster)")
run_row("neighbors: wrapped -> native", wrap, probe_fx, unwrap, probe_fx)
print("  RATIO t_networkx / t_fnx    (>1 means fnx faster)")
run_row("nx vs fnx WRAPPED (before)", noop, probe_nx, wrap, probe_fx)
run_row("nx vs fnx NATIVE (after)", noop, probe_nx, unwrap, probe_fx)
run_row("CONTROL nx vs nx", noop, probe_nx, noop, probe_nx)
unwrap()
