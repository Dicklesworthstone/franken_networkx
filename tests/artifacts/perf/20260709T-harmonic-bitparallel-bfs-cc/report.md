# Bit-parallel multi-source reverse BFS for `harmonic_centrality` — 2.4×–17.6× vs ORIG

**Agent:** cc_nx · **Date:** 2026-07-09 · **Crate:** `fnx-algorithms`
**Kernel:** all-pairs unweighted reverse BFS behind `harmonic_centrality` (+ `_directed`).
**Base:** `8e03ddd1d` · **Bead:** `br-r37-c1-7d8ps` (under `br-r37-c1-04z53`)

## Why this seam

Second sibling named by the bit-parallel BFS ledger (aspl `710cfc9db` 3.65×,
closeness `d82aba24e` 14.29×). Ledger-grepped `docs/NEGATIVE_EVIDENCE.md`,
`docs/NEGATIVE_EVIDENCE_cc.md`, `docs/progress/perf-negative-results.md`: **no
prior rejection**. The only harmonic entries concern the *weighted*
`harmonic(distance)` delegation path (0.95–0.96× neutral), a different function.

### Profile first (ranked hotspots, ORIG `harmonic_centrality/complete/100`)

`perf record -g`, pinned:

| % | symbol |
|---|---|
| 70.51% | `fnx_algorithms::harmonic_source` (the per-source BFS) |
| 7.70% | `IndexMap::get_index_of::<str>` (the string `reverse_adjacency` build) |
| 2.39% + 2.14% + 1.52% | `malloc_consolidate` / `_int_malloc` / `_int_free_chunk` |
| 2.03% | `fnx_algorithms::harmonic_centrality` |

The lever attacks ranked #1 (bit-parallel traversal) and ranked #2 + the malloc
churn (integer CSR instead of the string-keyed, per-node-`Vec` reverse adjacency).

## The transform

`ReachSink` generalises the closeness kernel so both centralities share one
traversal. The kernel guarantees `reach` is called **exactly once per
(source, node) first-reach event**, in **ascending level order**, with a value
derived **once per level**:

- `ClosenessSink`: `LevelValue = usize` → `sum_dist[s] += L`.
- `HarmonicSink`: `LevelValue = f64` → `harmonic[s] += 1.0/(L as f64)`.

Hoisting `1/L` to once-per-level (not once-per-event) keeps a division off the
`O(n²)` attribution path; the `O(|E|)` edge loop stays pure word AND/OR.

## Byte-identical to the ORIG kernel — and why the float order is safe

`harmonic_source` adds `1.0/(d as f64)` once per node it pops at distance `d`,
and a BFS pops in **non-decreasing** `d`. So its addition sequence is `1/1`
repeated `c(1)` times, then `1/2` repeated `c(2)` times, and so on. The kernel
reports first-reach events in ascending level order, and **every addend within a
level is the identical value `1/L`**, so permuting events inside a level cannot
change the result. `HarmonicSink` therefore replays exactly the original `f64`
addition sequence.

**This is a real constraint, not a formality.** The reassociated shortcut
`h += count * (1/L)` differs in bits on **88/100** sources of `grid(10,10)` and
**476/484** of `grid(22,22)`. It is *indistinguishable* on `complete(n)`, where
every node sits at distance 1. A test suite of complete graphs only would have
silently accepted the wrong implementation — which is why grids are in both the
tests and the bench. The `ReachSink` API also makes the shortcut inexpressible:
`reach` receives one per-level constant and can only accumulate it.

## PRE-EXISTING: fnx harmonic differs from networkx in the last ULP

Found while writing the end-to-end check, and **not caused by this change**:

| graph | path taken | fnx vs networkx | fnx vs pop-order reference |
|---|---|---|---|
| `path-64` | bit-parallel (new) | 51/64 mismatched | **0/64** |
| `path-600` | ORIG rayon fallback (**untouched**) | 490/600 mismatched | **0/600** |

NetworkX accumulates `centrality[u] += 1 / d_uv` while iterating
`for v in sources: for u, d_uv in dist.items()`, i.e. in **source/dict order with
mixed distances** — not grouped by level. fnx (ORIG *and* new) groups by level,
so the two sum the same multiset of `1/d` in different orders and land one ULP
apart. The untouched `n ≥ 500` fallback shows the same divergence, proving it
predates this work. Filed as its own bead; matching nx bit-for-bit would require
reproducing nx's source-order accumulation, which is incompatible with any
level-grouped (and hence any bit-parallel) traversal.

Closeness was unaffected by this class of issue because its score derives from
exact **integers**.

## Scope: sequential path only (`n < 500`)

Gated on the pre-existing `CENTRALITY_PARALLEL_THRESHOLD` (500) — exactly the
already-sequential branch. `n ≥ 500` keeps the per-source rayon path unchanged.

## Measurement

Two locally built bench binaries, **distinct md5**, reproducible (rebuild after
the incident below produced identical md5s): ORIG from a detached `git worktree`
at HEAD `8e03ddd1d` **with this commit's bench file copied in** (so both sides
have the harmonic bench and only the kernel differs); NEW from the working tree.

```
taskset -c 25 <bench> --bench harmonic_centrality \
  --sample-size 100 --measurement-time 2.0 --warm-up-time 0.8 --noplot
```

**14 alternating ORIG/NEW trials**, same machine, same core (SMT sibling checked).
Ratios are computed **paired per trial**, so contention — which affects both sides
in expectation — cancels; the bootstrap CI is over 4000 resamples of the paired
median.

| bench | median ratio | bootstrap 95% CI | min/min | clean cv% ORIG/NEW |
|---|---|---|---|---|
| `complete/20`  | 4.84× | [4.52×, 5.30×] | 5.22× | 3.96 / 5.18 |
| `complete/50`  | 10.41× | [9.48×, 11.18×] | 9.92× | 2.79 / 2.52 |
| `complete/100` | **17.60×** | [15.92×, 21.67×] | 18.26× | 4.05 / 3.07 |
| `grid/100`     | 3.27× | [3.01×, 3.44×] | 3.03× | 5.33 / 5.02 |
| `grid/400`     | **2.41×** | [2.11×, 2.80×] | 2.05× | 7.88 / 2.19 |

`clean cv%` is over the 5 fastest trials per side (contention only *adds* time),
applied symmetrically. Raw all-trial cv was 12–30% because a peer agent was
running `pipeline_bench`/`fp-bench` and a `rustc` storm throughout (load 24–68 on
64 cores); `grid/400` ORIG stays at 7.88% even on the clean subset. The paired
bootstrap CI is the trustworthy statistic here, and every bench wins on its lower
bound. Grids (high diameter, many levels, few sources retired per traversal) are
the honest worst case at ~2.1–3.0×; `complete` (diameter 1) is the best case.

### Two measurement incidents worth recording

1. **`sbh` reaped the bench binaries mid-A/B.** The disk-pressure daemon runs in
   `enforce` mode; `/` was at 90% ("orange"), and it freed 2.94 GB / 118
   deletions in one hour, category `tmp`. Both `CARGO_TARGET_DIR`s under
   `/data/tmp/...` were emptied *during* an A/B run, so ORIG silently lost 4 of
   11 trials (`N=7` vs `N=11`) and the interleaving broke. Fixed with
   `.sbh-protect` marker files (the mechanism that protects
   `/data/tmp/cargo-target`) plus copying both binaries into a protected dir
   before benching. **A vanishing binary looks exactly like a slow trial in
   aggregate statistics.** Always assert equal trial counts per side.
2. **`maturin develop` failed but the wrapper reported success**, because its
   temp dir under `/data/tmp` was reaped too and the failure was masked by a
   pipe to `tail`. The `.so` was then 40 minutes stale — every Python parity
   number would have described the *old* kernel. Re-run with
   `TMPDIR=<protected>`; always check `_fnx.__file__` mtime before trusting a
   Python bench or parity run.

Criterion also switches units (`µs` ↔ `ms`) *within the same bench id* between
runs; a parser that reads only the number silently mixes 1000× values.

### No regression on untouched benches

`closeness_centrality` (which now shares the refactored kernel) and the other
families are covered by `cargo test` and the closeness proof; the `ReachSink`
generalisation is monomorphised per `(W, Sink)`, so the closeness path emits the
same code it did before.

## Correctness

- **7 new differential/property tests** (`bitpar_harmonic_tests`) against an
  independent per-source BFS over the string API that adds `1.0/(d as f64)` in
  pop order, compared with `f64::to_bits`. Covers lane widths W=1..8, `path(300)`
  (a long harmonic tail, the strongest float-order probe), grids, complete,
  disconnected/isolated, self-loops, the directed predecessor convention
  (out-star / cycle-70 / DAG), the `n ≥ 500` rayon fallback, and the multi-batch
  (`s0 > 0`) kernel loop driven directly at n=600.
- **Mutation-verified**: dropping the lane offset (`s0 + lane*64 + tz` →
  `s0 + tz`) fails exactly the 3 tests exercising W>1, and no others.
- `cargo test -p fnx-algorithms`: **909 passed, 0 failed** (902 + 7 new).
- `pytest -k harmonic`: 277 passed. `-k "closeness or centrality or harmonic"`:
  2620 passed, 0 failed. (The lone XPASS/XFAIL flip is
  `test_hits_structural_invariants[star-5]`, documented scipy `svds`
  non-determinism, unrelated.)
- `cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: exit 0.
  `cargo fmt --check`: clean. `ubs`: exit 0, **0 critical**.

## Witness semantics

As with closeness: `nodes_touched` (total reach) is identical to the per-source
path; `edges_scanned`/`queue_peak` report the work this kernel actually does (one
scan serves up to `W*64` sources). The witness is never compared in
`fnx-conformance` (only recorded) and is dropped by the Python binding.

## Next

The `n ≥ 500` parallel sizes still need the chunked-parallel design (rayon over
source *chunks*, bit-parallel within each chunk) to beat the per-source rayon
path — still deferred, still untried. `betweenness_centrality` (Brandes) shares
the forward-BFS shape but needs `sigma`/predecessor DAGs, which do not reduce to
an order-independent per-event accumulate.
