# Bit-parallel multi-source reverse BFS for `closeness_centrality` — up to 14.3× vs ORIG

**Agent:** cc_nx · **Date:** 2026-07-09 · **Crate:** `fnx-algorithms`
**Kernel:** all-pairs unweighted reverse BFS behind `closeness_centrality`
(+ `_directed`).
**Base:** `2fbc34d84` · **Bead:** `br-r37-c1-04z53` (no-gaps epic)

## Why this seam

Direct execution of the **NEXT SIBLING** named by the landed bit-parallel BFS
ledger entry (`docs/NEGATIVE_EVIDENCE.md`, commit `710cfc9db`,
`average_shortest_path_length` grid/400 3.65×):

> NEXT SIBLING: `closeness_centrality` (benched on complete(20/50/100), all
> n<500 SEQUENTIAL, diameter-1 = bit-parallel's BEST case; prototype ~11-17×) —
> needs per-source `(reached_j, sum_dist_j)` attribution (iterate set bits of
> `next[w]` per level, cheap on low-diameter).

Ledger-grepped `docs/NEGATIVE_EVIDENCE.md`, `docs/NEGATIVE_EVIDENCE_cc.md`,
`docs/progress/perf-negative-results.md` first: **no prior rejection** of
bit-parallel closeness. (The existing closeness entries are Python-vs-networkx
wins — a different game from per-crate `cargo bench` vs the ORIG Rust kernel.)

## The transform

Same machinery as the distance-sum kernel (`BitParBfsScratch<W>`,
`build_u32_csr`), but closeness needs a result **per source** —
`(reached_s, sum_dist_s)` — not one global sum.

- Bit `j` of each node's `[u64; W]` column = "source `s0+j` has reached me".
  One contiguous edge scan advances up to `W*64` sources; traversals collapse
  from `n` to `ceil(n/(W*64))`. For `n < 500` that is always exactly **one** batch.
- **Per-source attribution:** walk the SET BITS of each newly-reached node's
  column once per level. Bit `j` set in `next[w]` at level `L` ⇒ source `s0+j`
  first reached `w` at distance `L`, crediting `reached[s]+=1, sum_dist[s]+=L`.
- **The decisive sub-lever, carried over:** that bit-walk lives in the
  once-per-level deferred pass, **never in the `O(|E|)` edge loop**, which stays
  pure word AND/OR plus a cheap `any != 0` bail. Total bit-iterations over a
  whole run = number of reachable ordered pairs (≤ n²).
- **Second, independent win:** `GraphView::in_neighbors_indices` (new) exposes
  the integer reverse-adjacency row — `Graph → neighbors_indices`,
  `DiGraph → predecessors_indices`. These are the *same* `adj_indices` /
  `pred_indices` rows that `neighbors_iter` / `predecessors_iter` map to names,
  so the CSR is the identical reverse adjacency, and the fast path skips the
  `O(n·deg)` string-hash `reverse_adjacency` build (`get_node_index` per
  neighbour) that the per-source path pays before it even starts traversing.

## Byte-identical (not an approximation)

`reached` and `sum_dist` are **exact integers**, and both the bit-parallel and
per-source paths now feed them into one shared
`closeness_score(reached, sum_dist, n)` — literally the same expression, so the
`f64` is bit-identical by construction, whatever the lane width or batch order.
NX's `(reached-1)/sum_dist`, rescaled by `(reached-1)/(n-1)`, is untouched.

## Scope: sequential path only (`n < 500`)

Gated on the pre-existing `CENTRALITY_PARALLEL_THRESHOLD` (500) — exactly the
branch that was already sequential. `n ≥ 500` keeps the per-source rayon path
**unchanged (no regression)**, for the reason the aspl ship recorded: on a
many-core host, per-source embarrassing parallelism beats one wide sequential
sweep. Beating the parallel sizes needs a chunked-parallel design (rayon over
source-chunks, bit-parallel within each chunk) — still deferred.

## Measurement (criterion, `--profile release`)

Two locally built bench binaries, **distinct md5**: ORIG from a detached
`git worktree` at HEAD `2fbc34d84` (working tree never mutated — a concurrent
agent is active in this checkout), NEW from the working tree.

```
taskset -c 28 <bench> --bench closeness_centrality \
  --sample-size 100 --measurement-time 3.0 --warm-up-time 1.0 --noplot
```

5 alternating ORIG/NEW trials, same machine, same core, back-to-back.

| bench | ORIG median | NEW median | median | min/min | worst-case | cv% ORIG / NEW |
|---|---|---|---|---|---|---|
| `complete/20`  | 12.994 µs | 2.515 µs | **5.17×** | 5.16× | 4.74× | 6.65 / 3.94 |
| `complete/50`  | 117.900 µs | 12.831 µs | **9.19×** | 9.13× | 8.65× | 2.60 / 2.01 |
| `complete/100` | 811.950 µs | 56.807 µs | **14.29×** | 14.04× | 13.34× | 2.72 / 1.97 |

"worst-case" = ORIG's fastest trial vs NEW's slowest. Win scales with `n` at
fixed (diameter-1) density, as the lever predicts: more sources per traversal.

**Measurement trap found and fixed (worth recording).** The first A/B pinned to
core 62, whose **SMT sibling (core 30) was busy** with a concurrent agent's
`rustc`. NEW `complete/100` swung 70.8 µs → 54.3 µs across trials (30%) while
ORIG stayed within 0.9% — the fast kernel is short enough that sibling
contention dominates it. Repinned to core 28 (sibling 60 idle): every cv < 4%.
**Always check `thread_siblings_list` of the pinned core, not just its idle%.**

### No regression on untouched benches (same protocol)

| bench | ORIG | NEW |
|---|---|---|
| `average_shortest_path_length/grid/400` | 437.54 µs | 407.66 µs |
| `degree_centrality/path/{50,100,500}` | 3.28 / 5.89 / 29.11 µs | 2.85 / 6.38 / 30.56 µs |
| `betweenness_centrality/complete/50` | 159.57 µs | 154.93 µs |

All within run-to-run noise; the added `GraphView` method is defaulted and
statically dispatched, and the hoisted `CENTRALITY_PARALLEL_THRESHOLD` is the
same value both call sites already used.

## Correctness

- **7 new differential/property tests** (`bitpar_closeness_tests`). Reference is
  an *independent* per-source reverse BFS over the string API
  (`VecDeque`/`HashMap`), spelling NX's formula out longhand — it shares no code
  with the kernel. Scores compared with `f64::to_bits`. Covers lane widths
  W=1..8, diameters 1..n-1, disconnected/isolated, self-loops, the directed
  predecessor convention (out-star / cycle n=70 / DAG), the `n ≥ 500` rayon
  fallback, and the multi-batch (`s0 > 0`) kernel loop driven directly at n=600
  — a path production never reaches, since `n < 500` ⇒ one batch.
- **Mutation-verified (the tests can fail).** Dropping the lane offset
  (`s0 + lane*64 + tz` → `s0 + tz`) fails exactly the 3 tests that exercise W>1,
  and no others. Pointing `DiGraph::in_neighbors_indices` at `successors_indices`
  fails exactly the directed test, and no others (undirected graphs cannot
  distinguish in- from out-adjacency).
- `cargo test -p fnx-algorithms`: **902 passed, 0 failed** (895 + 7 new);
  `centrality_perf_isomorphism`: 2 passed.
- **Python vs real networkx, byte-exact** (compared as float hex):
  27 case families / **1521 values, 0 mismatches** — complete{1,2,5,20,50,100},
  path{2,64,65,200}, disconnected, self-loop, directed out-star / cycle-70 / DAG,
  and 12 seeded random directed+undirected graphs.
- `pytest -k "closeness or centrality or harmonic"`: **2620 passed**, 78 skipped,
  1 xpassed, **0 failed**.
- `cargo clippy -p fnx-algorithms --all-targets -- -D warnings`: exit 0.
  `cargo fmt --check`: clean. `ubs crates/fnx-algorithms/src/lib.rs`: exit 0,
  **0 critical** (the 7266 file-wide warnings are the pre-existing baseline of a
  46k-line file, unchanged by this diff).

## Witness semantics (deliberate, documented)

`ComplexityWitness.nodes_touched` (total reach over all sources) is **identical**
to the per-source path. `edges_scanned` / `queue_peak` now report the work this
kernel actually does — one scan serves up to `W*64` sources — so they sit far
below the per-source sum by design. This is the precedent set by the aspl ship
and is safe: the witness is never compared in `fnx-conformance` (only recorded),
and the Python binding drops it (`centrality_to_dict(..., &result.scores)`).

## Next

`harmonic_centrality` (same reverse-BFS core). Its `harmonic += 1/d` is a float
sum, but BFS pops in non-decreasing `d` and **all addends within a level are the
same value `1/L`**, so replaying `h[s] += 1.0/(L as f64)` once per first-reach
event in ascending `L` reproduces the original addition sequence exactly ⇒
byte-identical. Must be repeated addition, **not** `h += count/L` (different
rounding). Blocker to surface: `harmonic_centrality` has **no criterion bench**
in `algorithm_benchmarks.rs`, so honest A/B requires adding one first.
