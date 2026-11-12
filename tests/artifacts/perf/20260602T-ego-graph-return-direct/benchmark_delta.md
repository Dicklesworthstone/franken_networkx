# Benchmark Delta: ego_graph Return Path

## Sample Benchmark

- Baseline fnx mean: `0.17297742869704963s`
- After fnx mean: `0.04074702410271851s`
- NetworkX mean: `0.02183564264778397s`
- Sample speedup: `4.245385576730306x`
- Baseline fnx/NetworkX ratio: `7.921792433006525x`
- After fnx/NetworkX ratio: `1.8659771391383724x`

## Hyperfine Benchmark

- Baseline mean: `2.1717935009s`
- After mean: `0.85744852116s`
- Speedup: `2.5328558476745484x`
- Baseline stddev: `0.032029275273254346s`
- After stddev: `0.016791950362190115s`

## Profile Movement

- Baseline profile: `_from_nx_graph` consumed `2.028s` over repeat-10.
- After profile: `_from_nx_graph` is absent from the hot path; remaining time is in the necessary graph construction and normalization path.

## Verdict

Keep. Score is above `2.0`, output sha is unchanged, and the lever is a single return-path rewrite.
