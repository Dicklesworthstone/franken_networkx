"""Balanced-square vs-incumbent A/B, usable on a contended host.

WHY THIS EXISTS. `scripts/perf_harness.py` is the sanctioned harness, and its
`require_host_wide_quiescence()` is mandatory at both `pre_setup` and
`pre_measurement`: it demands five consecutive windows in which EVERY cpu on the
box is idle. On a 64-way host shared by tens of agents that condition is
effectively unreachable — `br-r37-c1-3s8x7` recorded 25 consecutive attempts
with zero admitted, and a run of mine aborted with
``host-wide benchmark exclusivity failed at pre_setup after 300 windows,
cpu47=100.0%``. The result is a fleet that cannot produce the one artifact the
campaign accepts as a win: a vs-incumbent ratio measured live, in the same
invocation.

This substrate reaches those rows WITHOUT a host-wide gate, because it does not
try to make the host quiet — it makes the COMPARISON immune to the host being
busy:

  * Both arms run INSIDE one round, interleaved as a balanced square
    ``A B B A A B B A``. Each arm occupies the same set of slot POSITIONS, so
    any drift across the round hits both equally instead of biasing one.
  * Each arm carries its own A/A null: the same arm's first-half slots divided
    by its second-half slots, which must come out 1.0. A null is what detects
    the contention this gate was trying to exclude — so contention is caught
    per-row, after the fact, instead of being excluded up front.
  * A row whose null leaves [0.98, 1.02] is reported NULL-FAILED and its ratio
    is not a result. REFUSING is the point; see `mutation_arms_fail_aa_nulls`.

It is NOT a replacement for perf_harness.py's contract rows. It is the
substrate to use when the gate cannot be met, which is most of the time.

USAGE

    PYTHONPATH=python PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
      taskset -c 40-47 python3 scripts/balanced_square_ab.py --workload view-reads

    --workload   which registered workload set to run (see --list)
    --rounds     rounds per row (default 41)
    --reps       operations per timed slot (default 400)
    --expect-elf first 16 hex chars of the ELF you INTEND to measure; the run
                 aborts on mismatch. A bare `python3` silently loads the
                 site-packages build, which is a DIFFERENT binary — this guard
                 exists because that trap cost a full session's numbers once.

Ratio convention is t_incumbent / t_fnx, so > 1 means fnx is faster. That is
the same convention the ledgers use.

ADDING A WORKLOAD. Append to `WORKLOADS`. A workload is a callable returning
`(build, ops)` where `build(module)` constructs an equivalent graph in either
library and `ops(graph, fixture)` returns `{label: callable}`. Every op is
parity-gated against the incumbent BEFORE timing, so an arm that computes
something different fails loudly instead of producing a fast wrong number.
Include at least one row the change under test CANNOT affect, as a control.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import os
import platform
import random
import socket
import statistics
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as _fnx_ext

SQUARE = "ABBAABBA"
NULL_BOUND = 0.02


# ---------------------------------------------------------------------------
# Provenance, self-reported from INSIDE this process.
#
# Every field here exists because a ratio without it is not checkable: the
# ACTUAL observed thread count (not the requested one), host identity, CPU
# governor, runtime ISA, and an ELF SHA-256 read from the loaded module's own
# path so a harness cannot silently compare a build against itself.
# ---------------------------------------------------------------------------
def provenance() -> dict:
    elf = _fnx_ext.__file__
    with open(elf, "rb") as handle:
        elf_sha = hashlib.sha256(handle.read()).hexdigest()
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") as handle:
            governor = handle.read().strip()
    except OSError:
        governor = "unavailable"
    flags = ""
    try:
        with open("/proc/cpuinfo") as handle:
            for line in handle:
                if line.startswith("flags"):
                    flags = line
                    break
    except OSError:
        pass
    isa = [f for f in ("avx512f", "avx2", "avx", "sse4_2") if f" {f} " in flags]
    threads = "unknown"
    try:
        with open("/proc/self/status") as handle:
            for line in handle:
                if line.startswith("Threads:"):
                    threads = line.split()[1]
                    break
    except OSError:
        pass
    return {
        "host": socket.gethostname(),
        "elf": elf,
        "elf_sha256": elf_sha,
        "governor": governor,
        "runtime_isa": ",".join(isa) or "baseline",
        "observed_os_threads": threads,
        "observed_affinity_cpus": len(os.sched_getaffinity(0)),
        "python": platform.python_version(),
        "incumbent_networkx": nx.__version__,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "<unset>"),
        "loadavg_start": os.getloadavg(),
    }


# ---------------------------------------------------------------------------
# Workloads
# ---------------------------------------------------------------------------
def _simple_graph(module, nodes: int, edges: int, seed: int = 11):
    """An identically-shaped attributed simple graph in either library."""
    rng = random.Random(seed)
    graph = module.Graph()
    names = [f"n{i}" for i in range(nodes)]
    graph.add_nodes_from((n, {"color": "r", "rank": i}) for i, n in enumerate(names))
    seen: set[tuple[int, int]] = set()
    while len(seen) < edges:
        a, b = rng.randrange(nodes), rng.randrange(nodes)
        if a == b:
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            continue
        seen.add(pair)
        graph.add_edge(names[pair[0]], names[pair[1]], weight=1.0)
    return graph, (names, [(names[a], names[b]) for a, b in seen])


def workload_view_reads(reps: int):
    """Read probes on the view surface (br-r37-c1-ey6ob, br-r37-c1-ef8rt)."""

    def build(module):
        return _simple_graph(module, 2000, 8000)

    def ops(graph, fixture):
        names, edges = fixture
        # Seeded on purpose: the probe sequence must be identical in both arms
        # and reproducible across runs. This is fixture selection, not secret
        # material, so `random` is correct here and `secrets` would be wrong.
        rng = random.Random(7)
        probe_nodes = [names[rng.randrange(len(names))] for _ in range(reps)]
        probe_edges = [edges[rng.randrange(len(edges))] for _ in range(reps)]
        nodeview, edgeview = graph.nodes, graph.edges
        return {
            "n in G": lambda: sum(1 for n in probe_nodes if n in graph),
            "G.has_node(n)": lambda: sum(1 for n in probe_nodes if graph.has_node(n)),
            "n in G.nodes()": lambda: sum(1 for n in probe_nodes if n in nodeview),
            "G.nodes[n]": lambda: sum(len(nodeview[n]) for n in probe_nodes),
            "G.nodes.get(n)": lambda: sum(len(nodeview.get(n)) for n in probe_nodes),
            "(u,v) in G.edges()": lambda: sum(1 for p in probe_edges if p in edgeview),
            "G.edges[u,v]": lambda: sum(len(edgeview[u, v]) for u, v in probe_edges),
            # Control: no view lever can touch a bare node count.
            "CONTROL len(G)": lambda: sum(len(graph) for _ in range(reps)),
        }

    return build, ops


WORKLOADS = {"view-reads": workload_view_reads}


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def time_slot(fn) -> int:
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter_ns()
        fn()
        return time.perf_counter_ns() - start
    finally:
        gc.enable()


def bootstrap_ci(values, iters: int = 4000, seed: int = 3):
    rng = random.Random(seed)
    n = len(values)
    medians = sorted(
        statistics.median(values[rng.randrange(n)] for _ in range(n))
        for _ in range(iters)
    )
    return medians[int(0.025 * iters)], medians[int(0.975 * iters)]


def run_row(label: str, incumbent_fn, fnx_fn, rounds: int, warmup: int) -> dict:
    for _ in range(warmup):
        incumbent_fn()
        fnx_fn()

    ratios, null_a, null_b = [], [], []
    for _ in range(rounds):
        a_slots, b_slots = [], []
        for slot in SQUARE:
            if slot == "A":
                a_slots.append(time_slot(incumbent_fn))
            else:
                b_slots.append(time_slot(fnx_fn))
        ratios.append(statistics.median(a_slots) / statistics.median(b_slots))
        # Each arm's own first-half / second-half ratio. The square places the
        # halves symmetrically, so a null that departs from 1.0 is drift or
        # contention, not slot position.
        null_a.append(statistics.median(a_slots[:2]) / statistics.median(a_slots[2:]))
        null_b.append(statistics.median(b_slots[:2]) / statistics.median(b_slots[2:]))

    ratio = statistics.median(ratios)
    low, high = bootstrap_ci(ratios)
    n_a, n_b = statistics.median(null_a), statistics.median(null_b)
    nulls_ok = abs(n_a - 1.0) <= NULL_BOUND and abs(n_b - 1.0) <= NULL_BOUND
    if not nulls_ok:
        verdict = "NULL-FAILED"
    elif low <= 1.0 <= high:
        verdict = "STRADDLES-1"
    else:
        verdict = "ADMISSIBLE"
    return {
        "label": label,
        "ratio": ratio,
        "ci": (low, high),
        "null_incumbent": n_a,
        "null_fnx": n_b,
        "verdict": verdict,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", default="view-reads")
    parser.add_argument("--rounds", type=int, default=41)
    parser.add_argument("--reps", type=int, default=400)
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--expect-elf", default=os.environ.get("EXPECT_ELF_SHA"))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.list:
        for name in WORKLOADS:
            print(name)
        return 0
    if args.workload not in WORKLOADS:
        raise SystemExit(f"unknown workload {args.workload!r}; try --list")

    prov = provenance()
    print("PROVENANCE (self-reported from inside the process)")
    for key, value in prov.items():
        print(f"  {key:24s} {value}")
    print(f"  {'rounds/warmup/reps':24s} {args.rounds}/{args.warmup}/{args.reps}")

    # A bare `python3` loads the site-packages extension, which is a DIFFERENT
    # build. Refuse rather than measure the wrong binary.
    if args.expect_elf and not prov["elf_sha256"].startswith(args.expect_elf):
        raise SystemExit(
            f"ELF MISMATCH: loaded {prov['elf_sha256'][:16]} from {prov['elf']}, "
            f"expected {args.expect_elf}"
        )

    build, ops = WORKLOADS[args.workload](args.reps)
    g_nx, fx_nx = build(nx)
    g_fx, fx_fx = build(fnx)
    if g_nx.number_of_nodes() != g_fx.number_of_nodes():
        raise SystemExit("fixture mismatch: node counts differ")
    if g_nx.number_of_edges() != g_fx.number_of_edges():
        raise SystemExit("fixture mismatch: edge counts differ")

    ops_nx = ops(g_nx, fx_nx)
    ops_fx = ops(g_fx, fx_fx)

    # Parity gate BEFORE timing: an arm that computes something different must
    # fail loudly, not produce a fast wrong number.
    for name in ops_nx:
        got_nx, got_fx = ops_nx[name](), ops_fx[name]()
        if got_nx != got_fx:
            raise SystemExit(f"PARITY MISMATCH on {name}: {got_nx} != {got_fx}")

    print(
        f"\nRATIO = t_networkx / t_fnx   (>1 means fnx faster)   square={SQUARE}"
        f"   null bound +/-{NULL_BOUND}"
    )
    admitted = 0
    for name in ops_nx:
        row = run_row(name, ops_nx[name], ops_fx[name], args.rounds, args.warmup)
        low, high = row["ci"]
        print(
            f"  {name:22s} {row['ratio']:7.4f}x  CI [{low:.4f}, {high:.4f}]  "
            f"nulls {row['null_incumbent']:.4f}/{row['null_fnx']:.4f}  {row['verdict']}"
        )
        admitted += row["verdict"] == "ADMISSIBLE"

    print(f"\n  loadavg_end              {os.getloadavg()}")
    print(f"  admitted rows            {admitted}/{len(ops_nx)}")
    if admitted == 0:
        print("  NO ADMISSIBLE ROW — do not quote any number from this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
