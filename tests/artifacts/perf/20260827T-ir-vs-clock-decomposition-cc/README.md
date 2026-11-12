# Which remaining losses have REMOVABLE WORK, and which are crossing-bound (br-r37-c1-irclock)

**Verdict: the read surface is largely converged at the INSTRUCTION level. Three
rows execute networkx's instruction count or better and still lose on the clock —
those are crossing-bound and cannot be fixed by removing work.**

Wall-time on this host ranged loadavg 12-95 during this cycle, so ratios were
grounded in instruction counts (load-independent) and read against the clock
numbers measured earlier at low load.

Method per `20260827T-callgrind-blas-confound-cc`: `OPENBLAS_NUM_THREADS=1`
(mandatory — only fnx pulls the spinning BLAS thread, so leaving it on biases
AGAINST fnx by ~41%), and each library differenced against a zero-work run of
ITSELF, which cancels import, interpreter startup and graph construction.
12,000 calls per cell, V=800 E=3200.

## The table

    op                        nx Ir/call  fnx Ir/call   fnx/nx   wall-clock
    MultiGraph iter_row           1097.6      3031.9     2.76x      0.30x
    DiGraph    keys_row           1456.0      2974.8     2.04x      0.48x
    MultiGraph keys_row           1681.3      3144.3     1.87x      0.46x
    MultiGraph len_row             947.9      1525.9     1.61x      0.41x
    DiGraph    iter_row           1169.5      1855.1     1.59x     ~0.68x
    MultiGraph list_keys          7946.8     10673.2     1.34x      0.58x
    MultiGraph neighbors          1408.4      1366.1     0.97x      0.89x
    MultiGraph has_edge           1383.4      1341.9     0.97x      0.95x
    MultiGraph getitem            2431.3      2456.5     1.01x      0.87x
    MultiGraph degree_n           9455.2      3195.1     0.34x      fnx wins

## Reading the two columns TOGETHER is the point

An Ir ratio near 1.0 with a clock ratio below 1.0 means fnx does the SAME AMOUNT
OF WORK and is still slower. The difference is per-crossing cost — PyO3 boundary,
cache and branch behaviour — which callgrind's Ir does not price. Removing
Python-level or instruction-level work cannot recover it.

  - CROSSING-BOUND, do not attack by shaving work:
      neighbors  0.97x Ir / 0.89x clock
      has_edge   0.97x Ir / 0.95x clock
      getitem    1.01x Ir / 0.87x clock
    These three are already at instruction parity. `20260827T-graph-neighbors-
    headroom-cc` reached the same conclusion for `neighbors` from the clock side
    (40ns above a 72.1ns crossing floor); the instruction count now confirms it
    independently — the 40ns is not work.

  - fnx ALREADY WINS ON WORK: degree_n at 0.34x Ir, a third of networkx's
    instructions. Nothing to do.

  - REAL INSTRUCTION HEADROOM, but already explained:
      iter_row 2.76x, keys_row 1.87-2.04x, len_row 1.51-1.61x
    These are the cache-validated view paths. The excess instructions are the
    `(nodes_seq, edges_seq)` token plus the snapshot compare — see
    `20260827T-multigraph-row-iter-token-cc`. The obvious lever there (one
    combined revision accessor) was BUILT AND REFUTED in br-r37-c1-revtoken: it
    saved 3.5-6.4ns, about 3 percent, because per-call crossing overhead is
    largely fixed and the tuple allocation dominates.

  - list_keys is the trap: WORST clock ratio of the keys rows (0.58x) but the
    LEAST instruction headroom (1.34x). Picking a lever by clock ranking alone
    would have sent work here, where at most a third of the gap is removable.

## Consequence for lever selection

Of ten rows measured, none is both (a) a significant clock loss and (b) holding
significant removable instruction work that has not already been explained and
attacked. The remaining losses are either crossing-bound or token-bound with a
refuted fix.

That is a convergence statement, not a claim that the surface is optimal: it says
the next real gain has to come from REDUCING THE NUMBER OF CROSSINGS or changing
what a view returns, not from making the Python or Rust side of an existing
crossing cheaper.

## Provenance

    bench_elf_sha256=5ebd66b00b74898d61ce9af11022b013a7bd265fc26aa30690bc9f1bdc8a2ef8
    valgrind 3.25.1; cg_survey.py committed alongside
