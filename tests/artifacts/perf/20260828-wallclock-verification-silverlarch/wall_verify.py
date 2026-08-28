"""Same-invocation wall-clock verification of this session's landed claims.

Every claim I landed this session was an INSTRUCTION-COUNT claim, because
host_quiet_check refused this host continuously. It is now clear, so this re-measures the
same rows in wall clock under the protocol the Ir work could not use:

  * live networkx in the SAME invocation as fnx - not a separate process, not a recorded
    number;
  * arms INTERLEAVED inside one loop, order reversed on odd rounds (ABBA), so monotone
    drift cannot land preferentially on one arm;
  * an A/A NULL arm: a SEPARATELY BUILT fnx fixture timed through the identical call
    protocol. Timing one object against itself is blind to the ~5% spread between
    separately built fixtures, so the null uses a second graph;
  * median over rounds, and the null must sit near 1.0 for the row to be quotable.

Ir has moved opposite to wall clock in this repo before (br-r37-c1-p1tvg cut 101 Ir/call and
ran 1.27x SLOWER), so a row that fails here is a real finding, not a formality.
"""

import hashlib
import random
import statistics
import sys
import time

import networkx as nx

import franken_networkx as fnx
import franken_networkx._fnx as ext

ROUNDS = 21


def digraph(mod, n, seed=11, weighted=False):
    rng = random.Random(seed)
    g = mod.DiGraph()
    g.add_nodes_from(range(n))
    for i in range(n):
        for _ in range(4):
            j = rng.randrange(n)
            if i != j:
                if weighted:
                    g.add_edge(i, j, weight=float(rng.randint(1, 9)))
                else:
                    g.add_edge(i, j)
    return g


def undirected(mod, n, seed=7):
    rng = random.Random(seed)
    g = mod.Graph()
    g.add_nodes_from(range(n))
    for i in range(n):
        for _ in range(3):
            j = rng.randrange(n)
            if i != j:
                g.add_edge(i, j, weight=float(rng.randint(1, 9)))
    return g


def build_case(name):
    """Return (label, fnx_call, nx_call, fnx_null_call, claimed)."""
    if name == "effective_size":
        n = 200
        fg, ng, fg2 = digraph(fnx, n), digraph(nx, n), digraph(fnx, n)
        sub = list(range(0, n, 4))
        return ("effective_size(DiGraph, nodes=subset)",
                lambda: fnx.effective_size(fg, nodes=sub),
                lambda: nx.effective_size(ng, nodes=sub),
                lambda: fnx.effective_size(fg2, nodes=sub), "1068x")
    if name == "constraint":
        n = 200
        fg, ng, fg2 = digraph(fnx, n), digraph(nx, n), digraph(fnx, n)
        sub = list(range(0, n, 4))
        return ("constraint(DiGraph, nodes=subset)",
                lambda: fnx.constraint(fg, nodes=sub),
                lambda: nx.constraint(ng, nodes=sub),
                lambda: fnx.constraint(fg2, nodes=sub), "306.7x")
    if name == "greedy_color":
        n = 250
        fg, ng, fg2 = digraph(fnx, n), digraph(nx, n), digraph(fnx, n)
        return ("greedy_color(DiGraph)",
                lambda: fnx.greedy_color(fg),
                lambda: nx.greedy_color(ng),
                lambda: fnx.greedy_color(fg2), "7.512x")
    if name == "maximum_branching":
        n = 400
        fg, ng, fg2 = undirected(fnx, n), undirected(nx, n), undirected(fnx, n)
        return ("maximum_branching(Graph)",
                lambda: fnx.maximum_branching(fg),
                lambda: nx.maximum_branching(ng),
                lambda: fnx.maximum_branching(fg2), "0.849x (a LOSS)")
    raise SystemExit(name)


with open(ext.__file__, "rb") as fh:
    print(f"elf_sha256 {hashlib.sha256(fh.read()).hexdigest()[:16]}  networkx {nx.__version__}")
print(f"{'row':38} {'nx/fnx':>10} {'A/A null':>9}  claimed (Ir)")

for case in ("effective_size", "constraint", "greedy_color", "maximum_branching"):
    label, f_call, n_call, null_call, claimed = build_case(case)
    arms = {"fnx": f_call, "nx": n_call, "null": null_call}
    samples = {k: [] for k in arms}
    for r in range(ROUNDS):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for key in order:
            t = time.perf_counter()
            arms[key]()
            samples[key].append(time.perf_counter() - t)
    med = {k: statistics.median(v) for k, v in samples.items()}
    ratio = med["nx"] / med["fnx"]
    null = med["null"] / med["fnx"]
    flag = "" if 0.90 <= null <= 1.10 else "   <- NULL OUT OF BAND, row not quotable"
    print(f"{label:38} {ratio:9.3f}x {null:8.3f}   {claimed}{flag}", flush=True)
