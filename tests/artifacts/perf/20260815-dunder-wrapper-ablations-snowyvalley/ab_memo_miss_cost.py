"""What does a memo MISS cost? (br-r37-c1-6n9vm retry predicate)

An absent exact-`str` key now pays a set probe BEFORE the canonical path that
still has to answer. There is no second build to compare against, so the two
arms are two key TYPES in one invocation on one ELF:

  incumbent = a `str` SUBCLASS, which is gated OUT of the memo and therefore
              takes the canonical path alone
  candidate = an exact `str`, which pays the set probe and then the same
              canonical path

Both are absent, both canonicalise to the same characters. The gap is the memo
probe on a miss. CAVEAT stated rather than hidden: a subclass is not byte-for-
byte the same canonical branch as an exact `str`, so this BOUNDS the cost rather
than isolating it perfectly.
"""
import gc, hashlib, os, platform, random, statistics, time
import franken_networkx as fnx
import franken_networkx._fnx as ext

SQUARE, NULL_BOUND = "ABBAABBA", 0.02
ROUNDS, REPS, WARMUP = int(os.environ.get("ROUNDS", "61")), 400, 8


class SubStr(str):
    pass


g = fnx.Graph()
names = [f"n{i}" for i in range(2000)]
g.add_nodes_from(names)
rng = random.Random(11)
for _ in range(8000):
    g.add_edge(names[rng.randrange(2000)], names[rng.randrange(2000)])

absent_exact = [f"absent{i}" for i in range(REPS)]
absent_sub = [SubStr(s) for s in absent_exact]
present = [names[i % 2000] for i in range(REPS)]
for n in present:            # populate the memo, as a real workload would
    assert g.has_node(n)
assert not any(g.has_node(k) for k in absent_exact)
assert not any(g.has_node(k) for k in absent_sub)


def probe_exact():
    return sum(1 for k in absent_exact if g.has_node(k))


def probe_sub():
    return sum(1 for k in absent_sub if g.has_node(k))


def time_slot(fn):
    gc.collect(); gc.disable()
    try:
        t = time.perf_counter_ns(); fn(); return time.perf_counter_ns() - t
    finally:
        gc.enable()


def bootstrap_ci(values, iters=4000, seed=3):
    r = random.Random(seed); n = len(values)
    m = sorted(statistics.median(values[r.randrange(n)] for _ in range(n)) for _ in range(iters))
    return m[int(0.025 * iters)], m[int(0.975 * iters)]


def run_row(label, a_fn, b_fn):
    for _ in range(WARMUP):
        a_fn(); b_fn()
    ratios, na, nb = [], [], []
    for _ in range(ROUNDS):
        a, b = [], []
        for slot in SQUARE:
            (a if slot == "A" else b).append(time_slot(a_fn if slot == "A" else b_fn))
        ratios.append(statistics.median(a) / statistics.median(b))
        na.append(statistics.median(a[:2]) / statistics.median(a[2:]))
        nb.append(statistics.median(b[:2]) / statistics.median(b[2:]))
    r = statistics.median(ratios); lo, hi = bootstrap_ci(ratios)
    x, y = statistics.median(na), statistics.median(nb)
    ok = abs(x - 1.0) <= NULL_BOUND and abs(y - 1.0) <= NULL_BOUND
    v = "NULL-FAILED" if not ok else ("STRADDLES-1" if lo <= 1.0 <= hi else "ADMISSIBLE")
    print(f"  {label:34s} {r:7.4f}x  CI [{lo:.4f}, {hi:.4f}]  nulls {x:.4f}/{y:.4f}  {v}")


with open(ext.__file__, "rb") as fh:
    print(f"  bench_elf_sha256={hashlib.sha256(fh.read()).hexdigest()}")
print(f"  host {platform.node()}  loadavg {os.getloadavg()}  rounds/reps {ROUNDS}/{REPS}")
print("\n  RATIO t_subclass(no memo) / t_exact(memo miss)  (<1 means the miss costs)")
run_row("absent key: no-memo -> memo miss", probe_sub, probe_exact)
run_row("CONTROL subclass vs subclass", probe_sub, probe_sub)
