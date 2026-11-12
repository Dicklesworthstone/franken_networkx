# br-r37-c1-bger9 — chunked-parallel bit-parallel BFS for `average_shortest_path_length`

**Status: NOT SHIPPED. Patch parked in `lever.patch`.** The target row is an enormous,
reproducible win. The `auto` guard regresses ~3% on `grid_1600` in three independent
runs, its ci95 excludes 1.0 every time, and the gate's MEASURED overhead explains at
most a quarter of it. The mechanism is unknown, so nothing lands.

## What the kernel needed: nothing

Unlike the centralities, aspl required no kernel surgery. `bitpar_bfs_batch` already
returns a self-contained `AsplAgg` per batch and writes no shared per-source array, so
the chunks were independent all along. `AsplAgg::merge` is `+` on three integers and
`max` on the fourth — associative AND commutative — so rayon's non-deterministic
reduction tree reproduces the sequential aggregate bit-for-bit, and the
`sum / (n*(n-1))` division that follows is bit-identical too. 10/10 aspl tests green,
including chunked-vs-sequential aggregate equality at every lane width 1..8 (asserting
`sum`, `reached_pairs`, `edges_scanned` AND `queue_peak`, not just the sum).

## Results — `paired_interleaved_ab`, 121 rounds, one rch invocation each

| run | worker | change under test | `lowdiam_2000` auto | `grid_1600` auto (GUARD) | `grid_1600` chunked |
|---|---|---|---|---|---|
| 1 | hz1 | CSR built before the gate | **17.115x** [16.979,17.236] cv 0.39% | **0.961x** [0.952,0.973] cv 0.55% | 1.975x |
| 2 | hz1 | + `gate_overhead_only` arm | 22.412x [20.650,25.419] cv 5.93% | **0.974x** [0.946,0.984] cv 1.02% | 1.926x |
| 3 | hz2 | CSR built only on accept | **7.605x** [7.493,7.685] cv 0.70% | **0.970x** [0.949,0.983] cv 0.94% | 1.078x |

All target rows: 121/121 paired wins. Absolute times differ ~3x between hz1 and hz2 —
which is exactly why only the WITHIN-run paired ratio is quoted.

## Self-time, measured — and it does not add up

`aspl_gate_overhead_cost` is a bench arm that runs **exactly** what `Auto` does before
it decides (u32 CSR build + eccentricity probe) and nothing else:

| workload | gate_overhead_only | per_source baseline | share |
|---|---|---|---|
| `grid_1600` (run 2) | **17.27 µs** | 6.255 ms | **0.28%** |
| `grid_1600` (run 3) | **13.81 µs** | 1.931 ms | **0.71%** |
| `lowdiam_2000` (run 2) | 60.74 µs | 34.34 ms | 0.18% |

The guard regresses **2.6–3.9%**. The gate's entire measured cost is **≤0.71%**. At
least three quarters of the regression is **unattributed**, and per the ledger-integrity
rule it is therefore **not explained**. No mechanism is claimed here.

## A hypothesis that was tested and REFUTED

Hypothesis: the wasted u32 CSR — built before the gate, thrown away on decline —
perturbs the per-source sweep that immediately follows (allocator state, cache).

Fix attempted (run 3): build the adjacency rows ONCE (the per-source fallback needs
them anyway), let the gate probe those rows via a new
`bitpar_probe_eccentricity_rows`, and construct the CSR **only when the gate accepts**.
A declined graph now never builds a CSR at all.

Result: the guard moved 0.961x / 0.974x → **0.970x**. Unchanged. **Hypothesis refuted.**
The restructure also made the forced `chunked_bitpar` arm on grid slower (1.975x →
1.078x), because the accepted path now pays for the adjacency rows *and* the CSR.

This is the second mechanism I have proposed for a guard regression on this lever and
the second one measurement has killed. The first was "the CSR build costs 2 ms",
inferred by subtracting noisy arms (`csr_build_only` measured it at 10.0 µs). Writing
either into the ledger as a REJECT rationale would have been fiction.

Follow-up bead: **br-r37-c1-wkpfc**.

## What the next session must do

1. `perf record` the `auto` arm on `grid_1600` and diff its self-time profile against
   the `per_source` arm. Something costs ~60 µs of a 1.93 ms wall that is neither the
   CSR nor the probe. Until that frame is named, this does not ship.
2. Note the probe is SEQUENTIAL while the baseline is rayon-parallel, so its wall-clock
   share scales as `threads/n`, not `1/n`. That predicts ~0.5% here, not 3% — it is a
   contributor, not the explanation. Do not promote it to a mechanism without a profile.
3. The gate declines `grid_1600` where forced chunked wins (1.078x–1.975x). Same
   finding as closeness (1.503x) and harmonic (1.456x); see br-r37-c1-yy0rp.

Nothing was reverted from the working tree; the patch is captured here so a later
session can re-apply it against a fresh baseline.
