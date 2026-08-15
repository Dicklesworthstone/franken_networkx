"""Rank the cheap public methods of `Graph` against live networkx.

`len(G)` turned out to be 0.41x purely because of a Python wrapper on a native
slot, and 30 entries on `_fnx.Graph` are still Python functions. This measures
the cheap ones — where a per-call frame cannot be amortised — and prints, next
to each ratio, whether that entry is a Python frame or a native slot, so the
ranking and the explanation arrive together.

Balanced ABBAABBA square with per-arm A/A nulls, same design as
scripts/balanced_square_ab.py. Every row is parity-gated before it is timed.
"""

import gc
import hashlib
import os
import platform
import random
import statistics
import sys
import time

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as ext

SQUARE = "ABBAABBA"
NULL_BOUND = 0.02
ROUNDS = int(os.environ.get("ROUNDS", "41"))
REPS = int(os.environ.get("REPS", "400"))
WARMUP = 8


def build(module, nodes=2000, edges=8000, seed=11, multi=False):
    rng = random.Random(seed)
    graph = module.MultiGraph() if multi else module.Graph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from((n, {"color": "r", "rank": i}) for i, n in enumerate(names))
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
    return graph, names


def time_slot(fn):
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        fn()
        return time.perf_counter_ns() - start
    finally:
        gc.enable()


def bootstrap_ci(values, iters=4000, seed=3):
    rng = random.Random(seed)
    n = len(values)
    medians = sorted(
        statistics.median(values[rng.randrange(n)] for _ in range(n))
        for _ in range(iters)
    )
    return medians[int(0.025 * iters)], medians[int(0.975 * iters)]


def run_row(label, kind, a_fn, b_fn):
    for _ in range(WARMUP):
        a_fn()
        b_fn()
    ratios, null_a, null_b = [], [], []
    for _ in range(ROUNDS):
        a_slots, b_slots = [], []
        for slot in SQUARE:
            (a_slots if slot == "A" else b_slots).append(
                time_slot(a_fn if slot == "A" else b_fn)
            )
        ratios.append(statistics.median(a_slots) / statistics.median(b_slots))
        null_a.append(statistics.median(a_slots[:2]) / statistics.median(a_slots[2:]))
        null_b.append(statistics.median(b_slots[:2]) / statistics.median(b_slots[2:]))
    ratio = statistics.median(ratios)
    low, high = bootstrap_ci(ratios)
    n_a, n_b = statistics.median(null_a), statistics.median(null_b)
    ok = abs(n_a - 1.0) <= NULL_BOUND and abs(n_b - 1.0) <= NULL_BOUND
    verdict = (
        "NULL-FAILED" if not ok else ("STRADDLES-1" if low <= 1.0 <= high else "ADMISSIBLE")
    )
    print(
        f"  {label:26s} {kind:14s} {ratio:7.4f}x  CI [{low:.4f}, {high:.4f}]  "
        f"nulls {n_a:.4f}/{n_b:.4f}  {verdict}"
    )


def entry_kind(name):
    value = vars(ext.Graph).get(name)
    if value is None:
        return "inherited"
    return "PYTHON-FRAME" if type(value).__name__ == "function" else "native"


def main():
    with open(ext.__file__, "rb") as fh:
        elf_sha = hashlib.sha256(fh.read()).hexdigest()
    print("PROVENANCE (self-reported from inside the process)")
    print(f"  host {platform.node()}   bench_elf_sha256={elf_sha}")
    print(f"  networkx {nx.__version__}   python {platform.python_version()}")
    print(f"  affinity {len(os.sched_getaffinity(0))}   loadavg {os.getloadavg()}")
    print(f"  rounds/reps {ROUNDS}/{REPS}")

    g_fx, names_fx = build(fnx)
    g_nx, names_nx = build(nx)
    mg_fx, _ = build(fnx, multi=True)
    mg_nx, _ = build(nx, multi=True)
    rng = random.Random(7)
    probes = [rng.randrange(len(names_fx)) for _ in range(REPS)]

    def view_ops(graph, mgraph, names):
        picks = [names[i] for i in probes]
        adj = graph.adj
        medges = mgraph.edges
        madj = mgraph.adj
        pairs = [(names[i], n) for i in probes for n in list(graph.neighbors(names[i]))[:1]]
        return {
            "u in G.adj": lambda: sum(1 for n in picks if n in adj),
            "G.adj[u]": lambda: sum(len(adj[n]) for n in picks),
            "len(MG.edges)": lambda: sum(len(medges) for _ in range(REPS)),
            "(u,v) in MG.edges": lambda: sum(1 for p in pairs if p in medges),
            "u in MG.adj": lambda: sum(1 for n in picks if n in madj),
            "list(G.nodes(data))": lambda: sum(
                len(list(graph.nodes(data=True))) for _ in range(2)
            ),
            "iter G.edges(data)": lambda: sum(
                1 for _ in range(2) for _e in graph.edges(data=True)
            ),
            "iter MG.edges(keys)": lambda: sum(
                1 for _ in range(2) for _e in mgraph.edges(keys=True)
            ),
            "G.adj[u][v]": lambda: sum(
                len(adj[u][v]) for u, v in pairs
            ),
            "len(G.adj)": lambda: sum(len(adj) for _ in range(REPS)),
            "G.degree(n) view": lambda: sum(graph.degree[n] for n in picks),
        }

    def ops(graph, names):
        picks = [names[i] for i in probes]
        return {
            "number_of_edges()": lambda: sum(
                graph.number_of_edges() for _ in range(REPS)
            ),
            "number_of_nodes()": lambda: sum(
                graph.number_of_nodes() for _ in range(REPS)
            ),
            "order()": lambda: sum(graph.order() for _ in range(REPS)),
            "size()": lambda: sum(graph.size() for _ in range(REPS)),
            "has_node(n)": lambda: sum(1 for n in picks if graph.has_node(n)),
            "degree(n)": lambda: sum(graph.degree(n) for n in picks),
            "list(neighbors(n))": lambda: sum(len(list(graph.neighbors(n))) for n in picks),
            "G[n]": lambda: sum(len(graph[n]) for n in picks),
            "is_directed()": lambda: sum(1 for _ in range(REPS) if graph.is_directed()),
        }

    ops_fx, ops_nx = ops(g_fx, names_fx), ops(g_nx, names_nx)
    ops_fx.update(view_ops(g_fx, mg_fx, names_fx))
    ops_nx.update(view_ops(g_nx, mg_nx, names_nx))
    for name in ops_nx:
        got_nx, got_fx = ops_nx[name](), ops_fx[name]()
        if got_nx != got_fx:
            raise SystemExit(f"PARITY MISMATCH on {name}: nx {got_nx} fnx {got_fx}")

    print(f"\nRATIO = t_networkx / t_fnx  (>1 means fnx faster)  square={SQUARE}")
    for name in ops_nx:
        attr = name.split("(")[0].replace("list ", "").strip()
        kind = "view" if any(t in name for t in (".adj", "MG.")) else entry_kind(
            "__getitem__" if name == "G[n]" else attr
        )
        run_row(name, kind, ops_nx[name], ops_fx[name])
    print(f"  loadavg_end {os.getloadavg()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
