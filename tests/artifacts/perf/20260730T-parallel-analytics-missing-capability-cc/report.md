# Parallel analytics pass — MISSING CAPABILITY vs nx 3.6.1 (cc, 2026-07-30)

Status: **measurement artifact + reusable harness.** No kernel change. The parallel Brandes
kernel already existed (`crates/fnx-algorithms/src/lib.rs`, `BRANDES_PARALLEL_THRESHOLD = 500`);
what did not exist was an end-to-end measurement of it as a *whole job* against a live NetworkX,
with build provenance and a null-gated verdict. That is what this lands.

## Why this target, and why it is not "just faster"

NetworkX 3.6.1 has three separable structural weaknesses. Interpreted-language overhead and the
per-edge attribute-dict generality tax are constant factors — real, but ordinary. The third is
different: there are operations it **cannot perform at scale at all**, and anything genuinely
parallel is one of them.

Exact all-sources centrality is the canonical case. Brandes betweenness is `|V|` independent
single-source passes — textbook embarrassingly parallel — and NetworkX cannot exploit that:

1. CPython's GIL serialises bytecode, so `threading` over the source loop yields ~1x. NetworkX
   ships no thread pool and no `n_jobs`.
2. `multiprocessing` requires pickling the graph into every worker. A dict-of-dict adjacency with
   a per-edge attribute dict is a large Python object graph: pickle round-trip plus an N-fold
   memory blowup.
3. Parallel NetworkX lives in the separate `nx-parallel` backend, not core 3.6.1, and it pays the
   same pickling cost.

"Use the other 31 cores" is not a knob a NetworkX user has. It is absent from the library, not
slow in it. The `--threads 1` row below is what makes that claim falsifiable rather than
rhetorical: it separates "left Python" from "used the cores".

## Measured — nx 3.6.1 live in the same invocation, arms interleaved

Host `thinkstation1`, AMD Ryzen Threadripper PRO 5975WX, **32 physical / 64 SMT**, Python 3.13.7.
fnx ELF SHA-256 `fe0ceb632c11d55580f69952c51a9ac1900d06eb8ee8fc66583b85895f29fd60`, built on
**rch remote worker `vmi1167313`**, profile `release` (this repo's `release-perf` only adds
`debug = "line-tables-only"` on top of `release`, so `release` is both what was measured and what
the maturin wheel ships). `NETWORKX_AUTOMATIC_BACKENDS` unset; the nx arm resolves to
`networkx.algorithms.centrality.betweenness`, the fnx arm to `franken_networkx`.

The job is one pass, identical against both modules — `read_edgelist` → `remove_self_loops` →
`connected_components` → `degree_assortativity` → `average_clustering` → `core_number` →
`pagerank` → **exact** `betweenness_centrality` → `closeness_centrality`. Graph load is included;
it is a stage fnx loses.

| graph | nx wall | fnx@32 wall | ratio | reps |
|---|--:|--:|--:|--:|
| `facebook_combined` (4039 n, 88 234 e) | 113.372 s | **0.243 s** | **467.3x** — CI [424.0, 515.3] | 12 + 12 interleaved |
| `ca-AstroPh` (18 772 n, 198 050 e) | 3043.073 s | **4.748 s** | **640.9x** — CI [558.9, 728.7] | 2 + 2 |

A real 18 772-node collaboration network: **50.7 minutes under NetworkX, 4.7 seconds under fnx.**
Dominant stages on `ca-AstroPh` are `betweenness_exact` 2180.99 s → 3.03 s (720x) and `closeness`
858.29 s → 0.68 s (1264x).

### Concurrency is measured, not asserted

Each stage records process CPU time over wall time. NetworkX sits at **1.00 on every stage of
every row** — that flat 1.00 *is* the missing capability, observed. fnx's `betweenness_exact`
`cpu/wall` tracks the pool almost linearly:

| threads | betweenness wall | betweenness cpu/wall | TOTAL wall | scaling vs 1 thread |
|--:|--:|--:|--:|--:|
| 1 | 37.785 s | 1.00 | 54.111 s | 1.00x |
| 2 | 20.584 s | 1.94 | 29.468 s | 1.84x |
| 4 | 11.486 s | 3.89 | 16.559 s | 3.29x |
| 8 | 7.254 s | 7.69 | 10.305 s | 5.21x |
| 16 | 4.287 s | 14.83 | 6.253 s | 8.81x |
| 32 | 3.027 s | 28.22 | 4.748 s | 12.48x |
| 64 | 2.869 s | 49.64 | 4.314 s | 13.17x |

### Decomposing the win — only the second row is the capability claim

| factor | ratio | what it is |
|---|--:|---|
| nx → fnx @ 1 thread | **56x** | leaving interpreted Python + the generality tax. Ordinary compiled-vs-interpreted advantage; a NetworkX user could get this from any compiled single-threaded library. |
| fnx @ 1 → fnx @ 64 threads | **12.5x** | using the machine's cores. **No NetworkX-side equivalent at any graph size.** |
| combined | **705x** | whole-job wall clock |

Scaling is near-linear to 16 threads, then bends; the last doubling (32→64) crosses into SMT
siblings rather than new cores and buys only a few percent. Size the pool to physical cores.

## Parity — the speedup is on the same answer

All scalar invariants agree on both graphs (`n_components`, `largest_cc_size`, `max_core`,
`average_clustering`, `assortativity`, self-loops removed), and the **top-10 rankings for
pagerank, betweenness and closeness match exactly** on both. Betweenness values agree to within
1 ULP rather than bit-identically: the parallel reduction replays per-source contributions in
source order, but the per-source inner accumulation differs from nx's in-place dict update by one
rounding. Rankings are unaffected.

## Where fnx does NOT win

| graph | stage | nx | fnx | ratio |
|---|---|--:|--:|--:|
| `ca-AstroPh` | `read_edgelist` | 0.721 s | 0.791 s | **0.91x** |
| `ca-AstroPh` | `remove_self_loops` | 0.004 s | 0.006 s | **0.7x** |

Reported because this is a whole-job claim. Both are stages dominated by building Python objects
for the caller, where fnx pays a conversion cost nx does not — and both are sub-second against
centrality stages measured in minutes.

## Gate verdict — UNDECIDABLE, and not tuned into a pass

Both rows are reported **UNDECIDABLE** under the fleet's corrected three-clause rule, for
different reasons, and neither threshold was relaxed to change that:

- `ca-AstroPh` — **UNDECIDABLE-NO-NULL.** The A/A null needs ≥4 reps per arm to split by parity
  and the nx arm has 2 (one pass costs ~51 min). A missing null is not a satisfied clause; the
  gate returns no verdict rather than borrowing one.
- `facebook_combined` — clauses 1 and 2 pass (effect CI [424.0, 515.3] excludes 1.0; deviation
  466.3 ≫ 2× null half-width 0.327). **Clause 3 fails: worst null median bias 0.0397 > 0.02.**
  This is a *real* arm-order effect, not imprecision. Within-replicate order alternates by
  replicate parity and the null splits on that same parity, so these nulls measure POSITION: nx
  null median 0.9631 (faster running first) and fnx null median 1.0397 (slower running second)
  independently agree that the arm going first is ~4% faster. Bias-to-effect ratio **8.52e-05** —
  a 4% position effect cannot manufacture a 467x ratio. Clause 3 is calibrated to stop a near-1.0
  claim from being position bias in disguise; here it is a true positive about the substrate and a
  false alarm about the conclusion. Closing it properly needs both arms pinned to fixed cores on a
  quiet host, which this shared 64-thread box (peer load averaged 6→208 during the run) could not
  provide.

The gate carries **no CI-straddle veto**: null CIs are telemetry, bounded by their median.
Requiring a null CI to contain 1.0 couples the verdict to the null's precision backwards, so a
tighter null — a better measurement — becomes more likely to veto its own row.
`--role selfcheck` asserts the gate discriminates in both directions: it returns UNDECIDABLE for a
no-effect pair and for a marginal 1.02x inside the null, decides a genuine 0.5x regression *as a
loss*, and does not veto a large effect on a tight null whose CI excludes 1.0.

## CHOOSER STATEMENT

**Use NetworkX 3.6.1** when the graph is small enough that the pass is already sub-second either
way (there is nothing to buy, and nx is the reference semantics); when you need nx's full API
surface, backend ecosystem, exotic node objects or heavy per-edge attribute mutation; or when you
want the implementation everyone else's numbers are quoted against.

**Use FrankenNetworkX** when the dominant stage is an exact all-sources centrality at real scale —
`ca-AstroPh`'s pass is 3043 s under nx and 4.75 s under fnx; when you run the pass more than once
(parameter sweep, temporal snapshots, CI), because a 50-minute pass is a batch job you schedule
while a 5-second pass is a question you ask interactively, and that changes which analyses you
attempt at all; and when you have more than one core, which is the load-bearing point — the 12.5x
parallel factor has no NetworkX-side equivalent at any graph size.

**Crossover rule:** pick by the *dominant stage*, not graph size. Dominated by exact betweenness /
closeness / harmonic / load / percolation centrality — the kernels fnx fans over rayon — fnx wins
by a margin that grows with core count and is unavailable to nx in principle. Dominated by
materialising Python objects into user code — the two are close and nx may edge ahead.

## Reproduce

```
python3 scripts/parallel_analytics_pass.py --role fetch     --graph-dir <dir>
python3 scripts/parallel_analytics_pass.py --role selfcheck
python3 scripts/parallel_analytics_pass.py --role driver --graph-dir <dir> --out <art> \
    --builder "<rch worker>" --profile release --plan '[
      {"engine":"both","graph":"facebook_combined","threads":32,"reps":12},
      {"engine":"fnx","graph":"ca-AstroPh","threads":1,"reps":3},
      {"engine":"both","graph":"ca-AstroPh","threads":32,"reps":2}]'
python3 scripts/parallel_analytics_report.py --study <art>/study.json --out <art>
```

Full generated detail in `analytics_pass_report.md`; per-(engine, graph, threads, rep, stage) rows
with host identity and thread count on **every** row in `rows.csv` (460 rows); raw records in
`study_facebook_12rep.json` and `study_astroph_and_sweep.json`.
