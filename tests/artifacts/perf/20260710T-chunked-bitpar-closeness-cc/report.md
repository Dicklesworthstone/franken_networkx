# br-r37-c1-x0jz8 — chunked-parallel bit-parallel BFS for `closeness_centrality` (n >= 500)

**Status: NOT LANDED.** Large repeated win on the target workload; the keep-gate
(cv_pct < 5 on the decisive rows) is NOT met because the shared rch worker drifted
**2.02x on identical code between two invocations**. The lever is correct and
byte-exact — 13/13 tests green — but no honest ship/reject verdict is available
from this substrate today. Patch parked in `lever.patch`.

## Substrate

`rch exec -- cargo bench -p fnx-algorithms --bench algorithm_benchmarks -- closeness_centrality_parallel --sample-size 20 --warm-up-time 1.0 --measurement-time 3.0`,
remote worker `ovh-a`. BOTH arms live in ONE criterion group in ONE binary and ONE
invocation, because rch exposes no `--worker` flag and its ratios are not
worker-invariant (br-r37-c1-839yx). Local disk never moved (89G, `target/` 4.2G).

`per_source` is the pre-lever production path. `chunked_bitpar` forces the
candidate past its gate. `auto` is what a caller would actually get.
`csr_build_only` is a stage-cost probe added specifically to satisfy the
ledger-integrity rule below.

## Results — two invocations, same code

| workload | arm | run 1 | cv | run 2 | cv |
|---|---|---|---|---|---|
| `lowdiam_2000` | `per_source` (ORIG) | 12.598 ms | 1.3% | 25.508 ms | 13.1% |
| `lowdiam_2000` | `chunked_bitpar` | **3.102 ms** | 1.7% | 3.333 ms | 28.8% |
| `lowdiam_2000` | `auto` | 3.051 ms | 20.1% | **2.114 ms** | 2.4% |
| `lowdiam_2000` | `csr_build_only` | — | — | 0.023 ms | 4.7% |
| `grid_1600` (guard) | `per_source` (ORIG) | 3.002 ms | 1.7% | 2.809 ms | 2.2% |
| `grid_1600` | `chunked_bitpar` | 2.229 ms | 2.1% | 2.821 ms | 46.1% |
| `grid_1600` | `auto` | 5.028 ms | 7.3% | 3.331 ms | 5.5% |
| `grid_1600` | `csr_build_only` | — | — | 0.010 ms | 2.2% |

Target row ratio (`per_source / candidate`): **4.06x** (run 1), **12.1x** (run 2,
`auto`). Directionally huge and reproduced. Magnitude uncertain.

## Why no verdict: the substrate, not the lever

`per_source/lowdiam_2000` — unchanged code, unchanged input — measured **12.598 ms
then 25.508 ms across two invocations (2.02x)**. Within a single run, cv ranges
1.3% to 46.1%. Several decisive rows exceed the cv_pct<5 keep-gate. Nothing here
can certify a 5% guard, and the `auto/grid_1600` numbers (0.60x then 0.84x vs
`per_source`) disagree with each other by more than the effect they purport to show.

## LEDGER-INTEGRITY: the mechanism I was about to blame is REFUTED

Per the frankenmermaid `5feb977` alert (a REJECT row is invalid if the code under
test never executed, and every REJECT must carry a self-time figure), two checks
were run BEFORE writing any ledger row.

**1. Did the arm under test actually execute on this input?** The gate's answer
depends on `rayon::current_num_threads()`, which is a property of a remote worker
we do not control. Rather than assume, the decision is pinned by test
`bench_workloads_take_the_path_the_ledger_claims_at_any_thread_count`: for every
thread count 1..=128, `grid_1600` DECLINES and `lowdiam_2000` ACCEPTS. So
`auto/grid_1600` provably ran the per-source fallback and `auto/lowdiam_2000`
provably ran the chunked kernel, on any worker.

**2. Stage cost, measured instead of inferred.** From run 1 I had *inferred*, by
subtracting arm timings, that the reverse-CSR build costs ~2.0 ms and dominated
every bit-parallel arm — a tidy story that explained `auto`'s apparent grid
regression. It is **wrong**. Measured directly, `csr_build_only` (rows collect +
`build_u32_csr`) is **10.0 µs on grid_1600 (0.36% of `per_source`, cv 2.2%)** and
22.5 µs on lowdiam_2000. Adding the probe BFS — one O(V+E) sweep of the same order
— bounds `auto`'s total overhead on a DECLINED graph at well under 1%. Therefore
the observed 0.60x/0.84x `auto/grid_1600` "regressions" **cannot be real**; they
are worker noise, and had I written that REJECT it would have been a fiction
propped up by arithmetic between two noisy numbers.

## Caveat this raises against an EXISTING ledger row

`docs/NEGATIVE_EVIDENCE.md` records, for `average_shortest_path_length`:
*"batch-parallel bit-parallel grid/1600 6.16 ms >> ORIG rayon 1.63 ms"* — a 0.27x
regression, cited since as evidence that bit-parallel loses at n >= 500. Today, on
`closeness_centrality`, the chunked design measures 2.23–2.82 ms on grid_1600
against a 2.81–3.00 ms per-source path: parity or better, nowhere near 0.27x. The
old row measured a DIFFERENT algorithm and a DIFFERENT design (one wide sweep, not
rayon-over-chunks), so it is not evidence against this lever and must not be cited
as such. It carries no self-time figure and predates the integrity rule; it should
be re-measured before anyone leans on it again.

Consequence for the gate: it was built on that row's premise (decline when
`levels >= lanes`). `grid_1600` has ~78 levels against 64 lanes, so it declines —
yet the forced `chunked_bitpar` arm was never actually slower than `per_source`
there. **The gate is likely too conservative and may be leaving a win on the
table.** That is a tuning question, not a correctness one.

## The lever (in `lever.patch`, 588 insertions / 77 deletions)

Rayon fans out one source-CHUNK per task instead of one SOURCE per task. To make
chunks independent, the sinks became stateless markers with an associated `Acc`
type: a sink that borrows one `&mut [T]` for the whole run cannot be split across
tasks. Each chunk now owns disjoint `reached`/`acc` sub-slices and its own scratch,
so every source sees the identical level sequence — and, for `HarmonicSink`, the
identical addend sequence — which is what keeps f64 bit-exact. Both reduced witness
fields (`+`, `max` over integers) are order-free, so rayon's non-deterministic
reduction tree cannot perturb them.

`bitpar_reverse_bfs_batch` now indexes results CHUNK-RELATIVE while still resolving
source NODES absolutely through `s0` — the two indexings are independent, and
`chunked_parallel_matches_sequential_kernel_at_every_lane_width` fails if either is
conflated.

## Correctness (13/13 green, remote)

- chunked == sequential kernel at every lane width 1..8 (`reached` and `sum_dist`)
- all three arms agree **bit-for-bit** (`to_bits`) above the threshold, on a grid
  and on a hub graph
- gate accepts low-diameter, rejects high-diameter, and DECLINES when the probe
  cannot reach every node (one root's eccentricity says nothing about a
  disconnected graph)
- lane-width selection keeps the pool saturated
- the pre-existing `kernel_multi_batch_matches_single_batch` still passes

## What the next session must do

1. Re-run on a quiet worker (or raise `--sample-size` well past 20) until the
   decisive rows clear cv_pct < 5. Only then ship or reject.
2. Consider relaxing the gate: the `levels >= lanes` premise comes from a row that
   measured a different design, and grid_1600 shows no regression when forced.
3. `HarmonicSink` already rides the same refactored kernel, so harmonic and aspl
   are follow-on commits once the gate is settled.
