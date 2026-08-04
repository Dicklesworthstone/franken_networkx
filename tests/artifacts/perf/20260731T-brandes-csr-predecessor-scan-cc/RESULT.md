# br-r37-c1-bcsr — Brandes: CSR adjacency + predecessor-by-scan

KEEP. `betweenness_centrality` was the dominant stage of the whole-job analytics
pass (35-38% of fnx time, ~10x the next stage measured in isolation). The kernel
was already parallel at `cpu/wall` 42; the win here is per-source efficiency, not
more cores.

## What changed

`crates/fnx-algorithms/src/lib.rs`, shared by
`betweenness_centrality_brandes` (both arms) and
`betweenness_centrality_sampled_generic`:

1. **`Vec<Vec<usize>>` adjacency -> flat u32 CSR.** Built once per call by
   `brandes_build_csr` from the *same* `neighbors_iter` + `get_node_index` walk
   the old build used, so the BFS visits neighbours in an unchanged order and
   `sigma[w] += sigma_v` associates identically.
2. **The per-node predecessor lists are gone.** `BrandesScratch` no longer holds
   `predecessors: Vec<Vec<usize>>` — `n` heap rows that were cleared on every one
   of the `n` sources (`n^2` pointer-chasing clears) and pushed to once per tree
   edge. The dependency phase re-derives the same predecessor set by scanning
   `w`'s reverse-CSR row for `distance[v] == distance[w] - 1`.
3. **Reverse CSR by transpose.** `transpose_u32_csr` counting-sorts the forward
   CSR, which yields the neighbour multiset on undirected graphs and true
   in-neighbours on directed ones — one construction, no `is_directed` branch.

## Why it is bit-exact, not merely close

For a fixed `w`, every `v` in its predecessor row is a distinct accumulator (a
repeated `v` from a parallel edge contributes an identical addend), so the order
*within* a predecessor row cannot change any sum. What does matter — the order the
`w`s are popped from the stack, and the source order of the outer reduction — is
untouched. The `(sigma[v] / sigma_w) * (1.0 + delta_w)` expression is preserved
literally; hoisting the division would be a different rounding.

`dist_w > 0` guards the scan: it excludes the source (whose predecessor list is
empty) and stops the `dist_w - 1 == -1` probe from matching unreached nodes,
which carry `distance == -1`.

## Gates

- `betweenness_csr_predecessor_scan_is_bit_identical_to_stored_lists` — new.
  Reimplements the exact pre-change stored-predecessor kernel as a reference and
  asserts `f64::to_bits()` equality. Covers n = 64/499/500/700/1100 (both sides
  of `BRANDES_PARALLEL_THRESHOLD` = 500), undirected **and** directed, all four
  `normalized` x `endpoints` combinations, plus disconnected graphs with isolates.
- `cargo test -p fnx-algorithms --lib` — 960 passed, 0 failed.
- `pytest tests/python` — 49919 passed, 1065 skipped. The 7 failures in
  `test_coverage_gaps.py` are environmental and pre-existing: the generator
  shells out to `python3 -I -c "import networkx"`, and isolated mode excludes
  `~/.local`, where networkx 3.6.1 lives. They fail identically on clean HEAD.
- `scripts/analytics_pass.py 3000 15000 7` — **14/14 stages byte-identical** to
  live NetworkX 3.6.1 in the same invocation.
- `cargo fmt --check` clean, `cargo clippy` clean.

## Measurements

Host `thinkstation1`, AMD Ryzen Threadripper PRO 5975WX, 32 physical / 64 SMT,
NetworkX 3.6.1. Arms interleaved within one window; per-arm median of repeated
calls after a warm-up call (the rayon pool spin-up is real and otherwise lands
entirely on whichever parallel stage runs first).

ELF sha256 of the measured extension:
- baseline (HEAD `ba40f2548`): `6e870e22ddd7a4060c1433789db6f4e8e95f8fbadb79daa55a296874c443f8a3`
- candidate: `f83f1bdda5a6b078ec1614b092b771b55d1c1c1e8de221fc452ffdb81bddcc44`

### betweenness_centrality, isolated, interleaved

| graph | load | HEAD | candidate | ratio |
|---|---:|---:|---:|---:|
| n=3000 m=15000 | 22-34 | `53.08 / 51.45 / 52.19 ms` | `38.72 / 38.60 / 34.74 ms` | **1.37 / 1.33 / 1.50x** |
| n=6000 m=30000 | 17-22 | `177.12 / 175.96 ms` | `116.72 / 114.08 ms` | **1.52 / 1.54x** |
| n=3000 m=60000 | 17-22 | `93.71 / 94.96 ms` | `66.87 / 65.88 ms` | **1.40 / 1.44x** |

The ratio grows with `n`, which is the signature of removing an `n^2` term.

### Whole-job analytics pass, live nx 3.6.1 in the same invocation

`n=3000 m=15000 seed=7`, 14 stages, every stage byte-identical:

    stage                           nx ms     fnx ms     ratio   nx c/w  fnx c/w
    betweenness_centrality        21291.1       28.2    755.3x     1.00    38.00
    ...
    WHOLE JOB                     48045.4       78.7    610.7x

betweenness went **509.6x -> 755.3x** against nx. `nx c/w` pins at 1.00 on every
stage of every row; that flat 1.00 is the capability being measured.

## Tried and reverted in the same beadword — NOT ledger-grade

Slab-backed deltas (one `chunk * n` allocation reused across chunks, one row per
source) **plus** a rayon reduction over disjoint node blocks. Order-preserving,
and the bit-identity gate passed with it in place. Measured 36.5 ms against
29.4 ms for the kept kernel (n=3000 m=15000, cross-binary, three interleaved
rounds) — a 24% regression against the thing it was meant to improve, while
still beating HEAD, which is the shape that ships by accident if only the HEAD
comparison is run.

**Deliberately not written to `docs/NEGATIVE_EVIDENCE.md`.** The ledger gate
(`scripts/perf_ledger_preflight.py`) rejected the row and was right to: the
candidate moved *two* variables at once (allocation strategy and reduction
strategy) and carried no same-invocation A/A null, so it cannot support a
mechanism claim about which one cost the time. Recorded here as a directional
observation only. To make it ledger-grade, split the two changes and run the
in-binary paired A/B with an A/A null, per the `*_ab()` convention already used
elsewhere in this crate.

The reasoning error that motivated it is worth keeping regardless: the slab was
prompted by `cpu/wall` falling 20.31 -> 17.80 between HEAD and the CSR kernel,
read as a serial-reduction Amdahl bottleneck. That pair was measured at **load
average 88**, where oversubscription deflates `cpu/wall` toward 1.0 regardless of
code. Re-measured at load 23-30, HEAD's own `cpu/wall` is **42.2** and the premise
evaporates. Check `/proc/loadavg` before drawing a *structural* conclusion from a
parallelism ratio, not only before quoting a speed.
