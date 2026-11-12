# br-r37-c1-04z53.28 Validation Summary

## Baseline artifacts

- `baseline_pprof.txt`: rch pprof baseline, `per_iter_ms 67.6660`, checksum `993.361081`.
- `baseline_bench_raw.txt`: rch direct baseline, `70.1537 ms/iter`, checksum `2317.842521`.
- `baseline_criterion.txt`: rch Criterion baseline for `closeness_centrality`.
- `baseline_golden.txt`: 1600 full-precision score rows.
- `baseline_golden_sha256.txt`: `3d66193c4860fa5be5dc24548d1343d873bf353ea6daa580c891d820e6eb1009`.

## Candidate artifacts

- `after_golden.txt`: 1600 full-precision score rows, byte-identical to baseline.
- `after_golden_sha256.txt`: `3d66193c4860fa5be5dc24548d1343d873bf353ea6daa580c891d820e6eb1009`.
- `after_bench_raw.txt`: rch direct candidate, `106.5779 ms/iter`, checksum `2317.842521`.
- `after_criterion.txt`: rch Criterion candidate; all three benchmark sizes regressed.

## Revert verification

- `git diff --quiet -- crates/fnx-algorithms/src/lib.rs`: pass after revert.
- No algorithm source code is kept from the rejected lever.
