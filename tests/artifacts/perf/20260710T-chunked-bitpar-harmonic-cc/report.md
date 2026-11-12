# br-r37-c1-qdcdq — chunked-parallel bit-parallel BFS for `harmonic_centrality` (n >= 500)

The follow-on to the closeness ship (`1e8a6d2d7`). Harmonic already rode the shared
`ReachSink` kernel, so this wires it onto the chunked-parallel driver and the same
expected-loss gate. `ClosenessArm` is renamed `BitparArm` — both centralities now
share one arm selector rather than duplicating an enum.

## Substrate

`RCH_REQUIRE_REMOTE=1 env -u CARGO_TARGET_DIR rch exec -- cargo bench -p fnx-algorithms`,
worker `ovh-a`. Decision numbers come from `paired_interleaved_ab`: arms alternate
INSIDE one loop (criterion group members run sequentially and do NOT cancel drift),
arm order flips each round, one ratio per adjacent pair, median bootstrapped over
4000 resamples. `cv_pct<5` is applied to the **estimator**, not to individual pairs.
Inputs and results both pass through `black_box`; both arms' scores are compared
bit-for-bit before timing, so a DCE'd arm cannot pass.

## Results — 121 paired rounds

| workload | arm | ratio_med | ci95 | median_cv | win_rate |
|---|---|---|---|---|---|
| `harmonic/lowdiam_2000` | **auto (ships)** | **7.150x** | [7.018, 7.264] | 0.93% | **121/121** |
| `harmonic/lowdiam_2000` | `chunked_bitpar` | 7.366x | [7.226, 7.475] | 0.93% | 121/121 |
| `harmonic/grid_1600` GUARD | **auto (ships)** | **0.989x** | [0.982, 0.995] | 0.34% | 41/121 |
| `harmonic/grid_1600` | `chunked_bitpar` | 1.456x | [1.439, 1.478] | 0.93% | 118/121 |

## The guard regresses ~1.1%, and I am not going to bury it

`harmonic/grid_1600` `auto` is **0.989x with ci95 [0.982, 0.995] — the interval
EXCLUDES 1.0**. That is a certified ~1.1% regression on graphs the gate declines,
which is the price of the gate's own probe. Closeness's guard in the same binary
read 0.997x [0.983, 1.009] (straddling 1.0).

What is MEASURED: `csr_build_only` (rows collect + `build_u32_csr`) is **10.0 us on
grid_1600 = 0.35% of the 2.85 ms per-source arm** (cv 2.2%). The eccentricity probe
is one O(V+E) BFS — the per-source arm runs 1600 of them — so it is a further ~0.1%.
Together that attributes roughly **0.45%** of the 1.1%.

What is NOT measured, and therefore NOT claimed: the residual ~0.65%. Both
centralities build the same CSR, run the same probe, on the same graph, with
near-identical per-source baselines (2.849 ms harmonic vs 2.843 ms closeness), so the
0.989x / 0.997x split between them is **unexplained**. It may be that closeness's
61-round estimate simply could not resolve a cost harmonic's 121-round estimate can;
it may be something else. Attributing it requires a `gate_probe_only` stage arm, the
same instrument that refuted my earlier "the CSR build costs 2 ms" story. Filed with
br-r37-c1-yy0rp.

The trade shipped: **7.150x on low-diameter graphs** — the shape real social,
citation and web workloads have — for ~1.1% on the synthetic high-diameter worst
case. br-r37-c1-yy0rp (reuse the CSR on the declined path) should remove the cost
entirely, and would also let the gate relax, since forced `chunked_bitpar` already
BEATS per-source on grid_1600 by **1.456x** (118/121 pairs) — a graph the gate
declines.

## Correctness

Harmonic sums f64 (`+= 1/d`), so chunking must repartition SOURCES only, never the
addition order within a source. `chunked_parallel_matches_sequential_kernel_at_every_lane_width`
compares `f64::to_bits` per source across lane widths 1..8 on a 24x25 grid — many
levels with varying per-level counts, which is precisely where a reassociated sum
diverges in the low bits. A complete graph cannot detect it (every node at distance
1); that fixture lesson is why the grid is used here.

- all three arms agree bit-for-bit above the threshold, on grid and hub graphs
- `bench_workloads_take_the_path_the_ledger_claims_at_any_thread_count` pins the gate
  decision for EVERY thread count 1..=128, so the ledger can state which path each
  bench row took on any worker (frankenmermaid 5feb977 execution proof)
- 918/918 `fnx-algorithms` lib tests green on `ovh-a`
- `cargo clippy -p fnx-algorithms --all-targets -- -D warnings` clean; `cargo fmt --check` clean

## aspl is NOT included

`average_shortest_path_length` uses a different kernel (`bitpar_bfs_batch`, a global
distance-sum accumulator, not a `ReachSink`). Chunking it requires either converting
it to the `ReachSink` trait or writing a second chunked driver, plus its own gate,
tests and paired rows. That is a separate lever and a separate commit.
