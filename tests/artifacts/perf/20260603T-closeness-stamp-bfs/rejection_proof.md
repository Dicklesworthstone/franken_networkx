# br-r37-c1-04z53.28 Rejection Proof

## Profile-backed target

The bead target was profile-backed before editing:

- `rch exec -- cargo run -q -p fnx-algorithms --profile release-perf --features profile-pprof --bin perf_harness -- --pprof --pprof-top=30 --algo=closeness --n=1600 --deg=5 --iters=3`
- Baseline profile artifact: `baseline_pprof.txt`
- Baseline sample: `closeness_centrality_generic<fnx_classes::Graph>` held 197/197 inclusive samples in the captured run.

## Candidate lever

Replace per-source `Vec<Option<usize>>` distance allocation and fresh queue allocation in `closeness_centrality_generic` with reused `Vec<usize>` distances, a `Vec<usize>` seen-stamp array, and a cleared `VecDeque`.

The candidate preserved reverse adjacency construction and traversal order; only distance storage/reset changed.

## Behavior proof

- Golden baseline rows: 1600.
- Golden after rows: 1600.
- Baseline SHA: `3d66193c4860fa5be5dc24548d1343d873bf353ea6daa580c891d820e6eb1009`.
- Candidate SHA: `3d66193c4860fa5be5dc24548d1343d873bf353ea6daa580c891d820e6eb1009`.
- `cmp` between baseline and candidate golden files: equal.

Ordering, tie-breaking, and floating-point scoring were unchanged in the candidate output. RNG was only used by deterministic harness graph generation and remained the same.

## Performance result

Direct rch sparse harness, `--algo=closeness --n=1600 --deg=5 --iters=7`:

- Baseline: `70.1537 ms/iter`, checksum `2317.842521`.
- Candidate: `106.5779 ms/iter`, checksum `2317.842521`.
- Result: 0.66x, regression.

Criterion rch baseline/after, `closeness_centrality`:

- complete/20: `14.132 us` median -> `34.540 us` median.
- complete/50: `139.22 us` median -> `337.95 us` median.
- complete/100: `922.81 us` median -> `2.3545 ms` median.

## Verdict

Rejected. Score 1.0. Source was reverted exactly; `git diff --quiet -- crates/fnx-algorithms/src/lib.rs` passed after revert.
